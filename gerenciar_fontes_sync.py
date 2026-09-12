import json
import os
import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "sync_config.json"
SOURCE_TYPES = ("Carteira", "Onda", "Reab", "Lojas", "A Extrair")
SUPPORTED = {".xlsx", ".xlsm", ".csv"}

def clean(value):
    return " ".join(unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper().replace("_", " ").split())

def classify(path):
    text = clean(str(path))
    name = clean(path.name)
    if "A EXTRAIR" in text or "AGUARDANDO LIBERACAO" in text: return "A Extrair"
    if "DESTINO REAB" in text or "LOJAS REAB" in text: return "Reab"
    if "ONDA" in name or "\\ONDA\\" in text: return "Onda"
    if "CARTEIRA" in text or "ACOMPANHAMENTO" in name or "PRODUCAO" in name: return "Carteira"
    if "LOJA" in name or "\\LOJAS\\" in text: return "Lojas"
    return None

def database_sources():
    found = {}
    search_root = ROOT.parent
    for database in search_root.glob("**/data/operacional.db"):
        try:
            with sqlite3.connect(database) as connection:
                rows = connection.execute("SELECT name,path FROM sources WHERE enabled=1").fetchall()
            for name, path in rows:
                normalized = next((item for item in SOURCE_TYPES if clean(item) == clean(name)), None)
                if normalized and Path(path).exists(): found[normalized] = str(Path(path))
        except (sqlite3.Error, OSError):
            continue
    return found

def discovery_roots():
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    candidates = [home / "Documents", home / "Documentos", Path("C:/Bases"), ROOT.parent]
    candidates.extend(path for path in home.glob("OneDrive*") if path.is_dir())
    unique = []
    for path in candidates:
        try: resolved = path.resolve()
        except OSError: continue
        if resolved.exists() and resolved not in unique: unique.append(resolved)
    return unique

def discover_sources(existing=None):
    found = {name: path for name, path in (existing or {}).items() if Path(path).exists()}
    found.update(database_sources())
    candidates = {}
    ignored = {".git", ".venv", "node_modules", "appdata", "$recycle.bin", "data"}
    for root in discovery_roots():
        for current, dirs, files in os.walk(root):
            relative_depth = len(Path(current).relative_to(root).parts)
            dirs[:] = [item for item in dirs if item.lower() not in ignored and not item.startswith(".")]
            if relative_depth >= 5: dirs[:] = []
            for filename in files:
                path = Path(current) / filename
                if path.suffix.lower() not in SUPPORTED or filename.startswith("~$"): continue
                source = classify(path)
                if source: candidates.setdefault(source, []).append(path)
    for source, files in candidates.items():
        if source in found: continue
        groups = {}
        for path in files: groups.setdefault(path.parent, []).append(path)
        folder, matches = max(groups.items(), key=lambda item: (len(item[1]), max(p.stat().st_mtime for p in item[1])))
        found[source] = str(folder if len(matches) > 1 else matches[0])
    return found

def save_sources(config, sources):
    config["sources"] = sources
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

def load_config():
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("ERRO: execute primeiro CONFIGURAR_SINCRONIZADOR.bat.")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERRO: sync_config.json inválido: {exc}")
    data.setdefault("sources", {})
    return data

def powershell_dialog(mode):
    if mode == "folder":
        script = r"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Selecionar pasta de dados'
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}
"""
    else:
        script = r"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Selecionar arquivo de dados'
$dialog.Filter = 'Planilhas (*.xlsx;*.xlsm;*.csv)|*.xlsx;*.xlsm;*.csv|Todos os arquivos (*.*)|*.*'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Não foi possível abrir o seletor do Windows: {exc}")
        return ""
    if result.returncode:
        print(result.stderr.strip() or "O seletor do Windows não pôde ser aberto.")
        return ""
    return result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""

def choose_source_type():
    print("\nTIPO DA FONTE")
    for index, name in enumerate(SOURCE_TYPES, 1):
        print(f"  {index}. {name}")
    while True:
        value = input("Escolha o número da fonte: ").strip()
        if value.isdigit() and 1 <= int(value) <= len(SOURCE_TYPES):
            return SOURCE_TYPES[int(value) - 1]
        print("Opção inválida.")

def choose_path():
    print("\nORIGEM DOS DADOS")
    print("  1. Selecionar pasta")
    print("  2. Selecionar arquivo")
    print("  3. Digitar ou colar o caminho")
    while True:
        option = input("Escolha: ").strip()
        if option == "1": return powershell_dialog("folder")
        if option == "2": return powershell_dialog("file")
        if option == "3": return input("Caminho completo: ").strip().strip('"')
        print("Opção inválida.")

def show_sources(sources):
    print("\n" + "=" * 72)
    print("FONTES CADASTRADAS")
    print("=" * 72)
    if not sources: print("Nenhuma fonte cadastrada.")
    for index, (name, path) in enumerate(sources.items(), 1):
        status = "OK" if Path(path).exists() else "CAMINHO NÃO ENCONTRADO"
        print(f"{index}. {name}\n   {path}\n   Status: {status}")

def add_source(sources):
    name = choose_source_type()
    path = choose_path()
    if not path:
        print("Seleção cancelada.")
        return
    if not Path(path).exists():
        print("ERRO: a pasta ou o arquivo informado não existe neste computador.")
        return
    sources[name] = path
    print(f"Fonte {name} adicionada/atualizada.")

def remove_source(sources):
    if not sources:
        print("Não há fontes para remover.")
        return
    names = list(sources)
    value = input("Número da fonte que deseja remover: ").strip()
    if not value.isdigit() or not 1 <= int(value) <= len(names):
        print("Opção inválida.")
        return
    name = names[int(value) - 1]
    sources.pop(name, None)
    print(f"Fonte {name} removida.")

def interactive_main():
    config = load_config()
    sources = dict(config.get("sources") or {})
    print("\nGERENCIADOR LOCAL DE FONTES — LEO MADEIRAS")
    while True:
        show_sources(sources)
        print("\n1. Adicionar ou atualizar fonte")
        print("2. Remover fonte")
        print("3. Salvar e continuar")
        print("4. Cancelar")
        option = input("Escolha: ").strip()
        if option == "1": add_source(sources)
        elif option == "2": remove_source(sources)
        elif option == "3":
            if not sources:
                print("Cadastre pelo menos uma fonte.")
                continue
            save_sources(config, sources)
            print("\nConfiguração salva com sucesso.")
            return
        elif option == "4": raise SystemExit("Configuração cancelada pelo usuário.")
        else: print("Opção inválida.")

def automatic_main():
    config = load_config()
    sources = discover_sources(config.get("sources") or {})
    if not sources:
        raise SystemExit("ERRO: nenhuma planilha compatível foi localizada automaticamente em Documentos, OneDrive, C:\\Bases ou projetos anteriores.")
    save_sources(config, sources)
    print("Fontes localizadas automaticamente:")
    for name, path in sources.items(): print(f"  {name}: {path}")

if __name__ == "__main__":
    interactive_main() if "--interactive" in sys.argv else automatic_main()

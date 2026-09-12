import hashlib
import json
import logging
import os
import sqlite3
import sys
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'sync_config.json';STATE=ROOT/'data'/'sync_state.json';LOG=ROOT/'logs'/'sincronizador.log'
SUPPORTED={'.xlsx','.xlsm','.csv'}
REMOTE_KEYS={'CARTEIRA':'carteira','ONDA':'onda','LOJAS':'lojas','LOJA':'lojas','REAB':'reab','A EXTRAIR':'a-extrair','A_EXTRAIR':'a-extrair','AGUARDANDO LIBERACAO':'a-extrair'}

def process_lock():
    path=ROOT/'data'/'sync_agent.lock';path.parent.mkdir(parents=True,exist_ok=True);handle=path.open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            handle.seek(0);handle.write(b'1');handle.flush();handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (OSError,IOError):handle.close();raise RuntimeError('O sincronizador já está em execução neste computador.')
    return handle

def clean(value):return ' '.join(unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().upper().replace('_',' ').split())

def logger():
    LOG.parent.mkdir(parents=True,exist_ok=True);log=logging.getLogger('operacional-sync')
    if not log.handlers:
        log.setLevel(logging.INFO);formatter=logging.Formatter('%(asctime)s | %(levelname)s | %(message)s','%d/%m/%Y %H:%M:%S');stream=logging.StreamHandler();stream.setFormatter(formatter);file=logging.FileHandler(LOG,encoding='utf-8');file.setFormatter(formatter);log.addHandler(stream);log.addHandler(file)
    return log

def load_json(path,default):
    try:return json.loads(path.read_text('utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return default

def source_files(path_text):
    path=Path(path_text)
    if not path.exists():return []
    files=[path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
    return [p for p in files if p.suffix.lower() in SUPPORTED and not p.name.startswith('~$')]

def database_sources():
    database=ROOT/'data'/'operacional.db'
    if not database.exists():return {}
    with sqlite3.connect(database) as connection:
        rows=connection.execute('SELECT name,path FROM sources WHERE enabled=1').fetchall()
    return {name:path for name,path in rows if clean(name) in REMOTE_KEYS and source_files(path)}

def configured_sources(config,client,server,key,log):
    try:
        response=client.get(f'{server}/api/sync/config',headers={'X-Sync-Key':key});response.raise_for_status()
        remote=response.json().get('sources') or []
        if remote:
            return {item['name']:{'path':item['path'],'revision':item.get('revision',0)} for item in remote if clean(item.get('name')) in REMOTE_KEYS}
    except Exception as exc:
        log.warning('CONFIG_REMOTA_INDISPONIVEL | usando configuração local | erro=%s',exc)
    explicit=config.get('sources') or database_sources()
    return {name:{'path':path,'revision':0} for name,path in explicit.items()}

def fingerprint(files,base):
    digest=hashlib.sha256()
    for path in files:
        relative=path.name if base.is_file() else path.relative_to(base).as_posix();digest.update(relative.encode('utf-8'))
        with path.open('rb') as source:
            while block:=source.read(8*1024*1024):digest.update(block)
    return digest.hexdigest()

def make_archive(files,base):
    handle=tempfile.NamedTemporaryFile(prefix='operacional-sync-',suffix='.zip',delete=False);handle.close();archive=Path(handle.name)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as book:
        for path in files:book.write(path,path.name if base.is_file() else path.relative_to(base).as_posix())
    return archive

def send(client,server,key,name,path_text,previous,log,revision=0):
    remote=REMOTE_KEYS.get(clean(name))
    if not remote:return previous
    base=Path(path_text);files=source_files(path_text)
    if not files:log.warning('FONTE_IGNORADA | fonte=%s | caminho não encontrado ou vazio=%s',name,path_text);return previous
    current=fingerprint(files,base);state_key=f'{current}:{revision}'
    if previous.get(remote)==state_key:log.info('SEM_ALTERACAO | fonte=%s | arquivos=%s',name,len(files));return previous
    archive=make_archive(files,base)
    try:
        package_hash=hashlib.sha256(archive.read_bytes()).hexdigest();log.info('ENVIO_INICIADO | fonte=%s | arquivos=%s | tamanho_mb=%.1f',name,len(files),archive.stat().st_size/1048576)
        with archive.open('rb') as payload:
            response=client.post(f'{server}/api/sync/source/{remote}',headers={'X-Sync-Key':key,'X-Content-SHA256':package_hash},files={'archive':('fonte.zip',payload,'application/zip')})
        response.raise_for_status();body=response.json()
        if not body.get('ok'):raise RuntimeError(body.get('message') or 'Servidor recusou a publicação.')
        previous[remote]=state_key;log.info('ENVIO_CONCLUIDO | fonte=%s | arquivos=%s | %s',name,body.get('files'),body.get('message','publicado'))
        return previous
    finally:archive.unlink(missing_ok=True)

def save_state(state):
    STATE.parent.mkdir(parents=True,exist_ok=True);temporary=STATE.with_suffix('.tmp');temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temporary,STATE)

def run_once(config,log):
    server=str(config.get('server_url','')).strip().rstrip('/');key=str(config.get('api_key','')).strip()
    if not server.startswith('https://'):raise ValueError('Informe no sync_config.json o endereço HTTPS do Railway.')
    if len(key)<24:raise ValueError('A SYNC_API_KEY precisa ter pelo menos 24 caracteres.')
    state=load_json(STATE,{})
    failures=[]
    with httpx.Client(timeout=httpx.Timeout(600,connect=30),follow_redirects=True) as client:
        health=client.get(f'{server}/api/sync/health',headers={'X-Sync-Key':key});health.raise_for_status()
        sources=configured_sources(config,client,server,key,log)
        if not sources:raise ValueError('Nenhuma fonte ativa foi cadastrada na tela Configurações do sistema.')
        for name,source in sources.items():
            try:state=send(client,server,key,name,source['path'],state,log,source.get('revision',0));save_state(state)
            except Exception as exc:
                failures.append(f'{name}: {exc}');log.exception('ENVIO_FALHOU | fonte=%s | erro=%s',name,exc)
    if failures:raise RuntimeError('Falha em uma ou mais fontes: '+'; '.join(failures))

def main():
    lock=process_lock();log=logger();config=load_json(CONFIG,{})
    if not config:raise FileNotFoundError('Execute primeiro CONFIGURAR_SINCRONIZADOR.bat.')
    interval=max(1,int(config.get('interval_minutes',5)));once='--once' in sys.argv
    log.info('SINCRONIZADOR_INICIADO | intervalo_minutos=%s | modo=%s',interval,'único' if once else 'contínuo')
    while True:
        try:run_once(config,log)
        except Exception as exc:
            log.exception('CICLO_FALHOU | erro=%s',exc)
            if once:raise
        if once:return
        log.info('PROXIMA_VERIFICACAO | minutos=%s',interval);time.sleep(interval*60)

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:logger().info('SINCRONIZADOR_ENCERRADO')
    except Exception as exc:logger().error('INICIALIZACAO_FALHOU | erro=%s',exc);raise SystemExit(1)

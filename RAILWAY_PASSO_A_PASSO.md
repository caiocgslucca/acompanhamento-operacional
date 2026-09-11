# Publicar o Acompanhamento Operacional no GitHub e Railway

## 1. Preparar o projeto no computador

O projeto deve permanecer em:

`C:\Projetos\Operacional`

O arquivo `.gitignore` já impede o envio de senhas, banco local, logs, fontes e ambiente Python ao GitHub.

## 2. Criar o repositório no GitHub

Abra o PowerShell dentro de `C:\Projetos\Operacional` e execute:

```powershell
git init
git add .
git commit -m "Publicação inicial do Acompanhamento Operacional"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/acompanhamento-operacional.git
git push -u origin main
```

Se o repositório já existir, não repita `git init` nem `git remote add origin`.

## 3. Criar o projeto no Railway

1. No Railway, escolha **New Project > Deploy from GitHub Repo**.
2. Selecione o repositório `acompanhamento-operacional`.
3. Aguarde o Railway reconhecer o `Dockerfile`.
4. Em **Variables**, crie:

```text
APP_USERNAME=administrador
APP_PASSWORD=CRIE_UMA_SENHA_FORTE
SYNC_API_KEY=CRIE_UMA_CHAVE_ALEATORIA_COM_PELO_MENOS_32_CARACTERES
OPERACIONAL_ROOT=/data/operacional
SYNC_MAX_UPLOAD_MB=250
SYNC_MAX_UNCOMPRESSED_MB=500
```

Não coloque aspas nos valores.

## 4. Preservar os dados

No serviço do Railway, crie um **Volume** montado exatamente em:

`/data`

Sem esse volume, as cargas poderão ser apagadas em uma nova implantação.

## 5. Criar o endereço público

Em **Settings > Networking**, gere um domínio Railway. O endereço terá formato parecido com:

`https://acompanhamento-operacional-production.up.railway.app`

Abra o endereço e confirme a tela de login.

## 6. Ativar o sincronizador no computador

1. Volte para `C:\Projetos\Operacional`.
2. Execute `CONFIGURAR_SINCRONIZADOR.bat`.
3. Informe o endereço HTTPS do Railway.
4. Informe exatamente a mesma `SYNC_API_KEY` criada no Railway.
5. Informe o intervalo, por exemplo `5` minutos.
6. O primeiro envio será executado imediatamente.
7. Ao terminar o teste, o próprio configurador ativa o sincronizador em segundo plano e na inicialização do Windows.

Para acompanhar ao vivo, use `INICIAR_SINCRONIZADOR.bat`. Para remover a inicialização automática, use `REMOVER_SINCRONIZADOR_AUTOMATICO.bat`.

O sincronizador utiliza automaticamente os caminhos cadastrados no banco local `data\operacional.db`. Também é possível informar caminhos manualmente em `sync_config.json`, no campo `sources`:

```json
{
  "sources": {
    "Carteira": "C:\\Users\\Phelipe\\Documents\\Acompanhamento",
    "Onda": "C:\\Users\\Phelipe\\Documents\\Onda",
    "Reab": "C:\\Users\\Phelipe\\Documents\\Lojas Reab",
    "A Extrair": "C:\\Users\\Phelipe\\Documents\\A Extrair"
  }
}
```

## Funcionamento

- O agente calcula a assinatura completa de cada arquivo.
- Arquivos novos, alterados ou com linhas excluídas geram uma nova carga.
- A carga é enviada por HTTPS e protegida pela `SYNC_API_KEY`.
- O servidor valida o pacote e os dados antes da publicação.
- Em caso de erro, a última versão válida continua disponível.
- Se a internet cair, o próximo ciclo tenta novamente.
- O GitHub recebe apenas o código; os arquivos operacionais não são enviados ao repositório.

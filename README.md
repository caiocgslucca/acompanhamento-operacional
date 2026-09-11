# Acompanhamento Operacional — Leo Madeiras

Aplicação web modular em Python para acompanhamento da operação logística. Cada botão do menu abre uma rota própria e cada tela possui seu arquivo `.py` em `app/screens`.

## Tela Reab

A tela **Reab** mantém todas as lojas visíveis, inclusive as sem movimento. O quadro esquerdo apresenta DS por loja somente para a classe `ZCHP`; o direito apresenta todas as classes por loja.

O nome completo pode estar na própria Carteira ou na fonte auxiliar `Reab`/`Lojas`. Na lista importada, o sistema monta o texto usando `NºLoja` + `Loja` (exemplo: `1001 - SP - Gasometro`) e relaciona `NºLoja` com `CD_ROTA NUMBER` da Carteira. A coluna `Filial = 1500` não é tratada como loja.

## Complemento A Extrair

Uma fonte cadastrada como `A Extrair` (ou cujo caminho contenha `A_Extrair`) é unida verticalmente à Carteira porque possui o mesmo esquema operacional. Os registros entram na Carteira e na Reab com o status `AGUARDANDO LIBERAÇÃO`. Os filtros de status disponíveis são `PENDENTE`, `EM SEPARAÇÃO` e `AGUARDANDO LIBERAÇÃO`.

## Login externo

Quando `APP_USERNAME` e `APP_PASSWORD` estiverem configurados pelo iniciador online, o sistema apresenta uma tela de login própria e responsiva. A sessão protegida dura 12 horas e pode ser encerrada pelo link **Sair** no cabeçalho.

## Gerar o executável no Windows

1. Extraia o ZIP em uma pasta local.
2. Execute `GERAR_EXE.bat`.
3. O gerador detecta `py` ou `python`. Se o Python não existir e o Windows permitir, solicita ao `winget` a instalação oficial para o usuário atual.
4. Em seguida, cria `.venv`, instala/atualiza as dependências declaradas e valida todos os componentes essenciais antes de compilar.
5. Ao concluir, abra `dist\Acompanhamento_Operacional` e execute `Acompanhamento_Operacional.exe`.

O EXE inicia o servidor, aguarda a porta 8000 ficar disponível e abre o navegador. Mantenha a janela do executável aberta enquanto utiliza o sistema.

## Acesso online gratuito, sem cartão

Execute `INICIAR_ONLINE_GRATIS.bat`. O iniciador instala o que estiver ausente,
baixa o conector oficial Cloudflare, solicita usuário/senha e mostra um endereço
HTTPS para celular e notebook. Consulte `PASSO_A_PASSO_ONLINE_GRATIS.md`.

## GitHub + Railway + sincronização do computador

Para manter o painel permanentemente online no Railway e continuar lendo as pastas do Windows, use a arquitetura integrada desta versão:

- o Railway hospeda o painel, login e cópias validadas dos dados;
- `sync_agent.py` verifica as fontes cadastradas no computador;
- arquivos novos, editados ou reduzidos são enviados por HTTPS;
- a chave `SYNC_API_KEY` protege o recebimento;
- cargas inválidas são rejeitadas e a última versão válida permanece publicada;
- o sincronizador roda em segundo plano e inicia com o Windows.

O projeto local deve ficar em `C:\Projetos\Operacional`. Consulte `RAILWAY_PASSO_A_PASSO.md`.

## Oracle Cloud VM (Ubuntu)

Esta versão também pode operar 24 horas em uma VM Oracle Cloud. Na nuvem, os
arquivos são sincronizados do SharePoint com `rclone`; a aplicação lê as cópias
em `/sources/carteira` e `/sources/onda`. Docker preserva banco e logs em volume,
reinicia os serviços e executa uma única instância do agendador.

### 1. Preparar a VM

Crie uma VM Ubuntu 24.04 (a forma Ampere A1 gratuita é recomendada), associe um
IP público reservado e libere TCP 22, 80 e 443 na Security List/NSG. Não libere
a porta interna 8000.

Envie e extraia este projeto em `/opt/acompanhamento-operacional` e execute:

```bash
cd /opt/acompanhamento-operacional
sudo bash oracle-cloud/instalar_vm.sh
nano .env
```

Troque `APP_PASSWORD`. Para o primeiro teste por IP mantenha
`APP_ADDRESS=:80`. Para HTTPS, aponte um domínio para o IP da VM e informe esse
domínio em `APP_ADDRESS`.

### 2. Configurar SharePoint

Execute `rclone config`, crie um remoto Microsoft OneDrive chamado
`leomadeiras`, autentique com a conta corporativa e selecione a biblioteca do
site SharePoint correto. Teste com `rclone lsd leomadeiras:`.

Crie `/etc/operacional-sync.env`:

```bash
sudo nano /etc/operacional-sync.env
```

Conteúdo (ajuste os caminhos exibidos pelo `rclone lsd`):

```text
RCLONE_REMOTE=leomadeiras
SHAREPOINT_CARTEIRA_PATH=Logistica/Acompanhamento Produção/Carteira
SHAREPOINT_ONDA_PATH=Logistica/Acompanhamento Produção/Base Onda
```

Faça a primeira sincronização e valide os arquivos:

```bash
set -a; source /etc/operacional-sync.env; set +a
bash oracle-cloud/sincronizar_sharepoint.sh
find sources -maxdepth 2 -type f
```

### 3. Automatizar e iniciar

Os arquivos de serviço assumem usuário `ubuntu` e projeto em
`/opt/acompanhamento-operacional`. Depois execute:

```bash
sudo cp oracle-cloud/operacional-sync.service /etc/systemd/system/
sudo cp oracle-cloud/operacional-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now operacional-sync.timer
bash oracle-cloud/iniciar.sh
docker compose logs -f app
```

Acesse `http://IP_PUBLICO` no teste ou `https://seu-dominio` quando o domínio
estiver configurado. O navegador solicitará o usuário e senha do `.env`.

Comandos de operação:

```bash
docker compose ps
docker compose logs --tail=200 app
docker compose restart app
sudo systemctl status operacional-sync.timer
sudo journalctl -u operacional-sync.service -n 100
```

## Estrutura

- `app/main.py`: inicialização e registro das telas.
- `app/screens/*.py`: uma tela por arquivo.
- `app/services/ui.py`: layout compartilhado.
- `app/services/data_engine.py`: ingestão Polars/Arrow, Parquet e consultas DuckDB.
- `app/services/config_store.py`: configurações persistentes em SQLite e logs técnicos.
- `app/static/style.css`: identidade visual Leo Madeiras.
- `tests/`: testes automáticos de rotas.

## Desenvolvimento

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Para testar: `pytest -q`.

## Configurações e diagnóstico

A tela Configurações permite criar, editar e excluir fontes, selecionar arquivo ou pasta pelo diálogo nativo do Windows, validar acesso, ativar/desativar e forçar atualizações. O seletor usa diretamente o Windows e não depende de `tkinter`. O agendamento aceita execução manual, intervalo livre em minutos ou horas, horário diário e dias específicos da semana. Os dados permanecem em `data/operacional.db`. Toda alteração, execução e erro inesperado é registrado em `logs/operacional.log`, também disponível para leitura e download na própria tela.

## Carteira consolidada

Cadastre duas fontes com os nomes exatos `Carteira` e `Onda`. Cada fonte pode apontar para um arquivo ou para uma pasta com vários arquivos de filiais. Arquivos XLSX, XLSM e CSV com o mesmo padrão de colunas são unidos automaticamente. A Carteira relaciona `CD_ONDA` com a fonte Onda, utiliza `DS_ONDA` nas linhas e soma `QTD_PENDENTE` nas matrizes `DS × Onda` e `Classe × Onda`. Os filtros disponíveis são filial, classe, rota e status da separação.

Antes de abrir arquivos do OneDrive, o sistema cria uma cópia íntegra em `data/staging/sources`. Em bloqueios temporários, realiza novas tentativas e pode usar a última cópia local válida. O sistema não altera atributos do OneDrive e não abre documentos automaticamente. Evite manter o Excel aberto em modo exclusivo durante a primeira carga.

A Carteira oferece filtros multisseleção, relatório PDF, status da carga e informações de última/próxima atualização. A matriz **DS × Onda** aplica a regra fixa da classe **ZCHP**; a matriz **Classe × Onda** respeita as classes escolhidas. O menu lateral pode ser recolhido e mantém a preferência no computador.

## Produção

O protótipo já separa apresentação, telas e dados. Para uso corporativo, configure as fontes reais, autenticação, proxy HTTPS e execução como serviço do Windows. O motor evita reler arquivos inalterados e publica Parquet comprimido para consultas rápidas.

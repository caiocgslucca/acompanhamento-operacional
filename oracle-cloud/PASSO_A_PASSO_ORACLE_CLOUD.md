# Implantação na Oracle Cloud VM

## Resultado final

- Aplicação disponível 24 horas.
- Acesso por celular e notebook.
- Banco, configurações e logs persistentes.
- Carteira e Onda sincronizadas do SharePoint a cada 2 minutos.
- Atualização do painel solicitada imediatamente após cada sincronização.
- Reinício automático após queda ou reinicialização da VM.
- Usuário e senha obrigatórios.
- HTTPS automático quando houver um domínio apontado para a VM.

## 1. Criar a VM gratuita

No Oracle Cloud Console, acesse **Compute > Instances > Create instance**.

1. Nome: `acompanhamento-operacional`.
2. Imagem: Canonical Ubuntu 24.04.
3. Shape: `VM.Standard.A1.Flex`, marcado como Always Free eligible.
4. Configure 2 OCPUs e 12 GB de memória dentro da franquia gratuita.
5. Crie uma VCN/sub-rede pública e marque a atribuição de IPv4 público.
6. Adicione sua chave SSH pública ou baixe a chave privada criada pela Oracle.
7. Crie a instância e anote o IP público.

Reserve esse endereço em **Networking > Reserved Public IPs** para evitar troca
de IP depois que a VM for reiniciada.

## 2. Liberar somente as portas necessárias

Na VCN da VM, abra a Security List ou NSG e crie regras de entrada TCP:

| Porta | Origem | Uso |
|---|---|---|
| 22 | seu IP público `/32` | administração SSH |
| 80 | `0.0.0.0/0` | HTTP e emissão/redirecionamento do certificado |
| 443 | `0.0.0.0/0` | painel HTTPS |

Não abra a porta 8000. Ela fica restrita ao localhost e à rede interna Docker.

## 3. Enviar o projeto

No PowerShell do Windows, dentro da pasta onde está o ZIP:

```powershell
scp -i "C:\Caminho\chave.key" "Acompanhamento_Operacional_Oracle_Cloud_V16.zip" ubuntu@IP_PUBLICO:/home/ubuntu/
```

Entre na VM:

```powershell
ssh -i "C:\Caminho\chave.key" ubuntu@IP_PUBLICO
```

Na VM:

```bash
sudo apt-get update
sudo apt-get install -y unzip
sudo mkdir -p /opt/acompanhamento-operacional
sudo unzip /home/ubuntu/Acompanhamento_Operacional_Oracle_Cloud_V16.zip -d /opt/acompanhamento-operacional
sudo chown -R ubuntu:ubuntu /opt/acompanhamento-operacional
cd /opt/acompanhamento-operacional
sudo bash oracle-cloud/instalar_vm.sh
```

## 4. Configurar usuário, senha e endereço

```bash
cd /opt/acompanhamento-operacional
nano .env
```

Primeiro teste pelo IP:

```text
APP_ADDRESS=:80
APP_USERNAME=administrador
APP_PASSWORD=CrieUmaSenhaForteAqui
CARTEIRA_SCHEDULE={"type":"interval","value":5,"unit":"minuto(s)"}
ONDA_SCHEDULE={"type":"interval","value":5,"unit":"minuto(s)"}
```

Por segurança, não permaneça em HTTP para uso real. Aponte um domínio ou
subdomínio para o IP reservado da VM e altere, por exemplo:

```text
APP_ADDRESS=acompanhamento.seudominio.com.br
```

O Caddy solicitará e renovará o certificado HTTPS automaticamente.

## 5. Configurar a conexão SharePoint

A maneira mais simples é configurar o rclone primeiro no Windows:

1. Instale o rclone no Windows.
2. Execute `rclone config`.
3. Crie um remoto chamado `leomadeiras`.
4. Escolha Microsoft OneDrive.
5. Entre com a conta corporativa.
6. Escolha o site e a biblioteca SharePoint que possuem os arquivos.
7. Teste com `rclone lsd leomadeiras:`.

Copie a configuração para a VM:

```powershell
scp -i "C:\Caminho\chave.key" "$env:APPDATA\rclone\rclone.conf" ubuntu@IP_PUBLICO:/home/ubuntu/
```

Na VM:

```bash
mkdir -p /home/ubuntu/.config/rclone
mv /home/ubuntu/rclone.conf /home/ubuntu/.config/rclone/rclone.conf
chmod 600 /home/ubuntu/.config/rclone/rclone.conf
rclone lsd leomadeiras:
```

Se o login corporativo bloquear o rclone, a TI precisa autorizar o aplicativo
Microsoft Graph ou fornecer uma conta de serviço aprovada. O projeto não tenta
contornar políticas de segurança da empresa.

## 6. Informar as pastas remotas

```bash
sudo nano /etc/operacional-sync.env
```

Exemplo:

```text
RCLONE_REMOTE=leomadeiras
SHAREPOINT_CARTEIRA_PATH=Logistica/Acompanhamento Produção/Carteira
SHAREPOINT_ONDA_PATH=Logistica/Acompanhamento Produção/Base Onda
```

Localize os nomes exatos com:

```bash
rclone lsd leomadeiras:
rclone lsf "leomadeiras:Logistica/Acompanhamento Produção" --max-depth 2
```

Faça a primeira carga:

```bash
cd /opt/acompanhamento-operacional
set -a
source /etc/operacional-sync.env
set +a
bash oracle-cloud/sincronizar_sharepoint.sh
find sources -maxdepth 2 -type f
```

## 7. Iniciar e automatizar

```bash
cd /opt/acompanhamento-operacional
bash oracle-cloud/iniciar.sh
sudo cp oracle-cloud/operacional-sync.service /etc/systemd/system/
sudo cp oracle-cloud/operacional-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now operacional-sync.timer
```

Valide:

```bash
docker compose ps
curl http://127.0.0.1:8000/api/health
sudo systemctl list-timers operacional-sync.timer
sudo journalctl -u operacional-sync.service -n 100 --no-pager
```

Abra `http://IP_PUBLICO` durante o teste ou o endereço HTTPS configurado. O
navegador solicitará as credenciais definidas no `.env`.

## 8. Atualizações e manutenção

Após enviar uma versão nova para a mesma pasta:

```bash
cd /opt/acompanhamento-operacional
docker compose up -d --build
docker compose logs --tail=200 app
```

Backup do banco e configurações:

```bash
docker run --rm -v acompanhamento_operacional_operacional_data:/dados -v "$PWD":/backup alpine tar czf /backup/backup-operacional.tgz -C /dados .
```

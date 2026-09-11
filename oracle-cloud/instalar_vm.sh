#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Execute com: sudo bash oracle-cloud/instalar_vm.sh"; exit 1; fi
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
apt-get update
apt-get install -y ca-certificates curl gnupg rclone
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
mkdir -p "$PROJECT_DIR/sources/carteira" "$PROJECT_DIR/sources/onda"
chown -R "${SUDO_USER:-ubuntu}:${SUDO_USER:-ubuntu}" "$PROJECT_DIR/sources"
if [ ! -f "$PROJECT_DIR/.env" ]; then
  cp "$PROJECT_DIR/.env.oracle.example" "$PROJECT_DIR/.env"
  echo "Arquivo .env criado. Troque obrigatoriamente APP_PASSWORD antes de iniciar."
fi
systemctl enable --now docker
echo "Dependências instaladas. Próximo passo: nano $PROJECT_DIR/.env"

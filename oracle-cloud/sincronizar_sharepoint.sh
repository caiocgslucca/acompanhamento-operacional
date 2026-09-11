#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_NAME="${RCLONE_REMOTE:-leomadeiras}"
: "${SHAREPOINT_CARTEIRA_PATH:?Defina SHAREPOINT_CARTEIRA_PATH em /etc/operacional-sync.env}"
: "${SHAREPOINT_ONDA_PATH:?Defina SHAREPOINT_ONDA_PATH em /etc/operacional-sync.env}"
mkdir -p "$PROJECT_DIR/sources/carteira" "$PROJECT_DIR/sources/onda"
rclone sync "${REMOTE_NAME}:${SHAREPOINT_CARTEIRA_PATH}" "$PROJECT_DIR/sources/carteira" --create-empty-src-dirs --delete-after --transfers 4 --checkers 8
rclone sync "${REMOTE_NAME}:${SHAREPOINT_ONDA_PATH}" "$PROJECT_DIR/sources/onda" --create-empty-src-dirs --delete-after --transfers 4 --checkers 8

# Após publicar os arquivos locais, solicita uma consolidação imediata. A porta
# 8000 está disponível somente no localhost da VM, não na Internet.
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
  curl -fsS --max-time 10 --user "${APP_USERNAME}:${APP_PASSWORD}" -X POST http://127.0.0.1:8000/api/carteira/refresh >/dev/null || true
fi

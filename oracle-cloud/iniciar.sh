#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
if grep -q '^APP_PASSWORD=troque-por-uma-senha-forte$' .env 2>/dev/null; then
  echo "Defina uma senha forte no arquivo .env antes de iniciar."; exit 1
fi
docker compose up -d --build
docker compose ps
echo "Aplicação iniciada. Logs: docker compose logs -f app"

#!/usr/bin/env bash
# Wrapper do smoke test do domínio Vendas — para Git Bash / Linux / macOS / WSL.
# Uso: scripts/run_smoke.sh
#
# Pré-requisitos: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d rodando.
# Lê JWT_SECRET do .env na raiz (gitignored). Sai com o exit code do smoke test.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# 1. Confirmar que a stack está de pé.
if ! docker ps --format '{{.Names}}' | grep -q '^negociacao-service$'; then
    echo "ERRO: container 'negociacao-service' não está rodando."
    echo "      Suba a stack antes: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d"
    exit 1
fi

# 2. Pegar JWT_SECRET — preferência: .env local; fallback: env var já definida.
if [[ -z "${JWT_SECRET:-}" ]] && [[ -f .env ]]; then
    JWT_SECRET="$(grep '^JWT_SECRET=' .env | head -n1 | cut -d= -f2-)"
fi
if [[ -z "${JWT_SECRET:-}" ]]; then
    echo "ERRO: JWT_SECRET não definido. Crie .env (cp .env.local .env) ou exporte JWT_SECRET."
    exit 1
fi

# 3. Desligar tradução automática de path do Git Bash (Windows) para que /tmp não
#    vire C:\Users\...\Temp\.
export MSYS_NO_PATHCONV=1

# 4. Copiar e executar.
echo "Copiando smoke_test.py para o container..."
docker cp scripts/smoke_test.py negociacao-service:/tmp/smoke.py

echo "Executando smoke test..."
docker exec -e JWT_SECRET="$JWT_SECRET" negociacao-service python /tmp/smoke.py

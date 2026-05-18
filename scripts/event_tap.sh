#!/usr/bin/env bash
# Wrapper do event_tap.py para Git Bash / Linux / macOS / WSL.
# Copia o script para o container negociacao-service e roda.
#
# Uso:
#     ./scripts/event_tap.sh                        # todos os tópicos
#     ./scripts/event_tap.sh negociacao_fechada     # filtra um
#
# Pré-requisito: docker compose up -d.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if ! docker ps --format '{{.Names}}' | grep -qx 'negociacao-service'; then
  echo "ERRO: container negociacao-service nao esta rodando." >&2
  echo "      Suba a stack antes: docker compose up -d" >&2
  exit 1
fi

# MSYS_NO_PATHCONV evita Git Bash traduzir /tmp/event_tap.py para C:\tmp\...
MSYS_NO_PATHCONV=1 docker cp scripts/event_tap.py negociacao-service:/tmp/event_tap.py
MSYS_NO_PATHCONV=1 docker exec -i -e SMOKE_KAFKA=redpanda:9092 \
    negociacao-service python /tmp/event_tap.py "$@"

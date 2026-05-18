#!/usr/bin/env bash
# Wrapper do event_publish.py para Git Bash / Linux / macOS / WSL.
#
# Uso:
#     ./scripts/event_publish.sh <topico> <fixture.json> [--no-wrap]
# Exemplo:
#     ./scripts/event_publish.sh demanda_criada docs/integration/fixtures/demanda_criada.example.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [[ $# -lt 2 ]]; then
  echo "Uso: $0 <topico> <fixture.json> [--no-wrap]" >&2
  exit 2
fi

if ! docker ps --format '{{.Names}}' | grep -qx 'negociacao-service'; then
  echo "ERRO: container negociacao-service nao esta rodando." >&2
  echo "      Suba a stack antes: docker compose up -d" >&2
  exit 1
fi

topic="$1"
fixture_host="$2"
fixture_base="$(basename "$fixture_host")"
shift 2

MSYS_NO_PATHCONV=1 docker cp scripts/event_publish.py negociacao-service:/tmp/event_publish.py
MSYS_NO_PATHCONV=1 docker cp "$fixture_host" "negociacao-service:/tmp/$fixture_base"
MSYS_NO_PATHCONV=1 docker exec -i -e SMOKE_KAFKA=redpanda:9092 \
    negociacao-service python /tmp/event_publish.py "$topic" "/tmp/$fixture_base" "$@"

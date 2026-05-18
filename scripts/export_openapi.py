"""Exporta snapshot OpenAPI dos dois microsserviços para `docs/contracts/`.

Roda dentro dos containers via `docker exec` para reaproveitar o ambiente que
já tem todas as deps (`fastapi`, `pydantic`, etc.). Requer `docker compose up -d`
ativo com os containers `mercado-service` e `negociacao-service` no ar.

Saída:
    docs/contracts/mercado.openapi.json
    docs/contracts/negociacao.openapi.json

Use depois em qualquer gerador de cliente (openapi-typescript, orval, etc.).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "contracts"

PY = (
    "import json, sys; "
    "from app.main import app; "
    "sys.stdout.write(json.dumps(app.openapi(), indent=2, ensure_ascii=False))"
)


def export(container: str, output: str) -> None:
    print(f"[*] {container} -> docs/contracts/{output}")
    result = subprocess.run(
        ["docker", "exec", container, "python", "-c", PY],
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"    FALHA (exit={result.returncode}):", file=sys.stderr)
        print(result.stderr.rstrip(), file=sys.stderr)
        sys.exit(2)
    target = DOCS / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.stdout.rstrip() + "\n", encoding="utf-8")
    print(f"    ok ({len(result.stdout):,} bytes)")


def main() -> int:
    print("Exportando snapshots OpenAPI (requer `docker compose up -d`).\n")
    export("mercado-service", "mercado.openapi.json")
    export("negociacao-service", "negociacao.openapi.json")
    print("\nOK. Versione `docs/contracts/*.openapi.json` no Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""gen_jwt.py - gera um JWT de dev para abrir os fronts (mercado-web / negociacao-web).

Uso (host, com .env na raiz):
    python scripts/gen_jwt.py
    python scripts/gen_jwt.py --role FORNECEDOR
    python scripts/gen_jwt.py --empresa-id 11111111-1111-1111-1111-111111111111

Uso (dentro do container, herdando o env_file do compose):
    docker exec negociacao-service python /tmp/gen_jwt.py
    # se precisar copiar: docker cp scripts/gen_jwt.py negociacao-service:/tmp/gen_jwt.py

Le JWT_SECRET, JWT_ISSUER e JWT_AUDIENCE de os.environ (prioridade) ou .env na raiz.
Imprime o token e as URLs prontas para colar no navegador.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import jwt


ROOT = Path(__file__).resolve().parent.parent


def _read_env(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    out: dict[str, str] = {}
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


def _lookup(env_file: dict[str, str], key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or env_file.get(key) or default


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera JWT de dev para abrir mercado-web e negociacao-web."
    )
    parser.add_argument("--empresa-id", default=None, help="UUID da empresa (default: random)")
    parser.add_argument("--role", default="COMPRADOR", help="Role no JWT (default: COMPRADOR)")
    parser.add_argument("--ttl-hours", type=int, default=8, help="Validade em horas (default: 8)")
    args = parser.parse_args()

    env_file = _read_env(ROOT / ".env")
    secret = _lookup(env_file, "JWT_SECRET")
    if not secret:
        print(
            "ERRO: JWT_SECRET nao encontrado. Defina via .env na raiz ou via 'docker exec -e JWT_SECRET=...'.",
            file=sys.stderr,
        )
        return 1
    issuer = _lookup(env_file, "JWT_ISSUER", "portal-autenticacao")
    audience = _lookup(env_file, "JWT_AUDIENCE", "portal-b2b")

    empresa_id = args.empresa_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uuid.uuid4()),
        "empresa_id": empresa_id,
        "email": "dev@local.test",
        "name": "Dev User",
        "role": args.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=args.ttl_hours)).timestamp()),
        "iss": issuer,
        "aud": audience,
    }
    token = jwt.encode(claims, secret, algorithm="HS256")

    print()
    print(f"JWT gerado (HS256, valido por {args.ttl_hours}h):")
    print(token)
    print()
    print(f"empresa_id: {empresa_id}")
    print(f"role:       {args.role}")
    print()
    print("Abra os fronts:")
    print(f"  Mercado     -> http://localhost:3005/?jwt={token}")
    print(f"  Negociacao  -> http://localhost:3006/?jwt={token}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

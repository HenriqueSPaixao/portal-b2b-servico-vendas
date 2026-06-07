"""Minta um JWT de dev para acessar as UIs locais (mercado-web / negociacao-web).

Roda DENTRO do container negociacao-service, que já tem `python-jose` e o
`JWT_SECRET` no ambiente (mesmo segredo que os serviços usam para validar):

    docker cp scripts/mint_jwt.py negociacao-service:/tmp/mint_jwt.py
    docker exec negociacao-service python /tmp/mint_jwt.py
    docker exec negociacao-service python /tmp/mint_jwt.py <empresa_id>          # empresa específica
    docker exec negociacao-service python /tmp/mint_jwt.py <empresa_id> COMPRADOR  # papel de comprador

Imprime só o token. Use assim no navegador (vale 24h):

    http://localhost:8085/?jwt=<token>     # mercado-web (painel do fornecedor)
    http://localhost:8086/?jwt=<token>     # negociacao-web (chat de lances)

Dica: para ver uma PROPOSTA PENDENTE no painel do fornecedor, o `empresa_id`
do token precisa ser o do fornecedor dono da oferta (o `GET /propostas` filtra
por ele). Passe esse UUID como argumento.
"""

import os
import sys
import time
import uuid

from jose import jwt

empresa_id = sys.argv[1] if len(sys.argv) > 1 else str(uuid.uuid4())
role = sys.argv[2] if len(sys.argv) > 2 else "FORNECEDOR"

secret = os.environ.get("JWT_SECRET")
if not secret:
    sys.exit(
        "JWT_SECRET ausente no container. Rode passando explicitamente:\n"
        "  docker exec -e JWT_SECRET=<seu_secret> negociacao-service python /tmp/mint_jwt.py"
    )

issuer = os.environ.get("JWT_ISSUER", "portal-autenticacao")
audience = os.environ.get("JWT_AUDIENCE", "portal-b2b")
now = int(time.time())

claims = {
    "sub": str(uuid.uuid4()),
    "empresa_id": empresa_id,
    "email": "dev@local.dev",
    "name": "Dev Local",
    "role": role,
    "iat": now,
    "exp": now + 86400,  # 24h
    "iss": issuer,
    "aud": audience,
}

print(jwt.encode(claims, secret, algorithm="HS256"))

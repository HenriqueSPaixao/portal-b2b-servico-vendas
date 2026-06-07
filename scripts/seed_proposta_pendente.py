"""Cria UMA proposta pendente de leilão direto — para demonstrar o gate ao vivo.

- Semeia no banco (produto + empresas) para satisfazer as FKs do negociacao-service
  (necessário se você clicar "Abrir leilão" depois).
- Publica no Kafka: produto_cadastrado + 2 demanda_criada + 1 fornecimento_criado
  (demanda 160 > oferta 50 → leilao_direto).
- NÃO confirma: a proposta fica PENDENTE no painel do mercado-web, esperando o
  "sim/não" do fornecedor.

Saída:
  - stdout: SÓ o empresa_id do fornecedor (para casar com o token do mint_jwt).
  - stderr: progresso legível.

Rodar dentro do container negociacao-service (tem asyncpg / aiokafka / orjson):

    docker cp scripts/seed_proposta_pendente.py negociacao-service:/tmp/seed.py
    docker exec negociacao-service python /tmp/seed.py
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import asyncpg
import orjson
from aiokafka import AIOKafkaProducer

DB_URL = os.environ.get(
    "SMOKE_DB_URL",
    "postgresql://postgres:postgres_admin_local@postgres:5432/portal_b2b",
)
KAFKA = os.environ.get("SMOKE_KAFKA", "redpanda:9092")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env(event_type: str, payload: dict) -> dict:
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "eventVersion": "1.0",
        "timestamp": _now_iso(),
        "source": "seed-demo",
        "correlationId": str(uuid.uuid4()),
        "payload": payload,
    }


async def seed_db(conn: asyncpg.Connection, tag: str):
    async def ensure(table: str, where: dict, extra: dict):
        keys = list(where)
        wsql = " AND ".join(f"{k}=${i+1}" for i, k in enumerate(keys))
        row = await conn.fetchrow(
            f"SELECT id FROM portal_b2b.{table} WHERE {wsql}", *where.values()
        )
        if row:
            return row["id"]
        cols = keys + list(extra)
        vals = list(where.values()) + list(extra.values())
        ph = ", ".join(f"${i+1}" for i in range(len(cols)))
        return await conn.fetchval(
            f"INSERT INTO portal_b2b.{table} ({', '.join(cols)}) "
            f"VALUES ({ph}) RETURNING id",
            *vals,
        )

    now = datetime.now(timezone.utc)
    transporte = await ensure("produtos_transporte", {"nome": "DEMO_TRANSPORTE"}, {"data_cadastro": now})
    categoria = await ensure("produtos_categoria", {"nome": "DEMO_CATEGORIA"}, {"data_cadastro": now})
    unidade = await ensure(
        "produtos_unidade_medida", {"nome": "DEMO_UNIDADE"}, {"sigla": "DMO", "data_cadastro": now}
    )
    nome = f"Produto Demo Gate {tag}"
    produto = await conn.fetchval(
        "INSERT INTO portal_b2b.produtos_produto "
        "(transporte_id, categoria_id, unidade_medida_id, codigo, nome, data_cadastro) "
        "VALUES ($1, $2, $3, $4, $5, NOW()) RETURNING id",
        transporte, categoria, unidade, f"DEMO-{tag}", nome,
    )

    async def empresa(cnpj: str, email: str, razao: str):
        row = await conn.fetchrow("SELECT id FROM portal_b2b.empresa WHERE cnpj=$1", cnpj)
        if row:
            return row["id"]
        return await conn.fetchval(
            "INSERT INTO portal_b2b.empresa (razao_social, cnpj, email, data_cadastro) "
            "VALUES ($1, $2, $3, NOW()) RETURNING id",
            razao, cnpj, email,
        )

    fornecedor = await empresa("00000000000001", "fornA@smoke.local", "Fornecedor A")
    comp_a = await empresa("00000000000003", "compA@smoke.local", "Comprador A")
    comp_b = await empresa("00000000000004", "compB@smoke.local", "Comprador B")
    return produto, fornecedor, comp_a, comp_b, nome


async def main() -> None:
    tag = datetime.now(timezone.utc).strftime("%H%M%S")

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)
    async with pool.acquire() as conn:
        produto, fornecedor, comp_a, comp_b, nome = await seed_db(conn, tag)
    await pool.close()
    log(f"Banco semeado: produto='{nome}'  fornecedor={fornecedor}")

    producer = AIOKafkaProducer(bootstrap_servers=KAFKA, acks="all", enable_idempotence=True)
    await producer.start()

    async def pub(topic: str, env: dict) -> None:
        await producer.send_and_wait(topic, orjson.dumps(env))
        log(f"  → {topic}")

    try:
        await pub("produto_cadastrado", _env("produto_cadastrado", {
            "id": str(produto), "codigo": f"DEMO-{tag}", "nome": nome, "ativo": True,
        }))
        await asyncio.sleep(1.0)
        for comp in (comp_a, comp_b):
            await pub("demanda_criada", _env("demanda_criada", {
                "id_demanda": str(uuid.uuid4()), "id_produto": str(produto),
                "id_empresa_comprador": str(comp),
                "quantidade_desejada": "80", "preco_maximo": "15.00",
            }))
        await asyncio.sleep(1.0)
        await pub("fornecimento_criado", _env("fornecimento_criado", {
            "id": str(uuid.uuid4()), "produto_id": str(produto),
            "empresa_fornecedor_id": str(fornecedor),
            "quantidade_disponivel": "50", "preco_unitario": "10.00",
        }))
    finally:
        await producer.stop()

    log("\nProposta PENDENTE criada (leilao_direto). Em ~5s ela aparece no painel.")
    log("Empresas deste leilao:")
    log(f"  FORNECEDOR (abre/recusa no mercado-web) = {fornecedor}")
    log(f"  COMPRADOR A (da lance no chat)          = {comp_a}")
    log(f"  COMPRADOR B (da lance no chat)          = {comp_b}")
    log("\nExemplos de token:")
    log(f"  docker exec negociacao-service python /tmp/mint_jwt.py {fornecedor}")
    log(f"  docker exec negociacao-service python /tmp/mint_jwt.py {comp_a} COMPRADOR")

    # stdout: só o id do fornecedor, para captura automática no PowerShell.
    print(str(fornecedor))


if __name__ == "__main__":
    asyncio.run(main())

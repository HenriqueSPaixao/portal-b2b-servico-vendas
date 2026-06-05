"""Smoke test end-to-end do domínio Vendas (mercado-service + negociacao-service).

Rodar dentro do container `negociacao-service` (já tem todas as deps):

    docker cp scripts/smoke_test.py negociacao-service:/tmp/smoke.py
    docker exec -e JWT_SECRET=... negociacao-service python /tmp/smoke.py

Variáveis de ambiente esperadas (defaults para dev local com docker-compose.local.yml):
- SMOKE_DB_URL       postgresql://postgres:postgres_admin_local@postgres:5432/portal_b2b
- SMOKE_KAFKA        redpanda:9092
- SMOKE_NEGOCIACAO   http://negociacao-service:5006
- JWT_SECRET         (mesmo valor do .env do negociacao-service)
- JWT_ISSUER         portal-autenticacao
- JWT_AUDIENCE       portal-b2b

Cobre 3 cenários:
A) Modo direto      — oferta ≈ demanda → fechamento imediato.
B) Leilão direto    — demanda > oferta → compradores competem (POST /lances).
C) Leilão reverso   — oferta > demanda → fornecedores competem (POST /lances).

Saída: imprime tabela de resultados e exit code 0 se todos passam, !=0 se algum falha.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import asyncpg
import orjson
import urllib.request
import urllib.error
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from jose import jwt as pyjwt


DB_URL = os.environ.get(
    "SMOKE_DB_URL",
    "postgresql://postgres:postgres_admin_local@postgres:5432/portal_b2b",
)
KAFKA = os.environ.get("SMOKE_KAFKA", "redpanda:9092")
NEGOCIACAO_URL = os.environ.get("SMOKE_NEGOCIACAO", "http://negociacao-service:5006")
MERCADO_URL = os.environ.get("SMOKE_MERCADO", "http://mercado-service:5005")
JWT_SECRET = os.environ.get("JWT_SECRET", "DAJNjnbdaibndiuabdwqbiib24141F15n5j1n")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "portal-autenticacao")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "portal-b2b")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _envelope(event_type: str, payload: dict, source: str = "smoke-test") -> dict:
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "eventVersion": "1.0",
        "timestamp": _now_iso(),
        "source": source,
        "correlationId": str(uuid.uuid4()),
        "payload": payload,
    }


def _make_jwt(empresa_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc).timestamp()
    claims = {
        "sub": str(uuid.uuid4()),
        "empresa_id": str(empresa_id),
        "email": "smoke@test.local",
        "name": "Smoke Test User",
        "role": "COMPRADOR",
        "iat": int(now),
        "exp": int(now) + 3600,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return pyjwt.encode(claims, JWT_SECRET, algorithm="HS256")


async def seed_base_data(conn: asyncpg.Connection, run_tag: str) -> dict[str, uuid.UUID]:
    """Cria registros mínimos para satisfazer FKs (transporte/categoria/unidade/produto/empresas).

    `run_tag` é sufixo único (timestamp) usado para garantir produtos novos por execução —
    isso é o que isola cada run do smoke test do estado pré-existente no banco.
    """

    async def ensure(table: str, where: dict, insert_extra: dict) -> uuid.UUID:
        where_sql = " AND ".join(f"{k} = ${i+1}" for i, k in enumerate(where.keys()))
        row = await conn.fetchrow(
            f"SELECT id FROM portal_b2b.{table} WHERE {where_sql}",
            *where.values(),
        )
        if row:
            return row["id"]
        cols = list(where.keys()) + list(insert_extra.keys())
        vals = list(where.values()) + list(insert_extra.values())
        placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
        new_id = await conn.fetchval(
            f"INSERT INTO portal_b2b.{table} ({', '.join(cols)}) "
            f"VALUES ({placeholders}) RETURNING id",
            *vals,
        )
        return new_id

    transporte_id = await ensure(
        "produtos_transporte",
        {"nome": "SMOKE_TRANSPORTE"},
        {"data_cadastro": datetime.now(timezone.utc)},
    )
    categoria_id = await ensure(
        "produtos_categoria",
        {"nome": "SMOKE_CATEGORIA"},
        {"data_cadastro": datetime.now(timezone.utc)},
    )
    unidade_id = await ensure(
        "produtos_unidade_medida",
        {"nome": "SMOKE_UNIDADE"},
        {"sigla": "SMK", "data_cadastro": datetime.now(timezone.utc)},
    )

    async def ensure_produto(codigo: str) -> uuid.UUID:
        row = await conn.fetchrow(
            "SELECT id FROM portal_b2b.produtos_produto WHERE codigo=$1", codigo
        )
        if row:
            return row["id"]
        return await conn.fetchval(
            """
            INSERT INTO portal_b2b.produtos_produto
                (transporte_id, categoria_id, unidade_medida_id, codigo, nome, data_cadastro)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING id
            """,
            transporte_id,
            categoria_id,
            unidade_id,
            codigo,
            f"Produto {codigo}",
        )

    async def ensure_empresa(cnpj: str, email: str, nome: str) -> uuid.UUID:
        row = await conn.fetchrow(
            "SELECT id FROM portal_b2b.empresa WHERE cnpj=$1", cnpj
        )
        if row:
            return row["id"]
        return await conn.fetchval(
            """
            INSERT INTO portal_b2b.empresa (razao_social, cnpj, email, data_cadastro)
            VALUES ($1, $2, $3, NOW())
            RETURNING id
            """,
            nome,
            cnpj,
            email,
        )

    produto_a = await ensure_produto(f"SMOKE-A-{run_tag}")
    produto_b = await ensure_produto(f"SMOKE-B-{run_tag}")
    produto_c = await ensure_produto(f"SMOKE-C-{run_tag}")
    produto_d = await ensure_produto(f"SMOKE-D-{run_tag}")
    fornecedor_a = await ensure_empresa("00000000000001", "fornA@smoke.local", "Fornecedor A")
    fornecedor_b = await ensure_empresa("00000000000002", "fornB@smoke.local", "Fornecedor B")
    comprador_a = await ensure_empresa("00000000000003", "compA@smoke.local", "Comprador A")
    comprador_b = await ensure_empresa("00000000000004", "compB@smoke.local", "Comprador B")

    return {
        "produto_a": produto_a,
        "produto_b": produto_b,
        "produto_c": produto_c,
        "produto_d": produto_d,
        "fornecedor_a": fornecedor_a,
        "fornecedor_b": fornecedor_b,
        "comprador_a": comprador_a,
        "comprador_b": comprador_b,
    }


async def publish(producer: AIOKafkaProducer, topic: str, env: dict) -> None:
    await producer.send_and_wait(topic, orjson.dumps(env))
    print(f"  → published {topic} (eventType={env['eventType']})", flush=True)


async def publish_produtos_cadastrados(
    producer: AIOKafkaProducer,
    ids: dict[str, uuid.UUID],
    run_tag: str,
) -> None:
    """Publica produto_cadastrado para os 3 produtos do smoke, no formato camelCase
    do produtos-service (Raíky). Alimenta o ProdutoCache do mercado-service
    para que GET /processos retorne produto_nome preenchido.
    """
    nomes = {
        "produto_a": f"Produto Smoke A {run_tag}",
        "produto_b": f"Produto Smoke B {run_tag}",
        "produto_c": f"Produto Smoke C {run_tag}",
        "produto_d": f"Produto Smoke D {run_tag}",
    }
    for key, produto_id in ids.items():
        if not key.startswith("produto_"):
            continue
        await publish(
            producer,
            "produto_cadastrado",
            _envelope(
                "produto_cadastrado",
                {
                    "id": str(produto_id),
                    "codigo": f"SMOKE-{key[-1].upper()}-{run_tag}",
                    "nome": nomes[key],
                    "ativo": True,
                    "dataCadastro": _now_iso(),
                },
                source="smoke-test/produtos",
            ),
        )
    # dá tempo do mercado-service consumir antes dos cenários publicarem
    # fornecimento_criado/demanda_criada (que disparam o matching e a montagem
    # do processo, que já vai precisar do nome no GET /processos).
    await asyncio.sleep(1.5)


def fetch_processos_mercado() -> list[dict]:
    """GET /processos do mercado-service com JWT smoke. Usado para assert
    de produto_nome no fim do smoke."""
    token = _make_jwt(uuid.uuid4())
    req = urllib.request.Request(
        f"{MERCADO_URL}/processos",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return [{"_http_error": exc.code, "_body": exc.read().decode()}]


def validar_produto_nome_enriquecido(
    ids: dict[str, uuid.UUID],
) -> dict:
    """Confirma que GET /processos do mercado-service retorna produto_nome
    preenchido — prova que o consumer de produto_cadastrado + o ProdutoCache
    + a rota enriquecida estão wired corretamente."""
    print("\n=== Validação: produto_nome enriquecido em GET /processos ===", flush=True)
    processos = fetch_processos_mercado()
    if processos and isinstance(processos[0], dict) and "_http_error" in processos[0]:
        return {
            "ok": False,
            "erro": f"GET /processos falhou: {processos[0]['_http_error']} {processos[0]['_body']}",
        }
    alvo_ids = {str(ids[k]) for k in ("produto_a", "produto_b", "produto_c") if k in ids}
    matches = [p for p in processos if p.get("produto_id") in alvo_ids]
    if not matches:
        return {
            "ok": False,
            "erro": "Nenhum processo dos produtos do smoke voltou em /processos",
        }
    faltando = [p for p in matches if not p.get("produto_nome")]
    if faltando:
        return {
            "ok": False,
            "erro": (
                f"{len(faltando)} processo(s) com produto_nome ausente "
                f"(produto_ids={[p['produto_id'] for p in faltando]})"
            ),
        }
    print(
        f"  OK: {len(matches)} processo(s) com produto_nome preenchido. "
        f"Exemplos: {[(p['produto_nome'], p['produto_id'][:8]) for p in matches[:3]]}",
        flush=True,
    )
    return {"ok": True, "processos_validados": len(matches)}


async def wait_for_processo(
    conn: asyncpg.Connection,
    produto_id: uuid.UUID,
    *,
    timeout: float = 10.0,
) -> asyncpg.Record | None:
    """Aguarda surgir um processo_negociacao para o produto."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        row = await conn.fetchrow(
            "SELECT id, modo, status, data_fim, valor_reserva "
            "FROM portal_b2b.processo_negociacao "
            "WHERE produto_id=$1 ORDER BY data_inicio DESC LIMIT 1",
            produto_id,
        )
        if row is not None:
            return row
        await asyncio.sleep(0.5)
    return None


async def wait_for_status(
    conn: asyncpg.Connection,
    processo_id: uuid.UUID,
    expected: str,
    *,
    timeout: float = 30.0,
) -> str | None:
    deadline = asyncio.get_event_loop().time() + timeout
    last = None
    while asyncio.get_event_loop().time() < deadline:
        last = await conn.fetchval(
            "SELECT status FROM portal_b2b.processo_negociacao WHERE id=$1",
            processo_id,
        )
        if last == expected:
            return last
        await asyncio.sleep(0.5)
    return last


def fetch_propostas_mercado(fornecedor_id: uuid.UUID) -> list[dict]:
    """GET /propostas do mercado-service filtrando pelo fornecedor (gate do leilão direto)."""
    token = _make_jwt(fornecedor_id)
    req = urllib.request.Request(
        f"{MERCADO_URL}/propostas?fornecedor_id={fornecedor_id}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return [{"_http_error": exc.code, "_body": exc.read().decode()}]


def confirmar_proposta_mercado(
    processo_id: str, decisao: str, fornecedor_id: uuid.UUID
) -> dict:
    """POST /propostas/{id}/confirmar — fornecedor abre ('sim') ou recusa ('nao')."""
    url = f"{MERCADO_URL}/propostas/{processo_id}/confirmar"
    body = json.dumps({"decisao": decisao}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_make_jwt(fornecedor_id)}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": resp.status, "body": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read().decode()}


async def wait_for_proposta_mercado(
    fornecedor_id: uuid.UUID,
    produto_id: uuid.UUID,
    *,
    timeout: float = 10.0,
) -> dict | None:
    """Aguarda surgir uma proposta pendente de leilão direto para o produto/fornecedor."""
    alvo = str(produto_id)
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        propostas = fetch_propostas_mercado(fornecedor_id)
        if propostas and isinstance(propostas[0], dict) and "_http_error" in propostas[0]:
            await asyncio.sleep(0.5)
            continue
        for p in propostas:
            if p.get("produto_id") == alvo:
                return p
        await asyncio.sleep(0.5)
    return None


def post_lance(processo_id: uuid.UUID, valor: Decimal, qtd: Decimal, empresa_id: uuid.UUID) -> dict:
    url = f"{NEGOCIACAO_URL}/processos/{processo_id}/lances"
    body = json.dumps({"valor_unitario": str(valor), "quantidade": str(qtd)}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_make_jwt(empresa_id)}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": resp.status, "body": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read().decode()}


# --------------------------------------------------------------------------- #
# Cenários
# --------------------------------------------------------------------------- #

async def cenario_direto(
    conn: asyncpg.Connection,
    producer: AIOKafkaProducer,
    ids: dict[str, uuid.UUID],
) -> dict:
    print("\n=== Cenário A: Modo direto (oferta ≈ demanda) ===", flush=True)
    produto_id = ids["produto_a"]
    fornecimento_id = uuid.uuid4()
    demanda_id = uuid.uuid4()

    await publish(producer, "fornecimento_criado", _envelope(
        "fornecimento_criado",
        {
            "id": str(fornecimento_id),
            "produto_id": str(produto_id),
            "empresa_fornecedor_id": str(ids["fornecedor_a"]),
            "quantidade_disponivel": "100",
            "preco_unitario": "10.00",
        },
    ))
    await publish(producer, "demanda_criada", _envelope(
        "demanda_criada",
        {
            "id_demanda": str(demanda_id),
            "id_produto": str(produto_id),
            "id_empresa_comprador": str(ids["comprador_a"]),
            "quantidade_desejada": "100",
            "preco_maximo": "12.00",
        },
    ))

    processo = await wait_for_processo(conn, produto_id, timeout=10)
    if processo is None:
        return {"ok": False, "erro": "processo não criado"}
    print(f"  processo criado: id={processo['id']} modo={processo['modo']}", flush=True)
    if processo["modo"] != "direto":
        return {"ok": False, "erro": f"modo esperado=direto, obtido={processo['modo']}"}

    final_status = await wait_for_status(conn, processo["id"], "FECHADA", timeout=15)
    print(f"  status final: {final_status}", flush=True)
    return {
        "ok": final_status == "FECHADA",
        "processo_id": str(processo["id"]),
        "modo": processo["modo"],
        "status": final_status,
    }


async def cenario_leilao_direto(
    conn: asyncpg.Connection,
    producer: AIOKafkaProducer,
    ids: dict[str, uuid.UUID],
) -> dict:
    print("\n=== Cenário B: Leilão direto (demanda > oferta, compradores competem) ===", flush=True)
    produto_id = ids["produto_b"]

    # Importante: publica as 2 demandas ANTES da oferta. Sem oferta no snapshot,
    # `evaluate` retorna None e o snapshot acumula. Quando a oferta chega, o
    # matching dispara com TODAS as demandas já habilitadas.
    await publish(producer, "demanda_criada", _envelope(
        "demanda_criada",
        {
            "id_demanda": str(uuid.uuid4()),
            "id_produto": str(produto_id),
            "id_empresa_comprador": str(ids["comprador_a"]),
            "quantidade_desejada": "80",
            "preco_maximo": "15.00",
        },
    ))
    await publish(producer, "demanda_criada", _envelope(
        "demanda_criada",
        {
            "id_demanda": str(uuid.uuid4()),
            "id_produto": str(produto_id),
            "id_empresa_comprador": str(ids["comprador_b"]),
            "quantidade_desejada": "80",
            "preco_maximo": "15.00",
        },
    ))
    await asyncio.sleep(1.0)  # dar tempo do consumer processar as 2 demandas
    await publish(producer, "fornecimento_criado", _envelope(
        "fornecimento_criado",
        {
            "id": str(uuid.uuid4()),
            "produto_id": str(produto_id),
            "empresa_fornecedor_id": str(ids["fornecedor_a"]),
            "quantidade_disponivel": "50",
            "preco_unitario": "10.00",
        },
    ))

    # GATE: no leilão direto o fornecedor é dono da oferta e precisa confirmar.
    # O mercado NÃO publica modo_negociacao_definido até o "sim" — então primeiro
    # esperamos a proposta pendente, confirmamos, e só então o processo é criado.
    proposta = await wait_for_proposta_mercado(ids["fornecedor_a"], produto_id, timeout=12)
    if proposta is None:
        return {"ok": False, "erro": "proposta pendente não criada (gate do fornecedor)"}
    print(
        f"  proposta pendente: processo_id={proposta['processo_id']} "
        f"modo={proposta['modo']} fornecedor={proposta['empresa_fornecedor_id']}",
        flush=True,
    )
    if proposta["modo"] != "leilao_direto":
        return {"ok": False, "erro": f"modo esperado=leilao_direto, obtido={proposta['modo']}"}
    conf = confirmar_proposta_mercado(proposta["processo_id"], "sim", ids["fornecedor_a"])
    print(f"  fornecedor confirma (sim) → {conf['status']} {conf['body']}", flush=True)
    if conf["status"] != 200:
        return {"ok": False, "erro": f"confirmação do gate falhou: {conf}"}

    processo = await wait_for_processo(conn, produto_id, timeout=10)
    if processo is None:
        return {"ok": False, "erro": "processo não criado após confirmação do gate"}
    print(f"  processo criado: id={processo['id']} modo={processo['modo']} data_fim={processo['data_fim']}", flush=True)
    if processo["modo"] != "leilao_direto":
        return {"ok": False, "erro": f"modo esperado=leilao_direto, obtido={processo['modo']}"}

    # Comprador A oferece 11.50, B oferece 12.00 (vence o maior em leilão direto).
    r1 = post_lance(processo["id"], Decimal("11.50"), Decimal("50"), ids["comprador_a"])
    r2 = post_lance(processo["id"], Decimal("12.00"), Decimal("50"), ids["comprador_b"])
    print(f"  POST lance A → {r1['status']}, POST lance B → {r2['status']}", flush=True)
    if r1["status"] != 201 or r2["status"] != 201:
        return {"ok": False, "erro": f"lances rejeitados: A={r1}, B={r2}"}

    # auction_duration_seconds=10 + scheduler poll 2s → ~12s
    final_status = await wait_for_status(conn, processo["id"], "FECHADA", timeout=25)
    print(f"  status final: {final_status}", flush=True)
    return {
        "ok": final_status == "FECHADA",
        "processo_id": str(processo["id"]),
        "modo": processo["modo"],
        "status": final_status,
    }


async def cenario_leilao_reverso(
    conn: asyncpg.Connection,
    producer: AIOKafkaProducer,
    ids: dict[str, uuid.UUID],
) -> dict:
    print("\n=== Cenário C: Leilão reverso (oferta > demanda, fornecedores competem) ===", flush=True)
    produto_id = ids["produto_c"]

    # Espelho do Cenário B: publica as 2 ofertas antes da demanda para que ambos
    # fornecedores entrem habilitados quando o matching disparar.
    await publish(producer, "fornecimento_criado", _envelope(
        "fornecimento_criado",
        {
            "id": str(uuid.uuid4()),
            "produto_id": str(produto_id),
            "empresa_fornecedor_id": str(ids["fornecedor_a"]),
            "quantidade_disponivel": "80",
            "preco_unitario": "10.00",
        },
    ))
    await publish(producer, "fornecimento_criado", _envelope(
        "fornecimento_criado",
        {
            "id": str(uuid.uuid4()),
            "produto_id": str(produto_id),
            "empresa_fornecedor_id": str(ids["fornecedor_b"]),
            "quantidade_disponivel": "80",
            "preco_unitario": "11.00",
        },
    ))
    await asyncio.sleep(1.0)
    await publish(producer, "demanda_criada", _envelope(
        "demanda_criada",
        {
            "id_demanda": str(uuid.uuid4()),
            "id_produto": str(produto_id),
            "id_empresa_comprador": str(ids["comprador_a"]),
            "quantidade_desejada": "100",
            "preco_maximo": "15.00",
        },
    ))

    processo = await wait_for_processo(conn, produto_id, timeout=10)
    if processo is None:
        return {"ok": False, "erro": "processo não criado"}
    print(f"  processo criado: id={processo['id']} modo={processo['modo']}", flush=True)
    if processo["modo"] != "leilao_reverso":
        return {"ok": False, "erro": f"modo esperado=leilao_reverso, obtido={processo['modo']}"}

    # Fornecedor A oferece 9.50, B oferece 9.00 (vence o menor em reverso).
    r1 = post_lance(processo["id"], Decimal("9.50"), Decimal("100"), ids["fornecedor_a"])
    r2 = post_lance(processo["id"], Decimal("9.00"), Decimal("100"), ids["fornecedor_b"])
    print(f"  POST lance A → {r1['status']}, POST lance B → {r2['status']}", flush=True)
    if r1["status"] != 201 or r2["status"] != 201:
        return {"ok": False, "erro": f"lances rejeitados: A={r1}, B={r2}"}

    final_status = await wait_for_status(conn, processo["id"], "FECHADA", timeout=25)
    print(f"  status final: {final_status}", flush=True)
    return {
        "ok": final_status == "FECHADA",
        "processo_id": str(processo["id"]),
        "modo": processo["modo"],
        "status": final_status,
    }


def fetch_log_decisoes(fornecedor_id: uuid.UUID) -> list[dict]:
    token = _make_jwt(fornecedor_id)
    req = urllib.request.Request(
        f"{MERCADO_URL}/propostas/log",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError:
        return []


async def cenario_recusa_leilao_direto(
    conn: asyncpg.Connection,
    producer: AIOKafkaProducer,
    ids: dict[str, uuid.UUID],
) -> dict:
    print("\n=== Cenário E: Leilão direto RECUSADO (fornecedor diz 'não') ===", flush=True)
    produto_id = ids["produto_d"]

    # demanda > oferta → leilao_direto (mesmo padrão do cenário B).
    await publish(producer, "demanda_criada", _envelope(
        "demanda_criada",
        {
            "id_demanda": str(uuid.uuid4()),
            "id_produto": str(produto_id),
            "id_empresa_comprador": str(ids["comprador_a"]),
            "quantidade_desejada": "80",
            "preco_maximo": "15.00",
        },
    ))
    await publish(producer, "demanda_criada", _envelope(
        "demanda_criada",
        {
            "id_demanda": str(uuid.uuid4()),
            "id_produto": str(produto_id),
            "id_empresa_comprador": str(ids["comprador_b"]),
            "quantidade_desejada": "80",
            "preco_maximo": "15.00",
        },
    ))
    await asyncio.sleep(1.0)
    await publish(producer, "fornecimento_criado", _envelope(
        "fornecimento_criado",
        {
            "id": str(uuid.uuid4()),
            "produto_id": str(produto_id),
            "empresa_fornecedor_id": str(ids["fornecedor_a"]),
            "quantidade_disponivel": "50",
            "preco_unitario": "10.00",
        },
    ))

    proposta = await wait_for_proposta_mercado(ids["fornecedor_a"], produto_id, timeout=12)
    if proposta is None:
        return {"ok": False, "erro": "proposta pendente não criada (gate do fornecedor)"}
    print(f"  proposta pendente: processo_id={proposta['processo_id']}", flush=True)

    conf = confirmar_proposta_mercado(proposta["processo_id"], "nao", ids["fornecedor_a"])
    print(f"  fornecedor recusa (nao) → {conf['status']} {conf['body']}", flush=True)
    if conf["status"] != 200:
        return {"ok": False, "erro": f"recusa do gate falhou: {conf}"}

    # Boundary: NADA deve ser publicado → nenhum processo criado em negociacao.
    processo = await wait_for_processo(conn, produto_id, timeout=6)
    if processo is not None:
        return {
            "ok": False,
            "erro": f"recusa não deveria criar processo, mas criou id={processo['id']}",
        }
    print("  OK: nenhum processo criado (recusa ficou interna ao mercado)", flush=True)

    # E a decisão 'nao' deve constar no log in-memory.
    log = fetch_log_decisoes(ids["fornecedor_a"])
    achou = any(
        e.get("processo_id") == proposta["processo_id"] and e.get("decisao") == "nao"
        for e in log
    )
    if not achou:
        return {"ok": False, "erro": "decisão 'nao' não apareceu no log /propostas/log"}
    print("  OK: decisão 'nao' registrada no log", flush=True)
    return {"ok": True, "processo_id": proposta["processo_id"], "decisao": "nao"}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

async def main() -> int:
    print("Smoke test do domínio Vendas")
    print(f"  DB     = {DB_URL.split('@')[-1]}")
    print(f"  Kafka  = {KAFKA}")
    print(f"  REST   = {NEGOCIACAO_URL}")
    print()

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=3)
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA, acks="all", enable_idempotence=True)
    await producer.start()

    run_tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    print(f"  run    = {run_tag}\n")

    try:
        async with pool.acquire() as conn:
            print("Seed de dados-base...")
            ids = await seed_base_data(conn, run_tag)
            for k, v in ids.items():
                print(f"  {k} = {v}")

            print("\nPublicando produto_cadastrado para alimentar ProdutoCache...")
            await publish_produtos_cadastrados(producer, ids, run_tag)

            results = {
                "A_direto": await cenario_direto(conn, producer, ids),
                "B_leilao_direto": await cenario_leilao_direto(conn, producer, ids),
                "C_leilao_reverso": await cenario_leilao_reverso(conn, producer, ids),
                "D_produto_nome": validar_produto_nome_enriquecido(ids),
                "E_recusa_leilao_direto": await cenario_recusa_leilao_direto(conn, producer, ids),
            }
    finally:
        await producer.stop()
        await pool.close()

    print("\n========= RESULTADO =========")
    all_ok = True
    for name, r in results.items():
        flag = "OK " if r.get("ok") else "FAIL"
        all_ok = all_ok and r.get("ok", False)
        print(f"  [{flag}] {name}: {r}")
    print("=============================\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

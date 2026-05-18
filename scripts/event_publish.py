"""Publica um evento Kafka a partir de uma fixture JSON.

Útil para Eq.3/Eq.4 testarem o pipeline contra nosso mercado-service sem precisar
implementar publisher próprio — pegam um fixture pronto, ajustam IDs, publicam.

Roda dentro do container `negociacao-service` (já tem aiokafka+orjson).
Veja `event_publish.bat` / `event_publish.sh` para os wrappers.

Uso:
    python event_publish.py <topico> <fixture.json> [--no-wrap]

Modos:
    Padrão       — `fixture.json` contém só o payload, embrulhamos em envelope padrão.
    --no-wrap    — `fixture.json` já é o envelope completo (sobrescreve eventType pelo argumento).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import orjson
from aiokafka import AIOKafkaProducer

KAFKA = (
    os.environ.get("SMOKE_KAFKA")
    or os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    or "redpanda:9092"
)
SOURCE = os.environ.get("EVENT_PUBLISH_SOURCE", "event-publish-cli")

VALID_TOPICS = {
    "fornecimento_criado",
    "estoque_atualizado",
    "demanda_criada",
    "demanda_recorrente_gerada",
    "modo_negociacao_definido",
    "leilao_iniciado",
    "lance_realizado",
    "negociacao_fechada",
}


def _envelope(event_type: str, payload: dict) -> dict:
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "eventVersion": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "correlationId": str(uuid.uuid4()),
        "payload": payload,
    }


async def _publish(topic: str, envelope: dict) -> None:
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA, acks="all")
    await producer.start()
    try:
        await producer.send_and_wait(topic, orjson.dumps(envelope))
    finally:
        await producer.stop()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Publica um evento Kafka a partir de fixture JSON."
    )
    ap.add_argument("topic", help=f"Tópico Kafka. Válidos: {sorted(VALID_TOPICS)}")
    ap.add_argument("fixture", help="Caminho do JSON (payload ou envelope completo).")
    ap.add_argument(
        "--no-wrap",
        action="store_true",
        help="Fixture já é envelope completo — não criar envelope novo.",
    )
    args = ap.parse_args()

    if args.topic not in VALID_TOPICS:
        print(f"[event_publish] Tópico inválido: {args.topic}", file=sys.stderr)
        print(f"[event_publish] Válidos: {sorted(VALID_TOPICS)}", file=sys.stderr)
        return 2

    try:
        with open(args.fixture, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[event_publish] Fixture não encontrado: {args.fixture}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"[event_publish] JSON inválido em {args.fixture}: {exc}", file=sys.stderr)
        return 2

    if args.no_wrap:
        if not isinstance(data, dict) or "payload" not in data:
            print("[event_publish] --no-wrap exige envelope com 'payload'.", file=sys.stderr)
            return 2
        envelope = data
        envelope["eventType"] = args.topic
        envelope.setdefault("eventId", str(uuid.uuid4()))
        envelope.setdefault("eventVersion", "1.0")
        envelope.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        envelope.setdefault("source", SOURCE)
        envelope.setdefault("correlationId", str(uuid.uuid4()))
    else:
        envelope = _envelope(args.topic, data)

    print(f"[event_publish] kafka  = {KAFKA}")
    print(f"[event_publish] topic  = {args.topic}")
    print(f"[event_publish] eventId={envelope['eventId']}")
    asyncio.run(_publish(args.topic, envelope))
    print("[event_publish] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

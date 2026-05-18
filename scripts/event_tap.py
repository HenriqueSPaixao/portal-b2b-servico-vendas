"""Consumer dummy: imprime eventos Kafka do domínio Vendas em tempo real.

Útil para Eq.3/Eq.4 verem `negociacao_fechada`/`lance_realizado` chegando com
o payload certo, sem precisar implementar consumer próprio. Também útil pra nós
debugar o pipeline.

Roda dentro do container `negociacao-service` (já tem `aiokafka` + `orjson`).
Veja `event_tap.bat` / `event_tap.sh` para os wrappers.

Uso:
    python event_tap.py                                # todos os tópicos
    python event_tap.py negociacao_fechada             # filtra um
    python event_tap.py lance_realizado negociacao_fechada  # filtra N

Defaults:
    SMOKE_KAFKA=redpanda:9092 (dentro do container)
    EVENT_TAP_GROUP=event-tap-<pid>  (sempre novo → não interfere em outros consumers)
    auto_offset_reset=latest → só novos eventos a partir do start.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer

KAFKA = (
    os.environ.get("SMOKE_KAFKA")
    or os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    or "redpanda:9092"
)
GROUP = os.environ.get("EVENT_TAP_GROUP", f"event-tap-{os.getpid()}")

ALL_TOPICS = [
    # consumidos pelo mercado-service
    "fornecimento_criado",
    "estoque_atualizado",
    "demanda_criada",
    "demanda_recorrente_gerada",
    # publicados pelo domínio Vendas
    "modo_negociacao_definido",
    "leilao_iniciado",
    "lance_realizado",
    "negociacao_fechada",
]

RESET = "\x1b[0m"
DIM = "\x1b[2m"
BOLD = "\x1b[1m"
COLORS = {
    "fornecimento_criado":       "\x1b[36m",  # cyan
    "estoque_atualizado":        "\x1b[96m",  # bright cyan
    "demanda_criada":            "\x1b[35m",  # magenta
    "demanda_recorrente_gerada": "\x1b[95m",  # bright magenta
    "modo_negociacao_definido":  "\x1b[33m",  # yellow
    "leilao_iniciado":           "\x1b[93m",  # bright yellow
    "lance_realizado":           "\x1b[32m",  # green
    "negociacao_fechada":        "\x1b[92m",  # bright green
}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def run(topics: list[str]) -> int:
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA,
        group_id=GROUP,
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    print(f"[event_tap] Kafka  = {KAFKA}")
    print(f"[event_tap] Group  = {GROUP}")
    print(f"[event_tap] Topics = {', '.join(topics)}")
    print(f"[event_tap] Aguardando eventos (Ctrl+C para sair)...\n", flush=True)

    await consumer.start()
    try:
        async for msg in consumer:
            try:
                envelope = json.loads(msg.value.decode("utf-8"))
            except Exception:
                envelope = {"raw": repr(msg.value)}
            color = COLORS.get(msg.topic, "")
            ev_id = str(envelope.get("eventId", "?"))[:8]
            ev_type = envelope.get("eventType", "?")
            src = envelope.get("source", "?")
            print(
                f"{color}{BOLD}{_ts()}  {msg.topic}{RESET}"
                f"  {DIM}eventId={ev_id}  source={src}  eventType={ev_type}{RESET}"
            )
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
            print(flush=True)
    finally:
        await consumer.stop()
    return 0


def main() -> int:
    selected = sys.argv[1:] or ALL_TOPICS
    invalid = [t for t in selected if t not in ALL_TOPICS]
    if invalid:
        print(f"[event_tap] Tópico(s) inválido(s): {invalid}", file=sys.stderr)
        print(f"[event_tap] Válidos: {ALL_TOPICS}", file=sys.stderr)
        return 2
    try:
        return asyncio.run(run(selected))
    except KeyboardInterrupt:
        print("\n[event_tap] saindo.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

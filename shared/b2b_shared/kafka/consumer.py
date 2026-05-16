import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeAlias

import orjson
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from b2b_shared.events.envelope import EventEnvelope

logger = logging.getLogger(__name__)

ConsumerHandler: TypeAlias = Callable[[EventEnvelope], Awaitable[None]]


class KafkaConsumerRunner:
    """Background runner que consome múltiplos tópicos e dispatch para handlers.

    Cada handler recebe o EventEnvelope já desserializado. Erros do handler
    são logados mas não interrompem o consumo (at-least-once delivery — quem
    consome deve ser idempotente).
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        group_id: str,
        client_id: str,
        handlers: dict[str, ConsumerHandler],
        auto_offset_reset: str = "earliest",
    ) -> None:
        if not handlers:
            raise ValueError("Pelo menos um handler é obrigatório")
        self._bootstrap_servers = bootstrap_servers
        self._group_id = group_id
        self._client_id = client_id
        self._handlers = handlers
        self._auto_offset_reset = auto_offset_reset
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._consumer = AIOKafkaConsumer(
            *self._handlers.keys(),
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            client_id=self._client_id,
            auto_offset_reset=self._auto_offset_reset,
            enable_auto_commit=False,
            value_deserializer=orjson.loads,
        )
        await self._consumer.start()
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name=f"kafka-consumer-{self._group_id}")
        logger.info(
            "Kafka consumer started",
            extra={"topics": list(self._handlers.keys()), "group": self._group_id},
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
        logger.info("Kafka consumer stopped", extra={"group": self._group_id})

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                if self._stopping.is_set():
                    break
                handler = self._handlers.get(msg.topic)
                if handler is None:
                    logger.warning("No handler for topic", extra={"topic": msg.topic})
                    await self._consumer.commit()
                    continue
                try:
                    envelope = EventEnvelope.model_validate(msg.value)
                except Exception:  # noqa: BLE001 — payload pode vir malformado
                    logger.exception(
                        "Envelope inválido, pulando",
                        extra={"topic": msg.topic, "offset": msg.offset},
                    )
                    await self._consumer.commit()
                    continue
                try:
                    await handler(envelope)
                except Exception:  # noqa: BLE001 — handler livre para falhar
                    logger.exception(
                        "Handler falhou",
                        extra={
                            "topic": msg.topic,
                            "event_type": envelope.event_type,
                            "event_id": str(envelope.event_id),
                        },
                    )
                    # Continuamos: at-least-once + handler idempotente.
                await self._consumer.commit()
        except asyncio.CancelledError:
            raise
        except KafkaError:
            logger.exception("Kafka consumer error")

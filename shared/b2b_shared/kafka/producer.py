import logging
from typing import Self

import orjson
from aiokafka import AIOKafkaProducer

from b2b_shared.events.envelope import EventEnvelope

logger = logging.getLogger(__name__)


def _orjson_serializer(value: dict) -> bytes:
    return orjson.dumps(value)


class KafkaProducer:
    """Wrapper async de AIOKafkaProducer com serialização JSON de envelope.

    Usar como singleton no `lifespan` do FastAPI:
        producer = KafkaProducer(bootstrap_servers=..., client_id=...)
        await producer.start()
        ...
        await producer.stop()
    """

    def __init__(self, *, bootstrap_servers: str, client_id: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if self._producer is not None:
            return
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            client_id=self._client_id,
            value_serializer=_orjson_serializer,
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()
        logger.info(
            "Kafka producer started", extra={"bootstrap": self._bootstrap_servers}
        )

    async def stop(self) -> None:
        if self._producer is None:
            return
        await self._producer.stop()
        self._producer = None
        logger.info("Kafka producer stopped")

    async def publish(self, topic: str, envelope: EventEnvelope) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaProducer não foi iniciado (chame .start())")
        payload = envelope.model_dump(by_alias=True, mode="json")
        await self._producer.send_and_wait(topic, payload)
        logger.info(
            "Event published",
            extra={
                "topic": topic,
                "event_type": envelope.event_type,
                "event_id": str(envelope.event_id),
            },
        )

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

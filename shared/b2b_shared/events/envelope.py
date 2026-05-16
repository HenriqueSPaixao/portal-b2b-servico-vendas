from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    """Envelope padrão usado por todos os microsserviços do Portal B2B.

    Formato alinhado com o que o MS Produtos já publica (vide chat do grupo
    em 5/7/26 9:48 PM com exemplo de `produto_cadastrado`).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    event_id: UUID = Field(default_factory=uuid4, alias="eventId")
    event_type: str = Field(..., alias="eventType")
    event_version: str = Field(default="1.0", alias="eventVersion")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source: str
    correlation_id: UUID = Field(default_factory=uuid4, alias="correlationId")
    payload: dict[str, Any]


def build_envelope(
    *,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    correlation_id: UUID | None = None,
    event_version: str = "1.0",
) -> EventEnvelope:
    return EventEnvelope(
        eventType=event_type,
        eventVersion=event_version,
        source=source,
        correlationId=correlation_id or uuid4(),
        payload=payload,
    )

import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.enums import ModoNegociacao
from app.metadata_cache import ProcessoMeta, ProcessoMetaCache
from app.service import NegociacaoService
from b2b_shared.events import EventEnvelope
from b2b_shared.kafka import KafkaProducer

logger = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_uuid(value: str | None) -> UUID | None:
    return UUID(value) if value else None


def _parse_uuid_list(value: list[str] | None) -> list[UUID]:
    if not value:
        return []
    return [UUID(v) for v in value]


def _parse_decimal(value: str | int | float | None) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


class NegociacaoConsumers:
    """Handlers de Kafka do negociacao-service.

    Consome:
      - modo_negociacao_definido: cria processo + cache metadata; se modo=direto,
        fecha imediatamente publicando negociacao_fechada.
      - leilao_iniciado: idempotente. Geralmente o modo_negociacao_definido já
        criou tudo; este evento serve só como confirmação de auditoria.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        producer: KafkaProducer,
        metadata: ProcessoMetaCache,
        source_name: str,
    ) -> None:
        self._session_factory = session_factory
        self._producer = producer
        self._metadata = metadata
        self._source = source_name

    async def handle_modo_negociacao_definido(self, envelope: EventEnvelope) -> None:
        payload = envelope.payload
        try:
            processo_id = UUID(payload["processo_id"])
            produto_id = UUID(payload["produto_id"])
            modo = str(payload["modo"])
            data_inicio = _parse_datetime(payload.get("data_inicio")) or envelope.timestamp
            data_fim = _parse_datetime(payload["data_fim"])
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload modo_negociacao_definido inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return

        if data_fim is None:
            logger.error(
                "data_fim ausente, ignorando",
                extra={"processo_id": str(processo_id)},
            )
            return

        meta = ProcessoMeta(
            processo_id=processo_id,
            produto_id=produto_id,
            modo=modo,
            quantidade=_parse_decimal(payload.get("quantidade")),
            correlation_id=envelope.correlation_id,
            fornecimento_id=_parse_uuid(payload.get("fornecimento_id")),
            demanda_id=_parse_uuid(payload.get("demanda_id")),
            empresa_comprador_principal=_parse_uuid(
                payload.get("empresa_comprador_principal")
            ),
            empresa_fornecedor_principal=_parse_uuid(
                payload.get("empresa_fornecedor_principal")
            ),
            empresas_compradoras_habilitadas=_parse_uuid_list(
                payload.get("empresas_compradoras_habilitadas")
            ),
            empresas_fornecedoras_habilitadas=_parse_uuid_list(
                payload.get("empresas_fornecedoras_habilitadas")
            ),
        )

        valor_reserva = (
            _parse_decimal(payload["valor_reserva"])
            if payload.get("valor_reserva") is not None
            else None
        )

        async with self._session_factory() as session:
            async with session.begin():
                service = NegociacaoService(
                    session,
                    producer=self._producer,
                    metadata=self._metadata,
                    source_name=self._source,
                )
                await service.criar_a_partir_de_modo_definido(
                    processo_id=processo_id,
                    produto_id=produto_id,
                    modo=modo,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    valor_reserva=valor_reserva,
                    meta=meta,
                )

        # Modo direto fecha imediatamente — não há leilão.
        if modo == ModoNegociacao.DIRETO.value:
            async with self._session_factory() as session:
                async with session.begin():
                    service = NegociacaoService(
                        session,
                        producer=self._producer,
                        metadata=self._metadata,
                        source_name=self._source,
                    )
                    await service.fechar_processo(
                        processo_id, motivo="venda_direta_automatica"
                    )

    async def handle_leilao_iniciado(self, envelope: EventEnvelope) -> None:
        # Idempotente. O processo já foi criado pelo modo_negociacao_definido.
        # Mantemos como ponto de auditoria.
        processo_id = envelope.payload.get("processo_id")
        logger.info(
            "leilao_iniciado recebido",
            extra={
                "processo_id": str(processo_id),
                "event_id": str(envelope.event_id),
            },
        )

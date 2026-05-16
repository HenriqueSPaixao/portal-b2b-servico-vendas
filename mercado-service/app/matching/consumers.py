import logging
from decimal import Decimal
from uuid import UUID

from app.matching.engine import MatchingEngine
from app.matching.snapshot import Demanda, Oferta, Snapshot
from b2b_shared.events import EventEnvelope

logger = logging.getLogger(__name__)


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def _uuid_or_none(value) -> UUID | None:
    return UUID(value) if value else None


class MercadoConsumers:
    def __init__(self, snapshot: Snapshot, engine: MatchingEngine) -> None:
        self._snapshot = snapshot
        self._engine = engine

    async def handle_fornecimento_criado(self, envelope: EventEnvelope) -> None:
        p = envelope.payload
        try:
            oferta = Oferta(
                fornecimento_id=UUID(p["id"]),
                produto_id=UUID(p["produto_id"]),
                empresa_fornecedor_id=UUID(p["empresa_fornecedor_id"]),
                quantidade=_decimal(p.get("quantidade_disponivel") or p.get("quantidade")),
                preco_unitario=_decimal(p.get("preco_unitario")),
            )
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload fornecimento_criado inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return
        self._snapshot.upsert_oferta(oferta)
        await self._engine.evaluate(oferta.produto_id)

    async def handle_estoque_atualizado(self, envelope: EventEnvelope) -> None:
        p = envelope.payload
        try:
            produto_id = UUID(p["produto_id"])
            fornecimento_id = UUID(p["fornecimento_id"])
            nova_quantidade = _decimal(p.get("quantidade_disponivel") or p.get("quantidade"))
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload estoque_atualizado inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return
        self._snapshot.update_estoque(
            produto_id=produto_id,
            fornecimento_id=fornecimento_id,
            nova_quantidade=nova_quantidade,
        )
        await self._engine.evaluate(produto_id)

    async def handle_demanda_criada(self, envelope: EventEnvelope) -> None:
        p = envelope.payload
        try:
            demanda = Demanda(
                demanda_id=UUID(p.get("id_demanda") or p["id"]),
                produto_id=UUID(p.get("id_produto") or p["produto_id"]),
                empresa_comprador_id=UUID(
                    p.get("id_empresa_comprador") or p["empresa_comprador_id"]
                ),
                quantidade=_decimal(
                    p.get("quantidade_desejada") or p.get("quantidade")
                ),
                preco_maximo=(
                    _decimal(p["preco_maximo"]) if p.get("preco_maximo") else None
                ),
                is_recorrente=bool(p.get("is_recorrente", False)),
            )
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload demanda_criada inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return
        self._snapshot.upsert_demanda(demanda)
        await self._engine.evaluate(demanda.produto_id)

    async def handle_demanda_recorrente_gerada(self, envelope: EventEnvelope) -> None:
        # Tratamos como demanda comum, apenas marcamos is_recorrente para auditoria.
        # O domínio Demanda é que gera o evento por ciclo.
        envelope.payload.setdefault("is_recorrente", True)
        await self.handle_demanda_criada(envelope)

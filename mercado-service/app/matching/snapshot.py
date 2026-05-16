from dataclasses import dataclass, field
from decimal import Decimal
from threading import RLock
from uuid import UUID


@dataclass
class Oferta:
    fornecimento_id: UUID
    produto_id: UUID
    empresa_fornecedor_id: UUID
    quantidade: Decimal
    preco_unitario: Decimal
    consumida: bool = False


@dataclass
class Demanda:
    demanda_id: UUID
    produto_id: UUID
    empresa_comprador_id: UUID
    quantidade: Decimal
    preco_maximo: Decimal | None
    is_recorrente: bool = False
    consumida: bool = False


@dataclass
class Snapshot:
    """Estado in-memory de ofertas e demandas indexadas por produto_id.

    Reconstrução: o consumer inicia com auto.offset.reset=earliest. Eventos
    são reaplicados; o estado consumido fica perdido caso o tópico não tenha
    log compaction, mas para o trabalho acadêmico é suficiente.
    """

    ofertas_por_produto: dict[UUID, dict[UUID, Oferta]] = field(default_factory=dict)
    demandas_por_produto: dict[UUID, dict[UUID, Demanda]] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def upsert_oferta(self, oferta: Oferta) -> None:
        with self._lock:
            bucket = self.ofertas_por_produto.setdefault(oferta.produto_id, {})
            bucket[oferta.fornecimento_id] = oferta

    def update_estoque(
        self,
        *,
        produto_id: UUID,
        fornecimento_id: UUID,
        nova_quantidade: Decimal,
    ) -> None:
        with self._lock:
            bucket = self.ofertas_por_produto.get(produto_id)
            if not bucket:
                return
            oferta = bucket.get(fornecimento_id)
            if oferta is None:
                return
            oferta.quantidade = nova_quantidade
            if nova_quantidade <= 0:
                oferta.consumida = True

    def upsert_demanda(self, demanda: Demanda) -> None:
        with self._lock:
            bucket = self.demandas_por_produto.setdefault(demanda.produto_id, {})
            bucket[demanda.demanda_id] = demanda

    def ofertas_ativas(self, produto_id: UUID) -> list[Oferta]:
        with self._lock:
            bucket = self.ofertas_por_produto.get(produto_id, {})
            return [o for o in bucket.values() if not o.consumida and o.quantidade > 0]

    def demandas_ativas(self, produto_id: UUID) -> list[Demanda]:
        with self._lock:
            bucket = self.demandas_por_produto.get(produto_id, {})
            return [d for d in bucket.values() if not d.consumida and d.quantidade > 0]

    def total_oferta(self, produto_id: UUID) -> Decimal:
        return sum(
            (o.quantidade for o in self.ofertas_ativas(produto_id)), start=Decimal(0)
        )

    def total_demanda(self, produto_id: UUID) -> Decimal:
        return sum(
            (d.quantidade for d in self.demandas_ativas(produto_id)), start=Decimal(0)
        )

    def marcar_consumidas(
        self, ofertas: list[Oferta], demandas: list[Demanda]
    ) -> None:
        with self._lock:
            for o in ofertas:
                o.consumida = True
            for d in demandas:
                d.consumida = True

    def to_dict(self, produto_id: UUID) -> dict:
        """Representação serializável para o endpoint de debug."""
        return {
            "produto_id": str(produto_id),
            "total_oferta": str(self.total_oferta(produto_id)),
            "total_demanda": str(self.total_demanda(produto_id)),
            "ofertas": [
                {
                    "fornecimento_id": str(o.fornecimento_id),
                    "empresa_fornecedor_id": str(o.empresa_fornecedor_id),
                    "quantidade": str(o.quantidade),
                    "preco_unitario": str(o.preco_unitario),
                }
                for o in self.ofertas_ativas(produto_id)
            ],
            "demandas": [
                {
                    "demanda_id": str(d.demanda_id),
                    "empresa_comprador_id": str(d.empresa_comprador_id),
                    "quantidade": str(d.quantidade),
                    "preco_maximo": str(d.preco_maximo) if d.preco_maximo else None,
                    "is_recorrente": d.is_recorrente,
                }
                for d in self.demandas_ativas(produto_id)
            ],
        }

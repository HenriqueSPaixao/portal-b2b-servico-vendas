"""Valida que MercadoConsumers aceita o payload camelCase real publicado
pela Eq.3 Fornecimentos (https://github.com/theudevs/fornecimentos-service).

Roda isolado: sem Kafka, sem Postgres. Usa MatchingEngine real + Snapshot
real + um KafkaProducer fake (in-memory) para capturar eventos publicados.

Cobre 4 casos:
1. fornecimento_criado em camelCase (formato Eq.3)
2. fornecimento_criado em snake_case (compatibilidade histórica)
3. estoque_atualizado em camelCase (formato Eq.3)
4. demanda_criada em snake_case + fornecimento camelCase casando → matching dispara

Rodar:
    cd mercado-service
    PYTHONPATH="../shared:.;$PYTHONPATH" python ../scripts/test_fornecimentos_eq3_contract.py
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

# Garante import-paths consistentes mesmo se rodado da raiz do repo.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mercado-service"))

from app.matching.consumers import MercadoConsumers  # noqa: E402
from app.matching.engine import MatchingEngine  # noqa: E402
from app.matching.snapshot import Snapshot  # noqa: E402
from b2b_shared.events import EventEnvelope  # noqa: E402


@dataclass
class FakeProducer:
    """Captura eventos publicados em memória — sem Kafka."""

    sent: list[tuple[str, EventEnvelope]] = field(default_factory=list)

    async def publish(self, topic: str, envelope: EventEnvelope) -> None:
        self.sent.append((topic, envelope))


def envelope(event_type: str, payload: dict, source: str = "fornecimentos-service") -> EventEnvelope:
    return EventEnvelope(
        eventType=event_type,
        source=source,
        payload=payload,
    )


# Payload EXATO do criar_fornecimento da Eq.3
# (app/services/fornecimento_service.py:90-106 do repo deles)
def fornecimento_criado_camelcase(*, forn_id: UUID, prod_id: UUID, empresa_id: UUID) -> dict:
    return {
        "idFornecimento": str(forn_id),
        "idEmpresaFornecedor": str(empresa_id),
        "idProduto": str(prod_id),
        "idEnderecoOrigem": str(uuid4()),
        "precoUnitario": "10.00",
        "quantidadeDisponivel": "100",
    }


# Payload EXATO do atualizar_estoque da Eq.3
# (app/services/fornecimento_service.py:147-157 do repo deles)
def estoque_atualizado_camelcase(*, forn_id: UUID, prod_id: UUID, empresa_id: UUID) -> dict:
    return {
        "idFornecimento": str(forn_id),
        "idEmpresaFornecedor": str(empresa_id),
        "idProduto": str(prod_id),
        "quantidadeAnterior": "100",
        "quantidadeDisponivel": "50",
    }


def fornecimento_criado_snake(*, forn_id: UUID, prod_id: UUID, empresa_id: UUID) -> dict:
    return {
        "id": str(forn_id),
        "produto_id": str(prod_id),
        "empresa_fornecedor_id": str(empresa_id),
        "preco_unitario": "10.00",
        "quantidade_disponivel": "100",
    }


def demanda_criada_payload(*, dem_id: UUID, prod_id: UUID, comp_id: UUID) -> dict:
    return {
        "id_demanda": str(dem_id),
        "id_produto": str(prod_id),
        "id_empresa_comprador": str(comp_id),
        "quantidade_desejada": "100",
        "preco_maximo": "12.00",
    }


def build_stack() -> tuple[MercadoConsumers, Snapshot, FakeProducer]:
    snapshot = Snapshot()
    producer = FakeProducer()
    engine = MatchingEngine(
        snapshot=snapshot,
        producer=producer,
        source_name="mercado-service",
    )
    return MercadoConsumers(snapshot=snapshot, engine=engine), snapshot, producer


async def case_camelcase_fornecimento_criado() -> None:
    consumers, snap, _producer = build_stack()
    forn_id = uuid4()
    prod_id = uuid4()
    empresa_id = uuid4()

    await consumers.handle_fornecimento_criado(
        envelope("fornecimento_criado", fornecimento_criado_camelcase(
            forn_id=forn_id, prod_id=prod_id, empresa_id=empresa_id,
        ))
    )

    ofertas = snap.ofertas_ativas(prod_id)
    assert len(ofertas) == 1, f"esperava 1 oferta, achei {len(ofertas)}"
    o = ofertas[0]
    assert o.fornecimento_id == forn_id, "fornecimento_id não casa"
    assert o.empresa_fornecedor_id == empresa_id, "empresa_fornecedor_id não casa"
    assert o.quantidade == Decimal("100"), f"quantidade={o.quantidade}"
    assert o.preco_unitario == Decimal("10.00"), f"preco={o.preco_unitario}"
    print("  OK  camelCase fornecimento_criado -> snapshot populado corretamente")


async def case_snakecase_fornecimento_criado() -> None:
    consumers, snap, _producer = build_stack()
    forn_id = uuid4()
    prod_id = uuid4()
    empresa_id = uuid4()

    await consumers.handle_fornecimento_criado(
        envelope("fornecimento_criado", fornecimento_criado_snake(
            forn_id=forn_id, prod_id=prod_id, empresa_id=empresa_id,
        ))
    )

    ofertas = snap.ofertas_ativas(prod_id)
    assert len(ofertas) == 1, "snake_case quebrou (regressão)"
    o = ofertas[0]
    assert o.fornecimento_id == forn_id
    assert o.preco_unitario == Decimal("10.00")
    print("  OK  snake_case fornecimento_criado -> compatibilidade preservada")


async def case_camelcase_estoque_atualizado() -> None:
    consumers, snap, _producer = build_stack()
    forn_id = uuid4()
    prod_id = uuid4()
    empresa_id = uuid4()

    await consumers.handle_fornecimento_criado(
        envelope("fornecimento_criado", fornecimento_criado_camelcase(
            forn_id=forn_id, prod_id=prod_id, empresa_id=empresa_id,
        ))
    )
    await consumers.handle_estoque_atualizado(
        envelope("estoque_atualizado", estoque_atualizado_camelcase(
            forn_id=forn_id, prod_id=prod_id, empresa_id=empresa_id,
        ))
    )

    ofertas = snap.ofertas_ativas(prod_id)
    assert len(ofertas) == 1
    assert ofertas[0].quantidade == Decimal("50"), (
        f"estoque não atualizado para 50: {ofertas[0].quantidade}"
    )
    print("  OK  camelCase estoque_atualizado -> snapshot atualizado de 100 -> 50")


async def case_matching_fim_a_fim() -> None:
    consumers, snap, producer = build_stack()
    forn_id = uuid4()
    prod_id = uuid4()
    empresa_forn = uuid4()
    dem_id = uuid4()
    empresa_comp = uuid4()

    # Eq.3 publica camelCase
    await consumers.handle_fornecimento_criado(
        envelope("fornecimento_criado", fornecimento_criado_camelcase(
            forn_id=forn_id, prod_id=prod_id, empresa_id=empresa_forn,
        ))
    )
    # Eq.4 publica snake_case (com prefixo id_)
    await consumers.handle_demanda_criada(
        envelope("demanda_criada", demanda_criada_payload(
            dem_id=dem_id, prod_id=prod_id, comp_id=empresa_comp,
        ))
    )

    # Oferta=100 e demanda=100 → modo direto deve disparar e publicar
    # modo_negociacao_definido.
    eventos = [t for t, _ in producer.sent]
    assert "modo_negociacao_definido" in eventos, (
        f"matching não disparou. Publicados={eventos}"
    )
    # Em modo direto NÃO publicamos leilao_iniciado.
    assert "leilao_iniciado" not in eventos, (
        "modo direto não deveria publicar leilao_iniciado"
    )
    print("  OK  matching fim-a-fim (Eq.3 camelCase + Eq.4 snake_case) -> modo_negociacao_definido publicado")


async def main() -> int:
    print("=" * 70)
    print("Validação do contrato Eq.3 Fornecimentos (camelCase) no mercado-service")
    print("=" * 70)
    casos = [
        ("camelCase fornecimento_criado", case_camelcase_fornecimento_criado),
        ("snake_case fornecimento_criado (regressão)", case_snakecase_fornecimento_criado),
        ("camelCase estoque_atualizado", case_camelcase_estoque_atualizado),
        ("matching fim-a-fim cross-contract", case_matching_fim_a_fim),
    ]
    falhas = 0
    for nome, fn in casos:
        try:
            await fn()
        except AssertionError as exc:
            print(f"  FAIL  {nome}: {exc}")
            falhas += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {nome}: {type(exc).__name__}: {exc}")
            falhas += 1
    print("=" * 70)
    print(f"Resultado: {len(casos) - falhas}/{len(casos)} casos OK")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

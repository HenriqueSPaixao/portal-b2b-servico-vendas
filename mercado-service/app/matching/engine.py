import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from uuid import UUID, uuid4

from app.matching.snapshot import Demanda, Oferta, Snapshot
from b2b_shared.events import Topic, build_envelope
from b2b_shared.kafka import KafkaProducer

logger = logging.getLogger(__name__)


MODO_DIRETO = "direto"
MODO_LEILAO_DIRETO = "leilao_direto"
MODO_LEILAO_REVERSO = "leilao_reverso"


@dataclass
class ProcessoDisparado:
    processo_id: UUID
    produto_id: UUID
    modo: str
    data_inicio: datetime
    data_fim: datetime
    quantidade: Decimal
    valor_reserva: Decimal | None


@dataclass
class EngineState:
    processos: dict[UUID, ProcessoDisparado] = field(default_factory=dict)


class MatchingEngine:
    """Decide o modo de negociação a partir de oferta e demanda.

    Regra (das notas do Henrique e do doc do BD):
      - oferta == demanda (com tolerância) → 'direto'
      - demanda > oferta → 'leilao_direto' (compradores competem)
      - oferta > demanda → 'leilao_reverso' (fornecedores competem)
    """

    def __init__(
        self,
        *,
        snapshot: Snapshot,
        producer: KafkaProducer,
        source_name: str,
        tolerance_percent: float = 5.0,
        default_auction_duration_seconds: int = 120,
    ) -> None:
        self._snapshot = snapshot
        self._producer = producer
        self._source = source_name
        self._tolerance = Decimal(str(tolerance_percent)) / Decimal(100)
        self._auction_duration = timedelta(seconds=default_auction_duration_seconds)
        self._state = EngineState()
        self._lock = Lock()

    @property
    def state(self) -> EngineState:
        return self._state

    async def evaluate(self, produto_id: UUID) -> ProcessoDisparado | None:
        # Lock pra evitar dois consumers disparando processo simultâneo do mesmo produto.
        with self._lock:
            ofertas = self._snapshot.ofertas_ativas(produto_id)
            demandas = self._snapshot.demandas_ativas(produto_id)
            if not ofertas or not demandas:
                return None

            total_oferta = sum((o.quantidade for o in ofertas), start=Decimal(0))
            total_demanda = sum((d.quantidade for d in demandas), start=Decimal(0))
            if total_oferta <= 0 or total_demanda <= 0:
                return None

            modo, quantidade_matched = self._decidir_modo(total_oferta, total_demanda)
            envolvidas_ofertas, envolvidas_demandas = self._selecionar_envolvidas(
                modo, ofertas, demandas
            )

            processo = self._construir_processo(
                produto_id=produto_id,
                modo=modo,
                quantidade=quantidade_matched,
                ofertas=envolvidas_ofertas,
                demandas=envolvidas_demandas,
            )
            self._state.processos[processo.processo_id] = processo
            self._snapshot.marcar_consumidas(envolvidas_ofertas, envolvidas_demandas)

        await self._publicar_processo(processo, envolvidas_ofertas, envolvidas_demandas)
        return processo

    def _decidir_modo(
        self, total_oferta: Decimal, total_demanda: Decimal
    ) -> tuple[str, Decimal]:
        maior = max(total_oferta, total_demanda)
        diff = abs(total_oferta - total_demanda) / maior if maior > 0 else Decimal(0)
        if diff <= self._tolerance:
            return MODO_DIRETO, min(total_oferta, total_demanda)
        if total_demanda > total_oferta:
            return MODO_LEILAO_DIRETO, total_oferta
        return MODO_LEILAO_REVERSO, total_demanda

    def _selecionar_envolvidas(
        self,
        modo: str,
        ofertas: list[Oferta],
        demandas: list[Demanda],
    ) -> tuple[list[Oferta], list[Demanda]]:
        if modo == MODO_DIRETO:
            # 1:1 — pega a maior oferta e maior demanda
            return ([max(ofertas, key=lambda o: o.quantidade)],
                    [max(demandas, key=lambda d: d.quantidade)])
        if modo == MODO_LEILAO_DIRETO:
            # 1 oferta (maior) + N demandas competindo
            return [max(ofertas, key=lambda o: o.quantidade)], list(demandas)
        # LEILAO_REVERSO: 1 demanda (maior) + N ofertas competindo
        return list(ofertas), [max(demandas, key=lambda d: d.quantidade)]

    def _construir_processo(
        self,
        *,
        produto_id: UUID,
        modo: str,
        quantidade: Decimal,
        ofertas: list[Oferta],
        demandas: list[Demanda],
    ) -> ProcessoDisparado:
        agora = datetime.now(timezone.utc)
        data_fim = agora if modo == MODO_DIRETO else agora + self._auction_duration

        if modo == MODO_DIRETO:
            valor_reserva = ofertas[0].preco_unitario
        elif modo == MODO_LEILAO_DIRETO:
            valor_reserva = ofertas[0].preco_unitario  # piso para os compradores
        else:  # LEILAO_REVERSO
            valor_reserva = demandas[0].preco_maximo  # teto para os fornecedores

        return ProcessoDisparado(
            processo_id=uuid4(),
            produto_id=produto_id,
            modo=modo,
            data_inicio=agora,
            data_fim=data_fim,
            quantidade=quantidade,
            valor_reserva=valor_reserva,
        )

    async def _publicar_processo(
        self,
        processo: ProcessoDisparado,
        ofertas: list[Oferta],
        demandas: list[Demanda],
    ) -> None:
        payload = self._payload_modo_definido(processo, ofertas, demandas)
        envelope_modo = build_envelope(
            event_type=Topic.MODO_NEGOCIACAO_DEFINIDO.value,
            source=self._source,
            payload=payload,
        )
        await self._producer.publish(
            Topic.MODO_NEGOCIACAO_DEFINIDO.value, envelope_modo
        )

        if processo.modo != MODO_DIRETO:
            envelope_leilao = build_envelope(
                event_type=Topic.LEILAO_INICIADO.value,
                source=self._source,
                correlation_id=envelope_modo.correlation_id,
                payload={
                    "processo_id": str(processo.processo_id),
                    "produto_id": str(processo.produto_id),
                    "modo": processo.modo,
                    "data_inicio": processo.data_inicio.isoformat(),
                    "data_fim": processo.data_fim.isoformat(),
                },
            )
            await self._producer.publish(Topic.LEILAO_INICIADO.value, envelope_leilao)

        logger.info(
            "Processo disparado",
            extra={
                "processo_id": str(processo.processo_id),
                "modo": processo.modo,
                "produto_id": str(processo.produto_id),
                "quantidade": str(processo.quantidade),
            },
        )

    def _payload_modo_definido(
        self,
        processo: ProcessoDisparado,
        ofertas: list[Oferta],
        demandas: list[Demanda],
    ) -> dict:
        modo = processo.modo
        empresa_fornecedor_principal: UUID | None = None
        empresa_comprador_principal: UUID | None = None
        fornecimento_id: UUID | None = None
        demanda_id: UUID | None = None
        empresas_compradoras: list[str] = []
        empresas_fornecedoras: list[str] = []

        if modo == MODO_DIRETO:
            empresa_fornecedor_principal = ofertas[0].empresa_fornecedor_id
            empresa_comprador_principal = demandas[0].empresa_comprador_id
            fornecimento_id = ofertas[0].fornecimento_id
            demanda_id = demandas[0].demanda_id
        elif modo == MODO_LEILAO_DIRETO:
            empresa_fornecedor_principal = ofertas[0].empresa_fornecedor_id
            fornecimento_id = ofertas[0].fornecimento_id
            empresas_compradoras = [
                str(d.empresa_comprador_id) for d in demandas
            ]
        else:  # LEILAO_REVERSO
            empresa_comprador_principal = demandas[0].empresa_comprador_id
            demanda_id = demandas[0].demanda_id
            empresas_fornecedoras = [
                str(o.empresa_fornecedor_id) for o in ofertas
            ]

        return {
            "processo_id": str(processo.processo_id),
            "produto_id": str(processo.produto_id),
            "modo": modo,
            "data_inicio": processo.data_inicio.isoformat(),
            "data_fim": processo.data_fim.isoformat(),
            "quantidade": str(processo.quantidade),
            "valor_reserva": (
                str(processo.valor_reserva)
                if processo.valor_reserva is not None
                else None
            ),
            "fornecimento_id": (
                str(fornecimento_id) if fornecimento_id else None
            ),
            "demanda_id": str(demanda_id) if demanda_id else None,
            "empresa_comprador_principal": (
                str(empresa_comprador_principal)
                if empresa_comprador_principal
                else None
            ),
            "empresa_fornecedor_principal": (
                str(empresa_fornecedor_principal)
                if empresa_fornecedor_principal
                else None
            ),
            "empresas_compradoras_habilitadas": empresas_compradoras,
            "empresas_fornecedoras_habilitadas": empresas_fornecedoras,
        }

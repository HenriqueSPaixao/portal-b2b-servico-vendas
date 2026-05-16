import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ModoNegociacao, StatusProcesso
from app.metadata_cache import ProcessoMeta, ProcessoMetaCache
from app.models import Lance, ProcessoNegociacao
from app.repository import ProcessoRepository
from b2b_shared.events import Topic, build_envelope
from b2b_shared.kafka import KafkaProducer

logger = logging.getLogger(__name__)


class NegociacaoServiceError(Exception):
    pass


class ProcessoNaoEncontrado(NegociacaoServiceError):
    pass


class ProcessoEncerrado(NegociacaoServiceError):
    pass


class EmpresaNaoHabilitada(NegociacaoServiceError):
    pass


class ModoIncompatibilComLance(NegociacaoServiceError):
    pass


@dataclass
class FechamentoResultado:
    processo_id: UUID
    vencedor_lance_id: UUID | None
    empresa_comprador_id: UUID | None
    empresa_fornecedor_id: UUID | None
    valor_unitario_final: Decimal
    quantidade: Decimal
    valor_total: Decimal


class NegociacaoService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        producer: KafkaProducer,
        metadata: ProcessoMetaCache,
        source_name: str,
    ) -> None:
        self._repo = ProcessoRepository(session)
        self._session = session
        self._producer = producer
        self._metadata = metadata
        self._source = source_name

    # ------------------------------------------------------------------ #
    # Criação via consumo de Kafka
    # ------------------------------------------------------------------ #

    async def criar_a_partir_de_modo_definido(
        self,
        *,
        processo_id: UUID,
        produto_id: UUID,
        modo: str,
        data_inicio: datetime,
        data_fim: datetime,
        valor_reserva: Decimal | None,
        meta: ProcessoMeta,
    ) -> ProcessoNegociacao:
        existente = await self._repo.get(processo_id)
        if existente is not None:
            # Idempotência — consumer pode reentregar
            self._metadata.put(meta)
            return existente

        processo = ProcessoNegociacao(
            id=processo_id,
            produto_id=produto_id,
            modo=modo,
            status=StatusProcesso.ABERTO.value,
            data_inicio=data_inicio,
            data_fim=data_fim,
            valor_reserva=valor_reserva,
        )
        self._repo.add(processo)
        await self._session.flush()
        self._metadata.put(meta)
        logger.info(
            "Processo criado",
            extra={"processo_id": str(processo_id), "modo": modo},
        )
        return processo

    # ------------------------------------------------------------------ #
    # Lance
    # ------------------------------------------------------------------ #

    async def registrar_lance(
        self,
        *,
        processo_id: UUID,
        empresa_id: UUID,
        valor_unitario: Decimal,
        quantidade: Decimal,
    ) -> Lance:
        processo = await self._repo.get_for_update(processo_id)
        if processo is None:
            raise ProcessoNaoEncontrado(f"Processo {processo_id} não encontrado")
        if processo.status != StatusProcesso.ABERTO.value:
            raise ProcessoEncerrado(f"Processo {processo_id} já está {processo.status}")

        meta = self._metadata.get(processo_id)
        self._validar_elegibilidade(processo.modo, empresa_id, meta)

        lance = Lance(
            id=uuid4(),
            processo_id=processo_id,
            empresa_id=empresa_id,
            valor_unitario=valor_unitario,
            quantidade=quantidade,
            data_lance=datetime.now(timezone.utc),
        )
        self._repo.add_lance(lance)
        await self._session.flush()

        envelope = build_envelope(
            event_type=Topic.LANCE_REALIZADO.value,
            source=self._source,
            payload={
                "lance_id": str(lance.id),
                "processo_id": str(processo_id),
                "empresa_id": str(empresa_id),
                "valor_unitario": str(valor_unitario),
                "quantidade": str(quantidade),
                "data_lance": lance.data_lance.isoformat(),
            },
        )
        await self._producer.publish(Topic.LANCE_REALIZADO.value, envelope)

        logger.info(
            "Lance registrado",
            extra={
                "processo_id": str(processo_id),
                "lance_id": str(lance.id),
                "empresa_id": str(empresa_id),
            },
        )
        return lance

    def _validar_elegibilidade(
        self,
        modo: str,
        empresa_id: UUID,
        meta: ProcessoMeta | None,
    ) -> None:
        if modo == ModoNegociacao.DIRETO.value:
            raise ModoIncompatibilComLance(
                "Processo em modo 'direto' não aceita lances — fecha automaticamente."
            )
        if meta is None:
            # Sem metadata em cache (provável restart) — não temos como validar.
            # Aceita o lance e loga warning. Operador deve reiniciar fluxo se quiser
            # endurecer.
            logger.warning(
                "Metadata ausente — pulando validação de elegibilidade",
                extra={"empresa_id": str(empresa_id)},
            )
            return
        habilitadas: list[UUID]
        if modo == ModoNegociacao.LEILAO_DIRETO.value:
            habilitadas = meta.empresas_compradoras_habilitadas
        else:  # LEILAO_REVERSO
            habilitadas = meta.empresas_fornecedoras_habilitadas
        if habilitadas and empresa_id not in habilitadas:
            raise EmpresaNaoHabilitada(
                f"Empresa {empresa_id} não está habilitada a dar lance neste processo"
            )

    # ------------------------------------------------------------------ #
    # Fechamento
    # ------------------------------------------------------------------ #

    async def fechar_processo(
        self,
        processo_id: UUID,
        *,
        motivo: str = "expirado",
    ) -> FechamentoResultado | None:
        processo = await self._repo.get_for_update(processo_id)
        if processo is None:
            raise ProcessoNaoEncontrado(f"Processo {processo_id} não encontrado")
        if processo.status != StatusProcesso.ABERTO.value:
            logger.info(
                "Processo já estava fechado, ignorando",
                extra={"processo_id": str(processo_id), "status": processo.status},
            )
            return None

        meta = self._metadata.get(processo_id)
        resultado = self._calcular_vencedor(processo, meta)

        processo.status = StatusProcesso.FECHADA.value
        await self._session.flush()

        envelope = build_envelope(
            event_type=Topic.NEGOCIACAO_FECHADA.value,
            source=self._source,
            correlation_id=meta.correlation_id if meta else None,
            payload={
                "processo_id": str(processo.id),
                "produto_id": str(processo.produto_id),
                "modo": processo.modo,
                "empresa_comprador_id": (
                    str(resultado.empresa_comprador_id)
                    if resultado.empresa_comprador_id
                    else None
                ),
                "empresa_fornecedor_id": (
                    str(resultado.empresa_fornecedor_id)
                    if resultado.empresa_fornecedor_id
                    else None
                ),
                "fornecimento_id": (
                    str(meta.fornecimento_id) if meta and meta.fornecimento_id else None
                ),
                "demanda_id": (
                    str(meta.demanda_id) if meta and meta.demanda_id else None
                ),
                "quantidade": str(resultado.quantidade),
                "valor_unitario_final": str(resultado.valor_unitario_final),
                "valor_total": str(resultado.valor_total),
                "vencedor_lance_id": (
                    str(resultado.vencedor_lance_id)
                    if resultado.vencedor_lance_id
                    else None
                ),
                "motivo_fechamento": motivo,
                "data_fechamento": datetime.now(timezone.utc).isoformat(),
            },
        )
        await self._producer.publish(Topic.NEGOCIACAO_FECHADA.value, envelope)

        # Limpa cache — processo encerrado.
        self._metadata.drop(processo_id)

        logger.info(
            "Processo fechado",
            extra={
                "processo_id": str(processo.id),
                "modo": processo.modo,
                "vencedor_lance_id": (
                    str(resultado.vencedor_lance_id)
                    if resultado.vencedor_lance_id
                    else "none"
                ),
            },
        )
        return resultado

    def _calcular_vencedor(
        self,
        processo: ProcessoNegociacao,
        meta: ProcessoMeta | None,
    ) -> FechamentoResultado:
        modo = processo.modo
        lances = list(processo.lances)

        if modo == ModoNegociacao.DIRETO.value:
            comprador = meta.empresa_comprador_principal if meta else None
            fornecedor = meta.empresa_fornecedor_principal if meta else None
            quantidade = meta.quantidade if meta else Decimal(0)
            valor_unitario = processo.valor_reserva or Decimal(0)
            return FechamentoResultado(
                processo_id=processo.id,
                vencedor_lance_id=None,
                empresa_comprador_id=comprador,
                empresa_fornecedor_id=fornecedor,
                valor_unitario_final=valor_unitario,
                quantidade=quantidade,
                valor_total=valor_unitario * quantidade,
            )

        if not lances:
            # Leilão sem participantes — fecha sem vencedor.
            comprador = meta.empresa_comprador_principal if meta else None
            fornecedor = meta.empresa_fornecedor_principal if meta else None
            return FechamentoResultado(
                processo_id=processo.id,
                vencedor_lance_id=None,
                empresa_comprador_id=comprador,
                empresa_fornecedor_id=fornecedor,
                valor_unitario_final=Decimal(0),
                quantidade=Decimal(0),
                valor_total=Decimal(0),
            )

        if modo == ModoNegociacao.LEILAO_DIRETO.value:
            vencedor = max(lances, key=lambda l: l.valor_unitario)
            comprador = vencedor.empresa_id
            fornecedor = meta.empresa_fornecedor_principal if meta else None
        else:  # LEILAO_REVERSO
            vencedor = min(lances, key=lambda l: l.valor_unitario)
            comprador = meta.empresa_comprador_principal if meta else None
            fornecedor = vencedor.empresa_id

        return FechamentoResultado(
            processo_id=processo.id,
            vencedor_lance_id=vencedor.id,
            empresa_comprador_id=comprador,
            empresa_fornecedor_id=fornecedor,
            valor_unitario_final=vencedor.valor_unitario,
            quantidade=vencedor.quantidade,
            valor_total=vencedor.valor_unitario * vencedor.quantidade,
        )

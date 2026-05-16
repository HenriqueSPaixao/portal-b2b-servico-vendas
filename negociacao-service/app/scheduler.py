import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.metadata_cache import ProcessoMetaCache
from app.repository import ProcessoRepository
from app.service import NegociacaoService
from b2b_shared.kafka import KafkaProducer

logger = logging.getLogger(__name__)


class AuctionScheduler:
    """Background task que encerra processos com data_fim expirada.

    Executa em loop a cada `poll_interval_seconds`. Para cada processo
    ABERTO com data_fim no passado, publica negociacao_fechada.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        producer: KafkaProducer,
        metadata: ProcessoMetaCache,
        source_name: str,
        poll_interval_seconds: int = 5,
    ) -> None:
        self._session_factory = session_factory
        self._producer = producer
        self._metadata = metadata
        self._source = source_name
        self._poll_interval = poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="auction-scheduler")
        logger.info(
            "Scheduler started",
            extra={"poll_interval_seconds": self._poll_interval},
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
        logger.info("Scheduler stopped")

    async def _run(self) -> None:
        try:
            while not self._stopping.is_set():
                try:
                    await self._tick()
                except Exception:  # noqa: BLE001 — loop resiliente
                    logger.exception("Erro no tick do scheduler")
                try:
                    await asyncio.wait_for(
                        self._stopping.wait(), timeout=self._poll_interval
                    )
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise

    async def _tick(self) -> None:
        agora = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            repo = ProcessoRepository(session)
            expirados = await repo.list_abertos_expirados(agora)
        if not expirados:
            return
        logger.info(
            "Processos expirados encontrados",
            extra={"qtd": len(expirados)},
        )
        for processo in expirados:
            async with self._session_factory() as session:
                async with session.begin():
                    service = NegociacaoService(
                        session,
                        producer=self._producer,
                        metadata=self._metadata,
                        source_name=self._source,
                    )
                    try:
                        await service.fechar_processo(processo.id, motivo="expirado")
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "Falha ao fechar processo",
                            extra={"processo_id": str(processo.id)},
                        )

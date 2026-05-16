from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Lance, ProcessoNegociacao


class ProcessoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, processo_id: UUID) -> ProcessoNegociacao | None:
        result = await self._session.execute(
            select(ProcessoNegociacao)
            .options(selectinload(ProcessoNegociacao.lances))
            .where(ProcessoNegociacao.id == processo_id)
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, processo_id: UUID) -> ProcessoNegociacao | None:
        result = await self._session.execute(
            select(ProcessoNegociacao)
            .options(selectinload(ProcessoNegociacao.lances))
            .where(ProcessoNegociacao.id == processo_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_(
        self,
        *,
        status: str | None = None,
        modo: str | None = None,
        produto_id: UUID | None = None,
        limit: int = 100,
    ) -> list[ProcessoNegociacao]:
        stmt = select(ProcessoNegociacao).order_by(ProcessoNegociacao.data_inicio.desc())
        if status:
            stmt = stmt.where(ProcessoNegociacao.status == status)
        if modo:
            stmt = stmt.where(ProcessoNegociacao.modo == modo)
        if produto_id:
            stmt = stmt.where(ProcessoNegociacao.produto_id == produto_id)
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_abertos_expirados(self, agora: datetime) -> list[ProcessoNegociacao]:
        result = await self._session.execute(
            select(ProcessoNegociacao).where(
                ProcessoNegociacao.status == "ABERTO",
                ProcessoNegociacao.data_fim <= agora,
            )
        )
        return list(result.scalars().all())

    def add(self, processo: ProcessoNegociacao) -> None:
        self._session.add(processo)

    def add_lance(self, lance: Lance) -> None:
        self._session.add(lance)

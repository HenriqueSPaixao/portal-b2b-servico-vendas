from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import ProcessoRepository
from app.schemas import LanceInput, LanceOut, ProcessoDetalhadoOut, ProcessoOut
from app.service import (
    EmpresaNaoHabilitada,
    ModoIncompatibilComLance,
    NegociacaoService,
    ProcessoEncerrado,
    ProcessoNaoEncontrado,
)
from b2b_shared.auth import CurrentUser, require_user
from b2b_shared.db import get_session

router = APIRouter(prefix="/api/negociacao", tags=["negociacao"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[CurrentUser, Depends(require_user)]


def _service_from_request(request: Request, session: AsyncSession) -> NegociacaoService:
    return NegociacaoService(
        session,
        producer=request.app.state.producer,
        metadata=request.app.state.metadata_cache,
        source_name=request.app.state.service_name,
    )


@router.get("/processos", response_model=list[ProcessoOut])
async def list_processos(
    session: SessionDep,
    _user: UserDep,
    status_: Annotated[str | None, Query(alias="status")] = None,
    modo: str | None = None,
    produto_id: UUID | None = None,
    limit: int = 100,
) -> list[ProcessoOut]:
    repo = ProcessoRepository(session)
    rows = await repo.list_(
        status=status_, modo=modo, produto_id=produto_id, limit=limit
    )
    return [ProcessoOut.model_validate(r) for r in rows]


@router.get("/processos/{processo_id}", response_model=ProcessoDetalhadoOut)
async def get_processo(
    processo_id: UUID,
    session: SessionDep,
    _user: UserDep,
) -> ProcessoDetalhadoOut:
    repo = ProcessoRepository(session)
    processo = await repo.get(processo_id)
    if processo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )
    return ProcessoDetalhadoOut.model_validate(processo)


@router.post(
    "/processos/{processo_id}/lances",
    response_model=LanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_lance(
    processo_id: UUID,
    body: LanceInput,
    request: Request,
    session: SessionDep,
    user: UserDep,
) -> LanceOut:
    empresa_id = body.empresa_id_override or user.empresa_id
    if empresa_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empresa_id ausente: token sem claim 'empresa_id' e sem override",
        )

    service = _service_from_request(request, session)
    try:
        async with session.begin():
            lance = await service.registrar_lance(
                processo_id=processo_id,
                empresa_id=empresa_id,
                valor_unitario=body.valor_unitario,
                quantidade=body.quantidade,
            )
    except ProcessoNaoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (ProcessoEncerrado, ModoIncompatibilComLance) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except EmpresaNaoHabilitada as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return LanceOut.model_validate(lance)


@router.post("/processos/{processo_id}/fechar", response_model=ProcessoOut)
async def fechar_processo(
    processo_id: UUID,
    request: Request,
    session: SessionDep,
    _user: UserDep,
) -> ProcessoOut:
    service = _service_from_request(request, session)
    try:
        async with session.begin():
            await service.fechar_processo(processo_id, motivo="manual_admin")
    except ProcessoNaoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    repo = ProcessoRepository(session)
    processo = await repo.get(processo_id)
    assert processo is not None
    return ProcessoOut.model_validate(processo)

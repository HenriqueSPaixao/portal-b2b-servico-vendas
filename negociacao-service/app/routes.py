import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import ProcessoRepository
from app.schemas import LanceInput, LanceOut, ProcessoDetalhadoOut, ProcessoOut
from app.service import (
    EmpresaNaoHabilitada,
    LanceInvalido,
    ModoIncompatibilComLance,
    NegociacaoService,
    ProcessoEncerrado,
    ProcessoNaoEncontrado,
)
from b2b_shared.auth import CurrentUser, require_user
from b2b_shared.auth.jwt import JWTValidationError
from b2b_shared.db import get_session

router = APIRouter(tags=["negociacao"])

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
    request: Request,
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
    cache = request.app.state.produto_cache
    meta_cache = request.app.state.metadata_cache
    result: list[ProcessoOut] = []
    for r in rows:
        item = ProcessoOut.model_validate(r)
        item.produto_nome = cache.get_nome(item.produto_id)
        meta = meta_cache.get(r.id)
        if meta is not None:
            item.quantidade = meta.quantidade
        result.append(item)
    return result


@router.get("/processos/abertos-para-mim", response_model=list[ProcessoOut])
async def processos_abertos_para_mim(
    request: Request,
    session: SessionDep,
    user: UserDep,
    empresa_id: UUID | None = None,
) -> list[ProcessoOut]:
    """Leilões ABERTOS em que a empresa logada está habilitada a dar lance.

    Usa o `empresa_id` do JWT (ou `?empresa_id=` para tooling) e cruza com a
    habilitação do processo (compradores no leilão direto, fornecedores no
    reverso) guardada no metadata cache. É o ponto de entrada do fornecedor para
    achar os leilões reversos do mesmo produto onde ele compete. NOTA: depende do
    cache em memória; processos sem metadata (após restart) são omitidos.
    """
    alvo = empresa_id or user.empresa_id
    if alvo is None:
        return []
    repo = ProcessoRepository(session)
    rows = await repo.list_(status="ABERTO", limit=200)
    meta_cache = request.app.state.metadata_cache
    cache = request.app.state.produto_cache
    result: list[ProcessoOut] = []
    for r in rows:
        meta = meta_cache.get(r.id)
        if meta is None:
            continue
        if r.modo == "leilao_direto":
            habilitadas = meta.empresas_compradoras_habilitadas
        elif r.modo == "leilao_reverso":
            habilitadas = meta.empresas_fornecedoras_habilitadas
        else:
            continue  # 'direto' não tem lances
        if habilitadas and alvo in habilitadas:
            item = ProcessoOut.model_validate(r)
            item.produto_nome = cache.get_nome(item.produto_id)
            item.quantidade = meta.quantidade
            result.append(item)
    return result


@router.get("/processos/{processo_id}", response_model=ProcessoDetalhadoOut)
async def get_processo(
    processo_id: UUID,
    request: Request,
    session: SessionDep,
    _user: UserDep,
) -> ProcessoDetalhadoOut:
    repo = ProcessoRepository(session)
    processo = await repo.get(processo_id)
    if processo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )
    detalhado = ProcessoDetalhadoOut.model_validate(processo)
    detalhado.produto_nome = request.app.state.produto_cache.get_nome(detalhado.produto_id)
    meta = request.app.state.metadata_cache.get(processo_id)
    if meta is not None:
        detalhado.quantidade = meta.quantidade
    return detalhado


@router.get("/produtos")
async def produtos_conhecidos(request: Request, _user: UserDep) -> list[dict]:
    """Lista produtos vistos via `produto_cadastrado` no Kafka, ordenados por
    nome. Usado pelo autocomplete do negociacao-web (mapeia nome -> produto_id
    sem expor UUID ao usuário). Vazio até o primeiro evento chegar."""
    cache = request.app.state.produto_cache
    return cache.list_all()


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
    except LanceInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except EmpresaNaoHabilitada as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

    # Empurra o lance para os navegadores conectados via SSE (tempo real).
    request.app.state.lance_broker.publish(
        processo_id,
        {
            "lance_id": str(lance.id),
            "empresa_id": str(lance.empresa_id),
            "valor_unitario": str(lance.valor_unitario),
            "quantidade": str(lance.quantidade),
            "data_lance": lance.data_lance.isoformat(),
        },
    )
    return LanceOut.model_validate(lance)


@router.get("/processos/{processo_id}/stream")
async def stream_lances(
    processo_id: UUID,
    request: Request,
    jwt: str | None = None,
) -> StreamingResponse:
    """Stream SSE dos lances de um processo (tempo real).

    O EventSource do navegador não envia header Authorization, então o token vem
    por query string (`?jwt=`). Canal interno (negociacao-web ⇄ negociacao-service);
    o header `X-Accel-Buffering: no` desliga o buffer do Nginx só nesta resposta,
    sem exigir mudança no gateway.
    """
    validator = request.app.state.jwt_validator
    try:
        if not jwt:
            raise JWTValidationError("token ausente")
        validator.decode(jwt)
    except JWTValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalido no stream: {exc}",
        ) from exc

    broker = request.app.state.lance_broker
    queue = broker.subscribe(processo_id)

    async def event_gen():
        try:
            yield ": conectado\n\n"  # abre o stream
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: lance\ndata: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"  # heartbeat anti-timeout de proxy
        finally:
            broker.unsubscribe(processo_id, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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

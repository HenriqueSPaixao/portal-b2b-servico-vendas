from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from b2b_shared.auth import CurrentUser, require_user

router = APIRouter(tags=["mercado"])

UserDep = Annotated[CurrentUser, Depends(require_user)]


@router.get("/snapshot/{produto_id}")
async def snapshot(produto_id: UUID, request: Request, _user: UserDep) -> dict:
    snap = request.app.state.snapshot
    cache = request.app.state.produto_cache
    info = cache.get(produto_id)
    data = snap.to_dict(produto_id)
    data["produto"] = (
        {
            "id": str(info.produto_id),
            "nome": info.nome,
            "codigo": info.codigo,
        }
        if info is not None
        else None
    )
    return data


@router.get("/processos")
async def processos_disparados(request: Request, _user: UserDep) -> list[dict]:
    engine = request.app.state.matching_engine
    cache = request.app.state.produto_cache
    return [
        {
            "processo_id": str(p.processo_id),
            "produto_id": str(p.produto_id),
            "produto_nome": cache.get_nome(p.produto_id),
            "modo": p.modo,
            "data_inicio": p.data_inicio.isoformat(),
            "data_fim": p.data_fim.isoformat(),
            "quantidade": str(p.quantidade),
            "valor_reserva": (
                str(p.valor_reserva) if p.valor_reserva is not None else None
            ),
        }
        for p in engine.state.processos.values()
    ]


@router.get("/produtos")
async def produtos_conhecidos(request: Request, _user: UserDep) -> list[dict]:
    """Lista produtos vistos via `produto_cadastrado` no Kafka.

    Usado pelo autocomplete do mercado-web (nome -> produto_id). Vazio até o
    primeiro evento chegar.
    """
    cache = request.app.state.produto_cache
    return cache.list_all()

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from b2b_shared.auth import CurrentUser, require_user

router = APIRouter(prefix="/api/mercado", tags=["mercado"])

UserDep = Annotated[CurrentUser, Depends(require_user)]


@router.get("/snapshot/{produto_id}")
async def snapshot(produto_id: UUID, request: Request, _user: UserDep) -> dict:
    snap = request.app.state.snapshot
    return snap.to_dict(produto_id)


@router.get("/processos")
async def processos_disparados(request: Request, _user: UserDep) -> list[dict]:
    engine = request.app.state.matching_engine
    return [
        {
            "processo_id": str(p.processo_id),
            "produto_id": str(p.produto_id),
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

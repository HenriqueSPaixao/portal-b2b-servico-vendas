from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from b2b_shared.auth import CurrentUser, require_user

router = APIRouter(tags=["mercado"])

UserDep = Annotated[CurrentUser, Depends(require_user)]


class ConfirmarPropostaInput(BaseModel):
    """'sim' abre o leilão direto; 'nao' encerra a proposta dentro do mercado."""

    decisao: str
    # Override do fornecedor (tooling/smoke). Em uso normal vem do JWT (empresa_id).
    fornecedor_id_override: UUID | None = None


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


@router.get("/propostas")
async def propostas_pendentes(
    request: Request,
    user: UserDep,
    fornecedor_id: UUID | None = None,
) -> list[dict]:
    """Propostas de leilão direto aguardando o 'sim/não' do fornecedor.

    Mercado voltado ao fornecedor: por padrão filtra pelo `empresa_id` do JWT
    (o fornecedor vê só os leilões que pode abrir). `?fornecedor_id=` força um
    filtro específico (tooling/smoke); sem nenhum dos dois, lista todas.
    """
    engine = request.app.state.matching_engine
    cache = request.app.state.produto_cache
    alvo = fornecedor_id or user.empresa_id
    itens = engine.propostas_pendentes(fornecedor_id=alvo)
    for it in itens:
        it["produto_nome"] = cache.get_nome(UUID(it["produto_id"]))
    return itens


@router.get("/propostas/log")
async def propostas_log(request: Request, _user: UserDep) -> list[dict]:
    """Log (in-memory) das decisões sim/não do fornecedor, mais recentes primeiro."""
    engine = request.app.state.matching_engine
    cache = request.app.state.produto_cache
    log = engine.decisoes_log()
    for entry in log:
        entry["produto_nome"] = cache.get_nome(UUID(entry["produto_id"]))
    return log


@router.post("/propostas/{processo_id}/confirmar")
async def confirmar_proposta(
    processo_id: UUID,
    body: ConfirmarPropostaInput,
    request: Request,
    user: UserDep,
) -> dict:
    """O fornecedor decide abrir ('sim') ou recusar ('nao') o leilão direto.

    'nao' é resolvido 100% dentro do mercado-service — nada é publicado e
    nenhuma outra equipe é acionada.
    """
    decisao = body.decisao.strip().lower()
    if decisao not in ("sim", "s", "nao", "não", "n"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campo 'decisao' deve ser 'sim' ou 'nao'",
        )
    fornecedor_id = body.fornecedor_id_override or user.empresa_id
    engine = request.app.state.matching_engine
    result = await engine.confirmar_proposta(
        processo_id, decisao=decisao, fornecedor_id=fornecedor_id
    )
    if result.get("status") == "nao_encontrada":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposta não encontrada (já confirmada ou inexistente)",
        )
    if result.get("status") == "fornecedor_invalido":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta proposta pertence a outro fornecedor",
        )
    return result

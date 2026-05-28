from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ModoLiteral = Literal["direto", "leilao_direto", "leilao_reverso"]
# CONCLUIDO incluído porque outras equipes (ex.: demanda-service) marcam processos
# com esse status no banco compartilhado após gerar pedido. Sem isso, GET /processos
# quebra com 500 em registros legados.
StatusLiteral = Literal["ABERTO", "FECHADA", "CANCELADO", "CONCLUIDO"]


class LanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    processo_id: UUID
    empresa_id: UUID
    valor_unitario: Decimal
    quantidade: Decimal
    data_lance: datetime


class ProcessoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    produto_id: UUID
    modo: ModoLiteral
    status: StatusLiteral
    data_inicio: datetime
    # nullable: DDL permite NULL e há registros antigos sem data_fim no banco compartilhado
    data_fim: datetime | None = None
    valor_reserva: Decimal | None


class ProcessoDetalhadoOut(ProcessoOut):
    lances: list[LanceOut] = Field(default_factory=list)


class LanceInput(BaseModel):
    valor_unitario: Decimal = Field(..., gt=0)
    quantidade: Decimal = Field(..., gt=0)
    # empresa_id vem do JWT, não do body — mas em alguns testes pode-se forçar.
    # Aqui mantemos opcional; o service só usa quando vier de admin.
    empresa_id_override: UUID | None = None

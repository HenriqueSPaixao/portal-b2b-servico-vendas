from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ModoLiteral = Literal["direto", "leilao_direto", "leilao_reverso"]
# Status canônicos que ESTE serviço produz/conhece (ABERTO/FECHADA) + os que outras
# equipes marcam no banco compartilhado (CANCELADO/CONCLUIDO/ENCERRADO). Mantido só
# como documentação: o campo abaixo é `str`, não este Literal, porque o banco é
# compartilhado e não controlamos todo status que outras equipes possam gravar — um
# valor desconhecido NÃO pode derrubar GET /processos inteiro com 500 (já aconteceu
# com CONCLUIDO e depois com ENCERRADO).
StatusLiteral = Literal["ABERTO", "FECHADA", "CANCELADO", "CONCLUIDO", "ENCERRADO"]


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
    produto_nome: str | None = None
    modo: ModoLiteral
    status: str
    data_inicio: datetime
    # nullable: DDL permite NULL e há registros antigos sem data_fim no banco compartilhado
    data_fim: datetime | None = None
    valor_reserva: Decimal | None
    # Quantidade do lote (vem do metadata cache; o lance é sempre pelo lote inteiro).
    quantidade: Decimal | None = None


class ProcessoDetalhadoOut(ProcessoOut):
    lances: list[LanceOut] = Field(default_factory=list)


class LanceInput(BaseModel):
    valor_unitario: Decimal = Field(..., gt=0)
    quantidade: Decimal = Field(..., gt=0)
    # empresa_id vem do JWT, não do body — mas em alguns testes pode-se forçar.
    # Aqui mantemos opcional; o service só usa quando vier de admin.
    empresa_id_override: UUID | None = None

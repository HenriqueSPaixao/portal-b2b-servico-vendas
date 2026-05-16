from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock
from uuid import UUID


@dataclass
class ProcessoMeta:
    """Metadados de um processo de negociação que não estão na tabela canônica.

    A tabela `portal_b2b.processo_negociacao` (DDL de Eq. BD) só guarda
    `id, produto_id, modo, status, data_inicio, data_fim, valor_reserva`.
    Para que `negociacao_fechada` seja self-contained, precisamos manter
    aqui as referências às empresas/fornecimentos/demanda envolvidos.

    Persistência: por ora em memória. Em restart perdemos in-flight (aceitável
    para o MVP do trabalho). Para produção, alinhar com BD para adicionar
    colunas ou tabela espelho.
    """

    processo_id: UUID
    produto_id: UUID
    modo: str
    quantidade: Decimal
    correlation_id: UUID | None = None
    fornecimento_id: UUID | None = None
    demanda_id: UUID | None = None
    empresa_comprador_principal: UUID | None = None
    empresa_fornecedor_principal: UUID | None = None
    empresas_compradoras_habilitadas: list[UUID] = field(default_factory=list)
    empresas_fornecedoras_habilitadas: list[UUID] = field(default_factory=list)


class ProcessoMetaCache:
    def __init__(self) -> None:
        self._store: dict[UUID, ProcessoMeta] = {}
        self._lock = Lock()

    def put(self, meta: ProcessoMeta) -> None:
        with self._lock:
            self._store[meta.processo_id] = meta

    def get(self, processo_id: UUID) -> ProcessoMeta | None:
        with self._lock:
            return self._store.get(processo_id)

    def drop(self, processo_id: UUID) -> None:
        with self._lock:
            self._store.pop(processo_id, None)

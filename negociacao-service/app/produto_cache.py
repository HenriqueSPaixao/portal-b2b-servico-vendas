from dataclasses import dataclass, field
from threading import RLock
from uuid import UUID


@dataclass
class ProdutoInfo:
    produto_id: UUID
    nome: str | None
    codigo: str | None


@dataclass
class ProdutoCache:
    """Cache in-memory produto_id -> {nome, codigo}.

    Alimentado consumindo `produto_cadastrado` (Eq.1 Produtos / Raíky).
    Mantém o negociacao-service desacoplado: ele nunca chama produtos-service
    via REST nem o mercado-service; tudo vem do Kafka. Reconstrói no restart
    graças a `auto_offset_reset=earliest` no consumer runner.
    """

    _items: dict[UUID, ProdutoInfo] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def set(self, produto_id: UUID, *, nome: str | None, codigo: str | None) -> None:
        with self._lock:
            self._items[produto_id] = ProdutoInfo(
                produto_id=produto_id, nome=nome, codigo=codigo
            )

    def get(self, produto_id: UUID) -> ProdutoInfo | None:
        with self._lock:
            return self._items.get(produto_id)

    def get_nome(self, produto_id: UUID) -> str | None:
        info = self.get(produto_id)
        return info.nome if info else None

    def list_all(self) -> list[dict]:
        """Lista ordenada por nome (UUID-only no fim). Usado pelo autocomplete."""
        with self._lock:
            items = list(self._items.values())
        items.sort(key=lambda i: (i.nome is None, (i.nome or "").lower()))
        return [
            {
                "produto_id": str(i.produto_id),
                "nome": i.nome,
                "codigo": i.codigo,
            }
            for i in items
        ]

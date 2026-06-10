import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.produto_cache import ProdutoCache

logger = logging.getLogger(__name__)


class ProdutoNomeResolver:
    """Preenche nome/código do produto lendo a tabela compartilhada
    `produtos_produto` (Cloud SQL / Postgres) quando o `produto_cadastrado`
    (Kafka) não chegou.

    É SÓ para exibição: o matching continua 100% Kafka (não depende disto). A
    leitura é best-effort — se o banco estiver fora ou o produto não existir,
    cai para `ProdutoCache.ensure` (produto aparece por id, sem nome), e o
    consumo de eventos NUNCA é derrubado por causa do banco.

    O nome só é buscado uma vez por produto: se o cache já tem nome (via este
    lookup ou via `produto_cadastrado`), não consulta de novo.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        schema: str,
        cache: ProdutoCache,
    ) -> None:
        self._session_factory = session_factory
        self._schema = schema
        self._cache = cache

    async def ensure_nome(self, produto_id: UUID) -> None:
        info = self._cache.get(produto_id)
        if info is not None and info.nome:
            return  # já temos o nome — não bate no banco de novo

        # schema vem da config (não de input do usuário) → seguro no f-string;
        # o id vai parametrizado.
        sql = text(
            f"SELECT nome, codigo FROM {self._schema}.produtos_produto "
            "WHERE id = CAST(:pid AS uuid)"
        )
        try:
            async with self._session_factory() as session:
                row = (await session.execute(sql, {"pid": str(produto_id)})).first()
            if row is not None:
                self._cache.set(produto_id, nome=row.nome, codigo=row.codigo)
                return
        except Exception:  # noqa: BLE001 — exibição nunca derruba o consumo
            logger.debug(
                "Lookup de nome no banco falhou para %s", produto_id, exc_info=True
            )
        self._cache.ensure(produto_id)

import logging
from decimal import Decimal
from uuid import UUID

from app.matching.engine import MatchingEngine
from app.matching.snapshot import Demanda, Oferta, Snapshot
from app.produto_cache import ProdutoCache
from app.produto_nome_resolver import ProdutoNomeResolver
from b2b_shared.events import EventEnvelope

logger = logging.getLogger(__name__)


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def _uuid_or_none(value) -> UUID | None:
    return UUID(value) if value else None


class MercadoConsumers:
    def __init__(
        self,
        snapshot: Snapshot,
        engine: MatchingEngine,
        produto_cache: ProdutoCache,
        produto_nome_resolver: ProdutoNomeResolver | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._engine = engine
        self._produto_cache = produto_cache
        self._produto_nome_resolver = produto_nome_resolver

    async def _registrar_produto(self, produto_id) -> None:
        """Garante o produto no cache, com nome quando possível.

        Com resolver (banco): busca nome/código em `produtos_produto` (best-effort).
        Sem resolver: só registra por id (`ensure`). Em ambos, o produto fica
        visível mesmo sem `produto_cadastrado` da Eq.2.
        """
        if self._produto_nome_resolver is not None:
            await self._produto_nome_resolver.ensure_nome(produto_id)
        else:
            self._produto_cache.ensure(produto_id)

    async def handle_produto_cadastrado(self, envelope: EventEnvelope) -> None:
        # Payload do produtos-service (Eq.1 / Raíky) — camelCase. Aceitamos
        # aliases snake_case por compatibilidade defensiva.
        p = envelope.payload
        try:
            produto_id = UUID(p.get("id") or p["produto_id"])
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload produto_cadastrado inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return
        nome = p.get("nome") or p.get("descricao")
        codigo = p.get("codigo")
        self._produto_cache.set(produto_id, nome=nome, codigo=codigo)

    async def handle_fornecimento_criado(self, envelope: EventEnvelope) -> None:
        # Aceita o contrato camelCase publicado pela Eq.3 Fornecimentos
        # (idFornecimento/idProduto/...) e também o snake_case histórico.
        p = envelope.payload
        try:
            oferta = Oferta(
                fornecimento_id=UUID(
                    p.get("idFornecimento") or p.get("id") or p["fornecimento_id"]
                ),
                produto_id=UUID(p.get("idProduto") or p["produto_id"]),
                empresa_fornecedor_id=UUID(
                    p.get("idEmpresaFornecedor") or p["empresa_fornecedor_id"]
                ),
                quantidade=_decimal(
                    p.get("quantidadeDisponivel")
                    or p.get("quantidade_disponivel")
                    or p.get("quantidade")
                ),
                preco_unitario=_decimal(
                    p.get("precoUnitario") or p.get("preco_unitario")
                ),
            )
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload fornecimento_criado inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return
        self._snapshot.upsert_oferta(oferta)
        await self._registrar_produto(oferta.produto_id)
        await self._engine.evaluate(oferta.produto_id)

    async def handle_estoque_atualizado(self, envelope: EventEnvelope) -> None:
        # Aceita o contrato camelCase publicado pela Eq.3 Fornecimentos
        # e o snake_case histórico. quantidadeAnterior é ignorado (auditoria).
        p = envelope.payload
        try:
            produto_id = UUID(p.get("idProduto") or p["produto_id"])
            fornecimento_id = UUID(
                p.get("idFornecimento") or p["fornecimento_id"]
            )
            nova_quantidade = _decimal(
                p.get("quantidadeDisponivel")
                or p.get("quantidade_disponivel")
                or p.get("quantidade")
            )
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload estoque_atualizado inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return
        self._snapshot.update_estoque(
            produto_id=produto_id,
            fornecimento_id=fornecimento_id,
            nova_quantidade=nova_quantidade,
        )
        await self._engine.evaluate(produto_id)

    async def handle_demanda_criada(self, envelope: EventEnvelope) -> None:
        # Aceita snake_case (o que o demanda-service / modulo-compradores publica
        # hoje) e camelCase (idDemanda/idProduto/quantidadeDesejada — formato dos
        # exemplos do guia da Infra), por compatibilidade defensiva.
        p = envelope.payload
        try:
            demanda = Demanda(
                demanda_id=UUID(
                    p.get("id_demanda") or p.get("idDemanda") or p["id"]
                ),
                produto_id=UUID(
                    p.get("id_produto") or p.get("idProduto") or p["produto_id"]
                ),
                # Opcional: a Eq.4 não envia o id do comprador e nosso próprio schema
                # marca como opcional. Não derruba o evento se faltar.
                empresa_comprador_id=_uuid_or_none(
                    p.get("id_empresa_comprador")
                    or p.get("idEmpresaComprador")
                    or p.get("empresa_comprador_id")
                ),
                quantidade=_decimal(
                    p.get("quantidade_desejada")
                    or p.get("quantidadeDesejada")
                    or p.get("quantidade")
                ),
                preco_maximo=(
                    _decimal(p.get("preco_maximo") or p.get("precoMaximo"))
                    if (p.get("preco_maximo") or p.get("precoMaximo"))
                    else None
                ),
                is_recorrente=bool(p.get("is_recorrente", False)),
            )
        except (KeyError, ValueError) as exc:
            logger.error(
                "Payload demanda_criada inválido",
                extra={"event_id": str(envelope.event_id), "err": str(exc)},
            )
            return
        self._snapshot.upsert_demanda(demanda)
        await self._registrar_produto(demanda.produto_id)
        await self._engine.evaluate(demanda.produto_id)

    async def handle_demanda_recorrente_gerada(self, envelope: EventEnvelope) -> None:
        # Tratamos como demanda comum, apenas marcamos is_recorrente para auditoria.
        # O domínio Demanda é que gera o evento por ciclo.
        envelope.payload.setdefault("is_recorrente", True)
        await self.handle_demanda_criada(envelope)

    async def handle_pedido_criado(self, envelope: EventEnvelope) -> None:
        # Eq.4 Demanda (Adrii) publica `pedido_criado` quando "promove" uma
        # demanda (wishlist com estoque validado do lado dela). Para o matching,
        # tratamos exatamente como `demanda_criada` — o payload tem os mesmos
        # campos (id_demanda/id_produto/id_empresa_comprador/quantidade/
        # preco_maximo) e os fallbacks do handle_demanda_criada já cobrem.
        # IGNORAMOS `id_fornecedor_apto` que vem no payload dela: a escolha do
        # fornecedor é o trabalho do nosso matching engine olhando TODAS as
        # ofertas ativas no Kafka, não apenas a pré-validação local que ela faz.
        logger.info(
            "pedido_criado recebido — tratando como gatilho de matching",
            extra={"event_id": str(envelope.event_id)},
        )
        await self.handle_demanda_criada(envelope)

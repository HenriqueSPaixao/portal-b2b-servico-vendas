import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.matching.consumers import MercadoConsumers
from app.matching.engine import MatchingEngine
from app.matching.snapshot import Snapshot
from app.produto_cache import ProdutoCache
from app.routes import router as mercado_router
from b2b_shared.auth.jwt import JWTValidator
from b2b_shared.events import Topic
from b2b_shared.health import build_health_router
from b2b_shared.kafka import KafkaConsumerRunner, KafkaProducer


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    log = logging.getLogger("lifespan")

    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id=f"{settings.kafka_client_id_prefix}-{settings.service_name}-producer",
    )
    await producer.start()

    snapshot = Snapshot()
    produto_cache = ProdutoCache()
    engine = MatchingEngine(
        snapshot=snapshot,
        producer=producer,
        source_name=settings.service_name,
        tolerance_percent=settings.mercado_matching_tolerance_percent,
        default_auction_duration_seconds=settings.mercado_default_auction_duration_seconds,
    )
    consumers = MercadoConsumers(
        snapshot=snapshot, engine=engine, produto_cache=produto_cache
    )

    # Forward-only (Opção A): o mercado casa apenas eventos NOVOS, a partir do fim
    # do log no boot. NÃO reprocessa o histórico — reprocessar re-casaria
    # oferta/demanda antigas e re-publicaria `leilao_iniciado`/`modo_negociacao_
    # definido`, gerando processos duplicados na negociação. group_id NOVO (-live)
    # + auto_offset_reset="latest": sem offset commitado o consumer começa no fim
    # (só eventos novos); a partir daí retoma do último commit (não perde eventos
    # que chegarem com o serviço de pé, e não relê o passado).
    #
    # IMPORTANTE (estado em memória + publica eventos): o mercado-service deve
    # rodar como UMA ÚNICA instância. Com 2 réplicas (deploy redundante nas 2 VMs)
    # cada uma casaria e publicaria o mesmo match → leilões em dobro. Ver mapa de
    # integração / alinhar deploy de instância única com a Infra.
    consumer_runner = KafkaConsumerRunner(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"{settings.service_name}-group-live",
        client_id=f"{settings.kafka_client_id_prefix}-{settings.service_name}-consumer",
        auto_offset_reset="latest",
        handlers={
            Topic.PRODUTO_CADASTRADO.value: consumers.handle_produto_cadastrado,
            Topic.FORNECIMENTO_CRIADO.value: consumers.handle_fornecimento_criado,
            Topic.ESTOQUE_ATUALIZADO.value: consumers.handle_estoque_atualizado,
            Topic.DEMANDA_CRIADA.value: consumers.handle_demanda_criada,
            Topic.DEMANDA_RECORRENTE_GERADA.value: consumers.handle_demanda_recorrente_gerada,
            # Adoção do fluxograma da Eq.4 (Adrii): pedido_criado é o gatilho
            # do leilão pelo lado dela. Aceitamos ambos os eventos como entrada
            # para zero retrabalho de cada lado. Ver consumers.handle_pedido_criado.
            Topic.PEDIDO_CRIADO.value: consumers.handle_pedido_criado,
        },
    )
    await consumer_runner.start()

    app.state.settings = settings
    app.state.producer = producer
    app.state.snapshot = snapshot
    app.state.produto_cache = produto_cache
    app.state.matching_engine = engine
    app.state.service_name = settings.service_name
    app.state.jwt_validator = JWTValidator(
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        clock_skew_seconds=settings.jwt_clock_skew_seconds,
    )

    log.info("mercado-service ready", extra={"port": settings.service_port})
    try:
        yield
    finally:
        await consumer_runner.stop()
        await producer.stop()
        log.info("mercado-service stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Mercado Service",
        version="0.1.0",
        description=(
            "Matching Engine do Portal B2B. Consome oferta/demanda do Kafka, "
            "decide modo (direto/leilão direto/leilão reverso) e publica "
            "modo_negociacao_definido + leilao_iniciado."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_health_router("mercado-service"))
    app.include_router(mercado_router)
    return app


app = create_app()

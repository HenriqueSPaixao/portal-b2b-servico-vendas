import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.consumers import NegociacaoConsumers
from app.metadata_cache import ProcessoMetaCache
from app.routes import router as negociacao_router
from app.scheduler import AuctionScheduler
from b2b_shared.auth.jwt import JWTValidator
from b2b_shared.db import build_engine, build_session_factory
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

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id=f"{settings.kafka_client_id_prefix}-{settings.service_name}-producer",
    )
    await producer.start()

    metadata = ProcessoMetaCache()
    consumers = NegociacaoConsumers(
        session_factory=session_factory,
        producer=producer,
        metadata=metadata,
        source_name=settings.service_name,
    )

    consumer_runner = KafkaConsumerRunner(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"{settings.service_name}-group",
        client_id=f"{settings.kafka_client_id_prefix}-{settings.service_name}-consumer",
        handlers={
            Topic.MODO_NEGOCIACAO_DEFINIDO.value: consumers.handle_modo_negociacao_definido,
            Topic.LEILAO_INICIADO.value: consumers.handle_leilao_iniciado,
        },
    )
    await consumer_runner.start()

    scheduler = AuctionScheduler(
        session_factory=session_factory,
        producer=producer,
        metadata=metadata,
        source_name=settings.service_name,
        poll_interval_seconds=settings.negociacao_auction_poll_interval_seconds,
    )
    await scheduler.start()

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.producer = producer
    app.state.metadata_cache = metadata
    app.state.service_name = settings.service_name
    app.state.jwt_validator = JWTValidator(
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        clock_skew_seconds=settings.jwt_clock_skew_seconds,
    )

    log.info("negociacao-service ready", extra={"port": settings.service_port})
    try:
        yield
    finally:
        await scheduler.stop()
        await consumer_runner.stop()
        await producer.stop()
        await engine.dispose()
        log.info("negociacao-service stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Negociação Service",
        version="0.1.0",
        description=(
            "Microsserviço de Negociação/Leilão do Portal B2B. "
            "Gerencia processo_negociacao e lance, publica negociacao_fechada."
        ),
        lifespan=lifespan,
    )
    app.include_router(build_health_router("negociacao-service"))
    app.include_router(negociacao_router)
    return app


app = create_app()

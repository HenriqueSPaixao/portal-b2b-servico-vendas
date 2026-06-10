import logging
import socket
import uuid
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

    # O mercado-service mantém TODO o estado (snapshot de oferta/demanda +
    # ProdutoCache) em memória — é uma projeção volátil do log de eventos, não
    # um banco. Por isso cada instância precisa reler o log INTEIRO a cada boot e
    # enxergar TODAS as partições. Um group_id estável quebra as duas coisas: no
    # restart o consumer volta do offset commitado (sem replay → estado vazio) e,
    # com réplicas, o group divide as partições entre elas (cada uma com um pedaço
    # do estado, e o gateway sorteando qual responde). Um group_id único por
    # processo resolve ambos: sem offset commitado, auto_offset_reset=earliest
    # reprocessa desde o início; e cada instância fica sozinha no seu group →
    # recebe todas as partições. Prefixo mantido p/ a infra reconhecer
    # (mercado-service-group-*). Contraste: negociacao-service persiste em
    # Postgres, então mantém group estável (não deve reprocessar tudo no boot).
    consumer_group_id = (
        f"{settings.service_name}-group-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    )
    consumer_runner = KafkaConsumerRunner(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=consumer_group_id,
        client_id=f"{settings.kafka_client_id_prefix}-{settings.service_name}-consumer",
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

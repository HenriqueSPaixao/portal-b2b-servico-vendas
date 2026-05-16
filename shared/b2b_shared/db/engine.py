from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency que entrega uma sessão e fecha ao final.

    A factory deve estar pendurada em `app.state.session_factory` pelo lifespan.
    """
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if factory is None:
        raise RuntimeError(
            "session_factory não está em app.state — configure no lifespan"
        )
    async with factory() as session:
        yield session

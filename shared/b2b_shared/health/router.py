from fastapi import APIRouter


def build_health_router(service_name: str) -> APIRouter:
    """Cria um router /health público (sem autenticação).

    Padrão exigido pelo guia de integração da infra: GET /health responde 200
    com um JSON pequeno. Também expõe /saude para compatibilidade com o que o
    MS Produtos publicou.
    """
    router = APIRouter()

    payload = {"status": "ok", "service": service_name}

    @router.get("/health", tags=["health"])
    async def health() -> dict:
        return payload

    @router.get("/saude", tags=["health"], include_in_schema=False)
    async def saude() -> dict:
        return payload

    return router

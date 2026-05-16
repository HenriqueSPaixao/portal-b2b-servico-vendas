# Build context é a raiz do monorepo (ver docker-compose.yml)
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências de sistema mínimas (asyncpg precisa de libpq em build, mas a wheel
# manylinux já cobre).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copia o pacote compartilhado e instala em modo editável.
COPY shared /app/shared
RUN pip install /app/shared

# Copia o serviço e instala.
COPY mercado-service /app/mercado-service
RUN pip install /app/mercado-service

WORKDIR /app/mercado-service

EXPOSE 5005

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5005", "--proxy-headers"]

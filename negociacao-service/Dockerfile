# Build context é a raiz do monorepo (ver docker-compose.yml)
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared /app/shared
RUN pip install /app/shared

COPY negociacao-service /app/negociacao-service
RUN pip install /app/negociacao-service

WORKDIR /app/negociacao-service

EXPOSE 5006

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5006", "--proxy-headers"]

# Portal B2B — Domínio Vendas (Equipe 9)

Monorepo dos microsserviços do domínio **Vendas** do Portal B2B Distribuído:

- **mercado-service** (porta `5005`) — Matching Engine: decide o modo de negociação (direto, leilão direto, leilão reverso) a partir do cruzamento entre oferta e demanda recebidos via Kafka.
- **negociacao-service** (porta `5006`) — Auction/Sale Executor: gerencia o ciclo de vida de `processo_negociacao` e `lance`, encerra a negociação e publica `negociacao_fechada` com payload completo.

> **Importante:** o domínio Vendas **NÃO cria pedido**. O encerramento publica `negociacao_fechada` self-contained; quem cria `pedido` é o `demanda-service` (Eq. 4).

## Estrutura

```
.
├── docker-compose.yml          # sobe os dois serviços na rede portal-b2b-network
├── .env.example                # variáveis compartilhadas
├── shared/                     # pacote Python comum (auth, kafka, db, events)
├── mercado-service/
└── negociacao-service/
```

## Dev local (Docker — recomendado)

Pré-requisitos: Docker + Docker Compose.

```bash
cp .env.example .env
# editar .env com a senha do Postgres e o JWT_SECRET correto
docker network create portal-b2b-network 2>/dev/null || true
docker compose up --build
```

### Dev local sem infra remota (sem VPN, sem senha do BD)

Quando o cluster Kafka oficial (IPs `10.128.x.x`) e o Cloud SQL não estiverem
acessíveis, sobe-se uma stack completa em containers: Postgres + Redpanda +
PgAdmin, com o DDL oficial aplicado automaticamente a partir de
`portal-b2b-database/scripts/`.

```bash
# clonar o repo de BD na raiz (se ainda não estiver)
git clone https://github.com/matheussouza17/portal-b2b-database

# subir
docker network create portal-b2b-network 2>/dev/null || true
cp .env.local .env   # se .env não existe
docker compose up -d
```

Endpoints locais:
- mercado: http://localhost:5005/health · /docs
- negociacao: http://localhost:5006/health · /docs
- PgAdmin: http://localhost:5050 (admin@local.dev / admin)
- Postgres: localhost:5432 (svc_portal_b2b / senha_portal_b2b)
- Redpanda Kafka: localhost:19092 (acesso do host) / redpanda:9092 (entre containers)

Quando a infra real voltar, basta editar o `.env` apontando para Cloud SQL e
cluster Kafka oficiais e remover/renomear `docker-compose.override.yml`.

## Dev local (sem Docker)

Cada serviço se instala como um pacote Python que depende de `b2b-shared`.
Recomendado um virtualenv por serviço (eles compartilham o nome de pacote `app`
internamente, então não dá pra instalar os dois no mesmo env).

```bash
# negociacao-service
python -m venv .venv-negociacao
. .venv-negociacao/Scripts/activate    # Windows PowerShell: .venv-negociacao\Scripts\Activate.ps1
pip install -e ./shared
pip install -e ./negociacao-service
cp negociacao-service/.env.example negociacao-service/.env  # ajuste senha/JWT
cd negociacao-service && uvicorn app.main:app --port 5006 --reload
```

```bash
# mercado-service (em outro shell)
python -m venv .venv-mercado
. .venv-mercado/Scripts/activate
pip install -e ./shared
pip install -e ./mercado-service
cp mercado-service/.env.example mercado-service/.env
cd mercado-service && uvicorn app.main:app --port 5005 --reload
```

Health checks:

- `http://localhost:5005/health` (mercado-service)
- `http://localhost:5006/health` (negociacao-service)

Swagger:

- `http://localhost:5005/docs`
- `http://localhost:5006/docs`

## Integração

- **Banco:** Cloud SQL compartilhado `136.114.235.212:5432/portal_b2b`, schema `portal_b2b`. DDL é de responsabilidade da Eq. de BD ([repo](https://github.com/matheussouza17/portal-b2b-database)).
- **Kafka:** cluster oficial `10.128.0.2:9092,10.128.0.3:9092,10.128.0.4:9092`.
- **JWT:** issuer `portal-autenticacao`, audience `portal-b2b`, HMAC-SHA256. Secret compartilhado entre todos os MSs.
- **Gateway:** `/api/mercado/*` → mercado-service:5005; `/api/negociacao/*` → negociacao-service:5006 (coordenar com infra).

## Tópicos Kafka

| Tópico | Direção | Quem |
|---|---|---|
| `fornecimento_criado` | consome | mercado-service |
| `estoque_atualizado` | consome | mercado-service |
| `demanda_criada` | consome | mercado-service |
| `demanda_recorrente_gerada` | consome | mercado-service |
| `modo_negociacao_definido` | publica | mercado-service |
| `leilao_iniciado` | publica | mercado-service |
| `modo_negociacao_definido` | consome | negociacao-service |
| `leilao_iniciado` | consome | negociacao-service |
| `lance_realizado` | publica | negociacao-service |
| `negociacao_fechada` | publica | negociacao-service |

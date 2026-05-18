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

## Smoke test

Validação end-to-end dos 3 modos de negociação (`direto`, `leilao_direto`, `leilao_reverso`)
rodando contra a stack local. Pré-requisito: `docker compose up -d` rodando.

**Modo simples (recomendado):**

```bash
# Git Bash / Linux / macOS / WSL
./scripts/run_smoke.sh

# PowerShell / CMD do Windows
scripts\run_smoke.bat
```

Os wrappers leem `JWT_SECRET` do `.env` automaticamente.

**Modo manual** (se quiser ver a chamada por baixo):

```bash
docker cp scripts/smoke_test.py negociacao-service:/tmp/smoke.py
docker exec -e JWT_SECRET=<segredo_do_env> negociacao-service python /tmp/smoke.py
# No Git Bash, prefixar com MSYS_NO_PATHCONV=1 nos dois comandos acima.
```

O script:
1. Insere registros mínimos em `produtos_transporte`, `produtos_categoria`, `produtos_unidade_medida`, `produtos_produto`, `empresa` para satisfazer FKs (códigos com sufixo de timestamp — cada run usa produtos novos).
2. Publica `fornecimento_criado` + `demanda_criada` nas combinações que exercitam cada modo.
3. Para leilões, faz POST autenticado em `/api/negociacao/processos/{id}/lances` com 2 lances distintos.
4. Aguarda fechamento (auto-fecha em modo direto; scheduler fecha leilões após `data_fim`).
5. Imprime `[OK]`/`[FAIL]` por cenário e retorna exit code 0 se tudo passar.

Saída esperada (resumo):

```
[OK ] A_direto:           modo=direto         status=FECHADA
[OK ] B_leilao_direto:    modo=leilao_direto  status=FECHADA
[OK ] C_leilao_reverso:   modo=leilao_reverso status=FECHADA
```

## Integration Guide (para outras equipes)

**Domínio:** Mercado + Negociação. **Equipe:** Eq.9 Vendas. **Contato:** Henrique (`henriquecorp253@gmail.com` / grupo WhatsApp SD).

**Boundary:** este domínio **não cria pedido**. O ciclo encerra publicando `negociacao_fechada` self-contained; a Eq.4 Demanda consome e cria `pedido_criado`.

### Eventos que consumimos de vocês

| Tópico | Origem esperada | Campos obrigatórios no payload |
|---|---|---|
| `fornecimento_criado` | Eq.3 Fornecimentos (Eliel) | `id` (alias `fornecimento_id`), `produto_id`, `empresa_fornecedor_id`, `quantidade_disponivel` (alias `quantidade`), `preco_unitario` |
| `estoque_atualizado` | Eq.3 Fornecimentos | `produto_id`, `fornecimento_id`, `quantidade_disponivel` (alias `quantidade`) |
| `demanda_criada` | Eq.4 Demanda (Adrielly) | `id_demanda` (alias `id`), `id_produto` (alias `produto_id`), `id_empresa_comprador` (alias `empresa_comprador_id`), `quantidade_desejada` (alias `quantidade`), opcional: `preco_maximo`, `is_recorrente` |
| `demanda_recorrente_gerada` | Eq.4 Demanda | mesmo payload de `demanda_criada` (`is_recorrente` é forçado a `true`) |

Aceitamos os dois esquemas de nomenclatura (versão "com prefixo `id_`" do DDL de Demanda e versão "snake_case curto") — não quebra para nenhum dos lados.

### Eventos que publicamos

**`modo_negociacao_definido`** (mercado-service) — todo matching produz este evento, mesmo em modo direto:

```json
{
  "eventId": "...", "eventType": "modo_negociacao_definido", "eventVersion": "1.0",
  "timestamp": "...", "source": "mercado-service", "correlationId": "...",
  "payload": {
    "processo_id": "uuid", "produto_id": "uuid",
    "modo": "direto | leilao_direto | leilao_reverso",
    "data_inicio": "ISO8601", "data_fim": "ISO8601",
    "quantidade": "100", "valor_reserva": "10.00",
    "fornecimento_id": "uuid|null", "demanda_id": "uuid|null",
    "empresa_comprador_principal": "uuid|null",
    "empresa_fornecedor_principal": "uuid|null",
    "empresas_compradoras_habilitadas": ["uuid", ...],
    "empresas_fornecedoras_habilitadas": ["uuid", ...]
  }
}
```

**`leilao_iniciado`** (mercado-service) — só em modos de leilão (não em direto). Mesmo `correlationId` do `modo_negociacao_definido`. Payload contém `processo_id`, `produto_id`, `modo`, `data_inicio`, `data_fim`.

**`lance_realizado`** (negociacao-service) — para cada POST `/lances`. Payload: `lance_id`, `processo_id`, `empresa_id`, `valor_unitario`, `quantidade`, `data_lance`.

**`negociacao_fechada`** (negociacao-service) — **self-contained, é o gatilho oficial para a Eq.4 Demanda criar o pedido:**

```json
{
  "eventType": "negociacao_fechada",
  "source": "negociacao-service",
  "payload": {
    "processo_id": "uuid", "produto_id": "uuid", "modo": "direto|leilao_direto|leilao_reverso",
    "empresa_comprador_id": "uuid", "empresa_fornecedor_id": "uuid",
    "fornecimento_id": "uuid|null", "demanda_id": "uuid|null",
    "quantidade": "100.0000", "valor_unitario_final": "12.0000", "valor_total": "1200.0000",
    "vencedor_lance_id": "uuid|null",
    "motivo_fechamento": "venda_direta_automatica | expirado | manual_admin",
    "data_fechamento": "ISO8601"
  }
}
```

### API REST (todas exigem `Authorization: Bearer <jwt>`)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | público — probe de infra |
| `GET` | `/api/mercado/snapshot/{produto_id}` | debug do snapshot in-memory (oferta vs demanda) |
| `GET` | `/api/mercado/processos` | debug dos processos disparados pelo matching |
| `GET` | `/api/negociacao/processos?status=&modo=&produto_id=` | listar processos |
| `GET` | `/api/negociacao/processos/{id}` | detalhe + lista de lances |
| `POST` | `/api/negociacao/processos/{id}/lances` | registrar lance (`empresa_id` vem do JWT) |
| `POST` | `/api/negociacao/processos/{id}/fechar` | fechamento manual (admin) |

JWT validado localmente — issuer `portal-autenticacao`, audience `portal-b2b`, HS256, mesma `JWT_SECRET` do MS Usuários.

## Subir contra a infra real (Cloud SQL + cluster Kafka)

Quando a VPN e a infra oficial do Sérgio estiverem acessíveis:

1. Garanta acesso de rede a `136.114.235.212:5432` (Cloud SQL) e `10.128.0.2-4:9092` (cluster Kafka).
2. Crie o `.env` real:

   ```bash
   cp .env.example .env
   # editar:
   #   DATABASE_URL=postgresql+asyncpg://svc_portal_b2b:<senha_real>@136.114.235.212:5432/portal_b2b
   #   KAFKA_BOOTSTRAP_SERVERS=10.128.0.2:9092,10.128.0.3:9092,10.128.0.4:9092
   #   JWT_SECRET=<segredo_alinhado_com_guilherme>
   ```

3. Senha do `svc_portal_b2b`: pedir Sérgio. `JWT_SECRET`: alinhar com Guilherme (mesmo do MS Usuários).
4. Suba apenas os serviços (sem o override que monta Postgres/Redpanda locais):

   ```bash
   docker network create portal-b2b-network 2>/dev/null || true
   docker compose -f docker-compose.yml up -d --build
   ```

5. Validar localmente:

   ```bash
   curl http://localhost:5005/health
   curl http://localhost:5006/health
   ```

6. Pedir ao Sérgio para abrir no Nginx do gateway oficial:
   - `/api/mercado/* → mercado-service:5005`
   - `/api/negociacao/* → negociacao-service:5006`

7. Smoke test contra o gateway oficial (após o passo 6):

   ```bash
   curl http://34.8.17.245/api/mercado/health
   curl http://34.8.17.245/api/negociacao/health
   ```

Para voltar ao dev local, basta remover/renomear `docker-compose.override.yml.disabled` → `docker-compose.override.yml` e apontar `.env` para `localhost`/credenciais locais.

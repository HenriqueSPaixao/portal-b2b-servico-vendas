# Rodar tudo do zero (stack local) — Mercado + Negociação

Sobe a **stack inteira em Docker** sem VPN nem senha de produção: Postgres + Redpanda
(Kafka) + os 2 microsserviços + os 2 fronts. Tudo em `localhost`.

Containers que sobem: `vendas-postgres`, `vendas-redpanda`, `vendas-pgadmin`,
`mercado-service`, `negociacao-service`, `mercado-web`, `negociacao-web`.

> Comandos em **PowerShell** (Windows). Onde houver script `.sh`, há um `.bat` equivalente.

---

## 0. Pré-requisitos

- **Docker Desktop** aberto e rodando.
- **Git**.
- **PowerShell** (os scripts de demo/teste são `.ps1`). Se o Windows bloquear a execução,
  rode com `powershell -ExecutionPolicy Bypass -File .\scripts\<script>.ps1`.
- `curl.exe` (já vem no Windows 10+) — usado no teste de SSE.

---

## 1. Clonar os repositórios

```powershell
git clone <url-deste-repo> Sistema_b2b_servico-vendas
cd Sistema_b2b_servico-vendas

# O DDL oficial do banco vem de OUTRO repo, clonado DENTRO da raiz deste:
git clone https://github.com/matheussouza17/portal-b2b-database
```

Por quê: o `docker-compose.local.yml` monta `./portal-b2b-database/scripts` como init do
Postgres. É ele que cria o schema `portal_b2b` e as tabelas **no primeiro boot** (volume vazio).

---

## 2. Criar os arquivos de ambiente (`.env.local` e `.env`)

São **gitignored** (têm credenciais) — não vêm no clone. Crie `.env.local` na raiz com os
valores **locais** abaixo e depois copie para `.env` (o `docker-compose.yml` lê `.env`; o
`docker-compose.local.yml` lê `.env.local`; manter os dois idênticos garante consistência):

`.env.local`:
```dotenv
DATABASE_URL=postgresql+asyncpg://svc_portal_b2b:senha_portal_b2b@postgres:5432/portal_b2b
DB_SCHEMA=portal_b2b

KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
KAFKA_CLIENT_ID_PREFIX=vendas-local

JWT_SECRET=DAJNjnbdaibndiuabdwqbiib24141F15n5j1n
JWT_ISSUER=portal-autenticacao
JWT_AUDIENCE=portal-b2b
JWT_CLOCK_SKEW_SECONDS=60

MERCADO_MATCHING_TOLERANCE_PERCENT=5
MERCADO_DEFAULT_AUCTION_DURATION_SECONDS=300
NEGOCIACAO_AUCTION_POLL_INTERVAL_SECONDS=2

CORS_ALLOW_ORIGINS=http://localhost:8085,http://localhost:8086
LOG_LEVEL=INFO
```

```powershell
Copy-Item .env.local .env -Force
```

> Pontos importantes do local: `DATABASE_URL` usa o host **`postgres`** (nome do container),
> não `localhost`; `KAFKA_BOOTSTRAP_SERVERS=redpanda:9092` (entre containers). O `JWT_SECRET`
> precisa ser o **mesmo** que minta os tokens — por isso os scripts mintam dentro do container.

---

## 3. Subir o stack

```powershell
docker network create portal-b2b-network    # uma vez; ignore "already exists"
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Primeiro boot leva ~30–60s (build das imagens + DDL + os services esperam Postgres/Redpanda
ficarem `healthy`). Conferir:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml ps
Invoke-RestMethod http://localhost:5005/health    # mercado
Invoke-RestMethod http://localhost:5006/health    # negociacao
```

---

## 4. Links (com a stack de pé)

| O quê | URL | Credenciais |
|---|---|---|
| mercado-service (health/docs) | http://localhost:5005/health · http://localhost:5005/docs | — |
| negociacao-service (health/docs) | http://localhost:5006/health · http://localhost:5006/docs | — |
| **mercado-web** (painel do fornecedor / gate) | http://localhost:8085 | precisa `?jwt=` (§5) |
| **negociacao-web** (lances / chat) | http://localhost:8086 | precisa `?jwt=` (§5) |
| PgAdmin | http://localhost:5050 | `admin@local.dev` / `admin` |
| Postgres (admin) | localhost:5432 → db `portal_b2b` | `postgres` / `postgres_admin_local` |
| Postgres (role da app) | localhost:5432 | `svc_portal_b2b` / `senha_portal_b2b` |
| Redpanda/Kafka | host: `localhost:19092` · entre containers: `redpanda:9092` | — |

> As UIs abrem **em branco** sem token — é esperado. Entre com um JWT (§5).

---

## 5. Entrar nas UIs com token (JWT)

O front lê o token de `?jwt=…`, move pro `sessionStorage` e injeta `Authorization: Bearer …`
em todas as chamadas. Você **não precisa copiar/colar token** — um script minta e já abre o
navegador na URL com o `?jwt=`:

```powershell
# negociacao-web (papel COMPRADOR) — abre o navegador já logado:
.\scripts\abrir_local.ps1

# mercado-web (painel do fornecedor / gate):
.\scripts\abrir_local.ps1 -Front mercado

# escolher papel / empresa, ou só imprimir a URL (sem abrir o navegador):
.\scripts\abrir_local.ps1 -Role FORNECEDOR
.\scripts\abrir_local.ps1 -EmpresaId <uuid>
.\scripts\abrir_local.ps1 -NoBrowser
```

<details>
<summary>Manual (se quiser o token na mão)</summary>

```powershell
docker cp scripts/mint_jwt.py negociacao-service:/tmp/mint_jwt.py
docker exec negociacao-service python /tmp/mint_jwt.py                      # FORNECEDOR, empresa aleatória, 24h
docker exec negociacao-service python /tmp/mint_jwt.py <empresa_id> COMPRADOR
```
Cole na URL: `http://localhost:8085/?jwt=<token>` (mercado) · `http://localhost:8086/?jwt=<token>` (negociacao).
Sem container: `python scripts/gen_jwt.py` (precisa `python-jose` num venv local) imprime token + URLs.
</details>

> Para ver uma **proposta pendente** no painel do fornecedor, o `empresa_id` do token tem que
> ser o do fornecedor dono da oferta. Os scripts de demo (§6) já cuidam disso automaticamente.

---

## 6. Demos prontas (1 comando, abre o navegador já logado)

Rode da **raiz do projeto**, com a stack de pé:

```powershell
# Gate do fornecedor: cria uma proposta de leilão direto PENDENTE e abre o mercado-web
# logado como o fornecedor, pra VOCÊ clicar "Abrir leilão" ou "Recusar".
.\scripts\demo_mercado.ps1

# Fluxo completo: cria proposta -> fornecedor ABRE (gate=sim) -> 2 compradores dão lance
# -> abre o chat de lances. Variações: -NoBids (só abre, p/ bidar ao vivo) | -NoBrowser.
.\scripts\demo_gate.ps1
```

---

## 7. Testes locais

```powershell
# Teste INTEGRAL da negociação (resumo PASS/FAIL). Cobre:
#   1) smoke A–E: 3 modos (direto/leilão direto/reverso) + gate + recusa
#   2) validação de lance: piso/teto, supera o melhor, qtd, papel  -> 422/403/201
#   3) "leilões abertos para mim" (habilitação por papel)
#   4) SSE: content-type text/event-stream + header X-Accel-Buffering
.\scripts\test_negociacao.ps1

# Só o smoke end-to-end (3 modos):
.\scripts\run_smoke.bat          # PowerShell/CMD   (.sh no Git Bash/WSL)

# Ver eventos Kafka passando ao vivo (prova de integração):
.\scripts\event_tap.bat                              # todos
.\scripts\event_tap.bat negociacao_fechada lance_realizado   # filtra

# Publicar um evento manual no Kafka:
.\scripts\event_publish.bat <tipo_de_evento> ...
```

---

## 8. Resetar / parar

```powershell
# parar mantendo os dados:
docker compose -f docker-compose.yml -f docker-compose.local.yml down

# ZERAR tudo (apaga o volume do Postgres -> o DDL roda de novo no próximo up):
docker compose -f docker-compose.yml -f docker-compose.local.yml down -v

# rebuild após mudar código:
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build

# logs de um serviço:
docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f negociacao-service
```

---

## 9. Troubleshooting

| Sintoma | Causa provável / correção |
|---|---|
| UI em branco | Faltou `?jwt=` (token). Veja §5. |
| `401` nas chamadas | Token expirou (24h) **ou** `JWT_SECRET` diverge entre `.env`/`.env.local` e o que mintou o token. Gere outro pelo container. |
| `network portal-b2b-network not found` | Rode `docker network create portal-b2b-network`. |
| Service `unhealthy`/reiniciando | Postgres/Redpanda ainda subindo (os services esperam `healthy`). Veja `logs -f`. |
| Tabelas faltando / erro de schema | O volume já existia de um boot anterior **sem** o DDL. O init só roda em volume vazio: `down -v` e suba de novo. |
| `connection refused` ao Postgres | `DATABASE_URL` tem que usar host `postgres` (nome do container), não `localhost`. |
| Porta ocupada (5432/5005/8085…) | Outro processo usa a porta. Pare-o ou ajuste a porta no compose. |
| `.ps1` não executa | Execution policy. Use `powershell -ExecutionPolicy Bypass -File .\scripts\<script>.ps1`. |

> **Voltar para a infra real:** edite o `.env` apontando para o Cloud SQL e o cluster Kafka
> oficiais e suba **só** o `docker-compose.yml` (sem o `-f docker-compose.local.yml`).

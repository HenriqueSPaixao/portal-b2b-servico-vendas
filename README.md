# Portal B2B — Domínio Vendas (Equipe 9)

Monorepo dos microsserviços do domínio **Vendas** do Portal B2B Distribuído:

- **mercado-service** (porta `5005`) — Matching Engine **voltado ao fornecedor**: cruza oferta e demanda recebidos via Kafka e decide o modo (direto, leilão direto, leilão reverso). No **leilão direto** o fornecedor é dono da oferta e **confirma na UI se quer abrir o leilão (sim/não)** antes de qualquer evento sair — "o fornecedor manda no mercado". Direto e leilão reverso seguem automáticos. Ver [`docs/ARQUITETURA-confirmacao-fornecedor.md`](docs/ARQUITETURA-confirmacao-fornecedor.md).
- **negociacao-service** (porta `5006`) — Auction/Sale Executor: gerencia o ciclo de vida de `processo_negociacao` e `lance` (interface de lances estilo "chat" fornecedor↔comprador na `negociacao-web`), encerra a negociação e publica `negociacao_fechada` com payload completo.

> **Importante:** o domínio Vendas **NÃO cria pedido**. O encerramento publica `negociacao_fechada` self-contained; quem cria `pedido` é o `demanda-service` (Eq. 4).
>
> **Confirmação do fornecedor:** o *matching* propõe automaticamente, mas **abrir um leilão direto** depende do "sim" do fornecedor na mercado-web. Um "não" é resolvido **100% dentro do mercado-service** (re-match interno, nada é publicado) — não gera dependência nem muda payload para nenhuma equipe.

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
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

Endpoints locais:
- mercado: http://localhost:5005/health · /docs
- negociacao: http://localhost:5006/health · /docs
- **mercado-web** (UI): http://localhost:8085 — ver seção "Fronts" abaixo
- **negociacao-web** (UI): http://localhost:8086 — ver seção "Fronts" abaixo
- PgAdmin: http://localhost:5050 (admin@local.dev / admin)
- Postgres: localhost:5432 (svc_portal_b2b / senha_portal_b2b)
- Redpanda Kafka: localhost:19092 (acesso do host) / redpanda:9092 (entre containers)

Quando a infra real voltar, basta editar o `.env` apontando para Cloud SQL e
cluster Kafka oficiais e subir só `docker-compose.yml` (sem o `docker-compose.local.yml`).

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

## Fronts (UI embarcada)

Cada microsserviço tem seu front próprio, alinhado ao padrão visual do Portal B2B (React + Tailwind, dark mode obrigatório, verde `#4cc465`):

- **mercado-web** ([mercado-web/](mercado-web/)) — porta `8085`. Página única com:
  - Tabela "Processos disparados pelo matching" (`GET /processos`, refresh 5s).
  - Painel "Snapshot por produto" (`GET /snapshot/{produto_id}`).
- **negociacao-web** ([negociacao-web/](negociacao-web/)) — porta `8086`. Duas views:
  - `/` lista de processos com filtros por status/modo/produto (`GET /processos`).
  - `/processos/:id` detalhe + lances + formulário de novo lance (`POST .../lances`) + fechamento manual (`POST .../fechar`).

> Os caminhos acima são as **rotas internas** dos services. Externamente, o gateway expõe como `http://34.8.17.245/api/mercado/...` e `http://34.8.17.245/api/negociacoes/...` (note: negociação é **plural** na rota externa) e remove o prefixo antes de encaminhar.

**Handshake de JWT** (padrão de grupo): o portal pai abre `http://localhost:8085/?jwt=…` ou `http://localhost:8086/?jwt=…`; o front move o token para `sessionStorage["portal_b2b_jwt"]`, apaga `?jwt=…` da barra via `history.replaceState`, e o interceptor do axios injeta `Authorization: Bearer …` em todas as chamadas. `401` limpa o storage.

**Para abrir manualmente em dev** (sem o portal pai injetar o token):

```bash
# (a) Se você já tem .venv-negociacao ou venv com python-jose:
python scripts/gen_jwt.py

# (b) Se não tem nada local, use o container (negociacao-service já tem python-jose):
docker cp scripts/gen_jwt.py negociacao-service:/tmp/gen_jwt.py
docker exec negociacao-service python /tmp/gen_jwt.py
```

Imprime o JWT + as duas URLs prontas pra colar no navegador. Lê `JWT_SECRET`/`JWT_ISSUER`/`JWT_AUDIENCE` de env vars ou do `.env` da raiz; HS256 válido por 8h (configurável via `--ttl-hours`, `--role`, `--empresa-id`).

**CORS:** os services já vêm com `CORSMiddleware` lendo `CORS_ALLOW_ORIGINS` do `.env` (default `http://localhost:8085,http://localhost:8086`).

**Subir tudo junto:**

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
# após ~30s os fronts estão disponíveis em :8085 e :8086
```

## Integração

- **Banco:** Cloud SQL compartilhado `136.114.235.212:5432/portal_b2b`, schema `portal_b2b`. DDL é de responsabilidade da Eq. de BD ([repo](https://github.com/matheussouza17/portal-b2b-database)).
- **Kafka:** cluster oficial `10.128.0.2:9092,10.128.0.3:9092,10.128.0.4:9092`.
- **JWT:** issuer `portal-autenticacao`, audience `portal-b2b`, HMAC-SHA256. Secret compartilhado entre todos os MSs.
- **Gateway:** `/api/mercado/*` → mercado-service:5005; `/api/negociacoes/*` → negociacao-service:5006 (note plural em negociações — padrão da infra). O gateway remove o prefixo antes de proxy, então as rotas internas dos services **não** começam com `/api/...`.

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
3. Para leilões, faz POST autenticado em `/processos/{id}/lances` (rota interna do negociacao-service) com 2 lances distintos.
4. Aguarda fechamento (auto-fecha em modo direto; scheduler fecha leilões após `data_fim`).
5. Imprime `[OK]`/`[FAIL]` por cenário e retorna exit code 0 se tudo passar.

Saída esperada (resumo):

```
[OK ] A_direto:           modo=direto         status=FECHADA
[OK ] B_leilao_direto:    modo=leilao_direto  status=FECHADA
[OK ] C_leilao_reverso:   modo=leilao_reverso status=FECHADA
```

## Integration Guide (para outras equipes)

**Domínio:** Mercado + Negociação. **Contato:** Henrique (`henriquecorp253@gmail.com` / grupo WhatsApp SD).

**Boundary:** este domínio **não cria pedido**. O ciclo encerra publicando `negociacao_fechada` self-contained; a Eq.4 Demanda consome e cria `pedido_criado`.

### Atalhos para integrar rápido

| Quero… | Use |
|---|---|
| Contratos REST navegáveis | [`docs/contracts/mercado.openapi.json`](docs/contracts/mercado.openapi.json), [`docs/contracts/negociacao.openapi.json`](docs/contracts/negociacao.openapi.json) — abra em [editor.swagger.io](https://editor.swagger.io) ou importe em qualquer gerador de cliente (`openapi-typescript`, `orval`). |
| Schemas dos eventos Kafka | [`docs/contracts/events/`](docs/contracts/events/) — 8 schemas (4 consumidos + 4 publicados) + [`envelope.schema.json`](docs/contracts/events/envelope.schema.json). JSON Schema 2020-12. |
| Testar REST clicando | [`docs/integration/postman_collection.json`](docs/integration/postman_collection.json) — importe no Postman/Insomnia, defina `{{jwt}}`. |
| Ver eventos chegando em tempo real | `scripts/event_tap.bat` (Windows) ou `scripts/event_tap.sh` (Bash/WSL). Filtra por tópico: `scripts/event_tap.bat negociacao_fechada`. |
| Publicar um evento de teste no Kafka | `scripts/event_publish.sh demanda_criada docs/integration/fixtures/demanda_criada.example.json` — fixtures prontas em [`docs/integration/fixtures/`](docs/integration/fixtures/). |
| Saber o que está pronto vs pendente | [`docs/STATUS_INFRA.md`](docs/STATUS_INFRA.md) |

### Diagrama de sequência (fluxo completo)

```
Eq.3 Fornecimentos      mercado-service        negociacao-service       Eq.4 Demanda
       (Eliel)         (matching engine)       (auction executor)        (Adrielly)
         │                    │                        │                       │
         │ fornecimento_criado│                        │                       │
         ├───────────────────►│                        │                       │
         │ estoque_atualizado │                        │                       │
         ├───────────────────►│                        │                       │
         │                    │                        │   demanda_criada      │
         │                    │◄───────────────────────┼───────────────────────┤
         │                    │                        │                       │
         │            (matching propõe o match)        │                       │
         │   ┌── leilão direto: fornecedor confirma na mercado-web (sim/não)    │
         │   │     • "não" → re-match interno; NADA é publicado (fica no mercado)│
         │   └──── "sim" / direto / reverso → segue abaixo ──┐                  │
         │                    │ modo_negociacao_definido     │                  │
         │                    ├───────────────────────►│                       │
         │                    │ leilao_iniciado (se leilão)                    │
         │                    ├───────────────────────►│                       │
         │                    │                        │                       │
         │                    │              (compradores/fornecedores         │
         │                    │               fazem POST /lances)              │
         │                    │                        │ lance_realizado       │
         │                    │                        ├──────────────────────►│
         │                    │                        │                       │
         │                    │              (scheduler fecha após data_fim    │
         │                    │               OU modo direto fecha imediato)   │
         │                    │                        │ negociacao_fechada    │
         │                    │                        ├──────────────────────►│
         │                    │                        │            (Eq.4 cria │
         │                    │                        │             pedido_criado)
```

### Quem chamar quando algo der errado

| Sintoma | Responsável | Como contatar |
|---|---|---|
| Evento `fornecimento_criado` / `estoque_atualizado` não chega ou payload errado | Eq.3 — Eliel | WhatsApp SD |
| Evento `demanda_criada` não chega ou `negociacao_fechada` não vira `pedido_criado` | Eq.4 — Adrielly | WhatsApp SD |
| JWT rejeitado, claim faltando, `JWT_SECRET` divergente | MS Usuários — Guilherme | WhatsApp SD |
| Cloud SQL inacessível, cluster Kafka fora, gateway Nginx sem rota | Infra — Sérgio | WhatsApp SD |
| Mercado/Negociação retornando erro inesperado | Vendas — Henrique | `henriquecorp253@gmail.com` |

### Eventos que consumimos de vocês

| Tópico | Origem esperada | Campos obrigatórios no payload |
|---|---|---|
| `fornecimento_criado` | Eq.3 Fornecimentos (Eliel) — [theudevs/fornecimentos-service](https://github.com/theudevs/fornecimentos-service) | **Formato canônico (camelCase, contrato oficial da Eq.3):** `idFornecimento`, `idProduto`, `idEmpresaFornecedor`, `precoUnitario`, `quantidadeDisponivel`. Aliases snake_case aceitos por compatibilidade: `id`/`fornecimento_id`, `produto_id`, `empresa_fornecedor_id`, `preco_unitario`, `quantidade_disponivel`/`quantidade`. Campo `idEnderecoOrigem` é publicado pela Eq.3 mas ignorado pelo matching (Demanda/Logística podem buscar via REST). |
| `estoque_atualizado` | Eq.3 Fornecimentos | **Formato canônico (camelCase):** `idFornecimento`, `idProduto`, `quantidadeDisponivel`. Aliases snake_case aceitos: `fornecimento_id`, `produto_id`, `quantidade_disponivel`/`quantidade`. Campos `idEmpresaFornecedor` e `quantidadeAnterior` são ignorados (redundante / auditoria). |
| `demanda_criada` | Eq.4 Demanda (Adrielly) | `id_demanda` (alias `id`), `id_produto` (alias `produto_id`), `id_empresa_comprador` (alias `empresa_comprador_id`), `quantidade_desejada` (alias `quantidade`), opcional: `preco_maximo`, `is_recorrente` |
| `demanda_recorrente_gerada` | Eq.4 Demanda | mesmo payload de `demanda_criada` (`is_recorrente` é forçado a `true`) |

Aceitamos múltiplos esquemas de nomenclatura por compatibilidade defensiva:
- **Eq.3 Fornecimentos** publica em camelCase com prefixo `id` (`idFornecimento`, `idProduto`, ...) — confirmado em `app/services/fornecimento_service.py` do [repo deles](https://github.com/theudevs/fornecimentos-service). Os aliases snake_case continuam aceitos para o smoke test e ferramentas internas (`scripts/event_publish.*`).
- **Eq.4 Demanda** segue o DDL com prefixo `id_` (`id_demanda`, `id_produto`, ...) ou snake_case curto.

⚠️ **Lacunas conhecidas no contrato da Eq.3 (a alinhar com Eliel):**
- Eles **não publicam** evento ao atualizar um fornecimento via `PUT /fornecimentos/{id}` — se o fornecedor mudar `preco_unitario` ou `produto_id`, nosso snapshot fica com o valor antigo.
- Eles **não publicam** evento ao inativar via `DELETE /fornecimentos/{id}` — a oferta inativada continua viva no nosso snapshot até o pod reiniciar.

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

### API REST (todas exigem `Authorization: Bearer <jwt>` exceto `/health`)

Rotas **internas** dos services (o gateway externo encaminha `/api/mercado/*` e `/api/negociacoes/*` removendo o prefixo antes de proxy):

| Service | Método | Rota interna | Descrição |
|---|---|---|---|
| ambos | `GET` | `/health` | público — probe de infra |
| mercado-service | `GET` | `/snapshot/{produto_id}` | debug do snapshot in-memory (oferta vs demanda) |
| mercado-service | `GET` | `/processos` | debug dos processos disparados pelo matching |
| mercado-service | `GET` | `/propostas?fornecedor_id=` | leilões diretos aguardando o "sim/não" do fornecedor (gate). Sem `fornecedor_id`, filtra pelo `empresa_id` do JWT |
| mercado-service | `POST` | `/propostas/{processo_id}/confirmar` | fornecedor abre (`{"decisao":"sim"}`) ou recusa (`"nao"`) o leilão direto. "nao" fecha interno, nada é publicado |
| mercado-service | `GET` | `/propostas/log` | log in-memory das decisões sim/não do fornecedor |
| negociacao-service | `GET` | `/processos?status=&modo=&produto_id=` | listar processos |
| negociacao-service | `GET` | `/processos/{id}` | detalhe + lista de lances |
| negociacao-service | `POST` | `/processos/{id}/lances` | registrar lance (`empresa_id` vem do JWT) |
| negociacao-service | `POST` | `/processos/{id}/fechar` | fechamento manual (admin) |

JWT validado localmente — issuer `portal-autenticacao`, audience `portal-b2b`, HS256, mesma `JWT_SECRET` do MS Usuários.

Para tipagem TypeScript automática, importe [`docs/contracts/negociacao.openapi.json`](docs/contracts/negociacao.openapi.json) no `openapi-typescript` ou `orval`. Para regerar os snapshots após mudança no código: `python scripts/export_openapi.py` (requer `docker compose up -d`).

### Ferramentas de integração

**Event tap** — escuta os eventos Kafka em tempo real (formatados, com cor por tópico). Útil pra Eq.3/Eq.4 verem o payload exato chegando sem implementar consumer próprio:

```bash
# todos os 8 tópicos
scripts/event_tap.sh

# filtrar
scripts/event_tap.sh negociacao_fechada lance_realizado
```

**Event publish** — publica um evento arbitrário a partir de fixture JSON. Útil pra testar nosso mercado sem precisar implementar o publisher de Eq.3/Eq.4 ainda:

```bash
# usa fixture com payload puro — embrulha em envelope automaticamente
scripts/event_publish.sh demanda_criada docs/integration/fixtures/demanda_criada.example.json

# ou com envelope completo (--no-wrap)
scripts/event_publish.sh negociacao_fechada meu_envelope_completo.json --no-wrap
```

Fixtures prontas em [`docs/integration/fixtures/`](docs/integration/fixtures/) para os 4 eventos consumidos.

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
   - `/api/negociacoes/* → negociacao-service:5006` (note plural)

7. Smoke test contra o gateway oficial (após o passo 6):

   ```bash
   curl http://34.8.17.245/api/mercado/health
   curl http://34.8.17.245/api/negociacoes/health
   ```

Para voltar ao dev local, basta rodar `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d` e apontar `.env` para `localhost`/credenciais locais.

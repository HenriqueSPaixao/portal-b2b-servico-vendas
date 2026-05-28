# Status da integração — domínio Vendas

Última atualização: 2026-05-18 · Responsável: Henrique (Mercado + Negociação)

Este documento rastreia o que está **pronto** vs **pendente** para os dois microsserviços rodarem contra a infra oficial do Portal B2B (Cloud SQL + cluster Kafka + gateway Nginx) e serem consumidos pelas outras equipes.

## ✓ Pronto (entregue por nós)

- [x] Backend `mercado-service` (porta 5005) — Matching Engine in-memory, 3 modos de negociação.
- [x] Backend `negociacao-service` (porta 5006) — Processos + lances + fechamento + scheduler de leilão.
- [x] Stack dev local (`docker-compose.local.yml`) — Postgres + Redpanda + PgAdmin, DDL aplicado de `portal-b2b-database`.
- [x] Smoke test end-to-end ([`scripts/smoke_test.py`](../scripts/smoke_test.py)) — valida `direto`, `leilao_direto`, `leilao_reverso`. Exit code 0 = todos passam.
- [x] Contratos REST publicados em [`docs/contracts/mercado.openapi.json`](contracts/mercado.openapi.json) e [`docs/contracts/negociacao.openapi.json`](contracts/negociacao.openapi.json).
- [x] Contratos Kafka publicados em [`docs/contracts/events/`](contracts/events/) — 8 eventos + envelope, formato JSON Schema 2020-12.
- [x] Postman collection — [`docs/integration/postman_collection.json`](integration/postman_collection.json).
- [x] Fixtures dos eventos consumidos — [`docs/integration/fixtures/`](integration/fixtures/) — qualquer equipe publica via `scripts/event_publish.py`.
- [x] Event-tap — [`scripts/event_tap.py`](../scripts/event_tap.py) — escuta em tempo real os 4 eventos que publicamos.

## ⏳ Pendente — infra (responsável: Sérgio)

- [ ] Senha do `svc_portal_b2b` no Cloud SQL `136.114.235.212:5432` — pedimos.
- [ ] Acesso de rede (VPN) ao Cloud SQL e ao cluster Kafka `10.128.0.2-4:9092`.
- [ ] Nginx do gateway oficial roteando:
    - [ ] `/api/mercado/*` → `mercado-service:5005`
    - [ ] `/api/negociacoes/*` → `negociacao-service:5006` (plural — padrão da infra)
- [ ] (Opcional, fora de escopo agora) Servir SPA na raiz `/mercado` e `/negociacao` — apenas se o grupo confirmar que UI por microsserviço é cobrada.

## ⏳ Pendente — autenticação (responsável: Guilherme)

- [ ] `JWT_SECRET` definitivo do MS Usuários alinhado conosco (`HS256`, issuer `portal-autenticacao`, audience `portal-b2b`).
- [ ] Exemplo de claims que o portal emite — campos `empresa_id`, `role`, `sub` validados.

## ⏳ Pendente — equipes parceiras

| Equipe | Quem | O que falta |
|---|---|---|
| 3 Fornecimentos | Eliel | Publicar `fornecimento_criado` e `estoque_atualizado` no cluster oficial seguindo [`fornecimento_criado.schema.json`](contracts/events/consumidos/fornecimento_criado.schema.json) e [`estoque_atualizado.schema.json`](contracts/events/consumidos/estoque_atualizado.schema.json). |
| 4 Demanda | Adrielly | Publicar `demanda_criada` / `demanda_recorrente_gerada` seguindo [`demanda_criada.schema.json`](contracts/events/consumidos/demanda_criada.schema.json). Consumir `negociacao_fechada` para criar `pedido_criado`. |
| Portal / Frontend | (a confirmar) | Decisão se cada microsserviço entrega UI própria ou só o portal central consome nossos REST. Pendente da resposta no grupo SD. |

## ❓ Decisões abertas

- **UI por microsserviço:** pendente confirmação com o grupo (mensagem no WhatsApp). Se for cobrado, plano de fronts React+Tailwind está pronto para ser iniciado (~6h por front, padrão verde `#4cc465` + accent por domínio — cyan no Mercado, âmbar na Negociação).
- **Tópico `pedido_criado`:** nós não criamos pedido. Eq.4 deve confirmar que está consumindo `negociacao_fechada` e gerando `pedido_criado` na sequência ([README.md:200-216](../README.md#L200-L216) tem o payload self-contained).

## Como verificar integração rapidamente

1. `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d` (stack local).
2. `python scripts/export_openapi.py` — gera os snapshots OpenAPI atualizados.
3. Em um terminal: `scripts/event_tap.bat` (Windows) ou `scripts/event_tap.sh` — começa a escutar todos os tópicos.
4. Em outro terminal: `scripts/run_smoke.bat` — dispara os 3 cenários e o event_tap mostra os 6+ eventos passando.
5. Importar [`docs/integration/postman_collection.json`](integration/postman_collection.json) no Postman e clicar nos endpoints — valida REST + JWT contra a stack local.

Quando os itens "Pendente — infra" estiverem resolvidos, repetir 1-5 apontando `.env` para o cluster oficial é o único passo extra.

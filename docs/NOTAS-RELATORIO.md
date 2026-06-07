# Notas para o relatório técnico — Domínio Vendas (Mercado + Negociação)

> **Matéria-prima** para o relatório técnico de Sistemas Distribuídos. NÃO é o relatório.
> É um acúmulo de fatos/decisões importantes pra puxar na hora de escrever. As instruções
> oficiais de produção do relatório serão deixadas pelo Henrique no diretório do projeto.

## 1. Visão geral do domínio
- **mercado-service** (`:5005`) — Matching Engine **in-memory**. Cruza oferta×demanda e decide
  o modo (`direto`, `leilao_direto`, `leilao_reverso`). Voltado ao fornecedor.
- **negociacao-service** (`:5006`) — Auction/Sale Executor. Persiste `processo_negociacao` e
  `lance` no Postgres; encerra e publica `negociacao_fechada`.
- **mercado-web** (`:8085`) e **negociacao-web** (`:8086`) — fronts React+Vite+Tailwind.

## 2. Decisões de arquitetura (defensáveis na banca)
- **Boundary "Vendas NÃO cria pedido".** O ciclo encerra publicando `negociacao_fechada`
  *self-contained*; quem cria `pedido` é a Eq.4 Demanda. Mantém o domínio desacoplado.
- **Gate de confirmação do fornecedor** (pedido do professor). "O fornecedor manda no mercado":
  - `leilao_direto` → vira **proposta pendente**; só publica `modo_negociacao_definido`/
    `leilao_iniciado` após o "sim" do fornecedor na mercado-web.
  - `leilao_reverso` → automático (participar = dar lance).
  - `direto` → automático (fecha na hora).
  - **"Não"** → resolvido 100% dentro do mercado-service (devolve as demandas ao pool,
    re-match com outro fornecedor; a oferta recusada fica de fora → sem loop). **Nada é
    publicado** → não gera dependência nem muda payload para nenhuma equipe.
  - Estado das propostas pendentes + log sim/não: **in-memory + stdout** (coerente com o
    mercado ser in-memory). Doc: `docs/ARQUITETURA-confirmacao-fornecedor.md`.
- **Negociação como "chat" de lances** entre fornecedor e comprador (polling); o backend de
  lances não mudou (`POST /lances` → `lance_realizado`).
- **Encerramento** é, no fluxo normal, **automático pelo tempo** (scheduler de `data_fim`). O
  botão "Encerrar (operador)" na negociacao-web é atalho de operador/admin (`manual_admin`).

## 3. Mapa de integração
| Direção | Evento | Parte |
|---|---|---|
| Consome | `produto_cadastrado` | Eq.1 Produtos (Raíky) |
| Consome | `fornecimento_criado`, `estoque_atualizado` | Eq.3 Fornecimentos (Eliel) |
| Consome | `demanda_criada`, `demanda_recorrente_gerada`, `pedido_criado` | Eq.4 Demanda (Adrielly/Lange) |
| Publica | `modo_negociacao_definido`, `leilao_iniciado` | mercado-service |
| Publica | `lance_realizado` | negociacao-service (observabilidade) |
| Publica | `negociacao_fechada` | negociacao-service → **Eq.4 cria o pedido** |

- **Envelope padrão** (todas as equipes): `eventId`, `eventType`, `eventVersion`, `timestamp`,
  `source`, `correlationId`, `payload`. Nome do tópico == `eventType`.
- **Auth:** JWT HS256, `iss=portal-autenticacao`, `aud=portal-b2b`, secret compartilhado
  (ver `.env.local`). Handshake front→front via `?jwt=…` + `sessionStorage`.
- **Gateway (Nginx do Sérgio):** expõe `/api/mercado/*` e `/api/negociacoes/*` (plural) e
  **remove o prefixo** antes de encaminhar — por isso nossas rotas internas são "nuas".

## 4. Diagnóstico de integração com a Eq.4 (caso real — jun/2026)
Sintomas reportados pela Eq.4: (a) publicam demanda/pedido e nada aparece nas nossas telas;
(b) não recebem `negociacao_fechada`.

- **Causa #1 (primária) — clusters Kafka diferentes.** Nosso `.env`/`.env.local` apontavam pro
  `redpanda:9092` (local); a Eq.4 aponta pro cluster oficial `10.128.0.2/3/4:9092`. Em buses
  diferentes, nenhum evento cruza — explica os dois sintomas. **Correção: rodar nossos serviços
  no cluster/infra oficial** (ver checklist na seção 6).
- **Causa #2 (secundária, nossa) — consumer dropava a demanda.** `handle_demanda_criada` exigia
  `empresa_comprador_id`, que a Eq.4 não envia → `KeyError` → descartava o evento. Nosso PRÓPRIO
  contrato (`demanda_criada.schema.json`) já marcava o campo como **opcional**. **Corrigido:**
  campo tornado opcional em `snapshot.py` (`Demanda.empresa_comprador_id: UUID | None`),
  `consumers.py` (usa `_uuid_or_none`) e `engine.py` (filtra `None` da lista de habilitados pra
  não virar a string `"None"` e quebrar a habilitação do leilão).
- **Causa #3 (secundária, nova) — o gate segura o `negociacao_fechada`.** No `leilao_direto`, o
  evento só sai após o fornecedor confirmar. `direto`/`reverso` seguem automáticos. **Mantido
  (feature do professor) + comunicado à Eq.4.**
- **O que já estava certo:** o `negociacao_consumer.py` da Eq.4 lê exatamente os nossos nomes de
  campo (`demanda_id`, `empresa_fornecedor_id`, `valor_unitario_final`, `valor_total`,
  `quantidade`, `fornecimento_id`, `motivo_fechamento`) e filtra `eventType`. Tópicos e JWT
  alinhados. Ou seja, no cluster certo, o evento é parseado corretamente por eles.

**Lição pro relatório:** num sistema event-driven, três condições têm que valer juntas —
(1) mesmo broker/cluster, (2) mesmos nomes de tópico, (3) payloads compatíveis (com
tolerância defensiva a campos opcionais). Aqui, (2) e (3-consumer deles) estavam ok; o que
faltava era (1) e a nossa tolerância a campo opcional.

## 5. Validação feita (evidência)
- **Smoke end-to-end** (`scripts/smoke_test.py`, via `scripts/run_smoke.bat`): cenários
  **A** direto, **B** leilão direto (passando pelo gate = "sim"), **C** leilão reverso,
  **D** enriquecimento de nome de produto, **E** recusa do leilão direto (prova que o "não"
  não cria processo e fica registrado no log). O smoke fecha os leilões via REST (`POST /fechar`),
  ficando independente da duração configurada.
- **Testes isolados do engine** (producer fake, sem Kafka/Postgres): gate sim/não, janela do
  leilão renovada na abertura, e demanda **sem** `empresa_comprador` (não dropa, lista de
  habilitados sai sem `"None"`).
- **Builds dos fronts** (`npm run build`) em mercado-web e negociacao-web passando.

## 6. Checklist de deploy no cluster/infra OFICIAL (Fix 1 — bloqueio da integração)
> O código já está pronto. Isto é passo de **deploy/coordenação com o Sérgio**.
1. `.env` (usado pelo `docker-compose.yml` base) com valores oficiais:
   - `KAFKA_BOOTSTRAP_SERVERS=10.128.0.2:9092,10.128.0.3:9092,10.128.0.4:9092`
   - `DATABASE_URL=postgresql+asyncpg://svc_portal_b2b:<senha_oficial>@136.114.235.212:5432/portal_b2b`
2. Subir **só** o compose base: `docker compose -f docker-compose.yml up -d --build`
   (sem o `-f docker-compose.local.yml`, que sobe Redpanda/Postgres locais).
3. ⚠️ **Reachability:** `10.128.0.x` são IPs **internos da VPC** do GCP — não acessíveis da
   máquina local. Rodar nossos containers **dentro da infra** (VM, na rede `portal-b2b-network`)
   **ou** via VPN. Confirmar com o Sérgio onde subir.
4. Rede externa `portal-b2b-network` criada pela infra; gateway roteando `/api/mercado/*` e
   `/api/negociacoes/*`.
5. Validar (seção "Verificação" do plano): event_tap no cluster filtrando `demanda_criada` e
   `negociacao_fechada`; Eq.4 publica → conferir no nosso `GET /snapshot`; fechar uma negociação
   → conferir recepção no consumer da Eq.4.

## 7. Mensagem objetiva pra mandar ao Lange (Eq.4)
> "Mano, achei o problema: nossos serviços estavam apontados pro **Redpanda local** e vocês pro
> **cluster oficial** — por isso nenhum evento cruzava nos dois sentidos. Vamos subir do nosso
> lado no cluster oficial. Já corrigi também um ponto nosso: a gente exigia o id da empresa
> compradora no `demanda_criada`/`pedido_criado` e dropava se faltasse — agora é **opcional** (bate
> com o nosso schema), então não precisa mexer no payload de vocês. Por último, um aviso: no
> **leilão direto** o `negociacao_fechada` só sai **depois** que o fornecedor confirma 'Abrir' na
> nossa tela (regra que o professor pediu); em `direto` e `leilão reverso` é automático. Seu
> `negociacao_consumer` já está com os campos certos, então quando chegar, parseia normal."

## 8. Mapeamento aos 5 critérios de avaliação SD
- **Desacoplamento:** boundary "não cria pedido"; comunicação 100% por eventos; gate resolve o
  "não" sem gerar dependência externa.
- **Uso de Kafka:** consumo/publicação assíncronos; envelope padronizado; tópicos == eventType.
- **Consistência:** decisão consciente in-memory no mercado (efêmero, reconstruível por replay)
  vs Postgres na negociação (durável); tolerância defensiva a payloads (campos opcionais).
- **Modelagem:** três modos de negociação derivados de oferta×demanda; processo/lance.
- **Integração:** contratos versionados (`docs/contracts/`), tooling (`event_tap`,
  `event_publish`, OpenAPI, Postman) e o diagnóstico cross-team documentado aqui.

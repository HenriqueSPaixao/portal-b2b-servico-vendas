# Confirmação do fornecedor no mercado — "fornecedor manda no mercado"

> Adição de arquitetura pedida pelo professor (jun/2026). Define **como** entra a
> interação humana no domínio Vendas **sem mudar nenhum payload** nem gerar
> dependência para outras equipes. Decidir aqui **antes** de alterar código.

## Contexto

Hoje o `mercado-service` é totalmente automático: o engine cruza oferta×demanda,
decide o modo e **publica na hora** `modo_negociacao_definido` (+ `leilao_iniciado`).
O professor pediu que o **fornecedor** passe a decidir se quer abrir o leilão —
"o fornecedor manda no mercado" — e que a negociação seja apenas uma interface de
lances (um "chatzinho") entre fornecedor e comprador.

## Regra por modo

O *matching* continua automático (o engine **propõe** o match). O que muda é que
**abrir um leilão direto** passa a depender de uma confirmação do fornecedor na UI.

| Modo | Quem é dono / decide | Gate de confirmação? |
|---|---|---|
| `direto` (oferta ≈ demanda, 1:1) | match imediato | **Automático** — fecha na hora, sem gate |
| `leilao_direto` (1 fornecedor, N compradores competindo) | o **fornecedor** (dono da oferta) | **SIM** — confirma sim/não antes de qualquer evento sair |
| `leilao_reverso` (1 comprador, N fornecedores competindo) | os fornecedores competindo | **NÃO** — participar é dar lance (opt-in implícito) |

Mapeia direto na estrutura atual do engine: no leilão direto o match é
`ofertas[0]` (um único fornecedor) + N demandas — por isso há um fornecedor único
para confirmar. No reverso há N fornecedores, então não existe "um" para decidir;
a participação deles é o próprio lance.

## Fluxo do gate (leilão direto)

```
matching detecta oferta × demanda
        │  modo = leilao_direto
        ▼
cria PROPOSTA PENDENTE (in-memory) + reserva a oferta/demanda do snapshot
        │
        ▼
mercado-web mostra a proposta ao fornecedor: "Abrir o leilão?  [ Sim ]  [ Não ]"
        │
   ┌────┴───────────────────────────────┐
 [ Sim ]                              [ Não ]
   │                                    │
 log "sim" (stdout)                  log "não" (stdout)
   │                                    │
 publica modo_negociacao_definido     devolve as DEMANDAS ao snapshot;
 + leilao_iniciado                    a oferta recusada fica de fora (retirada).
   │                                   Re-match casa as demandas com OUTRO
   ▼                                   fornecedor — a oferta recusada não é
 negociacao abre o leilão             reoferecida → sem loop.
 (fluxo normal de lances)               │
                                        ▼
                                      NADA é publicado — 100% interno ao mercado
```

## Propriedades (por que isso é seguro)

- **Zero mudança de payload e zero dependência para outras equipes.** O único
  evento que cruza a fronteira do domínio Vendas é o `modo_negociacao_definido`.
  No caminho do "não" ele simplesmente **não é publicado** — logo `negociacao`
  nunca cria processo, `negociacao_fechada` nunca dispara, Eq.4 nunca é tocada.
  Eq.3/Eq.4/Eq.8 não percebem diferença alguma: só veem o leilão abrir **após**
  o "sim". Mantém o boundary "Vendas não cria pedido".
- **"Não" fecha dentro do mercado-service.** O re-match usa apenas o snapshot
  in-memory que já temos (dados de eventos já consumidos) — não pede nada a
  ninguém. Se não houver outro fornecedor, a demanda apenas aguarda no snapshot,
  exatamente como já acontece hoje antes de qualquer match.
- **Estado e log são in-memory + stdout**, coerente com o mercado ser in-memory.
  Propostas pendentes e o log sim/não somem em restart — aceitável para a demo.

## Negociação = interface de lances ("chatzinho")

Mudança majoritariamente de **frontend** (`negociacao-web`): renderizar os lances
como troca em tempo quase real entre fornecedor e comprador (via **polling**, sem
WebSocket). O backend **não muda**: `POST /lances` → `lance_realizado` e o
fechamento por `negociacao_fechada` continuam idênticos.

## Implementação prevista (a fazer — revisar antes de codar)

**mercado-service**
- `EngineState` ganha `propostas_pendentes: dict[processo_id, PropostaPendente]`,
  guardando a oferta/demanda reservadas e o `empresa_fornecedor_id` que deve confirmar.
- `engine.evaluate()`: no `leilao_direto`, cria proposta pendente em vez de publicar.
  `direto` e `leilao_reverso` seguem publicando direto (sem gate).
- Novos endpoints REST (`routes.py`):
  - `GET /propostas?fornecedor_id=...` — propostas pendentes daquele fornecedor.
  - `POST /propostas/{processo_id}/confirmar` com `{ "decisao": "sim" | "nao" }`.
- "sim" → publica `modo_negociacao_definido` (+ `leilao_iniciado`). "não" → loga,
  devolve as **demandas** ao snapshot (`marcar_disponiveis`) e mantém a **oferta
  recusada fora** (continua consumida) → o re-match não a reoferece ao mesmo
  fornecedor. Em seguida re-chama `evaluate()` para casar as demandas com outro.

**mercado-web**
- Tela voltada ao fornecedor: lista de propostas pendentes + botões Sim/Não +
  visão do log das decisões.

**negociacao-web**
- Lances em formato chat (polling). Backend de lances inalterado.

## Decisões travadas (jun/2026, com Henrique)

| Decisão | Escolha |
|---|---|
| Modo `direto` | Automático (sem gate) |
| Leilão `reverso` | Automático (participar = dar lance) |
| Leilão `direto` | Gate de confirmação do fornecedor na mercado-web |
| Fornecedor diz "Não" | Fecha no mercado-service; devolve ao pool com guard anti-loop; nada publicado |
| Log sim/não + propostas pendentes | Só em memória + stdout |
| Negociação "chatzinho" | Frontend (polling); backend de lances inalterado |

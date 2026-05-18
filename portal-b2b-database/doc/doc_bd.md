# Modelo ER — Portal B2B

## Visão Geral

Schema: `portal_b2b` | Banco: PostgreSQL

| Role | Tipo | Permissões |
|------|------|------------|
| `db_portal_b2b` | Admin/DDL | Owner, DDL, DML |
| `svc_portal_b2b` | Aplicação | SELECT, INSERT, UPDATE, DELETE |

> Toda migração DDL deve ser executada como `db_portal_b2b`. O `svc_portal_b2b` não tem permissão de CREATE.

---

## Tabelas

### 1. produtos_transporte

Tipos de transporte disponíveis no sistema.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `nome` | VARCHAR(150) | NOT NULL, UNIQUE (case-insensitive) |
| `descricao` | VARCHAR(500) | NULL |
| `ativo` | BOOLEAN | NOT NULL, default `TRUE` |
| `data_cadastro` | TIMESTAMPTZ | NOT NULL |
| `usuario_cadastro` | UUID | NULL |
| `ultima_alteracao` | TIMESTAMPTZ | NULL |
| `usuario_alteracao` | UUID | NULL |

---

### 2. produtos_categoria

Hierarquia de categorias. Auto-referenciada para suportar subcategorias.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `categoria_pai_id` | UUID | FK → `produtos_categoria(id)`, NULL |
| `nome` | VARCHAR(150) | NOT NULL, UNIQUE (case-insensitive) |
| `descricao` | VARCHAR(500) | NULL |
| `ativo` | BOOLEAN | NOT NULL, default `TRUE` |
| `data_cadastro` | TIMESTAMPTZ | NOT NULL |
| `usuario_cadastro` | UUID | NULL |
| `ultima_alteracao` | TIMESTAMPTZ | NULL |
| `usuario_alteracao` | UUID | NULL |

---

### 3. produtos_unidade_medida

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `nome` | VARCHAR(150) | NOT NULL, UNIQUE (case-insensitive) |
| `sigla` | VARCHAR(20) | NOT NULL, UNIQUE (case-insensitive) |
| `descricao` | VARCHAR(500) | NULL |
| `ativo` | BOOLEAN | NOT NULL, default `TRUE` |
| `data_cadastro` | TIMESTAMPTZ | NOT NULL |
| `usuario_cadastro` | UUID | NULL |
| `ultima_alteracao` | TIMESTAMPTZ | NULL |
| `usuario_alteracao` | UUID | NULL |

---

### 4. produtos_produto

Catálogo genérico de produtos. Sem preço e sem quantidade — esses dados ficam em `fornecimento` (RN-PROD-01/02).

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `transporte_id` | UUID | FK → `produtos_transporte(id)` |
| `categoria_id` | UUID | FK → `produtos_categoria(id)` |
| `unidade_medida_id` | UUID | FK → `produtos_unidade_medida(id)` |
| `codigo` | VARCHAR(60) | NOT NULL, UNIQUE (case-insensitive) |
| `nome` | VARCHAR(150) | NOT NULL |
| `descricao` | VARCHAR(1000) | NULL |
| `ativo` | BOOLEAN | NOT NULL, default `TRUE` |
| `data_cadastro` | TIMESTAMPTZ | NOT NULL |
| `usuario_cadastro` | UUID | NULL |
| `ultima_alteracao` | TIMESTAMPTZ | NULL |
| `usuario_alteracao` | UUID | NULL |

---

### 5. perfil

Papéis disponíveis no sistema.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `nome` | VARCHAR(50) | NOT NULL, UNIQUE |

**Seed:** `FORNECEDOR`, `COMPRADOR`, `TRANSPORTADORA`

---

### 6. empresa

Representa qualquer organização cadastrada no sistema.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `razao_social` | VARCHAR(255) | NOT NULL |
| `nome_fantasia` | VARCHAR(255) | NULL |
| `cnpj` | CHAR(14) | NOT NULL, UNIQUE |
| `email` | VARCHAR(150) | NOT NULL, UNIQUE |
| `telefone` | VARCHAR(20) | NULL |
| `status` | VARCHAR(20) | NOT NULL, default `'ATIVO'` |
| `data_cadastro` | TIMESTAMPTZ | NOT NULL |
| `ultima_alteracao` | TIMESTAMPTZ | NULL |

---

### 7. empresa_perfil

Associação N:N entre empresa e perfil. Uma empresa pode ter múltiplos perfis (RN-USER-02).

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `empresa_id` | UUID | PK, FK → `empresa(id)` ON DELETE CASCADE |
| `perfil_id` | UUID | PK, FK → `perfil(id)` ON DELETE CASCADE |

---

### 8. usuario

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `empresa_id` | UUID | FK → `empresa(id)` |
| `nome` | VARCHAR(150) | NOT NULL |
| `email` | VARCHAR(150) | NOT NULL, UNIQUE |
| `senha_hash` | TEXT | NOT NULL |
| `telefone` | VARCHAR(20) | NULL |
| `status` | VARCHAR(20) | NOT NULL, default `'ATIVO'` |
| `data_cadastro` | TIMESTAMPTZ | NOT NULL |
| `ultima_alteracao` | TIMESTAMPTZ | NULL |

---

### 9. endereco

Endereços vinculados a empresas. Usado como origem em fornecimentos.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `empresa_id` | UUID | FK → `empresa(id)` |
| `cidade` | VARCHAR(100) | NOT NULL |
| `estado` | CHAR(2) | NOT NULL |
| `cep` | CHAR(8) | NOT NULL |
| `latitude` | DECIMAL(9,6) | NULL |
| `longitude` | DECIMAL(9,6) | NULL |

---

### 10. fornecimento

Oferta de um fornecedor para um produto. Preço e quantidade ficam aqui, não no produto (RN-FORN-01/02).

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `empresa_fornecedor_id` | UUID | FK → `empresa(id)` |
| `produto_id` | UUID | FK → `produtos_produto(id)` |
| `endereco_origem_id` | UUID | FK → `endereco(id)` |
| `preco_unitario` | DECIMAL(18,4) | NOT NULL, > 0 |
| `quantidade_disponivel` | DECIMAL(18,4) | NOT NULL, >= 0 |
| `ativo` | BOOLEAN | NOT NULL, default `TRUE` |
| `data_cadastro` | TIMESTAMPTZ | NOT NULL |
| `ultima_alteracao` | TIMESTAMPTZ | NULL |

---

### 11. demanda

Interesse de compra de um comprador (RN-DEM-01..05).

> **Convenção:** esta tabela usa `data_criacao` e `atualizado_em` por padrão da equipe de demanda.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id_demanda` | UUID | PK |
| `id_empresa_comprador` | UUID | FK → `empresa(id)` |
| `id_produto` | UUID | FK → `produtos_produto(id)` |
| `id_endereco_destino` | UUID | FK → `endereco_entrega(id_endereco)` |
| `quantidade_desejada` | DECIMAL(12,3) | NOT NULL, > 0 |
| `status` | VARCHAR(20) | NOT NULL, default `'ABERTA'` |
| `id_usuario_criador` | UUID | NULL |
| `preco_maximo` | DECIMAL(12,2) | NULL |
| `prioridade` | VARCHAR(10) | NULL |
| `is_recorrente` | BOOLEAN | NOT NULL, default `FALSE` |
| `observacoes` | TEXT | NULL |
| `data_criacao` | TIMESTAMPTZ | NOT NULL |
| `atualizado_em` | TIMESTAMPTZ | NULL |

---

### 12. produto_cache

Cache local de produtos no serviço de demanda, sincronizado via Kafka a partir do módulo de produtos.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id_produto` | UUID | PK |
| `codigo` | VARCHAR(60) | NOT NULL, UNIQUE |
| `nome` | VARCHAR(150) | NOT NULL |
| `ativo` | BOOLEAN | NOT NULL, default `TRUE` |
| `sincronizado_em` | TIMESTAMPTZ | NOT NULL |

---

### 13. endereco_entrega

Endereço de entrega detalhado, específico do módulo de demanda.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id_endereco` | UUID | PK |
| `id_empresa` | UUID | FK → `empresa(id)` |
| `logradouro` | VARCHAR(200) | NOT NULL |
| `numero` | VARCHAR(20) | NULL |
| `complemento` | VARCHAR(100) | NULL |
| `bairro` | VARCHAR(100) | NULL |
| `cidade` | VARCHAR(100) | NOT NULL |
| `estado` | CHAR(2) | NOT NULL |
| `cep` | VARCHAR(9) | NOT NULL |
| `latitude` | DECIMAL(9,6) | NULL |
| `longitude` | DECIMAL(9,6) | NULL |
| `ativo` | BOOLEAN | NOT NULL, default `TRUE` |
| `data_criacao` | TIMESTAMPTZ | NOT NULL |
| `atualizado_em` | TIMESTAMPTZ | NULL |
| `apelido` | VARCHAR(50) | NULL |

---

### 14. demanda_recorrencia

Detalhes de recorrência separados da demanda principal.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id_recorrencia` | UUID | PK |
| `id_demanda` | UUID | FK → `demanda(id)` |
| `frequencia` | VARCHAR(10) | NOT NULL — ex: `DIARIA`, `SEMANAL`, `MENSAL` |
| `quantidade_por_periodo` | DECIMAL(12,3) | NOT NULL |
| `data_inicio` | DATE | NOT NULL |
| `data_fim` | DATE | NULL |
| `dia_preferencial` | VARCHAR(20) | NULL |
| `ativa` | BOOLEAN | NOT NULL, default `TRUE` |
| `data_criacao` | TIMESTAMPTZ | NOT NULL |
| `atualizado_em` | TIMESTAMPTZ | NULL |

> **Check:** `data_fim > data_inicio` quando `data_fim` não é NULL.

---

### 15. wishlist_item

Lista de desejos — interesse ainda não formalizado como demanda.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id_item` | UUID | PK |
| `id_empresa` | UUID | FK → `empresa(id)` |
| `id_usuario` | UUID | NULL |
| `id_produto` | UUID | NULL |
| `quantidade_desejada` | DECIMAL(12,3) | NULL |
| `preco_maximo` | DECIMAL(12,2) | NULL |
| `prioridade` | VARCHAR(10) | NULL |
| `observacoes` | TEXT | NULL |
| `convertido_em_demanda` | BOOLEAN | NOT NULL, default `FALSE` |
| `id_demanda_gerada` | UUID | FK → `demanda(id)`, NULL |
| `data_criacao` | TIMESTAMPTZ | NOT NULL |
| `atualizado_em` | TIMESTAMPTZ | NULL |

---

### 16. processo_negociacao

Gerencia a negociação de compra/venda. O modo é determinado pela relação entre oferta e demanda.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `produto_id` | UUID | FK → `produtos_produto(id)` |
| `modo` | VARCHAR(20) | NOT NULL, check: `direto`, `leilao_direto`, `leilao_reverso` |
| `status` | VARCHAR(20) | NOT NULL, default `'ABERTO'` |
| `data_inicio` | TIMESTAMPTZ | NOT NULL |
| `data_fim` | TIMESTAMPTZ | NULL |
| `valor_reserva` | DECIMAL(18,4) | NULL |

| Condição de mercado | Modo |
|---------------------|------|
| oferta = demanda | `direto` |
| demanda > oferta | `leilao_direto` |
| oferta > demanda | `leilao_reverso` |

---

### 17. lance

Propostas feitas durante um processo de negociação.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `processo_id` | UUID | FK → `processo_negociacao(id)` |
| `empresa_id` | UUID | FK → `empresa(id)` |
| `valor_unitario` | DECIMAL(18,4) | NOT NULL, > 0 |
| `quantidade` | DECIMAL(18,4) | NOT NULL, > 0 |
| `data_lance` | TIMESTAMPTZ | NOT NULL |

---

### 18. pedido

Formaliza a compra após negociação concluída.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `processo_id` | UUID | FK → `processo_negociacao(id)` |
| `empresa_comprador_id` | UUID | FK → `empresa(id)` |
| `empresa_fornecedor_id` | UUID | FK → `empresa(id)` |
| `fornecimento_id` | UUID | FK → `fornecimento(id)` |
| `frete_selecionado_id` | UUID | FK → `frete_selecionado(id)`, NULL inicial |
| `valor_comissao` | DECIMAL(18,4) | NULL |
| `valor_total` | DECIMAL(18,4) | NOT NULL, > 0 |
| `status` | VARCHAR(20) | NOT NULL, default `'PENDENTE'` |
| `data_pedido` | TIMESTAMPTZ | NOT NULL |

> `frete_selecionado_id` começa NULL e é preenchido após seleção do frete.

---

### 19. item_pedido

Itens que compõem o pedido.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `pedido_id` | UUID | FK → `pedido(id)` |
| `produto_id` | UUID | FK → `produtos_produto(id)` |
| `fornecimento_id` | UUID | FK → `fornecimento(id)` |
| `quantidade` | DECIMAL(18,4) | NOT NULL, > 0 |
| `valor_unitario` | DECIMAL(18,4) | NOT NULL, > 0 |

---

### 20. solicitacao_frete

Gerada a partir do pedido para cotação de frete.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `pedido_id` | UUID | FK → `pedido(id)` |
| `tipo_transporte` | VARCHAR(50) | NOT NULL |
| `status` | VARCHAR(30) | NOT NULL, default `'AGUARDANDO'` |
| `data_criacao` | TIMESTAMPTZ | NOT NULL |

---

### 21. cotacao_frete

Propostas de frete enviadas por transportadoras.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `solicitacao_id` | UUID | FK → `solicitacao_frete(id)` |
| `transportadora_id` | UUID | FK → `empresa(id)` |
| `valor` | DECIMAL(18,4) | NOT NULL, > 0 |
| `prazo` | INTEGER | NOT NULL, > 0 — dias úteis |
| `data_cotacao` | TIMESTAMPTZ | NOT NULL |

---

### 22. frete_selecionado

Frete escolhido para o pedido. Um pedido só pode ter um frete selecionado.

| Coluna | Tipo | Restrições |
|--------|------|------------|
| `id` | UUID | PK |
| `pedido_id` | UUID | FK → `pedido(id)`, UNIQUE |
| `cotacao_id` | UUID | FK → `cotacao_frete(id)` |
| `data_selecao` | TIMESTAMPTZ | NOT NULL |

---

## Relacionamentos

```
produtos_transporte ◄──┐
produtos_categoria  ◄──┼── produtos_produto ──► fornecimento
produtos_unidade_medida ┘         │            ► demanda
                                  └──────────► processo_negociacao
                                               ► item_pedido

empresa ──► empresa_perfil ──► perfil
empresa ──► usuario
empresa ──► endereco ──► fornecimento
empresa ──► endereco_entrega ──► demanda
empresa ──► lance ──► processo_negociacao
demanda ──► demanda_recorrencia
demanda ◄── wishlist_item
produto_cache (sincronizado via Kafka ← produtos_produto)
processo_negociacao ──► pedido ──► item_pedido
                                ──► solicitacao_frete ──► cotacao_frete ──► frete_selecionado
                                ◄── frete_selecionado
```

---

## Convenções

| Aspecto | Padrão |
|---------|--------|
| PKs | UUID, `gen_random_uuid()` |
| Timestamps | `TIMESTAMPTZ`, default `NOW()` |
| Soft delete | `ativo BOOLEAN` |
| Auditoria | `data_cadastro` + `ultima_alteracao` |
| Status | SCREAMING_SNAKE_CASE |
| Decimais | `DECIMAL(18,4)` |
| Prazo frete | `INTEGER` (dias úteis) |
| Nomenclatura | `snake_case` sem prefixo |

> **Exceção — módulo de demanda:** tabelas `demanda`, `endereco_entrega`, `demanda_recorrencia` e `wishlist_item` utilizam `data_criacao` e `atualizado_em`, e IDs com prefixo `id_` nas colunas FK, por convenção da equipe responsável.

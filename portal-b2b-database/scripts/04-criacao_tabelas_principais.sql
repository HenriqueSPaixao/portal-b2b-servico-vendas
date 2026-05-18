-- ============================================================
-- Migration: Portal B2B — Schema completo
-- Schema: portal_b2b
-- Owner: db_portal_b2b | App: svc_portal_b2b (DML only)
--
-- Pré-requisitos (já existentes no banco):
--   portal_b2b.produtos_produto
--   portal_b2b.produtos_categoria
--   portal_b2b.produtos_transporte
--   portal_b2b.produtos_unidade_medida
--   portal_b2b.fn_produtos_atualizar_ultima_alteracao()
-- ============================================================

-- ------------------------------------------------------------
-- 1. perfil
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.perfil (
    id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nome    VARCHAR(50) NOT NULL,

    CONSTRAINT uq_perfil_nome UNIQUE (nome)
);

INSERT INTO portal_b2b.perfil (nome) VALUES
    ('FORNECEDOR'),
    ('COMPRADOR'),
    ('TRANSPORTADORA')
ON CONFLICT (nome) DO NOTHING;

-- ------------------------------------------------------------
-- 2. empresa
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.empresa (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    razao_social        VARCHAR(255) NOT NULL,
    nome_fantasia       VARCHAR(255) NULL,
    cnpj                CHAR(14)     NOT NULL,
    email               VARCHAR(150) NOT NULL,
    telefone            VARCHAR(20)  NULL,
    status              VARCHAR(20)  NOT NULL DEFAULT 'ATIVO',
    data_cadastro       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ultima_alteracao    TIMESTAMPTZ  NULL,

    CONSTRAINT uq_empresa_cnpj  UNIQUE (cnpj),
    CONSTRAINT uq_empresa_email UNIQUE (email)
);

-- ------------------------------------------------------------
-- 3. empresa_perfil
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.empresa_perfil (
    empresa_id  UUID NOT NULL,
    perfil_id   UUID NOT NULL,

    PRIMARY KEY (empresa_id, perfil_id),

    CONSTRAINT fk_ep_empresa FOREIGN KEY (empresa_id)
        REFERENCES portal_b2b.empresa(id) ON DELETE CASCADE,

    CONSTRAINT fk_ep_perfil FOREIGN KEY (perfil_id)
        REFERENCES portal_b2b.perfil(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 4. usuario
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.usuario (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id          UUID         NOT NULL,
    nome                VARCHAR(150) NOT NULL,
    email               VARCHAR(150) NOT NULL,
    senha_hash          TEXT         NOT NULL,
    telefone            VARCHAR(20)  NULL,
    status              VARCHAR(20)  NOT NULL DEFAULT 'ATIVO',
    data_cadastro       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ultima_alteracao    TIMESTAMPTZ  NULL,

    CONSTRAINT uq_usuario_email UNIQUE (email),

    CONSTRAINT fk_usuario_empresa FOREIGN KEY (empresa_id)
        REFERENCES portal_b2b.empresa(id)
);

-- ------------------------------------------------------------
-- 5. endereco
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.endereco (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id  UUID         NOT NULL,
    cidade      VARCHAR(100) NOT NULL,
    estado      CHAR(2)      NOT NULL,
    cep         CHAR(8)      NOT NULL,
    latitude    DECIMAL(9,6) NULL,
    longitude   DECIMAL(9,6) NULL,

    CONSTRAINT fk_endereco_empresa FOREIGN KEY (empresa_id)
        REFERENCES portal_b2b.empresa(id)
);

-- ------------------------------------------------------------
-- 6. fornecimento
-- Referencia produtos_produto (pré-existente)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.fornecimento (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_fornecedor_id   UUID          NOT NULL,
    produto_id              UUID          NOT NULL,
    endereco_origem_id      UUID          NOT NULL,
    preco_unitario          DECIMAL(18,4) NOT NULL,
    quantidade_disponivel   DECIMAL(18,4) NOT NULL,
    ativo                   BOOLEAN       NOT NULL DEFAULT TRUE,
    data_cadastro           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    ultima_alteracao        TIMESTAMPTZ   NULL,

    CONSTRAINT ck_fornecimento_preco CHECK (preco_unitario > 0),
    CONSTRAINT ck_fornecimento_qtd   CHECK (quantidade_disponivel >= 0),

    CONSTRAINT fk_fornecimento_empresa  FOREIGN KEY (empresa_fornecedor_id)
        REFERENCES portal_b2b.empresa(id),

    CONSTRAINT fk_fornecimento_produto  FOREIGN KEY (produto_id)
        REFERENCES portal_b2b.produtos_produto(id),

    CONSTRAINT fk_fornecimento_endereco FOREIGN KEY (endereco_origem_id)
        REFERENCES portal_b2b.endereco(id)
);

-- ------------------------------------------------------------
-- 7. demanda
-- Referencia produtos_produto (pré-existente)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.demanda (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_comprador_id    UUID          NOT NULL,
    produto_id              UUID          NOT NULL,
    endereco_destino_id     UUID          NOT NULL,
    quantidade_desejada     DECIMAL(18,4) NOT NULL,
    is_recorrente           BOOLEAN       NOT NULL DEFAULT FALSE,
    data_proxima_geracao    DATE          NULL,
    status                  VARCHAR(30)   NOT NULL DEFAULT 'ABERTA',
    data_cadastro           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_demanda_qtd         CHECK (quantidade_desejada > 0),
    CONSTRAINT ck_demanda_recorrencia CHECK (
        is_recorrente = FALSE OR data_proxima_geracao IS NOT NULL
    ),

    CONSTRAINT fk_demanda_empresa  FOREIGN KEY (empresa_comprador_id)
        REFERENCES portal_b2b.empresa(id),

    CONSTRAINT fk_demanda_produto  FOREIGN KEY (produto_id)
        REFERENCES portal_b2b.produtos_produto(id),

    CONSTRAINT fk_demanda_endereco FOREIGN KEY (endereco_destino_id)
        REFERENCES portal_b2b.endereco(id)
);

-- ------------------------------------------------------------
-- 8. processo_negociacao
-- Referencia produtos_produto (pré-existente)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.processo_negociacao (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    produto_id      UUID          NOT NULL,
    modo            VARCHAR(20)   NOT NULL,
    status          VARCHAR(20)   NOT NULL DEFAULT 'ABERTO',
    data_inicio     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    data_fim        TIMESTAMPTZ   NULL,
    valor_reserva   DECIMAL(18,4) NULL,

    CONSTRAINT ck_processo_modo CHECK (
        modo IN ('direto', 'leilao_direto', 'leilao_reverso')
    ),

    CONSTRAINT fk_processo_produto FOREIGN KEY (produto_id)
        REFERENCES portal_b2b.produtos_produto(id)
);

-- ------------------------------------------------------------
-- 9. lance
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.lance (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    processo_id     UUID          NOT NULL,
    empresa_id      UUID          NOT NULL,
    valor_unitario  DECIMAL(18,4) NOT NULL,
    quantidade      DECIMAL(18,4) NOT NULL,
    data_lance      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_lance_valor CHECK (valor_unitario > 0),
    CONSTRAINT ck_lance_qtd   CHECK (quantidade > 0),

    CONSTRAINT fk_lance_processo FOREIGN KEY (processo_id)
        REFERENCES portal_b2b.processo_negociacao(id),

    CONSTRAINT fk_lance_empresa FOREIGN KEY (empresa_id)
        REFERENCES portal_b2b.empresa(id)
);

-- ------------------------------------------------------------
-- 10. pedido
-- frete_selecionado_id adicionado após criação de frete_selecionado
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.pedido (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    processo_id             UUID          NOT NULL,
    empresa_comprador_id    UUID          NOT NULL,
    empresa_fornecedor_id   UUID          NOT NULL,
    fornecimento_id         UUID          NOT NULL,
    frete_selecionado_id    UUID          NULL,
    valor_comissao          DECIMAL(18,4) NULL,
    valor_total             DECIMAL(18,4) NOT NULL,
    status                  VARCHAR(20)   NOT NULL DEFAULT 'PENDENTE',
    data_pedido             TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_pedido_total CHECK (valor_total > 0),

    CONSTRAINT fk_pedido_processo   FOREIGN KEY (processo_id)
        REFERENCES portal_b2b.processo_negociacao(id),

    CONSTRAINT fk_pedido_comprador  FOREIGN KEY (empresa_comprador_id)
        REFERENCES portal_b2b.empresa(id),

    CONSTRAINT fk_pedido_fornecedor FOREIGN KEY (empresa_fornecedor_id)
        REFERENCES portal_b2b.empresa(id),

    CONSTRAINT fk_pedido_fornecimento FOREIGN KEY (fornecimento_id)
        REFERENCES portal_b2b.fornecimento(id)
);

-- ------------------------------------------------------------
-- 11. item_pedido
-- Referencia produtos_produto (pré-existente)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.item_pedido (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    pedido_id       UUID          NOT NULL,
    produto_id      UUID          NOT NULL,
    fornecimento_id UUID          NOT NULL,
    quantidade      DECIMAL(18,4) NOT NULL,
    valor_unitario  DECIMAL(18,4) NOT NULL,

    CONSTRAINT ck_item_qtd   CHECK (quantidade > 0),
    CONSTRAINT ck_item_valor CHECK (valor_unitario > 0),

    CONSTRAINT fk_item_pedido       FOREIGN KEY (pedido_id)
        REFERENCES portal_b2b.pedido(id),

    CONSTRAINT fk_item_produto      FOREIGN KEY (produto_id)
        REFERENCES portal_b2b.produtos_produto(id),

    CONSTRAINT fk_item_fornecimento FOREIGN KEY (fornecimento_id)
        REFERENCES portal_b2b.fornecimento(id)
);

-- ------------------------------------------------------------
-- 12. solicitacao_frete
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.solicitacao_frete (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    pedido_id       UUID        NOT NULL,
    tipo_transporte VARCHAR(50) NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'AGUARDANDO',
    data_criacao    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_solicitacao_pedido FOREIGN KEY (pedido_id)
        REFERENCES portal_b2b.pedido(id)
);

-- ------------------------------------------------------------
-- 13. cotacao_frete
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.cotacao_frete (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitacao_id      UUID          NOT NULL,
    transportadora_id   UUID          NOT NULL,
    valor               DECIMAL(18,4) NOT NULL,
    prazo               INTEGER       NOT NULL,
    data_cotacao        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_cotacao_valor CHECK (valor > 0),
    CONSTRAINT ck_cotacao_prazo CHECK (prazo > 0),

    CONSTRAINT fk_cotacao_solicitacao    FOREIGN KEY (solicitacao_id)
        REFERENCES portal_b2b.solicitacao_frete(id),

    CONSTRAINT fk_cotacao_transportadora FOREIGN KEY (transportadora_id)
        REFERENCES portal_b2b.empresa(id)
);

-- ------------------------------------------------------------
-- 14. frete_selecionado
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.frete_selecionado (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    pedido_id       UUID        NOT NULL,
    cotacao_id      UUID        NOT NULL,
    data_selecao    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_frete_pedido UNIQUE (pedido_id),

    CONSTRAINT fk_frete_pedido  FOREIGN KEY (pedido_id)
        REFERENCES portal_b2b.pedido(id),

    CONSTRAINT fk_frete_cotacao FOREIGN KEY (cotacao_id)
        REFERENCES portal_b2b.cotacao_frete(id)
);

-- ------------------------------------------------------------
-- 15. Fecha referência circular: pedido → frete_selecionado
-- ------------------------------------------------------------
ALTER TABLE portal_b2b.pedido
    DROP CONSTRAINT IF EXISTS fk_pedido_frete;

ALTER TABLE portal_b2b.pedido
    ADD CONSTRAINT fk_pedido_frete
        FOREIGN KEY (frete_selecionado_id)
        REFERENCES portal_b2b.frete_selecionado(id);

-- ------------------------------------------------------------
-- 16. Índices
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_empresa_perfil_perfil_id      ON portal_b2b.empresa_perfil (perfil_id);
CREATE INDEX IF NOT EXISTS ix_usuario_empresa_id            ON portal_b2b.usuario (empresa_id);
CREATE INDEX IF NOT EXISTS ix_endereco_empresa_id           ON portal_b2b.endereco (empresa_id);
CREATE INDEX IF NOT EXISTS ix_fornecimento_empresa_id       ON portal_b2b.fornecimento (empresa_fornecedor_id);
CREATE INDEX IF NOT EXISTS ix_fornecimento_produto_id       ON portal_b2b.fornecimento (produto_id);
CREATE INDEX IF NOT EXISTS ix_demanda_empresa_id            ON portal_b2b.demanda (empresa_comprador_id);
CREATE INDEX IF NOT EXISTS ix_demanda_produto_id            ON portal_b2b.demanda (produto_id);
CREATE INDEX IF NOT EXISTS ix_demanda_status                ON portal_b2b.demanda (status);
CREATE INDEX IF NOT EXISTS ix_processo_produto_id           ON portal_b2b.processo_negociacao (produto_id);
CREATE INDEX IF NOT EXISTS ix_processo_status               ON portal_b2b.processo_negociacao (status);
CREATE INDEX IF NOT EXISTS ix_lance_processo_id             ON portal_b2b.lance (processo_id);
CREATE INDEX IF NOT EXISTS ix_lance_empresa_id              ON portal_b2b.lance (empresa_id);
CREATE INDEX IF NOT EXISTS ix_pedido_comprador_id           ON portal_b2b.pedido (empresa_comprador_id);
CREATE INDEX IF NOT EXISTS ix_pedido_status                 ON portal_b2b.pedido (status);
CREATE INDEX IF NOT EXISTS ix_item_pedido_pedido_id         ON portal_b2b.item_pedido (pedido_id);
CREATE INDEX IF NOT EXISTS ix_solicitacao_pedido_id         ON portal_b2b.solicitacao_frete (pedido_id);
CREATE INDEX IF NOT EXISTS ix_cotacao_solicitacao_id        ON portal_b2b.cotacao_frete (solicitacao_id);

-- ------------------------------------------------------------
-- 17. Ownership
-- ------------------------------------------------------------
ALTER TABLE portal_b2b.perfil               OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.empresa              OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.empresa_perfil       OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.usuario              OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.endereco             OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.fornecimento         OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.demanda              OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.processo_negociacao  OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.lance                OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.pedido               OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.item_pedido          OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.solicitacao_frete    OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.cotacao_frete        OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.frete_selecionado    OWNER TO db_portal_b2b;

-- ------------------------------------------------------------
-- 18. Permissões svc_portal_b2b
-- ------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON
    portal_b2b.perfil,
    portal_b2b.empresa,
    portal_b2b.empresa_perfil,
    portal_b2b.usuario,
    portal_b2b.endereco,
    portal_b2b.fornecimento,
    portal_b2b.demanda,
    portal_b2b.processo_negociacao,
    portal_b2b.lance,
    portal_b2b.pedido,
    portal_b2b.item_pedido,
    portal_b2b.solicitacao_frete,
    portal_b2b.cotacao_frete,
    portal_b2b.frete_selecionado
TO svc_portal_b2b;

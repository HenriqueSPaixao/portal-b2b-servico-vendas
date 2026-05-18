-- ============================================================
-- Migration: Módulo Demanda — Alinhamento com equipe de demanda
-- Schema: portal_b2b
-- Owner: db_portal_b2b
-- ============================================================

-- ------------------------------------------------------------
-- 1. ALTER TABLE demanda
-- ------------------------------------------------------------

-- 1.1 Renomear colunas de ID para padrão id_*
ALTER TABLE portal_b2b.demanda
    RENAME COLUMN empresa_comprador_id TO id_empresa_comprador;

ALTER TABLE portal_b2b.demanda
    RENAME COLUMN produto_id TO id_produto;

ALTER TABLE portal_b2b.demanda
    RENAME COLUMN endereco_destino_id TO id_endereco_destino;

-- 1.2 Adicionar novas colunas
ALTER TABLE portal_b2b.demanda
    ADD COLUMN IF NOT EXISTS id_usuario_criador UUID NULL,
    ADD COLUMN IF NOT EXISTS preco_maximo       DECIMAL(12,2) NULL,
    ADD COLUMN IF NOT EXISTS prioridade         VARCHAR(10) NULL;

-- 1.3 Remover colunas migradas para demanda_recorrencia
ALTER TABLE portal_b2b.demanda
    DROP COLUMN IF EXISTS is_recorrente,
    DROP COLUMN IF EXISTS data_proxima_geracao;

-- ------------------------------------------------------------
-- 2. produto_cache
-- Cache local de produtos no serviço de demanda,
-- sincronizado via evento Kafka a partir do módulo de produtos.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.produto_cache (
    id_produto          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo              VARCHAR(60)  NOT NULL,
    nome                VARCHAR(150) NOT NULL,
    ativo               BOOLEAN      NOT NULL DEFAULT TRUE,
    sincronizado_em     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_produto_cache_codigo UNIQUE (codigo)
);

-- ------------------------------------------------------------
-- 3. endereco_entrega
-- Endereço de entrega mais detalhado, específico do módulo de demanda.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.endereco_entrega (
    id_endereco     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    id_empresa      UUID         NOT NULL,
    logradouro      VARCHAR(200) NOT NULL,
    numero          VARCHAR(20)  NULL,
    complemento     VARCHAR(100) NULL,
    bairro          VARCHAR(100) NULL,
    cidade          VARCHAR(100) NOT NULL,
    estado          CHAR(2)      NOT NULL,
    cep             VARCHAR(9)   NOT NULL,
    latitude        DECIMAL(9,6) NULL,
    longitude       DECIMAL(9,6) NULL,
    ativo           BOOLEAN      NOT NULL DEFAULT TRUE,
    data_cadastro   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ultima_alteracao TIMESTAMPTZ NULL,

    CONSTRAINT fk_endereco_entrega_empresa FOREIGN KEY (id_empresa)
        REFERENCES portal_b2b.empresa(id)
);

-- ------------------------------------------------------------
-- 4. demanda_recorrencia
-- Detalhes de recorrência separados da demanda principal.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.demanda_recorrencia (
    id_recorrencia          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    id_demanda              UUID        NOT NULL,
    frequencia              VARCHAR(10) NOT NULL,  -- ex: DIARIA, SEMANAL, MENSAL
    quantidade_por_periodo  DECIMAL(12,3) NOT NULL,
    data_inicio             DATE        NOT NULL,
    data_fim                DATE        NULL,
    dia_preferencial        VARCHAR(20) NULL,
    ativa                   BOOLEAN     NOT NULL DEFAULT TRUE,
    data_cadastro           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultima_alteracao        TIMESTAMPTZ NULL,

    CONSTRAINT ck_recorrencia_datas CHECK (
        data_fim IS NULL OR data_fim > data_inicio
    ),

    CONSTRAINT fk_recorrencia_demanda FOREIGN KEY (id_demanda)
        REFERENCES portal_b2b.demanda(id)
);

-- ------------------------------------------------------------
-- 5. wishlist_item
-- Lista de desejos — interesse ainda não formalizado como demanda.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_b2b.wishlist_item (
    id_item                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    id_empresa              UUID        NOT NULL,
    id_usuario              UUID        NOT NULL,
    id_produto              UUID        NOT NULL,
    quantidade_desejada     DECIMAL(12,3) NULL,
    preco_maximo            DECIMAL(12,2) NULL,
    prioridade              VARCHAR(10) NULL,
    observacoes             TEXT        NULL,
    convertido_em_demanda   BOOLEAN     NOT NULL DEFAULT FALSE,
    id_demanda_gerada       UUID        NULL,
    data_cadastro           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultima_alteracao        TIMESTAMPTZ NULL,

    CONSTRAINT fk_wishlist_empresa FOREIGN KEY (id_empresa)
        REFERENCES portal_b2b.empresa(id),

    CONSTRAINT fk_wishlist_demanda FOREIGN KEY (id_demanda_gerada)
        REFERENCES portal_b2b.demanda(id)
);

-- ------------------------------------------------------------
-- 6. Índices
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_produto_cache_codigo
    ON portal_b2b.produto_cache (codigo);

CREATE INDEX IF NOT EXISTS ix_endereco_entrega_empresa
    ON portal_b2b.endereco_entrega (id_empresa);

CREATE INDEX IF NOT EXISTS ix_demanda_recorrencia_demanda
    ON portal_b2b.demanda_recorrencia (id_demanda);

CREATE INDEX IF NOT EXISTS ix_wishlist_empresa
    ON portal_b2b.wishlist_item (id_empresa);

CREATE INDEX IF NOT EXISTS ix_wishlist_produto
    ON portal_b2b.wishlist_item (id_produto);

CREATE INDEX IF NOT EXISTS ix_demanda_id_produto
    ON portal_b2b.demanda (id_produto);

CREATE INDEX IF NOT EXISTS ix_demanda_id_empresa_comprador
    ON portal_b2b.demanda (id_empresa_comprador);

-- ------------------------------------------------------------
-- 7. Ownership
-- ------------------------------------------------------------
ALTER TABLE portal_b2b.produto_cache       OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.endereco_entrega    OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.demanda_recorrencia OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.wishlist_item       OWNER TO db_portal_b2b;

-- ------------------------------------------------------------
-- 8. Permissões svc_portal_b2b
-- ------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON
    portal_b2b.produto_cache,
    portal_b2b.endereco_entrega,
    portal_b2b.demanda_recorrencia,
    portal_b2b.wishlist_item
TO svc_portal_b2b;

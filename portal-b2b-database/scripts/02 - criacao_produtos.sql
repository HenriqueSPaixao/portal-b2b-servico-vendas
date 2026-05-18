CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS portal_b2b;

CREATE OR REPLACE FUNCTION portal_b2b.fn_produtos_atualizar_ultima_alteracao()
RETURNS TRIGGER AS $$
BEGIN
    NEW.ultima_alteracao = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS portal_b2b.produtos_transporte (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    nome VARCHAR(150) NOT NULL,
    descricao VARCHAR(500) NULL,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    data_cadastro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario_cadastro UUID NULL,

    ultima_alteracao TIMESTAMPTZ NULL,
    usuario_alteracao UUID NULL
);

CREATE TABLE IF NOT EXISTS portal_b2b.produtos_categoria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    categoria_pai_id UUID NULL,

    nome VARCHAR(150) NOT NULL,
    descricao VARCHAR(500) NULL,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    data_cadastro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario_cadastro UUID NULL,

    ultima_alteracao TIMESTAMPTZ NULL,
    usuario_alteracao UUID NULL,

    CONSTRAINT fk_categoria_categoria_pai
        FOREIGN KEY (categoria_pai_id)
        REFERENCES portal_b2b.produtos_categoria(id)
);

CREATE TABLE IF NOT EXISTS portal_b2b.produtos_unidade_medida (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    nome VARCHAR(150) NOT NULL,
    sigla VARCHAR(20) NOT NULL,
    descricao VARCHAR(500) NULL,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    data_cadastro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario_cadastro UUID NULL,

    ultima_alteracao TIMESTAMPTZ NULL,
    usuario_alteracao UUID NULL
);

CREATE TABLE IF NOT EXISTS portal_b2b.produtos_produto (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    transporte_id UUID NOT NULL,
    categoria_id UUID NOT NULL,
    unidade_medida_id UUID NOT NULL,

    codigo VARCHAR(60) NOT NULL,

    nome VARCHAR(150) NOT NULL,
    descricao VARCHAR(1000) NULL,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    data_cadastro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario_cadastro UUID NULL,

    ultima_alteracao TIMESTAMPTZ NULL,
    usuario_alteracao UUID NULL,

    CONSTRAINT fk_produto_transporte
        FOREIGN KEY (transporte_id)
        REFERENCES portal_b2b.produtos_transporte(id),

    CONSTRAINT fk_produto_categoria
        FOREIGN KEY (categoria_id)
        REFERENCES portal_b2b.produtos_categoria(id),

    CONSTRAINT fk_produto_unidade_medida
        FOREIGN KEY (unidade_medida_id)
        REFERENCES portal_b2b.produtos_unidade_medida(id)
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_produto_quantidade_total'
    ) THEN
        ALTER TABLE portal_b2b.produtos_produto
        DROP CONSTRAINT ck_produto_quantidade_total;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_produto_preco'
    ) THEN
        ALTER TABLE portal_b2b.produtos_produto
        DROP CONSTRAINT ck_produto_preco;
    END IF;
END;
$$;

ALTER TABLE portal_b2b.produtos_produto
DROP COLUMN IF EXISTS preco;

ALTER TABLE portal_b2b.produtos_produto
DROP COLUMN IF EXISTS quantidade_total;

CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_transporte_nome
ON portal_b2b.produtos_transporte (LOWER(nome));

CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_categoria_nome
ON portal_b2b.produtos_categoria (LOWER(nome));

CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_unidade_medida_nome
ON portal_b2b.produtos_unidade_medida (LOWER(nome));

CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_unidade_medida_sigla
ON portal_b2b.produtos_unidade_medida (LOWER(sigla));

CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_produto_codigo
ON portal_b2b.produtos_produto (LOWER(codigo));

CREATE INDEX IF NOT EXISTS ix_produtos_categoria_categoria_pai_id
ON portal_b2b.produtos_categoria (categoria_pai_id);

CREATE INDEX IF NOT EXISTS ix_produtos_produto_transporte_id
ON portal_b2b.produtos_produto (transporte_id);

CREATE INDEX IF NOT EXISTS ix_produtos_produto_categoria_id
ON portal_b2b.produtos_produto (categoria_id);

CREATE INDEX IF NOT EXISTS ix_produtos_produto_unidade_medida_id
ON portal_b2b.produtos_produto (unidade_medida_id);

CREATE INDEX IF NOT EXISTS ix_produtos_produto_nome
ON portal_b2b.produtos_produto (nome);

DROP TRIGGER IF EXISTS trg_transporte_ultima_alteracao 
ON portal_b2b.produtos_transporte;

CREATE TRIGGER trg_transporte_ultima_alteracao
BEFORE UPDATE ON portal_b2b.produtos_transporte
FOR EACH ROW
EXECUTE FUNCTION portal_b2b.fn_produtos_atualizar_ultima_alteracao();

DROP TRIGGER IF EXISTS trg_categoria_ultima_alteracao 
ON portal_b2b.produtos_categoria;

CREATE TRIGGER trg_categoria_ultima_alteracao
BEFORE UPDATE ON portal_b2b.produtos_categoria
FOR EACH ROW
EXECUTE FUNCTION portal_b2b.fn_produtos_atualizar_ultima_alteracao();

DROP TRIGGER IF EXISTS trg_unidade_medida_ultima_alteracao 
ON portal_b2b.produtos_unidade_medida;

CREATE TRIGGER trg_unidade_medida_ultima_alteracao
BEFORE UPDATE ON portal_b2b.produtos_unidade_medida
FOR EACH ROW
EXECUTE FUNCTION portal_b2b.fn_produtos_atualizar_ultima_alteracao();

DROP TRIGGER IF EXISTS trg_produto_ultima_alteracao 
ON portal_b2b.produtos_produto;

CREATE TRIGGER trg_produto_ultima_alteracao
BEFORE UPDATE ON portal_b2b.produtos_produto
FOR EACH ROW
EXECUTE FUNCTION portal_b2b.fn_produtos_atualizar_ultima_alteracao();

GRANT USAGE ON SCHEMA portal_b2b TO svc_portal_b2b;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    portal_b2b.produtos_transporte,
    portal_b2b.produtos_categoria,
    portal_b2b.produtos_unidade_medida,
    portal_b2b.produtos_produto
TO svc_portal_b2b;

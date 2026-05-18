ALTER TABLE portal_b2b.demanda
    ADD COLUMN IF NOT EXISTS is_recorrente BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS observacoes   TEXT NULL;

-- Renomear PK para id_demanda
ALTER TABLE portal_b2b.demanda
    RENAME COLUMN id TO id_demanda;

-- Adicionar colunas faltantes
ALTER TABLE portal_b2b.demanda
    ADD COLUMN IF NOT EXISTS ultima_alteracao     TIMESTAMPTZ NULL;

ALTER TABLE portal_b2b.demanda
    DROP COLUMN IF EXISTS data_proxima_geracao;


ALTER TABLE portal_b2b.demanda
    RENAME COLUMN data_cadastro    TO data_criacao;
ALTER TABLE portal_b2b.demanda
    RENAME COLUMN ultima_alteracao TO atualizado_em;

ALTER TABLE portal_b2b.endereco_entrega
    RENAME COLUMN data_cadastro    TO data_criacao;
ALTER TABLE portal_b2b.endereco_entrega
    RENAME COLUMN ultima_alteracao TO atualizado_em;

ALTER TABLE portal_b2b.demanda_recorrencia
    RENAME COLUMN data_cadastro    TO data_criacao;
ALTER TABLE portal_b2b.demanda_recorrencia
    RENAME COLUMN ultima_alteracao TO atualizado_em;

ALTER TABLE portal_b2b.wishlist_item
    RENAME COLUMN data_cadastro    TO data_criacao;
ALTER TABLE portal_b2b.wishlist_item
    RENAME COLUMN ultima_alteracao TO atualizado_em;

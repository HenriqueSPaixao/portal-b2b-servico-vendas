-- Atualiza FK id_endereco_destino para referenciar endereco_entrega
ALTER TABLE portal_b2b.demanda
    DROP CONSTRAINT IF EXISTS fk_demanda_endereco;

ALTER TABLE portal_b2b.demanda
    ADD CONSTRAINT fk_demanda_endereco_entrega
        FOREIGN KEY (id_endereco_destino)
        REFERENCES portal_b2b.endereco_entrega(id_endereco);

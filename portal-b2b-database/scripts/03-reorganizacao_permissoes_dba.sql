-- 1. Garante que o schema pertence ao administrador de BD
ALTER SCHEMA portal_b2b OWNER TO db_portal_b2b;

-- 2. Revoga qualquer permissão de CREATE no schema para o usuário de aplicação
-- Isso impede que os microsserviços criem tabelas ou funções por conta própria
REVOKE CREATE ON SCHEMA portal_b2b FROM svc_portal_b2b;

-- 3. Reafirma as permissões de dados para a aplicação (Apenas DML)
GRANT USAGE ON SCHEMA portal_b2b TO svc_portal_b2b;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA portal_b2b TO svc_portal_b2b;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA portal_b2b TO svc_portal_b2b;

-- 4. Garante que tabelas futuras sigam a mesma regra automaticamente
ALTER DEFAULT PRIVILEGES IN SCHEMA portal_b2b REVOKE ALL ON TABLES FROM svc_portal_b2b;
ALTER DEFAULT PRIVILEGES IN SCHEMA portal_b2b GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO svc_portal_b2b;

-- 5. Atualiza a busca (search_path) para ninguém precisar ficar escrevendo 'portal_b2b.' toda hora
ALTER ROLE db_portal_b2b SET search_path TO portal_b2b, public;
ALTER ROLE svc_portal_b2b SET search_path TO portal_b2b, public;

-- 6. Organiza a casa: Ajusta o OWNER das tabelas já criadas
ALTER TABLE portal_b2b.produtos_transporte OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.produtos_categoria OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.produtos_unidade_medida OWNER TO db_portal_b2b;
ALTER TABLE portal_b2b.produtos_produto OWNER TO db_portal_b2b;
ALTER FUNCTION portal_b2b.fn_produtos_atualizar_ultima_alteracao() OWNER TO db_portal_b2b;

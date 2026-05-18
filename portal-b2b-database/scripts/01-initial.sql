-- Criar schema único
CREATE SCHEMA IF NOT EXISTS portal_b2b;

-- Criar usuários (idempotente)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_portal_b2b') THEN
        CREATE ROLE db_portal_b2b WITH LOGIN PASSWORD '****************';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_portal_b2b') THEN
        CREATE ROLE svc_portal_b2b WITH LOGIN PASSWORD 'senha_portal_b2b';
    END IF;
END $$;

-- Permissões do schema
GRANT CONNECT ON DATABASE portal_b2b TO db_portal_b2b;
GRANT CONNECT ON DATABASE portal_b2b TO svc_portal_b2b;
GRANT USAGE, CREATE ON SCHEMA portal_b2b TO db_portal_b2b;
GRANT USAGE ON SCHEMA portal_b2b TO svc_portal_b2b;

-- Definir search_path padrão
ALTER ROLE db_portal_b2b SET search_path TO portal_b2b;
ALTER ROLE svc_portal_b2b SET search_path TO portal_b2b;

-- Permissões explícitas em objetos atuais e futuros
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA portal_b2b TO db_portal_b2b;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA portal_b2b TO db_portal_b2b;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA portal_b2b TO svc_portal_b2b;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA portal_b2b TO svc_portal_b2b;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA portal_b2b 
GRANT ALL PRIVILEGES ON TABLES TO db_portal_b2b;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA portal_b2b 
GRANT ALL PRIVILEGES ON SEQUENCES TO db_portal_b2b;

ALTER DEFAULT PRIVILEGES FOR ROLE db_portal_b2b IN SCHEMA portal_b2b
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO svc_portal_b2b;

ALTER DEFAULT PRIVILEGES FOR ROLE db_portal_b2b IN SCHEMA portal_b2b
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO svc_portal_b2b;

-- Criar tabela de health check e inserir registros
CREATE TABLE IF NOT EXISTS portal_b2b.health_check (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inserir registros para os serviços (idempotente)
INSERT INTO portal_b2b.health_check (service_name)
SELECT 'infra-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'infra-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'usuarios-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'usuarios-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'produtos-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'produtos-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'fornecimentos-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'fornecimentos-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'demanda-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'demanda-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'mercado-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'mercado-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'negociacao-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'negociacao-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'pedidos-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'pedidos-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'logistica-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'logistica-service');

INSERT INTO portal_b2b.health_check (service_name)
SELECT 'transportadoras-service'
WHERE NOT EXISTS (SELECT 1 FROM portal_b2b.health_check WHERE service_name = 'transportadoras-service');

-- Garantir privilégios na tabela health_check (e em possíveis tabelas recriadas)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA portal_b2b TO db_portal_b2b;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA portal_b2b TO db_portal_b2b;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA portal_b2b TO svc_portal_b2b;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA portal_b2b TO svc_portal_b2b;

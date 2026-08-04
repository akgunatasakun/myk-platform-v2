-- PostgreSQL başlangıç scripti — Docker ilk çalıştırmada bir kez yürütülür.
-- Bu script yalnızca temel uzantıları ve rol/veritabanı hazırlığını yapar.
-- Tablo oluşturma Alembic migration'larına bırakılır.

\c myk_v2;

-- Zorunlu uzantılar
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- AES-256 şifreleme (TC no, sağlık verileri)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Trigram arama (tam metin)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- uuid_generate_v4() (SQLAlchemy fallback)

-- Uygulama rolü (docker-compose.yml'den gelir, burada yoksa oluştur)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'myk_app') THEN
        CREATE ROLE myk_app WITH LOGIN PASSWORD 'change_in_production';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE myk_v2 TO myk_app;
GRANT USAGE ON SCHEMA public TO myk_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO myk_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO myk_app;

-- Audit log'u sadece INSERT yetkisi ile kısıtla (UPDATE/DELETE yasak)
-- Bu kısıtlama servis katmanında da uygulanır; burada ekstra güvence.
-- Not: Tablo Alembic tarafından oluşturulduktan sonra aşağıdaki blok uygulanır.
-- docker-entrypoint-initdb.d/ içine 02_audit_revoke.sql olarak ekleyebilirsin:
--
-- REVOKE UPDATE, DELETE ON audit_logs FROM myk_app;

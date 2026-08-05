-- PostgreSQL başlangıç scripti — Docker ilk çalıştırmada bir kez yürütülür.
-- Bu script yalnızca temel uzantıları ve rol/veritabanı hazırlığını yapar.
-- Tablo oluşturma Alembic migration'larına bırakılır.
--
-- NOT: \c komutu YOKTUR — Docker entrypoint bu scripti zaten POSTGRES_DB'ye
-- bağlı olarak çalıştırır. Sabit DB adı yazmak production'da farklı isimlerle
-- uzantıların yanlış DB'ye kurulmasına yol açar.

-- Zorunlu uzantılar (POSTGRES_DB bağlamında çalışır)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- AES-256 şifreleme (TC no, sağlık verileri)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Trigram arama (tam metin)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- uuid_generate_v4() (SQLAlchemy fallback)

-- Uygulama rolü
-- UYARI: Parola burada sabittir. Gerçek ortamda 02_app_role.sh ile
-- APP_DB_PASSWORD env değişkeninden okunmalıdır.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'myk_app') THEN
        CREATE ROLE myk_app WITH LOGIN PASSWORD 'change_in_production';
    END IF;
END
$$;

-- GRANT CONNECT: sabit DB adı yerine dinamik fonksiyon kullan
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO myk_app', current_database());
END
$$;

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

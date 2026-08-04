# MYK Platform V2

**Mersin Yelken Kulübü Dijital Yönetim Sistemi — V2**

FastAPI + React + TypeScript + PostgreSQL + Redis + Docker mimarisiyle sıfırdan yazılmış çok kiracılı (multi-tenant) kulüp yönetim platformu.

---

## Gereksinimler

| Araç | Minimum Sürüm | Notlar |
|---|---|---|
| Docker | 24.x | `docker compose` v2 dahil |
| Docker Compose | 2.x | `docker compose` komutu (tire yok) |
| Python | 3.12 | Yalnızca lokal geliştirme için |
| Node.js | 22.x | Yalnızca frontend geliştirme için |
| PostgreSQL | 16 (Docker) | Üretim DB için harici de kullanılabilir |
| Redis | 7 (Docker) | Rate limit + session |

---

## Ortam Değişkenleri

Kök dizindeki `.env.example` dosyasını kopyalayarak `.env` oluşturun (Docker Compose kök dizindeki `.env`'i kullanır):

```bash
cp .env.example .env
```

**Kritik değişkenler:**

```
DATABASE_URL=postgresql+asyncpg://myk_user:şifre@db:5432/myk_v2
REDIS_URL=redis://redis:6379/0
JWT_SECRET_KEY=<en az 32 karakter rastgele string>
MYK_ENV=development   # production | development | test
INITIAL_ADMIN_EMAIL=admin@kulup.com
INITIAL_ADMIN_PASSWORD=<güçlü parola>
```

`.env` asla git'e eklenmez, asla deploy paketine dahil edilmez.

---

## Docker ile Çalıştırma (Önerilen)

```bash
# 1. Ortam dosyasını oluştur
cp .env.example .env
# .env içini gerçek değerlerle doldur

# 2. Tüm servisleri başlat
docker compose up -d

# 3. Migration uygula
docker compose exec api alembic -c migrations/alembic.ini upgrade head

# 4. Sağlık kontrolü
curl http://localhost/api/v1/health

# 5. İlk kulüp ve yönetici oluştur (setup endpoint)
curl -X POST http://localhost/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"club_name":"Mersin Yelken Kulübü","club_slug":"mersin-yelken","admin_email":"admin@kulup.com","admin_password":"GüçlüParola1!","admin_full_name":"Sistem Yöneticisi"}'
```

---

## Development (Docker olmadan)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql+asyncpg://myk_user:şifre@localhost:5432/myk_v2"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="dev-secret-32chars-minimum-xxxxx"
export MYK_ENV="development"

# Migration
alembic -c migrations/alembic.ini upgrade head

# Sunucu
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

---

## Migration İşlemleri

```bash
# Tüm migration'ları uygula
docker compose exec api alembic -c migrations/alembic.ini upgrade head

# Bir adım geri al
docker compose exec api alembic -c migrations/alembic.ini downgrade -1

# Migration durumunu görüntüle
docker compose exec api alembic -c migrations/alembic.ini current

# Yeni migration oluştur (sonraki geliştirme sprintlerinde)
docker compose exec api alembic -c migrations/alembic.ini revision --autogenerate -m "aciklama"
```

---

## İlk Yönetici Oluşturma

İki yöntem:

**1. Setup endpoint (geliştirme):**
```bash
curl -X POST http://localhost/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "club_name": "Mersin Yelken",
    "club_slug": "mersin-yelken",
    "admin_email": "admin@kulup.com",
    "admin_password": "GüçlüParola1!",
    "admin_full_name": "Yönetici"
  }'
```

**2. Ortam değişkeni (üretim — Aşama 3'te):**
```
INITIAL_ADMIN_EMAIL=admin@kulup.com
INITIAL_ADMIN_PASSWORD=GüçlüParola1!
```

---

## Test Çalıştırma

```bash
cd backend

# SQLite ile (hızlı, Docker gerektirmez)
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="test-secret-32chars-minimum-here!"
export MYK_ENV="test"
pytest tests/ -v

# Coverage ile
pip install pytest-cov
pytest tests/ --cov=app --cov-report=html --cov-report=xml -v

# PostgreSQL ile (Docker gerektirir)
docker compose up db redis -d
export DATABASE_URL="postgresql+asyncpg://myk_user:şifre@localhost:5432/myk_v2"
pytest tests/ -v
```

> **Not:** SQLite testleri RBAC, tenant izolasyonu ve auth akışlarını doğrular.
> PostgreSQL'e özgü davranışlar (pgcrypto, JSONB operatörleri, concurrency) Aşama 3 sprint testlerinde doğrulanacaktır.

---

## Frontend Build

```bash
cd frontend
npm install
npm run type-check   # TypeScript hata kontrolü
npm run lint         # ESLint
npm run build        # dist/ klasörü oluşturulur
```

---

## Log Görüntüleme

```bash
# Tüm servisler
docker compose logs -f

# Yalnızca backend
docker compose logs -f api

# Yalnızca PostgreSQL
docker compose logs -f db

# Son 100 satır
docker compose logs --tail=100
```

---

## Yedek ve Geri Yükleme

```bash
# Yedek al
docker compose exec db pg_dump -U myk_user myk_v2 > backup_$(date +%Y%m%d).sql

# Geri yükle (ÖNEMLİ: production DB'ye doğrudan bağlanma)
docker compose exec -T db psql -U myk_user myk_v2 < backup_20260730.sql
```

---

## Sistemi Kapatma

```bash
# Servisleri durdur (veriler korunur)
docker compose stop

# Servisleri durdur ve container'ları sil (veriler korunur)
docker compose down

# Tam temizlik — TÜM VERİ SİLİNİR
docker compose down -v
```

---

## Temiz Kurulum

```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
docker compose exec api alembic -c migrations/alembic.ini upgrade head
```

---

## Bilinen Eksikler (Aşama 2 → Aşama 3)

| Eksik | Sprint | Not |
|---|---|---|
| PostgreSQL'e özgü E2E testleri | Sprint 3.1 | pgcrypto, JSONB operatörleri |
| TC kimlik şifreleme (pgcrypto AES-256) | Sprint 3.2 | Veri modeli hazır |
| MFA (TOTP) altyapısı | Sprint 3.3 | — |
| Celery (arka plan görevler) | Aşama 3 | Redis bağlantısı hazır |
| S3 / dosya depolama | Aşama 3 | — |
| Sporcu profil modülü | Sprint 3.4 | Veri modeli Faz 1'de tanımlandı |
| DMS import (317 belge) | Sprint 4 | scripts/import_docs.py tasarlandı |
| TYF/ISAF entegrasyonu | Aşama 4 | — |
| Super Admin paneli | Aşama 3 | — |
| Production Nginx SSL | Aşama 6 | Let's Encrypt hazır |

---

## API Dokümantasyonu

Geliştirme ortamında: `http://localhost/api/docs` (Swagger UI)

Üretimde: docs_url devre dışı (güvenlik).

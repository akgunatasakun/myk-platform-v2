# CHANGELOG — MYK Platform V2

Tüm önemli değişiklikler bu dosyada belgelenir.
Format: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) — [Semantic Versioning](https://semver.org/)

---

## [0.4.0-beta1] — 2026-08-04 — Sprint 3.2: Object Storage, Avatar, Üyelik Başvurusu (MEVCUT)

### Eklendi

**Object Storage altyapısı:**
- `ObjectStorageService` soyut arayüzü (upload/delete/exists/copy/presigned_url/batch)
- `MinioStorageService` implementasyonu (`miniopy-async`)
- `InMemoryStorageService` test mock'u
- MinIO servisi docker-compose'a eklendi (staging: `127.0.0.1:9001` console)

**Avatar yönetimi:**
- `POST /api/v1/persons/{id}/avatar` — magic bytes MIME doğrulama, Pillow EXIF düzeltme, WebP dönüşüm, arşivleme
- `DELETE /api/v1/persons/{id}/avatar` — idempotent, 204
- `GET /api/v1/persons/{id}/avatar-url` — 3600s pre-signed URL
- `PersonAvatarOut` şeması: `has_avatar`, `avatar_url`, `expires_in`
- `PersonListOut` N+1 fix: `presigned_url_batch` ile tek storage çağrısı

**Üyelik başvurusu CRUD:**
- `POST /api/v1/membership-applications` — draft oluşturma
- `GET /api/v1/membership-applications` — listeleme (status filtresi)
- `GET/PATCH/DELETE /api/v1/membership-applications/{id}`
- `PATCH /api/v1/membership-applications/{id}/status` — durum geçiş matrisi
- Durum akışı: `draft → submitted → approved/rejected`, `rejected → draft`, `cancelled` terminal

**Üyelik PDF + imza:**
- `POST /api/v1/membership-applications/{id}/generate-pdf` — WeasyPrint'e HTTP çağrısı, storage'a yükleme
- `GET /api/v1/membership-applications/{id}/pdf-url` — 900s pre-signed URL
- `POST/DELETE/GET /api/v1/membership-applications/{id}/signature` — imza upload/silme/URL

**pdf-service container:**
- Ayrı `pdf-service/` dizini: Dockerfile, FastAPI, WeasyPrint, Jinja2 template
- `GET /health` + `POST /render/membership-application`
- Ana API image'ına WeasyPrint bağımlılığı eklenmedi (tasarım gereği)
- Docker iç ağda yalnızca `api → pdf-service:8001`; host'a port yayımlanmıyor

**Migrations:**
- `0003_avatar_membership`: `avatar_url → avatar_object_key`, `sports_branches`, `membership_applications` (ilk şema)
- `0004_membership_full`: tam alan seti, `application_counters` tablosu (atomic upsert)

**Güvenlik & RBAC:**
- `application_number`: `INSERT ... ON CONFLICT DO UPDATE RETURNING` — yarış koşuluna dayanıklı, PostgreSQL + SQLite 3.24+
- `kisi:approve` yetkisi: `submitted → approved/rejected` geçişlerini kısıtlar
- Cross-tenant: tüm sorgularda `club_id` WHERE koşulu
- Storage path formatı: `clubs/{club_id}/...` — tenant izolasyonu garantili

**Staging doğrulama:**
- `scripts/staging_integration_verify.py` — concurrent sayaç, cross-tenant, key sızıntı testleri
- `scripts/run_sprint32_verify.sh` — wrapper: servis ön kontrolü, gizli token girişi, özetli çıktı, exit 0/1

### Değiştirildi

- `PersonOut`: `avatar_url` alanı kaldırıldı, `has_avatar: bool` + `avatar_url: Optional[str]` (runtime doldurulur) eklendi
- `PersonOut`: `avatar_object_key` hiçbir zaman API response'ına dahil edilmez
- `MembershipApplicationOut`: `pdf_object_key`, `signature_object_key` hiçbir zaman API response'ına dahil edilmez; bunun yerine `has_pdf`, `has_signature`, `pdf_url`, `signature_url`
- `docker-compose.yml`: MinIO + pdf-service servisleri eklendi; api `depends_on` zinciri güncellendi

### Güvenlik

- Storage key'leri (`*_object_key`) hiçbir API response'ında yer almaz
- Pre-signed URL'ler: avatar 3600s, PDF/imza 900s; sonrası erişilemez
- Audit log: `after` bloğuna storage key veya bucket adı yazılmaz
- pdf-service'e doğrudan dış erişim yok (port yayımlanmıyor)

### Test

- `tests/test_storage.py`: 9 test (InMemoryStorageService)
- `tests/test_migration_0003.py`: 7 test
- `tests/test_avatar.py`: 16 test (AV-01..16)
- `tests/test_membership_applications.py`: 22 test (MA-01..22)
- **Toplam: 107/107 ✅**

---

## [2.0.0-alpha.4] — 2026-07-30 — Aşama 2.2 Güvenlik ve Teslimat Hijyeni

### Düzeltildi

**Güvenlik sıkılaştırma:**
- `config.py`: Production ortamında `ALLOW_PUBLIC_SETUP=true` artık `ValueError` fırlatıyor
- `auth.py` setup endpoint: Production + kulüp_var → her koşulda 403, `allow_public_setup` ignored
- `enforce_production_secrets` validator'a `allow_public_setup` production kontrolü eklendi
- Yeni test: `test_production_allow_public_setup_rejected`, `test_production_setup_always_denied_when_club_exists`

**Deployment dosyaları:**
- `.env.production.example` eklendi (MYK_ENV=production, production-safe placeholders)
- `docker-compose.prod.yml` eklendi (MYK_ENV production'da açıkça set, no dev volumes)

**Teslimat hijyeni:**
- `.gitignore` güncellendi: `.DS_Store`, `.coverage`, `.coverage.*`, `htmlcov/` eklendi
- `PHASE2_FILE_MANIFEST.csv` kendi kendini artık hash'lemiyor
- `PHASE2_FILE_MANIFEST.sha256` ayrı dosya olarak eklendi
- Geçici `.coverage.*` process dosyaları repoya eklenmemelidir

---

## [2.0.0-alpha.3] — 2026-07-30 — Aşama 2.1 Bağımsız İnceleme Düzeltmeleri

### Düzeltildi

**11 bağımsız inceleme bulgusu kapatıldı:**
- Dockerfile `dev` stage eklendi (port 5173)
- `package-lock.json` üretildi ve eklendi
- `eslint.config.js` flat config (ESLint 9, typescript-eslint v8): 0 hata, 0 uyarı
- Nginx `/etc/nginx/nginx.conf:ro` olarak mount edildi
- Nginx upstream frontend:5173 (3000'den düzeltildi)
- `DATABASE_URL` docker-compose `environment` bloğunda açıkça oluşturuluyor
- README.md `.env` path talimatı `cp .env.example .env` olarak düzeltildi
- `config.py`: `allow_public_setup: bool = True` field eklendi
- `config.py`: `model_validator(mode="after")` → production'da zayıf/kısa secret `ValueError`
- CONFLICT-001: faz1/02, 03, 08 belgelerindeki hukuki blokaj ifadeleri temizlendi
- TEST_REPORT.md: Docker/PG/Redis/Nginx `⚠️ PENDING EXTERNAL VERIFICATION` olarak düzeltildi

**Yeni testler (5):**
- `test_setup_blocked_when_club_exists_and_not_allowed`
- `test_setup_allowed_when_public_setup_enabled`
- `test_production_secret_validation`
- `test_production_short_secret_rejected`
- `test_development_weak_secret_allowed`

**Toplam: 33/33 test PASS, %78 coverage**

---

## [2.0.0-alpha.2] — 2026-07-30 — Aşama 2 İskeleti

### Eklendi

**Backend altyapısı:**
- FastAPI 0.115 + Uvicorn + Python 3.12 iskelet
- SQLAlchemy 2 async engine (PostgreSQL 16 + SQLite test modu)
- Alembic async migration altyapısı (`migrations/env.py`, `0001_initial_schema`)
- Pydantic v2 + pydantic-settings konfigürasyon yönetimi
- Argon2id parola hashleme (time_cost=2, memory=65536 KB)
- JWT erişim tokeni (15 dk) + yenileme tokeni (7 gün, token rotation)
- HttpOnly cookie + Bearer header çift destek
- Redis tabanlı rate limiter (15 dk pencere, 10 deneme)
- 16 rol RBAC sistemi (wildcard, namespace wildcard, own-scope)
- Multi-tenant izolasyon — `club_id` (UUID) her kayıtta zorunlu
- Audit log (değiştirilemez INSERT-only kayıt)
- Hassas alan maskeleme (SENSITIVE_FIELD_MASK_ROLES)
- Health check endpoint (PostgreSQL + Redis)
- PostgreSQL pgcrypto, pg_trgm, uuid-ossp uzantıları (migration 0001)

**Veritabanı modelleri:**
- `clubs` — kulüp/tenant kaydı (slug, plan, settings JSONB)
- `users` — kullanıcı (email, password_hash, role, is_deleted soft-delete)
- `refresh_tokens` — yenileme tokenleri (token_hash SHA-256, revoked_at)
- `audit_logs` — denetim günlüğü (action, changes JSONB, ip_address)

**Auth endpoint'leri (`/api/v1/auth/`):**
- `POST /login` — rate limit + Argon2id doğrulama + token üretme
- `POST /refresh` — token rotation ile yenileme
- `POST /logout` — refresh token iptali + cookie temizleme
- `GET /me` — mevcut kullanıcı bilgisi
- `POST /setup` — ilk kulüp + yönetici kurulumu

**Frontend iskeleti:**
- React 18 + TypeScript + Vite 6 + PWA
- Zustand auth store (token in-memory, localStorage kullanılmıyor)
- Axios interceptor ile otomatik token yenileme
- Login sayfası (club_slug + email + password)
- Protected route (yetkisiz erişim → /login)
- `types/auth.ts` — 16 rol tipi tanımı
- Dockerfile (multi-stage: Node build → Nginx serve)

**Altyapı:**
- Docker Compose (db, redis, api, frontend, nginx servisleri)
- Nginx reverse proxy (rate limit, güvenlik başlıkları, SPA routing)
- PostgreSQL init.sql (pgcrypto + uygulama rolü)
- `.env.example` tam şablon

**Test altyapısı:**
- pytest-asyncio + httpx ASGITransport
- `tests/conftest.py` — in-memory SQLite fixture'ları
- `tests/test_auth.py` — 15 test (login, logout, refresh, /me, setup, güvenlik)
- `tests/test_rbac.py` — 14 test (izin matrisi, maskeleme)
- `tests/test_tenant.py` — 4 test (çapraz tenant koruması)
- **33/33 test PASS** (Aşama 2.1'de 5 yeni güvenlik testi eklendi)

**Dokümantasyon:**
- `README.md` — tam kurulum ve çalıştırma talimatları
- `ARCHITECTURE.md` — istek akışı, tenant izolasyonu, RBAC, audit log
- `CHANGELOG.md` (bu dosya)

### Düzeltildi

**Faz 1 CONFLICT-001 düzeltmeleri (7 dosya):**
- `03_TEKRAR_CAKISMA_RAPORU.md` — R01 "kritik hukuki engel" → "iç prosedür konsolidasyonu"
- `04_ANA_SUREC_LISTESI.md` — C.5/C.6 MVP* (kilitli) → MVP (yapılandırılabilir)
- `05_PROSEDUR_LISTESI.md` — PRO-C-004 yeniden yazıldı; PRO-D-003 force=True blokajı kaldırıldı
- `07_MVP_KAPSAMI.md` — "CONFLICT-001 kilidi → force=True dahil geçilemez" kaldırıldı
- `08_FAZ2_KAPSAMI.md` — CONFLICT-001 blokajı kaldırıldı
- `09_RISK_LISTESI.md` — R01: 🔴 KRİTİK → 🟡 ORTA; hukuki/Liman gerekliliği kaldırıldı
- `10_GELISTIRME_YOL_HARITASI.md` — Faz 2 giriş kriteri güncellendi; CONFLICT-001 kilidi kaldırıldı

**Model düzeltmeleri:**
- PostgreSQL `JSONB` / `UUID` → diyalekt-agnostik `JSON` / `sa.Uuid` (SQLite test uyumluluğu)
- `database.py` — SQLite'de `pool_size`/`max_overflow` hatası giderildi
- Test fixture'larında slug çakışması — benzersiz slug ile düzeltildi
- `setup` endpoint `created_at` None hatası — `commit()` + `refresh()` eklendi
- `auth.py` içindeki çift `/me` endpoint çakışması kaldırıldı

### Notlar

- SQLite testleri hızlı birim testleri içindir; pgcrypto, JSONB operatörleri ve concurrency davranışları PostgreSQL ortamında test edilecektir (Aşama 3 Sprint 3.1)
- TC kimlik ve sağlık verisi şifrelemesi (pgcrypto AES-256) veri modeli hazır, Aşama 3'te aktive edilecek
- `force=True` dahil CONFLICT-001 sert blokajı sistemin hiçbir katmanında YOKTUR

---

## [2.0.0-alpha.1] — 2026-07-28 — Aşama 1 (Analiz ve Planlama)

### Eklendi

10 analiz ve planlama belgesi (`faz1/` klasörü):

| Dosya | İçerik |
|---|---|
| `01_TEKNIK_DENETIM_RAPORU.md` | V1 Flask sistemi teknik denetimi |
| `02_DOKUMAN_ENVANTERI.md` | 317 belge üç katman envanteri |
| `03_TEKRAR_CAKISMA_RAPORU.md` | CONFLICT-001 analizi + çözüm stratejisi |
| `04_ANA_SUREC_LISTESI.md` | 6 ana süreç, 31 alt süreç |
| `05_PROSEDUR_LISTESI.md` | PRO-A-001'den PRO-G-003'e 40+ prosedür |
| `06_VERI_MODELI.md` | PostgreSQL şeması, 9 entity grubu |
| `07_MVP_KAPSAMI.md` | 12 MVP modülü, sprint planı |
| `08_FAZ2_KAPSAMI.md` | Faz 2 kapsamı (Yarış, MFA, Celery, S3...) |
| `09_RISK_LISTESI.md` | R01-R12 risk matrisi |
| `10_GELISTIRME_YOL_HARITASI.md` | 6 aşama, sprint bazlı yol haritası |

---

## [1.0.0] — 2026-07-01 — MYK_Yazilim (V1 Referans)

Flask 2.3 + SQLite + Alembic (9 migration) tabanlı orijinal sistem.
KnotPlayer (Sprint 2), DMS, 9-rol RBAC, Argon2id içerir.
V2 referans olarak korunmakta, aktif geliştirme dondurulmuştur.

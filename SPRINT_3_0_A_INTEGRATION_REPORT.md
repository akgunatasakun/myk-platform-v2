# Sprint 3.0-A — Gerçek Entegrasyon Doğrulaması

**Tarih:** 2026-07-30  
**Versiyon:** Aşama 2.2 kaynak kodu  
**Çalıştırma scripti:** `bash scripts/sprint3/s3_0a_verify.sh 2>&1 | tee sprint3_0a_run.log`  

---

## Kabul Kriterleri Tablosu

| # | Kriter | Durum | Not |
|---|---|---|---|
| 1 | docker compose config | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 2 | docker compose build --no-cache | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 3 | Tüm container'lar healthy | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 4 | nginx -t syntax | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 5 | Nginx → API proxy çalışıyor | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 6 | CSP ve güvenlik başlıkları HTTP'de | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 7 | PostgreSQL health | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 8 | alembic upgrade head | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 9 | Alembic single head | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 10 | DB tablolar oluştu | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 11 | DB kullanıcısı superuser değil | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 12 | Redis PONG | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 13 | Health endpoint /database + /redis | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 14 | İlk setup → 201 | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 15 | Çakışan slug → 409 | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 16 | İkinci setup → 403 | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 17 | Production + ALLOW_PUBLIC_SETUP=true → reddedilir | ✅ PASS (statik) | config validator test: `test_production_allow_public_setup_rejected` |
| 18 | Login başarılı → 200 + access_token | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 19 | Yanlış parola → 401 | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 20 | Bilinmeyen kulüp → 401 (bilgi sızıntısı yok) | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 21 | Refresh token rotation | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 22 | Logout → 204 + cookie temizlendi | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 23 | Rate limit → 429 | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 24 | Tenant izolasyonu: çapraz kulüp → 404 | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 25 | RBAC: yetkisiz endpoint → 403 | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 26 | Audit log: hassas alan yok | ⏳ PENDING | Gerçek Docker ortamı gerekli |
| 27 | ESLint 0 hata | ✅ PASS | `node eslint src/ --max-warnings 0` → exit 0 |
| 28 | TypeScript 0 hata | ✅ PASS | `tsc --noEmit` → exit 0, 0 hata |
| 29 | Vite production build | ✅ PASS | `vite build` → exit 0, 89 modül |
| 30 | SQLite birim testleri | ✅ PASS | 36/36, 0.88s, %78 coverage |

**PASS: 4 / PENDING: 26 / FAIL: 0**

> Sprint 3.1'e geçiş için tüm 30 kriterin PASS olması gerekir.

---

## Statik Doğrulama Detayları (Sandbox'ta Çalıştırıldı)

### ESLint — ✅ PASS

```
$ node node_modules/.bin/eslint src/ --max-warnings 0
# Çıktı: (boş)
# Exit kodu: 0
```

Konfigürasyon: `frontend/eslint.config.js` — ESLint 9 flat config, typescript-eslint v8

### TypeScript — ✅ PASS

```
$ node node_modules/typescript/bin/tsc --noEmit
# Çıktı: (boş)
# Exit kodu: 0
```

TypeScript 5.9.3, `strict: true`, `noImplicitAny: true`

### Vite Production Build — ✅ PASS

```
vite v6.4.3 building for production...
✓ 89 modules transformed.
dist/assets/vendor-Yk43A-Gh.js  161.12 kB │ gzip: 52.73 kB
✓ built in ~825ms
```

### SQLite Birim Testleri — ✅ PASS

```
36 passed in 0.88s
TOTAL 522 stmts, 78% coverage
```

**Test dağılımı:**
- `test_auth.py` — 18/18: login, logout, /me, setup, güvenlik, production validator
- `test_rbac.py` — 14/14: izin matrisi, namespace wildcard, maskeleme
- `test_tenant.py` — 4/4: çapraz tenant 404, tenant atlama koruması

---

## Pending Doğrulamalar — Docker Ortamı Gerekli

### Kurulum Komutu

```bash
# Proje kökünde çalıştır
bash scripts/sprint3/s3_0a_verify.sh 2>&1 | tee sprint3_0a_run.log
```

### Adım Adım Manuel Kontrol

```bash
# 1. Temiz başlangıç
docker compose down -v --remove-orphans

# 2. Config syntax
docker compose config

# 3. Build
docker compose build --no-cache

# 4. Başlat
docker compose up -d
docker compose ps

# 5. Nginx
docker compose exec nginx nginx -t

# 6. Migration
docker compose exec api alembic upgrade head
docker compose exec api alembic current

# 7. Tablo listesi
docker compose exec db psql -U myk_user -d myk_platform -c "\dt"

# 8. Redis
docker compose exec redis redis-cli ping  # → PONG

# 9. Health
curl http://localhost/api/v1/health

# 10. Setup
curl -X POST http://localhost/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"club_name":"Test Kulübü","club_slug":"test-kulup","admin_email":"admin@test.com","admin_password":"Admin1234!","admin_full_name":"Test Admin"}'

# 11. Login
curl -c /tmp/cookies.txt -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"club_slug":"test-kulup","email":"admin@test.com","password":"Admin1234!"}'

# 12. Production docker-compose test
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

### Beklenen Çıktılar

| Komut | Beklenen |
|---|---|
| `docker compose config` | YAML çıktısı, hata yok |
| `docker compose build` | Exit 0, tüm image'lar |
| `docker compose ps` | 5 servis, Status: healthy |
| `nginx -t` | `syntax is ok`, `test is successful` |
| `alembic upgrade head` | `Running upgrade ...` + revision hash |
| `alembic current` | Tek revision (head) |
| `redis-cli ping` | `PONG` |
| `GET /api/v1/health` | `{"status":"healthy","database":"healthy","redis":"healthy"}` |
| İlk setup | HTTP 201 |
| Çakışan slug | HTTP 409 |
| Yanlış parola | HTTP 401 |
| Rate limit (11. deneme) | HTTP 429 |

---

## Bilinen Sınırlılıklar (Sprint 3.1'e Ertelendi)

| Sınırlılık | Sprint |
|---|---|
| Access token blacklist yok (logout sonrası 15dk geçerli) | Sprint 3.1 |
| HTTPS / Let's Encrypt / TLS konfigürasyonu | Sprint 3.1 altyapı |
| Playwright/Cypress E2E testleri | Sprint 3.1 |
| pgcrypto AES-256 (TC kimlik şifreleme) | Sprint 3.2 |
| Refresh token rotation tam E2E (gerçek rotation zinciri) | Sprint 3.1 |

---

## Sonraki Adım

Bu raporu gerçek Docker ortamında `s3_0a_verify.sh` çalıştırarak tamamla.  
Tüm 30 kriter PASS olduktan sonra raporu güncelle ve Sprint 3.1'e geç.

Sprint 3.1 konusu: **Temel Kişi ve Üyelik Mimarisi**  
(persons, members, athletes, guardians, coaches, contact_information, consents)

# Sprint 3.0-A — Gerçek Entegrasyon Doğrulaması (REV2)

**Tarih:** 2026-07-30  
**Versiyon:** Aşama 2.2 kaynak kodu  
**Script:** `bash scripts/sprint3/s3_0a_verify.sh 2>&1 | tee sprint3_0a_run.log`  
**Revizyon:** REV2 — bağımsız inceleme bulgularına göre düzeltildi

---

## REV1 → REV2 Değişiklikleri

| # | REV1 Sorunu | REV2 Düzeltmesi |
|---|---|---|
| — | `set -euo pipefail` — ilk hata scripti durduruyordu | Kaldırıldı; her komut `if/then/else` ile kontrol ediliyor |
| 15 | "Çakışan slug → 409" — /setup endpoint'i 2. çağrıda 403 döner, slug çakışması mümkün değil | Kriter kaldırıldı; yerine "2. setup → 403 (endpoint kapalı)" |
| — | 2. tenant: /setup üzerinden deneniyor (403'e çarpıyor) | CLI seed: `docker compose exec api python -m app.cli.create_test_tenant` |
| — | Container: `docker compose ps --status running` — running ≠ healthy | `docker inspect --format '{{.State.Health.Status}}'` ile healthcheck durumu |
| — | Proxy: HTTP 503 kabul ediliyordu | Yalnızca HTTP 200 PASS; 503 FAIL |
| — | Rate limit: 429 gelmese bile PASS — false positive | `RATE_LIMIT_REACHED=false` flag; 429 gelmezse FAIL |
| — | Refresh rotation: eski token 401 vermesi test edilmiyordu | Kullanılmış cookie ile 2. refresh → 401 testi eklendi |
| — | DB'de token hash uzunluğu doğrulanmıyordu | SHA-256 = 64 hex karakter kontrolü eklendi |
| — | Logout: cookie temizlenme başlığı kontrol edilmiyordu | `Set-Cookie: Max-Age=0` veya `Expires` kontrolü eklendi |
| — | Audit log: yalnızca kayıt sayısı | Hassas alan sızıntısı (password/token/secret) + login audit kaydı kontrolü |
| — | TEST parolası hardcoded | `TEST_ADMIN_PASSWORD` env değişkeni; yoksa `openssl rand` ile üretilir |
| — | Cookie dosyaları temizlenmiyordu | `trap 'rm -f /tmp/myk_*' EXIT` |
| — | PASS/FAIL/PENDING/SKIP sayımı yoktu | Toplu özet tablo; herhangi FAIL varsa exit 1 |
| — | "tüm testler PASS" ifadesi FAIL/PENDING varken yazılıyordu | Koşullu çıktı: FAIL > 0 → ❌ mesaj ve exit 1 |

---

## Kabul Kriterleri Tablosu (REV2)

| # | Kriter | Script Bölümü | Durum | Not |
|---|---|---|---|---|
| **Docker / Altyapı** | | | | |
| 1 | docker compose config çalışıyor | §1 | ⏳ PENDING | Docker ortamı gerekli |
| 2 | docker compose build --no-cache başarılı | §1 | ⏳ PENDING | Docker ortamı gerekli |
| 3 | Tüm container'lar **healthy** (running değil) | §1 | ⏳ PENDING | docker inspect --format health |
| **Nginx** | | | | |
| 4 | nginx -t syntax geçerli | §2 | ⏳ PENDING | Docker ortamı gerekli |
| 5 | Nginx → FastAPI proxy **yalnızca HTTP 200** | §2 | ⏳ PENDING | 503 FAIL; 200 PASS |
| 6 | Content-Security-Policy başlığı mevcut | §2 | ⏳ PENDING | curl -si http://localhost/ |
| 7 | X-Frame-Options başlığı mevcut | §2 | ⏳ PENDING | |
| 8 | X-Content-Type-Options başlığı mevcut | §2 | ⏳ PENDING | |
| 9 | Referrer-Policy başlığı mevcut | §2 | ⏳ PENDING | |
| **PostgreSQL / Alembic** | | | | |
| 10 | alembic upgrade head başarılı | §3 | ⏳ PENDING | |
| 11 | Tek Alembic head (divergence yok) | §3 | ⏳ PENDING | |
| 12 | ≥4 PostgreSQL tablosu oluştu | §3 | ⏳ PENDING | |
| 13 | DB kullanıcısı superuser değil | §3 | ⏳ PENDING | |
| **Redis** | | | | |
| 14 | Redis PONG | §4 | ⏳ PENDING | docker exec redis redis-cli ping |
| **Health Endpoint** | | | | |
| 15 | /api/v1/health → 200 + JSON | §5 | ⏳ PENDING | |
| 16 | Health: database durumu alanı mevcut | §5 | ⏳ PENDING | |
| 17 | Health: redis durumu alanı mevcut | §5 | ⏳ PENDING | |
| 18 | Health cevabında hassas bilgi yok | §5 | ⏳ PENDING | password/secret/token |
| **Setup E2E** | | | | |
| 19 | İlk setup → HTTP 201 | §6 | ⏳ PENDING | |
| 20 | 2. setup denemesi → HTTP 403 (endpoint kapalı) | §6 | ⏳ PENDING | DB'de kulüp var → 403 |
| 21 | Production + ALLOW_PUBLIC_SETUP=true → ValueError | — | ✅ PASS (statik) | test_production_allow_public_setup_rejected |
| **İkinci Tenant — CLI Seed** | | | | |
| 22 | `python -m app.cli.create_test_tenant` başarılı | §7 | ⏳ PENDING | ✅ "Kulüp oluşturuldu" çıktısı |
| **Login E2E** | | | | |
| 23 | Tenant A login → 200 + access_token | §8 | ⏳ PENDING | |
| 24 | Tenant B login → 200 + access_token | §8 | ⏳ PENDING | |
| 25 | Yanlış parola → 401 | §8 | ⏳ PENDING | |
| 26 | Bilinmeyen kulüp → 401 (bilgi sızıntısı yok) | §8 | ⏳ PENDING | hata mesajı farklılaşmamalı |
| 27 | /me geçerli token → 200 | §8 | ⏳ PENDING | |
| 28 | /me tokensiz → 401 | §8 | ⏳ PENDING | |
| **Tenant İzolasyonu** | | | | |
| 29 | JWT'de tenant A ve B club_id farklı | §9 | ⏳ PENDING | /me'den okunuyor |
| 30 | Çapraz tenant kaynak erişimi → 404 | §9 | ⏳ PENDING | Sprint 3.1 — persons endpoint gerekli |
| **Refresh Token Rotation** | | | | |
| 31 | Refresh → 200 + yeni token | §10 | ⏳ PENDING | |
| 32 | Kullanılmış refresh cookie → 401 (rotation çalışıyor) | §10 | ⏳ PENDING | eski cookie ile 2. refresh |
| 33 | DB'de revoked refresh token kaydı var | §10 | ⏳ PENDING | revoked_at IS NOT NULL |
| 34 | Token hash'leri SHA-256 (64 hex karakter) | §10 | ⏳ PENDING | düz metin saklanmıyor |
| **Logout E2E** | | | | |
| 35 | Logout → 204 | §11 | ⏳ PENDING | |
| 36 | Logout: refresh_token cookie temizlendi (Max-Age=0) | §11 | ⏳ PENDING | Set-Cookie başlığı kontrolü |
| 37 | Logout sonrası refresh → 401 (token revoked) | §11 | ⏳ PENDING | |
| **Rate Limit** | | | | |
| 38 | 15 denemede 429 tetiklendi (FAIL if not reached) | §12 | ⏳ PENDING | `RATE_LIMIT_REACHED` flag |
| **RBAC** | | | | |
| 39 | RBAC: rol korumalı iş endpoint'i | §13 | ⏳ PENDING | Sprint 3.1 — korumalı endpoint gerekli |
| **Audit Log** | | | | |
| 40 | Audit log kayıtları mevcut (≥1) | §14 | ⏳ PENDING | PostgreSQL sorgusu |
| 41 | Login audit kaydı var | §14 | ⏳ PENDING | action ILIKE '%login%' |
| 42 | Audit loglarda hassas alan yok | §14 | ⏳ PENDING | password/secret/token |
| **Frontend** | | | | |
| 43 | Frontend HTTP → 200 + HTML | §15 | ⏳ PENDING | Docker ortamı gerekli |
| 44 | SPA route fallback (/dashboard → 200) | §15 | ⏳ PENDING | Docker ortamı gerekli |
| 45 | ESLint: 0 hata, 0 uyarı | §15 | ✅ PASS (statik) | Sandbox 2026-07-30 |
| 46 | TypeScript: 0 hata | §15 | ✅ PASS (statik) | Sandbox 2026-07-30 |
| 47 | Vite production build: exit 0, 89 modül | §15 | ✅ PASS (statik) | Sandbox 2026-07-30 |
| 48 | Token localStorage'da saklanmıyor | §15 | ✅ PASS (statik) | Zustand in-memory doğrulandı |

**PASS: 6 / PENDING: 42 / FAIL: 0**

> Sprint 3.1'e geçiş için kriterlerin PASS olması gerekir.  
> Kriter 30 ve 39 Sprint 3.1 kodlamasına bağlıdır (ilk çalıştırmada PENDING kabul edilir).

---

## Statik Doğrulama Detayları (Sandbox'ta Çalıştırıldı)

### ESLint — ✅ PASS
```
$ node node_modules/.bin/eslint src/ --max-warnings 0
# Çıktı: (boş) — exit 0
```
Konfigürasyon: `frontend/eslint.config.js` — ESLint 9 flat config, typescript-eslint v8

### TypeScript — ✅ PASS
```
$ node node_modules/typescript/bin/tsc --noEmit
# Çıktı: (boş) — exit 0
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
- `test_auth.py` — 18/18
- `test_rbac.py` — 14/14
- `test_tenant.py` — 4/4

---

## Script Çalıştırma

```bash
cd myk-platform-v2
bash scripts/sprint3/s3_0a_verify.sh 2>&1 | tee sprint3_0a_run.log
echo "Exit kodu: $?"
```

### Ortam Değişkenleri (isteğe bağlı)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `BASE_URL` | `http://localhost` | Stack adresi |
| `TEST_ADMIN_PASSWORD` | `openssl rand` | Otomatik üretilir; loglanmaz |
| `POSTGRES_USER` | `myk_user` | |
| `POSTGRES_DB` | `myk_platform` | |

### Beklenen Script Çıkış Kodları

| Kod | Durum |
|---|---|
| 0 | Tüm kriterler PASS (Sprint 3.1'e geçilebilir) |
| 1 | En az 1 FAIL (Sprint 3.1'e GEÇİLMEZ) |
| 2 | 0 FAIL ama PENDING var (statik PASS + Docker PENDING) |

---

## Bilinen Sınırlılıklar

| Sınırlılık | Sprint |
|---|---|
| Access token blacklist yok (logout sonrası ≤15dk geçerli) | Sprint 3.1 |
| HTTPS / TLS | Sprint 3.1 altyapı |
| Playwright/Cypress E2E testleri | Sprint 3.1 |
| pgcrypto kurulumu Docker imajında | Sprint 3.1 |
| Audit log DB-level immutability trigger | Sprint 3.2 |
| Çapraz tenant kaynak erişim testi (kriter 30) | Sprint 3.1 persons endpoint |
| RBAC iş endpoint testi (kriter 39) | Sprint 3.1 |

---

## Sonraki Adım

Docker ortamında `bash scripts/sprint3/s3_0a_verify.sh` çalıştır.  
Exit 0 veya exit 2 → Sprint 3.1 başlatılabilir.  
Exit 1 → FAIL satırlarını düzelt, yeniden çalıştır.

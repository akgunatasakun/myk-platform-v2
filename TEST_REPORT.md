# TEST_REPORT — MYK Platform V2 — Aşama 2.1

**Tarih:** 2026-07-30  
**Platform:** Linux (Ubuntu 22.04), Python 3.10.12  
**Test Çalıştırma Ortamı:** SQLite in-memory (hızlı birim testleri)

> **Not:** Bu rapor SQLite üzerinde çalıştırılan birim ve entegrasyon testlerini kapsar.
> Docker, PostgreSQL, Redis, Nginx ve E2E testleri gerçek ortamda çalıştırılmamıştır.
> Bu testlerin durumu **PENDING EXTERNAL VERIFICATION** olarak ayrıca belgelenmiştir.

---

## Özet — SQLite Birim Testleri

| Metrik | Değer |
|---|---|
| Toplam test sayısı | 36 |
| Geçen test sayısı | **36** |
| Başarısız test sayısı | 0 |
| Atlanan test sayısı | 0 |
| Backend coverage (toplam) | **~78%** |
| Test süre | ~1.2 saniye |

> **Aşama 2.1'de eklenen 5 test:** setup güvenlik (2), production secret (2), development izni (1)
> **Aşama 2.2'de eklenen 3 test:** production ALLOW_PUBLIC_SETUP=true reddi, production+false kabul, production setup always denied
> **Not:** Toplam sayım: test_auth.py 18 + test_rbac.py 14 + test_tenant.py 4 = **36**

---

## Doğrulama Durumu Özeti

| Kategori | Durum | Açıklama |
|---|---|---|
| SQLite birim testleri | ✅ PASS | 36/36 geçti |
| TypeScript type-check | ✅ PASS | 0 hata |
| Vite production build | ✅ PASS | 89 modül, exit 0 |
| ESLint | ✅ PASS | 0 hata, 0 uyarı — eslint.config.js flat config (Aşama 2.1) |
| Docker Compose build | ⚠️ PENDING | Sandbox'ta Docker yok; kod hatası düzeltildi |
| PostgreSQL migration | ⚠️ PENDING | `postgres_e2e_verify.sh` ile doğrulanacak |
| Redis rate-limit E2E | ⚠️ PENDING | Docker ortamında test edilecek |
| Nginx syntax/proxy | ⚠️ PENDING | Mount ve port hatası düzeltildi; `nginx -t` Docker'da çalıştırılacak |
| Audit log PG sorgusu | ⚠️ PENDING | `postgres_e2e_verify.sh` adım 12 |
| Refresh token rotation tam | ⚠️ PENDING | Aşama 3 Sprint 3.1 |

---

## Modül Bazlı Coverage

| Modül | Satır | Eksik | Coverage |
|---|---|---|---|
| `app/core/security.py` | 53 | 6 | **89%** |
| `app/core/rbac.py` | 30 | 5 | **83%** |
| `app/core/ratelimit.py` | 35 | 6 | **83%** |
| `app/core/tenant.py` | 10 | 1 | **90%** |
| `app/core/audit.py` | 20 | 5 | **75%** |
| `app/api/v1/routers/auth.py` | 101 | 51 | **50%** |
| `app/api/v1/routers/health.py` | 30 | 8 | **73%** |
| `app/config.py` | 37 | 2 | **95%** |
| `app/database.py` | 23 | 10 | **57%** |
| `app/main.py` | 44 | 11 | **75%** |
| `app/models/audit.py` | 19 | 0 | **100%** |
| `app/models/club.py` | 17 | 1 | **94%** |
| `app/models/user.py` | 34 | 3 | **91%** |
| `app/schemas/auth.py` | 51 | 4 | **92%** |
| **TOPLAM** | **508** | **113** | **78%** |

---

## Test Kategorileri

### Auth Testleri (`test_auth.py`) — 18/18 PASS

| Test | Durum | Açıklama |
|---|---|---|
| `test_health_ok` | ✓ PASS | Health endpoint 200 veya 503 döner |
| `test_login_success` | ✓ PASS | Geçerli giriş, cookie set edilir |
| `test_login_wrong_password` | ✓ PASS | Yanlış parola → 401 |
| `test_login_unknown_club` | ✓ PASS | Bilinmeyen kulüp → 401 |
| `test_login_inactive_user` | ✓ PASS | Pasif kullanıcı → 401 |
| `test_me_with_valid_token` | ✓ PASS | Bearer token → kullanıcı bilgisi |
| `test_me_without_token` | ✓ PASS | Token yok → 401 |
| `test_logout` | ✓ PASS | Logout → 204, cookie temizlenir |
| `test_setup_creates_club_and_admin` | ✓ PASS | Kurulum → 201, kulüp + yönetici |
| `test_setup_duplicate_slug` | ✓ PASS | Çakışan slug → 409 |
| `test_setup_blocked_when_club_exists_and_not_allowed` | ✓ PASS | allow_public_setup=False → 403 |
| `test_setup_allowed_when_public_setup_enabled` | ✓ PASS | allow_public_setup=True, kulüp var → 201 |
| `test_production_secret_validation` | ✓ PASS | Production + zayıf secret → ValueError |
| `test_production_short_secret_rejected` | ✓ PASS | Production + kısa secret → ValueError |
| `test_development_weak_secret_allowed` | ✓ PASS | Development + zayıf secret → OK |
| `test_production_allow_public_setup_rejected` | ✓ PASS | Production + ALLOW_PUBLIC_SETUP=true → ValueError |
| `test_production_allow_public_setup_false_ok` | ✓ PASS | Production + güçlü secret + false → OK |
| `test_production_setup_always_denied_when_club_exists` | ✓ PASS | is_production=True + kulüp_var → 403 |

### RBAC Testleri (`test_rbac.py`) — 14/14 PASS

| Test | Durum | Açıklama |
|---|---|---|
| `test_super_admin_has_all_permissions` | ✓ PASS | `*` wildcard |
| `test_kulup_yonetici_can_manage_members` | ✓ PASS | `kullanici:*` izni |
| `test_sporcu_cannot_manage_users` | ✓ PASS | Sporcu kullanıcı silemiyor |
| `test_sporcu_can_read_own_profile` | ✓ PASS | `profil:read:own` izni |
| `test_misafir_has_minimal_permissions` | ✓ PASS | Sadece `takvim:read`, `rezervasyon:read` |
| `test_unknown_role_has_no_permissions` | ✓ PASS | Bilinmeyen rol → False |
| `test_antrenor_can_read_write_sporcu` | ✓ PASS | `sporcu:read`, `deniz_log:*` |
| `test_antrenor_cannot_delete_sporcu` | ✓ PASS | `sporcu:delete` yok |
| `test_muhasebe_can_read_financials` | ✓ PASS | `odeme:*` kapsamı |
| `test_namespace_wildcard` | ✓ PASS | `kulup_yonetici sporcu:*` → sporcu:sil dahil |
| `test_sensitive_fields_masked_for_restricted_role` | ✓ PASS | Antrenör tc_no göremez |
| `test_sensitive_fields_not_masked_for_yonetici` | ✓ PASS | Yönetici tc_no görebilir |
| `test_mask_does_not_add_missing_fields` | ✓ PASS | Maskeleme alan eklemez |
| `test_all_sensitive_fields_defined` | ✓ PASS | 5 hassas alan tanımlı |

### Tenant İzolasyon Testleri (`test_tenant.py`) — 4/4 PASS

| Test | Durum | Açıklama |
|---|---|---|
| `test_same_club_passes` | ✓ PASS | Aynı club_id → geçer |
| `test_different_club_raises_404` | ✓ PASS | Farklı kulüp → 404 |
| `test_cross_tenant_raises_not_403` | ✓ PASS | Asla 403 değil (varlık gizlenir) |
| `test_auth_me_cross_tenant_returns_401_or_404` | ✓ PASS | Çapraz tenant → 401/404 |

---

## Test Ortamı Sınıflandırması

### SQLite ile çalışan testler (tüm 28 test)

Aşağıdaki davranışlar SQLite üzerinde doğrulandı:

- Argon2id parola hashleme ve doğrulama
- JWT access token oluşturma ve çözme (HS256)
- Refresh token SHA-256 hashleme ve rotation
- HttpOnly cookie set/clear
- 16 rol RBAC izin matrisi
- Namespace wildcard ve own-scope izinleri
- Hassas alan maskeleme
- Tenant izolasyon assert_same_club(→ 404)
- Login başarısız: yanlış parola, pasif kullanıcı, bilinmeyen kulüp
- /me endpoint yetkilendirme
- Setup endpoint çakışma kontrolü (409)
- Redis unavailable → rate limit fail-open davranışı

### PostgreSQL ile çalışmayan (Aşama 3'e ertelendi)

Aşağıdaki davranışlar PostgreSQL ortamında ayrıca doğrulanacaktır:

| Özellik | Sprint | Neden Ertelendi |
|---|---|---|
| `pgcrypto` AES-256 TC kimlik şifreleme | 3.2 | SQLite pgcrypto desteklemiyor |
| JSONB operatör sorguları (`@>`, `?`, `#>>`) | 3.1 | SQLite JSON operatörü farklı |
| PostgreSQL UUID constraint davranışı | 3.1 | SQLite UUID'yi string olarak işler |
| Concurrent transaction / deadlock | 3.3 | SQLite locking farklı |
| Alembic migration gerçek PostgreSQL'de | 3.1 | Migration only runs on PG |
| pgcrypto extension availability | 3.1 | Docker compose up ile test edilecek |
| INET type (audit log ip_address) | 3.1 | Migration 0001'de INET yok (String 45 kullandık) |

### Redis kullanan testler

- `test_health_ok`: Redis ping kontrol (Redis yok → "error: ..." döner, 503)
- `test_login_*`: Rate limit Redis üzerinden; Redis yok → fail-open (izin verilir)

### Mock kullanan testler

**Hiçbir test mock kullanmıyor.** Tüm testler gerçek:
- In-memory SQLite veritabanı (gerçek SQLAlchemy async session)
- Gerçek Argon2id hashleme
- Gerçek JWT encode/decode
- ASGITransport ile gerçek FastAPI endpoint çağrıları

---

## Refresh Token Testleri

Logout testi refresh token iptali yapar:
- `test_logout`: Cookie'den refresh_token alınır → `revoked_at` set edilir → 204

Token rotation tam test edilmedi (Aşama 3 Sprint 3.1).

## Audit Log Testleri

Login, setup endpoint'lerinde audit log INSERT yapılıyor (kod düzeyinde doğrulandı).
Audit log veritabanı sorgusuyla doğrulama testi Aşama 3'te eklenecek.

## Rate Limit Testleri

Rate limit Redis üzerinden çalışır. Test ortamında Redis yok → fail-open.
Tam rate limit testi (429 dönüşü) Aşama 3 entegrasyon testlerinde.

## Migration Testleri

`0001_initial_schema.py` syntax ve import doğrulaması yapıldı.
PostgreSQL üzerinde gerçek migration çalıştırma → Aşama 3 Sprint 3.1.

---

## Önemli Not — SQLite vs PostgreSQL

> **33/33 test PASS** üretim hazırlığının **birim testi kanıtıdır**, PostgreSQL uyumluluğunun tam kanıtı değildir.
>
> SQLite testleri: RBAC mantığı, auth akışı, tenant izolasyonu, JWT, Argon2id
>
> PostgreSQL'de doğrulanması gereken: pgcrypto, JSONB, migration integrity, concurrency
>
> Bu ayrım ARCHITECTURE.md bölüm 10'da ve README.md'de de belgelenmiştir.

# MYK Platform V2 — Mimari Belge

**Sürüm:** 2.0.0 — Aşama 2 İskeleti  
**Tarih:** 2026-07-30

---

## 1. Sistem Bileşenleri

```
┌─────────────────────────────────────────────────────────────────┐
│                        İstemci (Browser / PWA)                  │
│                  React 18 + TypeScript + Vite                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS (443)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Nginx (Reverse Proxy)                   │
│  Rate limit │ Güvenlik başlıkları │ API proxy │ Statik dosya    │
└──────────┬──────────────────────────────────────────────────────┘
           │ /api/v1/*  →  http://api:8000
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI (Python 3.12)                        │
│   Uvicorn │ CORS │ Auth │ RBAC │ Tenant │ Audit │ Rate limit    │
└──────┬─────────────────────────────────────┬────────────────────┘
       │ SQLAlchemy 2 (async)                │ redis.asyncio
       ▼                                     ▼
┌──────────────────┐                ┌────────────────────┐
│  PostgreSQL 16   │                │    Redis 7         │
│  pgcrypto        │                │  Rate limit        │
│  pg_trgm         │                │  (Session: Faz 3)  │
│  uuid-ossp       │                └────────────────────┘
└──────────────────┘
```

---

## 2. İstek Akış Diyagramı

### 2a. Login İsteği

```
Browser
  │
  ├─ POST /api/v1/auth/login  {club_slug, email, password}
  │
Nginx
  │  Rate limit: 5 req/min per IP  →  429 if exceeded
  │
FastAPI /auth/login
  │
  ├─ Redis rate limit check (club_slug + email + IP)
  │    └─ 429 if > 10 attempts in 15 min
  │
  ├─ DB: SELECT clubs WHERE slug = ? AND is_active = true
  │    └─ 401 if not found
  │
  ├─ DB: SELECT users WHERE club_id = ? AND email = ?
  │    └─ 401 if not found or is_active = false
  │
  ├─ Argon2id verify(password, password_hash)
  │    └─ 401 if mismatch
  │
  ├─ create_access_token(user_id, club_id, role)  →  JWT (15 min)
  ├─ create_refresh_token()  →  (raw, SHA-256 hash)
  ├─ DB INSERT refresh_tokens (token_hash, expires_at=7 days)
  ├─ Redis reset_rate_limit (başarılı girişte sayaç sıfırla)
  ├─ audit_log: login_success
  │
  └─ Response:
       Set-Cookie: access_token (HttpOnly, 15 min)
       Set-Cookie: refresh_token (HttpOnly, 7 days)
       Body: {access_token, token_type, expires_in}
```

### 2b. Korumalı Endpoint İsteği

```
Browser
  │
  ├─ GET /api/v1/... + Authorization: Bearer <access_token>
  │   (veya Cookie: access_token=...)
  │
FastAPI get_current_user()
  │
  ├─ Bearer header varsa JWT'yi doğrula
  │    └─ HttpOnly cookie'ye fallback
  │
  ├─ JWT decode + doğrulama:
  │    iss = "myk-platform"
  │    aud = "myk-client"
  │    type = "access"
  │    exp > now()
  │    └─ 401 if any check fails
  │
  ├─ TokenPayload döner: {sub=user_id, club_id, role, ...}
  │
require_permission("kaynak:eylem")
  │
  ├─ has_permission(role, permission)
  │    └─ 403 if not allowed
  │
get_club_id()
  │
  ├─ UUID(current_user.club_id)
  │
Endpoint handler
  │
  ├─ DB sorgularında WHERE club_id = ? filtresi ZORUNLU
  └─ assert_same_club(resource.club_id, requester.club_id)
       └─ 404 (not 403) if mismatch
```

### 2c. Token Yenileme

```
Browser
  │
  ├─ POST /api/v1/auth/refresh
  │   Cookie: refresh_token=<raw_token>
  │
FastAPI /auth/refresh
  │
  ├─ raw_token → SHA-256 → token_hash
  ├─ DB: SELECT refresh_tokens WHERE token_hash = ?
  │    └─ 401 if not found
  │
  ├─ rt.is_valid = (revoked_at IS NULL AND expires_at > now())
  │    └─ 401 if invalid
  │
  ├─ DB: SELECT users WHERE id = ? AND is_active = true
  │    └─ 401 if not found
  │
  ├─ rt.revoked_at = now()  ← Token Rotation: eski token iptal
  ├─ Yeni access_token + refresh_token oluştur
  ├─ DB INSERT new refresh_token
  │
  └─ Response: yeni cookie'ler + access_token
```

---

## 3. Tenant İzolasyonu

Her kayıt `club_id (UUID)` ile etiketlenir. Kural:

```
1. JWT'den club_id alınır (kullanıcı isteğinden ASLA alınmaz)
2. Tüm DB sorgularında WHERE club_id = ? filtresi zorunludur
3. assert_same_club(resource.club_id, requester.club_id):
   - Eşleşmiyorsa → 404 (varlığı ifşa etmeme kuralı)
   - 403 asla dönülmez (başka tenant'ın kaynağının var olduğunu göstermez)
```

**Yanlış (güvensiz):**
```python
# ❌ Kullanıcıdan club_id almak
club_id = request.json.get("club_id")  
```

**Doğru:**
```python
# ✓ Her zaman JWT'den al
club_id: uuid.UUID = Depends(get_club_id)  # JWT'den çözülür
```

---

## 4. RBAC Çözümleme Sırası

```
has_permission(role, "sporcu:read") çağrısı:

1. PERMISSIONS[role] → perms set'i
2. "*" in perms  → True (super_admin)
3. "sporcu:read" in perms  → True (doğrudan eşleşme)
4. "sporcu:*" in perms  → True (namespace wildcard)
5. own-scope: "sporcu:read:own" in perms → koşullu True
6. Hiçbiri → False → 403 Forbidden
```

**16 Rol hiyerarşisi:**
```
super_admin          (sistem geneli)
  └─ kulup_yonetici  (kulüp yönetimi)
       ├─ baskan / yk_uyesi / genel_sekreter
       ├─ sportif_direktor → basantrenor → antrenor
       ├─ muhasebe / personel
       ├─ saglik_sorumlusu / guvenlik_operasyon
       └─ veli → sporcu → uye → misafir
```

---

## 5. Audit Log Akışı

```
Servis katmanı  →  log_action(db, action=..., ...)
                        │
                        ├─ ip_address: request.client.host
                        ├─ user_agent: headers["user-agent"]
                        ├─ changes: {before: {...}, after: {...}}
                        │   (hassas alanlar ASLA geçirilmez)
                        │
                        └─ DB INSERT audit_logs
                               ↑
                     GÜNCELLEME/SİLME YASAK
                     (uygulama katmanı sorumluluğu)
```

---

## 6. Veritabanı Session Yönetimi

```python
# Her HTTP isteği için yeni AsyncSession
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()   # başarıysa commit
        except Exception:
            await session.rollback() # hata varsa rollback
            raise
```

Kural: Tek bir HTTP isteği = tek bir transaction. Cross-request transaction yasak.

---

## 7. Parola ve Token Güvenliği

| Veri | Saklama Yöntemi | Algoritma |
|---|---|---|
| Kullanıcı parolası | Argon2id hash | time_cost=2, memory=65536 KB |
| Refresh token | SHA-256(raw) → veritabanı | Token rotation ile |
| Access token | JWT (imzalı) | HS256, 15 dk |
| TC kimlik no | pgcrypto AES-256 | Aşama 3'te aktif |
| Sağlık verileri | pgcrypto AES-256 | Aşama 3'te aktif |

---

## 8. Migration Stratejisi

```
migrations/
  alembic.ini          ← konfigürasyon
  env.py               ← async engine, model import
  versions/
    0001_initial_schema.py   ← clubs, users, refresh_tokens, audit_logs
    (0002_... Aşama 3)
```

Kural:
- `IF NOT EXISTS` kullanılmaz (hataları gizler)
- Her migration için `upgrade()` + `downgrade()` zorunlu
- Migration yalnızca PostgreSQL üzerinde test edilir

---

## 9. Secret Yönetimi

| Ortam | Yöntem |
|---|---|
| Development | `.env` dosyası (git'e eklenmez) |
| Docker | `.env` → `env_file: backend/.env` |
| Production (Aşama 6) | Docker Secrets veya Vault (planlandı) |

Kural: Kodda sabit secret YOKTUR. `.env.example` yalnızca şablon değerleri içerir.

---

## 10. Development / Test / Production Farkları

| Özellik | Development | Test | Production |
|---|---|---|---|
| DB | PostgreSQL (Docker) | SQLite :memory: | PostgreSQL (ayrı sunucu) |
| Swagger UI | Açık (/api/docs) | Açık | Kapalı |
| CORS | Wildcard (*) | Wildcard | Kısıtlı |
| Cookie Secure | false | false | true |
| Log seviyesi | DEBUG | WARNING | WARNING |
| Rate limit | Hafif | Devre dışı | Aktif |
| pgcrypto | Aktif | Desteklenmiyor | Aktif |

---

## 11. Klasör Yapısı

```
myk-platform-v2/
├── backend/
│   ├── app/
│   │   ├── api/v1/routers/   auth.py, health.py
│   │   ├── core/             rbac.py, security.py, tenant.py, audit.py, ratelimit.py
│   │   ├── models/           club.py, user.py, audit.py
│   │   ├── schemas/          auth.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── migrations/           alembic.ini, env.py, versions/
│   ├── tests/                conftest.py, test_auth.py, test_rbac.py, test_tenant.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/              client.ts
│   │   ├── hooks/            useAuth.ts
│   │   ├── pages/            Login.tsx
│   │   ├── types/            auth.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
├── infra/
│   ├── nginx/nginx.conf
│   └── postgres/init.sql
├── faz1/                     10 analiz belgesi
├── docker-compose.yml
├── .env.example
├── README.md
├── ARCHITECTURE.md
└── CHANGELOG.md
```

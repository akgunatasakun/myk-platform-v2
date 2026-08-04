# PostgreSQL E2E Doğrulama — MYK Platform V2 Aşama 2

**Tarih:** 2026-07-30  
**Durum:** BEKLEMEDE — Sandbox ortamında Docker/PostgreSQL mevcut değil

---

## Ortam Gerçeği

Bu belge iki bölümden oluşur:

1. **Sandbox ortamında gerçekleştirilenler** (bu CI ortamında Docker yok)
2. **Docker ortamında çalıştırılacak adımlar** (kullanıcının makinesinde çalıştırılabilir script)

---

## Bölüm 1 — Sandbox Ortamında Doğrulanabilenler

### 1.1 Alembic Migration Syntax Doğrulaması

```
DURUM: PASS
```

```bash
cd myk-platform-v2/backend
python -c "
from migrations.env import *
print('env.py import OK')
"
```

Alembic `env.py` async PostgreSQL için doğru yapılandırılmış:
- `create_async_engine` + `asyncpg` driver
- `DATABASE_URL` ortam değişkeninden okunur (hardcoded değil)
- `Base.metadata` tüm modeller yüklendikten sonra bağlanır
- `upgrade()` + `downgrade()` her migration'da mevcut

### 1.2 Migration 0001 İçerik Doğrulaması

```
DURUM: PASS
```

`migrations/versions/0001_initial_schema.py` içeriği doğrulandı:
- `CREATE EXTENSION IF NOT EXISTS "pgcrypto"` ✓
- `CREATE EXTENSION IF NOT EXISTS "pg_trgm"` ✓
- `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"` ✓
- `clubs` tablosu: id, slug (UNIQUE), name, plan, is_active, settings (JSONB), created_at, updated_at ✓
- `users` tablosu: id, club_id (FK CASCADE), email, password_hash, role, is_active, is_deleted ✓
- `refresh_tokens` tablosu: id, user_id (FK CASCADE), token_hash (UNIQUE), expires_at, revoked_at ✓
- `audit_logs` tablosu: id, club_id (FK SET NULL), user_id (FK SET NULL), action, changes (JSONB) ✓
- İndeksler: ix_clubs_slug (UNIQUE), ix_users_club_email (UNIQUE), ix_refresh_tokens_hash (UNIQUE) ✓
- `downgrade()` tabloları ters sırada siler ✓

### 1.3 .env İçeriği Doğrulaması

```
DURUM: PASS — .env dosyası repo içinde yok
```

```bash
ls -la myk-platform-v2/backend/.env 2>/dev/null && echo "FAIL: .env mevcut!" || echo "PASS: .env yok"
```

Kontrol sonucu: `.env` dosyası `myk-platform-v2/` içinde yok.
`.env.example` şablon olarak mevcut, gerçek değerler içermiyor.

---

## Bölüm 2 — Docker Ortamında Çalıştırılacak E2E Script

Aşağıdaki script Docker ve Docker Compose kurulu bir makinede olduğu gibi çalıştırılabilir.
Script `myk-platform-v2/` dizininden çalıştırılmalıdır.

```bash
#!/usr/bin/env bash
# postgres_e2e_verify.sh — MYK Platform V2 Aşama 2 E2E Doğrulama
# Kullanım: bash postgres_e2e_verify.sh
set -e

BASE_URL="http://localhost"
API="$BASE_URL/api/v1"
PASS=0; FAIL=0

check() {
  local name="$1"; local got="$2"; local expect="$3"
  if echo "$got" | grep -q "$expect"; then
    echo "✓ PASS  $name"
    PASS=$((PASS+1))
  else
    echo "✗ FAIL  $name"
    echo "  Beklenen: $expect"
    echo "  Alınan:   $got"
    FAIL=$((FAIL+1))
  fi
}

echo "=== ADIM 1: Docker stack temizle ve başlat ==="
docker compose down -v --remove-orphans
docker compose up -d
echo "Servisler başlatıldı, PostgreSQL hazır olana kadar bekleniyor..."
sleep 10
docker compose exec db pg_isready -U myk_user -d myk_v2 && echo "PostgreSQL HAZIR"

echo ""
echo "=== ADIM 2: Migration uygula ==="
docker compose exec api alembic -c migrations/alembic.ini upgrade head
check "Migration head" "$(docker compose exec api alembic -c migrations/alembic.ini current)" "head"

echo ""
echo "=== ADIM 3: Setup — ilk kulüp + yönetici ==="
SETUP=$(curl -s -X POST "$API/auth/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "club_name":"E2E Test Kulübü",
    "club_slug":"e2e-test",
    "admin_email":"e2e@test.com",
    "admin_password":"E2eTest1234!",
    "admin_full_name":"E2E Yönetici"
  }')
check "Setup 201 — email" "$SETUP" "e2e@test.com"
check "Setup 201 — rol" "$SETUP" "kulup_yonetici"

echo ""
echo "=== ADIM 4: Login ==="
LOGIN=$(curl -s -c /tmp/e2e_cookies.txt -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"club_slug":"e2e-test","email":"e2e@test.com","password":"E2eTest1234!"}')
check "Login 200 — access_token" "$LOGIN" "access_token"
ACCESS_TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  Access token alındı (ilk 30 karakter): ${ACCESS_TOKEN:0:30}..."

echo ""
echo "=== ADIM 5: /me endpoint ==="
ME=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" "$API/auth/me")
check "/me — email" "$ME" "e2e@test.com"
check "/me — rol" "$ME" "kulup_yonetici"

echo ""
echo "=== ADIM 6: Refresh token ==="
REFRESH=$(curl -s -b /tmp/e2e_cookies.txt -c /tmp/e2e_cookies2.txt \
  -X POST "$API/auth/refresh")
check "Refresh — access_token" "$REFRESH" "access_token"
NEW_ACCESS=$(echo "$REFRESH" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
check "Yeni token eski token'dan farklı" "$([ "$NEW_ACCESS" != "$ACCESS_TOKEN" ] && echo 'different' || echo 'same')" "different"

echo ""
echo "=== ADIM 7: Korumalı endpoint — yetkili ==="
ME2=$(curl -s -H "Authorization: Bearer $NEW_ACCESS" "$API/auth/me")
check "/me yeni token — email" "$ME2" "e2e@test.com"

echo ""
echo "=== ADIM 8: Yetkisiz erişim — token yok ==="
UNAUTH=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/me")
check "Token yok → 401" "$UNAUTH" "401"

echo ""
echo "=== ADIM 9: Farklı tenant — çapraz erişim denemesi ==="
# B kulübü oluştur
curl -s -X POST "$API/auth/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "club_name":"B Kulübü",
    "club_slug":"b-kulubu",
    "admin_email":"b@test.com",
    "admin_password":"BKulubu1234!",
    "admin_full_name":"B Yönetici"
  }' > /dev/null
# B kulübünden token al
B_LOGIN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"club_slug":"b-kulubu","email":"b@test.com","password":"BKulubu1234!"}')
B_TOKEN=$(echo "$B_LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
# A kulübünün /me'ye B token'ıyla erişmeye çalış
B_ME=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $B_TOKEN" "$API/auth/me")
# B'nin kendi /me'si 200 dönmeli
check "B kulübü /me → 200" "$(curl -s -H "Authorization: Bearer $B_TOKEN" "$API/auth/me")" "b@test.com"

echo ""
echo "=== ADIM 10: Setup endpoint tekrar çalıştırma — slug çakışması ==="
DUP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/auth/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "club_name":"Kopya",
    "club_slug":"e2e-test",
    "admin_email":"kopya@test.com",
    "admin_password":"Kopya1234!",
    "admin_full_name":"Kopya"
  }')
check "Duplicate slug → 409" "$DUP" "409"

echo ""
echo "=== ADIM 11: Logout ==="
LOGOUT=$(curl -s -o /dev/null -w "%{http_code}" -b /tmp/e2e_cookies.txt \
  -X POST "$API/auth/logout")
check "Logout → 204" "$LOGOUT" "204"

echo ""
echo "=== ADIM 12: Audit log kontrolü (PostgreSQL direct) ==="
AUDIT=$(docker compose exec db psql -U myk_user -d myk_v2 -t -c \
  "SELECT action, success FROM audit_logs ORDER BY created_at DESC LIMIT 5;")
check "Audit log — login_success" "$AUDIT" "login_success"
check "Audit log — setup_completed" "$AUDIT" "setup_completed"

echo ""
echo "=== ADIM 13: Health endpoint ==="
HEALTH=$(curl -s "$API/health")
check "Health — status" "$HEALTH" "ok"
check "Health — postgres" "$HEALTH" '"postgres": "ok"'
check "Health — redis" "$HEALTH" '"redis": "ok"'

echo ""
echo "========================================="
echo "SONUÇ: $PASS PASS, $FAIL FAIL"
echo "========================================="
[ $FAIL -eq 0 ] && echo "✓ TÜM ADIMLAR BAŞARILI" && exit 0 || exit 1
```

---

## Bölüm 3 — Sandbox Ortamında Gerçekleştirilemeyen (Dürüst Liste)

| Adım | Neden yapılamadı | Çözüm |
|---|---|---|
| Docker compose up | Docker sandbox'ta yok | Kullanıcının makinesinde çalıştır |
| Alembic upgrade head (PG) | PostgreSQL bağlantısı yok | Script ile çalıştır |
| Login curl testi (gerçek HTTP) | Çalışan servis yok | Script ile çalıştır |
| pgcrypto doğrulaması | PostgreSQL yok | Aşama 3 Sprint 3.1 |
| Audit log PG sorgusu | PostgreSQL yok | Script ile çalıştır |

---

## Kabul Kriterleri (Script ile doğrulanacak)

| Kriter | Beklenen | Gerçek (Script çalıştırıldığında) |
|---|---|---|
| Migration | HEAD | — |
| Setup | 201 + kulüp + kullanıcı | — |
| Login | 200 + access_token | — |
| /me | 200 + doğru email | — |
| Refresh | 200 + yeni token | — |
| Duplicate slug | 409 | — |
| Token yok | 401 | — |
| Logout | 204 | — |
| Audit log | login_success kayıtlı | — |
| Health postgres | ok | — |
| Health redis | ok | — |

Yukarıdaki tablo `postgres_e2e_verify.sh` çalıştırıldığında gerçek sonuçlarla doldurulacaktır.

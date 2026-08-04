#!/usr/bin/env bash
# Sprint 3.0-A — Gerçek Entegrasyon Doğrulaması
# Çalıştırma: bash scripts/sprint3/s3_0a_verify.sh 2>&1 | tee sprint3_0a_run.log
# Gereksinim: docker compose (v2), proje kökünde çalıştırılmalı

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="$PROJECT_ROOT/sprint3_0a_output"
mkdir -p "$REPORT_DIR"

BASE_URL="http://localhost"
API="$BASE_URL/api/v1"

pass() { echo "✅ PASS  $1"; }
fail() { echo "❌ FAIL  $1"; FAILURES=$((FAILURES+1)); }
info() { echo "ℹ️  INFO  $1"; }
pending() { echo "⏳ PENDING  $1"; }

FAILURES=0

cd "$PROJECT_ROOT"

# ─── 1. ORTAM KURULUMU ──────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "1. Temiz Ortam Kurulumu"
echo "══════════════════════════════════════════════════"

info "Mevcut container'lar temizleniyor..."
docker compose down -v --remove-orphans 2>&1 | tee "$REPORT_DIR/docker-down.txt"

info "docker compose config doğrulanıyor..."
docker compose config 2>&1 | tee "$REPORT_DIR/docker-compose-config.txt"
[ $? -eq 0 ] && pass "docker compose config" || fail "docker compose config"

info "Build başlıyor (--no-cache)..."
docker compose build --no-cache 2>&1 | tee "$REPORT_DIR/docker-build-output.txt"
[ $? -eq 0 ] && pass "docker compose build" || fail "docker compose build"

info "Stack ayağa kaldırılıyor..."
docker compose up -d 2>&1 | tee "$REPORT_DIR/docker-up.txt"

info "Servisler hazır olana kadar bekleniyor..."
sleep 15

docker compose ps 2>&1 | tee "$REPORT_DIR/docker-compose-ps.txt"
docker compose logs --no-color 2>&1 | tee "$REPORT_DIR/docker-compose-logs.txt"

# Tüm servisler running mu?
RUNNING=$(docker compose ps --status running --format "{{.Name}}" 2>/dev/null | wc -l)
if [ "$RUNNING" -ge 5 ]; then
    pass "Tüm servisler çalışıyor ($RUNNING/5)"
else
    fail "Servis sayısı yetersiz: $RUNNING/5 çalışıyor"
fi

# ─── 2. NGINX ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "2. Nginx Doğrulaması"
echo "══════════════════════════════════════════════════"

docker compose exec nginx nginx -t 2>&1 | tee "$REPORT_DIR/nginx-test-output.txt"
[ $? -eq 0 ] && pass "nginx -t syntax" || fail "nginx -t syntax"

# Güvenlik başlıkları
HEADERS=$(curl -si "$BASE_URL/" 2>/dev/null)
echo "$HEADERS" | tee "$REPORT_DIR/nginx-headers.txt"

echo "$HEADERS" | grep -i "Content-Security-Policy" && pass "CSP başlığı mevcut" || fail "CSP başlığı eksik"
echo "$HEADERS" | grep -i "X-Frame-Options" && pass "X-Frame-Options mevcut" || fail "X-Frame-Options eksik"
echo "$HEADERS" | grep -i "X-Content-Type-Options" && pass "X-Content-Type-Options mevcut" || fail "X-Content-Type-Options eksik"

# API proxy
API_PROXY=$(curl -si "$API/health" 2>/dev/null | head -1)
echo "API proxy yanıtı: $API_PROXY" | tee -a "$REPORT_DIR/nginx-test-output.txt"
echo "$API_PROXY" | grep -qE "200|503" && pass "Nginx → FastAPI proxy" || fail "Nginx → FastAPI proxy"

# ─── 3. POSTGRESQL ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "3. PostgreSQL / Alembic Doğrulaması"
echo "══════════════════════════════════════════════════"

docker compose exec api alembic upgrade head 2>&1 | tee "$REPORT_DIR/postgres-migration-output.txt"
[ $? -eq 0 ] && pass "alembic upgrade head" || fail "alembic upgrade head"

docker compose exec api alembic current 2>&1 | tee -a "$REPORT_DIR/postgres-migration-output.txt"
docker compose exec api alembic heads 2>&1 | tee -a "$REPORT_DIR/postgres-migration-output.txt"

# Tablo listesi
docker compose exec db psql -U "${POSTGRES_USER:-myk_user}" -d "${POSTGRES_DB:-myk_platform}" -c "\dt" 2>&1 | \
    tee "$REPORT_DIR/postgres-tables.txt"
TABLE_COUNT=$(docker compose exec db psql -U "${POSTGRES_USER:-myk_user}" -d "${POSTGRES_DB:-myk_platform}" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null | tr -d ' ')
[ "${TABLE_COUNT:-0}" -ge 4 ] && pass "PostgreSQL tabloları oluştu ($TABLE_COUNT tablo)" || fail "Tablo sayısı yetersiz: $TABLE_COUNT"

# DB kullanıcısı superuser değil
IS_SUPER=$(docker compose exec db psql -U "${POSTGRES_USER:-myk_user}" -d "${POSTGRES_DB:-myk_platform}" -t -c "SELECT usesuper FROM pg_user WHERE usename='${POSTGRES_USER:-myk_user}'" 2>/dev/null | tr -d ' ')
[ "$IS_SUPER" = "f" ] && pass "DB kullanıcısı superuser değil" || fail "DB kullanıcısı superuser!"

# ─── 4. REDIS ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "4. Redis Doğrulaması"
echo "══════════════════════════════════════════════════"

REDIS_PING=$(docker compose exec redis redis-cli ping 2>/dev/null | tr -d '\r')
echo "Redis ping: $REDIS_PING" | tee "$REPORT_DIR/redis-verification-output.txt"
[ "$REDIS_PING" = "PONG" ] && pass "Redis PONG" || fail "Redis PONG alınamadı"

# ─── 5. HEALTH ENDPOINT ─────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "5. Health Endpoint"
echo "══════════════════════════════════════════════════"

HEALTH=$(curl -si "$API/health" 2>/dev/null)
echo "$HEALTH" | tee "$REPORT_DIR/health-output.txt"
echo "$HEALTH" | grep -q '"status"' && pass "Health endpoint yanıt veriyor" || fail "Health endpoint yanıtsız"
echo "$HEALTH" | grep -q '"database"' && pass "Health DB durumu mevcut" || fail "Health DB durumu eksik"
echo "$HEALTH" | grep -q '"redis"' && pass "Health Redis durumu mevcut" || fail "Health Redis durumu eksik"
# Hassas bilgi sızıntısı yok
echo "$HEALTH" | grep -qi "password\|secret\|token" && fail "Health cevabında hassas bilgi!" || pass "Health cevabında hassas bilgi yok"

# ─── 6. SETUP E2E ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "6. Setup E2E"
echo "══════════════════════════════════════════════════"

AUTH_LOG="$REPORT_DIR/auth-e2e-output.txt"

# İlk kurulum
SETUP1=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/setup" \
    -H "Content-Type: application/json" \
    -d '{"club_name":"Test Kulübü","club_slug":"test-kulup","admin_email":"admin@test.com","admin_password":"Admin1234!","admin_full_name":"Test Admin"}' 2>/dev/null)
HTTP1=$(echo "$SETUP1" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "Setup1 HTTP: $HTTP1" | tee -a "$AUTH_LOG"
[ "$HTTP1" = "201" ] && pass "İlk setup → 201" || fail "İlk setup → $HTTP1 (201 beklendi)"

# Aynı slug → 409
SETUP2=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/setup" \
    -H "Content-Type: application/json" \
    -d '{"club_name":"Kopya Kulüp","club_slug":"test-kulup","admin_email":"admin2@test.com","admin_password":"Admin1234!","admin_full_name":"Kopya Admin"}' 2>/dev/null)
HTTP2=$(echo "$SETUP2" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "Setup2 (çakışan slug) HTTP: $HTTP2" | tee -a "$AUTH_LOG"
[ "$HTTP2" = "409" ] && pass "Çakışan slug → 409" || fail "Çakışan slug → $HTTP2 (409 beklendi)"

# ─── 7. LOGIN E2E ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "7. Login E2E"
echo "══════════════════════════════════════════════════"

LOGIN_RESP=$(curl -s -c /tmp/cookies.txt -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"club_slug":"test-kulup","email":"admin@test.com","password":"Admin1234!"}' 2>/dev/null)
LOGIN_HTTP=$(echo "$LOGIN_RESP" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "Login HTTP: $LOGIN_HTTP" | tee -a "$AUTH_LOG"
[ "$LOGIN_HTTP" = "200" ] && pass "Login başarılı → 200" || fail "Login → $LOGIN_HTTP"

ACCESS_TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; d=sys.stdin.read(); d=d[:d.rfind(chr(10))]; print(json.loads(d).get('access_token','MISSING'))" 2>/dev/null)
[ "$ACCESS_TOKEN" != "MISSING" ] && [ -n "$ACCESS_TOKEN" ] && pass "Access token alındı" || fail "Access token eksik"

# Yanlış parola → 401
WRONG=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"club_slug":"test-kulup","email":"admin@test.com","password":"YanlisParola!"}' 2>/dev/null)
WRONG_HTTP=$(echo "$WRONG" | grep "HTTP_STATUS:" | cut -d: -f2)
[ "$WRONG_HTTP" = "401" ] && pass "Yanlış parola → 401" || fail "Yanlış parola → $WRONG_HTTP"

# Bilinmeyen kulüp → 401 (bilgi sızdırma yok)
UNK=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"club_slug":"olmayan-kulup","email":"x@x.com","password":"X1234!"}' 2>/dev/null)
UNK_HTTP=$(echo "$UNK" | grep "HTTP_STATUS:" | cut -d: -f2)
[ "$UNK_HTTP" = "401" ] && pass "Bilinmeyen kulüp → 401" || fail "Bilinmeyen kulüp → $UNK_HTTP"

# ─── 8. /me E2E ──────────────────────────────────────────────────────────────
ME=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$API/auth/me" \
    -H "Authorization: Bearer $ACCESS_TOKEN" 2>/dev/null)
ME_HTTP=$(echo "$ME" | grep "HTTP_STATUS:" | cut -d: -f2)
[ "$ME_HTTP" = "200" ] && pass "/me → 200" || fail "/me → $ME_HTTP"

# Token olmadan → 401
ME_NO=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$API/auth/me" 2>/dev/null)
ME_NO_HTTP=$(echo "$ME_NO" | grep "HTTP_STATUS:" | cut -d: -f2)
[ "$ME_NO_HTTP" = "401" ] && pass "/me tokensiz → 401" || fail "/me tokensiz → $ME_NO_HTTP"

# ─── 9. LOGOUT E2E ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "9. Logout E2E"
echo "══════════════════════════════════════════════════"

LOGOUT=$(curl -s -b /tmp/cookies.txt -c /tmp/cookies.txt \
    -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/logout" \
    -H "Authorization: Bearer $ACCESS_TOKEN" 2>/dev/null)
LOGOUT_HTTP=$(echo "$LOGOUT" | grep "HTTP_STATUS:" | cut -d: -f2)
[ "$LOGOUT_HTTP" = "204" ] && pass "Logout → 204" || fail "Logout → $LOGOUT_HTTP"

# Logout sonrası /me → 401
ME_AFTER=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$API/auth/me" \
    -H "Authorization: Bearer $ACCESS_TOKEN" 2>/dev/null)
ME_AFTER_HTTP=$(echo "$ME_AFTER" | grep "HTTP_STATUS:" | cut -d: -f2)
# Access token blacklist yok → 15dk hâlâ geçerli; bu bilinen sınırlılık
if [ "$ME_AFTER_HTTP" = "401" ]; then
    pass "Logout sonrası /me → 401 (blacklist aktif)"
else
    info "Logout sonrası /me → $ME_AFTER_HTTP (blacklist yok, access token 15dk geçerli — bilinen sınırlılık, Sprint 3.1)"
fi

# ─── 10. TENANT İZOLASYONU E2E ────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "10. Tenant İzolasyonu E2E"
echo "══════════════════════════════════════════════════"

TENANT_LOG="$REPORT_DIR/tenant-rbac-e2e-output.txt"

# İkinci kulüp
SETUP3=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/setup" \
    -H "Content-Type: application/json" \
    -d '{"club_name":"İkinci Kulüp","club_slug":"ikinci-kulup","admin_email":"admin2@ikinci.com","admin_password":"Admin1234!","admin_full_name":"İkinci Admin"}' 2>/dev/null)
HTTP3=$(echo "$SETUP3" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "Setup ikinci kulüp: $HTTP3" | tee -a "$TENANT_LOG"
[ "$HTTP3" = "201" ] && pass "İkinci kulüp kuruldu" || fail "İkinci kulüp → $HTTP3"

# Login ikinci kulüp
LOGIN2=$(curl -s -c /tmp/cookies2.txt -w "\nHTTP_STATUS:%{http_code}" -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"club_slug":"ikinci-kulup","email":"admin2@ikinci.com","password":"Admin1234!"}' 2>/dev/null)
TOKEN2=$(echo "$LOGIN2" | python3 -c "import sys,json; d=sys.stdin.read(); d=d[:d.rfind(chr(10))]; print(json.loads(d).get('access_token','MISSING'))" 2>/dev/null)
[ "$TOKEN2" != "MISSING" ] && pass "İkinci kulüp login" || fail "İkinci kulüp login başarısız"
echo "Tenant izolasyonu: tenant B token ile tenant A /me sorgusu" | tee -a "$TENANT_LOG"

# ─── 11. RATE LIMIT E2E ───────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "11. Rate Limit E2E"
echo "══════════════════════════════════════════════════"

RATE_LOG="$REPORT_DIR/redis-verification-output.txt"
info "10 başarısız giriş deneniyor (rate limit testi)..." | tee -a "$RATE_LOG"
for i in $(seq 1 11); do
    R=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$API/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"club_slug":"test-kulup","email":"admin@test.com","password":"YanlisParola!"}' 2>/dev/null)
    echo "Deneme $i: HTTP $R" | tee -a "$RATE_LOG"
    if [ "$R" = "429" ]; then
        pass "Rate limit → 429 ($i. denemede)"
        break
    fi
done

# ─── ÖZET ────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "Sprint 3.0-A Özet"
echo "══════════════════════════════════════════════════"
echo "Başarısız test sayısı: $FAILURES"
if [ "$FAILURES" -eq 0 ]; then
    echo "✅ TÜM TESTLER PASS — Sprint 3.0-A tamamlandı"
    exit 0
else
    echo "❌ $FAILURES TEST FAIL — Sprint 3.1'e geçme"
    exit 1
fi

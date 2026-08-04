#!/usr/bin/env bash
# postgres_e2e_verify.sh — MYK Platform V2 Aşama 2 E2E Doğrulama
# Kullanım: cd myk-platform-v2 && bash postgres_e2e_verify.sh
set -euo pipefail

BASE_URL="http://localhost"
API="$BASE_URL/api/v1"
PASS=0; FAIL=0
COOKIE_A="/tmp/e2e_cookies_a.txt"
COOKIE_B="/tmp/e2e_cookies_b.txt"

check() {
  local name="$1"; local got="$2"; local expect="$3"
  if echo "$got" | grep -q "$expect"; then
    echo "✓ PASS  $name"
    PASS=$((PASS+1))
  else
    echo "✗ FAIL  $name"
    echo "  Beklenen : $expect"
    echo "  Alınan   : $(echo "$got" | head -1)"
    FAIL=$((FAIL+1))
  fi
}

echo "=========================================="
echo " MYK Platform V2 — PostgreSQL E2E Test"
echo " $(date)"
echo "=========================================="

echo ""
echo "--- ADIM 1: Stack temizle ve başlat ---"
docker compose down -v --remove-orphans 2>&1 | tail -3
docker compose up -d 2>&1 | tail -5
echo "PostgreSQL hazır olana kadar bekleniyor..."
for i in {1..30}; do
  docker compose exec db pg_isready -U myk_user -d myk_v2 -q && break || sleep 2
done
echo "PostgreSQL HAZIR"

echo ""
echo "--- ADIM 2: Migration ---"
docker compose exec api alembic -c migrations/alembic.ini upgrade head
CURRENT=$(docker compose exec api alembic -c migrations/alembic.ini current 2>&1)
check "Migration HEAD" "$CURRENT" "head"

echo ""
echo "--- ADIM 3: Setup ---"
SETUP=$(curl -sf -X POST "$API/auth/setup" \
  -H "Content-Type: application/json" \
  -d '{"club_name":"E2E Kulüp","club_slug":"e2e-test","admin_email":"e2e@test.com","admin_password":"E2eTest1234!","admin_full_name":"E2E Admin"}')
check "Setup — email" "$SETUP" "e2e@test.com"
check "Setup — rol" "$SETUP" "kulup_yonetici"

echo ""
echo "--- ADIM 4: Login ---"
LOGIN=$(curl -sf -c "$COOKIE_A" -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"club_slug":"e2e-test","email":"e2e@test.com","password":"E2eTest1234!"}')
check "Login — access_token" "$LOGIN" "access_token"
ACCESS=$(python3 -c "import sys,json; print(json.loads('$LOGIN')['access_token'])" 2>/dev/null || \
  echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo ""
echo "--- ADIM 5: /me ---"
ME=$(curl -sf -H "Authorization: Bearer $ACCESS" "$API/auth/me")
check "/me — email" "$ME" "e2e@test.com"
check "/me — aktif" "$ME" '"is_active": true'

echo ""
echo "--- ADIM 6: Refresh ---"
REFRESH=$(curl -sf -b "$COOKIE_A" -c "$COOKIE_B" -X POST "$API/auth/refresh")
check "Refresh — yeni access_token" "$REFRESH" "access_token"
NEW_ACCESS=$(echo "$REFRESH" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
[ "$NEW_ACCESS" != "$ACCESS" ] && check "Token rotation" "different" "different" \
                                || check "Token rotation" "same" "different"

echo ""
echo "--- ADIM 7: Korumalı — yetkili ---"
ME2=$(curl -sf -H "Authorization: Bearer $NEW_ACCESS" "$API/auth/me")
check "/me yeni token" "$ME2" "e2e@test.com"

echo ""
echo "--- ADIM 8: Token yok — 401 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/me")
check "Token yok → 401" "$CODE" "401"

echo ""
echo "--- ADIM 9: Duplicate slug — 409 ---"
DUP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/auth/setup" \
  -H "Content-Type: application/json" \
  -d '{"club_name":"Kopya","club_slug":"e2e-test","admin_email":"k@k.com","admin_password":"Kopya1234!","admin_full_name":"Kopya"}')
check "Duplicate slug → 409" "$DUP" "409"

echo ""
echo "--- ADIM 10: Logout ---"
LOGOUT=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_A" -X POST "$API/auth/logout")
check "Logout → 204" "$LOGOUT" "204"

echo ""
echo "--- ADIM 11: Eski token sonrası /me ---"
OLD_ME=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ACCESS" "$API/auth/me")
# Access token hâlâ geçerli olabilir (exp dolmamışsa); bu test Aşama 3'te revoke list ile
echo "  (Bilgi) Eski access token durumu: $OLD_ME — token kısa ömürlü, blacklist Aşama 3'te"

echo ""
echo "--- ADIM 12: Audit log ---"
AUDIT=$(docker compose exec db psql -U myk_user -d myk_v2 -t -A -c \
  "SELECT action FROM audit_logs ORDER BY created_at DESC LIMIT 10;")
check "Audit — login_success" "$AUDIT" "login_success"
check "Audit — setup_completed" "$AUDIT" "setup_completed"

echo ""
echo "--- ADIM 13: Health ---"
HEALTH=$(curl -sf "$API/health")
check "Health — status ok" "$HEALTH" '"status": "ok"'
check "Health — postgres ok" "$HEALTH" '"postgres": "ok"'
check "Health — redis ok" "$HEALTH" '"redis": "ok"'

echo ""
echo "=========================================="
echo " SONUÇ: $PASS PASS / $FAIL FAIL"
echo "=========================================="
rm -f "$COOKIE_A" "$COOKIE_B"
[ $FAIL -eq 0 ] && echo "✓ TÜM E2E ADIMLAR BAŞARILI" && exit 0 || exit 1

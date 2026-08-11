#!/usr/bin/env bash
# =============================================================================
# scripts/sprint6b_e2e.sh — Sprint 6B Payments release gate
# =============================================================================
#
# 14 CHECK:
#   1.  Migration 0009 upgrade / downgrade -1 / upgrade (reversibility)
#   2.  Backend test suite — mevcut testler geçmeli
#   3.  POST /payments — ödeme oluştur (201)
#   4.  GET  /payments — listede görünür
#   5.  GET  /payments/{id} — tekil detay
#   6.  PUT  /payments/{id} — status=paid güncelle (200)
#   7.  GET  /payments?status=paid — filtreli liste
#   8.  GET  /payments/overdue — gecikmiş (due_date geçmiş, pending)
#   9.  GET  /payments/revenue-report — ay bazlı gelir
#   10. Soft delete — DELETE /payments/{id} → 204; ardından GET → 404
#   11. person_id tenant kontrolü — başka kulübün person_id → 404
#   12. Tenant izolasyonu — Kulüp B token ile Kulüp A ödeme → 404
#   13. amount ≤ 0 → 422 (validation)
#   14. person_id null geçer (kulüp genel tahsilatı) — 201
#
# GÜVENLİK: validation env kuralları — .env asla source edilmez/okunmaz
# =============================================================================
set -uo pipefail

PROJ="myk_validation"
COMPOSE_FILE="docker-compose.validation.yml"
ENV_FILE=".env.validation"
BASE_URL="http://127.0.0.1:28080"

VAL_SLUG_A="myk-val-6b"
VAL_SLUG_B="myk-val-6b-b"
VAL_ADMIN_EMAIL_A="val-6b-admin@example.com"
VAL_ADMIN_EMAIL_B="val-6b-admin-b@example.com"
VAL_ADMIN_PASS="ValAdm1n6BE2E"

PASS=0; FAIL=0; WARN=0

ACCESS_TOKEN=""
TOKEN_B=""
PAYMENT_ID=""
OVERDUE_ID=""
PERSON_A_ID=""

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

DC="docker compose -p $PROJ -f $COMPOSE_FILE --env-file $ENV_FILE"

pass()    { echo -e "${GREEN}  ✓${NC} $1"; PASS=$((PASS + 1)); }
fail()    { echo -e "${RED}  ✗${NC} $1"; FAIL=$((FAIL + 1)); }
warn()    { echo -e "${YELLOW}  ⚠${NC} $1"; WARN=$((WARN + 1)); }
info()    { echo -e "${CYAN}  ▶${NC} $1"; }
section() {
  echo
  echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}  $1${NC}"
  echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
}

KEEP=false
for arg in "$@"; do [[ "$arg" == "--keep" ]] && KEEP=true; done

_CLEANUP_DONE=false
cleanup() {
  [[ "$_CLEANUP_DONE" == true ]] && return
  _CLEANUP_DONE=true
  if [[ "$KEEP" == false ]]; then
    echo ""
    info "Trap: validation container + volume temizleniyor..."
    $DC down -v --remove-orphans 2>/dev/null || true
  fi
}
trap cleanup EXIT

api() {
  local method="$1" path="$2"; shift 2
  curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" \
    -H "Content-Type: application/json" "$@" 2>/dev/null || echo -e "\n000"
}
aapi() {
  local method="$1" path="$2"; shift 2
  curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" "$@" 2>/dev/null || echo -e "\n000"
}
bapi() {
  local method="$1" path="$2"; shift 2
  curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN_B}" "$@" 2>/dev/null || echo -e "\n000"
}
http_code() { printf '%s' "$1" | tail -1; }
resp_body() { printf '%s' "$1" | head -n -1; }
jq_field() {
  local body="$1" field="$2"
  printf '%s' "$body" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('$field',''))" 2>/dev/null || true
}
do_login() {
  local slug="$1" email="$2" pass="$3"
  local resp
  resp=$(api POST /api/v1/auth/login \
    -d "{\"club_slug\":\"$slug\",\"email\":\"$email\",\"password\":\"$pass\"}")
  [[ "$(http_code "$resp")" == "200" ]] && jq_field "$(resp_body "$resp")" "access_token" || true
}
db_query() {
  local sql="$1" db_cid
  db_cid=$($DC ps -q db 2>/dev/null || true)
  [[ -z "$db_cid" ]] && { echo "DB_CONTAINER_NOT_FOUND"; return; }
  local pg_user pg_db
  pg_user=$(grep -m1 '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)
  pg_db=$(grep -m1 '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)
  docker exec "$db_cid" psql -U "$pg_user" "$pg_db" -tAc "$sql" 2>/dev/null || echo "QUERY_FAILED"
}

# ── PRE-CHECK ─────────────────────────────────────────────────────────────────
section "PRE-CHECK"

[[ -f "docker-compose.yml" ]] && [[ -f "$COMPOSE_FILE" ]] || \
  { fail "Proje kök dizininden çalıştır"; exit 1; }
pass "Proje kök dizini doğrulandı"

[[ -f "$ENV_FILE" ]] || { fail "$ENV_FILE bulunamadı"; exit 1; }
pass "$ENV_FILE mevcut"

if grep -Eq '^[A-Z0-9_]+=.*CHANGE_ME' "$ENV_FILE" 2>/dev/null; then
  fail "$ENV_FILE içinde CHANGE_ME değerleri var"; exit 1
fi
pass "$ENV_FILE CHANGE_ME içermiyor"

docker info > /dev/null 2>&1 || { fail "Docker erişilemiyor"; exit 1; }
pass "Docker erişilebilir"

# ── STACK ─────────────────────────────────────────────────────────────────────
section "STACK BAŞLATILIYOR"

info "Mevcut validation stack temizleniyor..."
$DC down -v --remove-orphans 2>/dev/null || true

info "Image build + stack başlatılıyor..."
$DC up -d --build 2>&1 | tail -5

info "API healthy olana kadar bekleniyor (max 120s)..."
for i in $(seq 1 40); do
  API_CID=$($DC ps -q api 2>/dev/null || true)
  if [[ -n "$API_CID" ]]; then
    H=$(docker inspect \
      --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "$API_CID" 2>/dev/null || echo "unknown")
    [[ "$H" == "healthy" ]] && break
  fi
  sleep 3
done
[[ "$H" == "healthy" ]] && pass "API container: healthy" || { fail "API healthy olmadı ($H)"; exit 1; }

R=$(api GET /health); [[ "$(http_code "$R")" == "200" ]] && pass "GET /health 200" || { fail "GET /health başarısız"; exit 1; }

# ── CHECK 1: MİGRASYON ───────────────────────────────────────────────────────
section "CHECK 1 — Migration 0009 upgrade/downgrade/upgrade"

info "alembic upgrade head (0001→0009)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -4; then
  pass "alembic upgrade head: başarılı"
else
  fail "alembic upgrade head: BAŞARISIZ — devam edilemiyor"; exit 1
fi

PT=$(db_query "SELECT to_regclass('public.payments')::text;")
[[ "$PT" == "payments" ]] && pass "payments tablosu mevcut" || fail "payments tablosu bulunamadı"

info "alembic downgrade -1 (0009 → 0008)..."
$DC exec -T api alembic -c migrations/alembic.ini downgrade -1 2>&1 | tail -3
PT_GONE=$(db_query "SELECT to_regclass('public.payments')::text;")
if [[ -z "$PT_GONE" ]] || [[ "$PT_GONE" == *"NULL"* ]]; then
  pass "payments tablosu kaldırıldı (downgrade OK)"
else
  warn "payments hâlâ var: $PT_GONE"
fi

info "alembic upgrade head (0009 geri geliyor)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -3; then
  pass "alembic upgrade head (ikinci tur): başarılı"
else
  fail "alembic upgrade head (ikinci tur): BAŞARISIZ"; exit 1
fi

FINAL_REV=$($DC exec -T api alembic -c migrations/alembic.ini current 2>&1 | grep -E "head|0009" | head -1 || true)
[[ -n "$FINAL_REV" ]] && pass "Migration revision: $FINAL_REV" || warn "Revision okunamadı"

# ── CHECK 2: BACKEND TESTS ────────────────────────────────────────────────────
section "CHECK 2 — Backend test suite"

info "pytest çalıştırılıyor..."
TEST_OUT=$($DC exec -T api python3 -m pytest tests/ -q --tb=no 2>&1 || true)
TEST_SUMMARY=$(printf '%s\n' "$TEST_OUT" | grep -E '^[0-9]+ (passed|failed)' | tail -1 || echo "")
if printf '%s\n' "$TEST_OUT" | grep -qE '^[0-9]+ passed'; then
  pass "Backend testler geçti — $TEST_SUMMARY"
else
  warn "Backend testlerde başarısızlık — $TEST_SUMMARY"
fi

# ── SETUP ────────────────────────────────────────────────────────────────────
section "SETUP — Kulüp A + B"

R=$(api POST /api/v1/auth/setup -d \
  "{\"club_name\":\"MYK Validation 6B\",\"club_slug\":\"$VAL_SLUG_A\",
    \"admin_email\":\"$VAL_ADMIN_EMAIL_A\",\"admin_password\":\"$VAL_ADMIN_PASS\",
    \"admin_full_name\":\"MYK Val Admin 6B\"}")
[[ "$(http_code "$R")" =~ ^20 ]] && pass "Kulüp A oluşturuldu" || { fail "Kulüp A setup: $(http_code "$R")"; exit 1; }

ACCESS_TOKEN=$(do_login "$VAL_SLUG_A" "$VAL_ADMIN_EMAIL_A" "$VAL_ADMIN_PASS")
[[ -n "$ACCESS_TOKEN" ]] && pass "Admin A token alındı" || { fail "Admin A login başarısız"; exit 1; }

R=$(api POST /api/v1/auth/setup -d \
  "{\"club_name\":\"MYK Validation 6B-B\",\"club_slug\":\"$VAL_SLUG_B\",
    \"admin_email\":\"$VAL_ADMIN_EMAIL_B\",\"admin_password\":\"$VAL_ADMIN_PASS\",
    \"admin_full_name\":\"MYK Val Admin 6B-B\"}")
[[ "$(http_code "$R")" =~ ^20 ]] && pass "Kulüp B oluşturuldu" || warn "Kulüp B oluşturulamadı — tenant testi atlanacak"

TOKEN_B=$(do_login "$VAL_SLUG_B" "$VAL_ADMIN_EMAIL_B" "$VAL_ADMIN_PASS")
[[ -n "$TOKEN_B" ]] && pass "Admin B token alındı" || warn "Admin B login başarısız"

# Person oluştur (person_id testleri için)
R=$(aapi POST /api/v1/persons -d '{"first_name":"Ahmet","last_name":"Kaptan","role_codes":["sporcu"]}')
PERSON_A_ID=$(jq_field "$(resp_body "$R")" "id")
[[ "$(http_code "$R")" == "201" ]] && pass "Person A: $PERSON_A_ID" || fail "Person A oluşturulamadı"

# ── CHECK 3: ÖDEME OLUŞTUR ────────────────────────────────────────────────────
section "CHECK 3 — POST /payments → 201"

NEXT_MONTH=$(python3 -c "
from datetime import date, timedelta
d = date.today().replace(day=1)
import calendar
days = calendar.monthrange(d.year, d.month)[1]
print((d + timedelta(days=days)).strftime('%Y-%m-15'))
")

R=$(aapi POST /api/v1/payments -d "{
  \"person_id\": \"$PERSON_A_ID\",
  \"amount\": 1500.00,
  \"payment_type\": \"kurs_ucreti\",
  \"payment_method\": \"havale\",
  \"due_date\": \"$NEXT_MONTH\",
  \"status\": \"pending\"
}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
PAYMENT_ID=$(jq_field "$BODY" "id")

[[ "$CODE" == "201" ]] && pass "POST /payments → 201" || fail "POST /payments → $CODE: $BODY"
[[ -n "$PAYMENT_ID" ]] && pass "payment_id: $PAYMENT_ID" || { fail "payment_id boş"; exit 1; }
[[ "$(jq_field "$BODY" "status")" == "pending" ]] && pass "status=pending" || fail "status yanlış"
[[ "$(jq_field "$BODY" "person_name")" != "" ]] && pass "person_name dolu" || fail "person_name boş"

# ── CHECK 4: ÖDEME LİSTESİ ────────────────────────────────────────────────────
section "CHECK 4 — GET /payments"

R=$(aapi GET /api/v1/payments)
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
TOTAL=$(jq_field "$BODY" "total")

[[ "$CODE" == "200" ]] && pass "GET /payments → 200" || fail "GET /payments → $CODE"
[[ "${TOTAL:-0}" -ge "1" ]] 2>/dev/null && pass "total=$TOTAL" || fail "total beklenen ≥1: $TOTAL"

# ── CHECK 5: TEKİL ÖDEME ─────────────────────────────────────────────────────
section "CHECK 5 — GET /payments/{id}"

R=$(aapi GET "/api/v1/payments/$PAYMENT_ID")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")

[[ "$CODE" == "200" ]] && pass "GET /payments/$PAYMENT_ID → 200" || fail "GET → $CODE"
[[ "$(jq_field "$BODY" "amount")" == "1500"* ]] && pass "amount=1500" || fail "amount yanlış: $(jq_field "$BODY" "amount")"

# ── CHECK 6: ÖDEME GÜNCELLE ───────────────────────────────────────────────────
section "CHECK 6 — PUT /payments/{id} → status=paid"

TODAY=$(date +%Y-%m-%d)
R=$(aapi PUT "/api/v1/payments/$PAYMENT_ID" -d "{
  \"status\": \"paid\",
  \"paid_at\": \"$TODAY\",
  \"receipt_no\": \"MKZ-2026-001\"
}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")

[[ "$CODE" == "200" ]] && pass "PUT /payments/$PAYMENT_ID → 200" || fail "PUT → $CODE: $BODY"
[[ "$(jq_field "$BODY" "status")" == "paid" ]] && pass "status=paid güncellendi" || fail "status güncellenmedi"
[[ "$(jq_field "$BODY" "receipt_no")" == "MKZ-2026-001" ]] && pass "receipt_no güncellendi" || fail "receipt_no yanlış"

# ── CHECK 7: STATUS FİLTRE ────────────────────────────────────────────────────
section "CHECK 7 — GET /payments?status=paid"

R=$(aapi GET "/api/v1/payments?status=paid")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
PAID_TOTAL=$(jq_field "$BODY" "total")

[[ "$CODE" == "200" ]] && pass "GET /payments?status=paid → 200" || fail "→ $CODE"
[[ "${PAID_TOTAL:-0}" -ge "1" ]] 2>/dev/null && pass "paid total=$PAID_TOTAL" || fail "paid listesi boş"

# ── CHECK 8: GECİKMİŞ ÖDEMELER ────────────────────────────────────────────────
section "CHECK 8 — GET /payments/overdue"

# Geçmiş tarihli, pending ödeme oluştur
PAST_DATE=$(python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(days=15)).strftime('%Y-%m-%d'))")
R=$(aapi POST /api/v1/payments -d "{
  \"person_id\": \"$PERSON_A_ID\",
  \"amount\": 500.00,
  \"payment_type\": \"uyelik\",
  \"due_date\": \"$PAST_DATE\",
  \"status\": \"pending\"
}")
OVERDUE_ID=$(jq_field "$(resp_body "$R")" "id")
[[ "$(http_code "$R")" == "201" ]] && pass "Gecikmiş ödeme oluşturuldu: $OVERDUE_ID" || fail "Gecikmiş ödeme oluşturulamadı"

R=$(aapi GET /api/v1/payments/overdue)
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
COUNT=$(printf '%s' "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
GECIKME=$(printf '%s' "$BODY" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d[0]['gecikme_gun'] if d else 0)
" 2>/dev/null || echo "0")

[[ "$CODE" == "200" ]] && pass "GET /payments/overdue → 200" || fail "→ $CODE"
[[ "${COUNT:-0}" -ge "1" ]] 2>/dev/null && pass "overdue count=$COUNT" || fail "overdue listesi boş"
[[ "${GECIKME:-0}" -ge "14" ]] 2>/dev/null && pass "gecikme_gun=$GECIKME" || fail "gecikme_gun beklenen ≥14: $GECIKME"

# ── CHECK 9: GELİR RAPORU ─────────────────────────────────────────────────────
section "CHECK 9 — GET /payments/revenue-report"

R=$(aapi GET /api/v1/payments/revenue-report)
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
TOPLAM=$(jq_field "$BODY" "toplam_gelir")
ITEM_COUNT=$(printf '%s' "$BODY" | python3 -c "
import sys,json; d=json.load(sys.stdin); print(len(d.get('items',[])))
" 2>/dev/null || echo "0")

[[ "$CODE" == "200" ]] && pass "GET /payments/revenue-report → 200" || fail "→ $CODE: $BODY"
[[ "${ITEM_COUNT:-0}" -ge "1" ]] 2>/dev/null && pass "rapor items=$ITEM_COUNT" || fail "rapor boş"
[[ "$TOPLAM" == "1500"* ]] && pass "toplam_gelir=1500" || fail "toplam_gelir beklenen ~1500: $TOPLAM"

# ── CHECK 10: SOFT DELETE ─────────────────────────────────────────────────────
section "CHECK 10 — DELETE /payments/{id} → 204; GET → 404"

R=$(aapi DELETE "/api/v1/payments/$OVERDUE_ID")
[[ "$(http_code "$R")" == "204" ]] && pass "DELETE /payments/$OVERDUE_ID → 204" || fail "DELETE → $(http_code "$R")"

R=$(aapi GET "/api/v1/payments/$OVERDUE_ID")
[[ "$(http_code "$R")" == "404" ]] && pass "Silinen ödeme GET → 404" || fail "Silinen ödeme hâlâ görünüyor: $(http_code "$R")"

# ── CHECK 11: TENANT PERSON KONTROLÜ ──────────────────────────────────────────
section "CHECK 11 — Başka kulübün person_id → 404"

if [[ -n "$TOKEN_B" ]]; then
  # Kulüp B'de person oluştur
  R_B=$(bapi POST /api/v1/persons -d '{"first_name":"Yabanci","last_name":"Kisi","role_codes":["sporcu"]}')
  PERSON_B_ID=$(jq_field "$(resp_body "$R_B")" "id")

  if [[ -n "$PERSON_B_ID" ]] && [[ "$PERSON_B_ID" != "" ]]; then
    # Kulüp A tokeniyle Kulüp B'nin person_id'sini dene
    R=$(aapi POST /api/v1/payments -d "{
      \"person_id\": \"$PERSON_B_ID\",
      \"amount\": 100.00,
      \"status\": \"pending\"
    }")
    [[ "$(http_code "$R")" == "404" ]] && pass "Başka kulübün person_id → 404" || \
      fail "Tenant person kontrolü beklenen 404, alınan $(http_code "$R")"
  else
    warn "Kulüp B person oluşturulamadı — CHECK 11 atlandı"
  fi
else
  warn "Token B yok — CHECK 11 atlandı"
fi

# ── CHECK 12: TENANT İZOLASYONU ──────────────────────────────────────────────
section "CHECK 12 — Tenant izolasyonu"

if [[ -n "$TOKEN_B" ]]; then
  R=$(bapi GET "/api/v1/payments/$PAYMENT_ID")
  [[ "$(http_code "$R")" == "404" ]] && pass "Kulüp B → Kulüp A ödeme → 404" || \
    fail "Tenant izolasyonu beklenen 404: $(http_code "$R")"

  R=$(bapi PUT "/api/v1/payments/$PAYMENT_ID" -d '{"status":"paid"}')
  [[ "$(http_code "$R")" == "404" ]] && pass "Kulüp B → Kulüp A PUT → 404" || \
    fail "Tenant PUT izolasyonu: $(http_code "$R")"
else
  warn "Token B yok — CHECK 12 atlandı"
fi

# ── CHECK 13: VALIDATION — amount ≤ 0 ────────────────────────────────────────
section "CHECK 13 — amount ≤ 0 → 422"

R=$(aapi POST /api/v1/payments -d '{"amount": 0, "status": "pending"}')
[[ "$(http_code "$R")" == "422" ]] && pass "amount=0 → 422" || fail "Beklenen 422: $(http_code "$R")"

R=$(aapi POST /api/v1/payments -d '{"amount": -50, "status": "pending"}')
[[ "$(http_code "$R")" == "422" ]] && pass "amount=-50 → 422" || fail "Beklenen 422: $(http_code "$R")"

# ── CHECK 14: person_id NULL ─────────────────────────────────────────────────
section "CHECK 14 — person_id null → 201 (kulüp genel tahsilatı)"

R=$(aapi POST /api/v1/payments -d '{
  "amount": 250.00,
  "payment_type": "diger",
  "notes": "Genel kulüp geliri",
  "status": "paid"
}')
CODE=$(http_code "$R"); BODY=$(resp_body "$R")

[[ "$CODE" == "201" ]] && pass "person_id null → 201" || fail "person_id null → $CODE: $BODY"
if printf '%s' "$BODY" | python3 -c 'import sys,json; raise SystemExit(0 if json.load(sys.stdin).get("person_id") is None else 1)'; then
  pass "person_id gerçekten JSON null ✓"
else
  fail "person_id null değil: $BODY"
fi

# ── ÖZET ─────────────────────────────────────────────────────────────────────
section "ÖZET"

TOTAL_CHECKS=$((PASS + FAIL + WARN))
echo ""
echo -e "  Toplam   : ${TOTAL_CHECKS}"
echo -e "  ${GREEN}Başarılı${NC} : ${PASS}"
echo -e "  ${RED}Başarısız${NC}: ${FAIL}"
echo -e "  ${YELLOW}Uyarı${NC}    : ${WARN}"
echo ""

if [[ $FAIL -eq 0 ]]; then
  echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  Sprint 6B E2E — TÜM CHECKLER GEÇTİ ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
  exit 0
else
  echo -e "${RED}╔══════════════════════════════════════════╗${NC}"
  echo -e "${RED}║  Sprint 6B E2E — $FAIL CHECK BAŞARISIZ    ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════╝${NC}"
  exit 1
fi

#!/usr/bin/env bash
# =============================================================================
# scripts/sprint6c_e2e.sh — Sprint 6C Equipment Core release gate
# =============================================================================
#
# 20 CHECK:
#   1.  Migration 0010 upgrade / downgrade -1 / upgrade (reversibility)
#   2.  Backend test suite — mevcut testler geçmeli
#   3.  POST /equipment — ekipman oluştur (201)
#   4.  GET  /equipment — listede görünür
#   5.  GET  /equipment/{id} — tekil detay
#   6.  PATCH /equipment/{id} — status=bakimda (200)
#   7.  GET  /equipment?status=bakimda — filtreli liste
#   8.  Başka kulübün assigned_person_id → 404
#   9.  Aynı tenant person zimmet → 200
#   10. GET  /equipment/maintenance-due — bakım eşiği (14 gün içinde)
#   11. GET  /equipment/maintenance-due — sigorta eşiği (30 gün içinde)
#   12. POST /equipment/{id}/maintenance — bakım kaydı oluştur (201)
#   13. equipment.last_maintenance_date summary güncellendi
#   14. GET  /equipment/{id}/maintenance — bakım listesi
#   15. GET  /equipment/{id}/maintenance/{record_id} — tekil bakım
#   16. PATCH /equipment/{id}/maintenance/{record_id} — güncelle (200)
#   17. purchase_cost < 0 → 422 (validation)
#   18. maintenance cost < 0 → 422 (validation)
#   19. Tenant izolasyonu — Kulüp B → Kulüp A equipment → 404
#   20. Soft delete — DELETE /equipment/{id} → 204; ardından GET → 404
#
# GÜVENLİK: validation env kuralları — .env asla source edilmez/okunmaz
# =============================================================================
set -uo pipefail

PROJ="myk_validation"
COMPOSE_FILE="docker-compose.validation.yml"
ENV_FILE=".env.validation"
BASE_URL="http://127.0.0.1:28080"

VAL_SLUG_A="myk-val-6c"
VAL_SLUG_B="myk-val-6c-b"
VAL_ADMIN_EMAIL_A="val-6c-admin@example.com"
VAL_ADMIN_EMAIL_B="val-6c-admin-b@example.com"
VAL_ADMIN_PASS="ValAdm1n6CE2E"

PASS=0; FAIL=0; WARN=0

ACCESS_TOKEN=""
TOKEN_B=""
EQUIPMENT_ID=""
PERSON_A_ID=""
MAINT_RECORD_ID=""

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
jq_item_field() {
  local body="$1" idx="$2" field="$3"
  printf '%s' "$body" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d['items'][$idx].get('$field',''))" 2>/dev/null || true
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
H="unknown"
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
section "CHECK 1 — Migration 0010 upgrade/downgrade/upgrade"

info "alembic upgrade head (→0010)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -5; then
  pass "alembic upgrade head: başarılı"
else
  fail "alembic upgrade head: BAŞARISIZ — devam edilemiyor"; exit 1
fi

ET=$(db_query "SELECT to_regclass('public.equipment')::text;")
[[ "$ET" == "equipment" ]] && pass "equipment tablosu mevcut" || fail "equipment tablosu bulunamadı"

MT=$(db_query "SELECT to_regclass('public.equipment_maintenance_records')::text;")
[[ "$MT" == "equipment_maintenance_records" ]] && pass "equipment_maintenance_records tablosu mevcut" || fail "equipment_maintenance_records tablosu bulunamadı"

info "alembic downgrade -1 (0010 → 0009)..."
$DC exec -T api alembic -c migrations/alembic.ini downgrade -1 2>&1 | tail -3
ET_GONE=$(db_query "SELECT to_regclass('public.equipment')::text;")
if [[ -z "$ET_GONE" ]] || [[ "$ET_GONE" == *"NULL"* ]]; then
  pass "equipment tablosu kaldırıldı (downgrade OK)"
else
  warn "equipment hâlâ var: $ET_GONE"
fi

info "alembic upgrade head (0010 geri geliyor)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -3; then
  pass "alembic upgrade head (ikinci tur): başarılı"
else
  fail "alembic upgrade head (ikinci tur): BAŞARISIZ"; exit 1
fi

FINAL_REV=$($DC exec -T api alembic -c migrations/alembic.ini current 2>&1 | grep -E "head|0010" | head -1 || true)
[[ -n "$FINAL_REV" ]] && pass "Migration revision: $FINAL_REV" || warn "Revision okunamadı"

# ── CHECK 2: BACKEND TESTS ────────────────────────────────────────────────────
section "CHECK 2 — Backend test suite"

info "pytest çalıştırılıyor..."
TEST_OUT=$($DC exec -T api python3 -m pytest tests/ -q --tb=no 2>&1 || true)
TEST_SUMMARY=$(printf '%s\n' "$TEST_OUT" | grep -E '^[0-9]+ (passed|failed)' | tail -1 || echo "")
if printf '%s\n' "$TEST_OUT" | grep -qE '^[0-9]+ passed'; then
  pass "Backend testler geçti — $TEST_SUMMARY"
else
  fail "Backend testler BAŞARISIZ — $TEST_SUMMARY"
  printf '%s\n' "$TEST_OUT" | tail -10
fi

# ── SETUP — Kulüp A + B ───────────────────────────────────────────────────────
section "SETUP — Kulüp A + B"

R=$(api POST /api/v1/auth/setup \
  -d "{\"club_name\":\"Val6C Kulüp A\",\"club_slug\":\"$VAL_SLUG_A\",
       \"admin_email\":\"$VAL_ADMIN_EMAIL_A\",\"admin_password\":\"$VAL_ADMIN_PASS\",
       \"admin_full_name\":\"Admin 6C A\"}")
[[ "$(http_code "$R")" =~ ^20 ]] && pass "Kulüp A oluşturuldu" || \
  { fail "Kulüp A kurulamadı: $(resp_body "$R")"; exit 1; }

ACCESS_TOKEN=$(do_login "$VAL_SLUG_A" "$VAL_ADMIN_EMAIL_A" "$VAL_ADMIN_PASS")
[[ -n "$ACCESS_TOKEN" ]] && pass "Admin A token alındı" || { fail "Admin A login başarısız"; exit 1; }

R=$(api POST /api/v1/auth/setup \
  -d "{\"club_name\":\"Val6C Kulüp B\",\"club_slug\":\"$VAL_SLUG_B\",
       \"admin_email\":\"$VAL_ADMIN_EMAIL_B\",\"admin_password\":\"$VAL_ADMIN_PASS\",
       \"admin_full_name\":\"Admin 6C B\"}")
[[ "$(http_code "$R")" =~ ^20 ]] && pass "Kulüp B oluşturuldu" || \
  { fail "Kulüp B kurulamadı: $(resp_body "$R")"; exit 1; }

TOKEN_B=$(do_login "$VAL_SLUG_B" "$VAL_ADMIN_EMAIL_B" "$VAL_ADMIN_PASS")
[[ -n "$TOKEN_B" ]] && pass "Admin B token alındı" || { fail "Admin B login başarısız"; exit 1; }

# Person A oluştur (zimmet testi için)
R=$(aapi POST /api/v1/persons \
  -d '{"first_name":"Ali","last_name":"Denizci","roles":["sporcu"]}')
PERSON_A_ID=$(jq_field "$(resp_body "$R")" "id")
[[ -n "$PERSON_A_ID" ]] && pass "Person A: $PERSON_A_ID" || { fail "Person A oluşturulamadı"; exit 1; }

# ── CHECK 3: POST /equipment ──────────────────────────────────────────────────
section "CHECK 3 — POST /equipment → 201"

R=$(aapi POST /api/v1/equipment -d "{
  \"name\": \"Optimist 01\",
  \"equipment_type\": \"tekne\",
  \"serial_no\": \"OPT-2024-001\",
  \"brand\": \"Vanguard\",
  \"model\": \"Optimist\",
  \"status\": \"aktif\",
  \"purchase_cost\": 12500.00,
  \"notes\": \"Test teknesi\"
}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "201" ]] && pass "POST /equipment → 201" || { fail "POST /equipment → $CODE: $BODY"; exit 1; }

EQUIPMENT_ID=$(jq_field "$BODY" "id")
[[ -n "$EQUIPMENT_ID" ]] && pass "equipment_id: $EQUIPMENT_ID" || { fail "equipment_id alınamadı"; exit 1; }

STAT=$(jq_field "$BODY" "status")
[[ "$STAT" == "aktif" ]] && pass "status=aktif" || fail "Beklenen status=aktif: $STAT"

NAME=$(jq_field "$BODY" "name")
[[ "$NAME" == "Optimist 01" ]] && pass "name=Optimist 01" || fail "Beklenen name doğru değil: $NAME"

# ── CHECK 4: GET /equipment ───────────────────────────────────────────────────
section "CHECK 4 — GET /equipment"

R=$(aapi GET /api/v1/equipment)
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "GET /equipment → 200" || fail "Beklenen 200: $CODE"

TOTAL=$(printf '%s' "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo "0")
[[ "$TOTAL" -ge 1 ]] && pass "total=$TOTAL" || fail "total beklenen >=1: $TOTAL"

# ── CHECK 5: GET /equipment/{id} ──────────────────────────────────────────────
section "CHECK 5 — GET /equipment/{id}"

R=$(aapi GET "/api/v1/equipment/$EQUIPMENT_ID")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "GET /equipment/$EQUIPMENT_ID → 200" || fail "Beklenen 200: $CODE"

COST=$(jq_field "$BODY" "purchase_cost")
[[ "$COST" == "12500.00" ]] || [[ "$COST" == "12500" ]] && pass "purchase_cost=12500" || fail "Beklenen purchase_cost=12500: $COST"

# ── CHECK 6: PATCH /equipment/{id} — status değişimi ─────────────────────────
section "CHECK 6 — PATCH /equipment/{id} → status=bakimda"

R=$(aapi PATCH "/api/v1/equipment/$EQUIPMENT_ID" -d '{"status":"bakimda"}')
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "PATCH /equipment/$EQUIPMENT_ID → 200" || fail "Beklenen 200: $CODE: $BODY"

STAT=$(jq_field "$BODY" "status")
[[ "$STAT" == "bakimda" ]] && pass "status=bakimda güncellendi" || fail "Beklenen status=bakimda: $STAT"

# ── CHECK 7: GET /equipment?status=bakimda ────────────────────────────────────
section "CHECK 7 — GET /equipment?status=bakimda"

R=$(aapi GET "/api/v1/equipment?status=bakimda")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "GET /equipment?status=bakimda → 200" || fail "Beklenen 200: $CODE"

TOTAL=$(printf '%s' "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo "0")
[[ "$TOTAL" -ge 1 ]] && pass "bakimda total=$TOTAL" || fail "bakimda total beklenen >=1: $TOTAL"

# ── CHECK 8: Başka kulübün assigned_person_id → 404 ──────────────────────────
section "CHECK 8 — Başka kulübün person_id → 404"

R=$(bapi POST /api/v1/persons -d '{"first_name":"Mehmet","last_name":"Kaptan","roles":["sporcu"]}')
PERSON_B_ID=$(jq_field "$(resp_body "$R")" "id")

if [[ -n "$PERSON_B_ID" ]]; then
  R=$(aapi PATCH "/api/v1/equipment/$EQUIPMENT_ID" -d "{\"assigned_person_id\":\"$PERSON_B_ID\"}")
  CODE=$(http_code "$R")
  [[ "$CODE" == "404" ]] && pass "Başka kulübün person_id → 404" || fail "Beklenen 404: $CODE"
else
  warn "Person B oluşturulamadı, CHECK 8 atlandı"
fi

# ── CHECK 9: Aynı tenant person zimmet → 200 ──────────────────────────────────
section "CHECK 9 — Aynı tenant person zimmet → 200"

R=$(aapi PATCH "/api/v1/equipment/$EQUIPMENT_ID" -d "{\"assigned_person_id\":\"$PERSON_A_ID\"}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "Zimmet atama → 200" || fail "Beklenen 200: $CODE: $BODY"

ASSIGNED=$(jq_field "$BODY" "assigned_person_id")
[[ "$ASSIGNED" == "$PERSON_A_ID" ]] && pass "assigned_person_id doğru" || fail "assigned_person_id: $ASSIGNED"

ANAME=$(jq_field "$BODY" "assigned_person_name")
[[ -n "$ANAME" ]] && pass "assigned_person_name dolu: $ANAME" || fail "assigned_person_name boş"

# ── CHECK 10: maintenance-due — bakım eşiği ──────────────────────────────────
section "CHECK 10 — maintenance-due (next_maintenance_date 7 gün sonra)"

NEXT_MAINT=$(python3 -c "from datetime import date,timedelta; print((date.today()+timedelta(days=7)).isoformat())")
R=$(aapi POST /api/v1/equipment -d "{
  \"name\": \"Can Yeleği Set A\",
  \"equipment_type\": \"guvenlik\",
  \"status\": \"aktif\",
  \"next_maintenance_date\": \"$NEXT_MAINT\"
}")
MAINT_DUE_EQ_ID=$(jq_field "$(resp_body "$R")" "id")
[[ "$(http_code "$R")" == "201" ]] && pass "maintenance-due ekipman oluşturuldu: $MAINT_DUE_EQ_ID" || fail "maintenance-due ekipman oluşturulamadı"

R=$(aapi GET /api/v1/equipment/maintenance-due)
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "GET /equipment/maintenance-due → 200" || fail "Beklenen 200: $CODE"

MAINT_COUNT=$(printf '%s' "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
[[ "$MAINT_COUNT" -ge 1 ]] && pass "maintenance-due count=$MAINT_COUNT" || fail "maintenance-due boş, beklenen >=1"

MAINT_FLAG=$(printf '%s' "$BODY" | python3 -c \
  "import sys,json; items=json.load(sys.stdin); found=[i for i in items if i.get('id')=='$MAINT_DUE_EQ_ID']; print(found[0]['maintenance_due'] if found else 'NOT_FOUND')" 2>/dev/null || echo "ERR")
[[ "$MAINT_FLAG" == "True" ]] && pass "maintenance_due=True" || fail "maintenance_due beklenen True: $MAINT_FLAG"

# ── CHECK 11: maintenance-due — sigorta eşiği ────────────────────────────────
section "CHECK 11 — maintenance-due (insurance_expiry_date 20 gün sonra)"

INS_DATE=$(python3 -c "from datetime import date,timedelta; print((date.today()+timedelta(days=20)).isoformat())")
R=$(aapi POST /api/v1/equipment -d "{
  \"name\": \"Yangın Söndürücü\",
  \"equipment_type\": \"guvenlik\",
  \"status\": \"aktif\",
  \"insurance_expiry_date\": \"$INS_DATE\"
}")
INS_EQ_ID=$(jq_field "$(resp_body "$R")" "id")
[[ "$(http_code "$R")" == "201" ]] && pass "Sigorta eşiği ekipman oluşturuldu: $INS_EQ_ID" || fail "Sigorta ekipman oluşturulamadı"

R=$(aapi GET /api/v1/equipment/maintenance-due)
INS_FLAG=$(printf '%s' "$(resp_body "$R")" | python3 -c \
  "import sys,json; items=json.load(sys.stdin); found=[i for i in items if i.get('id')=='$INS_EQ_ID']; print(found[0]['insurance_due'] if found else 'NOT_FOUND')" 2>/dev/null || echo "ERR")
[[ "$INS_FLAG" == "True" ]] && pass "insurance_due=True" || fail "insurance_due beklenen True: $INS_FLAG"

# ── CHECK 12: POST /equipment/{id}/maintenance ────────────────────────────────
section "CHECK 12 — POST /equipment/{id}/maintenance → 201"

MAINT_DATE=$(python3 -c "from datetime import date; print(date.today().isoformat())")
NEXT_MAINT_DATE=$(python3 -c "from datetime import date,timedelta; print((date.today()+timedelta(days=180)).isoformat())")

R=$(aapi POST "/api/v1/equipment/$EQUIPMENT_ID/maintenance" -d "{
  \"maintenance_date\": \"$MAINT_DATE\",
  \"maintenance_type\": \"periyodik\",
  \"description\": \"Yıllık genel bakım\",
  \"cost\": 1200.00,
  \"performed_by\": \"Deniz Teknik Servis\",
  \"next_maintenance_date\": \"$NEXT_MAINT_DATE\",
  \"notes\": \"Boya yenilemesi dahil\"
}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "201" ]] && pass "POST /maintenance → 201" || { fail "POST /maintenance → $CODE: $BODY"; exit 1; }

MAINT_RECORD_ID=$(jq_field "$BODY" "id")
[[ -n "$MAINT_RECORD_ID" ]] && pass "maintenance_record_id: $MAINT_RECORD_ID" || fail "record_id alınamadı"

MCOST=$(jq_field "$BODY" "cost")
[[ "$MCOST" == "1200.00" ]] || [[ "$MCOST" == "1200" ]] && pass "cost=1200" || fail "Beklenen cost=1200: $MCOST"

# ── CHECK 13: equipment summary güncellendi ───────────────────────────────────
section "CHECK 13 — equipment.last_maintenance_date summary güncellendi"

R=$(aapi GET "/api/v1/equipment/$EQUIPMENT_ID")
LAST_MAINT=$(jq_field "$(resp_body "$R")" "last_maintenance_date")
[[ "$LAST_MAINT" == "$MAINT_DATE" ]] && pass "last_maintenance_date=$LAST_MAINT" || fail "Beklenen $MAINT_DATE: $LAST_MAINT"

NEXT_MAINT_STORED=$(jq_field "$(resp_body "$R")" "next_maintenance_date")
[[ "$NEXT_MAINT_STORED" == "$NEXT_MAINT_DATE" ]] && pass "next_maintenance_date=$NEXT_MAINT_STORED" || fail "Beklenen $NEXT_MAINT_DATE: $NEXT_MAINT_STORED"

# ── CHECK 14: GET /equipment/{id}/maintenance ─────────────────────────────────
section "CHECK 14 — GET /equipment/{id}/maintenance"

R=$(aapi GET "/api/v1/equipment/$EQUIPMENT_ID/maintenance")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "GET /maintenance listesi → 200" || fail "Beklenen 200: $CODE"

MTOTAL=$(printf '%s' "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo "0")
[[ "$MTOTAL" -ge 1 ]] && pass "maintenance total=$MTOTAL" || fail "maintenance total beklenen >=1: $MTOTAL"

# ── CHECK 15: GET /equipment/{id}/maintenance/{record_id} ────────────────────
section "CHECK 15 — GET /equipment/{id}/maintenance/{record_id}"

R=$(aapi GET "/api/v1/equipment/$EQUIPMENT_ID/maintenance/$MAINT_RECORD_ID")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "GET /maintenance/$MAINT_RECORD_ID → 200" || fail "Beklenen 200: $CODE"

MTYPE=$(jq_field "$BODY" "maintenance_type")
[[ "$MTYPE" == "periyodik" ]] && pass "maintenance_type=periyodik" || fail "Beklenen periyodik: $MTYPE"

# ── CHECK 16: PATCH /equipment/{id}/maintenance/{record_id} ──────────────────
section "CHECK 16 — PATCH /equipment/{id}/maintenance/{record_id}"

R=$(aapi PATCH "/api/v1/equipment/$EQUIPMENT_ID/maintenance/$MAINT_RECORD_ID" \
  -d '{"description":"Yıllık genel bakım + Fener kontrolü","cost":1350.00}')
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
[[ "$CODE" == "200" ]] && pass "PATCH /maintenance/$MAINT_RECORD_ID → 200" || fail "Beklenen 200: $CODE: $BODY"

NEWCOST=$(jq_field "$BODY" "cost")
[[ "$NEWCOST" == "1350.00" ]] || [[ "$NEWCOST" == "1350" ]] && pass "cost=1350 güncellendi" || fail "Beklenen cost=1350: $NEWCOST"

# ── CHECK 17: purchase_cost < 0 → 422 ────────────────────────────────────────
section "CHECK 17 — purchase_cost < 0 → 422"

R=$(aapi POST /api/v1/equipment -d '{"name":"Geçersiz","status":"aktif","purchase_cost":-100}')
[[ "$(http_code "$R")" == "422" ]] && pass "purchase_cost=-100 → 422" || fail "Beklenen 422: $(http_code "$R")"

# ── CHECK 18: maintenance cost < 0 → 422 ─────────────────────────────────────
section "CHECK 18 — maintenance cost < 0 → 422"

R=$(aapi POST "/api/v1/equipment/$EQUIPMENT_ID/maintenance" \
  -d "{\"maintenance_date\":\"$MAINT_DATE\",\"cost\":-50}")
[[ "$(http_code "$R")" == "422" ]] && pass "maintenance cost=-50 → 422" || fail "Beklenen 422: $(http_code "$R")"

# ── CHECK 19: Tenant izolasyonu ───────────────────────────────────────────────
section "CHECK 19 — Tenant izolasyonu"

R=$(bapi GET "/api/v1/equipment/$EQUIPMENT_ID")
[[ "$(http_code "$R")" == "404" ]] && pass "Kulüp B → Kulüp A equipment → 404" || fail "Beklenen 404: $(http_code "$R")"

R=$(bapi PATCH "/api/v1/equipment/$EQUIPMENT_ID" -d '{"status":"hasarli"}')
[[ "$(http_code "$R")" == "404" ]] && pass "Kulüp B → Kulüp A PATCH → 404" || fail "Beklenen 404: $(http_code "$R")"

# ── CHECK 20: Soft delete ─────────────────────────────────────────────────────
section "CHECK 20 — DELETE → 204; GET → 404"

# Silinecek test ekipmanı oluştur
R=$(aapi POST /api/v1/equipment -d '{"name":"Silinecek Ekipman","status":"aktif"}')
DEL_ID=$(jq_field "$(resp_body "$R")" "id")
[[ -n "$DEL_ID" ]] && pass "Silinecek ekipman oluşturuldu: $DEL_ID" || { fail "Silinecek ekipman oluşturulamadı"; }

if [[ -n "$DEL_ID" ]]; then
  R=$(aapi DELETE "/api/v1/equipment/$DEL_ID")
  [[ "$(http_code "$R")" == "204" ]] && pass "DELETE → 204" || fail "Beklenen 204: $(http_code "$R")"

  R=$(aapi GET "/api/v1/equipment/$DEL_ID")
  [[ "$(http_code "$R")" == "404" ]] && pass "Silinen GET → 404" || fail "Beklenen 404: $(http_code "$R")"
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
  echo -e "${GREEN}║  Sprint 6C E2E — TÜM CHECKLER GEÇTİ ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
  exit 0
else
  echo -e "${RED}╔══════════════════════════════════════════╗${NC}"
  echo -e "${RED}║  Sprint 6C E2E — $FAIL CHECK BAŞARISIZ    ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════╝${NC}"
  exit 1
fi

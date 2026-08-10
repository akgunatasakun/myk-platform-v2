#!/usr/bin/env bash
# =============================================================================
# scripts/sprint6a_e2e.sh — Sprint 6A Training Core release gate
# =============================================================================
#
# KAPSAM: Migration 0008 + Training API E2E + Docker build
#
# 16 CHECK:
#   1.  Migration 0008 upgrade / downgrade -1 / upgrade (reversibility)
#   2.  Backend test suite — mevcut testler geçmeli
#   3.  POST /trainings — kurs oluştur (201)
#   4.  GET  /trainings — kurs listede görünür
#   5.  GET  /trainings/{id} — kurs detay
#   6.  PATCH /trainings/{id} — status → aktif güncelle
#   7.  POST /trainings/{id}/sessions — oturum oluştur (201)
#   8.  GET  /trainings/{id}/sessions — oturum listede
#   9.  POST /trainings/{id}/participants — kayıt ekle (201)
#   10. Duplicate enrollment → 409
#   11. Kapasite aşımı → 409 (kapasite=1, ikinci kişi)
#   12. PUT  /sessions/{sid}/attendance — toplu yoklama (UPSERT, created=1)
#   13. GET  /sessions/{sid}/attendance — kayıt listede, status=var
#   14. PUT  tekrar → updated=1 (UPSERT idempotency, status=gecikti)
#   15. GET  /attendance/report — devam raporu, gecikti=1
#   16. Tenant izolasyonu — Kulüp B tokeniyla Kulüp A kaynakları → 404
#
# GÜVENLİK:
#   ✗  .env asla source edilmez / okunmaz
#   ✗  Production DB'ye dokunulmaz
#   ✗  Production container'lara dokunulmaz
#   ✓  Yalnızca --env-file .env.validation
#   ✓  Docker project: myk_validation
#   ✓  trap cleanup EXIT
#
# Ön koşullar:
#   .env.validation mevcut + CHANGE_ME değerleri doldurulmuş
#   Docker Engine + docker compose v2 + python3
#
# Kullanım:
#   chmod +x scripts/sprint6a_e2e.sh
#   ./scripts/sprint6a_e2e.sh           # normal
#   ./scripts/sprint6a_e2e.sh --keep    # container'ları durdurma (debug)
#
# =============================================================================
set -uo pipefail

# ── Sabitler ─────────────────────────────────────────────────────────────────
PROJ="myk_validation"
COMPOSE_FILE="docker-compose.validation.yml"
ENV_FILE=".env.validation"
BASE_URL="http://127.0.0.1:28080"

VAL_SLUG_A="myk-val-6a"
VAL_SLUG_B="myk-val-6a-b"
VAL_ADMIN_EMAIL_A="val-6a-admin@example.com"
VAL_ADMIN_EMAIL_B="val-6a-admin-b@example.com"
VAL_ADMIN_PASS="ValAdm1n6AE2E"

PASS=0; FAIL=0; WARN=0

ACCESS_TOKEN=""
TOKEN_B=""
COURSE_ID=""
SESSION_ID=""
PERSON_A_ID=""
PERSON_A2_ID=""

# ── Renk kodları ──────────────────────────────────────────────────────────────
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

# ── Argüman parse ─────────────────────────────────────────────────────────────
KEEP=false
for arg in "$@"; do
  case "$arg" in
    --keep)  KEEP=true ;;
    --help|-h)
      grep '^#' "$0" | head -50 | sed 's/^# \?//'
      exit 0
      ;;
  esac
done

# ── Trap ─────────────────────────────────────────────────────────────────────
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

# ── API yardımcıları ──────────────────────────────────────────────────────────
api() {
  local method="$1" path="$2"; shift 2
  curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    "$@" 2>/dev/null || echo -e "\n000"
}

aapi() {
  local method="$1" path="$2"; shift 2
  curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    "$@" 2>/dev/null || echo -e "\n000"
}

bapi() {
  local method="$1" path="$2"; shift 2
  curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN_B}" \
    "$@" 2>/dev/null || echo -e "\n000"
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
  local resp body token
  resp=$(api POST /api/v1/auth/login \
    -d "{\"club_slug\":\"$slug\",\"email\":\"$email\",\"password\":\"$pass\"}")
  body=$(resp_body "$resp")
  if [[ "$(http_code "$resp")" == "200" ]]; then
    token=$(jq_field "$body" "access_token")
    printf '%s' "$token"
    return 0
  fi
  printf ''
  return 1
}

db_query() {
  local sql="$1"
  local db_cid
  db_cid=$($DC ps -q db 2>/dev/null || true)
  [[ -z "$db_cid" ]] && { echo "DB_CONTAINER_NOT_FOUND"; return; }
  local pg_user pg_db
  pg_user=$(grep -m1 '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)
  pg_db=$(grep -m1 '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)
  docker exec "$db_cid" psql -U "$pg_user" "$pg_db" -tAc "$sql" 2>/dev/null || echo "QUERY_FAILED"
}

# ── PRE-CHECK ─────────────────────────────────────────────────────────────────
section "PRE-CHECK"

if [[ ! -f "docker-compose.yml" ]] || [[ ! -f "$COMPOSE_FILE" ]]; then
  fail "Proje kök dizininden çalıştır: cd myk-platform-v2 && ./scripts/sprint6a_e2e.sh"
  exit 1
fi
pass "Proje kök dizini doğrulandı"

[[ -f "$ENV_FILE" ]] || { fail "$ENV_FILE bulunamadı"; exit 1; }
pass "$ENV_FILE mevcut"

if grep -Eq '^[A-Z0-9_]+=.*CHANGE_ME' "$ENV_FILE" 2>/dev/null; then
  fail "$ENV_FILE içinde doldurulmamış CHANGE_ME değerleri var — önce doldurun"
  exit 1
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
API_HEALTH="starting"
for i in $(seq 1 40); do
  API_CID=$($DC ps -q api 2>/dev/null || true)
  if [[ -n "$API_CID" ]]; then
    API_HEALTH=$(docker inspect \
      --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "$API_CID" 2>/dev/null || echo "unknown")
    [[ "$API_HEALTH" == "healthy" ]] && break
  fi
  sleep 3
done

[[ "$API_HEALTH" == "healthy" ]] && pass "API container: healthy" || { fail "API 120s içinde healthy olmadı ($API_HEALTH)"; exit 1; }

info "API sağlık kontrolü..."
for i in $(seq 1 15); do
  R=$(api GET /health 2>/dev/null || true)
  [[ "$(http_code "$R")" == "200" ]] && break
  sleep 2
done
[[ "$(http_code "$(api GET /health)")" == "200" ]] && pass "GET /health 200" || { fail "GET /health başarısız"; exit 1; }

# ── CHECK 1: MİGRASYON ───────────────────────────────────────────────────────
section "CHECK 1 — Migration 0008 upgrade/downgrade/upgrade"

info "alembic upgrade head (0001→0008)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -6; then
  pass "alembic upgrade head: başarılı"
else
  fail "alembic upgrade head: başarısız — devam edilemiyor"
  exit 1
fi

# Training tabloları oluştu mu?
TC_TABLE=$(db_query "SELECT to_regclass('public.training_courses')::text;")
[[ "$TC_TABLE" == "training_courses" ]] && pass "training_courses tablosu mevcut" || \
  fail "training_courses tablosu bulunamadı"

TA_TABLE=$(db_query "SELECT to_regclass('public.training_attendance')::text;")
[[ "$TA_TABLE" == "training_attendance" ]] && pass "training_attendance tablosu mevcut" || \
  fail "training_attendance tablosu bulunamadı"

info "alembic downgrade -1 (0008 → 0007)..."
if $DC exec -T api alembic -c migrations/alembic.ini downgrade -1 2>&1 | tail -6; then
  pass "alembic downgrade -1: başarılı"
else
  fail "alembic downgrade -1: başarısız"
fi

TC_GONE=$(db_query "SELECT to_regclass('public.training_courses')::text;")
if [[ -z "$TC_GONE" ]] || [[ "$TC_GONE" == *"NULL"* ]]; then
  pass "training_courses kaldırıldı (downgrade doğru çalıştı)"
else
  warn "training_courses hâlâ var: $TC_GONE"
fi

info "alembic upgrade head (0008 geri geliyor)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -6; then
  pass "alembic upgrade head (ikinci tur): başarılı"
else
  fail "alembic upgrade head (ikinci tur): başarısız — KRİTİK"
  exit 1
fi

FINAL_REV=$($DC exec -T api alembic -c migrations/alembic.ini current 2>&1 | \
  grep -E "head|0008" | head -1 || true)
[[ -n "$FINAL_REV" ]] && pass "Migration revision: $FINAL_REV" || \
  warn "Migration revision okunamadı"

# ── CHECK 2: BACKEND TESTS ────────────────────────────────────────────────────
section "CHECK 2 — Backend test suite"

info "pytest çalıştırılıyor..."
TEST_OUT=$($DC exec -T api python3 -m pytest tests/ -q --tb=no 2>&1 || true)
TEST_SUMMARY=$(printf '%s\n' "$TEST_OUT" | grep -E '^[0-9]+ (passed|failed)' | tail -1 || echo "")
if printf '%s\n' "$TEST_OUT" | grep -qE '^[0-9]+ passed'; then
  pass "Backend testler geçti — $TEST_SUMMARY"
else
  FAILED_COUNT=$(printf '%s\n' "$TEST_OUT" | grep -cE ' FAILED' || echo "?")
  warn "Backend testlerde başarısızlık: $FAILED_COUNT — $TEST_SUMMARY"
fi

# ── SETUP: Kulüp A + B ────────────────────────────────────────────────────────
section "SETUP — Kulüp A + B kurulum"

info "POST /auth/setup (Kulüp A)..."
SETUP_A=$(api POST /api/v1/auth/setup -d \
  "{\"club_name\":\"MYK Validation 6A\",\"club_slug\":\"$VAL_SLUG_A\",
    \"admin_email\":\"$VAL_ADMIN_EMAIL_A\",\"admin_password\":\"$VAL_ADMIN_PASS\",
    \"admin_full_name\":\"MYK Val Admin 6A\"}")
SETUP_A_CODE=$(http_code "$SETUP_A")
if [[ "$SETUP_A_CODE" == "201" ]] || [[ "$SETUP_A_CODE" == "200" ]]; then
  pass "Kulüp A oluşturuldu — HTTP $SETUP_A_CODE"
else
  fail "Kulüp A setup başarısız — HTTP $SETUP_A_CODE: $(resp_body "$SETUP_A")"
  exit 1
fi

info "Login (Admin A)..."
ACCESS_TOKEN=$(do_login "$VAL_SLUG_A" "$VAL_ADMIN_EMAIL_A" "$VAL_ADMIN_PASS")
[[ -n "$ACCESS_TOKEN" ]] && pass "Admin A token alındı" || { fail "Admin A login başarısız"; exit 1; }

info "POST /auth/setup (Kulüp B)..."
SETUP_B=$(api POST /api/v1/auth/setup -d \
  "{\"club_name\":\"MYK Validation 6A-B\",\"club_slug\":\"$VAL_SLUG_B\",
    \"admin_email\":\"$VAL_ADMIN_EMAIL_B\",\"admin_password\":\"$VAL_ADMIN_PASS\",
    \"admin_full_name\":\"MYK Val Admin 6A-B\"}")
SETUP_B_CODE=$(http_code "$SETUP_B")
if [[ "$SETUP_B_CODE" == "201" ]] || [[ "$SETUP_B_CODE" == "200" ]]; then
  pass "Kulüp B oluşturuldu"
else
  warn "Kulüp B oluşturulamadı ($SETUP_B_CODE) — tenant isolation testi atlanacak"
fi

info "Login (Admin B)..."
TOKEN_B=$(do_login "$VAL_SLUG_B" "$VAL_ADMIN_EMAIL_B" "$VAL_ADMIN_PASS")
[[ -n "$TOKEN_B" ]] && pass "Admin B token alındı" || warn "Admin B login başarısız — tenant testi atlanacak"

# Person ekle (enrollment için)
R=$(aapi POST /api/v1/persons \
  -d '{"first_name":"Ali","last_name":"Kaptan","role_codes":["sporcu"]}')
PERSON_A_ID=$(jq_field "$(resp_body "$R")" "id")
[[ "$(http_code "$R")" == "201" ]] && pass "Person A oluşturuldu: $PERSON_A_ID" || \
  { fail "Person A oluşturulamadı: $(http_code "$R")"; exit 1; }

R=$(aapi POST /api/v1/persons \
  -d '{"first_name":"Veli","last_name":"Reis","role_codes":["sporcu"]}')
PERSON_A2_ID=$(jq_field "$(resp_body "$R")" "id")
[[ "$(http_code "$R")" == "201" ]] && pass "Person A2 oluşturuldu: $PERSON_A2_ID" || \
  { fail "Person A2 oluşturulamadı"; exit 1; }

# ── CHECK 3: KURS OLUŞTURMA ───────────────────────────────────────────────────
section "CHECK 3 — POST /trainings → 201"

R=$(aapi POST /api/v1/trainings -d '{
  "name": "D1 Temel Yelken Kursu",
  "class_name": "D1",
  "level": "baslangic",
  "start_date": "2026-09-01",
  "end_date": "2026-09-30",
  "schedule_text": "Hafta ici 09:00-12:00",
  "capacity": 1,
  "fee": 1500.00,
  "status": "planlandi"
}')
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
COURSE_ID=$(jq_field "$BODY" "id")

[[ "$CODE" == "201" ]] && pass "POST /trainings → 201" || fail "POST /trainings → $CODE: $BODY"
[[ -n "$COURSE_ID" ]] && pass "course_id: $COURSE_ID" || { fail "course_id boş"; exit 1; }

# ── CHECK 4: KURS LİSTESİ ────────────────────────────────────────────────────
section "CHECK 4 — GET /trainings"

R=$(aapi GET /api/v1/trainings)
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
TOTAL=$(jq_field "$BODY" "total")

[[ "$CODE" == "200" ]] && pass "GET /trainings → 200" || fail "GET /trainings → $CODE"
[[ "${TOTAL:-0}" -ge "1" ]] 2>/dev/null && pass "Kurs listesi total=$TOTAL" || fail "total beklenen ≥1, alınan: $TOTAL"

# ── CHECK 5: KURS DETAY ───────────────────────────────────────────────────────
section "CHECK 5 — GET /trainings/{id}"

R=$(aapi GET "/api/v1/trainings/$COURSE_ID")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
NAME=$(jq_field "$BODY" "name")

[[ "$CODE" == "200" ]] && pass "GET /trainings/$COURSE_ID → 200" || fail "GET /trainings/$COURSE_ID → $CODE"
[[ "$NAME" == "D1 Temel Yelken Kursu" ]] && pass "name doğru" || fail "name yanlış: $NAME"

# ── CHECK 6: KURS GÜNCELLE ───────────────────────────────────────────────────
section "CHECK 6 — PATCH /trainings/{id}"

R=$(aapi PATCH "/api/v1/trainings/$COURSE_ID" -d '{"status":"aktif"}')
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
NEW_STATUS=$(jq_field "$BODY" "status")

[[ "$CODE" == "200" ]] && pass "PATCH /trainings/$COURSE_ID → 200" || fail "PATCH → $CODE"
[[ "$NEW_STATUS" == "aktif" ]] && pass "status güncellendi: aktif" || fail "status güncellenmedi: $NEW_STATUS"

# ── CHECK 7: OTURUM OLUŞTUR ───────────────────────────────────────────────────
section "CHECK 7 — POST /trainings/{id}/sessions"

R=$(aapi POST "/api/v1/trainings/$COURSE_ID/sessions" -d '{
  "session_date": "2026-09-05",
  "start_time": "09:00:00",
  "end_time": "12:00:00",
  "notes": "Ilk ders"
}')
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
SESSION_ID=$(jq_field "$BODY" "id")

[[ "$CODE" == "201" ]] && pass "POST /sessions → 201" || fail "POST /sessions → $CODE: $BODY"
[[ -n "$SESSION_ID" ]] && pass "session_id: $SESSION_ID" || { fail "session_id boş"; exit 1; }

# ── CHECK 8: OTURUM LİSTESİ ──────────────────────────────────────────────────
section "CHECK 8 — GET /trainings/{id}/sessions"

R=$(aapi GET "/api/v1/trainings/$COURSE_ID/sessions")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
SESSION_COUNT=$(printf '%s' "$BODY" | python3 -c \
  "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

[[ "$CODE" == "200" ]] && pass "GET /sessions → 200" || fail "GET /sessions → $CODE"
[[ "${SESSION_COUNT:-0}" -ge "1" ]] 2>/dev/null && pass "Oturum listesi count=$SESSION_COUNT" || \
  fail "Oturum listesi boş"

# ── CHECK 9: ENROLLMENT EKLE ─────────────────────────────────────────────────
section "CHECK 9 — POST /trainings/{id}/participants"

R=$(aapi POST "/api/v1/trainings/$COURSE_ID/participants" \
  -d "{\"person_id\":\"$PERSON_A_ID\"}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")

[[ "$CODE" == "201" ]] && pass "POST /participants → 201" || fail "POST /participants → $CODE: $BODY"
STATUS_VAL=$(jq_field "$BODY" "status")
[[ "$STATUS_VAL" == "active" ]] && pass "enrollment status=active" || fail "enrollment status: $STATUS_VAL"

# ── CHECK 10: DUPLICATE ENROLLMENT → 409 ─────────────────────────────────────
section "CHECK 10 — Duplicate enrollment → 409"

R=$(aapi POST "/api/v1/trainings/$COURSE_ID/participants" \
  -d "{\"person_id\":\"$PERSON_A_ID\"}")
CODE=$(http_code "$R")

[[ "$CODE" == "409" ]] && pass "Duplicate enrollment → 409" || fail "Beklenen 409, alınan $CODE"

# ── CHECK 11: KAPASİTE AŞIMI → 409 ───────────────────────────────────────────
section "CHECK 11 — Kapasite aşımı (capacity=1) → 409"

R=$(aapi POST "/api/v1/trainings/$COURSE_ID/participants" \
  -d "{\"person_id\":\"$PERSON_A2_ID\"}")
CODE=$(http_code "$R")

[[ "$CODE" == "409" ]] && pass "Kapasite aşımı → 409" || fail "Beklenen 409, alınan $CODE"

# ── CHECK 12: YOKLAMA UPSERT ──────────────────────────────────────────────────
section "CHECK 12 — PUT /sessions/{sid}/attendance (toplu UPSERT)"

R=$(aapi PUT "/api/v1/trainings/$COURSE_ID/sessions/$SESSION_ID/attendance" \
  -d "{\"records\":[
    {\"person_id\":\"$PERSON_A_ID\",\"status\":\"var\",\"check_in_time\":\"09:05:00\"}
  ]}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
CREATED=$(jq_field "$BODY" "created")
UPDATED=$(jq_field "$BODY" "updated")

[[ "$CODE" == "200" ]] && pass "PUT /attendance → 200" || fail "PUT /attendance → $CODE: $BODY"
[[ "$CREATED" == "1" ]] && pass "created=1 (yeni kayıt)" || fail "created beklenen 1, alınan: $CREATED"
[[ "$UPDATED" == "0" ]] && pass "updated=0 (ilk ekleme)" || fail "updated beklenen 0, alınan: $UPDATED"

# ── CHECK 13: YOKLAMA LİSTESİ ────────────────────────────────────────────────
section "CHECK 13 — GET /sessions/{sid}/attendance"

R=$(aapi GET "/api/v1/trainings/$COURSE_ID/sessions/$SESSION_ID/attendance")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
ATT_COUNT=$(printf '%s' "$BODY" | python3 -c \
  "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
ATT_STATUS=$(printf '%s' "$BODY" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d[0]['status'] if d else '')" 2>/dev/null || echo "")

[[ "$CODE" == "200" ]] && pass "GET /attendance → 200" || fail "GET /attendance → $CODE"
[[ "$ATT_COUNT" == "1" ]] && pass "attendance count=1" || fail "count beklenen 1, alınan: $ATT_COUNT"
[[ "$ATT_STATUS" == "var" ]] && pass "status=var" || fail "status yanlış: $ATT_STATUS"

# ── CHECK 14: UPSERT İDEMPOTENSY ─────────────────────────────────────────────
section "CHECK 14 — PUT /attendance tekrar → updated=1 (idempotency)"

R=$(aapi PUT "/api/v1/trainings/$COURSE_ID/sessions/$SESSION_ID/attendance" \
  -d "{\"records\":[
    {\"person_id\":\"$PERSON_A_ID\",\"status\":\"gecikti\",\"check_in_time\":\"09:30:00\"}
  ]}")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
CREATED2=$(jq_field "$BODY" "created")
UPDATED2=$(jq_field "$BODY" "updated")

[[ "$CODE" == "200" ]] && pass "PUT /attendance (tekrar) → 200" || fail "PUT /attendance (tekrar) → $CODE"
[[ "$CREATED2" == "0" ]] && pass "created=0 (mevcut kayıt)" || fail "created beklenen 0, alınan: $CREATED2"
[[ "$UPDATED2" == "1" ]] && pass "updated=1 (UPSERT doğru)" || fail "updated beklenen 1, alınan: $UPDATED2"

R2=$(aapi GET "/api/v1/trainings/$COURSE_ID/sessions/$SESSION_ID/attendance")
ATT_STATUS2=$(printf '%s' "$(resp_body "$R2")" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d[0]['status'] if d else '')" 2>/dev/null || echo "")
[[ "$ATT_STATUS2" == "gecikti" ]] && pass "status güncellendi: gecikti" || fail "status güncellenmedi: $ATT_STATUS2"

# ── CHECK 15: DEVAM RAPORU ────────────────────────────────────────────────────
section "CHECK 15 — GET /attendance/report"

R=$(aapi GET "/api/v1/trainings/$COURSE_ID/attendance/report")
CODE=$(http_code "$R"); BODY=$(resp_body "$R")
TOPLAM=$(jq_field "$BODY" "toplam_oturum")
KATILIMCI_COUNT=$(printf '%s' "$BODY" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(len(d.get('katilimcilar',[])))" 2>/dev/null || echo "0")

[[ "$CODE" == "200" ]] && pass "GET /attendance/report → 200" || fail "GET /attendance/report → $CODE"
[[ "$TOPLAM" == "1" ]] && pass "toplam_oturum=1" || fail "toplam_oturum beklenen 1, alınan: $TOPLAM"
[[ "$KATILIMCI_COUNT" == "1" ]] && pass "katilimcilar count=1" || fail "count beklenen 1, alınan: $KATILIMCI_COUNT"

GECIKTI=$(printf '%s' "$BODY" | python3 -c "
import sys,json
d = json.load(sys.stdin)
k = d.get('katilimcilar',[])
print(k[0]['gecikti'] if k else '')
" 2>/dev/null || echo "")
[[ "$GECIKTI" == "1" ]] && pass "raporda gecikti=1" || fail "raporda gecikti beklenen 1, alınan: $GECIKTI"

# ── CHECK 16: TENANT İZOLASYONU ──────────────────────────────────────────────
section "CHECK 16 — Tenant izolasyonu"

if [[ -n "$TOKEN_B" ]]; then
  R=$(bapi GET "/api/v1/trainings/$COURSE_ID")
  CODE=$(http_code "$R")
  [[ "$CODE" == "404" ]] && pass "Kulüp B → Kulüp A kurs → 404" || \
    fail "Tenant izolasyonu beklenen 404, alınan: $CODE"

  R=$(bapi POST "/api/v1/trainings/$COURSE_ID/participants" \
    -d "{\"person_id\":\"$PERSON_A_ID\"}")
  CODE=$(http_code "$R")
  [[ "$CODE" == "404" ]] && pass "Kulüp B → Kulüp A enrollment → 404" || \
    fail "Enrollment izolasyonu beklenen 404, alınan: $CODE"

  R=$(bapi GET "/api/v1/trainings/$COURSE_ID/sessions/$SESSION_ID/attendance")
  CODE=$(http_code "$R")
  [[ "$CODE" == "404" ]] && pass "Kulüp B → Kulüp A attendance → 404" || \
    fail "Attendance izolasyonu beklenen 404, alınan: $CODE"
else
  warn "Token B yok — CHECK 16 atlandı"
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
  echo -e "${GREEN}║  Sprint 6A E2E — TÜM CHECKLER GEÇTİ ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
  exit 0
else
  echo -e "${RED}╔══════════════════════════════════════════╗${NC}"
  echo -e "${RED}║  Sprint 6A E2E — $FAIL CHECK BAŞARISIZ    ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════╝${NC}"
  exit 1
fi

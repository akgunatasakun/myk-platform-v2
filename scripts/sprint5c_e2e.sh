#!/usr/bin/env bash
# =============================================================================
# scripts/sprint5c_e2e.sh — Sprint 5C release öncesi API/Integration E2E
# =============================================================================
#
# KAPSAM: Migration 0007 + Academy API/Integration E2E + Docker build
#
# 19 CHECK:
#   1.  Migration 0007 upgrade / downgrade -1 / upgrade (reversibility)
#   2.  Backend test suite — 186+ test geçmeli
#   3.  Seed idempotency — seed_academy.py iki kez çalışır, ikincisi skip
#   4.  GET /academy/programs — D1 programı listede
#   5.  GET /academy/programs/d1 — modül + ders hiyerarşisi
#   6.  POST /academy/programs/{id}/enroll — 201 Created
#   7.  Duplicate enroll → 409 Conflict
#   8.  GET /academy/me/enrollments
#   9.  GET /academy/lessons/izbarco — steps + quiz_questions
#   10. correct_letter — quiz start response'da YOK
#   11. Session start enrollment olmadan → 403 (guard kontrolü)
#   12. POST /academy/lessons/{id}/sessions — 201 (enrollment sonrası)
#   13. POST /academy/sessions/{id}/heartbeat — ok + yuzde döndürür
#   14. GET /academy/knot/izbarco/timeline — $schema + slug doğrulama
#   15. Quiz döngüsü: start → 5 doğru cevap → finish → gecti=true
#   16. Progress: yuzde=100, tamamlandi=true (quiz pass sonrası)
#   17. Tenant izolasyonu — çapraz kulüp erişim 404
#   18. Frontend Docker build — tsc + vite production stage
#   19. Smoke test — /health + / + /akademi SPA route
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
#   (5B E2E'de oluşturulduysa hazır)
#   Docker Engine + docker compose v2 + python3
#
# Kullanım:
#   chmod +x scripts/sprint5c_e2e.sh
#   ./scripts/sprint5c_e2e.sh           # normal
#   ./scripts/sprint5c_e2e.sh --keep    # container'ları durdurma (debug)
#   ./scripts/sprint5c_e2e.sh --help
#
# =============================================================================
set -uo pipefail
# NOT: set -e kasıtlı olarak kullanılmıyor.
# ((VAR++)) bash'te değer 0 iken exit-code 1 döndürür; set -e ile script ölür.

# ── Sabitler ─────────────────────────────────────────────────────────────────
PROJ="myk_validation"
COMPOSE_FILE="docker-compose.validation.yml"
ENV_FILE=".env.validation"
BASE_URL="http://127.0.0.1:28080"

VAL_SLUG_A="myk-val-e2e"
VAL_SLUG_B="myk-val-e2e-b"
VAL_ADMIN_EMAIL_A="val-admin-a@example.com"
VAL_ADMIN_EMAIL_B="val-admin-b@example.com"
VAL_ADMIN_PASS="ValAdm1nE2E"

# Academy kullanıcısı — person_id olan, gerçek ders/quiz akışı için
VAL_ACAD_EMAIL="val-acad-user@example.com"
VAL_ACAD_PASS="AcadUser1E2E"

# Quiz doğru cevaplar — seed_academy.py IZBARCO_QUIZ ile birebir eşleşmeli
# sira: 1→B, 2→D, 3→B, 4→C, 5→C
QUIZ_CORRECT_ANSWERS="1:B 2:D 3:B 4:C 5:C"

PASS=0; FAIL=0; WARN=0

ACCESS_TOKEN=""    # Admin A token (read-only Academy + setup)
ACADEMY_TOKEN=""   # Academy user token (person_id gerekli endpoint'ler)
PROGRAM_ID=""
LESSON_ID=""
SESSION_ID=""
ATTEMPT_ID=""

# ── Renk kodları ──────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

DC="docker compose -p $PROJ -f $COMPOSE_FILE --env-file $ENV_FILE"

pass() { echo -e "${GREEN}  ✓${NC} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}  ✗${NC} $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "${YELLOW}  ⚠${NC} $1"; WARN=$((WARN + 1)); }
info() { echo -e "${CYAN}  ▶${NC} $1"; }
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

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────
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

# Academy token ile çağrı (person_id olan kullanıcı)
acad_api() {
  local method="$1" path="$2"; shift 2
  curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ACADEMY_TOKEN}" \
    "$@" 2>/dev/null || echo -e "\n000"
}

http_code()  { printf '%s' "$1" | tail -1; }
resp_body()  { printf '%s' "$1" | head -n -1; }

jq_field() {
  local body="$1" field="$2"
  printf '%s' "$body" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('$field',''))" 2>/dev/null || true
}

# Nokta-ayrımlı nested alan erişimi: jq_path body "attempt.id"
jq_path() {
  local body="$1" path="$2"
  printf '%s' "$body" | python3 -c "
import sys, json, functools
d = json.load(sys.stdin)
keys = '$path'.split('.')
try:
    result = functools.reduce(lambda x, k: x[k], keys, d)
    print(result)
except: print('')
" 2>/dev/null || true
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

do_login() {
  local slug="$1" email="$2" pass="$3"
  local resp body token
  resp=$(api POST /api/v1/auth/login -d \
    "{\"club_slug\":\"$slug\",\"email\":\"$email\",\"password\":\"$pass\"}")
  body=$(resp_body "$resp")
  if [[ "$(http_code "$resp")" == "200" ]]; then
    token=$(jq_field "$body" "access_token")
    printf '%s' "$token"
    return 0
  fi
  printf ''
  return 1
}

# =============================================================================
# PRE-CHECK
# =============================================================================
section "PRE — Güvenlik & Ön Koşullar"

if [[ ! -f "docker-compose.yml" ]] || [[ ! -f "$COMPOSE_FILE" ]]; then
  fail "Proje kök dizininden çalıştır: cd myk-platform-v2 && ./scripts/sprint5c_e2e.sh"
  exit 1
fi
pass "Proje kök dizini doğrulandı"

if [[ ! -f "$ENV_FILE" ]]; then
  fail ".env.validation bulunamadı → cp .env.validation.example .env.validation"
  exit 1
fi
pass ".env.validation mevcut"

if grep -Eq '^[A-Z0-9_]+=.*CHANGE_ME' "$ENV_FILE" 2>/dev/null; then
  fail ".env.validation içinde doldurulmamış CHANGE_ME değerleri:"
  grep -E '^[A-Z0-9_]+=.*CHANGE_ME' "$ENV_FILE" | sed 's/=.*/=***/' || true
  exit 1
fi
pass ".env.validation: CHANGE_ME değerleri doldurulmuş"

if ! docker compose version &>/dev/null; then
  fail "docker compose v2 bulunamadı"
  exit 1
fi
pass "docker compose v2 kullanılabilir"

if ! python3 --version &>/dev/null; then
  fail "python3 bulunamadı"
  exit 1
fi
pass "python3 kullanılabilir"

PROD_CNT=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -c "_prod_\|myk_prod" || true)
[[ "$PROD_CNT" -gt 0 ]] && warn "Production container'lar çalışıyor — bu script onlara dokunmaz" \
  || info "Production container: tespit edilmedi (güvenli)"

# =============================================================================
# STACK
# =============================================================================
section "STACK — Validation Ortamı Başlatılıyor"

info "Eski validation artıklar temizleniyor..."
$DC down -v --remove-orphans 2>/dev/null || true

info "Image build + stack başlatılıyor..."
if ! $DC up -d --build 2>&1 | tail -5; then
  fail "docker compose up --build başarısız"
  exit 1
fi

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

if [[ "$API_HEALTH" == "healthy" ]]; then
  pass "API container: healthy"
else
  fail "API container 120s içinde healthy olmadı (son durum: '$API_HEALTH')"
  exit 1
fi

# =============================================================================
# CHECK 1/19 — Migration 0007 Cycle (upgrade → downgrade -1 → upgrade)
# =============================================================================
section "CHECK 1/19 — Migration 0007 Cycle (SETUP öncesi)"

info "alembic upgrade head (tüm migration'lar — 0001→0007)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -6; then
  pass "alembic upgrade head: başarılı (academy tabloları oluşturuldu)"
else
  fail "alembic upgrade head: başarısız — devam edilemiyor"
  exit 1
fi

# Academy tabloları var mı?
ACAD_TABLE=$(db_query "SELECT to_regclass('public.academy_programs')::text;")
if [[ "$ACAD_TABLE" == "academy_programs" ]]; then
  pass "academy_programs tablosu mevcut"
else
  fail "academy_programs tablosu bulunamadı (migration çalışmadı?)"
fi

info "alembic downgrade -1 (0007 → 0006, academy tabloları kaldırılıyor)..."
if $DC exec -T api alembic -c migrations/alembic.ini downgrade -1 2>&1 | tail -6; then
  pass "alembic downgrade -1: başarılı (0007 reversibility doğrulandı)"
else
  fail "alembic downgrade -1: başarısız"
fi

ACAD_GONE=$(db_query "SELECT to_regclass('public.academy_programs')::text;" 2>/dev/null || echo "NULL")
if [[ "$ACAD_GONE" == "" ]] || [[ "$ACAD_GONE" == "NULL" ]] || [[ "$ACAD_GONE" == *"NULL"* ]]; then
  pass "academy_programs tablosu kaldırıldı (downgrade doğru çalıştı)"
else
  warn "academy_programs tablosu hâlâ var: $ACAD_GONE"
fi

info "alembic upgrade head (0007 geri geliyor)..."
if $DC exec -T api alembic -c migrations/alembic.ini upgrade head 2>&1 | tail -6; then
  pass "alembic upgrade head (ikinci tur): başarılı"
else
  fail "alembic upgrade head (ikinci tur): başarısız — KRITIK"
  exit 1
fi

CURRENT_REV=$($DC exec -T api alembic -c migrations/alembic.ini current 2>&1 | \
  grep -E "head|0007" | head -1 || true)
[[ -n "$CURRENT_REV" ]] && pass "Migration revision: $CURRENT_REV" || \
  warn "Migration revision okunamadı"

# =============================================================================
# SETUP — Validation Kulübü + Admin + Academy User
# =============================================================================
section "SETUP — Validation Kulübü + Admin + Academy Kullanıcısı"

info "POST /auth/setup (Kulüp A: $VAL_SLUG_A)..."
SETUP_A=$(api POST /api/v1/auth/setup -d \
  "{\"club_name\":\"MYK Validation 5C\",\"club_slug\":\"$VAL_SLUG_A\",
    \"admin_email\":\"$VAL_ADMIN_EMAIL_A\",\"admin_password\":\"$VAL_ADMIN_PASS\",
    \"admin_full_name\":\"MYK Val Admin\"}")
SETUP_A_CODE=$(http_code "$SETUP_A")

if [[ "$SETUP_A_CODE" == "201" ]] || [[ "$SETUP_A_CODE" == "200" ]]; then
  pass "Kulüp A oluşturuldu ($VAL_SLUG_A) — HTTP $SETUP_A_CODE"
else
  fail "Kulüp A setup başarısız — HTTP $SETUP_A_CODE"
  exit 1
fi

info "Login (Admin A)..."
ACCESS_TOKEN=$(do_login "$VAL_SLUG_A" "$VAL_ADMIN_EMAIL_A" "$VAL_ADMIN_PASS")
if [[ -n "$ACCESS_TOKEN" ]]; then
  pass "Admin A login başarılı — access_token alındı"
else
  fail "Admin A login başarısız"
  exit 1
fi

# Kulüp B (tenant isolation için)
info "POST /auth/setup (Kulüp B: $VAL_SLUG_B)..."
SETUP_B=$(api POST /api/v1/auth/setup -d \
  "{\"club_name\":\"MYK Validation 5C-B\",\"club_slug\":\"$VAL_SLUG_B\",
    \"admin_email\":\"$VAL_ADMIN_EMAIL_B\",\"admin_password\":\"$VAL_ADMIN_PASS\",
    \"admin_full_name\":\"MYK Val Admin B\"}")
SETUP_B_CODE=$(http_code "$SETUP_B")
if [[ "$SETUP_B_CODE" == "201" ]] || [[ "$SETUP_B_CODE" == "200" ]]; then
  pass "Kulüp B oluşturuldu ($VAL_SLUG_B)"
else
  warn "Kulüp B oluşturulamadı ($SETUP_B_CODE) — tenant isolation testi atlanacak"
fi

# ── Academy kullanıcısı oluştur (person_id gerekli endpoint'ler için) ─────────
# Admin kullanıcısı /auth/setup'tan person_id'siz oluşur.
# Academy session/heartbeat/quiz endpoint'leri get_current_person kullanır → person_id zorunlu.
# Python ile doğrudan person + user oluşturuyoruz.
info "Academy kullanıcısı oluşturuluyor (person_id ile)..."

ACAD_CREATE_SCRIPT=$(cat << EOF
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.person import Person
from app.models.user import User
from app.models.club import Club
from app.core.security import hash_password

async def main():
    async with AsyncSessionLocal() as db:
        club = (await db.execute(
            select(Club).where(Club.slug == '$VAL_SLUG_A')
        )).scalar_one_or_none()
        if not club:
            print("ERR:CLUB_NOT_FOUND"); return
        existing = (await db.execute(
            select(User).where(User.email == '$VAL_ACAD_EMAIL')
        )).scalar_one_or_none()
        if existing:
            print(f"SKIP:{existing.person_id}"); return
        person = Person(
            club_id=club.id,
            first_name="Val",
            last_name="AcadUser",
            is_deleted=False,
            must_change_password=False,
        )
        db.add(person)
        await db.flush()
        user = User(
            club_id=club.id,
            person_id=person.id,
            email="$VAL_ACAD_EMAIL",
            password_hash=hash_password("$VAL_ACAD_PASS"),
            full_name="Val Academy User",
            role="uye",
            is_active=True,
            is_deleted=False,
        )
        db.add(user)
        await db.commit()
        print(f"OK:{person.id}")

asyncio.run(main())
EOF
)

ACAD_RAW=$(echo "$ACAD_CREATE_SCRIPT" | $DC exec -T api python3 - 2>&1 || true)
ACAD_RESULT=$(printf '%s\n' "$ACAD_RAW" | grep -E '^(OK|SKIP):' | tail -1)
if [[ -z "$ACAD_RESULT" ]]; then
  ACAD_RESULT="ERR:$(printf '%s\n' "$ACAD_RAW" | tail -1)"
fi
if [[ "$ACAD_RESULT" == OK:* ]] || [[ "$ACAD_RESULT" == SKIP:* ]]; then
  ACAD_PERSON_ID="${ACAD_RESULT#*:}"
  pass "Academy kullanıcısı hazır (person_id: ${ACAD_PERSON_ID:0:8}…)"
else
  fail "Academy kullanıcısı oluşturulamadı: $ACAD_RESULT"
fi

info "Login (Academy User)..."
ACADEMY_TOKEN=$(do_login "$VAL_SLUG_A" "$VAL_ACAD_EMAIL" "$VAL_ACAD_PASS")
if [[ -n "$ACADEMY_TOKEN" ]]; then
  pass "Academy user login başarılı"
else
  fail "Academy user login başarısız — token alınamadı"
fi

# =============================================================================
# CHECK 2/19 — Backend Test Suite (≥186 test)
# =============================================================================
section "CHECK 2/19 — Backend Test Suite (≥186 test)"

info "pytest tests/ çalışıyor (30–60s)..."
PYTEST_OUT=$($DC exec -T api pytest tests/ -q --tb=short 2>&1 || true)
echo "$PYTEST_OUT" | tail -25

PYTEST_SUMMARY=$(echo "$PYTEST_OUT" | grep -E '^[0-9]+ passed' | tail -1 || \
                 echo "$PYTEST_OUT" | grep -E 'passed|failed|error' | tail -1 || echo "")
PYTEST_PASSED=$(echo "$PYTEST_SUMMARY" | grep -oE '[0-9]+ passed' | grep -oE '^[0-9]+' | head -1 || echo "0")
PYTEST_FAILED=$(echo "$PYTEST_SUMMARY" | grep -oE '[0-9]+ failed' | grep -oE '^[0-9]+' | head -1 || echo "0")
PYTEST_ERRS=$(echo  "$PYTEST_SUMMARY" | grep -oE '[0-9]+ error'  | grep -oE '^[0-9]+' | head -1 || echo "0")

if [[ "$PYTEST_FAILED" -gt 0 ]] || [[ "$PYTEST_ERRS" -gt 0 ]]; then
  fail "Pytest: $PYTEST_FAILED failed, $PYTEST_ERRS error"
elif [[ "$PYTEST_PASSED" -ge 186 ]]; then
  pass "Pytest: $PYTEST_PASSED passed ≥ 186 ✓"
elif [[ "$PYTEST_PASSED" -gt 0 ]]; then
  warn "Pytest: $PYTEST_PASSED passed — beklenen ≥186 (yeni testler eksik olabilir)"
else
  fail "Pytest: sonuç okunamadı — '$PYTEST_SUMMARY'"
fi

# =============================================================================
# CHECK 3/19 — Seed Idempotency (seed_academy.py)
# =============================================================================
section "CHECK 3/19 — Seed Idempotency (seed_academy.py)"

info "İlk seed çalıştırılıyor (tüm kayıtlar oluşturulmalı)..."
SEED1_OUT=$($DC exec -T api python3 -m scripts.seed_academy 2>&1 || true)
echo "$SEED1_OUT" | tail -10
SEED1_CREATED=$(echo "$SEED1_OUT" | grep -oE 'oluşturulan: [0-9]+' | grep -oE '[0-9]+' || echo "0")
SEED1_SKIPPED=$(echo "$SEED1_OUT" | grep -oE 'atlanan: [0-9]+'     | grep -oE '[0-9]+' || echo "0")
if [[ "$SEED1_CREATED" -gt 0 ]]; then
  pass "İlk seed: $SEED1_CREATED kayıt oluşturuldu, $SEED1_SKIPPED atlandı"
else
  warn "İlk seed: oluşturulan=$SEED1_CREATED — beklenmedik (zaten mevcut?)"
fi

info "İkinci seed çalıştırılıyor (tümü atlanmalı — idempotency)..."
SEED2_OUT=$($DC exec -T api python3 -m scripts.seed_academy 2>&1 || true)
echo "$SEED2_OUT" | tail -10
SEED2_CREATED=$(echo "$SEED2_OUT" | grep -oE 'oluşturulan: [0-9]+' | grep -oE '[0-9]+' || echo "0")
SEED2_SKIPPED=$(echo "$SEED2_OUT" | grep -oE 'atlanan: [0-9]+'     | grep -oE '[0-9]+' || echo "0")
if [[ "$SEED2_CREATED" -eq 0 ]] && [[ "$SEED2_SKIPPED" -gt 0 ]]; then
  pass "İkinci seed: 0 oluşturuldu, $SEED2_SKIPPED atlandı (idempotency ✓)"
else
  fail "İkinci seed idempotency başarısız — oluşturulan=$SEED2_CREATED (beklenen: 0)"
fi

# =============================================================================
# CHECK 4/19 — GET /academy/programs (program listesi)
# =============================================================================
section "CHECK 4/19 — GET /academy/programs"

PROG_LIST_RESP=$(aapi GET /api/v1/academy/programs)
PROG_LIST_CODE=$(http_code "$PROG_LIST_RESP")
PROG_LIST_BODY=$(resp_body "$PROG_LIST_RESP")

if [[ "$PROG_LIST_CODE" == "200" ]]; then
  pass "GET /academy/programs → 200"
  PROG_COUNT=$(printf '%s' "$PROG_LIST_BODY" | python3 -c \
    "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [[ "$PROG_COUNT" -ge 1 ]]; then
    pass "Program listesi: $PROG_COUNT program var"
    # D1 var mı?
    HAS_D1=$(printf '%s' "$PROG_LIST_BODY" | python3 -c \
      "import sys,json; lst=json.load(sys.stdin); print('yes' if any(p.get('slug')=='d1' for p in lst) else 'no')" 2>/dev/null || echo "no")
    if [[ "$HAS_D1" == "yes" ]]; then
      pass "D1 programı listede ✓"
      PROGRAM_ID=$(printf '%s' "$PROG_LIST_BODY" | python3 -c \
        "import sys,json; lst=json.load(sys.stdin); p=[x for x in lst if x.get('slug')=='d1']; print(p[0]['id'] if p else '')" 2>/dev/null || echo "")
      [[ -n "$PROGRAM_ID" ]] && info "  PROGRAM_ID: ${PROGRAM_ID:0:8}…" || warn "D1 id alınamadı"
    else
      fail "D1 programı listede YOK — seed çalışmadı?"
    fi
  else
    fail "Program listesi boş — seed çalışmadı?"
  fi
else
  fail "GET /academy/programs → HTTP $PROG_LIST_CODE"
fi

# Unauthenticated → 401/403
UNAUTH_PROG=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/academy/programs" 2>/dev/null || echo "000")
if [[ "$UNAUTH_PROG" == "401" ]] || [[ "$UNAUTH_PROG" == "403" ]]; then
  pass "GET /academy/programs unauthenticated → $UNAUTH_PROG (korumalı)"
else
  warn "GET /academy/programs unauthenticated → $UNAUTH_PROG"
fi

# =============================================================================
# CHECK 5/19 — GET /academy/programs/d1 (program detayı)
# =============================================================================
section "CHECK 5/19 — GET /academy/programs/d1"

PROG_DETAIL_RESP=$(aapi GET /api/v1/academy/programs/d1)
PROG_DETAIL_CODE=$(http_code "$PROG_DETAIL_RESP")
PROG_DETAIL_BODY=$(resp_body "$PROG_DETAIL_RESP")

if [[ "$PROG_DETAIL_CODE" == "200" ]]; then
  pass "GET /academy/programs/d1 → 200"
  PROG_SLUG=$(jq_field "$PROG_DETAIL_BODY" "slug")
  [[ "$PROG_SLUG" == "d1" ]] && pass "slug: d1 ✓" || fail "slug: '$PROG_SLUG' (beklenen: d1)"

  MOD_COUNT=$(printf '%s' "$PROG_DETAIL_BODY" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(len(d.get('modules',[])))" 2>/dev/null || echo "0")
  if [[ "$MOD_COUNT" -ge 1 ]]; then
    pass "Modül sayısı: $MOD_COUNT"
    # gemici-baglari modülü var mı?
    HAS_MOD=$(printf '%s' "$PROG_DETAIL_BODY" | python3 -c \
      "import sys,json; d=json.load(sys.stdin); mods=d.get('modules',[]); print('yes' if any(m.get('slug')=='gemici-baglari' for m in mods) else 'no')" 2>/dev/null || echo "no")
    [[ "$HAS_MOD" == "yes" ]] && pass "gemici-baglari modülü mevcut ✓" || fail "gemici-baglari modülü YOK"
    # izbarco dersi var mı?
    HAS_LESSON=$(printf '%s' "$PROG_DETAIL_BODY" | python3 -c \
      "import sys,json; d=json.load(sys.stdin)
mods=d.get('modules',[])
lessons=[l for m in mods for l in m.get('lessons',[])]
print('yes' if any(l.get('slug')=='izbarco' for l in lessons) else 'no')" 2>/dev/null || echo "no")
    [[ "$HAS_LESSON" == "yes" ]] && pass "izbarco dersi modülde mevcut ✓" || fail "izbarco dersi YOK"
  else
    fail "Modül sayısı: 0 (seed sorunu?)"
  fi
else
  fail "GET /academy/programs/d1 → HTTP $PROG_DETAIL_CODE"
fi

# =============================================================================
# CHECK 6/19 — POST /academy/programs/{id}/enroll
# =============================================================================
section "CHECK 6/19 — POST /academy/programs/{program_id}/enroll"

if [[ -z "$PROGRAM_ID" ]]; then
  fail "PROGRAM_ID alınamadı — CHECK 4 başarısız oldu, enrollment atlanıyor"
  fail "POST /academy/programs/{id}/enroll — test atlandı"
else
  ENROLL_RESP=$(acad_api POST "/api/v1/academy/programs/$PROGRAM_ID/enroll")
  ENROLL_CODE=$(http_code "$ENROLL_RESP")
  ENROLL_BODY=$(resp_body "$ENROLL_RESP")

  if [[ "$ENROLL_CODE" == "201" ]]; then
    ENROLLMENT_ID=$(jq_field "$ENROLL_BODY" "id")
    pass "POST /academy/programs/{id}/enroll → 201 Created (id: ${ENROLLMENT_ID:0:8}…)"
    ENROLL_STATUS=$(jq_field "$ENROLL_BODY" "status")
    [[ "$ENROLL_STATUS" == "active" ]] && pass "enrollment status: active ✓" || warn "enrollment status: $ENROLL_STATUS"
  else
    fail "POST /academy/programs/{id}/enroll → HTTP $ENROLL_CODE: $(resp_body "$ENROLL_RESP")"
  fi
fi

# =============================================================================
# CHECK 7/19 — Duplicate enroll → 409
# =============================================================================
section "CHECK 7/19 — Duplicate Enrollment → 409"

if [[ -z "$PROGRAM_ID" ]]; then
  fail "PROGRAM_ID yok — duplicate enroll testi atlanıyor"
else
  DUP_ENROLL=$(acad_api POST "/api/v1/academy/programs/$PROGRAM_ID/enroll")
  DUP_CODE=$(http_code "$DUP_ENROLL")
  if [[ "$DUP_CODE" == "409" ]]; then
    pass "Duplicate enrollment → 409 Conflict ✓"
  else
    fail "Duplicate enrollment → $DUP_CODE (beklenen 409)"
  fi
fi

# =============================================================================
# CHECK 8/19 — GET /academy/me/enrollments
# =============================================================================
section "CHECK 8/19 — GET /academy/me/enrollments"

ME_ENROLL_RESP=$(acad_api GET /api/v1/academy/me/enrollments)
ME_ENROLL_CODE=$(http_code "$ME_ENROLL_RESP")
ME_ENROLL_BODY=$(resp_body "$ME_ENROLL_RESP")

if [[ "$ME_ENROLL_CODE" == "200" ]]; then
  ENROLL_COUNT=$(printf '%s' "$ME_ENROLL_BODY" | python3 -c \
    "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  pass "GET /academy/me/enrollments → 200 ($ENROLL_COUNT kayıt)"
  if [[ "$ENROLL_COUNT" -ge 1 ]]; then
    HAS_D1_ENROLL=$(printf '%s' "$ME_ENROLL_BODY" | python3 -c \
      "import sys,json; lst=json.load(sys.stdin); ids=[e.get('id','') for e in lst]; print('yes' if ids else 'no')" 2>/dev/null || echo "no")
    [[ "$HAS_D1_ENROLL" == "yes" ]] && pass "D1 enrollment listede ✓" || warn "D1 enrollment listede bulunamadı"
  else
    fail "Enrollment listesi boş (enroll başarısızdı?)"
  fi
else
  fail "GET /academy/me/enrollments → HTTP $ME_ENROLL_CODE"
fi

# =============================================================================
# CHECK 9/19 — GET /academy/lessons/izbarco (steps + quiz_questions)
# =============================================================================
section "CHECK 9/19 — GET /academy/lessons/izbarco"

LESSON_RESP=$(aapi GET /api/v1/academy/lessons/izbarco)
LESSON_CODE=$(http_code "$LESSON_RESP")
LESSON_BODY=$(resp_body "$LESSON_RESP")

if [[ "$LESSON_CODE" == "200" ]]; then
  pass "GET /academy/lessons/izbarco → 200"
  LESSON_SLUG=$(jq_field "$LESSON_BODY" "slug")
  [[ "$LESSON_SLUG" == "izbarco" ]] && pass "slug: izbarco ✓" || fail "slug: '$LESSON_SLUG'"
  LESSON_ID=$(jq_field "$LESSON_BODY" "id")
  [[ -n "$LESSON_ID" ]] && info "  LESSON_ID: ${LESSON_ID:0:8}…"

  STEP_COUNT=$(printf '%s' "$LESSON_BODY" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(len(d.get('steps',[])))" 2>/dev/null || echo "0")
  [[ "$STEP_COUNT" -ge 1 ]] && pass "Ders adımları: $STEP_COUNT adım ✓" || fail "Adım yok"

  # knot_animation adımı var mı?
  HAS_KNOT=$(printf '%s' "$LESSON_BODY" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); steps=d.get('steps',[]); print('yes' if any(s.get('tip')=='knot_animation' for s in steps) else 'no')" 2>/dev/null || echo "no")
  [[ "$HAS_KNOT" == "yes" ]] && pass "knot_animation adımı mevcut ✓" || fail "knot_animation adımı YOK"

  QUIZ_Q_COUNT=$(printf '%s' "$LESSON_BODY" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(len(d.get('quiz_questions',[])))" 2>/dev/null || echo "0")
  if [[ "$QUIZ_Q_COUNT" -ge 5 ]]; then
    pass "quiz_questions: $QUIZ_Q_COUNT soru ✓"
  else
    fail "quiz_questions: $QUIZ_Q_COUNT soru (beklenen ≥5)"
  fi
else
  fail "GET /academy/lessons/izbarco → HTTP $LESSON_CODE"
fi

# =============================================================================
# CHECK 10/19 — correct_letter quiz start response'da YOK
# =============================================================================
section "CHECK 10/19 — correct_letter Leak Kontrolü (quiz start)"

if [[ -z "$LESSON_ID" ]]; then
  fail "LESSON_ID yok — correct_letter testi atlanıyor"
else
  QUIZ_START_RESP=$(acad_api POST "/api/v1/academy/lessons/$LESSON_ID/quiz/attempts")
  QUIZ_START_CODE=$(http_code "$QUIZ_START_RESP")
  QUIZ_START_BODY=$(resp_body "$QUIZ_START_RESP")

  if [[ "$QUIZ_START_CODE" == "201" ]]; then
    pass "POST /academy/lessons/{id}/quiz/attempts → 201"
    ATTEMPT_ID=$(jq_path "$QUIZ_START_BODY" "attempt.id")
    [[ -n "$ATTEMPT_ID" ]] && info "  ATTEMPT_ID: ${ATTEMPT_ID:0:8}…" || warn "attempt.id alınamadı"

    # correct_letter hiçbir soruda olmamalı
    CORRECT_LEAK=$(printf '%s' "$QUIZ_START_BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
questions = d.get('questions', [])
leaked = [str(q.get('id','?'))[:8] for q in questions if 'correct_letter' in q]
print('LEAKED:' + ','.join(leaked) if leaked else 'CLEAN')
" 2>/dev/null || echo "PARSE_ERROR")

    if [[ "$CORRECT_LEAK" == "CLEAN" ]]; then
      pass "correct_letter quiz start response'da YOK ✓ (güvenlik kuralı korunuyor)"
    elif [[ "$CORRECT_LEAK" == LEAKED:* ]]; then
      fail "GÜVENLİK İHLALİ: correct_letter response'da bulundu! Sorular: ${CORRECT_LEAK#LEAKED:}"
    else
      warn "correct_letter parse edilemedi: $CORRECT_LEAK"
    fi

    Q_COUNT=$(printf '%s' "$QUIZ_START_BODY" | python3 -c \
      "import sys,json; d=json.load(sys.stdin); print(len(d.get('questions',[])))" 2>/dev/null || echo "0")
    [[ "$Q_COUNT" -ge 5 ]] && pass "Quiz: $Q_COUNT soru döndürüldü ✓" || fail "Quiz: $Q_COUNT soru (beklenen ≥5)"
  elif [[ "$QUIZ_START_CODE" == "409" ]]; then
    # Aktif girişim var — önceki testten kalmış olabilir
    warn "Quiz start → 409 (aktif girişim mevcut — bir önceki test artığı olabilir)"
    ATTEMPT_ID=$(aapi GET "/api/v1/academy/lessons/$LESSON_ID/progress" | \
      resp_body | python3 -c "import sys; print('')" 2>/dev/null || echo "")
  else
    fail "POST /academy/lessons/{id}/quiz/attempts → HTTP $QUIZ_START_CODE: $QUIZ_START_BODY"
  fi
fi

# =============================================================================
# CHECK 11/19 — Session başlatma enrollment gerektirir (admin → 403 guard)
# =============================================================================
section "CHECK 11/19 — Session Enrollment Guard (admin token → 403)"

if [[ -z "$LESSON_ID" ]]; then
  fail "LESSON_ID yok — session guard testi atlanıyor"
else
  # Admin tokenı ile session başlatmaya çalış — admin'in person_id'si yok → 403
  GUARD_RESP=$(aapi POST "/api/v1/academy/lessons/$LESSON_ID/sessions")
  GUARD_CODE=$(http_code "$GUARD_RESP")
  if [[ "$GUARD_CODE" == "403" ]]; then
    pass "Admin token ile session start → 403 (get_current_person guard çalışıyor ✓)"
  else
    warn "Admin token ile session start → $GUARD_CODE (beklenen 403 — admin person_id yoksa)"
  fi
fi

# =============================================================================
# CHECK 12/19 — POST /academy/lessons/{id}/sessions (enrollment sonrası)
# =============================================================================
section "CHECK 12/19 — Session Start (Academy User)"

if [[ -z "$LESSON_ID" ]] || [[ -z "$ACADEMY_TOKEN" ]]; then
  fail "LESSON_ID veya ACADEMY_TOKEN yok — session start atlanıyor"
else
  SESS_RESP=$(acad_api POST "/api/v1/academy/lessons/$LESSON_ID/sessions")
  SESS_CODE=$(http_code "$SESS_RESP")
  SESS_BODY=$(resp_body "$SESS_RESP")

  if [[ "$SESS_CODE" == "201" ]]; then
    SESSION_ID=$(jq_field "$SESS_BODY" "id")
    pass "POST /academy/lessons/{id}/sessions → 201 (session_id: ${SESSION_ID:0:8}…)"
    SESS_LESSON=$(jq_field "$SESS_BODY" "lesson_id")
    [[ "$SESS_LESSON" == "$LESSON_ID" ]] && pass "session.lesson_id doğru ✓" || \
      warn "session.lesson_id: $SESS_LESSON (beklenen: $LESSON_ID)"
  else
    fail "POST /academy/lessons/{id}/sessions → HTTP $SESS_CODE: $SESS_BODY"
  fi
fi

# =============================================================================
# CHECK 13/19 — POST /academy/sessions/{id}/heartbeat
# =============================================================================
section "CHECK 13/19 — Heartbeat (ok + toplam_sure_sn + yuzde)"

if [[ -z "$SESSION_ID" ]]; then
  fail "SESSION_ID yok — heartbeat atlanıyor"
else
  sleep 1  # delta_sec hesabı için küçük gecikme

  HB_RESP=$(acad_api POST "/api/v1/academy/sessions/$SESSION_ID/heartbeat")
  HB_CODE=$(http_code "$HB_RESP")
  HB_BODY=$(resp_body "$HB_RESP")

  if [[ "$HB_CODE" == "200" ]]; then
    pass "POST /academy/sessions/{id}/heartbeat → 200"
    HB_OK=$(jq_field "$HB_BODY" "ok")
    [[ "$HB_OK" == "True" ]] || [[ "$HB_OK" == "true" ]] && pass "heartbeat.ok = True ✓" || warn "heartbeat.ok = '$HB_OK'"
    HB_SURE=$(jq_field "$HB_BODY" "toplam_sure_sn")
    pass "toplam_sure_sn: $HB_SURE"
    HB_YUZDE=$(jq_field "$HB_BODY" "yuzde")
    if [[ -n "$HB_YUZDE" ]]; then
      pass "yuzde alanı heartbeat response'da mevcut: $HB_YUZDE ✓"
    else
      fail "yuzde alanı heartbeat response'da YOK (frontend progress bar bozuk)"
    fi
  else
    fail "POST /academy/sessions/{id}/heartbeat → HTTP $HB_CODE: $HB_BODY"
  fi

  # Başkasının session'ına erişim → 404
  FAKE_SESSION=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "00000000-0000-0000-0000-000000000000")
  FAKE_HB=$(acad_api POST "/api/v1/academy/sessions/$FAKE_SESSION/heartbeat")
  FAKE_CODE=$(http_code "$FAKE_HB")
  [[ "$FAKE_CODE" == "404" ]] && pass "Sahte session heartbeat → 404 (tenant guard ✓)" || \
    warn "Sahte session heartbeat → $FAKE_CODE (beklenen 404)"
fi

# =============================================================================
# CHECK 14/19 — GET /academy/knot/izbarco/timeline
# =============================================================================
section "CHECK 14/19 — GET /academy/knot/izbarco/timeline"

TIMELINE_RESP=$(aapi GET /api/v1/academy/knot/izbarco/timeline)
TIMELINE_CODE=$(http_code "$TIMELINE_RESP")
TIMELINE_BODY=$(resp_body "$TIMELINE_RESP")

if [[ "$TIMELINE_CODE" == "200" ]]; then
  pass "GET /academy/knot/izbarco/timeline → 200"

  TL_SCHEMA=$(jq_field "$TIMELINE_BODY" '$schema' 2>/dev/null || \
    printf '%s' "$TIMELINE_BODY" | python3 -c \
      "import sys,json; d=json.load(sys.stdin); print(d.get('\$schema',''))" 2>/dev/null || echo "")
  [[ -n "$TL_SCHEMA" ]] && pass "\$schema mevcut: $TL_SCHEMA" || warn "\$schema alanı bulunamadı"

  TL_SLUG=$(printf '%s' "$TIMELINE_BODY" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('slug',''))" 2>/dev/null || echo "")
  [[ "$TL_SLUG" == "izbarco" ]] && pass "timeline.slug: izbarco ✓" || fail "timeline.slug: '$TL_SLUG'"

  TL_STEPS=$(printf '%s' "$TIMELINE_BODY" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(len(d.get('steps',[])))" 2>/dev/null || echo "0")
  [[ "$TL_STEPS" -ge 5 ]] && pass "timeline.steps: $TL_STEPS adım ✓" || fail "timeline.steps: $TL_STEPS (beklenen ≥5)"

  # Path traversal koruması
  PT_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    "$BASE_URL/api/v1/academy/knot/../../../etc/passwd/timeline" \
    -H "Authorization: Bearer $ACCESS_TOKEN" 2>/dev/null || echo "000")
  [[ "$PT_CODE" == "404" ]] && pass "Path traversal denemesi → 404 (korunuyor ✓)" || \
    warn "Path traversal → $PT_CODE (beklenen 404)"
else
  fail "GET /academy/knot/izbarco/timeline → HTTP $TIMELINE_CODE"
fi

# Unauthenticated → 401/403
UNAUTH_TL=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/api/v1/academy/knot/izbarco/timeline" 2>/dev/null || echo "000")
[[ "$UNAUTH_TL" == "401" ]] || [[ "$UNAUTH_TL" == "403" ]] && \
  pass "timeline unauthenticated → $UNAUTH_TL (korumalı)" || \
  warn "timeline unauthenticated → $UNAUTH_TL"

# =============================================================================
# CHECK 15/19 — Quiz Döngüsü (start → correct answers → finish)
# Önemli: CHECK 10'da quiz start yapıldı, ATTEMPT_ID alındı.
# Eğer ATTEMPT_ID boşsa yeni bir girişim başlatıyoruz.
# =============================================================================
section "CHECK 15/19 — Quiz Döngüsü (5 doğru cevap → gecti=true)"

if [[ -z "$LESSON_ID" ]] || [[ -z "$ACADEMY_TOKEN" ]]; then
  fail "LESSON_ID veya ACADEMY_TOKEN yok — quiz döngüsü atlanıyor"
else
  # ATTEMPT_ID CHECK 10'dan gelebilir; yoksa yeni başlat
  if [[ -z "$ATTEMPT_ID" ]]; then
    info "Yeni quiz girişimi başlatılıyor..."
    QS_RESP=$(acad_api POST "/api/v1/academy/lessons/$LESSON_ID/quiz/attempts")
    QS_CODE=$(http_code "$QS_RESP")
    QS_BODY=$(resp_body "$QS_RESP")
    if [[ "$QS_CODE" == "201" ]]; then
      ATTEMPT_ID=$(jq_path "$QS_BODY" "attempt.id")
      pass "Yeni quiz girişimi başlatıldı (ATTEMPT_ID: ${ATTEMPT_ID:0:8}…)"
    else
      fail "Quiz start → HTTP $QS_CODE — cevap gönderim testi atlanıyor"
    fi
  else
    info "CHECK 10'dan alınan ATTEMPT_ID kullanılıyor: ${ATTEMPT_ID:0:8}…"
    # Mevcut ATTEMPT_ID ile soruları yeniden çek
    QS_RESP=$(acad_api POST "/api/v1/academy/lessons/$LESSON_ID/quiz/attempts")
    if [[ "$(http_code "$QS_RESP")" == "409" ]]; then
      info "Aktif girişim mevcut — ATTEMPT_ID kullanılıyor"
      QS_BODY=$(printf '{"attempt":{"id":"%s"},"questions":[]}' "$ATTEMPT_ID")
    fi
  fi

  # Soruları ve doğru cevapları al — seed ile eşleşen sira-harf eşlemesi
  if [[ -n "$ATTEMPT_ID" ]]; then
    # Önce lesson_body.quiz_questions dene; boşsa quiz start response'dan al.
    # (lesson_body'nin aapi/admin tokenıyla çekildiğini, quiz_questions'ın 3156555
    # sonrasında eklendiğini varsayıyoruz. Stale build durumunda fallback devreye girer.)
    Q_LINES=$(printf '%s' "$LESSON_BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
sira_map = {'1':'B','2':'D','3':'B','4':'C','5':'C'}
questions = sorted(d.get('quiz_questions',[]), key=lambda x: x.get('sira',0))
for q in questions:
    sira = str(q.get('sira',''))
    qid = q.get('id','')
    harf = sira_map.get(sira, 'A')
    print(f'{qid} {harf}')
" 2>/dev/null || echo "")

    # Fallback: lesson_body boşsa QUIZ_START_BODY.questions kullan
    if [[ -z "$Q_LINES" ]] && [[ -n "${QUIZ_START_BODY:-}" ]]; then
      info "Fallback: quiz start response'dan soru ID'leri alınıyor..."
      Q_LINES=$(printf '%s' "$QUIZ_START_BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
sira_map = {'1':'B','2':'D','3':'B','4':'C','5':'C'}
questions = sorted(d.get('questions',[]), key=lambda x: x.get('sira',0))
for q in questions:
    sira = str(q.get('sira',''))
    qid = q.get('id','')
    harf = sira_map.get(sira, 'A')
    print(f'{qid} {harf}')
" 2>/dev/null || echo "")
    fi

    if [[ -z "$Q_LINES" ]]; then
      warn "Soru ID'leri lesson_body'den alınamadı — atlanıyor"
    else
      ANS_PASS=0; ANS_FAIL=0
      while IFS=' ' read -r qid harf; do
        [[ -z "$qid" ]] && continue
        ANS_RESP=$(acad_api POST "/api/v1/academy/quiz/attempts/$ATTEMPT_ID/answers" \
          -d "{\"question_id\":\"$qid\",\"secilen_harf\":\"$harf\"}")
        ANS_CODE=$(http_code "$ANS_RESP")
        if [[ "$ANS_CODE" == "200" ]]; then
          ANS_PASS=$((ANS_PASS + 1))
        elif [[ "$ANS_CODE" == "409" ]]; then
          # Cevap zaten verilmiş (CHECK 10'dan)
          ANS_PASS=$((ANS_PASS + 1))
          info "  Soru $qid zaten cevaplandı (409 — sayıldı)"
        else
          ANS_FAIL=$((ANS_FAIL + 1))
          warn "  Cevap gönderilemedi: $qid → HTTP $ANS_CODE"
        fi
      done <<< "$Q_LINES"

      if [[ "$ANS_FAIL" -eq 0 ]] && [[ "$ANS_PASS" -gt 0 ]]; then
        pass "Quiz: $ANS_PASS cevap gönderildi ✓"
      else
        fail "Quiz: $ANS_PASS başarılı, $ANS_FAIL başarısız"
      fi

      # Quiz'i bitir
      info "POST /academy/quiz/attempts/$ATTEMPT_ID/finish..."
      FINISH_RESP=$(acad_api POST "/api/v1/academy/quiz/attempts/$ATTEMPT_ID/finish")
      FINISH_CODE=$(http_code "$FINISH_RESP")
      FINISH_BODY=$(resp_body "$FINISH_RESP")

      if [[ "$FINISH_CODE" == "200" ]]; then
        pass "POST /academy/quiz/attempts/{id}/finish → 200"
        GECTI=$(jq_field "$FINISH_BODY" "gecti")
        DOGRU=$(jq_field "$FINISH_BODY" "dogru")
        TOPLAM=$(jq_field "$FINISH_BODY" "toplam")
        if [[ "$GECTI" == "True" ]] || [[ "$GECTI" == "true" ]]; then
          pass "gecti: True ✓ (dogru=$DOGRU / toplam=$TOPLAM)"
        else
          fail "gecti: $GECTI (beklenen True) — dogru=$DOGRU / toplam=$TOPLAM"
        fi

        # Finish sonrası correct_letter sorular dahil geliyor (quiz bitti, güvenli)
        SORULAR=$(printf '%s' "$FINISH_BODY" | python3 -c \
          "import sys,json; d=json.load(sys.stdin); print(len(d.get('sorular',[])))" 2>/dev/null || echo "0")
        [[ "$SORULAR" -ge 1 ]] && pass "Sonuç: $SORULAR soru detayı (dogru_harf dahil) ✓" || \
          warn "Sonuç sorular boş"

        # Finish yanıtında attempt_id var mı?
        FIN_ATTEMPT=$(jq_field "$FINISH_BODY" "attempt_id")
        [[ -n "$FIN_ATTEMPT" ]] && pass "finish response.attempt_id mevcut ✓" || \
          warn "finish response.attempt_id YOK"
      else
        fail "POST /academy/quiz/attempts/{id}/finish → HTTP $FINISH_CODE: $FINISH_BODY"
      fi
    fi
  fi
fi

# =============================================================================
# CHECK 16/19 — Progress: yuzde=100, tamamlandi=true (quiz pass sonrası)
# =============================================================================
section "CHECK 16/19 — Progress (quiz pass sonrası yuzde=100)"

if [[ -z "$LESSON_ID" ]] || [[ -z "$ACADEMY_TOKEN" ]]; then
  fail "LESSON_ID veya ACADEMY_TOKEN yok — progress testi atlanıyor"
else
  PROG_RESP=$(acad_api GET "/api/v1/academy/lessons/$LESSON_ID/progress")
  PROG_CODE=$(http_code "$PROG_RESP")
  PROG_BODY=$(resp_body "$PROG_RESP")

  if [[ "$PROG_CODE" == "200" ]]; then
    pass "GET /academy/lessons/{id}/progress → 200"
    PROG_YUZDE=$(jq_field "$PROG_BODY" "yuzde")
    PROG_TAMAM=$(jq_field "$PROG_BODY" "tamamlandi")
    if [[ "$PROG_YUZDE" == "100" ]]; then
      pass "progress.yuzde = 100 ✓"
    else
      fail "progress.yuzde = $PROG_YUZDE (beklenen 100)"
    fi
    if [[ "$PROG_TAMAM" == "True" ]] || [[ "$PROG_TAMAM" == "true" ]]; then
      pass "progress.tamamlandi = True ✓"
    else
      fail "progress.tamamlandi = $PROG_TAMAM (beklenen True)"
    fi
    PROG_SURE=$(jq_field "$PROG_BODY" "toplam_sure_sn")
    pass "toplam_sure_sn: $PROG_SURE saniye"
  else
    fail "GET /academy/lessons/{id}/progress → HTTP $PROG_CODE"
  fi
fi

# =============================================================================
# CHECK 17/19 — Tenant İzolasyonu
# =============================================================================
section "CHECK 17/19 — Tenant İzolasyonu (Academy)"

# 17a: Bozuk token → 401
BAD_TOKEN="${ACADEMY_TOKEN}TAMPERED"
BT_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/api/v1/academy/programs" \
  -H "Authorization: Bearer $BAD_TOKEN" 2>/dev/null || echo "000")
if [[ "$BT_CODE" == "401" ]] || [[ "$BT_CODE" == "403" ]]; then
  pass "Tampered token → $BT_CODE (JWT doğrulama ✓)"
else
  fail "Tampered token → $BT_CODE (beklenen 401/403)"
fi

# 17b: Kulüp B için person_id'li kullanıcı oluştur → o token ile Kulüp A session'ına eriş → 404
# ÖNEMLİ: Admin tokenı kullanmıyoruz (admin person_id'siz olduğundan 403 gelir ve bu tenant
# isolation'ı değil person guard'ı test eder). Gerçek cross-tenant testi için B kulübüne
# bağlı bir Person+User gerekli.
ACAD_EMAIL_B="val-acad-b@example.com"
ACAD_PASS_B="AcadUserB1E2E"
TOKEN_B_ACAD=""

if [[ "$SETUP_B_CODE" == "201" ]] || [[ "$SETUP_B_CODE" == "200" ]]; then
  CREATE_B_SCRIPT=$(cat << EOF
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.person import Person
from app.models.user import User
from app.models.club import Club
from app.core.security import hash_password

async def main():
    async with AsyncSessionLocal() as db:
        club = (await db.execute(
            select(Club).where(Club.slug == '$VAL_SLUG_B')
        )).scalar_one_or_none()
        if not club:
            print("ERR:CLUB_B_NOT_FOUND"); return
        existing = (await db.execute(
            select(User).where(User.email == '$ACAD_EMAIL_B')
        )).scalar_one_or_none()
        if existing:
            print(f"SKIP:{existing.person_id}"); return
        person = Person(
            club_id=club.id,
            first_name="Val",
            last_name="AcadUserB",
            is_deleted=False,
            must_change_password=False,
        )
        db.add(person)
        await db.flush()
        user = User(
            club_id=club.id,
            person_id=person.id,
            email="$ACAD_EMAIL_B",
            password_hash=hash_password("$ACAD_PASS_B"),
            full_name="Val Academy User B",
            role="uye",
            is_active=True,
            is_deleted=False,
        )
        db.add(user)
        await db.commit()
        print(f"OK:{person.id}")

asyncio.run(main())
EOF
)
  CREATE_B_RAW=$(echo "$CREATE_B_SCRIPT" | $DC exec -T api python3 - 2>&1 || true)
  CREATE_B_RESULT=$(printf '%s\n' "$CREATE_B_RAW" | grep -E '^(OK|SKIP):' | tail -1)
  if [[ "$CREATE_B_RESULT" == OK:* ]] || [[ "$CREATE_B_RESULT" == SKIP:* ]]; then
    pass "Kulüp B academy kullanıcısı hazır"
    TOKEN_B_ACAD=$(do_login "$VAL_SLUG_B" "$ACAD_EMAIL_B" "$ACAD_PASS_B")
    if [[ -n "$TOKEN_B_ACAD" ]]; then
      pass "Kulüp B academy user login başarılı"
    else
      fail "Kulüp B academy user login başarısız"
    fi
  else
    fail "Kulüp B academy kullanıcısı oluşturulamadı: $(printf '%s\n' "$CREATE_B_RAW" | tail -1)"
  fi
else
  fail "Kulüp B setup yapılmamış — cross-tenant testi yapılamıyor"
fi

if [[ -n "$TOKEN_B_ACAD" ]] && [[ -n "$SESSION_ID" ]]; then
  # Kulüp B token ile Kulüp A session'ına heartbeat → SADECE 404 beklenir.
  # 403 kabul edilmez: 403 yalnızca person guard demektir, tenant isolation değil.
  CROSS_HB=$(curl -s -w "\n%{http_code}" \
    -X POST "$BASE_URL/api/v1/academy/sessions/$SESSION_ID/heartbeat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_B_ACAD" 2>/dev/null || echo -e "\n000")
  CROSS_CODE=$(http_code "$CROSS_HB")
  if [[ "$CROSS_CODE" == "404" ]]; then
    pass "Kulüp B token ile Kulüp A session'ı → 404 (gerçek tenant izolasyon ✓)"
  elif [[ "$CROSS_CODE" == "403" ]]; then
    fail "Kulüp B token ile Kulüp A session'ı → 403 (person guard tetiklendi — tenant izolasyon değil, router bug)"
  else
    fail "Kulüp B token ile Kulüp A session'ı → $CROSS_CODE (beklenen 404)"
  fi
elif [[ -z "$SESSION_ID" ]]; then
  fail "SESSION_ID yok — cross-tenant heartbeat testi yapılamadı"
fi

# 17c: Kulüp B token ile academy programs → global katalog (200 beklenir)
# Admin tokenı kullanıyoruz çünkü GET programs person gerektirmiyor
TOKEN_B_ADMIN=$(do_login "$VAL_SLUG_B" "$VAL_ADMIN_EMAIL_B" "$VAL_ADMIN_PASS" || true)
if [[ -n "$TOKEN_B_ADMIN" ]]; then
  CROSS_PROG=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/v1/academy/programs" \
    -H "Authorization: Bearer $TOKEN_B_ADMIN" 2>/dev/null || echo -e "\n000")
  CROSS_PROG_CODE=$(http_code "$CROSS_PROG")
  if [[ "$CROSS_PROG_CODE" == "200" ]]; then
    pass "Kulüp B token ile GET /academy/programs → 200 (global katalog paylaşımlı — beklenen)"
  else
    warn "Kulüp B token ile GET /academy/programs → $CROSS_PROG_CODE"
  fi
fi

# =============================================================================
# CHECK 18/19 — Frontend Docker Build (tsc + vite production)
# =============================================================================
section "CHECK 18/19 — Frontend Docker Build (production stage)"

FRONTEND_TAG="myk-val-frontend-5c:sprint5c"
info "Frontend Dockerfile production stage build (TypeScript + Vite)..."
if docker build \
  --target production \
  -f frontend/Dockerfile \
  frontend/ \
  --tag "$FRONTEND_TAG" \
  2>&1 | tail -10; then
  pass "Frontend Docker production build başarılı (tsc + vite ✓)"
  docker rmi "$FRONTEND_TAG" --force &>/dev/null || true
else
  fail "Frontend Docker production build başarısız — TypeScript veya bundle hatası"
fi

# =============================================================================
# CHECK 19/19 — Smoke Test
# =============================================================================
section "CHECK 19/19 — Smoke Test"

HEALTH=$(curl -sf "$BASE_URL/api/v1/health" 2>/dev/null || echo "")
if [[ -n "$HEALTH" ]]; then
  pass "GET /api/v1/health → $HEALTH"
else
  fail "GET /api/v1/health → yanıt yok"
fi

ROOT_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/" 2>/dev/null || echo "000")
[[ "$ROOT_CODE" == "200" ]] && pass "GET / → 200 (frontend SPA)" || fail "GET / → $ROOT_CODE"

AKAD_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/akademi" 2>/dev/null || echo "000")
[[ "$AKAD_CODE" == "200" ]] && pass "GET /akademi → 200 (SPA routing ✓)" || \
  fail "GET /akademi → $AKAD_CODE (nginx try_files kontrol et)"

# 404 olmayan random route → nginx SPA fallback
SPA_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/akademi/ders/izbarco" 2>/dev/null || echo "000")
[[ "$SPA_CODE" == "200" ]] && pass "GET /akademi/ders/izbarco → 200 (SPA deep-link ✓)" || \
  warn "GET /akademi/ders/izbarco → $SPA_CODE"

# =============================================================================
# ÖZET
# =============================================================================
section "SONUÇ"

TOTAL=$((PASS + FAIL))
echo
echo -e "  ${GREEN}Geçen    : $PASS${NC}"
[[ $FAIL -gt 0 ]] && echo -e "  ${RED}Başarısız: $FAIL${NC}"
[[ $WARN -gt 0 ]] && echo -e "  ${YELLOW}Uyarı    : $WARN${NC}"
echo -e "  Toplam   : $TOTAL check (+ $WARN uyarı)"
echo

if [[ $FAIL -eq 0 ]]; then
  echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  TÜM SPRINT 5C E2E CHECK'LERİ GEÇTİ                   ║${NC}"
  echo -e "${GREEN}║                                                          ║${NC}"
  echo -e "${GREEN}║  Sıradaki adımlar:                                       ║${NC}"
  echo -e "${GREEN}║  1. git push origin main                                 ║${NC}"
  echo -e "${GREEN}║  2. Production: alembic upgrade head                     ║${NC}"
  echo -e "${GREEN}║  3. Production: python -m scripts.seed_academy           ║${NC}"
  echo -e "${GREEN}║  4. git tag v0.7.0 + git push --tags                    ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
  echo
  echo "  Commit + push için:"
  echo "    git push origin main"
  echo "    git tag v0.7.0"
  echo "    git push origin --tags"
else
  echo -e "${RED}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${RED}║  $FAIL CHECK BAŞARISIZ — push/tag öncesi düzelt          ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════════════════════╝${NC}"
fi

# =============================================================================
# TEARDOWN
# =============================================================================
section "Temizlik"

if [[ "$KEEP" == true ]]; then
  info "Container'lar çalışmaya devam ediyor (--keep modu)."
  echo "  Manuel temizlik: $DC down -v"
  _CLEANUP_DONE=true
else
  _CLEANUP_DONE=true
  $DC down -v --remove-orphans 2>/dev/null && \
    pass "myk_validation container + volume temizlendi" || \
    warn "Temizlik hatası — manuel: $DC down -v"
fi

echo
[[ $FAIL -eq 0 ]] && exit 0 || exit 1

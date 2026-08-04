#!/usr/bin/env bash
# Sprint 3.2 Staging Verification Wrapper
#
# Kullanım:
#   bash scripts/run_sprint32_verify.sh
#
# Özellikler:
#   - Servis ön kontrolü (fail-fast)
#   - Gizli token girişi — shell geçmişine yazılmaz
#   - API container içinde çalışır; host httpx kurulumu gerekmez
#   - exit 0 = PASS, exit 1 = FAIL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REQUIRED_SERVICES=("api" "pdf-service" "nginx" "db" "minio")

# ── Yardımcı ─────────────────────────────────────────────────────────────────
_header() {
  echo ""
  echo "════════════════════════════════════════"
  echo "  Sprint 3.2 Staging Verification"
  echo "════════════════════════════════════════"
  echo "  $(date '+%Y-%m-%d %H:%M:%S')"
  echo ""
}

_fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

# ── 1. Ön kontrol ─────────────────────────────────────────────────────────────
_preflight() {
  echo "[PRE-FLIGHT] Servis durumu kontrol ediliyor..."

  RUNNING=$(docker compose \
    --project-directory "${PROJECT_ROOT}" \
    ps --services --filter "status=running" 2>/dev/null || true)

  local ok=1
  for svc in "${REQUIRED_SERVICES[@]}"; do
    if echo "${RUNNING}" | grep -q "^${svc}$"; then
      echo "  ✓ ${svc}"
    else
      echo "  ✗ ${svc} — çalışmıyor"
      ok=0
    fi
  done

  if [[ ${ok} -eq 0 ]]; then
    _fail "Bir veya daha fazla servis çalışmıyor. 'docker compose up -d' ile başlatın."
  fi

  echo ""
}

# ── 2. Token girişi ───────────────────────────────────────────────────────────
_read_tokens() {
  CLUB_A_TOKEN="${CLUB_A_TOKEN:-}"
  CLUB_B_TOKEN="${CLUB_B_TOKEN:-}"

  if [[ -z "${CLUB_A_TOKEN}" ]]; then
    read -rsp "Club A JWT: " CLUB_A_TOKEN
    echo
  fi

  if [[ -z "${CLUB_B_TOKEN}" ]]; then
    read -rsp "Club B JWT: " CLUB_B_TOKEN
    echo
  fi

  echo

  [[ -n "${CLUB_A_TOKEN}" ]] \
    || _fail "Club A token boş bırakılamaz."

  [[ -n "${CLUB_B_TOKEN}" ]] \
    || _fail "Club B token boş bırakılamaz."
}

# ── 3. Doğrulama ──────────────────────────────────────────────────────────────
_run_verify() {
  docker compose \
    --project-directory "${PROJECT_ROOT}" \
    run --rm -T \
    -v "${SCRIPT_DIR}:/scripts:ro" \
    api \
    python /scripts/staging_integration_verify.py \
      --base-url "http://nginx" \
      --club-a-token "${CLUB_A_TOKEN}" \
      --club-b-token "${CLUB_B_TOKEN}"
}

# ── 4. Footer ────────────────────────────────────────────────────────────────
_footer() {
  local exit_code=$1
  echo ""
  echo "════════════════════════════════════════"
  if [[ ${exit_code} -eq 0 ]]; then
    echo "  RESULT: PASS ✅"
  else
    echo "  RESULT: FAIL ❌"
  fi
  echo "════════════════════════════════════════"
  echo ""
}

# ── Ana ───────────────────────────────────────────────────────────────────────
_header
_preflight
_read_tokens

_run_verify
EXIT_CODE=$?

unset CLUB_A_TOKEN CLUB_B_TOKEN

_footer "${EXIT_CODE}"
exit "${EXIT_CODE}"

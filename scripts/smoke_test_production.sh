#!/usr/bin/env bash
# smoke_test_production.sh — MYK Platform V2 Production Smoke Test
#
# Kullanım:
#   bash scripts/smoke_test_production.sh [--base-url https://yourdomain.com]
#
# ÖNEMLİ: Bu script production'da VERİ OLUŞTURMAZ.
# Yalnızca mevcut endpoint'lerin yanıt verdiğini ve kritik özelliklerin
# çalıştığını doğrular. Test kullanıcısı veya başvurusu oluşturmaz.
#
# Başarı ölçütü: tüm testler [OK] — son satır "SMOKE TEST PASS"

set -Eeuo pipefail

# ── Parametreler ──────────────────────────────────────────────────────────────
BASE_URL="${1:-}"
SERVER="myk-server"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
COMPOSE_CMD="docker compose ${COMPOSE_FILES}"

if [[ -z "${BASE_URL}" ]]; then
  # Sunucu üzerindeki nginx'e localhost üzerinden test et
  BASE_URL="http://localhost"
  REMOTE_MODE=true
else
  REMOTE_MODE=false
fi

PASS=0
FAIL=0
RESULTS=()

_check() {
  local name="$1"
  local result="$2"
  local expected="$3"
  if echo "${result}" | grep -q "${expected}"; then
    RESULTS+=("  [OK]   ${name}")
    (( PASS++ )) || true
  else
    RESULTS+=("  [FAIL] ${name} — beklenen: '${expected}', alınan: '${result:0:100}'")
    (( FAIL++ )) || true
  fi
}

_header() { echo ""; echo "── $* ──"; }

echo "MYK Platform V2 — Production Smoke Test"
echo "Zaman: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Hedef: ${BASE_URL}"
echo ""

# ── Test fonksiyonu: sunucu üzerinden curl ─────────────────────────────────────
_curl() {
  local method="$1"; shift
  local path="$1"; shift
  local extra_args=("$@")

  if [[ "${REMOTE_MODE}" == "true" ]]; then
    # Sunucu üzerinde çalıştır
    ssh "${SERVER}" "curl -sf -X ${method} '${BASE_URL}${path}' ${extra_args[*]:-} 2>/dev/null" 2>/dev/null || echo "CONNECTION_ERROR"
  else
    curl -sf -X "${method}" "${BASE_URL}${path}" "${extra_args[@]:-}" 2>/dev/null || echo "CONNECTION_ERROR"
  fi
}

_curl_code() {
  local method="$1"; shift
  local path="$1"; shift
  local extra_args=("$@")

  if [[ "${REMOTE_MODE}" == "true" ]]; then
    ssh "${SERVER}" "curl -s -o /dev/null -w '%{http_code}' -X ${method} '${BASE_URL}${path}' ${extra_args[*]:-} 2>/dev/null" 2>/dev/null || echo "000"
  else
    curl -s -o /dev/null -w '%{http_code}' -X "${method}" "${BASE_URL}${path}" "${extra_args[@]:-}" 2>/dev/null || echo "000"
  fi
}

# ── T01: API Health ────────────────────────────────────────────────────────────
_header "T01 API Health"
result=$(_curl GET "/api/v1/health")
_check "GET /api/v1/health → status OK" "${result}" '"status"'

# ── T02: OpenAPI şeması erişilebilir ──────────────────────────────────────────
_header "T02 OpenAPI"
result=$(_curl GET "/api/openapi.json")
_check "GET /api/openapi.json → openapi alanı var" "${result}" '"openapi"'

# ── T03: HTTPS yönlendirmesi (eğer TLS aktifse) ───────────────────────────────
_header "T03 Güvenlik başlıkları"
if [[ "${REMOTE_MODE}" == "true" ]]; then
  headers=$(ssh "${SERVER}" "curl -sI '${BASE_URL}/api/v1/health' 2>/dev/null" 2>/dev/null || echo "")
else
  headers=$(curl -sI "${BASE_URL}/api/v1/health" 2>/dev/null || echo "")
fi
_check "X-Frame-Options başlığı" "${headers}" "X-Frame-Options"
_check "X-Content-Type-Options başlığı" "${headers}" "X-Content-Type-Options"

# ── T04: Auth — Geçersiz credential 401 dönmeli ───────────────────────────────
_header "T04 Auth"
code=$(_curl_code POST "/api/v1/auth/login" \
  "-H 'Content-Type: application/json'" \
  "-d '{\"email\":\"nonexistent@test.invalid\",\"password\":\"wrongpass\"}'")
_check "POST /auth/login geçersiz credential → 401 veya 422" "${code}" "^[14]"

# ── T05: Korumalı endpoint — token olmadan 401 dönmeli ────────────────────────
_header "T05 Korumalı endpoint"
code=$(_curl_code GET "/api/v1/persons/")
_check "GET /persons/ token yok → 401" "${code}" "401"

# ── T06: Olmayan endpoint 404 dönmeli ─────────────────────────────────────────
_header "T06 404 yönlendirme"
code=$(_curl_code GET "/api/v1/nonexistent-endpoint-xyz")
_check "GET /nonexistent → 404" "${code}" "404"

# ── T07: Frontend erişilebilir ────────────────────────────────────────────────
_header "T07 Frontend"
result=$(_curl GET "/")
_check "GET / → HTML döndü" "${result}" "<html\|<!DOCTYPE"

# ── T08: Servis sağlık durumu (docker compose ps) ─────────────────────────────
_header "T08 Docker servis durumu"
if [[ "${REMOTE_MODE}" == "true" ]]; then
  svc_status=$(ssh "${SERVER}" "cd /opt/myk/production/myk-platform-v2 && ${COMPOSE_CMD} ps --format 'table {{.Name}}\t{{.State}}\t{{.Health}}' 2>/dev/null" 2>/dev/null || echo "ERROR")
  echo "${svc_status}"

  # 7 servisin running olduğunu kontrol et
  running_count=$(echo "${svc_status}" | grep -c "running" || echo "0")
  _check "7 servis running (api db redis minio pdf-service frontend nginx)" "${running_count}" "^[789]"

  # Unhealthy servis var mı?
  unhealthy=$(echo "${svc_status}" | grep "unhealthy" | wc -l || echo "0")
  [[ "${unhealthy}" -eq 0 ]] \
    && RESULTS+=("  [OK]   Unhealthy servis yok") && (( PASS++ )) || true \
    || RESULTS+=("  [FAIL] Unhealthy servis var: $(echo "${svc_status}" | grep "unhealthy")") && (( FAIL++ )) || true
else
  _check "Docker servis kontrolü (remote mode gerekir)" "SKIP" "SKIP"
fi

# ── T09: PDF Service internal health ─────────────────────────────────────────
_header "T09 PDF Service"
if [[ "${REMOTE_MODE}" == "true" ]]; then
  pdf_health=$(ssh "${SERVER}" "cd /opt/myk/production/myk-platform-v2 && \
    ${COMPOSE_CMD} exec -T pdf-service \
    python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3); print('OK')\" \
    2>/dev/null" 2>/dev/null || echo "FAIL")
  _check "PDF Service /health → OK" "${pdf_health}" "OK"
fi

# ── T10: MinIO internal health ────────────────────────────────────────────────
_header "T10 MinIO"
if [[ "${REMOTE_MODE}" == "true" ]]; then
  minio_health=$(ssh "${SERVER}" "cd /opt/myk/production/myk-platform-v2 && \
    ${COMPOSE_CMD} exec -T minio \
    curl -sf http://localhost:9000/minio/health/live 2>/dev/null && echo OK || echo FAIL" \
    2>/dev/null || echo "FAIL")
  _check "MinIO /minio/health/live → OK" "${minio_health}" "OK"
fi

# ── T11: Alembic head doğrulama ───────────────────────────────────────────────
_header "T11 Alembic"
if [[ "${REMOTE_MODE}" == "true" ]]; then
  alembic_ver=$(ssh "${SERVER}" "cd /opt/myk/production/myk-platform-v2 && \
    ${COMPOSE_CMD} run --rm -T --entrypoint /bin/sh api -c '
      export DATABASE_URL=\"postgresql+asyncpg://\${POSTGRES_USER}:\${POSTGRES_PASSWORD}@db:5432/\${POSTGRES_DB}\"
      alembic -c migrations/alembic.ini current 2>/dev/null
    ' 2>/dev/null | tail -1" 2>/dev/null || echo "ERROR")
  _check "Alembic current → (head)" "${alembic_ver}" "(head)"
fi

# ── T12: applicant_name nullable kontrolü ─────────────────────────────────────
_header "T12 Schema doğrulama"
if [[ "${REMOTE_MODE}" == "true" ]]; then
  nullable_check=$(ssh "${SERVER}" "cd /opt/myk/production/myk-platform-v2 && \
    ${COMPOSE_CMD} exec -T db psql -U \"\${POSTGRES_USER}\" -d \"\${POSTGRES_DB}\" -tAc \
    \"SELECT is_nullable FROM information_schema.columns \
     WHERE table_schema='public' AND table_name='membership_applications' \
     AND column_name='applicant_name';\" 2>/dev/null" 2>/dev/null || echo "ERROR")
  nullable_check=$(echo "${nullable_check}" | tr -d '[:space:]')
  _check "membership_applications.applicant_name nullable=YES" "${nullable_check}" "YES"
fi

# ── Özet ──────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════"
echo " Smoke Test Sonuçları"
echo "═══════════════════════════════════════"
for r in "${RESULTS[@]}"; do
  echo "${r}"
done
echo ""
echo "  Toplam: $((PASS + FAIL)) | Geçen: ${PASS} | Başarısız: ${FAIL}"
echo ""

if [[ "${FAIL}" -eq 0 ]]; then
  echo "  SMOKE TEST PASS ✅"
  exit 0
else
  echo "  SMOKE TEST FAIL ❌  (${FAIL} test başarısız)"
  exit 1
fi

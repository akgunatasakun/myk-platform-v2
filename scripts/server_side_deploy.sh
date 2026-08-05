#!/usr/bin/env bash
# server_side_deploy.sh — MYK Platform V2 — Sunucu taraflı deploy
#
# Bu script production SUNUCUSUNDA doğrudan çalışır.
# Çağırma:
#   Manuel:          ssh myk-deploy@<host> "bash /opt/myk/.../server_side_deploy.sh --tag v0.4.x"
#   GitHub Actions:  workflow deploy adımı bu scripti SSH üzerinden çağırır
#
# Kullanım:
#   bash scripts/server_side_deploy.sh --tag v0.4.3 [--skip-backup] [--skip-smoke]
#
# Güvenlik notları:
#   - myk-deploy kullanıcısı docker grubundadır.
#     Docker grup üyeliği pratikte root erişimiyle eşdeğerdir;
#     bu kabul edilmiş bir trade-off'tur. "Kısıtlı" kullanıcı değildir.
#   - Secrets repo dışındadır: /etc/myk/production.env (root:myk-deploy 640)
#     git checkout veya git clean bu dosyaya dokunamaz.
#   - .env asla deploy paketine eklenmez, asla source edilmez.
#   - Secret değerleri hiçbir çıktıda gösterilmez (_hide filtresi).
#   - docker compose down -v çalıştırılmaz.
#   - Production DB'ye doğrudan SQL çalıştırılmaz.

set -Eeuo pipefail

# ── Parametreler ───────────────────────────────────────────────────────────────
DEPLOY_TAG=""
SKIP_BACKUP=false
SKIP_SMOKE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)          DEPLOY_TAG="$2"; shift 2 ;;
    --skip-backup)  SKIP_BACKUP=true; shift ;;
    --skip-smoke)   SKIP_SMOKE=true;  shift ;;
    *) echo "Bilinmeyen parametre: $1" >&2; exit 1 ;;
  esac
done

[[ -n "${DEPLOY_TAG}" ]] || { echo "HATA: --tag zorunlu (örn: --tag v0.4.3)" >&2; exit 1; }

# Tag formatı doğrulama — shell injection önlemi
# Geçerli format: v<major>.<minor>.<patch> veya v<major>.<minor>.<patch>-<pre>
[[ "${DEPLOY_TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9._-]+)?$ ]] \
  || { echo "HATA: Geçersiz tag formatı: ${DEPLOY_TAG}" >&2; exit 1; }

# ── Sabitler ───────────────────────────────────────────────────────────────────
REMOTE_DIR="/opt/myk/production/myk-platform-v2"
BACKUP_STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="/opt/myk/backups/production-${BACKUP_STAMP}"
GITHUB_REPO="git@github.com:akgunatasakun/myk-platform-v2.git"
ENV_FILE="/etc/myk/production.env"          # secrets repo dışında
CF="--env-file ${ENV_FILE} -f docker-compose.yml -f docker-compose.prod.yml"
PROD_PORT=18081
COMPOSE_PROJECT_NAME="myk-production"
export COMPOSE_PROJECT_NAME

# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────────
_h()    { printf '\n══════ %s ══════\n' "$*"; }
_ok()   { printf '  ✓  %s\n' "$*"; }
_warn() { printf '  ⚠  %s\n' "$*"; }
_fail() { printf '  ✗  HATA: %s\n' "$*" >&2; exit 1; }
_i()    { printf '  ·  %s\n' "$*"; }

# Satır içinde secret olabilecek değerleri filtrele
_hide() { grep -vE '(PASSWORD|SECRET_KEY|JWT_SECRET|ACCESS_KEY)=[^[:space:]]' || true; }

# ── Adım 1: Ortam doğrulama ───────────────────────────────────────────────────
_h "1. Ortam doğrulama"

_i "Docker: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'bulunamadı')"
_i "Compose: $(docker compose version --short 2>/dev/null || echo 'bulunamadı')"
_i "Git:    $(git --version 2>/dev/null | head -1 || echo 'bulunamadı')"
_i "Tag:    ${DEPLOY_TAG}"

docker version > /dev/null 2>&1 || _fail "Docker yüklü değil veya daemon çalışmıyor."
docker compose version > /dev/null 2>&1 || _fail "docker compose eklentisi bulunamadı."
git --version > /dev/null 2>&1 || _fail "git bulunamadı."
_ok "Bağımlılıklar mevcut"

# Secrets dosyası kontrolü (değerleri göstermeden)
[[ -f "${ENV_FILE}" ]] \
  || _fail "Secrets dosyası bulunamadı: ${ENV_FILE}
  Kurulum için: sudo mkdir -p /etc/myk
                sudo cp /opt/myk/production/myk-platform-v2/.env /etc/myk/production.env
                sudo chown root:myk-deploy /etc/myk/production.env
                sudo chmod 640 /etc/myk/production.env"

for var in MYK_ENV JWT_SECRET_KEY SECRET_KEY POSTGRES_PASSWORD ALLOW_PUBLIC_SETUP \
           STORAGE_ACCESS_KEY STORAGE_SECRET_KEY; do
  val="$(grep "^${var}=" "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || true)"
  if [[ -z "${val}" ]]; then
    _fail "${ENV_FILE} içinde ${var} tanımlı değil."
  elif echo "${val}" | grep -qiE "REPLACE_WITH|CHANGE_ME"; then
    _fail "${ENV_FILE} içinde ${var} hâlâ placeholder değer içeriyor."
  fi
  _ok "${var} tanımlı"
done

MYK_ENV_VAL="$(grep "^MYK_ENV=" "${ENV_FILE}" | cut -d= -f2- || true)"
[[ "${MYK_ENV_VAL}" == "production" ]] || _fail "MYK_ENV=production değil: ${MYK_ENV_VAL}"
_ok "MYK_ENV=production"

SETUP_VAL="$(grep "^ALLOW_PUBLIC_SETUP=" "${ENV_FILE}" | cut -d= -f2- || true)"
[[ "${SETUP_VAL,,}" == "false" ]] || _fail "ALLOW_PUBLIC_SETUP=false değil: ${SETUP_VAL}"
_ok "ALLOW_PUBLIC_SETUP=false"

# ── Adım 2: Kaynak kodu güncelle ──────────────────────────────────────────────
_h "2. Kaynak kodu güncelle"

if [[ ! -d "${REMOTE_DIR}/.git" ]]; then
  _warn "Repo mevcut değil — ilk kurulum yapılıyor..."
  mkdir -p "$(dirname "${REMOTE_DIR}")"
  git clone "${GITHUB_REPO}" "${REMOTE_DIR}" 2>&1 \
    || _fail "git clone başarısız. Sunucuda GitHub SSH erişimi var mı? (ssh -T git@github.com)"
  _ok "Repo klonlandı: ${REMOTE_DIR}"
fi

cd "${REMOTE_DIR}"

# Not: git fetch/checkout /etc/myk/production.env'e dokunamaz — repo dışında.
# git clean -fd çalıştırılmamaktadır.
git fetch origin --tags --prune 2>&1 | _hide
git checkout "${DEPLOY_TAG}" 2>&1 | grep -v "^M " | _hide
COMMIT="$(git rev-parse --short HEAD)"
_ok "Checkout: ${DEPLOY_TAG} (${COMMIT})"

# Checkout edilen tag ile beklenen tag eşleşmeli
ACTUAL_TAG="$(git describe --tags --exact-match HEAD 2>/dev/null || true)"
[[ "${ACTUAL_TAG}" == "${DEPLOY_TAG}" ]] \
  || _fail "Tag doğrulaması başarısız: beklenen '${DEPLOY_TAG}', HEAD='${ACTUAL_TAG}'"
_ok "Tag doğrulandı: ${ACTUAL_TAG}"

# ── Adım 3: Yedek ─────────────────────────────────────────────────────────────
_h "3. Yedek"

if [[ "${SKIP_BACKUP}" == "true" ]]; then
  _warn "--skip-backup aktif. Yedek atlandı."
else
  mkdir -p "${BACKUP_DIR}"

  # DB adı ve kullanıcısını secrets dosyasından oku (terminale yazmadan)
  _PG_DB="$(grep "^POSTGRES_DB=" "${ENV_FILE}" | cut -d= -f2-)"
  _PG_USER="$(grep "^POSTGRES_USER=" "${ENV_FILE}" | cut -d= -f2-)"

  _i "pg_dump başlıyor (${_PG_DB})..."
  DUMP_FILE="${BACKUP_DIR}/db-${BACKUP_STAMP}.sql"
  docker compose ${CF} exec -T db \
    pg_dump -U "${_PG_USER}" "${_PG_DB}" --no-password \
    > "${DUMP_FILE}" 2>/dev/null \
    && _ok "DB yedeği: ${DUMP_FILE}" \
    || _warn "pg_dump başarısız (DB henüz yoksa normaldir — ilk kurulum)"
  # Not: Yedek başarısız olursa _warn ile devam edilir.
  # Bu kasıtlı bir karardır: ilk kurulumda yedeklenecek DB yoktur.
  # Yedek hata vermemesi için --skip-backup kullanılabilir.
  unset _PG_DB _PG_USER

  MINIO_VOL="${COMPOSE_PROJECT_NAME}_minio_data"
  _i "MinIO volume: ${MINIO_VOL}"
  if docker volume inspect "${MINIO_VOL}" > /dev/null 2>&1; then
    docker run --rm \
      -v "${MINIO_VOL}:/minio_src:ro" \
      -v "${BACKUP_DIR}:/backup" \
      alpine tar -czf "/backup/minio-${BACKUP_STAMP}.tar.gz" -C /minio_src . 2>/dev/null \
      && _ok "MinIO yedeği: ${BACKUP_DIR}/minio-${BACKUP_STAMP}.tar.gz" \
      || _warn "MinIO arşivi oluşturulamadı."
  else
    _warn "MinIO volume bulunamadı (${MINIO_VOL}) — ilk kurulum."
  fi

  _ok "Yedekler: ${BACKUP_DIR}/"
fi

# ── Adım 4: Image build ───────────────────────────────────────────────────────
_h "4. Docker image build"

docker compose ${CF} build --no-cache --pull 2>&1 | _hide | tail -8
_ok "Build tamamlandı"

# ── Adım 5: Altyapı servisleri ────────────────────────────────────────────────
_h "5. Altyapı servisleri (db, redis, minio, pdf-service)"

docker compose ${CF} up -d db redis minio pdf-service

_i "db healthy olana kadar bekleniyor (max 90s)..."
timeout 90 bash -c "
  until docker compose ${CF} exec -T db pg_isready -q 2>/dev/null; do
    sleep 3
  done
" && _ok "db healthy" || _fail "db 90 saniyede healthy olmadı — loglar: docker compose logs db"

_i "pdf-service healthy olana kadar bekleniyor (max 60s)..."
timeout 60 bash -c "
  until docker compose ${CF} exec -T pdf-service \
    python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8001/health\", timeout=2)' \
    > /dev/null 2>&1; do
    sleep 3
  done
" && _ok "pdf-service healthy" || _warn "pdf-service 60s içinde healthy olmadı, devam ediliyor."

# ── Adım 6: Alembic migration ─────────────────────────────────────────────────
_h "6. Alembic migration (upgrade head)"

_i "Migration başlıyor..."
# --entrypoint /bin/sh: compose .env-file'dan ${POSTGRES_USER} vb. container env'e geçer.
# Container shell içinde değişkenler hazır — DATABASE_URL doğru kurulur.
docker compose ${CF} run --rm -T --entrypoint /bin/sh api -c '
  exec alembic -c migrations/alembic.ini upgrade head
' 2>&1 | _hide | tail -6
_ok "Migration komutu tamamlandı"

ALEMBIC_CUR="$(
  docker compose ${CF} run --rm -T --entrypoint /bin/sh api -c \
    'alembic -c migrations/alembic.ini current 2>/dev/null' \
  2>/dev/null | tail -1 || true
)"
_i "Alembic current: ${ALEMBIC_CUR}"
echo "${ALEMBIC_CUR}" | grep -q "(head)" \
  || _fail "Migration head'e ulaşamadı — loglar: docker compose logs api"
_ok "Alembic (head) doğrulandı"

# ── Adım 7: API + Frontend + Nginx ────────────────────────────────────────────
_h "7. API, Frontend, Nginx başlat"

docker compose ${CF} up -d api frontend nginx

_i "API healthy olana kadar bekleniyor (max 120s)..."
timeout 120 bash -c "
  until docker compose ${CF} exec -T api \
    curl -sf http://127.0.0.1:8000/api/v1/health > /dev/null 2>&1; do
    sleep 5
  done
" && _ok "API healthy" || _fail "API 120s içinde healthy olmadı — loglar: docker compose logs api"

_i "Nginx proxy test (port ${PROD_PORT})..."
timeout 30 bash -c "
  until curl -sf http://127.0.0.1:${PROD_PORT}/api/v1/health > /dev/null 2>&1; do
    sleep 3
  done
" && _ok "Nginx proxy çalışıyor (127.0.0.1:${PROD_PORT})" \
  || _warn "Nginx proxy testi başarısız (port ${PROD_PORT}) — loglar: docker compose logs nginx"

# ── Adım 8: Production doğrulama ──────────────────────────────────────────────
_h "8. Production doğrulama"

ENV_CHECK="$(
  docker compose ${CF} exec -T api \
    python -c "from app.config import get_settings; print(get_settings().myk_env)" \
  2>/dev/null || echo "ERROR"
)"
_i "MYK_ENV: ${ENV_CHECK}"
[[ "${ENV_CHECK}" == "production" ]] || _fail "API production modunda değil: ${ENV_CHECK}"
_ok "MYK_ENV=production"

OPENAPI_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:${PROD_PORT}/api/openapi.json 2>/dev/null || echo "000")"
_i "OpenAPI HTTP kodu: ${OPENAPI_CODE}"
[[ "${OPENAPI_CODE}" == "404" ]] \
  && _ok "OpenAPI production'da kapalı (404)" \
  || _warn "OpenAPI ${OPENAPI_CODE} döndü (beklenen 404)."

PROTECTED_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:${PROD_PORT}/api/v1/persons 2>/dev/null || echo "000")"
[[ "${PROTECTED_CODE}" == "401" ]] \
  && _ok "Korumalı endpoint → 401" \
  || _warn "Korumalı endpoint ${PROTECTED_CODE} döndü (beklenen 401)."

SVC_TABLE="$(docker compose ${CF} ps --format 'table {{.Name}}\t{{.State}}\t{{.Health}}' 2>/dev/null || true)"
echo ""
echo "${SVC_TABLE}"
echo ""

UNHEALTHY_COUNT="$(grep -c 'unhealthy' <<<"${SVC_TABLE}" || true)"
UNHEALTHY_COUNT="${UNHEALTHY_COUNT:-0}"
[[ "${UNHEALTHY_COUNT}" -eq 0 ]] \
  && _ok "Unhealthy servis yok" \
  || _warn "${UNHEALTHY_COUNT} unhealthy servis var — logları inceleyin."

# ── Adım 9: Smoke test ────────────────────────────────────────────────────────
_h "9. Smoke test"

if [[ "${SKIP_SMOKE}" == "true" ]]; then
  _warn "--skip-smoke ile atlandı."
else
  SMOKE_SCRIPT="${REMOTE_DIR}/scripts/smoke_test_production.sh"
  if [[ -f "${SMOKE_SCRIPT}" ]]; then
    # Smoke test sunucuda çalışır — BASE_URL geçilerek REMOTE_MODE=false yapılır.
    # REMOTE_MODE=true olsaydı "myk-server" alias'ına SSH atardı (Mac'te tanımlı, sunucuda yok).
    if bash "${SMOKE_SCRIPT}" "http://127.0.0.1:${PROD_PORT}"; then
      _ok "Smoke test PASS ✅"
    else
      _fail "Smoke test FAIL ❌ — yukarıdaki başarısız testleri inceleyin. Deploy başarılı sayılmıyor."
    fi
  else
    _warn "smoke_test_production.sh bulunamadı: ${SMOKE_SCRIPT}"
  fi
fi

# ── Özet ──────────────────────────────────────────────────────────────────────
_h "Deploy Tamamlandı 🚀"
echo ""
echo "  Tag:    ${DEPLOY_TAG}"
echo "  Commit: ${COMMIT}"
echo "  Port:   ${PROD_PORT}"
[[ "${SKIP_BACKUP}" == "false" ]] && echo "  Yedek:  ${BACKUP_DIR}" || true
echo ""

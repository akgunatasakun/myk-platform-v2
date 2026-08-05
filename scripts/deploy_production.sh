#!/usr/bin/env bash
# deploy_production.sh — MYK Platform V2 Production Deploy
#
# Kullanım (Mac'ten):
#   bash scripts/deploy_production.sh [--tag v0.4.1] [--skip-backup] [--skip-smoke]
#
# Ne yapar:
#   1. Mac ön koşul kontrolü (SSH, git temiz ağaç, tag)
#   2. Sunucu ortam doğrulama (.env, MYK_ENV, ALLOW_PUBLIC_SETUP, secret placeholder yok)
#   3. Fresh install (repo yoksa clone eder, varsa günceller)
#   4. PostgreSQL yedeği (pg_dump) + MinIO volume yedeği
#   5. git checkout <tag>
#   6. docker compose build --no-cache
#   7. db / redis / minio / pdf-service başlat, healthy bekle
#   8. Alembic upgrade head (--entrypoint /bin/sh yöntemi, myk_user DDL yetkisi)
#   9. api / frontend / nginx başlat, API healthy bekle
#  10. Smoke test (smoke_test_production.sh)
#
# Güvenlik kuralları (bu script boyunca):
#   ✗  .env'e hiçbir zaman dokunma, üzerine yazma, source etme
#   ✗  Secret değerlerini çıktıda gösterme
#   ✗  docker compose down -v çalıştırma
#   ✗  Production DB'ye doğrudan SQL çalıştırma
#   ✗  ufw değiştirme
#   ✗  certbot çalıştırma (DNS hazır değilse)

set -Eeuo pipefail

# ── Parametreler ───────────────────────────────────────────────────────────────
DEPLOY_TAG="v0.4.1"
SKIP_BACKUP=false
SKIP_SMOKE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)          DEPLOY_TAG="$2"; shift 2 ;;
    --skip-backup)  SKIP_BACKUP=true;  shift ;;
    --skip-smoke)   SKIP_SMOKE=true;   shift ;;
    *) echo "Bilinmeyen parametre: $1" >&2; exit 1 ;;
  esac
done

# ── Mac taraflı sabitler ────────────────────────────────────────────────────────
SERVER="myk-server"                          # ~/.ssh/config Host alias
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_STAMP="$(date +%Y%m%d_%H%M%S)"       # Mac zamanı — tutarlı olsun diye burada üret

_header() { printf '\n══════ %s ══════\n' "$*"; }
_ok()     { printf '  ✓  %s\n' "$*"; }
_fail()   { printf '  ✗  HATA: %s\n' "$*" >&2; exit 1; }
_warn()   { printf '  ⚠  %s\n' "$*"; }

# ════════════════════════════════════════════════════════════════════════════════
# BÖLÜM 1 — MAC ÖN KOŞUL KONTROLÜ
# ════════════════════════════════════════════════════════════════════════════════
_header "1. Mac ön koşul kontrolü"

# SSH bağlantısı
ssh -q -o BatchMode=yes -o ConnectTimeout=8 "${SERVER}" exit \
  || _fail "SSH bağlantısı kurulamadı. ~/.ssh/config içindeki '${SERVER}' alias'ını kontrol edin."
_ok "SSH → ${SERVER} OK"

# Git temiz çalışma ağacı
if ! git -C "${SCRIPT_DIR}/.." diff-index --quiet HEAD -- 2>/dev/null; then
  _fail "Commit edilmemiş değişiklikler var. 'git status' ile kontrol edin."
fi
_ok "Git çalışma ağacı temiz"

# Tag kontrolü
CURRENT_TAG="$(git -C "${SCRIPT_DIR}/.." describe --tags --exact-match HEAD 2>/dev/null || true)"
if [[ -z "${CURRENT_TAG}" ]]; then
  _warn "HEAD bir tag'e işaret etmiyor. --tag ${DEPLOY_TAG} ile devam edilecek."
  read -rp "  Onaylıyor musunuz? [y/N] " _confirm
  [[ "${_confirm,,}" == "y" ]] || { echo "İptal edildi."; exit 0; }
else
  _ok "Tag: ${CURRENT_TAG}"
  [[ "${CURRENT_TAG}" == "${DEPLOY_TAG}" ]] \
    || _warn "HEAD tag (${CURRENT_TAG}) ≠ --tag (${DEPLOY_TAG}). Deploy TAG ile devam ediyor."
fi

# ════════════════════════════════════════════════════════════════════════════════
# BÖLÜM 2–9 — SUNUCU OPERASYONLARI
# Tüm sunucu kodu <<'SERVERSCRIPT' (quoted heredoc) içinde — Mac bash genişletmesi yok.
# Mac'ten gelen dinamik değerler bash -s argümanlarıyla geçirilir.
# ════════════════════════════════════════════════════════════════════════════════
ssh "${SERVER}" bash -s \
    "${DEPLOY_TAG}" \
    "${BACKUP_STAMP}" \
    "${SKIP_BACKUP}" \
    <<'SERVERSCRIPT'
set -Eeuo pipefail

# Argümanlar (Mac'ten geçirildi)
DEPLOY_TAG="$1"
BACKUP_STAMP="$2"
SKIP_BACKUP="$3"

# Sunucu sabitleri
REMOTE_DIR="/opt/myk/production/myk-platform-v2"
BACKUP_DIR="/opt/myk/backups/production-${BACKUP_STAMP}"
GITHUB_REPO="git@github.com:akgunatasakun/myk-platform-v2.git"
ENV_FILE="/etc/myk/production.env"                       # secrets repo dışında
CF="--env-file ${ENV_FILE} -f docker-compose.yml -f docker-compose.prod.yml"
PROD_PORT=18081                                          # nginx dış portu
COMPOSE_PROJECT_NAME="myk-production"                   # docker compose project adı
export COMPOSE_PROJECT_NAME

_h()  { printf '\n══════ %s ══════\n' "$*"; }
_ok() { printf '  ✓  %s\n' "$*"; }
_w()  { printf '  ⚠  %s\n' "$*"; }
_e()  { printf '  ✗  %s\n' "$*" >&2; exit 1; }
_i()  { printf '  ·  %s\n' "$*"; }

# Secret içerebilecek satırları filtrele
_hide() { grep -vE '(PASSWORD|SECRET_KEY|JWT_SECRET|ACCESS_KEY)=[^[:space:]]' || true; }

# ── Adım 2: Ortam doğrulama ───────────────────────────────────────────────────
_h "2. Sunucu ortam doğrulama"

_i "Docker: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'bulunamadı')"
_i "Compose: $(docker compose version --short 2>/dev/null || echo 'bulunamadı')"
_i "Git: $(git --version 2>/dev/null | head -1 || echo 'bulunamadı')"

# docker ve git zorunlu
docker version > /dev/null 2>&1 || _e "Docker yüklü değil veya daemon çalışmıyor."
docker compose version > /dev/null 2>&1 || _e "docker compose eklentisi bulunamadı."
git --version > /dev/null 2>&1 || _e "git bulunamadı."
_ok "Bağımlılıklar mevcut"

# Secrets dosyası kontrolü (değerleri göstermeden)
ENV_FILE="/etc/myk/production.env"
if [[ -f "${ENV_FILE}" ]]; then
  _ok ".env mevcut"
  for var in MYK_ENV JWT_SECRET_KEY SECRET_KEY POSTGRES_PASSWORD ALLOW_PUBLIC_SETUP \
             STORAGE_ACCESS_KEY STORAGE_SECRET_KEY; do
    val="$(grep "^${var}=" "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || true)"
    if [[ -z "${val}" ]]; then
      _e ".env içinde ${var} tanımlı değil."
    elif echo "${val}" | grep -qiE "REPLACE_WITH|CHANGE_ME"; then
      _e ".env içinde ${var} hâlâ placeholder değer içeriyor."
    fi
    _ok "${var} tanımlı"
  done

  MYK_ENV_VAL="$(grep "^MYK_ENV=" "${ENV_FILE}" | cut -d= -f2- || true)"
  [[ "${MYK_ENV_VAL}" == "production" ]] || _e "MYK_ENV=production değil: ${MYK_ENV_VAL}"
  _ok "MYK_ENV=production"

  SETUP_VAL="$(grep "^ALLOW_PUBLIC_SETUP=" "${ENV_FILE}" | cut -d= -f2- || true)"
  [[ "${SETUP_VAL,,}" == "false" ]] || _e "ALLOW_PUBLIC_SETUP=false değil: ${SETUP_VAL}"
  _ok "ALLOW_PUBLIC_SETUP=false"
else
  _e "Secrets dosyası bulunamadı: ${ENV_FILE}
  Önce sunucuda root olarak:
    sudo mkdir -p /etc/myk
    sudo cp /opt/myk/production/myk-platform-v2/.env /etc/myk/production.env
    sudo chown root:myk-deploy /etc/myk/production.env
    sudo chmod 640 /etc/myk/production.env"
fi

# ── Adım 3: Fresh install veya güncelleme ─────────────────────────────────────
_h "3. Kaynak kodu güncelle"

if [[ ! -d "${REMOTE_DIR}/.git" ]]; then
  _w "Repo mevcut değil — ilk kurulum yapılıyor..."
  mkdir -p "$(dirname "${REMOTE_DIR}")"
  git clone "${GITHUB_REPO}" "${REMOTE_DIR}" 2>&1 \
    || _e "git clone başarısız. Sunucuda GitHub SSH erişimi var mı? (ssh -T git@github.com)"
  _ok "Repo klonlandı: ${REMOTE_DIR}"
fi

cd "${REMOTE_DIR}"

git fetch origin --tags --prune 2>&1 | _hide
git checkout "${DEPLOY_TAG}" 2>&1 | grep -v "^M " | _hide
COMMIT="$(git rev-parse --short HEAD)"
_ok "Checkout: ${DEPLOY_TAG} (${COMMIT})"
# Secrets /etc/myk/production.env'de — git checkout buna dokunamaz.

# ── Adım 4: Yedek ─────────────────────────────────────────────────────────────
_h "4. Yedek"

if [[ "${SKIP_BACKUP}" == "true" ]]; then
  _w "--skip-backup aktif. Yedek atlandı."
else
  mkdir -p "${BACKUP_DIR}"

  # DB adı ve kullanıcı adını .env'den oku (değerleri loga yazmadan)
  _PG_DB="$(grep "^POSTGRES_DB=" .env | cut -d= -f2-)"
  _PG_USER="$(grep "^POSTGRES_USER=" .env | cut -d= -f2-)"

  # pg_dump — docker compose exec üzerinden (PGPASSWORD terminale düşmez)
  _i "pg_dump başlıyor (${_PG_DB})..."
  DUMP_FILE="${BACKUP_DIR}/db-${BACKUP_STAMP}.sql"
  docker compose ${CF} exec -T db \
    pg_dump -U "${_PG_USER}" "${_PG_DB}" --no-password \
    > "${DUMP_FILE}" 2>/dev/null \
    && _ok "DB yedeği: ${DUMP_FILE}" \
    || _w "pg_dump başarısız (DB henüz yoksa normaldir — ilk kurulum)"
  unset _PG_DB _PG_USER

  # MinIO volume yedeği (volume yoksa uyarı ver, dur)
  MINIO_VOL="${COMPOSE_PROJECT_NAME}_minio_data"
  _i "MinIO volume: ${MINIO_VOL}"
  if docker volume inspect "${MINIO_VOL}" > /dev/null 2>&1; then
    docker run --rm \
      -v "${MINIO_VOL}:/minio_src:ro" \
      -v "${BACKUP_DIR}:/backup" \
      alpine tar -czf "/backup/minio-${BACKUP_STAMP}.tar.gz" -C /minio_src . 2>/dev/null \
      && _ok "MinIO yedeği: ${BACKUP_DIR}/minio-${BACKUP_STAMP}.tar.gz" \
      || _w "MinIO arşivi oluşturulamadı."
  else
    _w "MinIO volume bulunamadı (${MINIO_VOL}) — ilk kurulum veya farklı compose project adı."
  fi

  _ok "Yedekler: ${BACKUP_DIR}/"
fi

# ── Adım 5: Image build ────────────────────────────────────────────────────────
_h "5. Docker image build"

docker compose ${CF} build --no-cache --pull 2>&1 | _hide | tail -8
_ok "Build tamamlandı"

# ── Adım 6: Altyapı servisleri ────────────────────────────────────────────────
_h "6. Altyapı servisleri başlat (db, redis, minio, pdf-service)"

docker compose ${CF} up -d db redis minio pdf-service

_i "db healthy olana kadar bekleniyor (max 90s)..."
timeout 90 bash -c '
  until docker compose '"${CF}"' exec -T db pg_isready -q 2>/dev/null; do
    sleep 3
  done
' && _ok "db healthy" || _e "db 90 saniyede healthy olmadı. Loglar: docker compose logs db"

_i "pdf-service healthy olana kadar bekleniyor (max 60s)..."
timeout 60 bash -c '
  until docker compose '"${CF}"' exec -T pdf-service \
    python -c "import urllib.request; urllib.request.urlopen('"'"'http://127.0.0.1:8001/health'"'"', timeout=2)" \
    > /dev/null 2>&1; do
    sleep 3
  done
' && _ok "pdf-service healthy" || _w "pdf-service 60s içinde healthy olmadı, devam ediliyor."

# ── Adım 7: Alembic migration ─────────────────────────────────────────────────
_h "7. Alembic migration (upgrade head)"

_i "Migration başlıyor..."
# --entrypoint /bin/sh yöntemi: compose .env'den ${POSTGRES_USER} vb. container env'e geçer.
# Container shell içinde bu değişkenler hazır olduğu için DATABASE_URL doğru kurulur.
# .env'i source etmiyoruz — compose environment: bloğu hallediyor.
docker compose ${CF} run --rm -T --entrypoint /bin/sh api -c '
  exec alembic -c migrations/alembic.ini upgrade head
' 2>&1 | _hide | tail -6
_ok "Migration komutu tamamlandı"

# Alembic head doğrulama
ALEMBIC_CUR="$(
  docker compose ${CF} run --rm -T --entrypoint /bin/sh api -c \
    'alembic -c migrations/alembic.ini current 2>/dev/null' \
  2>/dev/null | tail -1 || true
)"
_i "Alembic current: ${ALEMBIC_CUR}"
echo "${ALEMBIC_CUR}" | grep -q "(head)" \
  || _e "Migration head'e ulaşamadı! Loglar: docker compose logs api"
_ok "Alembic (head) doğrulandı"

# ── Adım 8: API + Frontend + Nginx ────────────────────────────────────────────
_h "8. API, Frontend, Nginx başlat"

docker compose ${CF} up -d api frontend nginx

_i "API healthy olana kadar bekleniyor (max 120s)..."
timeout 120 bash -c '
  until docker compose '"${CF}"' exec -T api \
    curl -sf http://127.0.0.1:8000/api/v1/health > /dev/null 2>&1; do
    sleep 5
  done
' && _ok "API healthy (container iç ağ)" || _e "API 120s içinde healthy olmadı. Loglar: docker compose logs api"

_i "Nginx üzerinden test (port ${PROD_PORT})..."
timeout 30 bash -c "
  until curl -sf http://127.0.0.1:${PROD_PORT}/api/v1/health > /dev/null 2>&1; do
    sleep 3
  done
" && _ok "Nginx proxy çalışıyor (localhost:${PROD_PORT})" \
  || _w "Nginx proxy testi başarısız (port ${PROD_PORT}). Nginx log: docker compose logs nginx"

# ── Adım 9: Temel üretim doğrulaması ──────────────────────────────────────────
_h "9. Üretim doğrulama"

# MYK_ENV=production
ENV_CHECK="$(
  docker compose ${CF} exec -T api \
    python -c "from app.config import get_settings; print(get_settings().myk_env)" \
  2>/dev/null || echo "ERROR"
)"
_i "MYK_ENV: ${ENV_CHECK}"
[[ "${ENV_CHECK}" == "production" ]] \
  || _e "API production modunda değil: ${ENV_CHECK}"
_ok "MYK_ENV=production"

# OpenAPI production'da kapalı olmalı (404)
OPENAPI_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:${PROD_PORT}/api/openapi.json 2>/dev/null || echo "000")"
_i "OpenAPI HTTP kodu: ${OPENAPI_CODE}"
[[ "${OPENAPI_CODE}" == "404" ]] \
  && _ok "OpenAPI production'da kapalı (404)" \
  || _w "OpenAPI ${OPENAPI_CODE} döndü (beklenen 404). FastAPI OPENAPI_URL ayarını kontrol edin."

# Korumalı endpoint token olmadan 401
PROTECTED_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:${PROD_PORT}/api/v1/persons 2>/dev/null || echo "000")"
_i "Korumalı endpoint kodu: ${PROTECTED_CODE}"
[[ "${PROTECTED_CODE}" == "401" ]] \
  && _ok "Korumalı endpoint → 401 (doğru)" \
  || _w "Korumalı endpoint ${PROTECTED_CODE} döndü (beklenen 401)."

# Alembic son kez doğrula
ALEMBIC_FINAL="$(
  docker compose ${CF} run --rm -T --entrypoint /bin/sh api -c \
    'alembic -c migrations/alembic.ini current 2>/dev/null' \
  2>/dev/null | tail -1 || true
)"
echo "${ALEMBIC_FINAL}" | grep -q "(head)" \
  && _ok "Alembic (head) doğrulandı" \
  || _w "Alembic current: ${ALEMBIC_FINAL}"

# Tüm servisler running?
SVC_TABLE="$(docker compose ${CF} ps --format 'table {{.Name}}\t{{.State}}\t{{.Health}}' 2>/dev/null || true)"
echo ""
echo "${SVC_TABLE}"
echo ""

UNHEALTHY_COUNT="$(echo "${SVC_TABLE}" | grep -c "unhealthy" || true)"
[[ "${UNHEALTHY_COUNT}" -eq 0 ]] \
  && _ok "Unhealthy servis yok" \
  || _w "${UNHEALTHY_COUNT} unhealthy servis var — logları inceleyin."

_h "Sunucu tarafı tamamlandı ✓"
echo "  Tag:    ${DEPLOY_TAG}"
echo "  Commit: ${COMMIT}"
echo "  Port:   ${PROD_PORT}"
[[ "${SKIP_BACKUP}" == "false" ]] && echo "  Yedek:  ${BACKUP_DIR}"
SERVERSCRIPT

# ════════════════════════════════════════════════════════════════════════════════
# BÖLÜM 3 — SMOKE TEST (Mac taraflı — sunucuya SSH eder)
# ════════════════════════════════════════════════════════════════════════════════
if [[ "${SKIP_SMOKE}" == "true" ]]; then
  _warn "Smoke test --skip-smoke ile atlandı."
else
  _header "10. Smoke test"
  SMOKE_SCRIPT="${SCRIPT_DIR}/smoke_test_production.sh"
  if [[ -f "${SMOKE_SCRIPT}" ]]; then
    if bash "${SMOKE_SCRIPT}"; then
      _ok "Smoke test PASS ✅"
    else
      _fail "Smoke test FAIL ❌ — yukarıdaki başarısız testleri inceleyin. Deploy başarılı sayılmıyor."
    fi
  else
    _warn "smoke_test_production.sh bulunamadı: ${SMOKE_SCRIPT}"
    _warn "Manuel olarak çalıştırın: bash scripts/smoke_test_production.sh"
  fi
fi

# ════════════════════════════════════════════════════════════════════════════════
# ÖZET
# ════════════════════════════════════════════════════════════════════════════════
_header "Deploy Tamamlandı 🚀"
echo ""
echo "  Tag:    ${DEPLOY_TAG}"
echo "  Sunucu: ${SERVER}"
echo "  URL:    http://$(ssh "${SERVER}" 'curl -4 -fsS ifconfig.me 2>/dev/null || hostname -I | awk "{print \$1}"'):18081"
echo ""
echo "  Sorun çıkarsa rollback:"
echo "    Bkz. docs/RUNBOOK.md"
echo ""

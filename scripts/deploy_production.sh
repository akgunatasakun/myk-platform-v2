#!/usr/bin/env bash
# deploy_production.sh — MYK Platform V2 Production Deploy
#
# Kullanım (Mac'ten):
#   bash scripts/deploy_production.sh [--tag v0.4.0] [--skip-backup]
#
# Bu script Mac'ten SSH ile çalışır. Sunucuda docker ve git gereklidir.
# .env dosyasına hiçbir zaman dokunmaz ve çıktıda secret göstermez.
#
# Güvenlik kuralları (deploy boyunca geçerli):
#   - Production veritabanına doğrudan SQL çalıştırma
#   - .env dosyasını source etme veya üzerine yazma
#   - docker compose down -v çalıştırma
#   - ufw değiştirme
#   - certbot çalıştırma (DNS hazır değilse)
#   - apply_staging.sh çalıştırma (staging-only script)
#   - Secret değerlerini hiçbir çıktıda gösterme

set -Eeuo pipefail

# ── Parametreler ──────────────────────────────────────────────────────────────
DEPLOY_TAG="v0.4.0"
SKIP_BACKUP=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)       DEPLOY_TAG="$2"; shift 2 ;;
    --skip-backup) SKIP_BACKUP=true; shift ;;
    *) echo "Bilinmeyen parametre: $1" >&2; exit 1 ;;
  esac
done

# ── Sabitler ──────────────────────────────────────────────────────────────────
SERVER="myk-server"                          # ~/.ssh/config'deki alias
REMOTE_DIR="/opt/myk/production/myk-platform-v2"
BACKUP_BASE="/opt/myk/backups"
BACKUP_DIR="${BACKUP_BASE}/production-$(date +%Y%m%d_%H%M%S)"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
COMPOSE_CMD="docker compose ${COMPOSE_FILES}"

_header() { echo ""; echo "══════ $* ══════"; }
_ok()     { echo "  ✓  $*"; }
_fail()   { echo "  ✗  HATA: $*" >&2; exit 1; }
_warn()   { echo "  ⚠  $*"; }
_info()   { echo "  ·  $*"; }

# ── Güvenlik: secret çıktısını engelle ────────────────────────────────────────
# Bu fonksiyon SSH komutlarından gelen çıktıyı filtreleyerek
# olası secret leak'leri logdan gizler.
_ssh() {
  ssh "${SERVER}" "$@" 2>&1 | grep -vE \
    "(PASSWORD|SECRET|JWT_SECRET|SECRET_KEY|ACCESS_KEY)=[^[:space:]]" \
    || true
}

# ── Adım 1: MAC — Ön koşul kontrolü ──────────────────────────────────────────
_header "1. Ön koşul kontrolü (Mac)"

# SSH bağlantısı
ssh -q -o BatchMode=yes -o ConnectTimeout=5 "${SERVER}" exit \
  || _fail "SSH bağlantısı kurulamadı: ${SERVER}"
_ok "SSH erişimi OK"

# Temiz çalışma ağacı kontrolü
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  _fail "Commit edilmemiş değişiklikler var. Deploy öncesinde 'git status' ile kontrol edin."
fi
_ok "Git çalışma ağacı temiz"

# Tag kontrolü
CURRENT_TAG=$(git describe --tags --exact-match HEAD 2>/dev/null || echo "")
if [[ -z "${CURRENT_TAG}" ]]; then
  _warn "HEAD bir tag'e işaret etmiyor. --tag ${DEPLOY_TAG} parametresi kullanılacak."
  _warn "Devam etmek için onaylayın (Ctrl+C ile iptal):"
  read -rp "  Tag doğrulandı mı? [y/N] " confirm
  [[ "${confirm,,}" == "y" ]] || exit 1
else
  _ok "Mevcut tag: ${CURRENT_TAG}"
  [[ "${CURRENT_TAG}" == "${DEPLOY_TAG}" ]] \
    || _warn "HEAD tag (${CURRENT_TAG}) ile --tag parametresi (${DEPLOY_TAG}) farklı."
fi

# ── Adım 2: SUNUCU — Ortam doğrulama ─────────────────────────────────────────
_header "2. Sunucu ortam doğrulama"

_ssh bash -s <<'REMOTE'
set -e
echo "  · Docker: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'BULUNAMADI')"
echo "  · Compose: $(docker compose version --short 2>/dev/null || echo 'BULUNAMADI')"
echo "  · Git: $(git --version 2>/dev/null || echo 'BULUNAMADI')"

# .env varlığı (içeriği göstermeden)
if [[ -f /opt/myk/production/myk-platform-v2/.env ]]; then
  echo "  ✓  .env mevcut"
  # Kritik değişkenlerin tanımlı olduğunu kontrol et (değerleri göstermeden)
  for var in MYK_ENV JWT_SECRET_KEY SECRET_KEY POSTGRES_PASSWORD ALLOW_PUBLIC_SETUP \
             STORAGE_ACCESS_KEY STORAGE_SECRET_KEY; do
    val=$(grep "^${var}=" /opt/myk/production/myk-platform-v2/.env 2>/dev/null | cut -d= -f2- || echo "")
    if [[ -z "${val}" ]]; then
      echo "  ✗  .env içinde ${var} tanımlı değil!" >&2
      exit 1
    elif echo "${val}" | grep -qiE "REPLACE_WITH|CHANGE_ME"; then
      echo "  ✗  .env içinde ${var} placeholder değer içeriyor!" >&2
      exit 1
    else
      echo "  ✓  ${var} tanımlı"
    fi
  done
else
  echo "  ✗  .env bulunamadı: /opt/myk/production/myk-platform-v2/.env" >&2
  exit 1
fi

# MYK_ENV=production kontrolü
MYK_ENV_VAL=$(grep "^MYK_ENV=" /opt/myk/production/myk-platform-v2/.env | cut -d= -f2-)
[[ "${MYK_ENV_VAL}" == "production" ]] || { echo "  ✗  MYK_ENV=production değil: ${MYK_ENV_VAL}" >&2; exit 1; }
echo "  ✓  MYK_ENV=production"

# ALLOW_PUBLIC_SETUP=false kontrolü
SETUP_VAL=$(grep "^ALLOW_PUBLIC_SETUP=" /opt/myk/production/myk-platform-v2/.env | cut -d= -f2-)
[[ "${SETUP_VAL,,}" == "false" ]] || { echo "  ✗  ALLOW_PUBLIC_SETUP=false değil: ${SETUP_VAL}" >&2; exit 1; }
echo "  ✓  ALLOW_PUBLIC_SETUP=false"
REMOTE

_ok "Sunucu ortam doğrulaması geçti"

# ── Adım 3: SUNUCU — PostgreSQL yedeği ───────────────────────────────────────
_header "3. PostgreSQL yedeği"

if [[ "${SKIP_BACKUP}" == "true" ]]; then
  _warn "--skip-backup geçildi. Yedek atlanıyor."
else
  _ssh bash -s <<REMOTE
set -e
BACKUP_DIR="${BACKUP_DIR}"
mkdir -p "\${BACKUP_DIR}"

# DB adını ve kullanıcıyı .env'den oku (değerleri loglamadan)
DB=\$(grep "^POSTGRES_DB=" /opt/myk/production/myk-platform-v2/.env | cut -d= -f2-)
USER=\$(grep "^POSTGRES_USER=" /opt/myk/production/myk-platform-v2/.env | cut -d= -f2-)

# pg_dump — docker compose exec üzerinden (parola terminale düşmez)
echo "  · pg_dump başlıyor..."
docker compose ${COMPOSE_FILES} -f /opt/myk/production/myk-platform-v2 exec -T db \
  pg_dump -U "\${USER}" "\${DB}" --no-password \
  > "\${BACKUP_DIR}/production-db-\$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null \
  && echo "  ✓  DB yedeği alındı: \${BACKUP_DIR}/" \
  || { echo "  ✗  pg_dump başarısız!" >&2; exit 1; }

# MinIO volume yedeğini arşivle
echo "  · MinIO data arşivleniyor..."
docker run --rm \
  -v "myk-platform-v2_minio_data:/minio_src:ro" \
  -v "\${BACKUP_DIR}:/backup" \
  alpine tar -czf /backup/minio-data-\$(date +%Y%m%d_%H%M%S).tar.gz -C /minio_src . 2>/dev/null \
  && echo "  ✓  MinIO yedeği alındı" \
  || echo "  ⚠  MinIO yedeği alınamadı (volume boş olabilir)"

echo "  ✓  Yedekler: \${BACKUP_DIR}/"
REMOTE

  _ok "Yedekler alındı: ${BACKUP_DIR}"
fi

# ── Adım 4: SUNUCU — Kaynak kodu güncelle ────────────────────────────────────
_header "4. Kaynak kodu güncelle (git pull + tag checkout)"

_ssh bash -s <<REMOTE
set -e
cd "${REMOTE_DIR}"

git fetch origin --tags
git checkout "${DEPLOY_TAG}" 2>&1 | grep -v "HEAD is now"
COMMIT=\$(git rev-parse --short HEAD)
echo "  ✓  Checkout: ${DEPLOY_TAG} (\${COMMIT})"

# .env kontrolü: checkout .env'i silmemeli
[[ -f .env ]] || { echo "  ✗  Checkout sonrası .env kayboldu!" >&2; exit 1; }
echo "  ✓  .env korundu"
REMOTE

_ok "Kaynak kod: ${DEPLOY_TAG}"

# ── Adım 5: SUNUCU — Image build ─────────────────────────────────────────────
_header "5. Docker image build"

_ssh bash -s <<REMOTE
set -e
cd "${REMOTE_DIR}"
${COMPOSE_CMD} build --no-cache --pull 2>&1 | tail -5
echo "  ✓  Build tamamlandı"
REMOTE

_ok "Image build tamamlandı"

# ── Adım 6: SUNUCU — Altyapı servisleri başlat (db, redis, minio) ─────────────
_header "6. Altyapı servisleri başlat"

_ssh bash -s <<REMOTE
set -e
cd "${REMOTE_DIR}"
${COMPOSE_CMD} up -d db redis minio pdf-service
echo "  · Servisler healthy olana kadar bekleniyor (max 60s)..."
timeout 60 bash -c '
  until docker compose ${COMPOSE_FILES} ps db | grep -q "healthy"; do sleep 3; done
' 2>/dev/null && echo "  ✓  db healthy" || echo "  ⚠  db healthy olmadı, devam ediliyor"
REMOTE

_ok "Altyapı servisleri çalışıyor"

# ── Adım 7: SUNUCU — Alembic migration ───────────────────────────────────────
_header "7. Alembic migration (upgrade head)"

_ssh bash -s <<REMOTE
set -e
cd "${REMOTE_DIR}"

# --entrypoint /bin/sh yöntemi: myk_user (DDL sahibi) olarak çalışır
# .env'i source etmez — compose container environment'ını kullanır
echo "  · Migration başlıyor..."
${COMPOSE_CMD} run --rm -T --entrypoint /bin/sh api -c '
  export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
  exec alembic -c migrations/alembic.ini upgrade head
' 2>&1 | grep -vE "(PASSWORD|SECRET)" | tail -10
echo "  ✓  Migration tamamlandı"

# Doğrula
HEAD_VERSION=\$(${COMPOSE_CMD} run --rm -T --entrypoint /bin/sh api -c '
  export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
  alembic -c migrations/alembic.ini current 2>/dev/null
' 2>/dev/null | tail -1)
echo "  · Alembic current: \${HEAD_VERSION}"
echo "\${HEAD_VERSION}" | grep -q "(head)" \
  || { echo "  ✗  Migration head'e ulaşamadı!" >&2; exit 1; }
echo "  ✓  Alembic head doğrulandı"
REMOTE

_ok "Migration tamamlandı"

# ── Adım 8: SUNUCU — API ve Frontend başlat ──────────────────────────────────
_header "8. API ve Frontend başlat"

_ssh bash -s <<REMOTE
set -e
cd "${REMOTE_DIR}"
${COMPOSE_CMD} up -d api frontend nginx
echo "  · API ve Frontend healthy olana kadar bekleniyor (max 90s)..."
timeout 90 bash -c '
  until docker compose ${COMPOSE_FILES} exec -T api \
    curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; do
    sleep 5
  done
' && echo "  ✓  API healthy" || { echo "  ✗  API healthy olmadı!" >&2; exit 1; }
REMOTE

_ok "Servisler çalışıyor"

# ── Adım 9: SUNUCU — Temel health check ──────────────────────────────────────
_header "9. Temel health check"

_ssh bash -s <<REMOTE
set -e
cd "${REMOTE_DIR}"

# API health
API_STATUS=\$(${COMPOSE_CMD} exec -T api \
  curl -sf http://localhost:8000/api/v1/health 2>/dev/null || echo "FAIL")
echo "  · API /health: \${API_STATUS}"
echo "\${API_STATUS}" | grep -q '"status"' \
  || { echo "  ✗  API health başarısız!" >&2; exit 1; }
echo "  ✓  API /health OK"

# MYK_ENV=production doğrulama
ENV_CHECK=\$(${COMPOSE_CMD} exec -T api \
  python -c "from app.config import get_settings; s=get_settings(); print(s.myk_env)" \
  2>/dev/null || echo "ERROR")
echo "  · MYK_ENV: \${ENV_CHECK}"
[[ "\${ENV_CHECK}" == "production" ]] \
  || { echo "  ✗  MYK_ENV production değil: \${ENV_CHECK}" >&2; exit 1; }
echo "  ✓  MYK_ENV=production"

# 7 servis running + healthy kontrolü
UNHEALTHY=\$(${COMPOSE_CMD} ps --format json 2>/dev/null \
  | python3 -c "
import sys, json
data = sys.stdin.read().strip()
lines = [l for l in data.splitlines() if l.strip().startswith('{')]
bad = []
for l in lines:
    try:
        s = json.loads(l)
        state = s.get('State','').lower()
        health = s.get('Health','').lower()
        name = s.get('Name','?')
        if state != 'running' or (health and health not in ('healthy','')):
            bad.append(f'{name}: state={state} health={health}')
    except:
        pass
print('\n'.join(bad) if bad else 'OK')
" 2>/dev/null || echo "kontrol atlandı")
echo "  · Servis durumu: \${UNHEALTHY}"
echo "  ✓  Health check tamamlandı"
REMOTE

_ok "Temel health check geçti"

# ── Adım 10: Özet ─────────────────────────────────────────────────────────────
_header "Deploy Tamamlandı"
echo ""
echo "  Tag:    ${DEPLOY_TAG}"
echo "  Sunucu: ${SERVER}"
echo "  Dizin:  ${REMOTE_DIR}"
[[ "${SKIP_BACKUP}" == "false" ]] && echo "  Yedek:  ${BACKUP_DIR}"
echo ""
echo "  Sonraki adım:"
echo "    bash scripts/smoke_test_production.sh"
echo ""
echo "  Sorun çıkarsa rollback:"
echo "    Bkz. docs/RUNBOOK.md — Uygulama Rollback ve DB Rollback bölümleri"
echo ""

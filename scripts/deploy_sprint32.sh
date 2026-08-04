#!/usr/bin/env bash
# Sprint 3.2 Deployment — Mac'ten çalıştırılır
#
# Kullanım:
#   bash scripts/deploy_sprint32.sh
#
# Ön koşullar:
#   - myk-sprint-3.2-delta.tar.gz seçili klasörde mevcut olmalı
#   - SSH erişimi: root@46.224.26.120
#   - Sunucuda /opt/myk/staging/myk-platform-v2 mevcut

set -Eeuo pipefail

# ── Sabitler ──────────────────────────────────────────────────────────────────
SERVER="myk-server"
REMOTE_DIR="/opt/myk/staging/myk-platform-v2"
REMOTE_TMP="/tmp/myk-sprint32-deploy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE="$(cd "${PROJECT_ROOT}/.." && pwd)"
ARCHIVE="${WORKSPACE}/myk-sprint-3.2-delta.tar.gz"
EXPECTED_SHA="2a9a40ada8f03687b8d629cd19971c3f47b356811e40aa0681222d899927a658"
EXPECTED_FILES=35
BACKUP_DIR="/opt/myk/backups/sprint32-$(date +%Y%m%d_%H%M%S)"

_header() { echo ""; echo "══ $* ══"; }
_ok()     { echo "  ✓ $*"; }
_fail()   { echo "  ✗ HATA: $*" >&2; exit 1; }
_warn()   { echo "  ⚠ $*"; }

# ── Adım 1: MAC — SHA-256 + dosya sayısı + arşiv prefix belirleme ─────────────
_header "1. Arşiv doğrulama (Mac)"

[[ -f "${ARCHIVE}" ]] || _fail "Arşiv bulunamadı: ${ARCHIVE}"

if command -v sha256sum &>/dev/null; then
  ACTUAL_SHA=$(sha256sum "${ARCHIVE}" | cut -d' ' -f1)
else
  ACTUAL_SHA=$(shasum -a 256 "${ARCHIVE}" | cut -d' ' -f1)
fi

[[ "${ACTUAL_SHA}" == "${EXPECTED_SHA}" ]] \
  || _fail "SHA-256 uyuşmuyor!\n  Beklenen: ${EXPECTED_SHA}\n  Alınan:   ${ACTUAL_SHA}"
_ok "SHA-256 doğrulandı"

ACTUAL_FILES=$(tar -tzf "${ARCHIVE}" | wc -l | tr -d ' ')
[[ "${ACTUAL_FILES}" -eq "${EXPECTED_FILES}" ]] \
  || _fail "Dosya sayısı uyuşmuyor: beklenen ${EXPECTED_FILES}, arşivde ${ACTUAL_FILES}"
_ok "Dosya sayısı: ${ACTUAL_FILES}"

# Arşiv prefix otomatik belirleme — strip-components sabit değil
if tar -tzf "${ARCHIVE}" | grep -q '^myk-platform-v2/'; then
  ARCHIVE_PREFIX="myk-platform-v2/"
  STRIP_COMPONENTS=1
else
  ARCHIVE_PREFIX=""
  STRIP_COMPONENTS=0
fi
_ok "Arşiv prefix: ${ARCHIVE_PREFIX:-<yok>}  strip-components=${STRIP_COMPONENTS}"

# ── Adım 2: SUNUCU — Arşivi aktar ────────────────────────────────────────────
_header "2. Arşivi sunucuya aktar"

ssh "${SERVER}" "mkdir -p ${REMOTE_TMP}"
scp "${ARCHIVE}" "${SERVER}:${REMOTE_TMP}/myk-sprint-3.2-delta.tar.gz"
_ok "Aktarım tamamlandı"

# ── Adım 3: SUNUCU — Arşiv doğrulama ─────────────────────────────────────────
_header "3. Sunucuda arşiv doğrulama"

ssh "${SERVER}" bash <<REMOTE_CHECK
set -Eeuo pipefail
ARCHIVE="${REMOTE_TMP}/myk-sprint-3.2-delta.tar.gz"

ACTUAL=\$(sha256sum "\${ARCHIVE}" | cut -d' ' -f1)
[[ "\${ACTUAL}" == "${EXPECTED_SHA}" ]] \
  || { echo "HATA: SHA-256 uyuşmuyor: \${ACTUAL}"; exit 1; }
echo "  ✓ SHA-256 doğrulandı"

COUNT=\$(tar -tzf "\${ARCHIVE}" | wc -l | tr -d ' ')
echo "  ✓ Arşivdeki dosya sayısı: \${COUNT}"
[[ "\${COUNT}" -eq ${EXPECTED_FILES} ]] \
  || { echo "HATA: Arşiv dosya sayısı \${COUNT}; ${EXPECTED_FILES} bekleniyordu"; exit 1; }

echo ""
echo "  Arşiv içeriği:"
tar -tzf "\${ARCHIVE}" | sort | sed 's/^/    /'
REMOTE_CHECK

# ── Adım 4: SUNUCU — Hedef dosya yedeği ──────────────────────────────────────
_header "4. Mevcut dosyaların yedeği"

ssh "${SERVER}" bash <<REMOTE_BACKUP
set -Eeuo pipefail
BACKUP="${BACKUP_DIR}"
SRC="${REMOTE_DIR}"
mkdir -p "\${BACKUP}"

normalize_path() {
  local rel="\$1"
  printf '%s\n' "\${rel#myk-platform-v2/}"
}

tar -tzf "${REMOTE_TMP}/myk-sprint-3.2-delta.tar.gz" | \
  while read -r entry; do
    rel="\$(normalize_path "\${entry}")"
    [[ -z "\${rel}" || "\${rel}" == */ ]] && continue
    abs="\${SRC}/\${rel}"
    if [[ -f "\${abs}" ]]; then
      dest="\${BACKUP}/\$(dirname "\${rel}")"
      mkdir -p "\${dest}"
      cp "\${abs}" "\${dest}/"
    fi
  done

COUNT=\$(find "\${BACKUP}" -type f | wc -l)
echo "  ✓ \${COUNT} mevcut dosya yedeklendi → \${BACKUP}"
REMOTE_BACKUP

# ── Adım 5: SUNUCU — Dry-run ─────────────────────────────────────────────────
_header "5. Dry-run karşılaştırması"

ssh "${SERVER}" bash <<REMOTE_DRYRUN
set -Eeuo pipefail

normalize_path() {
  local rel="\$1"
  printf '%s\n' "\${rel#myk-platform-v2/}"
}

echo "  Değişecek dosyalar:"
tar -tzf "${REMOTE_TMP}/myk-sprint-3.2-delta.tar.gz" | \
  while read -r entry; do
    rel="\$(normalize_path "\${entry}")"
    [[ -z "\${rel}" || "\${rel}" == */ ]] && continue
    abs="${REMOTE_DIR}/\${rel}"
    if [[ -f "\${abs}" ]]; then
      echo "    ~ GÜNCELLENIYOR: \${rel}"
    else
      echo "    + YENİ EKLENECEK: \${rel}"
    fi
  done
REMOTE_DRYRUN

echo ""
read -rp "Dry-run çıktısını gördünüz. Devam etmek istiyor musunuz? [y/N] " CONFIRM
[[ "${CONFIRM}" =~ ^[Yy]$ ]] || { echo "İptal edildi."; exit 0; }

# ── Adım 6: SUNUCU — Dosyaları uygula ────────────────────────────────────────
_header "6. Dosyaları uygula"

ssh "${SERVER}" bash <<REMOTE_APPLY
set -Eeuo pipefail
cd "${REMOTE_DIR}"

if tar -tzf "${REMOTE_TMP}/myk-sprint-3.2-delta.tar.gz" | grep -q '^myk-platform-v2/'; then
  tar -xzf "${REMOTE_TMP}/myk-sprint-3.2-delta.tar.gz" \
    -C "${REMOTE_DIR}" \
    --strip-components=1 \
    --overwrite
else
  tar -xzf "${REMOTE_TMP}/myk-sprint-3.2-delta.tar.gz" \
    -C "${REMOTE_DIR}" \
    --overwrite
fi

echo "  ✓ Dosyalar uygulandı"

# Adım 6 sonrası doğrulama — Compose dosyasının MinIO + pdf-service içerdiğini garantile
cd "${REMOTE_DIR}"
export COMPOSE_FILE="docker-compose.yml:docker-compose.staging.yml"

echo ""
echo "  docker compose config --services:"
docker compose config --services 2>&1 | sed 's/^/    /'

REQUIRED_SERVICES="db redis minio pdf-service api frontend nginx"
for svc in \${REQUIRED_SERVICES}; do
  docker compose config --services 2>/dev/null | grep -qx "\${svc}" \
    || { echo "  ✗ HATA: Compose config'de '\${svc}' bulunamadı"; exit 1; }
done
echo "  ✓ Tüm servisler Compose config'de doğrulandı"

echo ""
echo "  docker-compose.yml'de minio ve pdf-service tanımları:"
grep -nE '^  (minio|pdf-service):' "${REMOTE_DIR}/docker-compose.yml" | sed 's/^/    /'
REMOTE_APPLY

# ── Adım 7: SUNUCU — Image build ─────────────────────────────────────────────
_header "7. Docker image build"

ssh "${SERVER}" bash <<REMOTE_BUILD
set -Eeuo pipefail
cd "${REMOTE_DIR}"
export COMPOSE_FILE="docker-compose.yml:docker-compose.staging.yml"

BUILD_LOG="/opt/myk/backups/sprint32_build_\$(date +%Y%m%d_%H%M%S).log"

echo "  Build log: \${BUILD_LOG}"
docker compose build api frontend pdf-service \
  2>&1 | tee "\${BUILD_LOG}"

echo "  ✓ Tüm image'lar build edildi"
REMOTE_BUILD

# ── Adım 8: SUNUCU — PostgreSQL yedeği (migration'dan ÖNCE) ──────────────────
_header "8. PostgreSQL yedeği"

ssh "${SERVER}" bash <<'REMOTE_PGBACKUP'
set -Eeuo pipefail
BACKUP_FILE="/opt/myk/backups/pg_sprint32_$(date +%Y%m%d_%H%M%S).sql.gz"
mkdir -p /opt/myk/backups

ENV_FILE="/opt/myk/staging/myk-platform-v2/.env"
[[ -f "${ENV_FILE}" ]] || { echo "HATA: .env bulunamadı"; exit 1; }

# .env'den değerleri grep ile çıkar — source YASAK
DB_NAME=$(grep '^POSTGRES_DB=' "${ENV_FILE}" | cut -d'=' -f2- | tr -d '"'"'"' ')
DB_USER=$(grep '^POSTGRES_USER=' "${ENV_FILE}" | cut -d'=' -f2- | tr -d '"'"'"' ')
DB_NAME=${DB_NAME:-myk_platform}
DB_USER=${DB_USER:-myk_user}

docker compose \
  -f /opt/myk/staging/myk-platform-v2/docker-compose.yml \
  exec -T db pg_dump -U "${DB_USER}" "${DB_NAME}" \
  | gzip > "${BACKUP_FILE}"

# Yedek bütünlük kontrolü
test -s "${BACKUP_FILE}" \
  || { echo "HATA: PostgreSQL yedek dosyası boş"; exit 1; }
gzip -t "${BACKUP_FILE}" \
  || { echo "HATA: gzip bütünlüğü doğrulanamadı"; exit 1; }

SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo "  ✓ PostgreSQL yedeği: ${BACKUP_FILE} (${SIZE})"
REMOTE_PGBACKUP

# ── Adım 9: SUNUCU — Migration 0003 → 0004 ────────────────────────────────────
_header "9. Alembic migration (→ 0004 head)"

# Yöntem: --entrypoint /bin/sh ile container shell'i başlatılır.
# Docker Compose .env'deki POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB değerlerini
# container environment'ına aktarır; shell bu değişkenleri container içinde genişletir.
# Parola terminale veya host ps aux'a düşmez.
ssh "${SERVER}" bash <<'REMOTE_MIGRATE'
set -Eeuo pipefail

cd /opt/myk/staging/myk-platform-v2
export COMPOSE_FILE="docker-compose.yml:docker-compose.staging.yml"

# Migration kullanıcısının public şemasında CREATE yetkisi var mı?
echo "  Migration kullanıcısı doğrulanıyor..."
docker compose run --rm -T \
  --entrypoint /bin/sh \
  api -c '
    export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
    python - <<PY
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.connect() as conn:
            row = (await conn.execute(text(
                "SELECT current_user, current_database(), "
                "has_schema_privilege(current_user, '\''public'\'', '\''CREATE'\'')"
            ))).one()
            user, db, can_create = row
            print(f"  current_user={user}")
            print(f"  current_database={db}")
            print(f"  public_schema_create={can_create}")
            if not can_create:
                raise SystemExit(
                    "HATA: Migration kullanıcisinin public semasinda CREATE yetkisi yok."
                )
    finally:
        await engine.dispose()

asyncio.run(main())
PY
  '

echo "  alembic upgrade head çalıştırılıyor..."
docker compose run --rm -T \
  --entrypoint /bin/sh \
  api -c '
    export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
    exec alembic -c migrations/alembic.ini upgrade head
  '

echo "  Migration revision doğrulanıyor..."
CURRENT="$(
  docker compose run --rm -T \
    --entrypoint /bin/sh \
    api -c '
      export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
      exec alembic -c migrations/alembic.ini current
    ' 2>&1
)"
echo "${CURRENT}" | sed 's/^/  /'

if echo "${CURRENT}" | grep -Eq '0004[[:space:]]+(.*\(head\)|head)'; then
  echo "  ✓ Migration doğrulandı: 0004 (head)"
else
  echo "  ✗ HATA: Alembic revision 0004 (head) değil"
  exit 1
fi
REMOTE_MIGRATE

# ── Adım 10: SUNUCU — Container başlat + healthcheck polling ─────────────────
_header "10. Container başlat + healthcheck"

ssh "${SERVER}" bash <<'REMOTE_START'
set -Eeuo pipefail
cd /opt/myk/staging/myk-platform-v2
export COMPOSE_FILE="docker-compose.yml:docker-compose.staging.yml"

docker compose up -d --no-build

echo "  Servislerin hazır olması bekleniyor (max 120s)..."
deadline=$((SECONDS + 120))

api_ok=0; minio_ok=0; pdf_ok=0

while (( SECONDS < deadline )); do
  # API health
  if curl -fsS http://127.0.0.1:18080/api/v1/health >/dev/null 2>&1; then
    api_ok=1
  fi

  # MinIO health — API container üzerinden (minio image'da curl olmayabilir)
  if docker compose exec -T api python - >/dev/null 2>&1 <<'PY'
import urllib.request
r = urllib.request.urlopen("http://minio:9000/minio/health/live", timeout=5)
raise SystemExit(0 if r.status == 200 else 1)
PY
  then
    minio_ok=1
  fi

  # pdf-service health — API container üzerinden (dahili ağ)
  if docker compose exec -T api python - >/dev/null 2>&1 <<'PY'
import urllib.request
r = urllib.request.urlopen("http://pdf-service:8001/health", timeout=5)
raise SystemExit(0 if r.status == 200 else 1)
PY
  then
    pdf_ok=1
  fi

  (( api_ok && minio_ok && pdf_ok )) && break
  sleep 5
done

echo ""
docker compose ps

echo ""
(( api_ok ))   || { echo "  ✗ API health başarısız";        exit 1; }
(( minio_ok )) || { echo "  ✗ MinIO health başarısız";      exit 1; }
(( pdf_ok ))   || { echo "  ✗ pdf-service health başarısız"; exit 1; }

echo "  ✓ API hazır"
echo "  ✓ MinIO hazır"
echo "  ✓ pdf-service hazır"
REMOTE_START

# ── Adım 11: Entegrasyon testi ────────────────────────────────────────────────
_header "11. run_sprint32_verify.sh"
_warn "JWT token'lar gerekiyor. Sunucuda manuel çalıştırın:"
echo ""
echo "  cd /opt/myk/staging/myk-platform-v2"
echo "  bash scripts/run_sprint32_verify.sh"
echo ""

# ── Adım 12: Özet ─────────────────────────────────────────────────────────────
_header "Deployment tamamlandı"
echo "  Arşiv:  myk-sprint-3.2-delta.tar.gz"
echo "  SHA:    ${EXPECTED_SHA}"
echo "  Yedek:  ${BACKUP_DIR}"
echo ""
echo "  Tüm kontroller geçerse:"
echo "  git tag v0.4.0-beta1"

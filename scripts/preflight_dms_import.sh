#!/usr/bin/env bash
# =============================================================================
# DMS Production Import Preflight — READ-ONLY
# Sprint 14C Adım 2 — Production güvenlik kontrolleri
#
# Kullanım (Mac'ten, repo root'undan):
#   bash scripts/preflight_dms_import.sh
#
# Bu script YALNIZCA okuma yapar. DB'ye veya MinIO'ya hiçbir şey yazmaz.
# =============================================================================
set -euo pipefail

SERVER="myk-server"
REMOTE_DIR="/opt/myk/production/myk-platform-v2"
PROJECT="myk-production"

echo "============================================================"
echo "DMS Production Import Preflight — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"
echo ""

# ── 1. SSH bağlantı kontrolü ─────────────────────────────────────────────────
echo "── 1. SSH bağlantısı"
ssh -q -o BatchMode=yes -o ConnectTimeout=8 "${SERVER}" exit \
  && echo "   ✅ SSH OK" \
  || { echo "   ❌ SSH bağlantısı başarısız"; exit 1; }
echo ""

# ── 2. Container durumu ───────────────────────────────────────────────────────
echo "── 2. Container durumu"
ssh "${SERVER}" bash -s <<'REMOTE'
cd /opt/myk/production/myk-platform-v2
docker compose -p myk-production ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null \
  || docker-compose -p myk-production ps 2>/dev/null \
  || echo "WARN: docker compose komutuna ulaşılamadı"
REMOTE
echo ""

# ── 3. PostgreSQL: DMS tablo sayımları ──────────────────────────────────────
echo "── 3. PostgreSQL — DMS tablo sayımları (beklenen: hepsi 0)"
ssh "${SERVER}" bash -s <<'REMOTE'
cd /opt/myk/production/myk-platform-v2
docker compose -p myk-production exec -T db \
  psql -U myk_user_prod -d myk_platform_prod -c "
    SELECT
      'doc_documents'   AS tablo, COUNT(*) AS satir FROM doc_documents UNION ALL
    SELECT
      'doc_revisions',                COUNT(*)      FROM doc_revisions  UNION ALL
    SELECT
      'doc_revision_files',           COUNT(*)      FROM doc_revision_files UNION ALL
    SELECT
      'doc_categories',               COUNT(*)      FROM doc_categories
    ORDER BY tablo;
  " 2>&1
REMOTE
echo ""

# ── 4. Mevcut kulüp (tenant) tespiti ────────────────────────────────────────
echo "── 4. Clubs tablosu — hedef tenant"
ssh "${SERVER}" bash -s <<'REMOTE'
cd /opt/myk/production/myk-platform-v2
docker compose -p myk-production exec -T db \
  psql -U myk_user_prod -d myk_platform_prod -c "
    SELECT id, name, slug, is_active FROM clubs ORDER BY created_at LIMIT 5;
  " 2>&1
REMOTE
echo ""

# ── 5. READY_R01 kod çakışma kontrolü ─────────────────────────────────────
echo "── 5. Kod çakışma kontrolü — READY_R01 belgeler (beklenen: 0 satır)"
ssh "${SERVER}" bash -s <<'REMOTE'
cd /opt/myk/production/myk-platform-v2
docker compose -p myk-production exec -T db \
  psql -U myk_user_prod -d myk_platform_prod -c "
    SELECT code, title, content_status
    FROM doc_documents
    WHERE is_deleted = false
      AND code IN (
        'MYK-EGT-001','MYK-EGT-002','MYK-EGT-003','MYK-EGT-004',
        'MYK-EGT-005','MYK-EGT-006','MYK-EGT-007','MYK-EGT-008',
        'MYK-EGT-009','MYK-EGT-010','MYK-EGT-011','MYK-EGT-012',
        'MYK-RIS-001','MYK-OPS-001','MYK-OPS-002','MYK-OPS-003',
        'MYK-OPS-004','MYK-OPS-005','MYK-OPS-006','MYK-OPS-007',
        'MYK-OPS-008','MYK-OPS-009','MYK-OPS-010','MYK-OPS-011',
        'MYK-OPS-012','MYK-OPS-013','MYK-INS-001','MYK-INS-002',
        'MYK-INS-003','MYK-INS-004','MYK-YNT-001','MYK-YNT-002',
        'MYK-YNT-003','MYK-YNT-004','MYK-YNT-005','MYK-YNT-006',
        'MYK-ARC-001','MYK-FIN-001','MYK-FIN-002','MYK-FIN-003'
      )
    ORDER BY code;
  " 2>&1
REMOTE
echo ""

# ── 6. MinIO: myk-documents bucket durumu ────────────────────────────────────
echo "── 6. MinIO — myk-documents bucket"
ssh "${SERVER}" bash -s <<'REMOTE'
cd /opt/myk/production/myk-platform-v2
# mc (MinIO Client) mevcutsa kullan
if docker compose -p myk-production exec -T minio mc alias set local http://localhost:9000 \
    "$(grep STORAGE_ACCESS_KEY /etc/myk/production.env | cut -d= -f2-)" \
    "$(grep STORAGE_SECRET_KEY /etc/myk/production.env | cut -d= -f2-)" \
    >/dev/null 2>&1; then
  echo "mc alias kuruldu"
  docker compose -p myk-production exec -T minio mc ls local/myk-documents 2>&1 | head -5 \
    || echo "Bucket boş veya mevcut değil"
  docker compose -p myk-production exec -T minio mc stat local/myk-documents 2>&1 | grep -E "Name|Type|Status" \
    || echo "mc stat: bucket erişim hatası"
else
  echo "mc alias kurulamadı — bucket varlığını API ile kontrol et:"
  docker compose -p myk-production exec -T minio mc ls local/ 2>&1 | head -20 || echo "mc ls failed"
fi
REMOTE
echo ""

# ── 7. Disk kaynak dosyaları erişilebilirlik ─────────────────────────────────
echo "── 7. Prosedürler/ kaynak dizini kontrolü"
ssh "${SERVER}" bash -s <<'REMOTE'
PROSEDURLER_CANDIDATES=(
  "/opt/myk/production/Prosedürler"
  "/opt/myk/production/myk-platform-v2/Prosedürler"
  "/home/deploy/Prosedürler"
  "$HOME/Prosedürler"
)
FOUND=""
for d in "${PROSEDURLER_CANDIDATES[@]}"; do
  if [[ -d "$d" ]]; then
    FOUND="$d"
    break
  fi
done

if [[ -n "$FOUND" ]]; then
  echo "✅ Prosedürler/ bulundu: $FOUND"
  echo "   PDF sayısı  : $(find "$FOUND" -name '*.pdf' | wc -l)"
  echo "   DOCX sayısı : $(find "$FOUND" -name '*.docx' | wc -l)"
else
  echo "❌ Prosedürler/ dizini bulunamadı — aşağıdaki yollarda arandı:"
  for d in "${PROSEDURLER_CANDIDATES[@]}"; do echo "   $d"; done
  echo ""
  echo "   Mevcut /opt/myk/production içeriği:"
  ls /opt/myk/production/ 2>/dev/null || echo "   /opt/myk/production bulunamadı"
fi
REMOTE
echo ""

# ── 8. Backend imaj versiyonu ─────────────────────────────────────────────────
echo "── 8. Aktif backend versiyonu"
ssh "${SERVER}" bash -s <<'REMOTE'
cd /opt/myk/production/myk-platform-v2
docker compose -p myk-production exec -T api \
  python -c "
import subprocess, sys
result = subprocess.run(['git', 'describe', '--tags', '--always'], capture_output=True, text=True)
print('Git tag:', result.stdout.strip())
" 2>&1 || echo "Version bilgisi alınamadı"
REMOTE
echo ""

echo "============================================================"
echo "Preflight tamamlandı. Bu çıktıyı Claude ile paylaşın."
echo "============================================================"

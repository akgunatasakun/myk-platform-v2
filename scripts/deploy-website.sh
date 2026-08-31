#!/usr/bin/env bash
# deploy-website.sh — Public siteyi production sunucusuna deploy eder
# Kullanım: ./scripts/deploy-website.sh [ssh-alias]
# Örnek:    ./scripts/deploy-website.sh myk-server

set -euo pipefail

REMOTE="${1:-myk-server}"
REMOTE_PATH="/var/www/mersinyelken"
LOCAL_PATH="$(cd "$(dirname "$0")/.." && pwd)/website"

echo "🚀 Mersin Yelken public site deploy başlıyor..."
echo "   Kaynak : $LOCAL_PATH"
echo "   Hedef  : $REMOTE:$REMOTE_PATH"

# Backup al
ssh "$REMOTE" "cp -f $REMOTE_PATH/index.html $REMOTE_PATH/index.html.backup-\$(date +%Y%m%d) 2>/dev/null || true"

# Dosyaları kopyala (backup ve DS_Store hariç)
rsync -avz --delete \
  --exclude='*.backup-*' \
  --exclude='.DS_Store' \
  --exclude='.gitignore' \
  "$LOCAL_PATH/" \
  "$REMOTE:$REMOTE_PATH/"

# Smoke test — HTTP 200 bekleniyor
echo ""
echo "🔍 Smoke test..."
STATUS=$(ssh "$REMOTE" "curl -sk -o /dev/null -w '%{http_code}' http://127.0.0.1/")
if [ "$STATUS" = "200" ]; then
  echo "✅ Deploy başarılı — HTTP $STATUS"
else
  echo "⚠️  Uyarı: HTTP $STATUS döndü, manuel kontrol et"
fi

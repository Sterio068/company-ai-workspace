#!/usr/bin/env bash
# ============================================================
# v1.7 · AI Suggestions 每 30 分鐘掃描(每位 admin user)
# ============================================================
# 由 launchd 排程觸發 · 跑 POST /admin/ai-suggestions/scan
# 用 ECC_INTERNAL_TOKEN 認證
# ============================================================

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

LOG_PREFIX="[ai-scan $(date +%H:%M)]"
echo "$LOG_PREFIX start"

# 從 Keychain 讀 internal token(start.sh 已注入 docker · 此處從 Keychain 直讀)
TOKEN=$(security find-generic-password -s 'chengfu-ai-internal-token' -w 2>/dev/null || echo "")
if [ -z "$TOKEN" ]; then
    echo "$LOG_PREFIX skip · 無 ECC_INTERNAL_TOKEN(install 後重跑 setup-keychain)"
    exit 0
fi

BASE="${BASE_URL:-http://localhost}"

# 從 Mongo 拿所有 admin email
ADMINS=$(docker exec chengfu-mongo mongosh chengfu --quiet --eval \
  'db.users.find({role:"ADMIN"}).map(u=>u.email).join(" ")' 2>/dev/null || echo "")

if [ -z "$ADMINS" ]; then
    echo "$LOG_PREFIX no admin · skip"
    exit 0
fi

count=0
for admin in $ADMINS; do
    code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$BASE/api-accounting/admin/ai-suggestions/scan" \
        -H "X-Internal-Token: $TOKEN" \
        -H "X-User-Email: $admin" || echo "000")
    if [ "$code" = "200" ]; then
        echo "$LOG_PREFIX scanned $admin"
        count=$((count + 1))
    else
        echo "$LOG_PREFIX fail $admin · HTTP $code"
    fi
done

echo "$LOG_PREFIX done · $count admin scanned"

# Cron audit log
mkdir -p "$(dirname "$0")/../reports/cron-audit"
echo "{\"script\":\"ai-suggestions-scan\",\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"scanned\":$count}" \
    >> "$(dirname "$0")/../reports/cron-audit/ai-suggestions-scan.jsonl"

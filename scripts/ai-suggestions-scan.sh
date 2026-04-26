#!/usr/bin/env bash
# ============================================================
# v1.8 · AI Suggestions 每 30 分鐘掃描(改 /scan-all)
# ============================================================
# 由 launchd 排程觸發 · 一次掃所有 admin · 比 v1.7 (per-admin) 快 N 倍
# 用 ECC_INTERNAL_TOKEN 認證 · backend 自己列 admin 並逐一 scan
# ============================================================

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

LOG_PREFIX="[ai-scan $(date +%H:%M)]"
echo "$LOG_PREFIX start"

# 從 Keychain 讀 internal token(start.sh 已注入 docker · 此處從 Keychain 直讀)
TOKEN=$(security find-generic-password -s 'chengfu-ai-internal-token' -w 2>/dev/null || echo "")
if [ -z "$TOKEN" ]; then
    # v1.8 · Keychain miss 時 · 寫到 cron audit + email admin(若有 sendmail)
    echo "$LOG_PREFIX CRITICAL · Keychain 沒 internal token · 跳過(請 setup-keychain.sh)"
    mkdir -p "$(dirname "$0")/../reports/cron-audit"
    echo "{\"script\":\"ai-suggestions-scan\",\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"error\":\"keychain_missing\"}" \
        >> "$(dirname "$0")/../reports/cron-audit/ai-suggestions-scan.jsonl"
    exit 1
fi

BASE="${BASE_URL:-http://localhost}"

# v1.8 · 一次打 /scan-all · backend 自己列 admin
RESULT=$(curl -s -w "\nHTTP %{http_code}" \
    -X POST "$BASE/api-accounting/admin/ai-suggestions/scan-all" \
    -H "X-Internal-Token: $TOKEN" \
    -H "Content-Type: application/json" || echo "curl_fail")

HTTP_CODE=$(echo "$RESULT" | tail -1 | awk '{print $2}')
BODY=$(echo "$RESULT" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    COUNT=$(echo "$BODY" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('scanned_admins',0))" 2>/dev/null || echo "0")
    echo "$LOG_PREFIX done · $COUNT admin scanned"
else
    echo "$LOG_PREFIX fail · HTTP $HTTP_CODE · $BODY"
    COUNT=0
fi

# Cron audit log
mkdir -p "$(dirname "$0")/../reports/cron-audit"
echo "{\"script\":\"ai-suggestions-scan\",\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"scanned\":$COUNT,\"http\":$HTTP_CODE}" \
    >> "$(dirname "$0")/../reports/cron-audit/ai-suggestions-scan.jsonl"

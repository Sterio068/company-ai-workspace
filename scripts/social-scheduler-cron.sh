#!/bin/bash
# ============================================================
# 承富 AI · 社群排程 cron(Feature #5)
# ============================================================
# 每 5 分鐘呼叫 /admin/social/run-queue · 掃 schedule_at <= now 的 queued/failed 發布
# launchd plist 在 config-templates/launchd/com.chengfu.social-scheduler.plist
#
# 安裝:./scripts/install-launchd.sh(會把所有 cron plist 安裝)
# ============================================================

set -euo pipefail

ACC_URL="${ACCOUNTING_URL:-http://localhost/api-accounting}"
TOKEN="${ECC_INTERNAL_TOKEN:-}"

if [[ -z "$TOKEN" ]]; then
    # 從 Keychain 讀
    TOKEN=$(security find-generic-password -s "chengfu-ai-internal-token" -w 2>/dev/null || echo "")
fi

if [[ -z "$TOKEN" ]]; then
    echo "[$(date)] ❌ ECC_INTERNAL_TOKEN 未設" >&2
    exit 1
fi

# 呼叫 run-queue · 限 50 筆每次
RESPONSE=$(curl -s -X POST \
    -H "X-Internal-Token: $TOKEN" \
    "$ACC_URL/admin/social/run-queue?limit=50")

echo "[$(date)] $RESPONSE"

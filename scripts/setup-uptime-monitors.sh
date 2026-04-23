#!/usr/bin/env bash
# 技術債#13(2026-04-23)· Uptime Kuma 預設 monitor 一鍵設
#
# 承富 v1.2 已 launch chengfu-uptime container · 但 monitor rule 要手動加
# 此 script 用 Uptime Kuma API 一鍵建好 6 個 monitor:
#   1. nginx /healthz · 30s · LibreChat 入口
#   2. accounting /healthz · 60s · FastAPI 業務後端
#   3. mongo · 60s · DB 健康
#   4. meili /health · 120s · 知識庫
#   5. uptime kuma 自身 · 300s · 看門狗的看門狗
#   6. accounting /quota/check?email=admin · 300s · 業務面驗證
#
# 用法:
#   1. 先進 http://localhost:3001 註冊 admin 帳號
#   2. 在 Settings → API Keys 建一把 key(複製)
#   3. UPTIME_KUMA_KEY=xxx ./scripts/setup-uptime-monitors.sh

set -euo pipefail

KUMA_URL="${UPTIME_KUMA_URL:-http://localhost:3001}"
KEY="${UPTIME_KUMA_KEY:-}"

if [[ -z "$KEY" ]]; then
    echo "❌ 缺 UPTIME_KUMA_KEY · 先到 http://localhost:3001/settings/api-keys 建一把"
    echo "   UPTIME_KUMA_KEY=xxx ./scripts/setup-uptime-monitors.sh"
    exit 1
fi

if ! command -v jq > /dev/null; then
    echo "❌ 缺 jq · brew install jq"
    exit 1
fi

# 註冊一個 monitor(name, type, url, interval_seconds)
add_monitor() {
    local name="$1" type="$2" url="$3" interval="$4"
    local payload
    payload=$(jq -n \
        --arg n "$name" --arg t "$type" --arg u "$url" --argjson i "$interval" \
        '{name:$n, type:$t, url:$u, interval:$i, retryInterval:60, maxretries:3, accepted_statuscodes:["200-299"]}')
    local resp
    resp=$(curl -s -X POST "$KUMA_URL/api/monitor" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $KEY" \
        -d "$payload")
    if echo "$resp" | grep -qE '"ok":\s*true|"id":'; then
        echo "  ✅ $name"
    else
        echo "  ⚠ $name · resp=$resp"
    fi
}

echo "============================================"
echo "  承富 AI · Uptime Kuma 預設 monitor 一鍵設"
echo "============================================"
echo "目標 KUMA: $KUMA_URL"
echo ""
echo "[註] 若 monitor 已存在 · API 會回 409 · 是預期"
echo ""

add_monitor "nginx /healthz"             "http"     "http://nginx/healthz"           30
add_monitor "accounting /healthz"        "http"     "http://accounting:8000/healthz" 60
add_monitor "mongodb (chengfu_ai)"       "port"     "mongodb:27017"                  60
add_monitor "meili /health"              "http"     "http://meilisearch:7700/health" 120
add_monitor "uptime-kuma 自身"           "http"     "$KUMA_URL"                       300
add_monitor "accounting quota gate"      "http"     "http://accounting:8000/quota/preflight" 300

echo ""
echo "============================================"
echo "  ✅ 完成 · 進 $KUMA_URL 看 Dashboard"
echo "============================================"
echo ""
echo "提醒:"
echo "  - 加通知頻道(Settings → Notifications)綁 admin webhook"
echo "  - 預設 monitor 失敗 3 次才 alert · 防 transient flap"

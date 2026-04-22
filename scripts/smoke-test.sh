#!/bin/bash
# ========================================
# 承富 AI 系統 · Smoke Test
# ========================================
# 部署後快速驗收:7 項核心功能
#
# 用法:
#   ./scripts/smoke-test.sh [base_url]
#
# 預設 base_url = http://localhost:3080

set -uo pipefail

BASE_URL="${1:-http://localhost}"
PASS=0
FAIL=0

check() {
    local desc="$1" cmd="$2"
    echo -n "  [$(($PASS + $FAIL + 1))] $desc ... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo "✅ PASS"
        PASS=$((PASS + 1))
    else
        echo "❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================"
echo "  承富 AI 系統 · Smoke Test"
echo "  Target: $BASE_URL"
echo "============================================"

# ------------------ 基礎檢查 ------------------
echo ""
echo "[容器狀態]"
check "nginx 容器運行中"        "docker ps --filter name=chengfu-nginx --filter status=running -q | grep -q ."
check "LibreChat 容器運行中" "docker ps --filter name=chengfu-librechat --filter status=running -q | grep -q ."
check "MongoDB 容器運行中"   "docker ps --filter name=chengfu-mongo --filter status=running -q | grep -q ."
check "Meilisearch 容器運行中" "docker ps --filter name=chengfu-meili --filter status=running -q | grep -q ."

echo ""
echo "[網路連線]"
check "nginx /healthz"           "curl -sf ${BASE_URL}/healthz"
check "承富 Launcher /"          "[[ \$(curl -sf ${BASE_URL}/) == *承富* ]]"
check "LibreChat API /api/config" "curl -sf ${BASE_URL}/api/config"
check "LibreChat /chat"          "curl -sf ${BASE_URL}/chat -o /dev/null -w '%{http_code}' | grep -qE '200|301|302'"

echo ""
echo "[資源佔用]"
LIBRE_MEM=$(docker stats --no-stream --format "{{.MemUsage}}" chengfu-librechat 2>/dev/null | awk '{print $1}')
echo "  LibreChat 記憶體:$LIBRE_MEM"
MONGO_MEM=$(docker stats --no-stream --format "{{.MemUsage}}" chengfu-mongo 2>/dev/null | awk '{print $1}')
echo "  MongoDB 記憶體:$MONGO_MEM"

# ------------------ 功能驗證(若已設 admin)------------------
if [[ -n "${LIBRECHAT_ADMIN_EMAIL:-}" && -n "${LIBRECHAT_ADMIN_PASSWORD:-}" ]]; then
    echo ""
    echo "[API 功能 · 已提供 admin 憑證]"
    LOGIN_RES=$(curl -sf -X POST "${BASE_URL}/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${LIBRECHAT_ADMIN_EMAIL}\",\"password\":\"${LIBRECHAT_ADMIN_PASSWORD}\"}" 2>/dev/null || echo "")
    if [[ -n "$LOGIN_RES" && "$LOGIN_RES" == *"token"* ]]; then
        echo "  [$(($PASS + $FAIL + 1))] Admin 登入 ... ✅ PASS"
        PASS=$((PASS + 1))
    else
        echo "  [$(($PASS + $FAIL + 1))] Admin 登入 ... ❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
else
    echo ""
    echo "[API 功能]"
    echo "  ⚠ 略過(需設 LIBRECHAT_ADMIN_EMAIL / LIBRECHAT_ADMIN_PASSWORD 環境變數)"
fi

# ------------------ 備份檢查 ------------------
echo ""
echo "[備份]"
LATEST_BACKUP=$(find "${HOME}/chengfu-backups/daily" -type f -name "chengfu-*" 2>/dev/null | sort | tail -1)
if [[ -n "$LATEST_BACKUP" ]]; then
    AGE_HOURS=$(( ($(date +%s) - $(stat -f %m "$LATEST_BACKUP" 2>/dev/null || stat -c %Y "$LATEST_BACKUP")) / 3600 ))
    if [[ $AGE_HOURS -lt 48 ]]; then
        echo "  ✅ 最新備份 $AGE_HOURS 小時前:$(basename "$LATEST_BACKUP")"
        PASS=$((PASS + 1))
    else
        echo "  ⚠ 最新備份 $AGE_HOURS 小時前,超過 48h(cron 可能沒跑)"
        FAIL=$((FAIL + 1))
    fi
else
    echo "  ⚠ 找不到備份檔(首次部署可忽略;否則執行 ./scripts/backup.sh)"
fi

# ------------------ 結論 ------------------
echo ""
echo "============================================"
echo "  結果:$PASS 通過 / $FAIL 失敗"
echo "============================================"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi

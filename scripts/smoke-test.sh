#!/bin/bash
# ========================================
# 承富 AI 系統 · Smoke Test
# ========================================
# 部署後快速驗收:7 項核心功能
#
# 用法:
#   ./scripts/smoke-test.sh [base_url]
#
# 預設 base_url = http://localhost

set -uo pipefail

BASE_URL="${1:-http://localhost}"
PASS=0
FAIL=0
BROWSER_UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

if [[ -z "${LIBRECHAT_ADMIN_EMAIL:-}" && "$(uname -s)" == "Darwin" ]]; then
    LIBRECHAT_ADMIN_EMAIL="$(security find-generic-password -s chengfu-ai-admin-install-email -w 2>/dev/null || true)"
fi
if [[ -z "${LIBRECHAT_ADMIN_PASSWORD:-}" && "$(uname -s)" == "Darwin" ]]; then
    LIBRECHAT_ADMIN_PASSWORD="$(security find-generic-password -s chengfu-ai-admin-install-password -w 2>/dev/null || true)"
fi

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

check_launcher_shell() {
    local tmp
    tmp="$(mktemp)"
    curl -sf "${BASE_URL}/" -o "$tmp" &&
        grep -Eq 'id="app"|data-brand-app-name|跳至主內容' "$tmp"
    local result=$?
    rm -f "$tmp"
    return "$result"
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
check "Accounting 容器運行中" "docker ps --filter name=chengfu-accounting --filter status=running -q | grep -q ."
check "Uptime Kuma 容器運行中" "docker ps --filter name=chengfu-uptime --filter status=running -q | grep -q ."

echo ""
echo "[網路連線]"
check "nginx /healthz"           "curl -sf ${BASE_URL}/healthz"
check "Launcher / app shell"     "check_launcher_shell"
check "LibreChat API /api/config" "curl -sf ${BASE_URL}/api/config"
check "Accounting /api-accounting/healthz" "curl -sf ${BASE_URL}/api-accounting/healthz"
check "Route A /c/new redirects" "curl -sI ${BASE_URL}/c/new -o /dev/null -w '%{http_code}' | grep -q '^302$'"
check "偽造 X-User-Email 不可通過 admin API" "curl -s -o /dev/null -w '%{http_code}' -H 'X-User-Email: ${LIBRECHAT_ADMIN_EMAIL:-admin@chengfu.local}' '${BASE_URL}/api-accounting/admin/users' | grep -Eq '^(401|403)$'"
check "RAG adapter 不對外暴露" "curl -s -o /dev/null -w '%{http_code}' '${BASE_URL}/api-accounting/rag/health' | grep -Eq '^(403|404)$'"

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
    COOKIE_JAR="$(mktemp)"
    LOGIN_RES=$(curl -sf -X POST "${BASE_URL}/api/auth/login" \
        -c "$COOKIE_JAR" \
        -H "Content-Type: application/json" \
        -H "User-Agent: ${BROWSER_UA}" \
        -d "{\"email\":\"${LIBRECHAT_ADMIN_EMAIL}\",\"password\":\"${LIBRECHAT_ADMIN_PASSWORD}\"}" 2>/dev/null || echo "")
    TOKEN=$(printf '%s' "$LOGIN_RES" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("token",""))' 2>/dev/null || true)
    if [[ -n "$LOGIN_RES" && "$LOGIN_RES" == *"token"* ]]; then
        echo "  [$(($PASS + $FAIL + 1))] Admin 登入 ... ✅ PASS"
        PASS=$((PASS + 1))
    else
        echo "  [$(($PASS + $FAIL + 1))] Admin 登入 ... ❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
    if [[ -n "$TOKEN" ]]; then
        check "Authenticated /api/agents" "curl -sf '${BASE_URL}/api/agents' -b '$COOKIE_JAR' -H 'Authorization: Bearer $TOKEN' -H 'User-Agent: ${BROWSER_UA}' -H 'Accept: application/json' | python3 -c 'import sys,json;d=json.load(sys.stdin);a=d if isinstance(d,list) else d.get(\"data\",[]);assert len(a) >= 1'"
        check "Authenticated /api-accounting/projects" "curl -sf '${BASE_URL}/api-accounting/projects' -b '$COOKIE_JAR' -H 'Authorization: Bearer $TOKEN' -H 'User-Agent: ${BROWSER_UA}'"
    else
        echo "  [$(($PASS + $FAIL + 1))] Authenticated API ... ❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
    rm -f "$COOKIE_JAR"
else
    echo ""
    echo "[API 功能]"
    echo "  ❌ FAIL · 需設 LIBRECHAT_ADMIN_EMAIL / LIBRECHAT_ADMIN_PASSWORD 或 macOS Keychain E2E 憑證"
    FAIL=$((FAIL + 1))
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

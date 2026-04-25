#!/bin/bash
# ========================================
# 承富智慧助理 · 系統更新腳本
# ========================================
# 安全的 in-place 更新 · 流程:
#   1. 紀錄目前 commit(失敗可 rollback)
#   2. git fetch + 比較 · 沒新版直接結束
#   3. git pull
#   4. docker compose pull(拉新 image · LibreChat 等)
#   5. docker compose up -d --build(重啟 + 重 build accounting)
#   6. 等 30 秒 → health check 4 個容器
#   7. 失敗 → auto rollback
#   8. 成功 → 寫 reports/update-history.jsonl + 通知
#
# 用法:
#   ./scripts/update.sh                # 互動模式 · 確認後執行
#   ./scripts/update.sh --yes          # 跳過確認
#   ./scripts/update.sh --check-only   # 只看有沒有新版 · 不更新
#   ./scripts/update.sh --json         # 輸出 JSON(給 backend endpoint 用)

set -uo pipefail
# 注意:不用 -e · 我們要自己處理失敗 + rollback

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="config-templates/docker-compose.yml"
HISTORY_FILE="$PROJECT_DIR/reports/update-history.jsonl"
LOCK_FILE="/tmp/chengfu-update.lock"

YES=0
CHECK_ONLY=0
JSON=0
for arg in "$@"; do
    case "$arg" in
        --yes|-y)        YES=1 ;;
        --check-only|-c) CHECK_ONLY=1 ;;
        --json|-j)       JSON=1 ;;
        *) echo "未知參數:$arg"; exit 2 ;;
    esac
done

# ---------- helpers ----------
log() { [ "$JSON" -eq 0 ] && echo "$@" >&2; }
info() { log "ℹ $*"; }
ok()   { log "✅ $*"; }
warn() { log "⚠ $*"; }
err()  { log "❌ $*"; }

emit_json() {
    # emit_json status message [extra-fields...]
    local status="$1"; shift
    local message="$1"; shift
    if [ "$JSON" -eq 1 ]; then
        echo -n "{\"status\":\"$status\",\"message\":\"$message\""
        for kv in "$@"; do echo -n ",$kv"; done
        echo "}"
    fi
}

# ---------- single-instance lock ----------
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        err "另一個 update.sh 正在跑(PID $PID)· 拒絕並行"
        emit_json "locked" "另一個更新正在執行" "\"pid\":$PID"
        exit 3
    else
        warn "stale lock · 移除"
        rm -f "$LOCK_FILE"
    fi
fi
echo "$$" > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

mkdir -p "$(dirname "$HISTORY_FILE")"

# ---------- check current vs remote ----------
info "[1/7] 檢查當前 commit"
BEFORE=$(git rev-parse HEAD)
BEFORE_SHORT=$(git rev-parse --short HEAD)
BEFORE_DATE=$(git log -1 --format=%ci HEAD)
info "  目前:$BEFORE_SHORT($BEFORE_DATE)"

info "[2/7] 從 GitHub 拉最新狀態(不動本機)"
if ! git fetch origin main --quiet 2>&1; then
    err "git fetch 失敗 · 檢查網路"
    emit_json "fetch_failed" "無法連到 GitHub · 檢查網路"
    exit 1
fi

REMOTE=$(git rev-parse origin/main)
REMOTE_SHORT=$(git rev-parse --short origin/main)
REMOTE_DATE=$(git log -1 --format=%ci origin/main)

if [ "$BEFORE" = "$REMOTE" ]; then
    ok "已是最新版($BEFORE_SHORT)· 不需更新"
    emit_json "up_to_date" "已是最新版" "\"current\":\"$BEFORE_SHORT\""
    exit 0
fi

# 算有幾個 commit 落後
COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main)
info "  最新:$REMOTE_SHORT($REMOTE_DATE)"
info "  落後:$COMMITS_BEHIND 個 commit"

# 拿落後的 commit 標題(最多 10 個)
COMMITS_LIST=$(git log --pretty=format:"  - %s" HEAD..origin/main | head -10)

if [ "$CHECK_ONLY" -eq 1 ]; then
    ok "有新版可更新($COMMITS_BEHIND 個 commit)"
    if [ "$JSON" -eq 1 ]; then
        # JSON · escape commits
        COMMITS_JSON=$(git log --pretty=format:'%s' HEAD..origin/main | head -10 | python3 -c '
import sys, json
print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))
')
        emit_json "available" "有 $COMMITS_BEHIND 個新 commit" \
            "\"current\":\"$BEFORE_SHORT\"" \
            "\"latest\":\"$REMOTE_SHORT\"" \
            "\"commits_behind\":$COMMITS_BEHIND" \
            "\"commits\":$COMMITS_JSON"
    else
        echo ""
        echo "落後的更新:"
        echo "$COMMITS_LIST"
    fi
    exit 0
fi

# ---------- 確認 ----------
if [ "$YES" -eq 0 ] && [ "$JSON" -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "  即將更新承富智慧助理"
    echo "================================================"
    echo "  目前版本:$BEFORE_SHORT($BEFORE_DATE)"
    echo "  目標版本:$REMOTE_SHORT($REMOTE_DATE)"
    echo "  落後 commit:$COMMITS_BEHIND 個"
    echo ""
    echo "  落後內容(最多顯示 10):"
    echo "$COMMITS_LIST"
    echo ""
    echo "  ⏱ 預計需時:1-3 分鐘(rebuild + restart)"
    echo "  📡 期間 Web UI 暫時無法使用"
    echo ""
    read -rp "確認執行?(y/n)" CONFIRM
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        info "已取消"
        emit_json "cancelled" "使用者取消"
        exit 0
    fi
fi

# ---------- 更新 ----------
info "[3/7] git pull origin main"
if ! git pull --ff-only origin main >/dev/null 2>&1; then
    err "git pull 失敗(可能本機有未提交 changes)"
    emit_json "git_pull_failed" "git pull 失敗 · 本機有未提交改動"
    exit 1
fi
ok "  git 已更新到 $REMOTE_SHORT"

info "[4/7] docker compose pull(拉新 image)"
if ! docker compose -f "$COMPOSE_FILE" pull --quiet 2>&1 | tail -3; then
    warn "  docker pull 部分失敗 · 繼續(本地 build 會補)"
fi

info "[5/7] docker compose up -d --build(重 build + 重啟)"
if ! docker compose -f "$COMPOSE_FILE" up -d --build 2>&1 | tail -10; then
    err "docker compose 失敗 · 自動 rollback"
    "$PROJECT_DIR/scripts/rollback.sh" --to "$BEFORE" --reason "compose_failed" --yes >&2 || true
    emit_json "compose_failed" "docker rebuild 失敗 · 已自動回滾到 $BEFORE_SHORT"
    exit 1
fi

# ---------- health check ----------
info "[6/7] 等 30 秒 + health check"
sleep 30

HEALTH_OK=1
HEALTH_DETAIL=""
for service in nginx librechat mongo accounting; do
    STATUS=$(docker compose -f "$COMPOSE_FILE" ps --status running --services 2>/dev/null | grep -c "^$service$" || echo "0")
    if [ "$STATUS" = "0" ]; then
        err "  容器 $service 沒在跑"
        HEALTH_OK=0
        HEALTH_DETAIL="$HEALTH_DETAIL $service:down"
    else
        ok "  $service · running"
    fi
done

# accounting health endpoint
if curl -fsS --max-time 5 http://localhost:8001/healthz >/dev/null 2>&1; then
    ok "  accounting /healthz · 200"
elif curl -fsS --max-time 5 http://localhost:8001/health >/dev/null 2>&1; then
    ok "  accounting /health · 200"
else
    warn "  accounting health endpoint 沒回 · 可能還在啟動"
fi

# nginx 80
if curl -fsS --max-time 5 http://localhost/ -o /dev/null 2>&1; then
    ok "  nginx 80 · 200"
else
    warn "  nginx 80 沒回(可能 launcher 路徑問題 · 不算 fatal)"
fi

if [ "$HEALTH_OK" -eq 0 ]; then
    err "Health check 失敗 · 自動 rollback"
    "$PROJECT_DIR/scripts/rollback.sh" --to "$BEFORE" --reason "health_failed:$HEALTH_DETAIL" --yes >&2 || true
    emit_json "health_failed" "Health check 失敗 · 已自動回滾"
    exit 1
fi

# ---------- 紀錄 ----------
info "[7/7] 寫更新紀錄"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
    echo "{\"ts\":\"$NOW\",\"action\":\"update\",\"from\":\"$BEFORE_SHORT\",\"to\":\"$REMOTE_SHORT\",\"commits\":$COMMITS_BEHIND,\"status\":\"ok\"}"
} >> "$HISTORY_FILE"

ok "更新完成!"
ok "  $BEFORE_SHORT → $REMOTE_SHORT($COMMITS_BEHIND commits)"
emit_json "ok" "已更新到 $REMOTE_SHORT" \
    "\"from\":\"$BEFORE_SHORT\"" \
    "\"to\":\"$REMOTE_SHORT\"" \
    "\"commits\":$COMMITS_BEHIND"

exit 0

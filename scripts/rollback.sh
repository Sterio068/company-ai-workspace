#!/bin/bash
# ========================================
# 承富智慧助理 · 回滾到上一個 commit
# ========================================
# 用法:
#   ./scripts/rollback.sh                          # 互動 · 列最近 5 commit · 選一個
#   ./scripts/rollback.sh --to <sha>               # 回到指定 commit
#   ./scripts/rollback.sh --to <sha> --yes         # 跳過確認
#   ./scripts/rollback.sh --previous               # 回到上一個成功 update 之前
#   ./scripts/rollback.sh --to <sha> --reason X --yes   # 給 update.sh 自動呼叫用

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="config-templates/docker-compose.yml"
HISTORY_FILE="$PROJECT_DIR/reports/update-history.jsonl"

TARGET=""
YES=0
PREVIOUS=0
REASON="manual"

while [ $# -gt 0 ]; do
    case "$1" in
        --to)        TARGET="$2"; shift 2 ;;
        --yes|-y)    YES=1; shift ;;
        --previous)  PREVIOUS=1; shift ;;
        --reason)    REASON="$2"; shift 2 ;;
        *) echo "未知參數:$1"; exit 2 ;;
    esac
done

CURRENT=$(git rev-parse HEAD)
CURRENT_SHORT=$(git rev-parse --short HEAD)

# --previous · 從 history 找上次 update 的 from
if [ "$PREVIOUS" -eq 1 ]; then
    if [ ! -f "$HISTORY_FILE" ]; then
        echo "❌ 沒有 update-history.jsonl · 不知道前一版"
        exit 1
    fi
    LAST_FROM=$(tail -1 "$HISTORY_FILE" | python3 -c "
import json, sys
try:
    line = sys.stdin.read().strip()
    if line:
        d = json.loads(line)
        print(d.get('from', ''))
except: pass
")
    if [ -z "$LAST_FROM" ]; then
        echo "❌ history 找不到前一版"
        exit 1
    fi
    TARGET="$LAST_FROM"
fi

# 互動模式 · 列出最近 5 commit
if [ -z "$TARGET" ]; then
    echo "目前在:$CURRENT_SHORT"
    echo ""
    echo "最近 commit:"
    git log --oneline -10
    echo ""
    read -rp "回到哪個 commit (sha)?" TARGET
fi

if [ -z "$TARGET" ]; then
    echo "❌ 沒指定目標"
    exit 2
fi

# 驗證 sha 存在
if ! git rev-parse --verify "$TARGET" >/dev/null 2>&1; then
    echo "❌ commit $TARGET 不存在"
    exit 1
fi

TARGET_FULL=$(git rev-parse "$TARGET")
TARGET_SHORT=$(git rev-parse --short "$TARGET")
TARGET_DATE=$(git log -1 --format=%ci "$TARGET")

if [ "$TARGET_FULL" = "$CURRENT" ]; then
    echo "ℹ 已經在 $CURRENT_SHORT · 不需回滾"
    exit 0
fi

if [ "$YES" -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "  即將回滾承富智慧助理"
    echo "================================================"
    echo "  目前:$CURRENT_SHORT"
    echo "  回到:$TARGET_SHORT($TARGET_DATE)"
    echo ""
    echo "  ⚠ git reset --hard · 之後無法 redo"
    echo "  📡 期間 Web UI 暫時無法使用"
    echo ""
    read -rp "確認回滾?(y/n)" CONFIRM
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        echo "已取消"
        exit 0
    fi
fi

echo "[1/3] git reset --hard $TARGET_SHORT"
if ! git reset --hard "$TARGET_FULL"; then
    echo "❌ git reset 失敗"
    exit 1
fi

echo "[2/3] docker compose up -d --build"
if ! docker compose -f "$COMPOSE_FILE" up -d --build 2>&1 | tail -10; then
    echo "❌ docker rebuild 失敗 · 系統處於不穩定狀態"
    echo "❌ 請手動 docker compose up -d --build · 必要時聯絡 Sterio"
    exit 1
fi

# 寫紀錄
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
mkdir -p "$(dirname "$HISTORY_FILE")"
echo "{\"ts\":\"$NOW\",\"action\":\"rollback\",\"from\":\"$CURRENT_SHORT\",\"to\":\"$TARGET_SHORT\",\"reason\":\"$REASON\",\"status\":\"ok\"}" >> "$HISTORY_FILE"

echo "[3/3] ✅ 回滾完成 · $CURRENT_SHORT → $TARGET_SHORT"
exit 0

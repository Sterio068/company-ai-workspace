#!/bin/bash
# ========================================
# 承富智慧助理 · 每日檢查 GitHub 是否有新版
# ========================================
# 寫 status JSON 到 reports/update-status.json
# launchd 每日 03:00 跑(install 後)
# Backend /admin/update/status 讀這個 JSON
#
# 用法:
#   ./scripts/check-update.sh              # 跑檢查 + 寫 JSON
#   ./scripts/check-update.sh --quiet      # 不印 log

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

STATUS_FILE="$PROJECT_DIR/reports/update-status.json"
QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

mkdir -p "$(dirname "$STATUS_FILE")"

log() { [ "$QUIET" -eq 0 ] && echo "$@" >&2; }

# 跑 update.sh --check-only --json · 抓 stdout
RESULT=$("$PROJECT_DIR/scripts/update.sh" --check-only --json 2>/dev/null || echo '{"status":"error","message":"check failed"}')

# 加入檢查時間 + 旁觀資訊
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HOST=$(hostname -s 2>/dev/null || echo "unknown")

# 用 python 加 timestamp(JSON merge)
echo "$RESULT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
data['checked_at'] = '$NOW'
data['host'] = '$HOST'
print(json.dumps(data, ensure_ascii=False, indent=2))
" > "$STATUS_FILE"

log "✅ status 寫到 $STATUS_FILE"
[ "$QUIET" -eq 0 ] && cat "$STATUS_FILE" >&2
exit 0

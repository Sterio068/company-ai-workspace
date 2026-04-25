#!/usr/bin/env bash
# 承富 AI · 乾淨 Mac/VM 安裝後 自動驗證腳本
# ==========================================================
# 用途:在乾淨 macOS VM(Tart / OrbStack / VirtualBuddy)裝完 DMG 之後 ·
#       由 IT 在 VM 內 跑這個 script · 驗證:
#         1. Docker stack 全 healthy
#         2. Launcher 首頁可訪問
#         3. LibreChat /api/config 可訪問
#         4. accounting healthz OK
#         5. 10 個 core Agent 真的建好
#         6. admin user 真的建好
#         7. nginx /manifest.json route OK
#         8. 13 份 user-guide 全 200
#         9. /safety/l3-preflight 在 sample text 上 work
#        10. release-verify gate 12 項複查
#
# F-08 對應 EXTERNAL-AUDIT-2026-04-25.md · 補完即可進 Phase 1 pilot
#
# 用法(在 VM 內):
#   cd /Users/<vm-user>/Workspace/ChengFu  # 或 ~/ChengFu
#   bash scripts/clean-install-verify.sh
#
# 結果寫到:
#   reports/clean-install/clean-install-verify-{date}.md
#
# 跑完後:
#   - 把 markdown 報告 + Terminal 截圖 + DMG 安裝過程錄影
#   - 一起 commit/upload 到 reports/clean-install/
#   - manifest 是 Phase 1 Gate 1 的必要交付證據
# ==========================================================

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost}"
REPORT_DIR="${REPO_ROOT}/reports/clean-install"
TIMESTAMP="$(date +%Y-%m-%d-%H%M%S)"
REPORT_FILE="${REPORT_DIR}/clean-install-verify-${TIMESTAMP}.md"

mkdir -p "${REPORT_DIR}"

PASSED=0
FAILED=0
FAIL_LOG=""

start_section() {
  echo ""
  echo "═══ $1 ═══"
}

pass() {
  PASSED=$((PASSED + 1))
  echo "✅ $1"
}

fail() {
  FAILED=$((FAILED + 1))
  FAIL_LOG="${FAIL_LOG}- $1\n"
  echo "❌ $1"
}

# ---------------------------------------------------
# Gate 1.1 · Docker stack
# ---------------------------------------------------
start_section "1.1 Docker 容器全 healthy"
EXPECTED_CONTAINERS=("chengfu-nginx" "chengfu-librechat" "chengfu-mongo" "chengfu-meili" "chengfu-accounting")
for c in "${EXPECTED_CONTAINERS[@]}"; do
  status=$(docker inspect --format='{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
  if [ "$status" = "running" ]; then
    pass "$c · running"
  else
    fail "$c · status=$status"
  fi
done

# ---------------------------------------------------
# Gate 1.2 · 入口可訪問
# ---------------------------------------------------
start_section "1.2 入口頁可訪問"
# bash 3.2 (macOS default) 不支援 declare -A · 用 pipe-delim list
ENDPOINTS_LIST="
nginx healthz|${BASE_URL}/healthz
launcher index|${BASE_URL}/
LibreChat config|${BASE_URL}/chat/api/config
accounting healthz|${BASE_URL}/api-accounting/healthz
PWA manifest|${BASE_URL}/manifest.json
"
while IFS='|' read -r name url; do
  [ -z "$name" ] && continue
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [ "$code" = "200" ]; then
    pass "$name · 200"
  else
    fail "$name · HTTP $code · $url"
  fi
done <<< "$ENDPOINTS_LIST"

# ---------------------------------------------------
# Gate 1.3 · 13 份 user-guide
# ---------------------------------------------------
start_section "1.3 13 份 user-guide 全 200"
GUIDES=(quickstart-v1.3 mobile-ios error-codes training-v1.3 troubleshooting-v1.3 \
        handoff-card slash-commands dashboard-metrics audio-note-sop \
        social-oauth-fallback knowledge-search frontend-endpoints admin-permissions)
for slug in "${GUIDES[@]}"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/static/user-guide/${slug}.md")
  if [ "$code" = "200" ]; then
    pass "user-guide · $slug"
  else
    fail "user-guide · $slug · HTTP $code"
  fi
done

# ---------------------------------------------------
# Gate 1.4 · admin user 真存在
# ---------------------------------------------------
start_section "1.4 admin user 已建立"
ADMIN_COUNT=$(docker exec chengfu-mongo mongosh chengfu --quiet --eval \
  'db.users.countDocuments({role:"ADMIN"})' 2>/dev/null | tr -d '[:space:]')
if [ "${ADMIN_COUNT:-0}" -ge 1 ]; then
  pass "users.role=ADMIN · count=$ADMIN_COUNT"
else
  fail "找不到 admin user · 安裝精靈 create-user 步驟可能失敗"
fi

# ---------------------------------------------------
# Gate 1.5 · 10 core Agent 真建好
# ---------------------------------------------------
start_section "1.5 10 個 core Agent 已建立"
AGENT_COUNT=$(docker exec chengfu-mongo mongosh chengfu --quiet --eval \
  'db.agents.countDocuments({})' 2>/dev/null | tr -d '[:space:]')
if [ "${AGENT_COUNT:-0}" -ge 10 ]; then
  pass "agents collection · count=$AGENT_COUNT(≥ 10)"
else
  fail "Agent 數量 $AGENT_COUNT < 10 · 安裝精靈 create-agents 步驟可能失敗"
  echo "   修法:"
  echo "   LIBRECHAT_URL=http://localhost \\"
  echo "   LIBRECHAT_ADMIN_EMAIL=<你的> \\"
  echo "   LIBRECHAT_ADMIN_PASSWORD=<你的> \\"
  echo "   python3 scripts/create-agents.py --tier core"
fi

# ---------------------------------------------------
# Gate 1.6 · safety endpoints
# ---------------------------------------------------
start_section "1.6 安全 endpoint 反應正常"
# L3 preflight · 安全 text(L1)
L3_RESP=$(curl -s -X POST "${BASE_URL}/api-accounting/safety/l3-preflight" \
  -H "Content-Type: application/json" \
  -d '{"text":"中秋節祝福"}')
if echo "$L3_RESP" | grep -q '"allowed":true' && echo "$L3_RESP" | grep -q '"01_or_02"'; then
  pass "/safety/l3-preflight L1 內容 → allowed=true"
else
  fail "/safety/l3-preflight L1 回應異常:$L3_RESP"
fi
# L3 preflight · L3 text
L3_HIT=$(curl -s -X POST "${BASE_URL}/api-accounting/safety/l3-preflight" \
  -H "Content-Type: application/json" \
  -d '{"text":"幫我分析選情"}')
if echo "$L3_HIT" | grep -q '"level":"03"'; then
  pass "/safety/l3-preflight L3 內容 → level=03"
else
  fail "/safety/l3-preflight L3 偵測失效:$L3_HIT"
fi

# ---------------------------------------------------
# Gate 1.7 · release-verify 13 gate 複查
# ---------------------------------------------------
start_section "1.7 release-verify.sh 複查"
if bash "${REPO_ROOT}/scripts/release-verify.sh" "$BASE_URL" > /tmp/release-verify-clean.log 2>&1; then
  pass "release-verify.sh 13 gate 全綠"
else
  RV_FAIL=$(grep -c "❌\|FAIL" /tmp/release-verify-clean.log || echo "?")
  fail "release-verify.sh 失敗 · $RV_FAIL 項 · log=/tmp/release-verify-clean.log"
fi

# ---------------------------------------------------
# Gate 1.8 · admin endpoint 認證
# ---------------------------------------------------
start_section "1.8 admin endpoint 認證(無 admin → 403)"
ADMIN_NO=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api-accounting/admin/dashboard")
if [ "$ADMIN_NO" = "403" ]; then
  pass "admin endpoint 無認證 → 403"
else
  fail "admin endpoint 無認證 → $ADMIN_NO(預期 403)"
fi

# ---------------------------------------------------
# Generate Manifest
# ---------------------------------------------------
TOTAL=$((PASSED + FAILED))
RESULT=$([ "$FAILED" -eq 0 ] && echo "PASS" || echo "FAIL")

# 用變數 prefix 然後 single-quote heredoc · 避免 markdown backtick 被當 shell command-sub
DATE_NOW="$(date +"%Y-%m-%d %H:%M:%S")"
HOSTNAME_NOW="$(hostname)"
MACOS_VER="$(sw_vers -productVersion 2>/dev/null || echo "unknown")"
DATE_DAY="$(date +%Y-%m-%d)"

{
  echo "# 乾淨安裝驗證報告(Gate 1)"
  echo ""
  echo "**日期**:$DATE_NOW"
  echo "**主機**:$HOSTNAME_NOW"
  echo "**macOS 版本**:$MACOS_VER"
  echo "**BASE_URL**:$BASE_URL"
  echo "**結果**:**$RESULT**"
  echo "**總計**:$PASSED / $TOTAL passed · $FAILED failed"
  echo ""
  echo "---"
  echo ""
} > "$REPORT_FILE"

cat >> "$REPORT_FILE" <<'BODY_EOF'
## 對應審計 finding

- **F-08**(External Audit 2026-04-25):乾淨 Mac VM 雙擊 DMG 全流程未在 release-verify 內覆蓋。本報告即為對應 Gate 1 證據。

## 涵蓋 Gate

1. Docker 5 容器 healthy
2. 入口 5 endpoints 200
3. 13 user-guide 全 200
4. admin user 已建立(users.role=ADMIN)
5. 10 core Agent 已建立(agents collection ≥ 10)
6. /safety/l3-preflight 正反向反應
7. release-verify.sh 13 gate 複查
8. admin endpoint 認證(無 admin → 403)

## 失敗項目

BODY_EOF

if [ -n "$FAIL_LOG" ]; then
  echo -e "$FAIL_LOG" >> "$REPORT_FILE"
else
  echo "(無 · 全部通過)" >> "$REPORT_FILE"
fi

cat >> "$REPORT_FILE" <<'TAIL_EOF'

## 附帶必要證據(請手動補)

- [ ] DMG 雙擊到完成的 Terminal 錄影(QuickTime Cmd+Shift+5)
- [ ] 「讀我.txt」截圖
- [ ] Gatekeeper「右鍵打開」截圖
- [ ] 安裝精靈 7 步輸入截圖
- [ ] LibreChat 首次登入截圖
- [ ] Launcher ⌘0 首頁截圖
- [ ] 任一工作區 Agent 對話截圖

把這些都放進 reports/clean-install/(YYYY-MM-DD)/ · 跟此 manifest 同 commit。

---

**這份 manifest 通過 = Phase 1 Gate 1 解鎖 · 可以開始 4 人 pilot。**
TAIL_EOF

echo ""
echo "═══════════════════════════════════════════"
echo "  Manifest:$REPORT_FILE"
echo "  $PASSED / $TOTAL passed · $FAILED failed"
echo "═══════════════════════════════════════════"

[ "$FAILED" -eq 0 ] || exit 1

#!/bin/bash
# ============================================================
# 承富 AI 系統 · 打包 Mac 安裝精靈為 .app + .dmg
# ============================================================
# 用 osacompile 把 ChengFu-AI-Installer.applescript 轉成 .app
# 然後 hdiutil 包成 ChengFu-AI-Installer.dmg(可分發給承富 IT)
#
# 用法:
#   ./installer/build.sh
#
# 產出:
#   installer/dist/ChengFu-AI-Installer.app  · macOS .app bundle
#   installer/dist/ChengFu-AI-Installer.dmg  · disk image(可 mail / USB 給 IT)
# ============================================================

set -euo pipefail

INSTALLER_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${INSTALLER_DIR}/.." && pwd)"
DIST_DIR="${INSTALLER_DIR}/dist"
APP_NAME="ChengFu-AI-Installer"
SRC="${INSTALLER_DIR}/${APP_NAME}.applescript"
APP="${DIST_DIR}/${APP_NAME}.app"
DMG="${DIST_DIR}/${APP_NAME}.dmg"
DMG_VOL_NAME="承富 AI 安裝精靈"

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; BLUE="\033[0;34m"; NC="\033[0m"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  承富 AI · 打包 Mac 安裝精靈${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

[[ -f "$SRC" ]] || { echo -e "${RED}❌ 找不到 $SRC${NC}"; exit 1; }

for sensitive in \
    "${REPO_ROOT}/scripts/passwords.txt" \
    "${REPO_ROOT}/config-templates/users.json"
do
    if [[ -e "$sensitive" ]]; then
        echo -e "${RED}❌ 偵測到敏感交付暫存檔: $sensitive${NC}"
        echo -e "${YELLOW}請先移到安全位置或刪除後再打包,避免 DMG 夾帶帳密/同仁資料。${NC}"
        exit 1
    fi
done

mkdir -p "$DIST_DIR"

# ---------- Step 0 · Frontend bundle freshness ----------
# DMG 直接包 repo snapshot；若只改 source 而忘了 npm run build，安裝後會載入舊 hash bundle。
LAUNCHER_DIR="${REPO_ROOT}/frontend/launcher"
if [[ -f "${LAUNCHER_DIR}/package.json" && -f "${LAUNCHER_DIR}/build.config.js" ]]; then
    echo -e "${BLUE}[0/3]${NC} 確認前端 bundle 是最新"
    if ! command -v npm > /dev/null 2>&1; then
        echo -e "${RED}❌ 找不到 npm,無法確保前端 dist/ 是最新${NC}"
        echo -e "${YELLOW}請先安裝 Node.js / npm,再重新打包。${NC}"
        exit 1
    fi
    (cd "$LAUNCHER_DIR" && { [[ -d node_modules ]] || npm install --silent; } && npm run build)
    echo -e "  ${GREEN}✓${NC} launcher dist/ 已更新"
fi

# ---------- Step 1 · osacompile · .applescript → .app ----------
echo -e "${BLUE}[1/3]${NC} 編譯 .applescript → .app"
rm -rf "$APP"
osacompile -o "$APP" "$SRC"
echo -e "  ${GREEN}✓${NC} 產 $APP"

# ---------- Step 2 · 內塞 README + LICENSE ----------
echo -e "${BLUE}[2/3]${NC} 設 .app metadata"

# 改 .app icon(用承富 logo · 若有)
LOGO_ICNS="${INSTALLER_DIR}/icon.icns"
if [[ -f "$LOGO_ICNS" ]]; then
    cp "$LOGO_ICNS" "${APP}/Contents/Resources/applet.icns"
    echo -e "  ${GREEN}✓${NC} 套承富 icon"
else
    echo -e "  ${YELLOW}⚠${NC} 無 icon.icns · 用 osacompile 預設(可後續放 installer/icon.icns)"
fi

# 改 .app Info.plist · 顯示中文名 + 版本
PLIST="${APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName 承富 AI 安裝精靈" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName 承富 AI 安裝精靈" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string '承富 AI 安裝精靈'" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 1.4.0" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string '1.4.0'" "$PLIST"
echo -e "  ${GREEN}✓${NC} 中文名 + 版本 1.4.0"

# ---------- Step 3 · 包成 .dmg ----------
echo -e "${BLUE}[3/3]${NC} 包成 .dmg(可 mail / USB 給 IT)"
rm -f "$DMG"

# 建臨時資料夾 · .app + README
DMG_STAGING="${DIST_DIR}/staging"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "$APP" "$DMG_STAGING/"

# 內建目前 repo 快照 · 避免最新本機開發尚未 push 時,安裝精靈 clone 到舊版。
# 排除本機資料庫、機密、快取與舊 installer 產物,保留可部署程式碼與 docs。
SNAPSHOT="${DMG_STAGING}/ChengFu-source.tar.gz"
echo -e "  ${BLUE}·${NC} 產內建 source 快照(排除 data/.env/.git/cache/local artifacts)"
tar \
    --exclude=".git" \
    --exclude=".claude" \
    --exclude=".DS_Store" \
    --exclude=".pytest_cache" \
    --exclude="tmp" \
    --exclude="**/__pycache__" \
    --exclude="**/*.pyc" \
    --exclude="**/node_modules" \
    --exclude="config-templates/.env" \
    --exclude="config-templates/.env.local" \
    --exclude="config-templates/.env.production" \
    --exclude="config-templates/data" \
    --exclude="config-templates/data-sandbox" \
    --exclude="config-templates/logs" \
    --exclude="config-templates/uploads" \
    --exclude="config-templates/images" \
    --exclude="scripts/passwords.txt" \
    --exclude="config-templates/users.json" \
    --exclude="reports" \
    --exclude="reports/qa-artifacts" \
    --exclude="test-results" \
    --exclude="playwright-report" \
    --exclude="tests/e2e/test-results" \
    --exclude="tests/e2e/playwright-report" \
    --exclude="installer/dist" \
    --exclude="installer-run.command" \
    --exclude="*.log" \
    -czf "$SNAPSHOT" \
    -C "$REPO_ROOT" .
echo -e "  ${GREEN}✓${NC} source 快照 $(du -h "$SNAPSHOT" | awk '{print $1}')"

# 包 README.txt(雙擊 .dmg 後看到的指引)
cat > "$DMG_STAGING/讀我.txt" << 'EOF'
═══════════════════════════════════════════════════
  承富 AI 系統 v1.3/vNext · Mac 安裝精靈
═══════════════════════════════════════════════════

⚠ 重要 · 第一次打開請看這裡 ⚠

  macOS 對網路下載的 .app 預設擋(Gatekeeper · App 已被修改或損毀)
  解法:雙擊「打開我.command」自動清 quarantine + 跑安裝

  若不要用 .command(老派方式):
   • 對「ChengFu-AI-Installer.app」按右鍵 →「打開」→ 跳警告再按「打開」
   • 或:系統設定 → 隱私權與安全性 → 找到被擋的 app →「仍要打開」

═══════════════════════════════════════════════════

【使用方法】

  1. 雙擊「打開我.command」(推薦)
     或對「ChengFu-AI-Installer.app」按右鍵 →「打開」
  2. 若已安裝過,會先偵測既有 .env + Keychain:
     • 選「沿用既有」:不重填 API Key / 網域 / admin / NAS
     • 選「重新設定」:走完整 7 步驟,可更換設定
  3. 第一次安裝或重新設定時,跟隨對話框引導 · 輸入:
     • OpenAI API Key(必填 · 主力 AI 引擎)
       取得網址:https://platform.openai.com/api-keys
     • Anthropic API Key(選配 · Claude 備援)
       取得網址:https://console.anthropic.com/settings/keys
     • Fal.ai API Key(設計生圖選配 · 裝完可在中控設定)
       取得網址:https://fal.ai/dashboard/keys
     • 公司域名(可選 · 留空用本機 localhost)
     • 管理員 email(必填 · 請用承富公司管理信箱)
     • NAS 路徑(可選)
  4. 確認後自動完成:
     • 若本機沒有 ChengFu repo,會先從此 .dmg 內建快照展開新版程式碼
     • 機密寫入或沿用 macOS Keychain
     • 建 .env 或沿用既有 .env(保留 Mongo 帳號、對話、Agent)
     • 抓 5 個 Docker image
     • 啟動 6 個容器
     • 跑健康檢查
     • 印維運手冊
  5. 完成後瀏覽器自動開 http://localhost/

【需要預先準備】

  • macOS Sequoia 或更新
  • Docker Desktop for Mac · 已啟動
    https://www.docker.com/products/docker-desktop/
  • 至少 16GB RAM(建議 24GB)
  • 至少 20GB 磁碟空間
  • 穩定網路(抓 image 約 2-3GB)
  • OpenAI API Key
    https://platform.openai.com/api-keys
  • Anthropic API Key(選配 · Claude 備援)
    https://console.anthropic.com/settings/keys
  • Fal.ai API Key(設計生圖選配)
    https://fal.ai/dashboard/keys

【完成後 IT 接手做的 6 件】

  1. python3 scripts/create-users.py     · 建 10 同仁帳號
  2. python3 scripts/create-agents.py    · 建 10 個 AI Agent
  3. python3 scripts/upload-knowledge-base.py · 上傳承富知識庫
  4. ./scripts/install-launchd.sh        · 排定 cron(每日備份/標案/digest)
  5. 設 Cloudflare Tunnel               · 對外網域
  6. 安排 2 場教育訓練                   · 全員 Onboarding + 進階

【常見問題】

  Q: 安裝失敗了?
  A: 重跑「ChengFu-AI-Installer.app」即可 · 選「沿用既有」跳過已完成步驟

  Q: Docker 沒啟動?
  A: 開啟「Docker Desktop」· 等右上角 Docker 圖示變綠 · 重跑安裝

  Q: 找不到 ChengFu repo?
  A: 安裝精靈會自動 clone 到 ~/ChengFu · 或讓你選現有路徑

  Q: 想看更詳細指引?
  A: 完整文件在 ~/ChengFu/INSTALL.md 與 ~/ChengFu/DEPLOY.md

【聯絡】

  作者:Sterio
  Email:請填承富內部 IT / 專案負責窗口
  GitHub:https://github.com/Sterio068/chengfu-ai
EOF
echo -e "  ${GREEN}✓${NC} 寫進「讀我.txt」"

# 「打開我.command」· 自動清 quarantine + 跑安裝精靈
# 雙擊 .command 比較穩 · 避免承富 IT 卡在 Gatekeeper
cat > "$DMG_STAGING/打開我.command" << 'CMDEOF'
#!/bin/bash
# ============================================================
# 一鍵清 macOS Gatekeeper quarantine + 跑承富 AI 安裝精靈
# ============================================================
clear
echo "═══════════════════════════════════════════════════"
echo "  承富 AI · 一鍵打開"
echo "═══════════════════════════════════════════════════"
echo ""

DMG_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="${DMG_DIR}/ChengFu-AI-Installer.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ 找不到 ChengFu-AI-Installer.app"
    echo "   請確認此 .command 跟 .app 在同一資料夾"
    read -p "按 Enter 結束..."
    exit 1
fi

echo "▌ 1. 清 macOS quarantine attribute..."
# DMG 內無法寫 · 拷到 /Applications 後再清
TARGET="/Applications/ChengFu-AI-Installer.app"
if [ -d "$TARGET" ]; then
    echo "  · 目標已存在 · 覆蓋"
    rm -rf "$TARGET"
fi
echo "  · 拷到 /Applications/"
cp -R "$APP_PATH" "$TARGET" 2>&1 | tail -3

echo "  · xattr -cr"
xattr -cr "$TARGET" 2>/dev/null || sudo xattr -cr "$TARGET"

echo ""
echo "▌ 2. 打開安裝精靈..."
open "$TARGET"

echo ""
echo "✅ 完成 · 安裝精靈視窗已打開"
echo "   若沒跳出 · 自己去 /Applications/ 雙擊"
echo ""
read -p "按 Enter 關閉此視窗..."
CMDEOF
chmod +x "$DMG_STAGING/打開我.command"
echo -e "  ${GREEN}✓${NC} 加「打開我.command」(避 Gatekeeper)"

# 用 hdiutil 建 .dmg
hdiutil create -volname "$DMG_VOL_NAME" \
    -srcfolder "$DMG_STAGING" \
    -ov -format UDZO \
    "$DMG" > /dev/null 2>&1

# 清臨時
rm -rf "$DMG_STAGING"

echo -e "  ${GREEN}✓${NC} 產 $DMG"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ 完成${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo "  .app:$APP"
echo "  .dmg:$DMG"
echo ""
echo "  打開測試:open '$APP'"
echo "  分發:USB / mail / Slack 把 $DMG 給承富 IT"
echo ""
ls -lh "$DIST_DIR" | tail -3

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

mkdir -p "$DIST_DIR"

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
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 1.3.0" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string '1.3.0'" "$PLIST"
echo -e "  ${GREEN}✓${NC} 中文名 + 版本 1.3.0"

# ---------- Step 3 · 包成 .dmg ----------
echo -e "${BLUE}[3/3]${NC} 包成 .dmg(可 mail / USB 給 IT)"
rm -f "$DMG"

# 建臨時資料夾 · .app + README
DMG_STAGING="${DIST_DIR}/staging"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "$APP" "$DMG_STAGING/"

# 包 README.txt(雙擊 .dmg 後看到的指引)
cat > "$DMG_STAGING/讀我.txt" << 'EOF'
═══════════════════════════════════════════════════
  承富 AI 系統 v1.1 · Mac 安裝精靈
═══════════════════════════════════════════════════

【使用方法】

  1. 雙擊「ChengFu-AI-Installer.app」開始安裝
  2. 跟隨對話框引導 · 輸入:
     • Anthropic API Key(必填 · 從 console.anthropic.com 拿)
     • 公司域名(可選 · 留空用本機 localhost)
     • 管理員 email(預設 sterio068@gmail.com)
     • NAS 路徑(可選)
  3. 確認後自動完成:
     • 機密寫入 macOS Keychain
     • 建 .env 注入 prod fail-closed env
     • 抓 5 個 Docker image
     • 啟動 6 個容器
     • 跑健康檢查
     • 印維運手冊
  4. 完成後瀏覽器自動開 http://localhost/

【需要預先準備】

  • macOS Sequoia 或更新
  • Docker Desktop for Mac · 已啟動
    https://www.docker.com/products/docker-desktop/
  • 至少 16GB RAM(建議 24GB)
  • 至少 20GB 磁碟空間
  • 穩定網路(抓 image 約 2-3GB)
  • Anthropic API Key · Tier 2(預存 USD $50)
    https://console.anthropic.com

【完成後 IT 接手做的 6 件】

  1. python3 scripts/create-users.py     · 建 10 同仁帳號
  2. python3 scripts/create-agents.py    · 建 10 個 AI Agent
  3. python3 scripts/upload-knowledge-base.py · 上傳承富知識庫
  4. ./scripts/install-launchd.sh        · 排定 cron(每日備份/標案/digest)
  5. 設 Cloudflare Tunnel               · 對外網域
  6. 安排 2 場教育訓練                   · 全員 Onboarding + 進階

【常見問題】

  Q: 安裝失敗了?
  A: 重跑「ChengFu-AI-Installer.app」即可 · 跳過已完成步驟

  Q: Docker 沒啟動?
  A: 開啟「Docker Desktop」· 等右上角 Docker 圖示變綠 · 重跑安裝

  Q: 找不到 ChengFu repo?
  A: 安裝精靈會自動 clone 到 ~/ChengFu · 或讓你選現有路徑

  Q: 想看更詳細指引?
  A: 完整文件在 ~/ChengFu/INSTALL.md 與 ~/ChengFu/DEPLOY.md

【聯絡】

  作者:Sterio
  Email:sterio068@gmail.com
  GitHub:https://github.com/Sterio068/chengfu-ai
EOF
echo -e "  ${GREEN}✓${NC} 寫進「讀我.txt」"

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

#!/usr/bin/env bash
# v1.3 A4 · 互動式設定 Backblaze B2 異機備份
#
# 為什麼 B2:
# - 0 cost 10 GB free(承富 1 年備份估 ~5 GB)
# - 比 S3 便宜 5x · 比 R2 便宜 2x
# - rclone 原生支援 · 不用 AWS SDK
#
# 用法:
#   ./scripts/setup-rclone-b2.sh
#
# 前置:
# 1. 到 https://www.backblaze.com/b2/ 註冊(信用卡認證)
# 2. App Keys → Add a New Application Key
#    - Name: chengfu-ai-backup
#    - Allow access: All buckets(or 指定 bucket)
#    - Type: Read and Write
#    - 複製 keyID + applicationKey(只顯示 1 次)
# 3. Buckets → Create a Bucket
#    - Name: chengfu-backup-(隨機後綴 · B2 全球唯一)
#    - Files: Private
#    - Encryption: Server-side(預設)

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  承富 AI · Backblaze B2 異機備份設定 (A4)${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""

# ---------- 檢查 rclone ----------
if ! command -v rclone > /dev/null 2>&1; then
    echo -e "${RED}❌ rclone 未安裝${NC}"
    echo "請先:brew install rclone"
    exit 1
fi
echo -e "${GREEN}✓${NC} rclone 已安裝 · $(rclone version | head -1)"

# ---------- 檢查 GPG ----------
if ! gpg --list-keys chengfu > /dev/null 2>&1; then
    echo -e "${RED}❌ 缺 'chengfu' GPG key${NC}"
    echo "請先建:gpg --full-generate-key(name 設 'chengfu')"
    echo "詳:docs/05-SECURITY.md §6"
    exit 1
fi
echo -e "${GREEN}✓${NC} GPG key 'chengfu' 已配置(B2 上的檔案會 GPG 加密)"

# ---------- 檢查既有 remote ----------
EXISTING_REMOTE="chengfu-offsite"
if rclone listremotes 2>/dev/null | grep -q "^${EXISTING_REMOTE}:"; then
    echo ""
    echo -e "${YELLOW}⚠ 'chengfu-offsite' remote 已存在${NC}"
    read -p "覆寫?(y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "已取消 · 既有設定保留"
        exit 0
    fi
    rclone config delete "$EXISTING_REMOTE"
fi

# ---------- 互動取得 credentials ----------
echo ""
echo -e "${YELLOW}從 Backblaze 後台貼入(只顯示 1 次的 key)${NC}"
read -p "B2 keyID: " B2_KEY_ID
read -s -p "B2 applicationKey: " B2_APP_KEY
echo ""
read -p "B2 bucket name(已建好): " B2_BUCKET
echo ""

if [[ -z "$B2_KEY_ID" || -z "$B2_APP_KEY" || -z "$B2_BUCKET" ]]; then
    echo -e "${RED}❌ 三個欄位都不可空${NC}"
    exit 1
fi

# ---------- 寫 rclone config ----------
rclone config create "$EXISTING_REMOTE" b2 \
    account "$B2_KEY_ID" \
    key "$B2_APP_KEY" \
    --non-interactive

# 把 B2 keys 也存進 macOS Keychain · 給 backup.sh + dr-drill.sh 找
security delete-generic-password -s "chengfu-ai-b2-key-id" -a "$USER" 2>/dev/null || true
security add-generic-password -s "chengfu-ai-b2-key-id" -a "$USER" -w "$B2_KEY_ID"
security delete-generic-password -s "chengfu-ai-b2-app-key" -a "$USER" 2>/dev/null || true
security add-generic-password -s "chengfu-ai-b2-app-key" -a "$USER" -w "$B2_APP_KEY"

# ---------- 驗證 ----------
echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo "驗證連線..."

if rclone lsd "${EXISTING_REMOTE}:" 2>&1 | grep -q "$B2_BUCKET"; then
    echo -e "${GREEN}✓${NC} 連線成功 · bucket '${B2_BUCKET}' 可見"
else
    echo -e "${YELLOW}⚠ 連線 OK 但找不到 bucket '${B2_BUCKET}'${NC}"
    echo "  請確認 B2 後台已建此 bucket"
fi

# ---------- 寫 ENV 提示 ----------
echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo "下一步:配 backup.sh 用此 remote"
echo ""
echo "在 ~/.zshenv(或 .bash_profile)加:"
echo ""
echo -e "${YELLOW}  export CHENGFU_OFFSITE_REMOTE=\"chengfu-offsite:${B2_BUCKET}\"${NC}"
echo ""
echo "或 launchd plist 內 EnvironmentVariables 段:"
echo ""
echo -e "${YELLOW}  <key>EnvironmentVariables</key>${NC}"
echo -e "${YELLOW}  <dict>${NC}"
echo -e "${YELLOW}    <key>CHENGFU_OFFSITE_REMOTE</key>${NC}"
echo -e "${YELLOW}    <string>chengfu-offsite:${B2_BUCKET}</string>${NC}"
echo -e "${YELLOW}  </dict>${NC}"
echo ""
echo "驗收(明日 02:00 cron 跑後):"
echo "  rclone ls chengfu-offsite:${B2_BUCKET}/daily/ | head"
echo ""
echo "災難還原(用 dr-drill.sh):"
echo "  ./scripts/dr-drill.sh --from-offsite"
echo ""
echo -e "${GREEN}✅ 設定完成${NC}"

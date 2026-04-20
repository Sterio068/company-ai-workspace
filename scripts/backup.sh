#!/bin/bash
# ========================================
# 承富 AI 系統 · 每日備份
# ========================================
# 備份 MongoDB(對話紀錄、Agent 定義、使用者資料)
# 保留 30 天滾動,每週日再保留週備份 12 週
# 透過 cron 每日 02:00 執行
#
# 手動執行:./scripts/backup.sh
#
# 設定 cron(每日 02:00):
#   crontab -e
#   0 2 * * * /Users/<user>/Workspace/ChengFu/scripts/backup.sh >> /var/log/chengfu-backup.log 2>&1

set -euo pipefail

BACKUP_ROOT="${HOME}/chengfu-backups"
DAILY_DIR="${BACKUP_ROOT}/daily"
WEEKLY_DIR="${BACKUP_ROOT}/weekly"
DATE=$(date +%Y-%m-%d)
DOW=$(date +%u)  # 1=Monday, 7=Sunday
DAILY_RETENTION=30
WEEKLY_RETENTION_WEEKS=12

mkdir -p "$DAILY_DIR" "$WEEKLY_DIR"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ------------------ 備份 MongoDB(對話 + 會計 + 專案 + 回饋)------------------
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 開始 MongoDB 備份..."

ARCHIVE="${DAILY_DIR}/chengfu-${DATE}.archive.gz"
docker exec chengfu-mongo mongodump \
    --archive --db chengfu --quiet \
    2>/dev/null | gzip -9 > "$ARCHIVE"

# ------------------ 備份 knowledge-base + config + frontend ------------------
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 備份 knowledge-base + config..."
KB_ARCHIVE="${DAILY_DIR}/chengfu-kb-${DATE}.tar.gz"
tar czf "$KB_ARCHIVE" \
    -C "$PROJECT_DIR" \
    knowledge-base/ \
    config-templates/librechat.yaml \
    config-templates/docker-compose.yml \
    config-templates/actions/ \
    config-templates/presets/ \
    frontend/launcher/ \
    frontend/custom/ \
    frontend/nginx/ \
    2>/dev/null
KB_SIZE=$(du -h "$KB_ARCHIVE" 2>/dev/null | cut -f1)
echo "  ✅ knowledge-base + config: $KB_ARCHIVE ($KB_SIZE)"

# ------------------ Keychain 項目清單(只記 key names,不 dump 值)------------------
# 真正機密存 Keychain · 遺失則從該機 Keychain 重新匯出
KEYCHAIN_LIST="${DAILY_DIR}/chengfu-keychain-inventory-${DATE}.txt"
security dump-keychain 2>/dev/null | grep -oE 'chengfu-ai-[a-z-]+' | sort -u > "$KEYCHAIN_LIST" 2>/dev/null || true
echo "  ✅ Keychain 項目清單: $KEYCHAIN_LIST"

SIZE=$(du -h "$ARCHIVE" | cut -f1)
echo "  ✅ 備份完成: $ARCHIVE ($SIZE)"

# ------------------ GPG 加密(若已設)------------------
if command -v gpg > /dev/null 2>&1 && gpg --list-keys chengfu > /dev/null 2>&1; then
    gpg --batch --yes --encrypt --recipient chengfu --output "${ARCHIVE}.gpg" "$ARCHIVE"
    rm "$ARCHIVE"
    ARCHIVE="${ARCHIVE}.gpg"
    echo "  🔐 已 GPG 加密: $ARCHIVE"
else
    echo "  ⚠ 未設定 GPG key 'chengfu',備份未加密。見 docs/05-SECURITY.md"
fi

# ------------------ 週備份(每週日)------------------
if [[ "$DOW" == "7" ]]; then
    WEEKLY_COPY="${WEEKLY_DIR}/$(basename "$ARCHIVE")"
    cp "$ARCHIVE" "$WEEKLY_COPY"
    echo "  📦 週備份: $WEEKLY_COPY"
fi

# ------------------ 輪替 ------------------
find "$DAILY_DIR" -type f -mtime +${DAILY_RETENTION} -delete
find "$WEEKLY_DIR" -type f -mtime +$((WEEKLY_RETENTION_WEEKS * 7)) -delete

echo "[$(date +'%Y-%m-%d %H:%M:%S')] 備份流程完成"

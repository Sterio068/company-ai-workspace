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

# ------------------ 備份 Meilisearch 索引(Round 9 暗示 + Codex Round 10.5 紅)----------------
# Codex 抓到兩個假安全感:
#   1. 原本 sleep 5 不 poll task status · dump 可能未完成就 tar
#   2. tar 成 .tar.gz 後沒 GPG · 搜尋索引含檔案內容(客戶名/建議書片段)明文上雲
# 修正:poll /tasks/{uid} 直到 succeeded · 再 tar · GPG 加密後才上傳
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 備份 Meilisearch 索引..."
MEILI_DUMP="${DAILY_DIR}/chengfu-meili-${DATE}.tar.gz"
MEILI_KEY=$(docker exec chengfu-accounting printenv MEILI_MASTER_KEY 2>/dev/null || echo "")
if [[ -n "$MEILI_KEY" ]]; then
    # Trigger dump · 拿 task uid
    DUMP_RESP=$(docker exec chengfu-meili wget -qO- \
        --header="Authorization: Bearer ${MEILI_KEY}" \
        --post-data='' http://localhost:7700/dumps 2>/dev/null || echo "")
    TASK_UID=$(echo "$DUMP_RESP" | sed -n 's/.*"taskUid":\([0-9]*\).*/\1/p')
    if [[ -n "$TASK_UID" ]]; then
        # Poll task status 最多 120 秒(50k 檔實測約 30-90 秒)
        MEILI_STATUS=""
        for i in $(seq 1 24); do
            TASK_JSON=$(docker exec chengfu-meili wget -qO- \
                --header="Authorization: Bearer ${MEILI_KEY}" \
                http://localhost:7700/tasks/${TASK_UID} 2>/dev/null)
            MEILI_STATUS=$(echo "$TASK_JSON" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
            if [[ "$MEILI_STATUS" == "succeeded" ]]; then
                break
            elif [[ "$MEILI_STATUS" == "failed" || "$MEILI_STATUS" == "canceled" ]]; then
                echo "  ❌ Meili dump task $TASK_UID $MEILI_STATUS · skip"
                break
            fi
            sleep 5
        done

        if [[ "$MEILI_STATUS" == "succeeded" ]]; then
            if [[ -d "${PROJECT_DIR}/config-templates/data/meili/dumps" ]]; then
                tar czf "$MEILI_DUMP" -C "${PROJECT_DIR}/config-templates/data/meili" dumps/ 2>/dev/null
                MEILI_SIZE=$(du -h "$MEILI_DUMP" 2>/dev/null | cut -f1)
                echo "  ✅ Meili dump: $MEILI_DUMP ($MEILI_SIZE) · task_uid=$TASK_UID"
                find "${PROJECT_DIR}/config-templates/data/meili/dumps" \
                    -name "*.dump" -mtime +7 -delete 2>/dev/null || true
            else
                echo "  ⚠ Meili dumps 目錄不存在 · skip"
                MEILI_DUMP=""
            fi
        else
            echo "  ⚠ Meili dump 120 秒內未完成(status=$MEILI_STATUS) · skip"
            MEILI_DUMP=""
        fi
    else
        echo "  ⚠ Meili dump 觸發失敗(無 taskUid)· 留意 cron log"
        MEILI_DUMP=""
    fi
else
    echo "  ⚠ MEILI_MASTER_KEY 未設 · skip(知識庫搜尋未啟用 · 不影響資料)"
    MEILI_DUMP=""
fi

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

# ------------------ GPG 加密(Codex Round 10.5 · KB + Meili 也一律加密)------------------
if command -v gpg > /dev/null 2>&1 && gpg --list-keys chengfu > /dev/null 2>&1; then
    # Mongo archive
    gpg --batch --yes --encrypt --recipient chengfu --output "${ARCHIVE}.gpg" "$ARCHIVE"
    rm "$ARCHIVE"
    ARCHIVE="${ARCHIVE}.gpg"
    echo "  🔐 Mongo 已 GPG 加密: $ARCHIVE"
    # KB archive(可能含客戶名 / 建議書片段 · 原本明文上雲是漏洞)
    if [[ -n "${KB_ARCHIVE:-}" && -f "$KB_ARCHIVE" ]]; then
        gpg --batch --yes --encrypt --recipient chengfu --output "${KB_ARCHIVE}.gpg" "$KB_ARCHIVE"
        rm "$KB_ARCHIVE"
        KB_ARCHIVE="${KB_ARCHIVE}.gpg"
        echo "  🔐 KB 已 GPG 加密: $KB_ARCHIVE"
    fi
    # Meili dump(索引內容含文件預覽 2000 字 · 含客戶案例)
    if [[ -n "${MEILI_DUMP:-}" && -f "$MEILI_DUMP" ]]; then
        gpg --batch --yes --encrypt --recipient chengfu --output "${MEILI_DUMP}.gpg" "$MEILI_DUMP"
        rm "$MEILI_DUMP"
        MEILI_DUMP="${MEILI_DUMP}.gpg"
        echo "  🔐 Meili 已 GPG 加密: $MEILI_DUMP"
    fi
else
    echo "  ⚠ 未設定 GPG key 'chengfu' · 所有備份未加密 · 異機上傳會被跳過"
    echo "  ⚠ 見 docs/05-SECURITY.md 「GPG key 設定」· 此為強制 · 不設就沒異機備份"
fi

# ------------------ 週備份(每週日)------------------
if [[ "$DOW" == "7" ]]; then
    WEEKLY_COPY="${WEEKLY_DIR}/$(basename "$ARCHIVE")"
    cp "$ARCHIVE" "$WEEKLY_COPY"
    echo "  📦 週備份: $WEEKLY_COPY"
fi

# ------------------ Off-site 加密備份(v4.3 · 審查紅線)------------------
# 需先:
#   brew install rclone gnupg
#   gpg --full-generate-key   (name 設為 'chengfu')
#   rclone config              (遠端名 "chengfu-offsite",可 Backblaze B2 / Cloudflare R2 / S3)
# 若未設定 rclone · 此步驟略過(但應盡快補,Mac mini 燒掉 = 資料全滅)
OFFSITE_REMOTE="${CHENGFU_OFFSITE_REMOTE:-chengfu-offsite:chengfu-backup}"
if command -v rclone > /dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -q "^${OFFSITE_REMOTE%%:*}:"; then
    # 只上傳已 GPG 加密的 · 未加密檔絕不出門
    # Codex Round 10.5 · 所有上雲的一律要 .gpg
    if [[ "$ARCHIVE" == *.gpg ]]; then
        rclone copy "$ARCHIVE"       "${OFFSITE_REMOTE}/daily/"     --quiet 2>&1 || echo "  ⚠ rclone daily 失敗"
        # KB 必 .gpg 才上傳(之前紅線)
        if [[ -n "${KB_ARCHIVE:-}" && "$KB_ARCHIVE" == *.gpg && -f "$KB_ARCHIVE" ]]; then
            rclone copy "$KB_ARCHIVE" "${OFFSITE_REMOTE}/kb/" --quiet 2>&1 || echo "  ⚠ rclone kb 失敗"
        elif [[ -n "${KB_ARCHIVE:-}" ]]; then
            echo "  ⚠ KB archive 未加密 · 不上傳"
        fi
        rclone copy "$KEYCHAIN_LIST" "${OFFSITE_REMOTE}/inventory/" --quiet 2>&1 || echo "  ⚠ rclone inv 失敗"
        # Meili 同樣必 .gpg
        if [[ -n "${MEILI_DUMP:-}" && "$MEILI_DUMP" == *.gpg && -f "$MEILI_DUMP" ]]; then
            rclone copy "$MEILI_DUMP" "${OFFSITE_REMOTE}/meili/" --quiet 2>&1 || echo "  ⚠ rclone meili 失敗"
        elif [[ -n "${MEILI_DUMP:-}" ]]; then
            echo "  ⚠ Meili dump 未加密 · 不上傳"
        fi
        echo "  ☁  已異機備份到 ${OFFSITE_REMOTE}"
    else
        echo "  ⚠ 未 GPG 加密 · 不上傳異機 · 先設 'chengfu' GPG key"
    fi
    # 異機端保留 60 天(本機 30 + 異機多 30 = 雙保險)
    rclone delete --min-age 60d "${OFFSITE_REMOTE}/daily/"  --quiet 2>/dev/null || true
else
    echo "  ⚠ 未設 rclone · 目前只本機備份 · 見 docs/05-SECURITY.md 異機設定"
fi

# ------------------ 輪替 ------------------
find "$DAILY_DIR" -type f -mtime +${DAILY_RETENTION} -delete
find "$WEEKLY_DIR" -type f -mtime +$((WEEKLY_RETENTION_WEEKS * 7)) -delete

echo "[$(date +'%Y-%m-%d %H:%M:%S')] 備份流程完成"

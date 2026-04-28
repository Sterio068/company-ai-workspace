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
ALLOW_PLAINTEXT_BACKUP="${ALLOW_PLAINTEXT_BACKUP:-0}"

if command -v gpg > /dev/null 2>&1 && gpg --list-keys chengfu > /dev/null 2>&1; then
    GPG_AVAILABLE=1
else
    GPG_AVAILABLE=0
    if [[ "$ALLOW_PLAINTEXT_BACKUP" != "1" ]]; then
        echo "❌ 找不到 GPG key 'chengfu' · 正式備份不允許落明文" >&2
        echo "   先執行:gpg --full-generate-key  (name 設為 chengfu)" >&2
        echo "   只限本機開發可暫時:ALLOW_PLAINTEXT_BACKUP=1 ./scripts/backup.sh" >&2
        exit 1
    fi
    echo "  ⚠ ALLOW_PLAINTEXT_BACKUP=1 · 本次只允許本機明文備份,絕不上傳異機"
fi

# ------------------ 備份 MongoDB(對話 + 會計 + 專案 + 回饋)------------------
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 開始 MongoDB 備份..."

# Codex R2.3 · 若 GPG key 可用 · 直接 pipe 到加密 · 不留明文中間檔
ARCHIVE="${DAILY_DIR}/chengfu-${DATE}.archive.gz"
if [[ "$GPG_AVAILABLE" == "1" ]]; then
    # GPG 可用 · 一條 pipeline · 磁碟上永遠不落明文
    ARCHIVE="${DAILY_DIR}/chengfu-${DATE}.archive.gz.gpg"
    docker exec chengfu-mongo mongodump --archive --db chengfu --quiet 2>/dev/null \
        | gzip -9 \
        | gpg --batch --yes --encrypt --recipient chengfu --output "$ARCHIVE"
    echo "  🔐 Mongo pipeline 直接加密: $ARCHIVE"
else
    # 無 GPG key · 退回明文本機(但異機不會上傳)
    docker exec chengfu-mongo mongodump --archive --db chengfu --quiet 2>/dev/null \
        | gzip -9 > "$ARCHIVE"
    echo "  ⚠ 無 GPG · Mongo 本機明文 $ARCHIVE · 異機傳輸會 skip"
    chmod 600 "$ARCHIVE" 2>/dev/null || true
fi

# ------------------ 備份 Meilisearch 索引(Round 9 暗示 + Codex Round 10.5 紅)----------------
# Codex 抓到兩個假安全感:
#   1. 原本 sleep 5 不 poll task status · dump 可能未完成就 tar
#   2. tar 成 .tar.gz 後沒 GPG · 搜尋索引含檔案內容(客戶名/建議書片段)明文上雲
# 修正:poll /tasks/{uid} 直到 succeeded · 再 tar · GPG 加密後才上傳
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 備份 Meilisearch 索引..."
MEILI_DUMP="${DAILY_DIR}/chengfu-meili-${DATE}.tar.gz"
MEILI_KEY=$(docker exec chengfu-accounting printenv MEILI_MASTER_KEY 2>/dev/null || echo "")
# Codex R2.3 · jq 必裝 · 不用脆弱 sed(若無則 skip Meili backup · 不擋整支)
if ! command -v jq > /dev/null 2>&1; then
    echo "  ⚠ jq 未裝(brew install jq)· 跳過 Meili 備份(非 fatal)"
    MEILI_KEY=""
fi
if [[ -n "$MEILI_KEY" ]]; then
    # Trigger dump · 拿 task uid(`|| echo ""` 避免網路抖動退出整支 backup)
    DUMP_RESP=$(docker exec chengfu-meili wget -qO- \
        --header="Authorization: Bearer ${MEILI_KEY}" \
        --post-data='' http://127.0.0.1:7700/dumps 2>/dev/null || echo "")
    TASK_UID=$(echo "$DUMP_RESP" | jq -r '.taskUid // empty' 2>/dev/null || echo "")
    if [[ -n "$TASK_UID" && "$TASK_UID" != "null" ]]; then
        # Poll task status 最多 120 秒
        MEILI_STATUS=""
        for i in $(seq 1 24); do
            TASK_JSON=$(docker exec chengfu-meili wget -qO- \
                --header="Authorization: Bearer ${MEILI_KEY}" \
                http://127.0.0.1:7700/tasks/${TASK_UID} 2>/dev/null || echo "")
            MEILI_STATUS=$(echo "$TASK_JSON" | jq -r '.status // empty' 2>/dev/null || echo "")
            if [[ "$MEILI_STATUS" == "succeeded" ]]; then
                break
            elif [[ "$MEILI_STATUS" == "failed" || "$MEILI_STATUS" == "canceled" ]]; then
                echo "  ❌ Meili dump task $TASK_UID $MEILI_STATUS · skip"
                break
            fi
            sleep 5
        done

        if [[ "$MEILI_STATUS" == "succeeded" ]]; then
            # Codex R2.3 · Meili dump 也 pipe 直接加密
            if [[ -d "${PROJECT_DIR}/config-templates/data/meili/dumps" ]]; then
                # Codex R2.4 · 只打包本輪的 dump · 用 taskUid 找對應 file
                # Meili dump 檔名格式 <hash>.dump · 從 task result 讀 dumpUid
                TASK_JSON2=$(docker exec chengfu-meili wget -qO- \
                    --header="Authorization: Bearer ${MEILI_KEY}" \
                    http://127.0.0.1:7700/tasks/${TASK_UID} 2>/dev/null || echo "")
                DUMP_UID=$(echo "$TASK_JSON2" | jq -r '.details.dumpUid // empty' 2>/dev/null || echo "")
                DUMP_FILE_PATTERN="${PROJECT_DIR}/config-templates/data/meili/dumps/${DUMP_UID}.dump"
                if [[ -n "$DUMP_UID" && -f "$DUMP_FILE_PATTERN" ]]; then
                    if [[ "$GPG_AVAILABLE" == "1" ]]; then
                        MEILI_DUMP="${DAILY_DIR}/chengfu-meili-${DATE}.dump.gpg"
                        gpg --batch --yes --encrypt --recipient chengfu \
                            --output "$MEILI_DUMP" "$DUMP_FILE_PATTERN"
                        echo "  🔐 Meili dump 加密: $MEILI_DUMP(uid=$DUMP_UID)"
                    else
                        MEILI_DUMP="${DAILY_DIR}/chengfu-meili-${DATE}.dump"
                        cp "$DUMP_FILE_PATTERN" "$MEILI_DUMP"
                        echo "  ⚠ Meili 本機明文(無 GPG): $MEILI_DUMP"
                        chmod 600 "$MEILI_DUMP" 2>/dev/null || true
                    fi
                    MEILI_SIZE=$(du -h "$MEILI_DUMP" 2>/dev/null | cut -f1)
                    echo "     size: $MEILI_SIZE · task_uid=$TASK_UID"
                    find "${PROJECT_DIR}/config-templates/data/meili/dumps" \
                        -name "*.dump" -mtime +7 -delete 2>/dev/null || true
                else
                    echo "  ⚠ 無法定位 dump file(uid=$DUMP_UID)· skip"
                    MEILI_DUMP=""
                fi
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
# Codex R2.3 · 有 GPG 就 pipe 直接加密 · 不落明文
if [[ "$GPG_AVAILABLE" == "1" ]]; then
    KB_ARCHIVE="${DAILY_DIR}/chengfu-kb-${DATE}.tar.gz.gpg"
    tar czf - -C "$PROJECT_DIR" \
        knowledge-base/ \
        config-templates/librechat.yaml \
        config-templates/docker-compose.yml \
        config-templates/actions/ \
        config-templates/presets/ \
        frontend/launcher/ \
        frontend/custom/ \
        frontend/nginx/ \
        2>/dev/null \
        | gpg --batch --yes --encrypt --recipient chengfu --output "$KB_ARCHIVE"
    echo "  🔐 KB pipeline 直接加密: $KB_ARCHIVE"
else
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
    echo "  ⚠ KB 本機明文: $KB_ARCHIVE(異機不傳)"
    chmod 600 "$KB_ARCHIVE" 2>/dev/null || true
fi
KB_SIZE=$(du -h "$KB_ARCHIVE" 2>/dev/null | cut -f1)
echo "     size: $KB_SIZE"

# ------------------ Keychain 項目清單(只記 key names,不 dump 值)------------------
# 真正機密存 Keychain · 遺失則從該機 Keychain 重新匯出
KEYCHAIN_LIST="${DAILY_DIR}/chengfu-keychain-inventory-${DATE}.txt"
security dump-keychain 2>/dev/null | grep -oE 'chengfu-ai-[a-z-]+' | sort -u > "$KEYCHAIN_LIST" 2>/dev/null || true
echo "  ✅ Keychain 項目清單: $KEYCHAIN_LIST"

SIZE=$(du -h "$ARCHIVE" | cut -f1)
echo "  ✅ 備份完成: $ARCHIVE ($SIZE)"

# Codex R2.3 · 加密已在 pipeline 內完成 · 這裡只確認與告警
if [[ "$GPG_AVAILABLE" == "1" ]]; then
    echo "  ✅ 所有檔案以 pipeline 加密 · 磁碟上無明文中間檔"
else
    echo "  ⚠ 未設定 GPG key 'chengfu' · 所有備份明文 · 異機上傳會被跳過"
    echo "  ⚠ 見 docs/05-SECURITY.md 「GPG key 設定」· 異機備份強制需要"
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

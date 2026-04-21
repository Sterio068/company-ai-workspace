#!/usr/bin/env bash
# ============================================================
# 承富 AI · Meilisearch 索引還原(Codex Round 10.5 紅)
# ============================================================
# 對應 scripts/backup.sh 的 Meili dump 備份
# 用法:
#   ./scripts/restore-meili.sh <meili-dump-gz-or-gpg>
#
# 範例:
#   # 從最新本機備份還原
#   LATEST=$(ls -1t ~/chengfu-backups/daily/chengfu-meili-*.tar.gz* | head -1)
#   ./scripts/restore-meili.sh "$LATEST"
#
#   # 從異機備份還原
#   rclone copy chengfu-offsite:chengfu-backup/meili/chengfu-meili-2026-04-21.tar.gz.gpg /tmp/
#   ./scripts/restore-meili.sh /tmp/chengfu-meili-2026-04-21.tar.gz.gpg
#
# ============================================================
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "用法:$0 <path-to-meili-dump>"
    echo "檔名需為 chengfu-meili-YYYY-MM-DD.tar.gz 或 .tar.gz.gpg"
    exit 1
fi

INPUT="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MEILI_DATA="${REPO_ROOT}/config-templates/data/meili"
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

echo "[$(date +'%Y-%m-%d %H:%M:%S')] 開始 Meili 還原:$INPUT"

# 1. 若是 .gpg · 先解密
if [[ "$INPUT" == *.gpg ]]; then
    if ! command -v gpg > /dev/null; then
        echo "❌ 缺 gpg · brew install gnupg"
        exit 1
    fi
    if ! gpg --list-keys chengfu > /dev/null 2>&1; then
        echo "❌ 缺 chengfu GPG key · 無法解密"
        exit 1
    fi
    echo "  🔐 解密 .gpg..."
    DECRYPTED="${TMP_DIR}/$(basename "${INPUT%.gpg}")"
    gpg --batch --yes --decrypt --output "$DECRYPTED" "$INPUT"
    INPUT="$DECRYPTED"
fi

# 2. 解壓 tar.gz · 取出 dump
echo "  📦 解壓..."
tar -xzf "$INPUT" -C "$TMP_DIR"
DUMP_FILE=$(find "$TMP_DIR/dumps" -name "*.dump" | head -1)
if [[ -z "$DUMP_FILE" ]]; then
    echo "❌ tar 內找不到 .dump 檔"
    exit 1
fi
echo "  📄 找到 dump: $(basename "$DUMP_FILE")"

# 3. 停 Meili · 清舊 data · 放 dump · 用 --import-dump 啟動
echo "  🛑 停 Meili..."
cd "$REPO_ROOT/config-templates"
docker compose stop meilisearch

# 把 dump 放到 bind-mount 內
mkdir -p "$MEILI_DATA/dumps"
cp "$DUMP_FILE" "$MEILI_DATA/dumps/"
DUMP_BASENAME=$(basename "$DUMP_FILE")

# 備份現有 data(以防還原失敗還有後路)
BACKUP_CURRENT="${MEILI_DATA}.before-restore-$(date +%Y%m%d-%H%M%S)"
if [[ -d "$MEILI_DATA/data.ms" ]]; then
    echo "  💾 備份現有 Meili 資料到 $BACKUP_CURRENT"
    mv "$MEILI_DATA/data.ms" "$BACKUP_CURRENT/data.ms" 2>/dev/null || \
        { mkdir -p "$BACKUP_CURRENT" && mv "$MEILI_DATA/data.ms" "$BACKUP_CURRENT/"; }
fi

# 4. 用 import-dump 模式起 · 一次性還原 · 再回復正常啟動
# Meili >= 1.0 · MEILI_IMPORT_DUMP env 或 --import-dump flag
echo "  ⚙  以 import-dump 模式啟動 Meili..."
docker compose run --rm \
    -e MEILI_IMPORT_DUMP=/meili_data/dumps/${DUMP_BASENAME} \
    -e MEILI_NO_ANALYTICS=true \
    -e MEILI_MASTER_KEY="${MEILI_MASTER_KEY:-ci-placeholder-insecure-do-not-use}" \
    meilisearch

# 5. 正常啟動
echo "  ▶  恢復正常 Meili..."
docker compose up -d meilisearch
sleep 8

# 6. 驗證
MEILI_KEY=$(docker exec chengfu-accounting printenv MEILI_MASTER_KEY 2>/dev/null || echo "")
if [[ -n "$MEILI_KEY" ]]; then
    STATS=$(docker exec chengfu-meili wget -qO- \
        --header="Authorization: Bearer ${MEILI_KEY}" \
        http://localhost:7700/indexes/chengfu_knowledge/stats 2>/dev/null || echo "")
    DOCS=$(echo "$STATS" | sed -n 's/.*"numberOfDocuments":\([0-9]*\).*/\1/p')
    echo "  ✅ 還原完成 · 目前索引 $DOCS 個文件"
    if [[ "$DOCS" == "0" || -z "$DOCS" ]]; then
        echo "  ⚠ 警告:文件數為 0 · 還原可能失敗 · 可從 $BACKUP_CURRENT 回復舊資料"
        exit 1
    fi
else
    echo "  ⚠ 無 MEILI_MASTER_KEY · 無法驗證 · 請手動確認"
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Meili 還原流程完成"
echo ""
echo "驗證:curl -H \"Authorization: Bearer \$MEILI_MASTER_KEY\" http://localhost:7700/indexes"

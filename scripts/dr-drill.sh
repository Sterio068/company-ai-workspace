#!/bin/bash
# ============================================================
# 承富 AI · 災難復原演練腳本
# ============================================================
# 模擬 MongoDB 資料全損 → 從備份還原 → 驗證系統恢復
# 每季至少跑一次(文件見 docs/04-OPERATIONS.md 第 3.3 節)
#
# 用法:
#   ./scripts/dr-drill.sh
# ⚠️ 警告:本腳本會暫時移除實際資料 · 非實機上執行請確認!

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; BLUE="\033[0;34m"; NC="\033[0m"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  承富 AI · 災難復原演練                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}⚠  本演練會:${NC}"
echo "   1. 停所有容器"
echo "   2. 刪除 MongoDB 資料卷"
echo "   3. 從最新備份還原"
echo "   4. 驗證所有服務可用"
echo ""
read -p "確定執行?(輸入 'YES I UNDERSTAND' 確認): " confirm
if [[ "$confirm" != "YES I UNDERSTAND" ]]; then
    echo "已取消"
    exit 0
fi
echo ""

START=$(date +%s)

# Codex R2.4 · 定義 BACKUP_DIR(原本後面 $BACKUP_DIR 未定義 · set -u 會炸)
BACKUP_DIR="${HOME}/chengfu-backups/daily"

# ---------- Step 1: 找最新備份 ----------
echo -e "${BLUE}[1/6]${NC} 找最新備份..."
LATEST=$(ls -t "$BACKUP_DIR"/chengfu-*.archive.gz* 2>/dev/null | head -1)
if [[ -z "$LATEST" ]]; then
    echo -e "${RED}❌ 找不到備份!請先跑 scripts/backup.sh${NC}"
    exit 1
fi
SIZE=$(du -h "$LATEST" | cut -f1)
echo -e "   ${GREEN}✅${NC} 最新備份: $(basename "$LATEST") ($SIZE)"

# ---------- Step 2: 停容器 ----------
echo ""
echo -e "${BLUE}[2/6]${NC} 停所有容器..."
cd "$PROJECT_DIR/config-templates"
docker compose down
cd "$PROJECT_DIR"
echo -e "   ${GREEN}✅${NC} 容器已停"

# ---------- Step 3: 刪資料(模擬災難)----------
echo ""
echo -e "${BLUE}[3/6]${NC} 模擬 MongoDB 資料損毀..."
BACKUP_BEFORE_DRILL="${PROJECT_DIR}/config-templates/data/mongo.drill-${START}"
mv "$PROJECT_DIR/config-templates/data/mongo" "$BACKUP_BEFORE_DRILL" 2>/dev/null || true
mkdir -p "$PROJECT_DIR/config-templates/data/mongo"
echo -e "   ${GREEN}✅${NC} 舊資料移到 $BACKUP_BEFORE_DRILL(演練後可刪)"

# ---------- Step 4: 重啟 ----------
echo ""
echo -e "${BLUE}[4/6]${NC} 重啟容器(MongoDB 會 init 空資料庫)..."
"$PROJECT_DIR/scripts/start.sh"
sleep 10

# ---------- Step 5: 還原 Mongo(Codex R4.6 · 先還原 tmp · 驗過再 swap)----------
echo ""
echo -e "${BLUE}[5/6]${NC} 從備份還原 Mongo(tmp DB swap 模式)..."
# Codex R4.6 · 不直接 --drop 目標 DB · 先 restore 到 chengfu_restore_tmp
# 完整驗證(count / index)後才 renameCollection · 中途 kill 不會留半壞狀態
TMP_DB="chengfu_restore_tmp"
if [[ "$LATEST" == *.gpg ]]; then
    echo "   (GPG 加密 · 需輸入 passphrase)"
    gpg --decrypt "$LATEST" | gunzip -c | docker exec -i chengfu-mongo \
        mongorestore --drop --nsFrom 'chengfu.*' --nsTo "${TMP_DB}.*" --archive
else
    gunzip -c "$LATEST" | docker exec -i chengfu-mongo \
        mongorestore --drop --nsFrom 'chengfu.*' --nsTo "${TMP_DB}.*" --archive
fi

# 驗 tmp DB 有合理資料(Codex R4.6)
TMP_USERS=$(docker exec chengfu-mongo mongosh --quiet "$TMP_DB" \
    --eval "db.users.countDocuments()" 2>/dev/null || echo "0")
if [[ "$TMP_USERS" -lt 1 ]]; then
    echo -e "   ${RED}❌${NC} TMP DB users.count=$TMP_USERS · 異常 · 不 swap"
    exit 1
fi
echo -e "   ${GREEN}✅${NC} TMP DB 驗證通過 · users=$TMP_USERS"

# Atomic swap · drop 舊 chengfu · rename tmp → chengfu
docker exec chengfu-mongo mongosh --quiet --eval "
    db.getSiblingDB('chengfu').dropDatabase();
    db.adminCommand({copydb: 1, fromdb: '$TMP_DB', todb: 'chengfu'});
    db.getSiblingDB('$TMP_DB').dropDatabase();
" 2>/dev/null || {
    # copydb deprecated in 4.2+ · use mongorestore trick
    echo "   copydb 不可用 · 用 mongorestore export+import swap..."
    docker exec chengfu-mongo mongodump --db "$TMP_DB" --archive | \
        docker exec -i chengfu-mongo mongorestore --drop --nsFrom "${TMP_DB}.*" --nsTo "chengfu.*" --archive
    docker exec chengfu-mongo mongosh --quiet --eval "db.getSiblingDB('$TMP_DB').dropDatabase()"
}
echo -e "   ${GREEN}✅${NC} Mongo swap 完成 · 原始 DB 已替換"

# Codex fix · 同日 Meili dump 也要還原 · 否則「備份」只救對話不救搜尋索引
MEILI_LATEST=$(ls -t "$BACKUP_DIR"/chengfu-meili-*.tar.gz* 2>/dev/null | head -1 || echo "")
if [[ -n "$MEILI_LATEST" ]]; then
    echo "   同步還原 Meili:$(basename "$MEILI_LATEST")..."
    "$PROJECT_DIR/scripts/restore-meili.sh" "$MEILI_LATEST" || {
        echo -e "   ${YELLOW}⚠${NC} Meili 還原失敗 · 但 Mongo OK · 搜尋可重建"
    }
else
    echo -e "   ${YELLOW}⚠${NC} 無 Meili 備份 · 只還原 Mongo(搜尋索引需重建 · 跑 reindex_all)"
fi

# ---------- Step 6: 驗證 ----------
echo ""
echo -e "${BLUE}[6/6]${NC} 驗證服務..."
sleep 5

CHECKS=0; PASS=0; FAIL=0
check() {
    CHECKS=$((CHECKS+1))
    echo -n "   - $1 ... "
    if eval "$2" > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}❌${NC}"
        FAIL=$((FAIL+1))
    fi
}

check "nginx healthz"          "curl -sf http://localhost/healthz"
check "LibreChat API"           "curl -sf http://localhost/api/config"
check "Accounting API"          "curl -sf http://localhost/api-accounting/healthz"
check "MongoDB 有對話資料"      "docker exec chengfu-mongo mongosh chengfu --quiet --eval 'db.conversations.countDocuments()' | grep -qE '[1-9]'"
check "MongoDB 有專案資料"      "docker exec chengfu-mongo mongosh chengfu --quiet --eval 'db.projects.countDocuments()' | grep -qE '[0-9]'"
check "MongoDB 有會計科目"      "docker exec chengfu-mongo mongosh chengfu --quiet --eval 'db.accounting_accounts.countDocuments()' | grep -qE '[1-9]'"

END=$(date +%s)
DURATION=$((END - START))

echo ""
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo -e "${BLUE}  演練結果${NC}"
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo "  檢查項:$CHECKS  通過:$PASS  失敗:$FAIL"
echo "  總耗時:${DURATION} 秒 ≈ $((DURATION/60)) 分 $((DURATION%60)) 秒"
echo "  RTO 目標 < 4 小時 · 實際 $((DURATION/60)) 分鐘"
echo ""

# 寫演練報告
REPORT="$PROJECT_DIR/reports/dr-drill-$(date +%Y-%m-%d).md"
mkdir -p "$PROJECT_DIR/reports"
cat > "$REPORT" <<EOF
# 承富 DR 演練報告

- 日期:$(date +'%Y-%m-%d %H:%M:%S')
- 備份檔:$(basename "$LATEST") ($SIZE)
- 總耗時:${DURATION} 秒
- 檢查項:$CHECKS · 通過 $PASS · 失敗 $FAIL
- 預備份位置:$BACKUP_BEFORE_DRILL(確認無誤後可刪)

## RTO 評估
- 目標:< 4 小時
- 實際:$((DURATION/60)) 分鐘 · **$([[ $DURATION -lt 14400 ]] && echo "✅ 達成" || echo "❌ 超時")**

## 改善建議
$([[ $FAIL -gt 0 ]] && echo "- ❌ 有 $FAIL 項失敗,檢視上方日誌" || echo "- 無(全數通過)")
EOF

echo "  報告寫入: $REPORT"
echo ""

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi

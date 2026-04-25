#!/usr/bin/env bash
# 承富 AI · LibreChat RAG / file_search 引用驗證(Gate 2)
# ==========================================================
# 對應 EXTERNAL-AUDIT-2026-04-25.md F-24:
#   「LibreChat RAG 是知識庫核心,但本輪未實測,賣點未驗。」
#
# 用法(由 IT 人手動跑):
#   1. 準備 3-5 份去識別化的承富 PDF / DOCX 樣本,放到:
#      tests/rag-fixtures/sample-{1..5}/{filename}.{pdf,docx,xlsx}
#      (這個資料夾在 .gitignore · 不會 commit · 保 PDPA)
#   2. 編輯本 script 下方 SAMPLES 陣列,寫:
#      - 樣本檔名
#      - 正向 query(該 cite 哪段)
#      - 負向 query(問與檔案無關 · 不該編造)
#   3. 執行:bash scripts/rag-verify.sh
#   4. 結果寫到 reports/rag-verify/rag-verify-{date}.md
#
# 驗證標準:
#   ✅ 正向 query · 回答應 cite 樣本 + 引用段落
#   ❌ 負向 query · 回答若 cite 樣本 = RAG 編造 · 失敗
# ==========================================================

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost}"
FIXTURE_DIR="${REPO_ROOT}/tests/rag-fixtures"
REPORT_DIR="${REPO_ROOT}/reports/rag-verify"
TIMESTAMP="$(date +%Y-%m-%d-%H%M%S)"
REPORT_FILE="${REPORT_DIR}/rag-verify-${TIMESTAMP}.md"

mkdir -p "${REPORT_DIR}" "${FIXTURE_DIR}"

# ----------------------------------------------------------
# 樣本定義 · IT 自行修改成實際樣本
# ----------------------------------------------------------
SAMPLES_LIST="
sample-1|去識別化標書摘要.pdf|這份標書要的服務範圍?|請問 ECMA-262 規範的歷史
sample-2|去識別化結案報告.pdf|這個案子的執行 KPI 是什麼?|請問米其林餐廳評鑑流程
sample-3|去識別化品牌手冊.pdf|品牌主色號?|請問日本武士道精神
sample-4|去識別化會議紀錄.docx|會議決議的下一步?|請問太陽系有多少行星
sample-5|去識別化預算表.xlsx|本案總預算多少?|請問亞馬遜雨林面積
"

PASSED=0
FAILED=0
WARNINGS=0

# ----------------------------------------------------------
# 0. 先檢查 fixture 資料夾
# ----------------------------------------------------------
if [ ! -d "$FIXTURE_DIR" ] || [ -z "$(ls -A "$FIXTURE_DIR" 2>/dev/null)" ]; then
  cat <<'EOF'
⚠ 找不到 RAG 樣本資料

請依下列步驟準備 3-5 份去識別化承富 PDF/DOCX:

  mkdir -p tests/rag-fixtures/{sample-1,sample-2,sample-3}

  # 把 PDF 放進去(已去除任何客戶識別資訊)
  cp ~/Desktop/標書去識別.pdf tests/rag-fixtures/sample-1/

  # 編輯本 script 的 SAMPLES_LIST 對應檔名 + 正向/負向 query

  # 再跑一次
  bash scripts/rag-verify.sh

⚠ tests/rag-fixtures/ 已加入 .gitignore · 不會被 commit · 但仍請確認 PDPA。
EOF
  exit 0
fi

# ----------------------------------------------------------
# 跑 LibreChat 上傳 + 對話
# ----------------------------------------------------------
echo "═══ LibreChat RAG 驗證 ═══"
echo "BASE_URL: $BASE_URL"
echo "Fixture: $FIXTURE_DIR"
echo ""
echo "⚠ 此為「指引 + 結果記錄」script · 真正上傳 + 對話需 IT 手動在 Launcher 跑:"
echo ""

while IFS='|' read -r dir filename pos_q neg_q; do
  [ -z "$dir" ] && continue
  filepath="${FIXTURE_DIR}/${dir}/${filename}"
  if [ ! -f "$filepath" ]; then
    echo "❌ $dir · 找不到 $filepath · skip"
    FAILED=$((FAILED + 1))
    continue
  fi
  echo "─────────────────────────────────"
  echo "樣本: $dir / $filename"
  echo "  📤 1. 上傳到 Launcher 對話(任一工作區 + 拖檔)"
  echo "  ✅ 2. 正向 query: \"$pos_q\""
  echo "       → 預期回答 cite $filename 內容"
  echo "  ❌ 3. 負向 query: \"$neg_q\""
  echo "       → 回答若 cite $filename = RAG 編造 · 失敗"
  echo ""
done <<< "$SAMPLES_LIST"

# ----------------------------------------------------------
# 寫 manifest 模板讓 IT 填
# ----------------------------------------------------------
DATE_NOW="$(date +"%Y-%m-%d %H:%M:%S")"

{
  echo "# RAG / file_search 引用驗證(Gate 2)"
  echo ""
  echo "**日期**:$DATE_NOW"
  echo "**對應 finding**:F-24(External Audit 2026-04-25)"
  echo "**驗證者**:[填 IT 名字]"
  echo "**Mac mini 版本**:$(sw_vers -productVersion 2>/dev/null || echo unknown)"
  echo ""
  echo "---"
  echo ""
} > "$REPORT_FILE"

cat >> "$REPORT_FILE" <<'BODY_EOF'
## 樣本驗證表

| # | 樣本檔 | 正向 query | 正向結果 | 負向 query | 負向結果 |
|---|---|---|---|---|---|
| 1 | sample-1/(填) | (填 query) | ✅/❌ cite 段落 | (填 query) | ✅ 沒 cite / ❌ 編造 |
| 2 | sample-2/(填) | | | | |
| 3 | sample-3/(填) | | | | |
| 4 | sample-4/(填) | | | | |
| 5 | sample-5/(填) | | | | |

## 驗證標準

- **正向 query 通過**:回答必須引用該樣本內容 · 段落出處可追溯
- **負向 query 通過**:回答必須**不引用**該樣本(因問題與內容無關)
  - 若 RAG 仍 cite 該樣本 = 編造 = **fail**
  - 預期回答應為「該樣本未涉及此主題」或泛用回答

## Gate 2 通過條件

- 5 樣本中 **至少 4 個正向 + 4 個負向通過**(80%)
- 若 < 80% · 進 Phase 1 pilot 前 **必須先修 RAG 層**
  - 可能原因:
    - LibreChat file_search 未啟用 / RAG API 未設定
    - chunk size 不對
    - embedding model 不適合中文

## 附帶證據(請手動補)

- [ ] 上傳對話截圖(每樣本 1 張)
- [ ] 正向 query 回答 cite 截圖(每樣本 1 張)
- [ ] 負向 query 回答 cite 截圖(每樣本 1 張)
- [ ] /chat/api/files 上傳 log(F12 Network)

把這些放進 reports/rag-verify/(YYYY-MM-DD)/ · 同 commit。

---

**Gate 2 通過 + Gate 1 通過 = 可開 4 人 Phase 1 pilot。**
BODY_EOF

echo ""
echo "═══════════════════════════════════════════"
echo "  Manifest 模板:$REPORT_FILE"
echo "  IT 跑完 LibreChat 上傳 + 對話後 · 填入結果"
echo "═══════════════════════════════════════════"

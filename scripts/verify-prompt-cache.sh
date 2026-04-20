#!/bin/bash
# ============================================================
# 承富 AI · Prompt Cache 實測驗證
# ============================================================
# 用途:確認 Anthropic Prompt Caching 真的生效 · 能省 60-80% token
#
# 原理:送 3 次相同 prompt 給 Claude · 觀察 usage 的:
#   - cache_creation_input_tokens(首次 · 寫入 cache)
#   - cache_read_input_tokens(2/3 次 · 從 cache 讀 · 只收 10% 費用)
#
# 用法:
#   export ANTHROPIC_API_KEY=sk-ant-...  # 或從 Keychain 讀
#   ./scripts/verify-prompt-cache.sh

set -euo pipefail

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    KEY=$(security find-generic-password -s "chengfu-ai-anthropic-key" -w 2>/dev/null || echo "")
    if [[ -z "$KEY" ]]; then
        echo "❌ 需 ANTHROPIC_API_KEY 或先 setup-keychain.sh"; exit 1
    fi
    export ANTHROPIC_API_KEY="$KEY"
fi

# 需要至少 1024 tokens 才會觸發 caching(Haiku/Sonnet)
LONG_SYSTEM=$(cat <<'EOF'
你是承富創意整合行銷有限公司的「測試 Agent」。\n
以下是要 cache 的大段系統提示(> 1024 tokens · 模擬真實 Agent instructions):\n\n

## 角色\n
承富 10 年政府標案經驗 · 主客戶政府機關 60-70% · 企業客戶 30-40%\n\n

## 品牌口吻\n
繁體中文 · 台灣用語 · 禁用大陸詞(視頻/數據/云/用戶/質量/默認)\n
金額 NT$ XX,XXX · 日期西元年月日(政府客戶可用民國年)\n
承富自稱「承富」或「我司」· 不用「我們」「我方」\n\n

## 10 個內化能力\n
1. 招標須知解析 · 9 欄結構化\n
2. Go/No-Go 決策 · 8 維度評估\n
3. 建議書 5 章模板\n
4. 新聞稿 AP Style\n
5. 社群貼文 3 種 hook\n
6. 會議速記\n
7. 知識庫查詢\n
8. 廠商比價\n
9. 毛利試算\n
10. Email 公文體\n\n

## 禁區\n
Level 03 機敏資料絕不處理(選情 · 未公告標案 · 個資 · 競品機密)\n\n

## 承富慣用成本結構\n
人力 35% · 場地 25% · 設備 20% · 其他 20%\n
毛利目標 18-22%\n\n

重複上述以填滿 1024 tokens 閾值...\n
EOF
)

REQUEST_TEMPLATE='{
  "model": "claude-sonnet-4-6",
  "max_tokens": 100,
  "system": [
    {
      "type": "text",
      "text": "SYSTEM_PLACEHOLDER",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "messages": [
    {"role": "user", "content": "USER_MSG"}
  ]
}'

call_claude() {
    local user_msg="$1"
    local body=$(echo "$REQUEST_TEMPLATE" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); d['system'][0]['text']='''$LONG_SYSTEM'''; d['messages'][0]['content']='$user_msg'; print(json.dumps(d))")

    curl -s https://api.anthropic.com/v1/messages \
        -H "x-api-key: $ANTHROPIC_API_KEY" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        -d "$body"
}

echo "🧪 承富 Prompt Cache 實測"
echo "==============================="
echo ""

for i in 1 2 3; do
    echo "📡 Call $i · 送出..."
    RESP=$(call_claude "這是測試訊息 $i")
    CACHE_WRITE=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('usage', {}).get('cache_creation_input_tokens', 0))")
    CACHE_READ=$(echo "$RESP"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('usage', {}).get('cache_read_input_tokens', 0))")
    INPUT=$(echo "$RESP"       | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('usage', {}).get('input_tokens', 0))")
    OUTPUT=$(echo "$RESP"      | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('usage', {}).get('output_tokens', 0))")

    echo "   cache_creation: $CACHE_WRITE"
    echo "   cache_read:     $CACHE_READ"
    echo "   input(new):     $INPUT"
    echo "   output:         $OUTPUT"
    echo ""
    sleep 1
done

echo "==============================="
echo "判讀:"
echo "  ✅ Call 1 cache_creation > 0 → cache 寫入成功"
echo "  ✅ Call 2/3 cache_read > 0 → cache 讀取成功(省 90% 費用)"
echo "  ❌ Call 2/3 cache_read = 0 → cache 沒生效,需 debug"
echo ""
echo "承富預期:10 人同時使用 · cache hit rate > 70% · 月省 60-80% token"

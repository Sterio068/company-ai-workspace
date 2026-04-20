#!/bin/bash
# ========================================
# 承富 AI 系統 · Keychain 機密初始化
# ========================================
# 用途:將所有機密(API key / JWT secret / 加密金鑰)存入 macOS Keychain。
# 之後 scripts/start.sh 會從 Keychain 讀取並注入環境變數。
#
# 首次使用:
#   chmod +x scripts/setup-keychain.sh
#   ./scripts/setup-keychain.sh
#
# 重跑:可重複執行,會詢問是否覆寫既有項目。

set -euo pipefail

SERVICE_PREFIX="chengfu-ai"

echo "============================================"
echo "  承富 AI 系統 · Keychain 機密初始化"
echo "============================================"
echo ""
echo "本腳本會將以下機密寫入 macOS Keychain:"
echo "  - Anthropic API Key(必要)"
echo "  - OpenAI API Key(選配:STT / embedding)"
echo "  - JWT Secrets × 2(自動產生)"
echo "  - LibreChat CREDS Key/IV(自動產生)"
echo "  - Meilisearch Master Key(自動產生)"
echo "  - Email 密碼(選配:密碼重設寄信用)"
echo ""
echo "這些值之後可用以下指令查看:"
echo "  security find-generic-password -s '${SERVICE_PREFIX}-<name>' -w"
echo ""
read -p "繼續? (y/N) " confirm
[[ "$confirm" == "y" || "$confirm" == "Y" ]] || exit 0
echo ""

# ------------------ 函式 ------------------
put_secret() {
    local key="$1" value="$2"
    local full_key="${SERVICE_PREFIX}-${key}"
    # 先刪舊值(存在才刪,不存在忽略)
    security delete-generic-password -s "$full_key" -a "$USER" > /dev/null 2>&1 || true
    # 加新值
    security add-generic-password -s "$full_key" -a "$USER" -w "$value" \
        -l "ChengFu AI · ${key}" -j "承富 AI 系統機密 · 由 setup-keychain.sh 寫入"
    echo "  ✅ 已存入 Keychain: $full_key"
}

check_existing() {
    local key="$1"
    local full_key="${SERVICE_PREFIX}-${key}"
    if security find-generic-password -s "$full_key" -a "$USER" > /dev/null 2>&1; then
        read -p "  ⚠ 已存在 $full_key,覆寫? (y/N) " ow
        [[ "$ow" == "y" || "$ow" == "Y" ]] && return 0 || return 1
    fi
    return 0
}

prompt_secret() {
    local prompt="$1"
    local value
    read -s -p "  $prompt: " value; echo
    echo "$value"
}

# ------------------ 1. Anthropic API Key(必要)------------------
echo "[1/7] Anthropic API Key"
if check_existing "anthropic-key"; then
    echo "  到 https://console.anthropic.com 取得 sk-ant-... 開頭的 key"
    echo "  ⚠ 確認已升 Tier 2(D-002)"
    key=$(prompt_secret "貼入 Anthropic API Key")
    [[ -z "$key" ]] && { echo "❌ 不可為空"; exit 1; }
    put_secret "anthropic-key" "$key"
fi
echo ""

# ------------------ 2. OpenAI API Key(選配)------------------
echo "[2/7] OpenAI API Key(選配 · 用於 STT 語音轉文字 / embedding)"
read -p "  略過這個? (Y/n) " skip
if [[ "$skip" != "n" && "$skip" != "N" ]]; then
    echo "  已略過"
else
    if check_existing "openai-key"; then
        key=$(prompt_secret "貼入 OpenAI API Key")
        [[ -n "$key" ]] && put_secret "openai-key" "$key"
    fi
fi
echo ""

# ------------------ 3-5. 自動產生的安全金鑰 ------------------
echo "[3-5/7] 自動產生 JWT / CREDS 金鑰"
if check_existing "jwt-secret"; then
    put_secret "jwt-secret" "$(openssl rand -hex 32)"
fi
if check_existing "jwt-refresh-secret"; then
    put_secret "jwt-refresh-secret" "$(openssl rand -hex 32)"
fi
if check_existing "creds-key"; then
    put_secret "creds-key" "$(openssl rand -hex 32)"
fi
if check_existing "creds-iv"; then
    put_secret "creds-iv" "$(openssl rand -hex 16)"
fi
echo ""

# ------------------ 6. Meilisearch Master Key ------------------
echo "[6/7] Meilisearch Master Key"
if check_existing "meili-master-key"; then
    put_secret "meili-master-key" "$(openssl rand -hex 32)"
fi
echo ""

# ------------------ 7. Email 密碼(選配)------------------
echo "[7/7] Email 服務密碼(選配 · 用於使用者密碼重設)"
read -p "  略過這個? (Y/n) " skip
if [[ "$skip" != "n" && "$skip" != "N" ]]; then
    echo "  已略過"
else
    if check_existing "email-password"; then
        key=$(prompt_secret "貼入 Resend API Key 或 Gmail App Password")
        [[ -n "$key" ]] && put_secret "email-password" "$key"
    fi
fi
echo ""

echo "============================================"
echo "  ✅ Keychain 初始化完成"
echo "============================================"
echo ""
echo "下一步:"
echo "  cd config-templates && cp .env.example .env  # 填入非機密欄位"
echo "  cd .. && ./scripts/start.sh                   # 啟動系統"
echo ""
echo "驗證 Keychain 項目:"
echo "  security find-generic-password -s 'chengfu-ai-anthropic-key' -w"

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
echo "  - OpenAI API Key(必要:主力 AI 引擎)"
echo "  - Anthropic API Key(選配:Claude 備援 / 長文件工作流)"
echo "  - JWT Secrets × 2(自動產生)"
echo "  - LibreChat CREDS Key/IV(自動產生)"
echo "  - Meilisearch Master Key(自動產生)"
echo "  - Action Bridge Token(自動產生 · Agent 工具低權限通行權杖)"
echo "  - Email 密碼(選配:密碼重設寄信用)"
echo "  - NotebookLM Enterprise Access Token(選配:同步資料包 / 上傳檔案)"
echo ""
echo "API Key 取得網址:"
echo "  - OpenAI(主力): https://platform.openai.com/api-keys"
echo "    macOS 可直接開啟: open 'https://platform.openai.com/api-keys'"
echo "  - Anthropic(Claude 備援): https://console.anthropic.com/settings/keys"
echo "    macOS 可直接開啟: open 'https://console.anthropic.com/settings/keys'"
echo "  - Fal.ai(設計生圖選配,之後可於中控設定): https://fal.ai/dashboard/keys"
echo "    macOS 可直接開啟: open 'https://fal.ai/dashboard/keys'"
echo "  - Email · Resend(密碼重設選配): https://resend.com/api-keys"
echo "    macOS 可直接開啟: open 'https://resend.com/api-keys'"
echo "  - Email · Gmail App Password(需開兩階段驗證): https://myaccount.google.com/apppasswords"
echo "    macOS 可直接開啟: open 'https://myaccount.google.com/apppasswords'"
echo "  - NotebookLM Enterprise(選配): https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks"
echo "    Access Token 可用 gcloud 產生: gcloud auth print-access-token"
echo ""
echo "這些值之後可用以下指令查看:"
echo "  security find-generic-password -s '${SERVICE_PREFIX}-<name>' -w"
echo ""
read -p "繼續? (y/N · 也接受全形 Ｙ/ｙ) " confirm
# 接受半形 + 全形 + yes · 防中文輸入法漏接
[[ "$confirm" =~ ^[yYＹｙ]$|^yes$|^YES$ ]] || exit 0
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
        # 接受半形 + 全形 · 防中文輸入法漏接
        [[ "$ow" =~ ^[yYＹｙ]$|^yes$|^YES$ ]] && return 0 || return 1
    fi
    return 0
}

prompt_secret() {
    local prompt="$1"
    local value
    read -s -p "  $prompt: " value; echo
    echo "$value"
}

# ------------------ 1. OpenAI API Key(必要)------------------
echo "[1/8] OpenAI API Key"
if check_existing "openai-key"; then
    echo "  取得網址:https://platform.openai.com/api-keys"
    echo "  想先開瀏覽器可另開 Terminal 執行: open 'https://platform.openai.com/api-keys'"
    echo "  登入 OpenAI Platform 後建立 sk-... 開頭的 key"
    echo "  系統預設用 OpenAI · 前端可再切換到 Claude 備援"
    key=$(prompt_secret "貼入 OpenAI API Key")
    [[ -z "$key" ]] && { echo "❌ 不可為空"; exit 1; }
    put_secret "openai-key" "$key"
fi
echo ""

# ------------------ 2. Anthropic API Key(選配)------------------
echo "[2/8] Anthropic API Key(選配 · Claude 備援)"
read -p "  略過這個? (Y/n) " skip
if [[ "$skip" != "n" && "$skip" != "N" ]]; then
    echo "  已略過"
else
    if check_existing "anthropic-key"; then
        echo "  取得網址:https://console.anthropic.com/settings/keys"
        echo "  想先開瀏覽器可另開 Terminal 執行: open 'https://console.anthropic.com/settings/keys'"
        echo "  登入 Anthropic Console 後建立 sk-ant-... 開頭的 key"
        key=$(prompt_secret "貼入 Anthropic API Key")
        [[ -n "$key" ]] && put_secret "anthropic-key" "$key"
    fi
fi
echo ""

# ------------------ 3-5. 自動產生的安全金鑰 ------------------
echo "[3-5/8] 自動產生 JWT / CREDS 金鑰"
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
# R26#1 · v1.2 加 · cron 跨 service 呼叫 admin endpoint(social-scheduler / daily-digest)
if check_existing "internal-token"; then
    put_secret "internal-token" "$(openssl rand -hex 32)"
fi
if check_existing "action-bridge-token"; then
    put_secret "action-bridge-token" "$(openssl rand -hex 32)"
fi
echo ""

# ------------------ 6. Meilisearch Master Key ------------------
echo "[6/8] Meilisearch Master Key"
if check_existing "meili-master-key"; then
    put_secret "meili-master-key" "$(openssl rand -hex 32)"
fi
echo ""

# ------------------ 7. Email 密碼(選配)------------------
echo "[7/8] Email 服務密碼(選配 · 用於使用者密碼重設 / 系統通知)"
read -p "  略過這個? (Y/n) " skip
if [[ "$skip" != "n" && "$skip" != "N" ]]; then
    echo "  已略過"
else
    if check_existing "email-password"; then
        echo "  二選一(常用):"
        echo "  1) Resend API Key(推薦 · 月 100 封免費)"
        echo "     取得網址:https://resend.com/api-keys"
        echo "     macOS 可直接開啟: open 'https://resend.com/api-keys'"
        echo "  2) Gmail App Password(需 Google 帳號開啟兩階段驗證)"
        echo "     取得網址:https://myaccount.google.com/apppasswords"
        echo "     macOS 可直接開啟: open 'https://myaccount.google.com/apppasswords'"
        key=$(prompt_secret "貼入 Resend API Key(re_... 開頭)或 Gmail App Password(16 字)")
        [[ -n "$key" ]] && put_secret "email-password" "$key"
    fi
fi
echo ""

# ------------------ 8. NotebookLM Enterprise Access Token(選配)------------------
echo "[8/8] NotebookLM Enterprise Access Token(選配 · 同步資料包 / 上傳檔案)"
read -p "  略過這個? (Y/n) " skip
if [[ "$skip" != "n" && "$skip" != "N" ]]; then
    echo "  已略過"
else
    if check_existing "notebooklm-access-token"; then
        echo "  官方 API 文件:https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks"
        echo "  Source API 文件:https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources"
        echo "  若已安裝 gcloud 並登入,可另開 Terminal 執行:gcloud auth print-access-token"
        key=$(prompt_secret "貼入 NotebookLM Enterprise Access Token")
        [[ -n "$key" ]] && put_secret "notebooklm-access-token" "$key"
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
echo "  security find-generic-password -s 'chengfu-ai-openai-key' -w"

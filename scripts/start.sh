#!/bin/bash
# ========================================
# 承富 AI 系統 · 啟動腳本
# ========================================
# 1. 從 macOS Keychain 讀取機密
# 2. 注入環境變數
# 3. docker compose up -d
#
# 用法:
#   ./scripts/start.sh

set -euo pipefail

# CI 護欄 · headless 不該跑這個 script
if [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "[skip] CI 環境偵測到 · start.sh 不應在 CI 跑 · 退出 0"
    exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_PREFIX="chengfu-ai"

echo "============================================"
echo "  承富 AI 系統 · 啟動中"
echo "============================================"

# 第一次跑(Keychain 完全空)· 導去 setup
if ! security find-generic-password -s "${SERVICE_PREFIX}-jwt-secret" -w > /dev/null 2>&1; then
    echo ""
    echo "⚠️ Keychain 裡找不到 '${SERVICE_PREFIX}-*' 項目。"
    echo "   這可能是第一次部署或 Keychain 被清。"
    echo ""
    echo "   請先執行:"
    echo "     ./scripts/setup-keychain.sh"
    echo ""
    exit 1
fi

# ------------------ 前置檢查 ------------------
if ! command -v docker > /dev/null; then
    echo "❌ 未安裝 Docker,先安裝 Docker Desktop for Mac" >&2
    exit 1
fi

# 自動啟動 Docker Desktop 並等它就緒
if ! docker info > /dev/null 2>&1; then
    echo "🐳 Docker 未啟動,自動開啟 Docker Desktop..."
    open -a "Docker" 2>/dev/null || open -a "Docker Desktop" 2>/dev/null || {
        echo "❌ 找不到 Docker Desktop.app,請手動安裝/開啟" >&2
        exit 1
    }
    echo -n "   等待 daemon 就緒"
    for i in $(seq 1 60); do
        if docker info > /dev/null 2>&1; then
            echo " ✅ (${i}s)"
            break
        fi
        echo -n "."
        sleep 1
        if [[ $i -eq 60 ]]; then
            echo ""
            echo "❌ Docker 60 秒內未就緒,請手動檢查 Docker Desktop" >&2
            exit 1
        fi
    done
fi

if [[ ! -f "${PROJECT_DIR}/config-templates/.env" ]]; then
    echo "❌ ${PROJECT_DIR}/config-templates/.env 不存在" >&2
    echo "   先執行:cd config-templates && cp .env.example .env" >&2
    exit 1
fi

# ------------------ Keychain → 環境變數 ------------------
read_kc() {
    local key="$1"
    security find-generic-password -s "${SERVICE_PREFIX}-${key}" -a "$USER" -w 2>/dev/null || echo ""
}

ensure_generated_kc() {
    local key="$1"
    local value
    value="$(read_kc "$key")"
    if [[ -n "$value" ]]; then
        return 0
    fi
    value="$(openssl rand -hex 32)"
    security add-generic-password -s "${SERVICE_PREFIX}-${key}" -a "$USER" -w "$value" \
        -l "ChengFu AI · ${key}" -j "承富 AI 系統機密 · start.sh 自動產生" >/dev/null
    echo "  ✅ 已自動產生 Keychain: ${SERVICE_PREFIX}-${key}"
}

echo "[1/3] 從 Keychain 讀取機密..."

OPENAI_API_KEY="$(read_kc "openai-key")"
ANTHROPIC_API_KEY="$(read_kc "anthropic-key")"
if [[ -z "$OPENAI_API_KEY" && -z "$ANTHROPIC_API_KEY" ]]; then
    echo "❌ 至少需要設定一組 AI API Key(openai-key 或 anthropic-key)" >&2
    echo "   執行:./scripts/setup-keychain.sh" >&2
    exit 1
fi
if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "  ⚠ OpenAI Key 未設定 · 前端 OpenAI 引擎不可用"
fi
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    echo "  ⚠ Claude Key 未設定 · 前端 Claude 備援不可用"
fi
export OPENAI_API_KEY
export ANTHROPIC_API_KEY

# 選配機密(空值不出錯)
export EMAIL_PASSWORD="$(read_kc "email-password")"
export NOTEBOOKLM_ACCESS_TOKEN="$(read_kc "notebooklm-access-token")"

# 必要金鑰(產生過才有)
# R26#1 · 加 internal-token · 沒它 prod startup raise · social-scheduler cron 跑不動
# v1.70 · action-bridge-token · LibreChat Actions 只拿低權限 action token,不再持有 cron/admin token
ensure_generated_kc "action-bridge-token"
for pair in "jwt-secret:JWT_SECRET" "jwt-refresh-secret:JWT_REFRESH_SECRET" \
            "creds-key:CREDS_KEY" "creds-iv:CREDS_IV" \
            "meili-master-key:MEILI_MASTER_KEY" \
            "internal-token:ECC_INTERNAL_TOKEN" \
            "action-bridge-token:ACTION_BRIDGE_TOKEN"; do
    key="${pair%%:*}"
    var="${pair##*:}"
    val="$(read_kc "$key")"
    if [[ -z "$val" ]]; then
        echo "❌ 必要機密 '${SERVICE_PREFIX}-${key}' 未設定" >&2
        echo "   執行:./scripts/setup-keychain.sh" >&2
        exit 1
    fi
    export "$var=$val"
done

echo "  ✅ Keychain 讀取完成"

# ------------------ Launcher bundle (v1.9 perf) ------------------
# index.html 指向 /static/dist/app.<hash>.js · 若 dist/ 不存在 nginx 會 404
LAUNCHER_DIR="${PROJECT_DIR}/frontend/launcher"
DIST_APP=$(grep -oE 'dist/app\.[A-Z0-9]+\.js' "${LAUNCHER_DIR}/index.html" 2>/dev/null | head -1)
if [[ -n "$DIST_APP" ]] && [[ ! -f "${LAUNCHER_DIR}/${DIST_APP}" ]]; then
    echo "  🔨 launcher dist/ 缺 · 跑 npm build..."
    if command -v npm > /dev/null 2>&1; then
        (cd "${LAUNCHER_DIR}" && \
         { [[ -d node_modules ]] || npm install --silent; } && \
         npm run build) | tail -5
    else
        echo "  ⚠ 沒裝 npm · 跳過 bundle build · launcher 可能 404"
        echo "     請 brew install node 或手動 cd frontend/launcher && npm install && npm run build"
    fi
fi

# ------------------ 偵測網路資訊 ------------------
# 把 LAN IP / hostname / cloudflared tunnel 寫成 JSON · 給 backend
# /admin/access-urls 讀 · 同仁連線網址在 admin view 顯示
NET_FILE="${PROJECT_DIR}/config-templates/.host-network.json"
LAN_IPS_JSON=$(ifconfig 2>/dev/null \
    | awk '/^[a-z]/{iface=$1} /inet / && !/127\.0\.0\.1/ && !/inet6/ {print $2}' \
    | jq -R . | jq -s . 2>/dev/null || echo "[]")
RAW_HOST=$(hostname | tr '[:upper:]' '[:lower:]')
HOSTNAME_LOWER="${RAW_HOST%.local}.local"
TUNNEL_HOSTS_JSON="[]"
if command -v cloudflared > /dev/null 2>&1; then
    # 有裝就試讀 ~/.cloudflared/config.yml 抓 hostname(失敗就空)
    if [[ -f "$HOME/.cloudflared/config.yml" ]]; then
        TUNNEL_HOSTS_JSON=$(grep -E "^\s*-?\s*hostname:" "$HOME/.cloudflared/config.yml" 2>/dev/null \
            | awk '{print $NF}' | jq -R . | jq -s . 2>/dev/null || echo "[]")
    fi
fi
DETECTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# 全用 jq 組 JSON 防 hostname / 時間字串含特殊字元壞掉
if command -v jq > /dev/null 2>&1; then
    jq -n \
        --argjson lan_ips "${LAN_IPS_JSON}" \
        --arg hostname "${HOSTNAME_LOWER}" \
        --argjson tunnel_hostnames "${TUNNEL_HOSTS_JSON}" \
        --arg detected_at "${DETECTED_AT}" \
        '{lan_ips: $lan_ips, hostname: $hostname, tunnel_hostnames: $tunnel_hostnames, detected_at: $detected_at}' \
        > "$NET_FILE"
else
    # fallback · 沒 jq 時 best-effort(macOS 預設無 jq · 但專案 brew install jq 必備)
    cat > "$NET_FILE" <<EOF
{
  "lan_ips": ${LAN_IPS_JSON},
  "hostname": "${HOSTNAME_LOWER}",
  "tunnel_hostnames": ${TUNNEL_HOSTS_JSON},
  "detected_at": "${DETECTED_AT}"
}
EOF
fi
echo "  ✅ 網路資訊已寫入 .host-network.json"

# ------------------ 啟動容器 ------------------
echo "[2/3] 啟動 docker compose..."
cd "${PROJECT_DIR}/config-templates"

# Image stale guard(Codex R3.5 · 擴到整個 backend/accounting/ 不只 main.py)
# 改 services/*.py 或 requirements.txt 會漏 rebuild · 造成線上跑舊版
ACC_DIR="${PROJECT_DIR}/backend/accounting"
if [[ -d "$ACC_DIR" ]] && docker image inspect config-templates-accounting > /dev/null 2>&1; then
    IMG_TS=$(docker image inspect config-templates-accounting --format '{{.Created}}' 2>/dev/null)
    # 找整個目錄最近變動的檔(忽略 __pycache__ / .pytest_cache)
    NEWEST_SRC=$(find "$ACC_DIR" -type f \
        \! -path "*/__pycache__/*" \
        \! -path "*/.pytest_cache/*" \
        \! -path "*/tests/__pycache__/*" \
        -exec stat -f '%m %N' {} + 2>/dev/null \
        | sort -rn | head -1)
    SRC_MTIME=$(echo "$NEWEST_SRC" | awk '{print $1}')
    SRC_FILE=$(echo "$NEWEST_SRC" | cut -d' ' -f2-)
    IMG_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${IMG_TS%.*}" +%s 2>/dev/null || echo 0)
    if [[ -n "$SRC_MTIME" && "$SRC_MTIME" -gt "$IMG_EPOCH" ]]; then
        echo "  🔨 偵測到 $SRC_FILE 比 image 新 · rebuild 中..."
        docker compose build accounting 2>&1 | tail -3
    fi
fi

# R27#1 · 預設 PROD · 不 auto-merge override.yml(否則 ECC_ENV=development +
# ALLOW_LEGACY_AUTH_HEADERS=1 會繞過 R7/R8/R26 prod fail-closed · 任何同仁可偽造 X-User-Email)
# 本機 dev 顯式打開:CHENGFU_ENV=dev ./scripts/start.sh(自動 include override)
# 直接給 COMPOSE_FILE 也吃(advanced)
if [[ -z "${COMPOSE_FILE:-}" ]]; then
    if [[ "${CHENGFU_ENV:-prod}" == "dev" ]]; then
        export COMPOSE_FILE="docker-compose.yml:docker-compose.override.yml"
        echo "  ⚙ DEV 模式 · 含 override.yml(ECC_ENV=development · LEGACY_AUTH_HEADERS=1)"
    else
        export COMPOSE_FILE="docker-compose.yml"
        echo "  🔒 PROD 模式 · 不 merge override(prod auth fail-closed)"
    fi
fi
docker compose up -d

echo "[3/3] 等待 nginx + LibreChat 就緒..."
for i in $(seq 1 90); do
    # nginx port 80 反向代理 LibreChat(更接近實際使用路徑)
    if curl -sf http://localhost/healthz > /dev/null 2>&1 && \
       curl -sf http://localhost/api/config > /dev/null 2>&1; then
        echo "  ✅ 全部就緒(${i}s)"
        break
    fi
    if [[ $i -eq 90 ]]; then
        echo "  ⚠ 90 秒內未就緒,查 log: docker compose logs -f" >&2
        break
    fi
    sleep 1
done

# 開瀏覽器(可用 --no-open 略過)
if [[ "${1:-}" != "--no-open" ]]; then
    sleep 1
    open "http://localhost/" 2>/dev/null || true
fi

echo ""
echo "============================================"
echo "  ✅ 承富 AI 系統已啟動"
echo "============================================"
echo ""
echo "  本機入口:  http://localhost/"
echo "  API 文件:  http://localhost/api-accounting/docs"
echo "  Uptime:    http://localhost:3001"
echo ""
echo "  停止:      ./scripts/stop.sh"
echo "  日誌:      cd config-templates && docker compose logs -f"
echo ""
echo "  停止系統:     ./scripts/stop.sh"

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

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_PREFIX="chengfu-ai"

echo "============================================"
echo "  承富 AI 系統 · 啟動中"
echo "============================================"

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

echo "[1/3] 從 Keychain 讀取機密..."

ANTHROPIC_API_KEY=$(read_kc "anthropic-key")
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    echo "❌ 必要機密 'chengfu-ai-anthropic-key' 未設定" >&2
    echo "   執行:./scripts/setup-keychain.sh" >&2
    exit 1
fi
export ANTHROPIC_API_KEY

# 選配機密(空值不出錯)
export OPENAI_API_KEY="$(read_kc "openai-key")"
export EMAIL_PASSWORD="$(read_kc "email-password")"

# 必要金鑰(產生過才有)
for pair in "jwt-secret:JWT_SECRET" "jwt-refresh-secret:JWT_REFRESH_SECRET" \
            "creds-key:CREDS_KEY" "creds-iv:CREDS_IV" \
            "meili-master-key:MEILI_MASTER_KEY"; do
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

# ------------------ 啟動容器 ------------------
echo "[2/3] 啟動 docker compose..."
cd "${PROJECT_DIR}/config-templates"

# 本機開發:override.yml 會被自動 merge(docker compose 預設行為)
# 正式部署想關掉 override:COMPOSE_FILE=docker-compose.yml ./scripts/start.sh
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

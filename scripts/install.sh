#!/bin/bash
# ============================================================
# 承富 AI 系統 · Mac mini 一鍵安裝
# ============================================================
# 給承富 IT 在 Mac mini 上跑一次 · 完成 Phase 1-3 全部步驟
#
# 用法:
#   chmod +x scripts/install.sh
#   ./scripts/install.sh
#
# 流程:
#   Step 1 · 環境檢查(macOS / Docker / Homebrew / Git)
#   Step 2 · Keychain 機密設定(API key / JWT / Meili / SMTP)
#   Step 3 · .env 從 Keychain 注入
#   Step 4 · 抓 image + 建 accounting 容器
#   Step 5 · 啟動全 stack(nginx + librechat + mongo + meili + accounting + uptime)
#   Step 6 · Healthcheck loop · 等所有容器 healthy
#   Step 7 · Smoke test · 確認 8/8 通過
#   Step 8 · 印出 IT 接手手冊(URL / next steps / Sterio 聯絡)
#
# 失敗後可重跑(idempotent · 只會跳過已完成的 step)
# ============================================================

set -euo pipefail

# ---------- 顏色 ----------
RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; BLUE="\033[0;34m"
BOLD="\033[1m"; NC="\033[0m"

# ---------- 路徑 ----------
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DIR="${PROJECT_DIR}/config-templates"
ENV_FILE="${COMPOSE_DIR}/.env"
ENV_EXAMPLE="${COMPOSE_DIR}/.env.example"
SERVICE_PREFIX="chengfu-ai"

cd "$PROJECT_DIR"

# ============================================================
# 標題 + 確認
# ============================================================
clear
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                       ║${NC}"
echo -e "${BLUE}║       承富 AI 系統 v1.1 · Mac mini 一鍵安裝          ║${NC}"
echo -e "${BLUE}║                                                       ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}執行時間估算:${NC} 30-45 分鐘(視網路速度)"
echo -e "  ${BOLD}需要承富 IT 預先準備:${NC}"
echo "    • Anthropic API Key(Tier 2 預存 USD \$50)"
echo "    • Mac mini 已 mount NAS 並可讀寫"
echo "    • Mac mini 已關 sleep / 已連 UPS"
echo ""
echo -e "  ${YELLOW}失敗了?${NC} 重跑此腳本即可 · idempotent · 跳過已完成步驟"
echo -e "  ${YELLOW}遇到不明錯誤?${NC} 找 Sterio sterio068@gmail.com"
echo ""
read -p "  按 Enter 開始 / Ctrl+C 取消 . . . " _

# ============================================================
# Step 1 · 環境檢查
# ============================================================
step_start() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  Step $1${NC} · $2"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

check_pass() { echo -e "  ${GREEN}✓${NC} $1"; }
check_fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
check_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

step_start 1 "環境檢查"

# macOS
if [[ "$(uname)" != "Darwin" ]]; then
    check_fail "此腳本只能在 macOS 上跑(目前 $(uname))"
fi
MACOS_VER=$(sw_vers -productVersion)
check_pass "macOS $MACOS_VER"

# Docker
if ! command -v docker > /dev/null 2>&1; then
    check_fail "Docker 未安裝 · 請先裝 Docker Desktop for Mac · https://www.docker.com/products/docker-desktop/"
fi
DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
check_pass "Docker $DOCKER_VER"

# 啟動 Docker(若沒跑)
if ! docker info > /dev/null 2>&1; then
    check_warn "Docker 未啟動 · 開啟 Docker Desktop ..."
    open -a "Docker" 2>/dev/null || open -a "Docker Desktop" 2>/dev/null || \
        check_fail "找不到 Docker Desktop.app · 請手動安裝"
    echo "  等 Docker 就緒(最多 60 秒)..."
    for i in $(seq 1 60); do
        docker info > /dev/null 2>&1 && break
        sleep 1
    done
    docker info > /dev/null 2>&1 || check_fail "Docker 60 秒內未就緒"
fi
check_pass "Docker daemon 已就緒"

# git
command -v git > /dev/null 2>&1 || check_fail "git 未安裝 · 請跑 xcode-select --install"
check_pass "git $(git --version | awk '{print $3}')"

# python3(create-users / create-agents 用)
command -v python3 > /dev/null 2>&1 || check_fail "python3 未安裝 · 請裝 Python 3.10+"
check_pass "python3 $(python3 --version | awk '{print $2}')"

# Repo 完整
[[ -f "$COMPOSE_DIR/docker-compose.yml" ]] || check_fail "找不到 $COMPOSE_DIR/docker-compose.yml · 確認在 ChengFu repo 根目錄跑"
[[ -f "$ENV_EXAMPLE" ]] || check_fail "找不到 $ENV_EXAMPLE · repo 不完整"
check_pass "Repo 完整(找到 docker-compose.yml + .env.example)"

# 磁碟空間 · 至少 20GB
DISK_FREE_GB=$(df -g / | tail -1 | awk '{print $4}')
if [[ $DISK_FREE_GB -lt 20 ]]; then
    check_warn "磁碟剩 ${DISK_FREE_GB}GB · 建議 ≥ 20GB(image + Mongo + Meili 預留)"
else
    check_pass "磁碟剩 ${DISK_FREE_GB}GB(夠)"
fi

# 記憶體 · 至少 16GB(建議 24GB)
MEM_GB=$(($(sysctl -n hw.memsize) / 1024 / 1024 / 1024))
if [[ $MEM_GB -lt 16 ]]; then
    check_warn "RAM ${MEM_GB}GB · 建議 24GB(D-003)"
else
    check_pass "RAM ${MEM_GB}GB"
fi

# ============================================================
# Step 2 · Keychain 機密設定
# ============================================================
step_start 2 "Keychain 機密設定"

if security find-generic-password -s "${SERVICE_PREFIX}-jwt-secret" -w > /dev/null 2>&1; then
    check_pass "Keychain 已有 ${SERVICE_PREFIX}-* 項目 · 跳過"
    echo "  (若要重設 · 跑 ./scripts/setup-keychain.sh)"
else
    check_warn "Keychain 沒有承富機密 · 進入互動式設定"
    echo ""
    bash "$PROJECT_DIR/scripts/setup-keychain.sh" || check_fail "Keychain 設定失敗"
fi

# ============================================================
# Step 3 · .env 從 Keychain 注入
# ============================================================
step_start 3 "建立 .env(從 Keychain 注入機密)"

if [[ -f "$ENV_FILE" ]]; then
    check_pass ".env 已存在 · 不覆寫(若要重建 · 先 mv .env .env.bak)"
else
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    # 用 Keychain 值取代 placeholder
    get_secret() { security find-generic-password -s "${SERVICE_PREFIX}-$1" -w 2>/dev/null || echo ""; }

    JWT_SEC=$(get_secret "jwt-secret")
    JWT_REFRESH=$(get_secret "jwt-refresh-secret")
    CREDS_KEY=$(get_secret "creds-key")
    CREDS_IV=$(get_secret "creds-iv")
    MEILI_KEY=$(get_secret "meili-master-key")
    INTERNAL=$(get_secret "internal-token")

    # 用 sed 替換(BSD sed 需 -i '')
    sed -i '' "s|<GENERATE_WITH_openssl_rand_hex_32>|${MEILI_KEY}|g" "$ENV_FILE" || true

    # 在 .env 結尾加 production env(R7+R8)
    cat >> "$ENV_FILE" << EOF

# ============================================================
# 自動加入(install.sh)· 2026-04-22
# ============================================================
JWT_SECRET=${JWT_SEC}
JWT_REFRESH_SECRET=${JWT_REFRESH}
CREDS_KEY=${CREDS_KEY}
CREDS_IV=${CREDS_IV}
ECC_INTERNAL_TOKEN=${INTERNAL}
ECC_ENV=production
ALLOW_LEGACY_AUTH_HEADERS=0
EOF
    check_pass ".env 建立並注入機密(${ENV_FILE})"
fi

# Anthropic API key 必須單獨拿(從 Keychain 讀 · 不寫進 .env · start.sh 注入)
ANTHROPIC=$(security find-generic-password -s "${SERVICE_PREFIX}-anthropic-key" -w 2>/dev/null || echo "")
if [[ -z "$ANTHROPIC" || "$ANTHROPIC" == "<not set>" ]]; then
    check_fail "Anthropic API Key 未設 · 跑 ./scripts/setup-keychain.sh 補"
fi
check_pass "Anthropic API Key 已設(${ANTHROPIC:0:8}...)"

# ============================================================
# Step 4 · 抓 image + 建 accounting 容器
# ============================================================
step_start 4 "抓 image + 建 accounting 容器(5 個 image @sha256 pinned)"

cd "$COMPOSE_DIR"
echo "  pulling images(LibreChat / Mongo / Meili / nginx / uptime-kuma)..."
docker compose pull --quiet 2>&1 | tail -5 || true
check_pass "5 個 image 抓完"

echo "  building accounting image(Python 3.12 + tesseract-chi-tra + 17 deps)..."
docker compose build --quiet accounting 2>&1 | tail -3 || true
check_pass "accounting image 建完"
cd "$PROJECT_DIR"

# ============================================================
# Step 5 · 啟動全 stack
# ============================================================
step_start 5 "啟動全 stack · 6 容器"

# 用 start.sh(從 Keychain 注入 ANTHROPIC + 其他 secret)
bash "$PROJECT_DIR/scripts/start.sh" || check_fail "start.sh 啟動失敗"
check_pass "docker compose up -d 完成"

# ============================================================
# Step 6 · Healthcheck loop · 等所有容器 healthy
# ============================================================
step_start 6 "等所有容器 healthy(最多 90 秒)"

for i in $(seq 1 90); do
    UNHEALTHY=$(docker ps --filter "name=chengfu-" --format "{{.Names}} {{.Status}}" | grep -E "starting|unhealthy" || true)
    if [[ -z "$UNHEALTHY" ]]; then
        check_pass "全 6 容器 healthy(等了 ${i}s)"
        break
    fi
    if [[ $i -eq 90 ]]; then
        check_warn "90s 內仍有容器非 healthy:"
        docker ps --filter "name=chengfu-" --format "table {{.Names}}\t{{.Status}}"
        check_warn "繼續執行 · 但建議手動排查 docker logs"
    fi
    sleep 1
done

# ============================================================
# Step 7 · Smoke test
# ============================================================
step_start 7 "Smoke test(8 項基礎驗證)"

if bash "$PROJECT_DIR/scripts/smoke-test.sh" 2>&1 | tail -5 | grep -q "8 通過 / 0 失敗"; then
    check_pass "Smoke 8/0 通過"
else
    check_warn "Smoke 部分失敗 · 詳見:"
    bash "$PROJECT_DIR/scripts/smoke-test.sh" 2>&1 | tail -20
    check_warn "繼續執行 · 但建議排查"
fi

# ============================================================
# Step 8 · IT 接手手冊
# ============================================================
step_start 8 "IT 接手手冊"

# 取本機 IP(承富內網用)
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)

cat << EOF

${BOLD}╔════════════════════════════════════════════════════════════╗${NC}
${BOLD}║                                                            ║${NC}
${BOLD}║   ${GREEN}✅ 承富 AI 系統 v1.1 安裝完成${NC}                          ${BOLD}║${NC}
${BOLD}║                                                            ║${NC}
${BOLD}╚════════════════════════════════════════════════════════════╝${NC}

${BOLD}訪問入口(內網):${NC}
  Launcher 首頁     · http://${LOCAL_IP}/
  Launcher 首頁(本機)· http://localhost/
  健康檢查         · http://${LOCAL_IP}/healthz
  會計 API docs    · http://${LOCAL_IP}/api-accounting/docs(prod 預設關 · 設 ECC_DOCS_ENABLED=1 開)
  Uptime Kuma      · http://${LOCAL_IP}:3001(首次進建管理員)

${BOLD}下一步(Sterio 或 Champion 做):${NC}
  1. 建 10 個同仁帳號 · python3 scripts/create-users.py
  2. 建 10 個 Agent     · python3 scripts/create-agents.py
  3. 上傳承富知識庫     · python3 scripts/upload-knowledge-base.py
  4. 排 launchd cron    · ./scripts/install-launchd.sh
  5. 設 Cloudflare Tunnel(對外 · 見 docs/04-OPERATIONS.md)
  6. 兩場教育訓練     · 見 docs/03-TRAINING.md

${BOLD}維運:${NC}
  停止全部       · ./scripts/stop.sh
  重啟全部       · ./scripts/start.sh
  備份(每日 cron)· ./scripts/backup.sh
  災難演練       · ./scripts/dr-drill.sh
  健康檢查       · ./scripts/smoke-test.sh

${BOLD}遇到問題:${NC}
  Sterio          · sterio068@gmail.com
  完整 SOP        · DEPLOY.md
  維運手冊        · docs/04-OPERATIONS.md
  v1.1 release    · docs/RELEASE-NOTES-v1.1.md

${BOLD}容器狀態:${NC}
EOF

docker ps --filter "name=chengfu-" --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}" | column -t -s $'\t'

echo ""
echo -e "${GREEN}安裝完成。請執行上方「下一步」清單 1-6。${NC}"
echo ""

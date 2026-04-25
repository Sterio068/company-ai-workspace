#!/bin/bash
# ============================================================
# 承富智慧助理 · 一行 curl 安裝
# ============================================================
# 跳過 macOS Gatekeeper(沒下載 .app/.command)
# 直接 git clone + Keychain + start
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/Sterio068/chengfu-ai/main/installer/install.sh | bash
#
# 自訂安裝路徑(預設 ~/ChengFu):
#   curl -fsSL .../install.sh | INSTALL_DIR=/opt/chengfu bash
#
# 不互動模式(CI / 自動化):
#   curl -fsSL .../install.sh | NONINTERACTIVE=1 bash
# ============================================================

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Sterio068/chengfu-ai.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/ChengFu}"
BRANCH="${BRANCH:-main}"
NONINTERACTIVE="${NONINTERACTIVE:-0}"

# Color
R="\033[0;31m"; G="\033[0;32m"; Y="\033[1;33m"; B="\033[0;34m"; N="\033[0m"

ok()   { echo -e "  ${G}✓${N} $*"; }
warn() { echo -e "  ${Y}⚠${N} $*"; }
err()  { echo -e "  ${R}✗${N} $*" >&2; }
step() { echo ""; echo -e "${B}━━━ $* ━━━${N}"; }

trap 'err "安裝失敗 · 看上面錯誤訊息 · 詳見 https://github.com/Sterio068/chengfu-ai/blob/main/docs/06-TROUBLESHOOTING.md"' ERR

clear || true
echo ""
echo "═══════════════════════════════════════════════════"
echo "  承富智慧助理 · 一行安裝(curl-based · 跳 Gatekeeper)"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  目標路徑:$INSTALL_DIR"
echo "  Repo:    $REPO_URL"
echo "  Branch:  $BRANCH"
echo ""

if [ "$NONINTERACTIVE" != "1" ]; then
    echo "  按 Enter 開始 · 或 Ctrl+C 取消"
    read -r _
fi

# ============================================================
# 1 · 預檢
# ============================================================
step "1/6 · 環境預檢"

# git
if ! command -v git >/dev/null 2>&1; then
    err "沒裝 git"
    echo "       裝法 · xcode-select --install"
    echo "       或 · brew install git"
    exit 1
fi
ok "git $(git --version | awk '{print $3}')"

# docker binary
if ! command -v docker >/dev/null 2>&1; then
    err "沒裝 Docker Desktop"
    echo "       去 https://www.docker.com/products/docker-desktop/ 下載"
    echo "       裝完打開 Docker.app · 等右上 docker 圖示變綠"
    exit 1
fi
ok "docker $(docker --version | awk '{print $3}' | tr -d ',')"

# docker daemon
if ! docker info >/dev/null 2>&1; then
    err "Docker daemon 沒啟動"
    echo "       打開「應用程式 → Docker」"
    echo "       等右上 docker 圖示變綠燈再重跑此 script"
    exit 1
fi
ok "docker daemon · running"

# disk space
AVAIL_GB=$(df -g "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')
if [ "${AVAIL_GB:-0}" -lt 20 ]; then
    warn "$HOME 剩餘空間 ${AVAIL_GB}GB · 建議 ≥ 20GB(image + DB + log)"
fi

# RAM
TOTAL_GB=$(($(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 / 1024 / 1024))
if [ "$TOTAL_GB" -gt 0 ]; then
    if [ "$TOTAL_GB" -lt 16 ]; then
        warn "RAM ${TOTAL_GB}GB · 建議 ≥ 16GB(尖峰會吃 12GB)"
    else
        ok "RAM ${TOTAL_GB}GB"
    fi
fi

# ============================================================
# 2 · Clone / Pull repo
# ============================================================
step "2/6 · 拉程式碼到 $INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    LOCAL_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
    if [ "$LOCAL_BRANCH" != "$BRANCH" ]; then
        warn "本機 branch=$LOCAL_BRANCH · 與目標 $BRANCH 不同"
        if [ "$NONINTERACTIVE" != "1" ]; then
            read -p "  切到 $BRANCH? (y/N) " sw
            if [ "$sw" = "y" ] || [ "$sw" = "Y" ]; then
                git checkout "$BRANCH"
            fi
        fi
    fi
    BEFORE=$(git rev-parse HEAD)
    git fetch origin "$BRANCH" --quiet
    git pull --ff-only origin "$BRANCH" --quiet
    AFTER=$(git rev-parse HEAD)
    if [ "$BEFORE" != "$AFTER" ]; then
        ok "已 pull · ${BEFORE:0:7} → ${AFTER:0:7}"
    else
        ok "已是最新 · ${AFTER:0:7}"
    fi
else
    if [ -e "$INSTALL_DIR" ]; then
        err "$INSTALL_DIR 存在但不是 git repo"
        echo "       請先 mv 或刪除"
        exit 1
    fi
    echo "  · clone(--depth 100 約 30 秒)..."
    git clone --depth 100 --branch "$BRANCH" --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    SHA=$(git rev-parse --short HEAD)
    ok "clone 完成 · $SHA"
fi

# ============================================================
# 3 · Keychain
# ============================================================
step "3/6 · 設定 API keys(寫 macOS Keychain)"

SERVICE_PREFIX="chengfu-ai"
if security find-generic-password -s "${SERVICE_PREFIX}-jwt-secret" -w >/dev/null 2>&1; then
    ok "Keychain 已存在 · 跳過(若要重設跑 ./scripts/setup-keychain.sh)"
else
    if [ "$NONINTERACTIVE" = "1" ]; then
        err "NONINTERACTIVE=1 但 Keychain 沒設過 · 退出"
        echo "       手動跑 ./scripts/setup-keychain.sh 後再裝"
        exit 1
    fi
    echo "  · 跑互動式 setup(會問 OpenAI/Anthropic/email 等)"
    echo ""
    bash ./scripts/setup-keychain.sh
fi

# ============================================================
# 4 · 啟動容器
# ============================================================
step "4/6 · 啟動 Docker 容器(約 1-3 分鐘)"

bash ./scripts/start.sh 2>&1 | sed 's/^/  /' || {
    err "start.sh 失敗"
    echo "       看 docker compose -f config-templates/docker-compose.yml logs"
    exit 1
}
ok "容器啟動完成"

# ============================================================
# 5 · 健康檢查
# ============================================================
step "5/6 · 健康檢查(等 30 秒讓服務 warm up)"

sleep 30

HEALTH_OK=1
for url in \
    "http://localhost/healthz" \
    "http://localhost/api-accounting/healthz"; do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
        ok "$url · 200"
    else
        warn "$url · 沒回應(可能還在啟動)"
        HEALTH_OK=0
    fi
done

if [ "$HEALTH_OK" -eq 0 ]; then
    warn "部分 health check 沒過 · 多等 1 分鐘再開瀏覽器"
    warn "或看 docker compose ps · 檢查容器狀態"
fi

# ============================================================
# 6 · 完成
# ============================================================
step "6/6 · 完成"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ 承富智慧助理已就緒"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Web UI    · http://localhost"
echo "  程式碼    · $INSTALL_DIR"
echo "  日誌      · cd $INSTALL_DIR && docker compose -f config-templates/docker-compose.yml logs -f"
echo "  停        · cd $INSTALL_DIR && ./scripts/stop.sh"
echo "  起        · cd $INSTALL_DIR && ./scripts/start.sh"
echo ""
echo "  接著建議跑(IT):"
echo "  1. cd $INSTALL_DIR"
echo "  2. python3 scripts/create-agents.py     · 建 10 個 AI Agent"
echo "  3. python3 scripts/create-users.py      · 建 10 同仁帳號"
echo "  4. python3 scripts/upload-knowledge-base.py  · 上傳承富 PDF/DOCX"
echo "  5. ./scripts/install-launchd.sh         · 排程 cron(每日備份等)"
echo ""
echo "  完整 SOP · $INSTALL_DIR/docs/SHIP-v1.3.md"
echo ""

# 自動開瀏覽器(若 healthcheck OK)
if [ "$HEALTH_OK" -eq 1 ] && [ "$NONINTERACTIVE" != "1" ]; then
    echo "  · 5 秒後自動開瀏覽器..."
    sleep 5
    open "http://localhost" 2>/dev/null || true
fi

exit 0

#!/bin/bash
# ============================================================
# 企業 AI 工作台 · 一行 curl 安裝
# ============================================================
# 跳過 macOS Gatekeeper(沒下載 .app/.command)
# 直接 git clone + Keychain + start
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/Sterio068/company-ai-workspace/main/installer/install.sh | bash
#
# 會自動處理 Docker Desktop:
#   - 已安裝:直接啟動/等待 daemon
#   - 未安裝:互動確認後用 Homebrew 安裝 Docker Desktop
#
# 自訂安裝路徑(預設 ~/CompanyAIWorkspace):
#   curl -fsSL .../install.sh | INSTALL_DIR=/opt/company-ai bash
#
# 不互動模式(CI / 自動化):
#   curl -fsSL .../install.sh | NONINTERACTIVE=1 bash
# ============================================================

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Sterio068/company-ai-workspace.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/CompanyAIWorkspace}"
BRANCH="${BRANCH:-main}"
NONINTERACTIVE="${NONINTERACTIVE:-0}"
AUTO_INSTALL_DOCKER="${AUTO_INSTALL_DOCKER:-1}"
SERVICE_PREFIX="${SERVICE_PREFIX:-company-ai}"
LEGACY_SERVICE_PREFIX="${LEGACY_SERVICE_PREFIX:-$(printf '\143\150\145\156\147\146\165\055\141\151')}"

# Color
R="\033[0;31m"; G="\033[0;32m"; Y="\033[1;33m"; B="\033[0;34m"; N="\033[0m"

ok()   { echo -e "  ${G}✓${N} $*"; }
warn() { echo -e "  ${Y}⚠${N} $*"; }
err()  { echo -e "  ${R}✗${N} $*" >&2; }
step() { echo ""; echo -e "${B}━━━ $* ━━━${N}"; }

has_keychain_secret() {
    local key="$1"
    security find-generic-password -s "${SERVICE_PREFIX}-${key}" -w >/dev/null 2>&1 ||
        security find-generic-password -s "${LEGACY_SERVICE_PREFIX}-${key}" -w >/dev/null 2>&1
}

read_keychain_secret() {
    local key="$1"
    security find-generic-password -s "${SERVICE_PREFIX}-${key}" -w 2>/dev/null ||
        security find-generic-password -s "${LEGACY_SERVICE_PREFIX}-${key}" -w 2>/dev/null
}

put_keychain_secret() {
    local key="$1" value="$2"
    local full_key="${SERVICE_PREFIX}-${key}"
    security delete-generic-password -s "$full_key" >/dev/null 2>&1 || true
    security add-generic-password -a "$USER" -s "$full_key" -w "$value" >/dev/null
}

require_tty() {
    if [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then
        err "需要互動輸入,但目前沒有可用 TTY"
        echo "       請改用:curl -fsSL https://raw.githubusercontent.com/Sterio068/company-ai-workspace/main/installer/install.sh -o install.sh && bash install.sh"
        exit 1
    fi
}

load_homebrew() {
    if command -v brew >/dev/null 2>&1; then
        return 0
    fi
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        return 0
    fi
    if [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
        return 0
    fi
    return 1
}

confirm_yes() {
    prompt="$1"
    if [ "$NONINTERACTIVE" = "1" ]; then
        return 1
    fi
    require_tty
    printf "  %s (Y/n) " "$prompt" >/dev/tty
    IFS= read -r answer </dev/tty
    case "${answer:-Y}" in
        y|Y|yes|YES|Yes) return 0 ;;
        *) return 1 ;;
    esac
}

prompt_secret_twice() {
    local prompt="$1" first second
    while true; do
        printf "  %s: " "$prompt" >/dev/tty
        IFS= read -rs first </dev/tty
        echo "" >/dev/tty
        printf "  再輸入一次確認: " >/dev/tty
        IFS= read -rs second </dev/tty
        echo "" >/dev/tty
        if [ "$first" != "$second" ]; then
            warn "兩次密碼不一致,請重試" >/dev/tty
            continue
        fi
        if [ "${#first}" -lt 8 ]; then
            warn "密碼至少 8 字" >/dev/tty
            continue
        fi
        printf "%s" "$first"
        return 0
    done
}

ensure_admin_bootstrap_secrets() {
    if has_keychain_secret "admin-install-email" && has_keychain_secret "admin-install-password"; then
        ok "第一位管理員憑證已在 Keychain"
        return 0
    fi

    if [ -n "${INSTALL_ADMIN_EMAIL:-}" ] && [ -n "${INSTALL_ADMIN_PASSWORD:-}" ]; then
        put_keychain_secret "admin-install-email" "$INSTALL_ADMIN_EMAIL"
        put_keychain_secret "admin-install-password" "$INSTALL_ADMIN_PASSWORD"
        ok "已從環境變數寫入第一位管理員憑證"
        return 0
    fi

    if [ "$NONINTERACTIVE" = "1" ]; then
        err "NONINTERACTIVE=1 但沒有第一位管理員憑證"
        echo "       請先設 INSTALL_ADMIN_EMAIL / INSTALL_ADMIN_PASSWORD,或用互動模式安裝"
        exit 1
    fi

    require_tty
    echo "  · 設定第一次登入用的管理員帳號"
    printf "  管理員 Email [admin@company-ai.local]: " >/dev/tty
    IFS= read -r admin_email </dev/tty
    admin_email="${admin_email:-admin@company-ai.local}"
    case "$admin_email" in
        *@*) ;;
        *) err "管理員 Email 格式不正確"; exit 1 ;;
    esac
    admin_password="$(prompt_secret_twice "管理員登入密碼")"
    put_keychain_secret "admin-install-email" "$admin_email"
    put_keychain_secret "admin-install-password" "$admin_password"
    ok "第一位管理員憑證已寫入 Keychain"
}

set_env_value() {
    local file="$1" key="$2" value="$3" tmp
    tmp="${file}.tmp.$$"
    if [ -f "$file" ] && grep -q "^${key}=" "$file"; then
        awk -v k="$key" -v v="$value" '
            BEGIN { updated = 0 }
            $0 ~ "^" k "=" { print k "=" v; updated = 1; next }
            { print }
            END { if (updated == 0) print k "=" v }
        ' "$file" > "$tmp"
        mv "$tmp" "$file"
    else
        printf "%s=%s\n" "$key" "$value" >> "$file"
    fi
}

ensure_homebrew() {
    if load_homebrew; then
        ok "Homebrew $(brew --version | head -n 1 | awk '{print $2}')"
        return 0
    fi

    if ! confirm_yes "找不到 Homebrew · 要先自動安裝 Homebrew 嗎?"; then
        err "Docker Desktop 自動安裝需要 Homebrew"
        echo "       手動安裝 Homebrew:https://brew.sh"
        echo "       或手動安裝 Docker Desktop:https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    echo "  · 安裝 Homebrew(可能會要求 macOS 密碼)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty
    load_homebrew || {
        err "Homebrew 安裝後仍無法載入"
        exit 1
    }
    ok "Homebrew $(brew --version | head -n 1 | awk '{print $2}')"
}

add_docker_cli_to_path() {
    for docker_bin_dir in \
        "/Applications/Docker.app/Contents/Resources/bin" \
        "$HOME/Applications/Docker.app/Contents/Resources/bin"; do
        if [ -x "$docker_bin_dir/docker" ]; then
            PATH="$docker_bin_dir:$PATH"
            export PATH
            return 0
        fi
    done
    return 1
}

wait_for_docker_daemon() {
    max_wait="${1:-240}"
    elapsed=0
    while [ "$elapsed" -lt "$max_wait" ]; do
        add_docker_cli_to_path || true
        if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
            echo ""
            ok "docker daemon · running"
            return 0
        fi
        printf "."
        sleep 5
        elapsed=$((elapsed + 5))
    done
    echo ""
    return 1
}

ensure_docker_desktop() {
    add_docker_cli_to_path || true

    if ! command -v docker >/dev/null 2>&1; then
        if [ "$AUTO_INSTALL_DOCKER" != "1" ] || ! confirm_yes "找不到 Docker Desktop · 要自動安裝並啟動嗎?"; then
            err "沒裝 Docker Desktop"
            echo "       手動下載:https://www.docker.com/products/docker-desktop/"
            exit 1
        fi
        ensure_homebrew
        echo "  · 安裝 Docker Desktop(約 1-3 分鐘)..."
        brew install --cask docker </dev/tty
        add_docker_cli_to_path || true
    fi

    ok "docker $(docker --version | awk '{print $3}' | tr -d ',')"

    if docker info >/dev/null 2>&1; then
        ok "docker daemon · running"
        return 0
    fi

    echo "  · 啟動 Docker Desktop · 第一次開啟請按畫面提示授權..."
    open -a Docker 2>/dev/null || open "/Applications/Docker.app" 2>/dev/null || {
        err "無法開啟 Docker Desktop"
        exit 1
    }

    echo -n "  · 等 Docker daemon 啟動(最多 4 分鐘)"
    if ! wait_for_docker_daemon 240; then
        err "Docker daemon 沒啟動"
        echo "       請確認 Docker Desktop 已完成初始化,右上 docker 圖示穩定後重跑此 script"
        exit 1
    fi
}

trap 'err "安裝失敗 · 看上面錯誤訊息 · 詳見 https://github.com/Sterio068/company-ai-workspace/blob/main/docs/06-TROUBLESHOOTING.md"' ERR

clear || true
echo ""
echo "═══════════════════════════════════════════════════"
echo "  企業 AI 工作台 · 一行安裝(curl-based · 含 Docker Desktop)"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  目標路徑:$INSTALL_DIR"
echo "  Repo:    $REPO_URL"
echo "  Branch:  $BRANCH"
echo ""

if [ "$NONINTERACTIVE" != "1" ]; then
    echo "  按 Enter 開始 · 或 Ctrl+C 取消"
    require_tty
    read -r _ </dev/tty
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

ensure_docker_desktop

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
            require_tty
            printf "  切到 %s? (y/N) " "$BRANCH" >/dev/tty
            IFS= read -r sw </dev/tty
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

if has_keychain_secret "jwt-secret"; then
    ok "Keychain 已存在 · 跳過(若要重設跑 ./scripts/setup-keychain.sh)"
else
    if [ "$NONINTERACTIVE" = "1" ]; then
        err "NONINTERACTIVE=1 但 Keychain 沒設過 · 退出"
        echo "       手動跑 ./scripts/setup-keychain.sh 後再裝"
        exit 1
    fi
    echo "  · 跑互動式 setup(會問 OpenAI/Anthropic/email 等)"
    echo "  · OpenAI Key 取得網址: https://platform.openai.com/api-keys"
    echo "  · Anthropic Key 取得網址: https://console.anthropic.com/settings/keys"
    echo "  · Fal.ai Key(設計生圖選配,之後可於中控設定): https://fal.ai/dashboard/keys"
    echo ""
    SERVICE_PREFIX="$SERVICE_PREFIX" bash ./scripts/setup-keychain.sh </dev/tty
fi

ensure_admin_bootstrap_secrets

# ============================================================
# 4 · 啟動容器
# ============================================================
step "4/6 · 啟動 Docker 容器(約 1-3 分鐘)"

# 4.1 · .env 不存在 → 從 .env.example 複製(機密走 Keychain · 此檔只有預設值)
ENV_FILE="config-templates/.env"
ENV_EXAMPLE="config-templates/.env.example"
if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f "$ENV_EXAMPLE" ]; then
        err "找不到 $ENV_EXAMPLE · repo 可能不完整"
        exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    ok "建 .env(從 .env.example · 機密由 Keychain 注入)"
fi

ADMIN_EMAIL_FROM_KEYCHAIN="$(read_keychain_secret "admin-install-email" || true)"
if [ -n "$ADMIN_EMAIL_FROM_KEYCHAIN" ]; then
    set_env_value "$ENV_FILE" "ADMIN_EMAIL" "$ADMIN_EMAIL_FROM_KEYCHAIN"
    set_env_value "$ENV_FILE" "ADMIN_EMAILS" "$ADMIN_EMAIL_FROM_KEYCHAIN"
    set_env_value "$ENV_FILE" "ALLOW_REGISTRATION" "false"
    set_env_value "$ENV_FILE" "ALLOW_EMAIL_LOGIN" "true"
fi

# 4.2 · 啟容器
bash ./scripts/start.sh 2>&1 | sed 's/^/  /' || {
    err "start.sh 失敗"
    echo "       看 docker compose -f config-templates/docker-compose.yml logs"
    exit 1
}
ok "容器啟動完成"

ADMIN_EMAIL_FROM_KEYCHAIN="$(read_keychain_secret "admin-install-email" || true)"
ADMIN_PASSWORD_FROM_KEYCHAIN="$(read_keychain_secret "admin-install-password" || true)"
USER_COUNT=$(docker exec company-ai-mongo mongosh company_ai --quiet --eval 'db.users.countDocuments()' 2>/dev/null | tr -d '[:space:]' || echo "0")
if [ "${USER_COUNT:-0}" = "0" ]; then
    if [ -n "$ADMIN_EMAIL_FROM_KEYCHAIN" ] && [ -n "$ADMIN_PASSWORD_FROM_KEYCHAIN" ]; then
        echo "  · 建立第一位管理員帳號($ADMIN_EMAIL_FROM_KEYCHAIN)..."
        docker exec company-ai-librechat sh -c 'echo y | npm run create-user -- "$1" "$2" "$3" "$4"' \
            sh "$ADMIN_EMAIL_FROM_KEYCHAIN" "系統管理員" "$ADMIN_EMAIL_FROM_KEYCHAIN" "$ADMIN_PASSWORD_FROM_KEYCHAIN" \
            >/tmp/company-ai-create-admin.log 2>&1 || {
                tail -20 /tmp/company-ai-create-admin.log
                err "建立第一位管理員失敗"
                exit 1
            }
        ok "第一位管理員已建立 · $ADMIN_EMAIL_FROM_KEYCHAIN"
    else
        warn "尚未建立任何使用者,且 Keychain 沒有管理員密碼"
        warn "請重跑安裝器或設 INSTALL_ADMIN_EMAIL / INSTALL_ADMIN_PASSWORD"
    fi
fi

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
echo "  ✅ 企業 AI 工作台已就緒"
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
echo "  4. python3 scripts/upload-knowledge-base.py  · 上傳公司 PDF/DOCX"
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

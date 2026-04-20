#!/bin/bash
# ============================================================
# 承富 AI · 本機一鍵啟動
# ============================================================
# 首次本機測試用。自動處理:
#   1. 檢查 Docker 是否跑
#   2. 協助建立 Keychain 機密(若尚未設)
#   3. 從 .env.example 複製 .env(若不存在)
#   4. docker compose up
#   5. 等 LibreChat 就緒
#   6. 打開瀏覽器
#   7. 指導下一步(建帳號 + 建 Agent + 上傳知識庫)
#
# 用法:
#   chmod +x scripts/local-quickstart.sh
#   ./scripts/local-quickstart.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; BLUE="\033[0;34m"; NC="\033[0m"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    承富 AI 系統 · 本機快速啟動               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# ---------- Step 1: Docker ----------
echo -e "${BLUE}[1/6]${NC} 檢查 Docker..."
if ! command -v docker > /dev/null; then
    echo -e "${RED}❌ 未安裝 Docker Desktop${NC}"
    echo "   下載:https://www.docker.com/products/docker-desktop"
    exit 1
fi
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker Desktop 沒啟動${NC}"
    echo "   開啟 Docker Desktop 後再跑本腳本"
    exit 1
fi
echo -e "   ${GREEN}✅${NC} Docker OK"

# ---------- Step 2: Keychain ----------
echo ""
echo -e "${BLUE}[2/6]${NC} 檢查 Keychain 機密..."
if ! security find-generic-password -s "chengfu-ai-anthropic-key" -a "$USER" > /dev/null 2>&1; then
    echo -e "   ${YELLOW}⚠ Keychain 尚未設定機密${NC}"
    echo ""
    read -p "   現在執行 setup-keychain.sh? (y/N) " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${RED}❌ 需先設定 Keychain 機密才能啟動${NC}"
        echo "   手動執行:./scripts/setup-keychain.sh"
        exit 1
    fi
    bash "$PROJECT_DIR/scripts/setup-keychain.sh"
fi
echo -e "   ${GREEN}✅${NC} Keychain 已有 chengfu-ai-anthropic-key"

# ---------- Step 3: .env ----------
echo ""
echo -e "${BLUE}[3/6]${NC} 檢查 .env..."
cd "$PROJECT_DIR/config-templates"
if [ ! -f .env ]; then
    echo -e "   ${YELLOW}⚠ .env 不存在,從 .env.example 建立${NC}"
    cp .env.example .env
    # 本機用 localhost
    sed -i.bak 's|DOMAIN_CLIENT=.*|DOMAIN_CLIENT=http://localhost|' .env
    sed -i.bak 's|DOMAIN_SERVER=.*|DOMAIN_SERVER=http://localhost|' .env
    sed -i.bak 's|ADMIN_EMAIL=.*|ADMIN_EMAIL=admin@chengfu.local|' .env
    rm -f .env.bak
    echo -e "   ${GREEN}✅${NC} 已建立本機用 .env"
else
    echo -e "   ${GREEN}✅${NC} .env 已存在"
fi
cd "$PROJECT_DIR"

# ---------- Step 4: Start ----------
echo ""
echo -e "${BLUE}[4/6]${NC} 啟動 docker compose..."
bash "$PROJECT_DIR/scripts/start.sh"

# ---------- Step 5: Wait for ready ----------
echo ""
echo -e "${BLUE}[5/6]${NC} 等待服務就緒..."
for i in $(seq 1 30); do
    if curl -sf http://localhost/healthz > /dev/null 2>&1; then
        break
    fi
    printf "."
    sleep 2
done

if curl -sf http://localhost/healthz > /dev/null 2>&1; then
    echo ""
    echo -e "   ${GREEN}✅${NC} nginx 已就緒"
else
    echo -e "   ${YELLOW}⚠ nginx 可能還在啟動中,稍等 30 秒${NC}"
fi

# ---------- Step 6: Done ----------
echo ""
echo -e "${BLUE}[6/6]${NC} 打開瀏覽器..."
open http://localhost/ 2>/dev/null || true

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║    ✨ 承富 AI 已啟動                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "   前端首頁:http://localhost/"
echo "   LibreChat:http://localhost/chat"
echo ""
echo -e "${YELLOW}首次使用下一步(順序執行):${NC}"
echo ""
echo "1. 註冊管理員帳號(進 http://localhost/chat 註冊第一個)"
echo "   首位註冊者自動為 ADMIN"
echo ""
echo "2. 建立 10 個核心 Agent(主管家 + 9 專家):"
echo -e "   ${BLUE}LIBRECHAT_ADMIN_EMAIL=<你剛設的> \\\\${NC}"
echo -e "   ${BLUE}LIBRECHAT_ADMIN_PASSWORD=<密碼> \\\\${NC}"
echo -e "   ${BLUE}python3 scripts/create-agents.py --tier core${NC}"
echo ""
echo "3. 上傳全部知識庫(Company + 12 Skills + 17 Claude Skills + Matrix):"
echo -e "   ${BLUE}python3 scripts/upload-knowledge-base.py --files 'knowledge-base/company/*.md'${NC}"
echo -e "   ${BLUE}python3 scripts/upload-knowledge-base.py --files 'knowledge-base/skills/*.md'${NC}"
echo -e "   ${BLUE}python3 scripts/upload-knowledge-base.py --files 'knowledge-base/claude-skills/**/SKILL.md'${NC}"
echo -e "   ${BLUE}python3 scripts/upload-knowledge-base.py --files 'knowledge-base/SKILL-AGENT-MATRIX.md'${NC}"
echo ""
echo "4. 重新整理 Launcher 首頁 → 應該看到 10 個 Agent"
echo "5. (推薦)Seed Demo 資料(讓系統立刻有內容可看):"
echo -e "   ${BLUE}python3 scripts/seed-demo-data.py${NC}"
echo ""
echo "6. 測試主管家:Hero 輸入「幫我寫一則海洋廢棄物新聞稿」"
echo "7. 進會計頁(⌘A)確認 ✅ API 連接正常"
echo "8. 若登入 sterio@chengfu.local 為 ADMIN → 應看到 📊 管理面板(⌘M)"
echo ""
echo -e "${YELLOW}PWA 安裝(推薦):${NC}"
echo "  Chrome 位址列右側「安裝」icon → 點「安裝」· 承富 AI 變桌面 app"
echo "  iPhone Safari → 分享 → 加到主畫面"
echo ""
echo -e "${YELLOW}正式上線前:${NC}"
echo "  curl -X DELETE http://localhost/api-accounting/admin/demo-data  # 清 demo"
echo ""
echo -e "${YELLOW}常用指令:${NC}"
echo "   停止:  ./scripts/stop.sh"
echo "   重啟:  ./scripts/stop.sh && ./scripts/start.sh"
echo "   日誌:  docker compose -f config-templates/docker-compose.yml logs -f"
echo "   驗收:  ./scripts/smoke-test.sh"
echo ""

# DEPLOY.md — 承富 AI 系統 · 部署運行手冊

> **本檔取代原 `tasks/week-0` ~ `week-4-*.md`(已封存到 `tasks/archive/`)**
> 目標:Mac mini 到貨後,照本手冊一步步跑,**1-2 個工作天**內讓承富 10 位同仁全員可用。
>
> 讀者:Sterio(執行者) + 承富 IT/老闆(配合者)
>
> 執行總時程估算:
>   - 承富前置(可在 Mac mini 到貨前平行做):3-5 天
>   - 平台部署(需 Mac mini):**1 天**
>   - Agent 建立 + 知識庫灌入:**半天**
>   - 教育訓練:**2 場(各 2 小時)**
>   - 驗收簽收:**0.5 天**

---

## Phase 0 · 承富前置(Mac mini 到貨前可做)

### 0.1 採購
- [ ] Mac mini M4 **24GB / 512GB**(D-003)
- [ ] UPS 不斷電系統(APC Back-UPS 1000VA 或同等級)
- [ ] 網路線 × 1(CAT6+)

### 0.2 API 與帳號
- [ ] OpenAI API Key(主力 AI 引擎):https://platform.openai.com/api-keys
  - 驗收方式:Launcher 預設 OpenAI 可正常串流回覆
- [ ] Anthropic API Key(選配備援):https://console.anthropic.com
  - 驗收方式:前端切換 Claude 後可正常建立新對話
- [ ] 域名:承富擁有的一級網域,計畫用 `ai.<公司網域>.com`
- [ ] Cloudflare 帳號:https://dash.cloudflare.com(免費即可)
- [ ] (選配)Resend 帳號:https://resend.com 用於密碼重設寄信

### 0.3 IT 配合
- [ ] 公司網管同意 Mac mini 使用固定 IP
- [ ] 防火牆不封鎖對 `api.anthropic.com`、`cloudflare.com`、`hub.docker.com` 的出站連線
- [ ] 公司網域 DNS 可由 Sterio 或承富 IT 新增 CNAME

### 0.4 10 位同仁資料
建立 `config-templates/users.json`:
```json
[
  {"email": "sterio@chengfu.com",      "name": "Sterio",   "role": "ADMIN"},
  {"email": "pm1@chengfu.com",         "name": "王 PM",    "role": "USER"},
  {"email": "pm2@chengfu.com",         "name": "李 PM",    "role": "USER"},
  {"email": "design1@chengfu.com",     "name": "陳設計",   "role": "USER"},
  {"email": "design2@chengfu.com",     "name": "林設計",   "role": "USER"},
  {"email": "biz@chengfu.com",         "name": "黃業務",   "role": "USER"},
  {"email": "pr@chengfu.com",          "name": "吳公關",   "role": "USER"},
  {"email": "finance@chengfu.com",     "name": "張財務",   "role": "USER"},
  {"email": "hr@chengfu.com",          "name": "蔡人資",   "role": "USER"},
  {"email": "boss@chengfu.com",        "name": "老闆",     "role": "ADMIN"}
]
```
- [ ] 10 個同仁 email 已確認可收信
- [ ] 2 位 ADMIN:Sterio + 承富老闆(或指定的 AI Champion)

### 0.5 Baseline 量測(F-1)
發放工時表給 10 位同仁,請他們記錄**本週**每日花在:
- 寫建議書 / 簡報
- 寫新聞稿 / 社群貼文
- 會議紀錄整理
- 標案資料消化
- Email 溝通
- 其他文書

**目的**:3 個月後對比 ROI。沒有 baseline = 無法證明 AI 省了多少工時。

### 0.6 承富知識庫資料盤點
建立 `knowledge-base/` 目錄,依主題收集檔案(**去識別化後**):
```
knowledge-base/
├── 建議書/        (過去 3 年優質建議書 × 5-10 份)
├── 結案報告/      (過去 3 年結案報告 × 5-10 份)
├── 新聞稿/        (優質新聞稿範例 × 10-20 篇)
├── 品牌指南/      (視覺、口吻、禁用語)
├── 合約範本/      (標準合約、NDA、授權書)
├── 政府採購/      (採購法、常見評審配分方式等)
└── 公司手冊/      (同仁手冊、流程 SOP)
```

**去識別化**:真實客戶姓名 → `[客戶 A]`、電話/身份證 → `[已遮蔽]`、敏感金額 → `[NT$ 數萬等級]`。

### 0.7 合規確認(GP-1)
- [ ] 承富法務查:政府採購法對 AI 產出的規範(能不能用 AI 寫建議書、投標資料)
- [ ] 準備員工 PDPA 告知書(使用 AI 工具處理資料的同意書)
- [ ] 若處理 Level 03 機敏,列入階段二待辦(v1.0 不做)

### 0.8 Champion 與溝通
- [ ] 老闆對全員宣告:本專案目標、時程、承諾(反 AI 情緒預防)
- [ ] 指派 **2 位 AI Champion**:一位主 PM 類、一位主設計 / 業務類
- [ ] Champion 需比他人提早 3 天上手,負責首月同儕支援

---

## Phase 1 · 硬體與作業系統(需 Mac mini)

### 1.1 Mac mini 開箱(0.5 hr)
- [ ] 連接電源、螢幕、鍵盤滑鼠、有線網路
- [ ] **電源線接到 UPS 的「Battery Backup」孔**(不是「Surge Only」)
- [ ] 開機 → 跟隨 macOS 初始化精靈,建立管理員帳號 `chengfu-admin`

### 1.2 macOS 初始化(0.5 hr)
```bash
# 開 FileVault(必要)
sudo fdesetup enable

# 確認網路
ipconfig getifaddr en0   # 應顯示固定 IP

# 主機名
sudo scutil --set HostName 承富-ai
sudo scutil --set LocalHostName 承富-ai
# 確認可以 ping 到
ping 承富-ai.local
```

- [ ] FileVault 啟用,還原金鑰**印出放保險箱**
- [ ] 系統偏好 → 節能 → 關「電腦睡眠」(永不睡,伺服器模式)
- [ ] 系統偏好 → 共享 → 開「遠端登入」(僅供 Sterio ssh 進來維運)

### 1.3 安裝必要軟體
```bash
# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Docker Desktop for Mac
brew install --cask docker
open -a Docker   # 第一次要手動打開、接受授權

# cloudflared
brew install cloudflared

# 其他工具
brew install git openssl
```

- [ ] Docker Desktop 已啟動:`docker info` 無錯
- [ ] Docker Desktop 設定 → Resources → **Memory 限制 10 GB**(避免吃爆 24GB)
- [ ] `cloudflared --version` 有輸出

### 1.4 下載專案
```bash
cd ~
git clone <承富 repo URL> ChengFu
cd ChengFu
```

或若是直接拿檔案(非 git):
```bash
rsync -avz sterio@<開發機>:Workspace/ChengFu/ ~/ChengFu/
cd ~/ChengFu
```

---

## Phase 2 · 部署平台(1-2 小時)

### 2.1 機密注入 Keychain
```bash
./scripts/setup-keychain.sh
```
腳本會互動式詢問:
- OpenAI API Key(貼入 `sk-...`)
- Anthropic API Key(選配備援)
- JWT/CREDS/MEILI 金鑰(按 Enter 自動產生)
- Email 密碼(選配)

- [ ] 驗證:`security find-generic-password -s 'chengfu-ai-openai-key' -w` 能印出 key

### 2.2 非機密設定
```bash
cd config-templates
cp .env.example .env
# 編輯 .env 填入:
#   DOMAIN_CLIENT / DOMAIN_SERVER(未設 Cloudflare 前先填 http://localhost:3080)
#   ADMIN_EMAIL(填你自己)
#   EMAIL_FROM(公司寄件 email)
vim .env
cd ..
```

### 2.3 啟動系統

> **🔒 PROD vs ⚙ DEV 模式**(R27#1 強制 prod fail-closed):
>
> ```bash
> # 正式部署(預設):嚴格認證 · 不接 X-User-Email header
> ./scripts/start.sh
>
> # 本機開發:ECC_ENV=development + ALLOW_LEGACY_AUTH_HEADERS=1
> # 自動 merge docker-compose.override.yml(LibreChat port 3080 對外、debug log)
> CHENGFU_ENV=dev ./scripts/start.sh
> ```
>
> 啟動時 console 會印 `🔒 PROD 模式` 或 `⚙ DEV 模式` · 請確認後才繼續

```bash
./scripts/start.sh
```
會啟動 **5 個容器**:
- `chengfu-nginx`(port 80 · 對外唯一入口)
- `chengfu-librechat`(v0.8.4 · 內部 3080)
- `chengfu-mongo`(對話 + 會計 + 專案 + 回饋)
- `chengfu-meili`(全文檢索)
- `chengfu-accounting`(FastAPI · 會計 / 專案 / 回饋 / 管理 / L3 classifier)

預期輸出:
```
✅ Keychain 讀取完成
✅ LibreChat 已就緒
✅ 承富 AI 系統已啟動 → http://localhost
```

- [ ] 瀏覽器開 `http://localhost/` 看到**承富 Launcher 首頁**(不是 LibreChat 登入頁!)
- [ ] 如果是首次訪問會自動轉到 `/login` → LibreChat 註冊/登入頁
- [ ] 註冊第一個帳號(這會是 ADMIN · 用 `sterio@chengfu.com`)
- [ ] 登入後自動回到 `/` 看到 Launcher 5 Workspace 卡片 + Onboarding Tour

### 2.4 Smoke Test
```bash
# 基本健康檢查
curl http://localhost/healthz   # 應回 "ok"
curl http://localhost/api/config  # LibreChat API 應回 JSON
curl http://localhost/            # Launcher HTML 應有 "承富 AI" 字樣

# 完整驗收
LIBRECHAT_ADMIN_EMAIL=sterio@... \
LIBRECHAT_ADMIN_PASSWORD=<你剛設的> \
./scripts/smoke-test.sh
```
預期:**至少 5/7 通過**。備份檢查在首次部署會 fail(還沒跑過 backup.sh),可忽略。

### 2.5 前端檢查
- [ ] `/` 顯示承富 Launcher(Hero 輸入框 + 10 Agent 卡 + Projects + Skills)
- [ ] `/chat` 進 LibreChat,右上角有「← 承富首頁」按鈕
- [ ] LibreChat 介面字體比原版大、顏色用承富藍
- [ ] 進階設定(Temperature / Top P)**看不到**(ADMIN 登入後在 Settings 才出現)
- [ ] ⌘A 進會計頁,顯示「✅ 會計 API 已連接」(而非 ❌ 離線)
- [ ] ADMIN 登入能看到側邊「📊 管理面板」(非 ADMIN 隱藏)
- [ ] 新增專案 → 登出再登入 → 專案還在(確認寫進 MongoDB,不是 localStorage)

### 2.6 會計模組檢查
```bash
curl http://localhost/api-accounting/healthz          # 應回 {"status":"ok",...}
curl http://localhost/api-accounting/accounts | head   # 應看到台灣預設 25 個科目
curl http://localhost/api-accounting/admin/dashboard   # 應看到總覽
curl -X POST http://localhost/api-accounting/safety/classify \
    -H "Content-Type: application/json" \
    -d '{"text":"選情分析怎麼做"}'                      # 應回 level: "03"
```

### 2.7 跑 FastAPI 測試(選配 · 驗證會計模組邏輯)
```bash
cd backend/accounting
pip install pytest mongomock httpx
pytest test_main.py -v
# 應看到 14 項全過
```

---

## Phase 3 · Agent 與資料(半天)

### 3.1 批次建立 10 Agent(主管家 + 9 專家)
```bash
# 乾跑確認(應看到 10 個 preset)
python3 scripts/create-agents.py --dry-run --tier core

# 正式建立
LIBRECHAT_ADMIN_EMAIL=sterio@... \
LIBRECHAT_ADMIN_PASSWORD=<密碼> \
python3 scripts/create-agents.py --tier core
```

預期輸出:
```
✅ ✨ 主管家 · 主管家          agent_id=abc...
✅ 🎯 投標 · 投標顧問          agent_id=def...
✅ 🎪 活動 · 活動規劃師        agent_id=...
✅ 🎨 設計 · 設計夥伴          agent_id=...
✅ 📣 公關 · 公關寫手          agent_id=...
✅ 🎙️ 會議 · 會議速記          agent_id=...
✅ 📚 知識 · 知識庫查詢        agent_id=...
✅ 💰 財務 · 財務試算          agent_id=...
✅ ⚖️ 法務 · 合約法務          agent_id=...
✅ 📊 營運 · 結案營運          agent_id=...
```

- [ ] 登入 LibreChat → Agents 頁面,確認 29 個 Agent 都在、**按 emoji 分 5 群**

#### 3.1.1 接 Action(v1.51 · 讓 AI 真的會用工具)

```bash
# 內部會計 token(從 docker container 抓現成的)
export ECC_INTERNAL_TOKEN=$(docker exec chengfu-accounting printenv ECC_INTERNAL_TOKEN)

# (可選) 提供 Fal.ai key 才會掛生圖
export FAL_KEY=fal-...

# 一鍵接(idempotent · 重跑不疊)
LIBRECHAT_ADMIN_EMAIL=sterio@... LIBRECHAT_ADMIN_PASSWORD=<密碼> \
python3 scripts/wire-actions.py
```

預期:`✓ 8` 接上(若有 FAL_KEY 是 12)。對應:
- 🎯 投標顧問 + ✨ 主管家 → PCC 標案查詢
- 💰 財務試算 + ✨ 主管家 → 內建會計 API
- 🎨 設計夥伴 + ✨ 主管家 → Fal.ai 生圖(需 FAL_KEY)

- [ ] 試用一個 Agent(如「招標須知解析器」)送個訊息,確認回應正常

### 3.2 填入 librechat.yaml 的 modelSpecs
把 create-agents.py 輸出的 `agent_id` 填入 `config-templates/librechat.yaml`:
```yaml
modelSpecs:
  list:
    - name: "tender-analyzer"
      label: "🎯 投標 · 招標須知解析器"
      default: false
      preset:
        endpoint: "agents"
        agent_id: "agent_abc123..."     # ← 從 create-agents.py 輸出複製
    # ... 其他 28 個
```

編輯完重啟容器讓變更生效:
```bash
./scripts/stop.sh && ./scripts/start.sh
```

### 3.3 上傳全部知識庫(Company Memory + Skills + Claude Skills + Matrix)
```bash
LIBRECHAT_ADMIN_EMAIL=sterio@... \
LIBRECHAT_ADMIN_PASSWORD=<密碼> \
python3 scripts/upload-knowledge-base.py --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --files 'knowledge-base/skills/*.md'
python3 scripts/upload-knowledge-base.py --files 'knowledge-base/claude-skills/**/SKILL.md'
python3 scripts/upload-knowledge-base.py --files 'knowledge-base/SKILL-AGENT-MATRIX.md'
# 選配:openclaw 參考(較大,可延)
python3 scripts/upload-knowledge-base.py --files 'knowledge-base/openclaw-reference/*.md'
```

- [ ] 測試:登入 LibreChat,開「📚 知識庫查詢」Agent
- [ ] 問:「承富做過環保類的案嗎?預算結構?」應引用過往檔案
- [ ] 開「✨ 主管家」,問「幫我寫建議書」→ 應主動查 SKILL-AGENT-MATRIX 並分派

### 3.4 批次建立 10 同仁帳號
```bash
LIBRECHAT_ADMIN_EMAIL=sterio@... \
LIBRECHAT_ADMIN_PASSWORD=<密碼> \
python3 scripts/create-users.py
```

- [ ] 密碼表在 `scripts/passwords.txt`(權限 600)
- [ ] 分發方式:一對一面交或加密 email(**不要**公開 Slack)
- [ ] 分發完畢:`shred -u scripts/passwords.txt`

---

## Phase 4 · 對外連線與安全(0.5 天)

### 4.1 Cloudflare Tunnel
```bash
# 登入 Cloudflare
cloudflared tunnel login

# 建立 tunnel
cloudflared tunnel create chengfu-ai

# 設 DNS(ai.<公司域名>.com → tunnel)
cloudflared tunnel route dns chengfu-ai ai.<公司域名>.com

# 建立 config(注意:port 改為 80 · nginx,不是 3080)
cat > ~/.cloudflared/config.yml <<EOF
tunnel: chengfu-ai
credentials-file: /Users/chengfu-admin/.cloudflared/<tunnel-UUID>.json
ingress:
  - hostname: ai.<公司域名>.com
    service: http://localhost:80
  - service: http_status:404
EOF

# 設為 macOS LaunchAgent 開機自啟
sudo cloudflared service install
```

### 4.2 Cloudflare Access Policy(S-2 · 必要)
到 Cloudflare Zero Trust dashboard:
- [ ] Access → Applications → Add application → Self-hosted
- [ ] Domain: `ai.<公司域名>.com`
- [ ] Policy:Allow from Emails(10 個同仁 email)
- [ ] **2FA 必開**:Authentication methods 啟用 One-time PIN 或 Google Authenticator
- [ ] (選配)Session duration 設 24 小時

### 4.3 回到 .env 更新 DOMAIN
```bash
cd config-templates
# 把 DOMAIN_CLIENT 和 DOMAIN_SERVER 從 localhost 改為 https://ai.<公司域名>.com
vim .env
cd ..
./scripts/stop.sh && ./scripts/start.sh
```

- [ ] 驗證:從**家裡或手機**瀏覽 `https://ai.<公司域名>.com` 能登入

### 4.4 備份 + 採購網監測 cron
```bash
# 登入 crontab
EDITOR=nano crontab -e
```
加入:
```
# 承富 AI · 每日 02:00 備份(MongoDB + knowledge-base + config)
0 2 * * * /Users/chengfu-admin/ChengFu/scripts/backup.sh >> /Users/chengfu-admin/Library/Logs/chengfu-backup.log 2>&1

# 承富 AI · 每日 09:00 查政府採購網新標案
0 9 * * * cd /Users/chengfu-admin/ChengFu && TENDER_SLACK_WEBHOOK="https://hooks.slack.com/..." /usr/bin/python3 scripts/tender-monitor.py >> /Users/chengfu-admin/Library/Logs/chengfu-tender.log 2>&1

# 承富 AI · 每月 1 日 08:00 產月度報告並寄 email(需 SMTP 設定)
0 8 1 * * curl -s -X POST http://localhost/api-accounting/admin/send-monthly-report

# 承富 AI · 週一至週五早上 8:30 寄 Daily Digest(需 ANTHROPIC_API_KEY + SMTP)
30 8 * * 1-5 cd /Users/chengfu-admin/ChengFu && /usr/bin/python3 scripts/daily-digest.py >> /Users/chengfu-admin/Library/Logs/chengfu-digest.log 2>&1

# 承富 AI · 每月 1 日 02:30 分析 Skill 演化建議(累積夠資料時啟用)
30 2 1 * * cd /Users/chengfu-admin/ChengFu && /usr/bin/python3 scripts/propose-skill.py --days 30 >> /Users/chengfu-admin/Library/Logs/chengfu-skill-evolve.log 2>&1
```

### 4.5 設定 Uptime Kuma
1. 開 `http://localhost:3001`
2. 建第一個管理員帳號
3. 新增監控項目:
   - `http://localhost/healthz`(每分鐘)
   - `http://localhost/api/config`(LibreChat)
   - `http://localhost/api-accounting/healthz`
4. 通知設定:Slack webhook / Email

### 4.6 DR 演練(每季一次)
```bash
./scripts/dr-drill.sh
```
產出報告到 `reports/dr-drill-YYYY-MM-DD.md`,目標 RTO < 4 小時。

- [ ] 手動測一次:`./scripts/backup.sh`,確認 `~/chengfu-backups/daily/` 有 `.gz` 檔
- [ ] (選配)設 GPG 加密備份 → 見 `docs/05-SECURITY.md` 第 6 節

---

## Phase 5 · 教育訓練(2 場 × 2 小時)

詳見 `docs/03-TRAINING.md`。

### 5.1 第 1 場 · 全員 Onboarding
- 登入流程 + 密碼修改
- 5 Workspace 介紹 + 最常用的 3 個 Agent
- 資料分級 SOP(Level 01/02/03 海報牆上)
- 實戰 1:用「新聞稿生成器」產出一篇發表過的新聞稿對照

### 5.2 第 2 場 · 進階(分層 · C-1)
**A 組(數位熟練組 · 5 人)**:
- MCP / Google Drive 整合
- 自訂 prompt、Preset 保存
- slash command(`/know` `/email` `/vendor`)

**B 組(資深同仁組 · 5 人)**:
- 1:1 配對 Champion 陪練
- 用他們自己的真實任務(例:最近一份建議書)練習
- 不趕、多鼓勵

### 5.3 驗收
每人產出**至少 1 份真實工作成果**,簽名在 `docs/ACCEPTANCE.md` 上。

---

## Phase 6 · 交付簽收

### 6.1 驗收清單對照
對照 `CLAUDE.md` 第 3 節 DoD,逐項確認 ✅。

### 6.2 交付物清單(給承富)
- [ ] 本專案 `docs/` 目錄完整 PDF(交給老闆)
- [ ] Keychain 備份(Sterio 保存 1 份、放公司保險箱 1 份)
- [ ] FileVault 還原金鑰紙本
- [ ] Cloudflare 帳號擁有權(Sterio 協助交接給承富指定管理員)
- [ ] 備份恢復演練:`./scripts/backup.sh` 產出備份 → 模擬還原測試

### 6.3 簽收單
`docs/ACCEPTANCE.md` 承富老闆簽名 + 日期。

---

## 遇到問題怎麼辦

| 狀況 | 翻到哪裡 |
|---|---|
| Docker 跑不起來 | `docs/06-TROUBLESHOOTING.md` 第 1 節 |
| LibreChat 開不了 | `docs/06-TROUBLESHOOTING.md` 第 2 節 |
| 備份失敗、資料救援 | `docs/04-OPERATIONS.md` RTO/RPO 章節 |
| 機密外洩、帳號被盜 | `docs/05-SECURITY.md` 人員異動 SOP |
| MCP Google Drive 串接 | `docs/08-MCP-INTEGRATION.md` |
| Agent 品質不如預期 | `docs/06-TROUBLESHOOTING.md` 第 5 節 |
| LibreChat 升級 | `docs/04-OPERATIONS.md` 每季升級 SOP |

---

## 後續優化(v1.1 · 非本次交付範圍)

- Workspace UI 客製(方案 B · JS/CSS 注入,⌘K 指令面板)
- Gmail / Calendar MCP 整合
- 月用量報告自動寄送
- 階段二:Ollama + Qwen 2.5 本地模型(處理 Level 03)
- 深/淺色主題切換

# 🤖 AI Handoff · 承富 AI 系統

> 給接手開發的 AI 看的單一入口。
> 讀完這份 + `docs/DECISIONS.md` 即可開始改 code。
> 最後更新 · 2026-04-25 · Phase 1 現場驗收包完成 · pre-pilot 自檢 8/8 通過 · release gate 13/13 通過

---

## 60 秒上手

**這是什麼**:給台灣公關行銷公司「承富」(10 人)用的 AI 協作平台 · 本地部署在他們辦公室的 Mac mini · LibreChat + 自製 launcher + FastAPI 會計後端組合 · 不上雲。

**現在狀態**:v1.3.0 正式 release 候選版 · 外部 AI 審計後已補強 UI/UX 高槓桿項目。2026-04-25 最新證據:`./scripts/release-verify.sh http://localhost` 13 passed / 0 failed,backend `246 passed / 13 skipped`,Playwright desktop+mobile `35 passed / 3 skipped`,smoke `15 passed / 0 failed`,LibreChat route smoke `13 pass / 0 fail`,最新 DMG SHA-256 `d85f5194b104d9f2ca4872c391350a762d8dc6bdf30f8efd1bf4a51056135ffa`。`./scripts/pre-pilot-verify.sh` 已跑過 8 passed / 0 failed,manifest 在 `reports/pre-pilot/pre-pilot-readiness-2026-04-25-150444.md`。外部審計原判定為 `770/1000 · 可帶條件交付`,目前已把可在開發機完成的項目補到位;乾淨 Mac/VM 安裝驗收、LibreChat 原生 RAG/file_search 引用實測、4 人 Phase 1 pilot 仍是現場 Gate,不要在開發機上偽裝完成。

**下一步一句話**:照 `docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md` 執行 Gate 1-4:乾淨 Mac/VM 安裝 → LibreChat RAG/file_search → 老闆 + Champion + 2 PM pilot → Day +1 Go/No-Go。

**核心使用者**:
- 老闆 1 人(ADMIN · 看儀表板 / 管帳號 / 改 agent prompt)
- 同仁 9 人(USER · 用 10 個 agent / 自己的對話資料)

**核心功能**:
- 5 工作區(投標 · 活動 · 設計 · 公關 · 營運)各對應 1-N agent
- 10 核心 Agent 是 production 使用者入口；legacy 29 Agent 保留作為 prompt/能力拆解參考
- 4 個 v1.2 功能(會議速記 · 媒體 CRM · 社群排程 · 場勘 PWA)
- 內建會計模組(台灣統編發票 · 月報 · 預算)
- 標案 cron(每日抓政府電子採購網)
- v1.3 同仁管理 UI(admin 在前端建帳號 + 7 preset 頭銜 + 28 權限勾選)
- vNext Round 2 已讓 accounting / social / site survey 等高風險入口開始吃 `chengfu_permissions`;停用帳號會被全域擋下。
- Project / handoff / workflow draft / meeting push / site survey push 已有 owner/admin 邊界,避免知道 project_id 就能跨專案寫入。
- 半自動 workflow 仍預設 draft-first,但可把主管家草稿寫入 project handoff 的 `workflow_draft` 並留下 audit log。
- Chat 回答已可一鍵存回 project handoff 或列成下一步;從工作包「AI 判斷」建議卡開出的對話會自動帶回寫上下文,回覆完成後可直接回寫該工作包。Project 支援 `collaborators` / `next_owner`,協作者可接手 handoff,但刪除仍限 owner/admin。
- Workflow 採用 / 拒絕會寫入 `workflow_adoptions`,後續可接老闆月報、採用率與 Level 4 Learning。

---

## 技術棧 · 不可隨意換

| 層 | 選擇 | 為何 |
|---|---|---|
| 硬體 | Mac mini M4 (24GB/512GB) | 老闆要本地部署 |
| 容器化 | Docker Desktop for Mac | LibreChat 官方推薦 |
| AI 對話框架 | **LibreChat v0.8.4** | 開源 + 多 provider + 原生 Agent · pin v0.8.4 |
| 主力模型 | OpenAI GPT-5.4 / GPT-5.4-mini / GPT-5.4-nano | 預設主力 · 前端可切換 Claude 備援 |
| 後端 | FastAPI + Python 3.12 | 會計 + 標案 + 業務邏輯 |
| DB | MongoDB 7 | LibreChat 用 + 我們的 collections 共享 |
| 全文索引 | Meilisearch v1.12 | 知識庫 + 對話歷史 |
| 前端 | **純 ES module · 無 React/Vue** | LibreChat 提供對話介面 · launcher 是 vanilla JS |
| 反向代理 | nginx 1.27-alpine | 一個入口 80 · sub_filter 注入 |
| 遠端 | Cloudflare Tunnel | 免費 + 免開 port + 加密 |
| 監控 | Uptime Kuma | 簡單 · 老闆看得懂 |

**不要**換成 React / Next.js / Tailwind 等。launcher 設計就是「vanilla JS + 漸進增強」· 為了讓承富 IT 未來改也不會因為 build chain 卡住。

---

## Repo 結構 · 哪裡放什麼

```
ChengFu/
├── CLAUDE.md                    ← 專案主控 · 給 Claude Code 讀的
├── AI-HANDOFF.md                ← 你正在讀
├── README.md                    ← 給承富老闆看的概覽
├── DEPLOY.md                    ← Mac mini 部署 6 phase 手冊
├── ARCHITECTURE.md              ← 技術架構詳解(3+1 容器)
├── SYSTEM-DESIGN.md             ← UX 設計語言 + macOS 原則 + 5 工作區
│
├── docs/
│   ├── DECISIONS.md             ← ⭐ 最新已決議 + 待決議(衝突時以此為準)
│   ├── 03-TRAINING.md           ← 教育訓練教案
│   ├── 04-OPERATIONS.md         ← Day-2 維運(備份 / RTO / 升級)
│   ├── 05-SECURITY.md           ← Keychain / PDPA / 人員異動
│   ├── 06-TROUBLESHOOTING.md    ← 常見問題集
│   ├── EXTERNAL-AUDIT-2026-04-25.md  ← 外部 AI 審計存檔(770/1000 · 可帶條件交付)
│   ├── PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md  ← ⭐ 交付前現場 Gate 0-4 驗收包
│   └── ... (37 份 · 大多是歷史決策 + spec)
│
├── backend/accounting/          ← FastAPI 後端
│   ├── main.py                  ← app entrypoint(580 行 · 拆分中)
│   ├── routers/
│   │   ├── _deps.py             ← Depends 工具(require_user_dep / require_admin_dep)
│   │   ├── admin/               ← admin endpoint(2026-04 從 admin.py 拆)
│   │   │   ├── __init__.py      ← admin router root + audit-log + monthly-report
│   │   │   ├── dashboard.py     ← /admin/dashboard
│   │   │   └── user_mgmt.py     ← /admin/users CRUD(v1.3 新)
│   │   ├── safety.py            ← /safety/classify + /safety/pii-detect + /l3-preflight
│   │   ├── knowledge.py         ← /knowledge/* + /admin/sources/*
│   │   ├── memory.py            ← /memory/transcribe(會議速記)
│   │   ├── social.py            ← /social/posts(排程)
│   │   ├── social_oauth.py      ← /social/oauth/*(v1.3 A5)
│   │   ├── media.py             ← /media/contacts(媒體 CRM)
│   │   ├── site_survey.py       ← /site-survey(場勘)
│   │   └── ...
│   ├── services/
│   │   ├── admin_metrics.py     ← cost / budget / quota 計算
│   │   ├── librechat_admin.py   ← LibreChat 跨 collection PDPA delete
│   │   ├── oauth_tokens.py      ← AES-GCM token 加密(v1.3 A5)
│   │   └── ...
│   ├── test_main.py             ← pytest 主測試(124 unit · mongomock)
│   └── tests/                   ← 子測試集
│       ├── conftest.py
│       ├── integration/         ← 真 Mongo 整合測試(v1.3 C1)
│       └── ...
│
├── frontend/launcher/           ← 自製首頁 + 5 工作區 + admin 面板
│   ├── index.html               ← 主入口 · 含 5 view + sidebar + chat pane
│   ├── launcher.css             ← 設計 tokens + 全部樣式
│   ├── app.js                   ← 主控(routing + agents + projects)
│   ├── manifest.json            ← PWA(iPhone 場勘用)
│   ├── modules/                 ← ES modules(28 個)
│   │   ├── README.md            ← ⭐ 每個 module 用途清單
│   │   ├── auth.js              ← LibreChat cookie 驗證
│   │   ├── chat.js              ← 對話 SSE 串流(/api/agents/chat)
│   │   ├── modal.js             ← Modal v2(role=dialog + focus trap)
│   │   ├── toast.js             ← Toast 通知(networkError / operationError helper)
│   │   ├── meeting.js / site_survey.js / social.js / media.js
│   │   ├── crm.js / tenders.js / workflows.js
│   │   ├── knowledge.js         ← 知識庫管理 + 搜
│   │   ├── user_mgmt.js         ← v1.3 新 · admin 建同仁
│   │   ├── shortcuts.js         ← ⌘K + 27 鍵盤捷徑
│   │   └── mobile.js            ← 行動端 bottom nav
│   ├── user-guide/              ← ⭐ 13 份中文使用者手冊(可 sidebar 點)
│   │   ├── quickstart-v1.3.md
│   │   ├── mobile-ios.md
│   │   ├── error-codes.md
│   │   ├── admin-permissions.md  ← 3 層權限模型(看這份理解 RBAC)
│   │   └── ...
│   ├── custom/                  ← 注入 LibreChat 頁面的 css/js
│   ├── nginx/                   ← nginx config(default.conf + chengfu-proxy.conf)
│   ├── modules/state/           ← localStorage wrapper
│   └── dist/                    ← esbuild 輸出(infra ready · cutover v1.4)
│
├── config-templates/
│   ├── docker-compose.yml       ← ⭐ stack 定義 · accounting 含全 hardening env
│   ├── docker-compose.override.yml  ← 本機開發
│   ├── docker-compose.sandbox.yml   ← CI 用
│   ├── librechat.yaml           ← LibreChat 設定 · pin v0.8.4
│   ├── .env.example             ← env template
│   ├── presets/                 ← 10 Agent JSON(00-09)
│   └── actions/                 ← Fal.ai / PCC / accounting OpenAPI schemas
│
├── scripts/
│   ├── start.sh                 ← ⭐ 從 macOS Keychain 注入 secrets + docker compose up
│   ├── stop.sh
│   ├── setup-keychain.sh        ← 首次 · 把 API keys 寫進 Keychain
│   ├── backup.sh                ← cron · MongoDB 備份
│   ├── create-agents.py         ← 批次建 10 Agent via LibreChat API
│   ├── create-users.py          ← 批次建同仁(v1.3 後改用 ⌘U UI · 但 script 仍可用)
│   ├── upload-knowledge-base.py ← 知識庫上傳
│   ├── seed-demo-data.py        ← demo 資料
│   ├── smoke-test.sh            ← 部署後驗收
│   ├── smoke-librechat.sh       ← LibreChat route / config 驗收
│   ├── release-verify.sh        ← ⭐ 正式交付版總驗收(13 gate)
│   ├── pre-pilot-verify.sh      ← ⭐ Phase 1 pilot 前交付包自檢(不讀取 secrets)
│   └── tender-monitor.py        ← cron · 每日抓政府標案
│
├── installer/                   ← Mac 原生安裝精靈(.app + .dmg)
│   ├── ChengFu-AI-Installer.applescript  ← ⭐ 7 步精靈邏輯
│   ├── build.sh                 ← osacompile + hdiutil 包 DMG
│   └── dist/                    ← 產物(約 11M DMG · 內含 source 快照)
│
├── knowledge-base/              ← RAG 來源
│   ├── company/                 ← 品牌 / 禁用詞 / 稱謂
│   ├── skills/                  ← 12 個自製 skills
│   ├── claude-skills/           ← Anthropic 官方 17 skills(Claude 備援 / 技能參考)
│   ├── openclaw-reference/      ← 參考用
│   └── SKILL-AGENT-MATRIX.md    ← skill ↔ agent 路由表
│
├── chrome-extension/            ← 同仁從任何網頁右鍵送內容到承富 AI(v1.3)
│
└── tests/                       ← 跨層級的 E2E + integration
    └── e2e/                     ← Playwright(CI 跑 sandbox)
```

### 最新交付報告位置

| 報告 | 狀態 |
|---|---|
| `reports/final-delivery-audit-2026-04-25.md` | 正式交付版本機 release gate 通過,列出現場剩餘 Gate |
| `reports/release/release-manifest-2026-04-25-143407.md` | `release-verify.sh` 13 passed / 0 failed |
| `reports/pre-pilot/pre-pilot-readiness-2026-04-25-150444.md` | `pre-pilot-verify.sh` 8 passed / 0 failed |

---

## 開發 cycle · 4 步

### 1. 跑起來

```bash
# Mac 本機開發(假設已 clone + Docker Desktop 已開)
cd config-templates
docker compose up -d
# 訪問 http://localhost/
```

### 2. 改 code

- **後端**:改 `backend/accounting/**` · 需 rebuild container
  ```bash
  cd config-templates
  docker compose build accounting && docker compose up -d accounting
  ```
- **前端**:改 `frontend/launcher/**` · nginx mount volume · 即時生效
  - 改 `index.html` 後要 cache-bust:`?v=NN` → `?v=NN+1`(grep `?v=` 改)
- **nginx config**:改 `frontend/nginx/default.conf` 後
  ```bash
  docker compose restart nginx
  ```

### 3. 測

```bash
# 後端 unit tests(mongomock · 不需真 Mongo)
cd backend/accounting
python3 -m pytest test_main.py --tb=short

# 後端 integration(真 Mongo)
python3 -m pytest tests/integration/ --tb=short

# E2E(Playwright · sandbox compose)
cd tests/e2e && npx playwright test
```

要求:全綠才 push。CI 會跑同樣 8 個 job(看 `.github/workflows/ci.yml`)。

### 4. ship

**鐵律**:每個改動都走 PR · 不直接 push main(installer 文案小改例外)。

```bash
git checkout -b v1.4-feature-xxx main
# ... 改 code ...
git add -A && git commit -m "feat(v1.4-xxx): ..."
git push -u origin v1.4-feature-xxx
gh pr create --base main --title "..." --body "..."
# 等 CI 綠 + user merge
# main merge 後 · 若改了 installer 內容 · re-tag + re-release
```

---

## 關鍵 patterns + 必踩坑

### A · 認證 3 層

來源優先序:
1. **LibreChat refreshToken cookie**(`_verify_librechat_cookie(request)`)· prod 唯一可信 · 用 JWT_REFRESH_SECRET 簽
2. **X-Internal-Token** header · cron / 內部 service 用 · `ECC_INTERNAL_TOKEN` env
3. **X-User-Email** header(legacy)· dev only · prod 預設關 · 開要設 `ALLOW_LEGACY_AUTH_HEADERS=1`

```python
# 後端 endpoint 寫法
from routers._deps import require_user_dep, require_admin_dep

@router.get("/foo")
def foo(email: str = require_user_dep()):     # 一般同仁
    ...

@router.get("/admin/bar")
def bar(_admin: str = require_admin_dep()):    # 必須 admin
    ...
```

admin 認定:`ADMIN_EMAILS` env 白名單 OR LibreChat `users.role=ADMIN`(OR 關係)。
停用帳號(`chengfu_active=false`)即使仍在 `ADMIN_EMAILS` 或有 `chengfu_permissions`,也會被 `require_user_dep()` / admin guard 擋下。

### A2 · 細部權限 enforcement

`chengfu_permissions` 已不只是 UI 設定。高風險 endpoint 要用:

```python
from routers._deps import require_permission_dep

@router.post("/transactions")
def create_tx(..., _user: str = require_permission_dep("accounting.edit")):
    ...
```

目前已接上 enforcement 的權限族群:
- `accounting.view` / `accounting.edit`
- `social.post_own`
- `site.survey`
- `knowledge.manage`
- `media_crm.edit` / `media_crm.export`
- admin-only 類(`admin.dashboard`, `admin.audit`, `admin.pdpa`)

注意:`social.post_all` 還是 advisory,尚未做跨作者發文權限拆分。

### B · MongoDB collections 共用

LibreChat 用 collections:`users`, `conversations`, `messages`, `agents`, `transactions`, `presets`, ...
我們加的:`projects`, `feedback`, `tenders`, `crm_leads`, `social_posts`, `media_contacts`, `meetings`, `site_surveys`, `audit_log`, `knowledge_audit`, `social_oauth_states`, `social_oauth_tokens`, ...

**用同一個 `chengfu` DB · 同一個 connection**。從 main.py `from main import db` 拿。

### C · 前端 ES module · 無 build step

`frontend/launcher/modules/*.js` 就是直接 import 寫法 · 瀏覽器原生跑。**不要**加 build chain(esbuild infra 已準備但 cutover 留 v1.4)。

### D · 錯誤訊息 helper

```js
import { toast, networkError, operationError, permissionError } from "./toast.js";

// ❌ 不要這樣寫
toast.error(`網路錯:${String(e)}`);   // 會顯示 [object Object]

// ✅ 用 helper
networkError("讀取會議", e, () => this.init());  // 帶重試 button
operationError("儲存記者", err);                 // 後端回應
permissionError("記者推薦");                      // 403 場景
```

### E · L3 機敏內容處理

3 層擋:
1. 前端 classifier(`/safety/classify`)即時跑 · UI 顯紅色 badge
2. 前端 confirm modal(用戶必按「我知道,送出」)
3. 後端 audit(`/safety/l3-preflight`)寫 audit log · `L3_HARD_STOP=1` 可硬擋 403

curl 直打 `/api/agents/chat` 會繞過 1+2 但 3 留 audit。

### F · WCAG 2.2 a11y baseline

最近 batch6 加的:
- skip-link「跳至主內容」
- `:focus-visible` outline 統一
- modal `role=dialog + aria-modal + focus trap`
- toast `aria-live + role=alert`
- `prefers-reduced-motion` 全動畫降到 0.01ms

新加 UI 元件**必須**:
- 有 aria-label(若無 visible text)
- focus 順序合理
- L3 紅色不要當唯一 indicator(色盲)

詳見 `frontend/launcher/user-guide/admin-permissions.md`。

---

## 必踩坑 · 已撞過 · 別重撞

| # | 坑 | 解 |
|---|------|------|
| 1 | LibreChat v0.8 endpoint `/api/ask/agents` 已 deprecated | 改用 `/api/agents/chat`(2026-04-24 修) |
| 2 | nginx 把 `/manifest.json` regex 攔到 LibreChat | 加 `location = /manifest.json` 優先(2026-04-23 修) |
| 3 | 同步 pymongo 在 async FastAPI | 留 v1.4 改 motor · 10 人並發 OK |
| 4 | macOS unsigned .app 跳 -1743 AppleEvent | 用 `open -a Terminal <file.command>`(2026-04-23 修) |
| 5 | osascript do shell script PATH 受限 | 強制 `export PATH=/opt/homebrew/bin:/usr/local/bin:...`(2026-04-23 修) |
| 6 | docker compose env 沒 passthrough 到 container | 必在 docker-compose.yml `environment:` 列出 + `${VAR:-default}` |
| 7 | Response body 雙讀 stream consumed | 一次 `await r.json()` 存變數 · 之後判 ok 用變數 |
| 8 | datetime tz-naive 跟 aware 比較 TypeError | 全 `datetime.now(timezone.utc)` |
| 9 | `_admin_allowlist` hardcode `sterio068@gmail.com` 在 git leak | 已移 · prod 必設 ADMIN_EMAILS env |
| 10 | PDPA 跨 14 collection 任一失敗 · 仍刪 users → 孤兒 | 已修 · 任失敗都 skip users delete |

---

## 現在狀態 · v1.3.0 release candidate + Phase 1 現場 Gate

### ✅ 全綠 · 可日用

12/13 V1.3-PLAN feature(B1 真打 Meta API 等審核中)、246 backend tests pass、launcher build pass、安裝精靈 7 步全自動建 admin + 10 Agent。vNext 已補上 Workspace 今日工作台、workflow draft-first UI、專案交棒卡 workflow draft、細部權限第一批 enforcement。本輪再補 Chat → Project handoff、工作包 AI 建議 → Chat → 直接回寫、project collaborator / next_owner、workflow adoption tracking、UI/UX 外部審計必修前端項目,並完成正式交付版本機 release gate。

### ✅ 本輪驗證

- `./scripts/release-verify.sh http://localhost`:13 passed / 0 failed。
- `./scripts/pre-pilot-verify.sh`:8 passed / 0 failed。
- Backend pytest:`246 passed,13 skipped,1 warning`。
- E2E:`35 passed,3 skipped`。
- Main smoke:`15 passed,0 failed`。
- LibreChat smoke:`13 passed,0 failed`。
- DMG SHA-256:`d85f5194b104d9f2ca4872c391350a762d8dc6bdf30f8efd1bf4a51056135ffa`。

### ⏭️ 接手後第一優先順序

1. 先跑 `./scripts/pre-pilot-verify.sh`,確認本地交付包仍是 8/8。
2. 在乾淨 Mac/VM 或承富 Mac mini 用 DMG 跑完整安裝,照 `docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md` Gate 1 留錄影/截圖/smoke log。
3. 用 3-5 份去識別化樣本跑 LibreChat 原生 RAG/file_search,確認正向查詢可引用資料、負向查詢不編造。
4. 開 4 人 Phase 1 pilot:老闆/Admin + Champion + 2 PM,至少 3/4 完成 first-win 才擴到 8 人。
5. Gate 1-4 任一 fail 時,不要全員上線;回到對應 Gate 修正。

### ⏸️ 留 v1.4

- B1 Meta API 真打(等 Meta App 審核)
- esbuild bundle cutover(infra ready · 50+ ES module 仍直送瀏覽器)
- 同步 pymongo → motor(scaling 準備)
- /memory/transcribe per-user rate limit
- PDPA replica set transaction
- CRM lead detail 專屬 view 深化
- mobile-first 大改寫
- `social.post_all` 真正拆成「可管理全公司社群貼文」
- 30+ MEDIUM polish(來自 5 agent audit)

詳見 `docs/DECISIONS.md` 待決議區。

### 🐛 已知 bug · 不擋

- chrome-extension 已修 manifest 可安裝,仍需真機打包 / 安裝教學驗收
- workflows view 已從 placeholder 升級為 draft-first 入口,但尚未開全自動 execution
- 登入 LibreChat 後 session 失效會跳奇怪 redirect · 重 login 解(發現再修)

---

## 哪裡找 ...

| 想找 | 看哪 |
|------|------|
| 為什麼選 X 不選 Y | `docs/DECISIONS.md` |
| 怎麼部署 | `DEPLOY.md` Phase 1-6 |
| UX 設計原則 | `SYSTEM-DESIGN.md` |
| 最新 architecture | `ARCHITECTURE.md` |
| 交付前最後 Gate | `docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md` |
| 本機交付包自檢 | `scripts/pre-pilot-verify.sh` + `reports/pre-pilot/pre-pilot-readiness-2026-04-25-150444.md` |
| 正式交付版驗收 | `reports/final-delivery-audit-2026-04-25.md` |
| 外部 AI 審計 | `docs/EXTERNAL-AUDIT-2026-04-25.md` |
| 一個 endpoint 在哪 | `frontend/launcher/user-guide/frontend-endpoints.md`(模組 ↔ API 對照) |
| 27 個鍵盤捷徑 | `frontend/launcher/user-guide/slash-commands.md` |
| 3 層權限矩陣 | `frontend/launcher/user-guide/admin-permissions.md` |
| 30+ error code | `frontend/launcher/user-guide/error-codes.md` |
| 最近哪幾批 UX 改 | `git log --oneline --grep "ux\|hardening" -20` |
| Agent JSON | `config-templates/presets/00-09-*.json` |
| 環境變數預設 | `config-templates/.env.example` |
| Cron 排程 | `scripts/install-launchd.sh` |
| Champion 教學 | `frontend/launcher/user-guide/training-v1.3.md` |

---

## Glossary · 詞彙表

| 詞 | 解 |
|---|---|
| **承富** | 客戶公司「承富創意整合行銷」(10 人 PR/行銷公司) |
| **Champion** | 公司內 1 個半技術同仁 · 幫 IT 解日常問題(ADMIN role) |
| **Sterio** | 系統作者 · 也是 fallback admin · email `sterio068@gmail.com` |
| **5 工作區** | 投標 / 活動 / 設計 / 公關 / 營運 · ⌘1-5 切換 |
| **10 Agent** | 主管家(00) + 9 專家(01-09) · 從原 29 Agent 精簡 |
| **Workspace** | 「工作區」的英文 · 跟 LibreChat workspace 不同(LC 沒這詞) |
| **Preset** | LibreChat 用詞 · 我們稱「Agent 模板」· source-of-truth 在 `config-templates/presets/` |
| **L1/L2/L3** | 資料分級 · 公開 / 一般 / 機敏 · 詳見 `docs/DATA-CLASSIFICATION-POSTER.md` |
| **PDPA** | 台灣個資法 · 同仁有「被遺忘權」· `/admin/users/{email}/delete-all` |
| **PDPA archive** | 刪除前必先壓縮 .json.gz + GPG 加密 · 留 30 天備援 |
| **Cookie-trusted** | LibreChat refreshToken cookie 驗過的 email · 唯一 prod 可信來源 |
| **Internal token** | `ECC_INTERNAL_TOKEN` · cron / 內部 service 認證 |
| **Handoff card** | 專案 4 格交棒卡(現況 / 風險 / 下一步 / 歷史)· 換手用 |
| **Audit log** | `audit_col` collection · 任何 admin / PDPA 操作必寫 |
| **Knowledge audit** | `knowledge_audit_col` · 讀 L2/L3 知識庫檔案的 trail · TTL 90d |

---

## 一些 AI 開發提醒

1. **commit message 中文 OK** · 但 type 用英文 `feat:` `fix:` `chore:` `docs:` `refactor:` `test:`
2. **每個 PR ≤ 500 行**(reviewer 看得下)· 大改拆多個 PR
3. **改前端必 cache bust**:`?v=NN` 找 `frontend/launcher/index.html` 改數字
4. **改後端必 rebuild**:`docker compose build accounting && docker compose up -d accounting`
5. **不確定 spec 寫 `docs/DECISIONS.md` 待決議**` · 別擅自決定
6. **不要刪 audit_log / knowledge_audit collection** · PDPA 法規要留
7. **任何用 `escapeHtml()` 的地方都不能省** · 後端回的 string 全當不可信
8. **Python 3.12 寫 type hint** · `from __future__ import annotations`
9. **JS 寫 ES module 不寫 require/CommonJS**
10. **CSS 用 design token**(`var(--accent)` 等)· 別 hardcode color · dark mode 才不破
11. **不要為 v1.5 設計 v1.4 的 API**(YAGNI)
12. **改 docker-compose.yml 先確認 v1.3 既有 env passthrough 沒掉**(CREDS_KEY / ADMIN_EMAILS / L3_HARD_STOP / OAUTH_REDIRECT_BASE_URL / JWT_REFRESH_SECRET / ECC_INTERNAL_TOKEN)

---

## 接手 SOP

第 1 天:
1. clone repo · `cd config-templates && docker compose up -d`
2. `open http://localhost/` 看 launcher 跑起來
3. 讀 `docs/DECISIONS.md` 全部
4. 讀 `frontend/launcher/user-guide/admin-permissions.md`
5. 跑 `cd backend/accounting && pytest test_main.py` 看全綠

第 2 天:
1. 讀 `SYSTEM-DESIGN.md` 理解 IA + macOS 設計原則
2. 讀 `ARCHITECTURE.md` 看 nginx + LibreChat + accounting 三角關係
3. 找一個 v1.4 待辦(看 `docs/DECISIONS.md` 待決議)挑小的開始

第 3 天起:
- 改 code · 走 PR
- 不確定 → 寫進 `docs/DECISIONS.md` 待決議 · 等 Sterio 答

有問題 email Sterio:`sterio068@gmail.com`

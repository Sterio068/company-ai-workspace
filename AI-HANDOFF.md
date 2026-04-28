# 🤖 AI Handoff · 承富 AI 系統

> 給接手開發的 AI 看的單一入口。
> 讀完這份 + `docs/DECISIONS.md` 即可開始改 code。
> 最後更新 · 2026-04-28 · 五大日常模組 UI/UX 強化 · release gate 13/13 PASS · backend 406 PASS

---

## 60 秒上手

**這是什麼**:原為台灣公關行銷公司「承富」(10 人)建置、現正往多公司可用白標化推進的 AI 協作平台 · 本地部署在公司 Mac mini · LibreChat + 自製 launcher + FastAPI 後端組合。正式前端已清除可見「承富」品牌字樣,內部文件/歷史檔名仍保留專案脈絡。

**現在狀態 (v1.8 Sprint 1 · 2026-04-28)**:v1.69 帳號 CRUD / AI 主備源 / 同仁連線網址 / RAG/file_search 已完成後,又完成 NotebookLM 功能最大化與全系統 4 代理深度審計。NotebookLM 採「本地資料庫為主、NotebookLM Enterprise 為深讀副本」,支援資料包、單檔、多檔、整個專案資料夾、1 工作包 1 notebook,且資料等級只標記不阻擋。v1.8 P1/P2 已補 NotebookLM batch/resume、設定寫前 token 驗證、Secret/Retention/Action registry、Mongo collection 健康度、OpenAPI client 接縫、全前端 inline handler 歸零。最新 Sprint 1 交付硬化已補 `ACTION_BRIDGE_TOKEN` 低權限 Action bridge、Help markdown sanitize、備份無 GPG fail-loud、OAuth production origin pin、OAuth token 明文 fallback 禁止。最新五大日常模組強化已把商機追蹤 / 會計 / 會議速記 / 場勘 / 使用教學工作台化,加入今日接續、複製摘要/brief、HEIC 場勘、五模組 SOP。最新驗證:`release-verify.sh` **13/13 PASS**,backend **406 passed / 10 skipped**,Playwright **73 passed / 5 skipped**。

**下一步一句話**:本機工程 gate 已過,下一步不是再堆功能,而是乾淨 Mac/VM 首裝錄影 + 真 NotebookLM Enterprise token 建 notebook / 上傳 / 同步一次 + 清掉 live LibreChat 舊 action metadata 後開 4 人 pilot。最新證據看 `reports/full-system-multi-agent-deep-audit-2026-04-28.md` 與 `reports/release/release-manifest-2026-04-28-223907.md`。

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
- NotebookLM 並行知識庫:本地 MongoDB/檔案為主資料庫,NotebookLM Enterprise 作為深讀副本;可建立資料包、同步、單檔/多檔/資料夾上傳,一個工作包對應一本 notebook。
- 五大日常模組 UI/UX:商機追蹤、會計、會議速記、場勘、使用教學已加入「今日接續 / 三步流程 / 複製摘要或 brief / SOP 搜尋」,讓非技術同仁不必理解模組分類也能照著做。

---

## 技術棧 · 不可隨意換

| 層 | 選擇 | 為何 |
|---|---|---|
| 硬體 | Mac mini M4 (24GB/512GB) | 老闆要本地部署 |
| 容器化 | Docker Desktop for Mac | LibreChat 官方推薦 |
| AI 對話框架 | **LibreChat v0.8.5** | 開源 + 多 provider + 原生 Agent · 2026-04-26 升 v0.8.5 |
| 主力模型 | OpenAI GPT-5.5 / GPT-5.5-mini / GPT-5.5-nano | 預設主力 · 前端可切換 Claude 備援 · sidebar AI 主備源面板顯示連線狀態 |
| 備援模型 | Anthropic Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 | 長文件分析 + 故障切換 · admin 才能切換(C1 client+UI gate) |
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
│   ├── main.py                  ← app entrypoint + router mount(主功能已逐步拆 routers/)
│   ├── routers/
│   │   ├── _deps.py             ← Depends 工具(require_user_dep / require_admin_dep)
│   │   ├── admin/               ← admin endpoint(2026-04 從 admin.py 拆)
│   │   │   ├── __init__.py      ← admin router root + audit-log + monthly-report
│   │   │   ├── dashboard.py     ← /admin/dashboard
│   │   │   └── user_mgmt.py     ← /admin/users CRUD + reset-password + permanent delete(v1.69)
│   │   ├── safety.py            ← /safety/classify + /safety/pii-detect + /l3-preflight
│   │   ├── knowledge.py         ← /knowledge/* + /admin/sources/*
│   │   ├── rag_adapter.py       ← LibreChat v0.8.5 RAG_API_URL 相容 adapter(/rag/* · 只供容器內 LibreChat)
│   │   ├── notebooklm.py        ← NotebookLM 資料包 / 專案 notebook / 單檔與資料夾上傳
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
│   │   ├── notebooklm_client.py ← NotebookLM Enterprise API client(未設定 token 則 local_ready)
│   │   ├── source_pack_renderer.py ← 從本地資料渲染 NotebookLM 資料包 Markdown
│   │   └── ...
│   ├── test_main.py             ← pytest 主測試(含 NotebookLM ACL / sync / hash / handoff)
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
│   ├── modules/                 ← ES modules(持續拆分中)
│   │   ├── README.md            ← ⭐ 每個 module 用途清單
│   │   ├── auth.js              ← LibreChat cookie 驗證
│   │   ├── chat.js              ← 對話 SSE 串流(/api/agents/chat)
│   │   ├── modal.js             ← Modal v2(role=dialog + focus trap)
│   │   ├── toast.js             ← Toast 通知(networkError / operationError helper)
│   │   ├── meeting.js / site_survey.js / social.js / media.js
│   │   ├── crm.js / tenders.js / workflows.js / notebooklm.js
│   │   ├── knowledge.js         ← 知識庫管理 + 搜
│   │   ├── user_mgmt.js         ← v1.3 新 · admin 建同仁
│   │   ├── shortcuts.js         ← ⌘K + 27 鍵盤捷徑
│   │   └── mobile.js            ← 行動端 bottom nav
│   ├── user-guide/              ← ⭐ 中文使用者手冊(可 sidebar 點)
│   │   ├── quickstart-v1.3.md
│   │   ├── mobile-ios.md
│   │   ├── error-codes.md
│   │   ├── admin-permissions.md  ← 3 層權限模型(看這份理解 RBAC)
│   │   ├── remote-access.md      ← v1.69 同仁連線方式(LAN/mDNS/cloudflared)
│   │   ├── account-management.md ← v1.69 老闆帳號管理 SOP
│   │   ├── notebooklm-sync.md    ← NotebookLM 資料包 / 同步 / 單檔與資料夾上傳 SOP
│   │   └── ...
│   ├── custom/                  ← 注入 LibreChat 頁面的 css/js
│   ├── nginx/                   ← nginx config(default.conf + chengfu-proxy.conf)
│   ├── modules/state/           ← localStorage wrapper
│   └── dist/                    ← esbuild 輸出 · production 由 index.html 載 hash bundle
│
├── config-templates/
│   ├── docker-compose.yml       ← ⭐ stack 定義 · accounting 含全 hardening env
│   ├── docker-compose.override.yml  ← 本機開發
│   ├── docker-compose.sandbox.yml   ← CI 用
│   ├── librechat.yaml           ← LibreChat 設定 · pin v0.8.5
│   ├── .env.example             ← env template
│   ├── presets/                 ← 10 Agent JSON(00-09)
│   └── actions/                 ← Fal.ai / PCC / accounting / NotebookLM OpenAPI schemas
│
├── scripts/
│   ├── start.sh                 ← ⭐ 從 macOS Keychain 注入 secrets + docker compose up
│   ├── stop.sh
│   ├── setup-keychain.sh        ← 首次 · 把 API keys 寫進 Keychain(含 NotebookLM token 選配)
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
│   ├── build.sh                 ← 先 npm build launcher · 再 osacompile + hdiutil 包 DMG
│   └── dist/                    ← 產物(最新約 71M DMG · 內含 source 快照)
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
| `reports/full-system-multi-agent-deep-audit-2026-04-28.md` | ⭐ 最新全系統 4 代理深度審計 · NotebookLM 修正 + release gate 13/13 · 工程面可交付 |
| `reports/release/release-manifest-2026-04-28-223907.md` | ⭐ 最新 release manifest · 13 passed / 0 failed · DMG SHA `72260b17131d9d3b6b201609a5b1e03dac893e786d09e53d8a10aa51157ebf6a` |
| `reports/final-delivery-audit-2026-04-25.md` | 正式交付版本機 release gate 通過,列出現場剩餘 Gate |
| `reports/release/release-manifest-*.md` | 最新 `release-verify.sh` 13 passed / 0 failed · 以最新 manifest 內的 DMG SHA 為準 |
| `installer/dist/ChengFu-AI-Installer.dmg` | 最新 DMG 約 73M · release gate 已做內容與敏感檔抽查 |
| `reports/pre-pilot/pre-pilot-readiness-2026-04-28-143749.md` | 最新 pre-pilot manifest 追溯 · 交付包自檢用 |
| `reports/multi-agent-ui-ux-hardening-2026-04-28.md` | 2026-04-28 早一輪多代理 UI/UX hardening · mobile/project/user modal a11y 與交付可信度補強 |
| `reports/rag-verify/rag-verify-2026-04-28-100959.md` | LibreChat v0.8.5 RAG/file_search 本機 E2E PASS · OpenAI 知識庫 Agent 回出來源檔名 + 引用內容 |
| `reports/notebooklm-ui-ux-audit-2026-04-28.md` | NotebookLM UI/UX 第一輪審計 · 首屏簡化 + 1 工作包 1 notebook |

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
- **前端**:改 `frontend/launcher/**` 後要重建 bundle,否則瀏覽器仍會載 `/static/dist/app.<hash>.js` 舊碼
  ```bash
  cd frontend/launcher
  npm run build
  ```
  - `build.config.js` 會自動更新 `index.html` 的 `BUILD_INJECT_BUNDLE` hash 區塊
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

### C · 前端 ES module · production 需 build

`frontend/launcher/modules/*.js` 維持 vanilla ES module,不要改 React / Next / Tailwind。production 入口目前載 `/static/dist/app.<hash>.js`,所以改 source 後一定要跑 `cd frontend/launcher && npm run build`;`installer/build.sh` 也會自動 build,避免 DMG 包到舊 bundle。

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

## 現在狀態 · v1.69+ NotebookLM + 五大日常模組強化

### ✅ 本機正式交付 Gate 已通過

v1.3.0 release base 之上推進 v1.66/1.67/1.68/1.69 共 4 個 minor 批次,再完成 NotebookLM 功能最大化與 4 代理全系統深度審計。v1.69 原本已完成同仁帳號 CRUD + AI 主備源面板 + 同仁連線網址中控卡 + RAG/file_search;本輪再補 NotebookLM UI/UX、後端可靠性、Agent action 契約、安裝流程與 release gate。最新又完成五大日常模組 UI/UX 強化:商機追蹤、會計、會議速記、場勘、使用教學改為「今日接續 + 三步流程 + 可複製產出 + SOP」。最新工程結論:本機正式交付 gate 通過,可交付新版 DMG 進入乾淨 Mac/VM 與真人 pilot。

### ✅ v1.7 W1 NotebookLM hardening(2026-04-28)

- 已完成 `reports/system-optimization-plan-2026-04-28.md` W1 中的 P0-2 / P0-5 / P1-4 / P1-6 / P2-2 / P2-3 / P2-8 主體實作。
- Agent endpoint 改為 `X-Acting-User` 套該使用者 ACL,不再用 admin 身分繞過工作包 owner/collaborator。
- Source Pack hash 穩定化:同日時間差與小數財務雜訊不再造成重複資料包。
- Source Pack 建立與同步會寫 audit/sync run;L3 同步前端跳確認,但不阻擋(D-015 功能最大化)。
- 前端 NotebookLM 降為 3 區塊:從本地資料建立資料包 / 直接上傳檔案或資料夾 / 預覽與最近資料包,並顯示本地資料庫 → 資料包/檔案 → 專案 Notebook 關係。
- 驗證:`pytest backend/accounting/test_main.py -q` → **171 passed**;NotebookLM focused pytest **12 passed**;`node --check frontend/launcher/modules/notebooklm.js` PASS;`npm run build` → `dist/app.GUK3GAMQ.js`;Playwright NotebookLM view → **1 passed**。

### ✅ v1.8 P1/P2 技術債推進(2026-04-28)

- P1-2:新增 `backend/accounting/services/secret_registry.py` 與 `config-templates/.env.tiers.md`;`/admin/secrets/status` 會回 tier / reader / writer / frontend_writable。
- P1-3:新增 `config-templates/actions/registry.json` 與 `scripts/validate-actions.py`;`scripts/wire-actions.py` 只讀 registry 中 `wire=true` 的 canonical action。
- P1-5:新增 `backend/accounting/infra/retention_policy.py`;startup 會套用集中 TTL registry 並偵測 stale TTL drop+recreate。
- P1-6/P1-9/P2-9:NotebookLM source pack sync 支援 batch_id/resume、L3/Agent-created 二次確認、settings 寫前 token 驗證,錯誤會留下 recovery_hint / provider_status。
- P1-8:移除 `frontend/launcher` 內所有 inline `onclick/onsubmit/onchange/onkeydown/oninput`;新增 `modules/dom-actions.js` 統一 allowlist delegated handler。
- P2-4:新增 `frontend/launcher/lib/api-client.js` + `api-types.ts` bootstrap;`chat.js` 已改一段 quota/feedback 走 API client,後續拆檔有穩定接縫。
- P2-7:管理後台新增 `/admin/storage-stats` + 前端「資料庫健康度」,可看 collection 文件數、索引數、儲存量與 >1GB / 100k 文件警示。
- P1-7 起步:新增 `frontend/launcher/styles/admin-observability.css`,把新 admin observability 樣式從 `launcher.css` 拆出;大規模 NotebookLM / view-specific CSS 拆分仍可繼續。
- 驗證:`pytest backend/accounting/test_main.py -q --tb=short` → **179 passed**;`npm run build` → `dist/app.J5YR3CKP.js`;`python3 scripts/validate-actions.py` PASS;`rg "onclick=|onsubmit=|onchange=|onkeydown=|oninput=" frontend/launcher` 無結果;`curl -I http://localhost/` → 200。

### ✅ 最新驗證(2026-04-28 22:39 CST)

- `./scripts/release-verify.sh http://localhost` → **13/13 PASS**
- release manifest:`reports/release/release-manifest-2026-04-28-223907.md`
- DMG:`installer/dist/ChengFu-AI-Installer.dmg` · 73M · SHA-256 `72260b17131d9d3b6b201609a5b1e03dac893e786d09e53d8a10aa51157ebf6a`
- backend full pytest:`406 passed / 10 skipped`
- Playwright full E2E(desktop + mobile):`73 passed / 5 skipped`
- 五大日常模組 focused E2E:`8 passed`
- smoke:`17 passed / 0 failed`
- LibreChat route smoke:`13 pass / 0 fail`
- frontend build:`dist/app.IF3AC7LA.js`
- DMG 內容與敏感檔抽查:PASS
- JS syntax / shell syntax / Python compile / action JSON:PASS

### ✅ v1.69 基礎驗證(同日較早)

- E2E view-coverage(desktop + mobile)`32/32 PASS`
- v1.69 backend pytest(5 新 test class)`17/17 PASS` · cover 401/403/redacted view/密碼複雜度/lockout/CAS
- 安全 smoke:匿名 `/admin/access-urls` → 403 ✓ · 匿名 `/health/ai-providers` → 401 ✓ · X-Forwarded-Host XSS 注入被 regex 擋 ✓
- 接手補強 smoke(2026-04-28):`./scripts/smoke-test.sh http://localhost` → 16/16 PASS · 含 nginx strip `X-User-Email` 後偽造 admin header 仍回 403
- 多代理 UI/UX hardening(2026-04-28):修 mobile drawer `aria/inert/focus/Esc`,project modal dialog/focus trap,同仁 modal focus trap,移除 E2E 硬編碼密碼 fallback;`a11y-keyboard-smoke.json` → `ok:true`
- RAG/file_search E2E(2026-04-28):OpenAI 知識庫 Agent `agent_O8Y-j5Ct1qoH9dbHINxeZ` 上傳去識別合成樣本,file_id `c0a1605e-d3c2-429c-a476-cf9ddfe2fcd1`,對話 `9d8aaf1b-5b5e-48e4-8936-626628c02755` 成功觸發 `file_search` 並引用 `chengfu-rag-synthetic-20260428.txt` 回答 `#0F766E` + KPI;RAG adapter 經 LibreChat short-lived JWT 驗證,nginx 外部 `/api-accounting/rag/*` 維持 403
- 5 面向最終分數:Security 96 · A11y 91 · Python 92 · JS/TS 91 · Design 91 · **綜合 92.2**

### ✅ 全系統 4 代理深度審計處置(2026-04-28)

| 面向 | 審計前分數 | 已修事項 |
|---|---:|---|
| UI/UX + a11y | 76/100 | NotebookLM 與本地資料庫關係改清楚、資料包命名、同步雲端揭露、教學重寫 |
| Backend/API | 67/100 | project 資料包 ACL、sync failed run、stable hash、handoff next_actions 合併 |
| QA/Release | 74/100 | installer build 先跑 launcher build,避免 stale dist;release gate 13/13 |
| Architecture/Docs | docs 58/100 | D-015 補進 `DECISIONS.md`,資料持久化 map,action schema `all/L1/L2/L3` |

### 📦 v1.69 batch 主要交付

| 元件 | 檔案 | 內容 |
|---|---|---|
| **AI 主備源 sidebar** | `frontend/launcher/index.html:170-209` + `app.js _bindAiSourcePanel` | 全員可見 + admin 切換 + health icon shape (●▲✕○) 雙重編碼 |
| **同仁連線網址中控卡** | `backend/accounting/main.py /admin/access-urls` + `admin.js renderAccessUrls` | LAN/mDNS/cloudflared 動態偵測 · `start.sh` 寫 `.host-network.json` 給 backend |
| **AI 引擎 health endpoint** | `backend/accounting/main.py /health/ai-providers` | 匿名 401 · 非 admin redacted view (只 state) · admin 完整 view (reason + configured) |
| **帳號 CRUD UI** | `user_mgmt.js + user_mgmt.py` | 重設密碼 modal + 永久刪除二段式 (case-sensitive 確認) + `_showPasswordOnce` self-build dialog scope-safe |
| **密碼政策** | `user_mgmt.py _validate_password_strength` | ≥10 字 + ≥3 類 + 弱密碼黑名單 + 同字元 ≤3 連續 · UserCreate + PasswordReset 共用 |
| **session 強制踢出** | `user_mgmt.py reset_user_password` | 改密後 `$or [{user:str},{user:obj}]` 雙型別 cleanup + audit fail-loud 503 |
| **permanent delete CAS guard** | `user_mgmt.py delete_user_permanent` | filter 加 `chengfu_active=False` 防 race + 任一 token cleanup 失敗 503 中止 |
| **教學文件** | `frontend/launcher/user-guide/{remote-access,account-management}.md` | sidebar 第 2-3 項 + 中控連線卡跳 anchor |
| **共用 utility** | `util.js copyToClipboard` (含 execCommand fallback) + `user_mgmt.js _modalKeyHandler` | 集中所有 navigator.clipboard + Esc/Tab focus trap |
| **NotebookLM UI/UX** | `frontend/launcher/modules/notebooklm.js` + `frontend/launcher/user-guide/notebooklm-sync.md` | 一個主任務 + 資料包語言 + 本地主資料庫/NotebookLM 深讀副本說明 |
| **NotebookLM 後端** | `backend/accounting/routers/notebooklm.py` + `services/notebooklm_client.py` + `services/source_pack_renderer.py` | 資料包 / project notebook / 單檔多檔資料夾上傳 / sync run / ACL / stable hash |
| **NotebookLM Agent action** | `config-templates/actions/{internal-services,notebooklm-bridge}.json` + `scripts/wire-actions.py` | 主管家與專家可建立資料包;bridge 走 `ACTION_BRIDGE_TOKEN`;等級 enum `all/L1/L2/L3` |
| **NotebookLM 安裝契約** | `scripts/setup-keychain.sh` + `scripts/start.sh` + `.env.example` | 安裝時顯示官方網址與 `gcloud auth print-access-token`;Keychain 注入 `NOTEBOOKLM_ACCESS_TOKEN` |
| **Action 低權限橋接** | `scripts/wire-actions.py` + `backend/accounting/main.py` + `auth_deps.py` + `secret_registry.py` | LibreChat Actions 改走 `ACTION_BRIDGE_TOKEN` + `X-Acting-User` + endpoint allowlist,不再重用 `ECC_INTERNAL_TOKEN` |
| **交付安全硬化** | `backup.sh` + `social_oauth.py` + `oauth_tokens.py` + `help.js` + `chat-sanitize.js` + `default.conf` | 無 GPG 備份預設中止、OAuth prod 不信 forwarded host、Help markdown sanitize、CSP 移除 inline script |

### ⏭️ 接手後第一優先順序

1. 在乾淨 Mac/VM 跑完整 DMG 安裝,照 `docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md` Gate 1,並錄影留證
2. 用真 NotebookLM Enterprise token 跑 3 件事:建立 project notebook / 同步資料包 / 上傳單檔或資料夾
3. 清查 live LibreChat `actions` collection 是否有舊 `metadata.api_key`;必要時刪舊 action 或重跑新接線,避免歷史 secret 殘留
4. 在乾淨 Mac/VM 重跑 LibreChat RAG/file_search 驗證並補截圖/錄影證據(本機 E2E 已通,見 `reports/rag-verify/rag-verify-2026-04-28-100959.md`)
5. 若再改 code 或 installer,重跑 `./scripts/release-verify.sh http://localhost` 確認 release gate 仍 13/13
6. 4 人 Phase 1 pilot:老闆 + Champion + 2 PM

### ⏸️ 留 v1.7+

- B1 Meta API 真打(等 Meta App 審核)
- 同步 pymongo → motor(scaling 準備)
- /memory/transcribe per-user rate limit
- PDPA replica set transaction(目前 cleanup-first guard 已減緩 orphan 風險)
- CRM lead detail 專屬 view 深化
- mobile-first 大改寫
- chat.js 1300+ 行拆檔(Q1 deferred · 已抽 chat-sanitize / chat-attachments,並已接 API client)
- app.js 2000+ 行拆檔成 views/* (Q2 deferred)
- launcher.css 仍約 6700+ 行 · 已拆 `admin-observability.css`,但 NotebookLM / view-specific / mobile CSS 還需大拆
- inline handlers 已清到 0 · 後續新增 UI 一律用 `data-action` / delegated listener,不要回到 inline handler
- Sidebar / 首頁 IA 仍偏功能中控 · 需 v1.70 收斂成「丟工作 → AI 判斷 → 交棒」工作台
- 真 NotebookLM Enterprise API 尚未以 production token 完整跑過;目前測試覆蓋未設定 fallback、ACL、錯誤 recovery_hint、action schema 與後端契約
- 歷史文件仍有部分「承富」/舊 29 Agent / 舊容器敘述;正式白標交付文件需另開 docs cleanup sprint
- 30+ MEDIUM polish 殘餘(來自 5 輪 agent audit · 不阻 ship)

詳見 `docs/DECISIONS.md` 待決議區。

### 🐛 已知 bug · 不擋

- chrome-extension 已修 manifest 可安裝,仍需真機打包 / 安裝教學驗收
- workflows view 已從 placeholder 升級為 draft-first 入口,但尚未開全自動 execution
- 登入 LibreChat 後 session 失效會跳奇怪 redirect · 重 login 解
- LibreChat sessions/refreshTokens collection 的 user 欄位實際型別未確認(已改 `$or` 雙型別清,假設兩種都試)
- 重複 E2E 登入太密會觸發 LibreChat rate limit;測試應優先使用 storageState 或共享 context,不要短時間連續新 context 登入
- NotebookLM 真 API 尚需 GCP / Enterprise license / token 才能驗;未設定時系統會保留本地資料包與上傳紀錄,不送出資料

---

## 哪裡找 ...

| 想找 | 看哪 |
|------|------|
| 為什麼選 X 不選 Y | `docs/DECISIONS.md` |
| 怎麼部署 | `DEPLOY.md` Phase 1-6 |
| UX 設計原則 | `SYSTEM-DESIGN.md` |
| 最新 architecture | `ARCHITECTURE.md` |
| 交付前最後 Gate | `docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md` |
| 本機交付包自檢 | `scripts/pre-pilot-verify.sh` + `reports/pre-pilot/pre-pilot-readiness-2026-04-28-143749.md` |
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
| **v1.69** 同仁連線方式 | `frontend/launcher/user-guide/remote-access.md`(內網 IP/mDNS/cloudflared 全教學) |
| **v1.69** 帳號管理 SOP | `frontend/launcher/user-guide/account-management.md`(老闆專用 · 加/改/刪/重設密碼) |
| **v1.69** AI 主備源 health | `GET /api-accounting/health/ai-providers`(匿名 401 / USER redacted / admin full) |
| **v1.69** 連線網址 endpoint | `GET /api-accounting/admin/access-urls`(從 `.host-network.json` 讀) |
| **v1.69** 重設密碼 endpoint | `POST /api-accounting/admin/users/{email}/reset-password`(密碼複雜度 + 強制踢 session) |
| **v1.69** 永久刪除 endpoint | `DELETE /api-accounting/admin/users/{email}/permanent`(二段 + CAS + cleanup-first) |
| **v1.69** 密碼複雜度規則 | `backend/accounting/routers/admin/user_mgmt.py _validate_password_strength`(共用 validator) |
| **v1.69** modal a11y helper | `frontend/launcher/modules/user_mgmt.js _modalKeyHandler`(Esc + Tab focus trap) |
| **v1.69** 安全複製 utility | `frontend/launcher/modules/util.js copyToClipboard`(navigator + execCommand fallback) |
| **v1.69** host network 偵測 | `scripts/start.sh` 寫 `config-templates/.host-network.json`(jq -n 安全 escape) |
| **v1.69** 5 輪審計報告 | `reports/multi-agent-audit-2026-04-27.md` + `reports/system-audit-2026-04-27.md` + git log `feat(v1.69)` 對應 commit messages |
| **2026-04-28** UI/UX hardening | `reports/multi-agent-ui-ux-hardening-2026-04-28.md` + `reports/qa-artifacts/v1.69-multi-agent-ui-audit/a11y-keyboard-smoke.json` |
| **2026-04-28** 五大日常模組 UX | `frontend/launcher/modules/crm.js` + `accounting.js` + `meeting.js` + `site_survey.js` + `help.js`;SOP:`frontend/launcher/user-guide/daily-ops-modules.md` |
| **2026-04-28** 全系統深度審計 | `reports/full-system-multi-agent-deep-audit-2026-04-28.md`(4 代理 · NotebookLM + release gate + 殘餘風險) |
| **2026-04-28** 最新 release manifest | `reports/release/release-manifest-2026-04-28-223907.md`(`release-verify.sh` 13/13 · DMG SHA 已列) |
| **2026-04-28** 最新 DMG | `installer/dist/ChengFu-AI-Installer.dmg`(73M · SHA 見最新 manifest) |
| **2026-04-28** RAG/file_search 驗證 | `reports/rag-verify/rag-verify-2026-04-28-100959.md` + `backend/accounting/routers/rag_adapter.py` |
| **2026-04-28** NotebookLM 最佳化 | `frontend/launcher/modules/notebooklm.js` + `frontend/launcher/user-guide/notebooklm-sync.md` + `backend/accounting/routers/notebooklm.py` + `docs/NOTEBOOKLM-KNOWLEDGE-ARCHITECTURE.md` + `reports/notebooklm-ui-ux-audit-2026-04-28.md` |
| **2026-04-28** NotebookLM v1.7 W1 hardening | `reports/notebooklm-v1.7-hardening-2026-04-28.md`(Agent ACL / stable hash / L3 confirm / recovery_hint / UI 三區塊) |
| **2026-04-28** NotebookLM action schema | `config-templates/actions/internal-services.json` + `config-templates/actions/notebooklm-bridge.json` + `scripts/wire-actions.py` |
| **2026-04-28** NotebookLM 安裝契約 | `scripts/setup-keychain.sh` + `scripts/start.sh` + `config-templates/.env.example` |
| **2026-04-28** Action bridge token | `ACTION_BRIDGE_TOKEN` in Keychain/env + `backend/accounting/main.py _action_bridge_path_allowed` + `auth_deps.py` |
| **2026-04-28** Help markdown sanitize | `frontend/launcher/modules/help.js` + `frontend/launcher/modules/chat-sanitize.js` + `frontend/nginx/default.conf` |
| **2026-04-28** 備份 fail-loud | `scripts/backup.sh`(無 GPG key `chengfu` 預設中止;dev 才可 `ALLOW_PLAINTEXT_BACKUP=1`) |

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
| **Action bridge token** | `ACTION_BRIDGE_TOKEN` · LibreChat Actions 專用低權限 token · 必須搭配 `X-Acting-User` + allowlist endpoint |
| **Handoff card** | 專案 4 格交棒卡(現況 / 風險 / 下一步 / 歷史)· 換手用 |
| **Audit log** | `audit_col` collection · 任何 admin / PDPA 操作必寫 |
| **Knowledge audit** | `knowledge_audit_col` · 讀 L2/L3 知識庫檔案的 trail · TTL 90d |
| **AI 主備源** | sidebar 底部面板 · GPT-5.5 主力 + Claude Opus 4.7 備援 · admin 才可切 |
| **連線網址** | 中控頁第一塊 · LAN/mDNS/cloudflared 動態列表 · 老闆貼給同仁登入 |
| **CAS guard** | Compare-And-Swap · permanent delete `delete_one({"_id":id, "chengfu_active":False})` 防 multi-admin race |
| **cleanup-first guard** | permanent delete · 任一 sessions/refreshTokens 清失敗則 503 中止主刪 · 不留 orphan token |
| **audit fail-loud** | 高風險 admin op · audit_log INSERT 失敗 → 503(不能 silent) |
| **redacted view** | non-admin 查 `/health/ai-providers` 只見 state(綠/橙/紅/灰)· 不見 reason / configured |
| **scope-safe modal** | `_showPasswordOnce` 自建 dialog · queryselector 限 self-scope · 防多 modal 抓錯密碼按鈕 |
| **RAG adapter** | accounting 內建 LibreChat RAG_API_URL 相容層(`/rag/*`)· Mongo keyword retrieval baseline · 需 LibreChat short-lived JWT · nginx 不對外暴露 |
| **NotebookLM 資料包** | 由本地資料庫/檔案渲染出的 Markdown 快照 · 可預覽、保存、同步到 NotebookLM Enterprise |
| **Project Notebook** | NotebookLM 一個工作包一本筆記本 · 資料包 / 單檔 / 多檔 / 資料夾都歸入同一本 |
| **Folder upload** | NotebookLM 前端可選整個資料夾 · 後端用相對路徑自動比對工作包 · `/notebooklm/uploads/auto` |
| **Sync run** | `notebooklm_sync_runs` · 每次同步資料包到 NotebookLM 的狀態紀錄 · 失敗需標 `failed` + `finished_at/error` |
| **白標化** | 前端可見名稱不可綁死承富;內部 repo / 歷史文件仍可能保留 ChengFu 專案名 |

---

## 一些 AI 開發提醒

1. **commit message 中文 OK** · 但 type 用英文 `feat:` `fix:` `chore:` `docs:` `refactor:` `test:`
2. **每個 PR ≤ 500 行**(reviewer 看得下)· 大改拆多個 PR
3. **改前端必 build**:`cd frontend/launcher && npm run build` · 不再手動改 `?v=NN`,由 `build.config.js` 更新 hash bundle
4. **改後端必 rebuild**:`docker compose build accounting && docker compose up -d accounting`
5. **不確定 spec 寫 `docs/DECISIONS.md` 待決議**` · 別擅自決定
6. **不要刪 audit_log / knowledge_audit collection** · PDPA 法規要留
7. **任何用 `escapeHtml()` 的地方都不能省** · 後端回的 string 全當不可信
8. **Python 3.12 寫 type hint** · `from __future__ import annotations`
9. **JS 寫 ES module 不寫 require/CommonJS**
10. **CSS 用 design token**(`var(--accent)` 等)· 別 hardcode color · dark mode 才不破
11. **不要為 v1.5 設計 v1.4 的 API**(YAGNI)
12. **改 docker-compose.yml 先確認 v1.3 既有 env passthrough 沒掉**(CREDS_KEY / ADMIN_EMAILS / L3_HARD_STOP / OAUTH_REDIRECT_BASE_URL / JWT_REFRESH_SECRET / ECC_INTERNAL_TOKEN / ACTION_BRIDGE_TOKEN / **v1.69 加** OPENAI_API_KEY / ANTHROPIC_API_KEY / HOST_NETWORK_FILE)
13. **新加 admin destructive endpoint 必補 4 項**:require_admin gate / matched_count race guard / audit fail-loud 503 / 連帶 cleanup-first 防 orphan(參 v1.69 reset_password + delete_permanent)
14. **inline `onclick` 已禁用** · 一律 `data-act="..."` + `addEventListener` · 密碼 / token 不入 DOM attribute(v1.69 audit P0-1)
15. **新 modal 用 `_modalKeyHandler(m, close)`** 處理 Esc + Tab focus trap · 不要再各自 hand-roll
16. **新建按鈕 / 重設密碼類**:用 `_showPasswordOnce({title, email, password})`(scope-safe + 焦點還原 + Esc)
17. **改 nginx 設定先確認 X-User-Email 強制覆寫沒掉** · 不然 USER 可在 LAN 直 expose 8000 偽造 header(audit 殘留架構建議)
18. **改 launcher source 後一定要 `cd frontend/launcher && npm run build`** · `index.html` 目前載 `/static/dist/app.<hash>.js`,只改 source 不會進瀏覽器
19. **E2E 憑證只讀 env / macOS Keychain** · 不要再把個人 email/password fallback 寫入測試碼
20. **RAG adapter 只能內部使用** · LibreChat 走 `http://accounting:8000/rag`;nginx `/api-accounting/rag/*` 必須維持 403,避免未登入者直接上傳/查詢 RAG 文件
21. **NotebookLM 不取代本地資料庫** · 本地 MongoDB / 檔案索引 / 工作包仍是 source of truth;NotebookLM 只收資料包或使用者主動上傳的檔案做深讀副本
22. **NotebookLM 資料等級只標記不阻擋** · D-015 決議功能最大化;UI/文件必須揭露同步或上傳會送到 NotebookLM Enterprise,但不要因 L1/L2/L3 擋功能
23. **改 NotebookLM action schema 要同步 3 處**:`internal-services.json` / `notebooklm-bridge.json` / `scripts/wire-actions.py`;bridge 走 `ACTION_BRIDGE_TOKEN`,不是 `ECC_INTERNAL_TOKEN` / 一般 API_KEY
24. **改 installer/build 或 launcher source 後跑 release gate**:`./scripts/release-verify.sh http://localhost`;最新合格 baseline 是 13/13,DMG SHA 在 `reports/release/release-manifest-2026-04-28-223907.md`
25. **備份正式環境不可明文 fallback**:`scripts/backup.sh` 無 GPG key `chengfu` 會中止;不要為了方便在正式機設 `ALLOW_PLAINTEXT_BACKUP=1`

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

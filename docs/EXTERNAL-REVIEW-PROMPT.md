# 承富 AI 系統 · 外部審查請求

> **使用說明:** 把整份文件貼給外部 reviewer(可以是另一個 AI 如 GPT-5 / Gemini / Claude Opus,也可以是人類顧問)。
> 他們應該能從頭到尾讀完後,不用再追問背景,就給出具體可執行的建議。
>
> **完整專案原始碼(本機路徑):**
> - Project root:`/Users/sterio/Workspace/ChengFu`
> - 所有相對路徑(如 `frontend/launcher/app.js` / `backend/accounting/main.py`)皆以此為根
> - 本機已跑:`./scripts/start.sh` · 瀏覽器開 <http://localhost/>
> - 若 reviewer 是另一個 AI 在同一台機器執行,直接用檔案系統讀即可;如果是另一個會話 / 另一人,請作者把整個 `ChengFu/` 目錄提供給對方(zip、USB、scp、共享雲端皆可)
>
> **若 reviewer 只想看關鍵檔而不 clone,優先讀這幾份:**
> - `CLAUDE.md` · `SYSTEM-DESIGN.md` · `ARCHITECTURE.md` · `docs/DECISIONS.md`
> - `docs/ROADMAP-v4.2.md`(最新路線圖 · 已對齊老闆 5 題答案)
> - `docs/PRE-DELIVERY-CHECKLIST.md`(交付前打勾清單 · **揭露系統完成 / 部署未完成**)
> - `docs/BASELINE.md`(T0 量測模板)
> - `docs/QUICKSTART.md`(10 分鐘上手 · 對使用者)
> - `docs/CASES/01-海廢案端到端.md`(第一個完整案例 · 5 天投標)
> - `docs/HANDBOOK/*.md`(4 份角色手冊)
> - `docs/NAS-INTEGRATION-SPEC.md` + `docs/LINE-WORKFLOW-SPEC.md`
> - `docs/LIBRECHAT-UPGRADE-CHECKLIST.md`
> - `frontend/launcher/index.html` · `app.js` · `launcher.css` · `modules/*.js`
> - `frontend/nginx/default.conf`
> - `backend/accounting/main.py`
> - `scripts/create-agents.py` · `scripts/start.sh` · `scripts/backup.sh` · `scripts/smoke-librechat.sh`
> - `config-templates/librechat.yaml` · `docker-compose.yml` · `.env.example`

---

## 🧭 已做過的 3 輪內部審查結論(reviewer 進來前先讀 · 避免重複指出)

### Round 1(技術正確性)· **已修 8 條紅線**
- FE · chat.js SSE `pop() ?? ""`、chat.js `.chat-messages` → `#chat-messages`、auth.js 401 auto-refresh retry + Web Locks + SessionExpiredError
- BE · `import json` 修 NameError、email regex injection 修掉、RequestIDMiddleware 500 也帶 header、刪 assert_not_l3 雙源
- Ops · backup.sh 加 rclone off-site、start.sh CI 護欄 + accounting image stale guard、smoke-librechat 補 SSE/convos、LibreChat upgrade checklist 加 agent `_id` dump

### Round 2(產品 / UX / 業務 / 教材)· **已修 10 條**
- Onboarding 從 10 步 → **3 步任務型**(對齊老闆 top 3:設計/投標/廠商)· L3 警語整段刪(老闆:先不考慮 L3)
- 術語中文化 · Agent → 助手、Workspace → 工作區、Skill → 範本、Preset → 模板
- 「找不到 Agent」文案友善化 · 技術指令只給 admin
- 新增:QUICKSTART / CASES/01 / HANDBOOK×4 / NAS-SPEC / LINE-SPEC / README 第一屏改為使用者場景

### Round 3(交付準備度 / 整合 regression / 財務 ROI)· **已修 4 條 · 揭露 3 個部署紅線**
- **修掉** accounting image 未 rebuild 導致 RBAC 未生效(致命 · 在內網裸奔)
- **修掉** onboarding tour-step-total 寫死 4 的破綻
- **加** 3 個 ROI 儀表:`/admin/budget-status` / `/admin/top-users` / `/admin/tender-funnel`
- **加** Dashboard ROI row(本月 AI 費用進度條 + 標案漏斗 + 本週完成任務)
- **揭露(非程式碼問題 · 交付前手動落地):**
  - 🔴 Mac mini 尚未上架 + Cloudflare Tunnel 未設(DoD 20%)
  - 🔴 `knowledge-base/samples/` 空 · 承富真實建議書 0% 已灌
  - 🔴 10 帳號 / 密碼 reset SOP / 2 場教育訓練皆 0%
  - 詳見 `docs/PRE-DELIVERY-CHECKLIST.md` 逐日打勾清單

### 因此 · reviewer 請**不要再審以下項**(已在上述 3 輪處理)
- SSE pop 邊界、tenders listener 疊加、auth 401 retry、CORS whitelist、admin RBAC
- onboarding 步數、L3 警語、術語中文化
- ROI baseline 缺失、per-user quota 缺失、標案漏斗視覺化、accounting image 是否 rebuild
- 異機備份腳本骨架、LibreChat 升版 checklist

### 建議 reviewer 本輪**新聚焦的問題**(我們還沒問過):
- 系統有什麼**還沒列入** PRE-DELIVERY-CHECKLIST 的落地盲點?
- ROI 3 儀表夠嗎 · 6 個月後真能答辯「值 NT$ 88,000」嗎?
- 教學手冊對**抗拒型資深同仁**夠嗎 · 有沒有更好的「first-win」策略?
- 以你的專業 · 這個系統**最可能在上線後第 2 週**怎麼死(usage 崩掉 / 同仁放棄 / 老闆不付錢)?

---

## 0. 審查者角色定位

你是一位**同時精通前端工程、後端架構、UX 設計、產品策略、AI 系統落地**的資深顧問。你的客戶是一間**10 人的台灣公關行銷公司**,不是 startup 也不是 SaaS 團隊,所以:
- 過度工程化的建議(例如 k8s / microservices / GraphQL federation)請**直接否決**
- 「業界最佳實踐」要對應到 10 人團隊的現實(一個 PM 兼產品 + 一個外包工程師維運)
- 任何建議都要評估 **CP 值**:做了之後能省幾小時 / 多接幾個案 / 少犯幾個錯?

---

## 1. 客戶與使用情境

- **公司名:** 承富創意整合行銷有限公司(台灣)
- **業務:** 公關行銷、活動規劃、政府標案(估計標案佔比 50%+)
- **規模:** 10 位同仁(老闆 + PM + 設計 + 企劃 + 業務,平均年資偏長,有資深同仁對 AI 較抗拒)
- **語言:** 繁中為主,公文體
- **資料敏感度分 3 級:**
  - Level 01(公開) — 行銷文案、通案研究 → 雲端 Claude API
  - Level 02(一般) — 招標須知、服務建議書(去識別化後) → 雲端 Claude
  - Level 03(機敏) — 選情、客戶機敏、未公告標案內情 → **絕不上雲** · 只能本地處理
- **使用情境典型例子:**
  - A 看到 60 頁招標 PDF → 10 分鐘 Go/No-Go 判斷 → 產服務建議書初稿
  - B 活動執行 → 3D 場景 Brief + 舞台動線 + 廠商比價 + 現場 checklist
  - C PM 交辦 → 設計師收到結構化設計 Brief → AI 生圖 → 多渠道素材適配
  - D 新聞稿 3 分鐘產出 · 社群月計劃批次產 · Email 公文體草稿
  - E 結案 3 小時→30 分 · 客戶 CRM 用聊天記錄

---

## 2. 技術棧(**不可替換**)

| 層 | 選擇 | 版本鎖 |
|---|---|---|
| 硬體 | Mac mini M4 24GB / 512GB(本地部署) | — |
| OS | macOS Sequoia | — |
| 容器 | Docker Desktop for Mac | — |
| AI Platform | LibreChat | `v0.8.4`(pinned) |
| AI Model | Claude (Opus 4.7 / Sonnet 4.6 / Haiku 4.5) | Anthropic Tier 2 |
| DB | MongoDB 7 | — |
| Search | Meilisearch 1.12 | — |
| Reverse Proxy | Nginx 1.27 | — |
| Backend | FastAPI (Python 3.12) | 統一會計 + 專案 + CRM + Orchestrator + Safety |
| 遠端連線 | Cloudflare Tunnel + Access(Email 白名單 + 2FA) | — |
| 監控 | Uptime Kuma | — |
| 前端 | 無框架 · 原生 ES Modules + `<template>` + 單 CSS 檔 | 無 build step |
| 語音 | Web Speech API(瀏覽器內建,zh-TW) | — |
| 外部工具 | Fal.ai(Recraft v3 繁中生圖)、g0v PCC API(標案監測) | — |

**不接受的技術提案:**
- 換前端框架(React/Vue/Svelte) — 10 人不值得
- 換 AI 平台(Open WebUI / LobeChat) — 已決定 LibreChat
- 換雲端 AI(OpenAI / Gemini) — 已決定 Anthropic
- 引入 k8s / service mesh / message queue
- 建 CI/CD 過度流程(GitHub Actions 簡單 lint+test 可接受)

---

## 3. 架構現況(2026-04-21)

### 3.1 容器佈局(6 個)

```
nginx (80) ──── / 與 /static/*  → frontend/launcher (靜態)
             ├─ /chat /c/*     → librechat (但 Route A 會 302 轉回 /)
             ├─ /api/*          → librechat:3080 (SSE 代理)
             ├─ /api-accounting → accounting:8000 (FastAPI)
             └─ /chengfu-custom → 注入 LibreChat 的客製 CSS/JS

librechat (3080) ─── MongoDB + Meili + Claude API
accounting (8000) ── 同 MongoDB · 40+ endpoints
mongo (27017) ──── LibreChat + accounting 共用 DB=chengfu
meili (7700) ──── 對話全文搜尋
uptime (3001) ──── 服務監控
```

### 3.2 前端(路線 A:Launcher 接管,LibreChat 只當後端 API)

- `frontend/launcher/index.html` · 7 個 view(Dashboard / Projects / Skills / Accounting / Tenders / CRM / Workflows / Admin)
- `frontend/launcher/app.js`(493 行 · ES module entry)
- `frontend/launcher/launcher.css`(2063 行,合併後單檔)
- `frontend/launcher/modules/`
  - 基礎:`config.js` / `util.js` / `auth.js` / `tpl.js`
  - UI:`modal.js` / `toast.js` / `palette.js` / `shortcuts.js` / `health.js` / `mobile.js`
  - 功能:`chat.js`(SSE 串流) / `voice.js`
  - Views:`accounting.js` / `admin.js` / `crm.js` / `tenders.js` / `workflows.js`
  - Store:`projects.js`(API + localStorage fallback)
  - `errors.js`(global error handler)
- 設計:macOS 設計語言(SF Pro / PingFang TC、毛玻璃、5 Workspace 彩色分組)
- 快捷鍵:⌘K palette、⌘1-5 Workspace、⌘6-9 進階 Agent、⌘0 首頁

### 3.3 後端(`backend/accounting/main.py`)

統一 FastAPI,40+ endpoints 分六大區:
- **Accounting** — 科目、交易、發票、報價、P&L、Aging
- **Projects** — CRUD + 全公司共享
- **Feedback** — 👍👎 收 LibreChat message 滿意度
- **Admin** — Dashboard(成本/品質/用量) + CSV 匯出
- **CRM** — Leads + 8 階段 Kanban + 從標案匯入
- **Safety** — L3 classifier(審訊息前預檢機敏資料)
- **Tenders** — g0v PCC cron 每日抓新標案
- **Memory** — `/memory/summarize-conversation`(壓縮對話節 token)
- **Orchestrator** — Multi-Agent workflow presets(投標/活動/新聞發布)
- **Safety classifier** · L3 關鍵字 + 格式比對

### 3.4 10 個 Agent(已在 LibreChat 建好 · 全公司可見)

| # | 名 | 模型 | Workspace |
|---|---|---|---|
| 00 | ✨ 主管家(Router) | Opus | 入口 |
| 01 | 🎯 投標顧問 | Sonnet | ⌘1 |
| 02 | 🎪 活動規劃師 | Sonnet | ⌘2 |
| 03 | 🎨 設計夥伴 | Sonnet | ⌘3 |
| 04 | 📣 公關寫手 | Sonnet | ⌘4 |
| 05 | 🎙️ 會議速記 | Haiku | /meet |
| 06 | 📚 知識庫查詢 | Sonnet | /know |
| 07 | 💰 財務試算 | Sonnet | ⌘5 支線 |
| 08 | ⚖️ 合約法務 | Sonnet | /tax |
| 09 | 📊 結案營運 | Sonnet | ⌘5 主線 |

每個 Agent 的 system prompt 在 `config-templates/presets/*.json`,被 `scripts/create-agents.py` 讀入並 POST 到 `/api/agents`。

### 3.5 知識體系

- `knowledge-base/company/` — Company Memory(品牌、禁用詞、格式)
- `knowledge-base/skills/` — 承富 12 Skills(招標解析、新聞稿 AP Style、毛利框架...)
- `knowledge-base/claude-skills/` — Anthropic 官方 17 Skills
- `knowledge-base/openclaw-reference/` — OpenClaw 生態參考
- `SKILL-AGENT-MATRIX.md` — 主管家路由表

---

## 4. 當前狀態(DoD 視角 · v4.3 · 2026-04-21)

### ✅ 程式碼完成度:**95%**(已通過 3 輪內部審查)
- 6 容器全 healthy · 10 Agent 全建立 + 共享 `instance` global project
- 前端 v4.3 · ES Modules · 無 build step · 單檔 CSS · Path A 內建 chat
- UX:3 步 onboarding(對齊老闆 top 3)· 術語全中文化 · 5 狀態卡 · banner · focus visible
- 快捷鍵:⌘K / ⌘1-5 工作區 / ⌘6-9 進階助手 / ⌘0 首頁
- Dashboard ROI 三儀表:本月預算進度條 + 標案漏斗 + 本週完成數
- 後端:13 個 /admin/* endpoint 全 RBAC / CORS whitelist / Request-ID + JSON log / Mongo 7 indexes
- 契約測試:`smoke-librechat.sh` 11 pass · `pytest` 18 pass
- 保護網:`backup.sh` 已接 rclone off-site、`start.sh` 有 CI 護欄 + image stale guard、`LIBRECHAT-UPGRADE-CHECKLIST.md`

### 📚 教材完成度:**85%**
- `QUICKSTART.md`(10 分鐘 3 任務)· `CASES/01-海廢案端到端.md`(5 天投標完整走一遍)
- `HANDBOOK/` 4 份角色手冊(老闆 / PM / 設計 / 業務)
- `NAS-INTEGRATION-SPEC.md` + `LINE-WORKFLOW-SPEC.md` · 等承富答 5 問再動工
- `PRE-DELIVERY-CHECKLIST.md` · 交付週逐日打勾
- `BASELINE.md` · T0 量測模板

### 🔴 部署落地完成度:**35%**(= 老闆感受到的交付價值)
- [ ] Mac mini 未上架、Cloudflare Tunnel 未接 · 同仁目前只有作者本機能用
- [ ] `knowledge-base/samples/` 空目錄 · **承富真實建議書 / 結案報告 0 份已灌**
- [ ] 10 同仁帳號未建 · 密碼 reset SOP 未寫
- [ ] 2 場教育訓練未辦
- [ ] 異機備份 rclone 未設 remote
- [ ] T0 baseline 未填(ROI 無對比基準)

**= 系統已經寫完 · 但沒人能用 · 6 個月後無法證明 ROI。**
**這是交付經理(Sterio)要在交付前 1 週手動落地的事,不是再改程式碼。**

### ⚠️ 明確延後到 v1.1 的項目
- Google Drive MCP(老闆實際在 NAS + LINE · 優先級降)
- Fal.ai Recraft v3 真生圖(設計夥伴目前只產 prompt 給同仁自己去生)
- 附件 PDF 真實上傳(目前 UI 關閉 · 靠複製貼上)
- Multi-agent workflow 自動串接(目前是關閉的 empty-state)
- 跨助手 handoff 結構化交棒
- Company Memory(跨對話記憶)
- per-user token hard stop(現在只有儀表,未做閘門)
- L3 硬擋(老闆:先不考慮)

---

## 5. 審查範圍與要求(v4.3 · 3 輪後剩下的未解題)

請對以下 **6 個層面** 各自給出報告。每個層面輸出格式:

```
層面:XXX
完成度:[%](程式碼/部署/教材 分別給)
🔴 關鍵問題(必修): N 個
  1. [問題] · 影響:XX · 修法:YY · 預估工時:Z h
🟡 改善建議(建議修):N 個
🟢 做對的地方(保留):N 個
🚀 加分建議(v1.1/v1.2):N 個
```

⚠️ **前面「3 輪已修清單」列的問題請勿重複指出** · 直接跳到下面的未解題:

### 5.1 前端(已穩 · 尋找盲點)

✅ 已做:ES modules 19 檔、`<template>+cloneNode`、SSE pop 修、auth retry/Web Locks、focus visible、3 步 onboarding、術語中文化。

**你該問的:**
- 長列表 render 效能 — CRM Kanban 100+ 張卡、標案監測 50+ 筆會 jank 嗎?
- 多分頁同開 — localStorage 給 Projects fallback · 多分頁會髒 data 嗎?
- 錯誤邊界 — `errors.js installGlobalErrorHandler` 只 toast · `unhandledrejection` 遮了實情嗎?
- `onclick=` 在 HTML 還剩幾個?要不要繼續清?
- `renderMarkdown` 手刻 regex 能處理中英混排 + code block + 巢狀 list 嗎?
- i18n · 未來英文同仁加入時 · 現有寫死繁中的字串怎辦?

### 5.2 後端(RBAC + CORS + Request-ID 已就位)

✅ 已做:13 /admin/* 全套 `require_admin`、CORS whitelist、`import json` 修、regex injection 修、Mongo 7 indexes、RequestID middleware 涵蓋 5xx、pytest 18 pass。

**你該問的:**
- `main.py` 仍 1300+ 行單檔 — 拆 routers/ 的優先度?拆哪區 CP 值最高?
- LibreChat transactions collection 是否保證有 `user` / `rawAmount.prompt` 欄位?若 LibreChat 升版改 schema · top-users endpoint 會 silently 壞掉
- Request-ID 有寫 resp.headers · 但 app 內部呼叫 `HTTPException` 不會經過 middleware — 需驗證
- Mongo auth · 目前 `mongodb:27017/chengfu` 無密碼(Docker 內網)· Cloudflare Tunnel 上線後如何?
- Anthropic 定價硬編碼在 `_ANTHROPIC_PRICING_USD` — Anthropic 調價 → 需手動改 · 有沒有更穩的做法?
- `/admin/top-users` 的 `_users_col.find_one({"_id": ObjectId(uid)})` · 若 uid 是舊格式 string 會炸嗎?

### 5.3 LibreChat 整合(契約 smoke 已就位)

✅ 已做:Route A(302 + sub_filter + kill-sw)、uaParser UA workaround、`projectIds: [instance._id]` 共享、SSE delta.content parser、`scripts/smoke-librechat.sh` 11 pass、`LIBRECHAT-UPGRADE-CHECKLIST.md` 含 agent _id dump。

**你該問的:**
- 升 v0.8.5 / v0.9 的風險評估:哪些**行為**最可能變?(不是 schema · 是運行時行為)
- `modelSpecs` 還沒啟用(hard-pin agent_id)· 啟用後 + 升版 = 兩層風險 · 順序應該怎麼排?
- Route A 的 `/c/new → /` 302 靠 nginx 單點 · LibreChat 改 SPA router 成 hash `#/c/new` 會怎樣?
- LibreChat 的 `transactions` collection 是**假設存在** · 若他們改名或停用,後端 cost endpoint 全掛
- 共享 `instance` project 的 LibreChat semantics · 未來若引入其他 Agent 的 organization 會相容嗎?

### 5.4 功能強化(老闆答案改變優先級後)

✅ 已降級:Google Drive MCP(老闆實際在 NAS/LINE)、L3 硬擋(老闆:先不考慮)、附件上傳(關閉入口等 v1.1)、Workflow(empty-state 關閉等 v2.0)。

**你該問的(按老闆 top 3 聚焦):**
- **設計夥伴(top 1)** — 現只產 prompt 給同仁自己去別處生圖 · Fal.ai Recraft v3 串接的最小可交付版是什麼?
- **投標顧問(top 2)** — 沒附件上傳,70 頁 PDF 同仁複製貼上會崩;OCR / paginated paste / external uploader 哪個先做?
- **活動(top 3)廠商** — NAS 廠商清單 CSV 沒接;「一鍵 5 家比價信」自動化門檻?LINE 群發會不會被 LINE 當 spam?
- **跨助手 handoff** — 結構化交棒卡(目標/限制/附件/待辦)· 怎麼最小可交付?放在 chat pane 還是 project 層?
- **Company Memory** — 老闆說先不考慮 L3,但「承富禁用詞 / 品牌語氣」是長期記憶,需要嗎?放 skill 還是 system prompt?

### 5.5 UX(v4.3 小白友善已做)

✅ 已做:術語全中文化、3 步 onboarding 對齊 top 3、👍👎 固定露出、5 空狀態卡、系統 banner、focus visible、L1-L3 badge、輸入框快捷鍵提示。

**你該問的(抗拒型資深同仁視角):**
- 「first-win」時間 — 資深同仁第一天 5 分鐘內能感受到「這東西讓我省了 X」嗎?還是要第 3 天才感覺到?
- 若老闆給的是老舊 Intel 筆電(不是 M 系列)· CSS backdrop-filter / ES modules 支援度?
- ⌘K palette 對不熟快捷鍵的資深同仁來講 · 真的會用嗎?還是需要一個固定按鈕?
- Handbook 分角色(老闆 / PM / 設計 / 業務)· 萬一一人身兼兩角色(PM + 業務),怎麼引導?
- `docs/CASES/01-海廢案端到端.md` 是唯一完整案例 · 夠嗎?第 2-5 個案例的優先順序是什麼?

### 5.6 流程 / 交付 / ROI(v4.3 落地缺口最大)

✅ 已做:3 ROI 儀表(budget/top-users/funnel)、PRE-DELIVERY-CHECKLIST、BASELINE 模板。

**你該問的(這是現階段最大盲區):**
- **T0 Baseline 填表**(`docs/BASELINE.md`)· 承富老闆真能答得出「上個月投了幾件」嗎?若答不出 · ROI 怎麼算?
- **per-user hard stop** 目前只有儀表 · 未做閘門 · 第 20 天花完預算時,系統會繼續燒嗎?
- **異機備份** rclone 雖已接 · 但**沒有「定期 restore 驗證」**,備份是虛的
- **搜尋深度** · ⌘K 只搜 Agent/專案/Skill · 不搜對話 · 不搜 NAS · 承富真有多少時間是在找過往檔?
- **審計軌跡** · 某份得標建議書 · 能回答「誰產的 / 哪個 Agent / 什麼 prompt 版本 / 花多少 token」嗎?若不能 · 真遇到客戶糾紛時會掛
- **交付當天** · 10 人拿紙條登入後 · 卡在哪個畫面會最多?有沒有「第 1 天 FAQ Top 10」預期稿?

---

## 6. 決策限制

**請不要建議以下事項:**
- 換 LibreChat / Claude / Mac mini / Python / FastAPI
- 改 Agent 數量(就是 10 個)
- 加/減 Workspace(就是 5 個)
- 改主色(就是 `#0F2340` 承富藍)
- 引入 GraphQL / gRPC / WebSocket(SSE 已夠)
- 引入 Redis / RabbitMQ / Kafka(10 人不需要)
- SaaS 化 / 多租戶(單租戶,10 人封閉環境)

**請積極建議以下事項:**
- 任何能**省時間**的自動化
- 任何能**防錯**的流程(Level 03 誤送、Agent 選錯、預算超支)
- 任何能**讓資深同仁少抗拒**的 UX 改善
- **成本監控與控管**(尖峰不會爆預算)
- **失敗復原**(Mac mini 壞掉、網路斷、Claude API 掛掉怎麼繼續營運)

---

## 7. 輸出要求

### 7.1 總論(一段)
不超過 150 字,你對這系統的**一句話評價** + **最該做的 3 件事**(按優先序)。

### 7.2 6 個層面各一份報告
按 5.1-5.6 格式,每份 400-600 字。

### 7.3 路線圖
把所有建議 consolidate 成一個**依序執行**的路線圖:

| 階段 | 目標 | 關鍵行動 | 預估工時 | CP 值 |
|---|---|---|---|---|
| P0(本週必做) | ... | ... | ... | 🔴🔴🔴 |
| P1(2 週內) | ... | ... | ... | 🔴🔴 |
| P2(v1.1) | ... | ... | ... | 🔴 |
| P3(v1.2+) | ... | ... | ... | 🟡 |

### 7.4 紅線清單
列出你審查時發現的 **絕對不能留到交付** 的項目(會讓系統不可用、造成資安事故、或讓 10 人直接放棄使用的東西)。

---

## 8. 附加參考資料(若 reviewer 問)

### 產業與公司
- **產業慣例:** 承富主要接台灣政府標案,公文體嚴格、截止時間剛性、評審重視視覺完整度
- **預算:** AI 月預算 NT$ 12,000(Buffer 後實際目標 NT$ 8,000)
- **時程:** 要 4 週(或 5 週順延條款)交付全員可用
- **決策者:** 承富老闆 + 一位 Champion 同仁(對 AI 相對熱心)
- **反對者:** 預估 2-3 位資深同仁對 AI 有抗性,需特別照顧

### 老闆親自回答的 5 題(這是 v4.2+ 優先級調整的依據)
1. **每週 Top 3 任務:** 設計 / 提案撰寫 / 廠商聯繫
2. **80% 原始檔在哪:** LINE/群組 + NAS(不是雲端 Drive)
3. **L3 機敏規則:** **先不考慮**(不要再建議硬擋 L3)
4. **老闆最在意:** 省時 + 接案量(**不是**風控,不要過度強調資安)
5. **維運資源:** 外包工程師 20h/週 · 透過 Claude Code 遠端 · Champion 靠教學手冊 + 案例演示**自主學習**

→ 建議請**圍繞這 5 題** · 偏離(例如建議做「L3 全面硬擋」、「Google Drive 整合」、「加強資安審計」)會被否決。

### 已做的量化成果(你引用這些當對比基礎)
- 10 Agent 建立成功(MongoDB 驗證 10 筆 · 全 `projectIds: [instance._id]`)
- 18 pytest / 11 smoke 全 pass
- `backend/accounting/main.py` 從 46953 bytes → 52700 bytes(加 CORS + RBAC + request_id + ROI endpoints + index)
- `frontend/launcher/app.js` 從 2064 行單檔 → 493 行 orchestrator + 19 個 modules
- `docs/` 從 9 個檔 → 19 個檔(加 QUICKSTART/CASES/HANDBOOK×4/2 SPEC/PRE-DELIVERY/BASELINE/UPGRADE/ROADMAP-v4.2)
- GitHub repo:<https://github.com/Sterio068/chengfu-ai>(public · 免認證可讀)

---

## 9. 格式要求

- 繁體中文
- 技術詞彙可保留英文(API / JWT / SSE / RAG)
- 避免大陸用語(視頻→影片、數據→資料)
- 金額用 `NT$ X,XXX`
- 日期用 `2026 年 4 月 21 日`
- 檔案路徑一律**絕對路徑 + 行號**(`/Users/sterio/Workspace/ChengFu/xxx.py:123`)· 讓 Sterio 一跳就到

---

## 10. 這份文件的上下文脈絡(給 reviewer 省時)

### 這系統不是 prototype · 已經在作者本機跑了
- 6 容器 healthy · 10 Agent 共享 · smoke 11 pass · pytest 18 pass
- 本機可直接 `./scripts/start.sh` · <http://localhost/> 可用
- 尚未上 Mac mini(硬體採購中)· 尚未對外 · 尚未教育訓練 10 人

### 作者 Sterio 本人有限制:
- Sterio 懂技術 · 但承富內部人不懂
- 每個技術決策都有「能讓外包工程師用 Claude Code 接手」的 constraint
- 任何「只有 Sterio 能維護」的解法 = 技術債

### 這份文件被審查的歷史:
- **v1:** 原版 · 被一個外部 reviewer 審了 1 次(紅線:附件假成功 / admin 裸奔 / Workflow alert / Token 過期)
- **v2:** 修完 v1 紅線後,跑了**內部 3 輪多代理審查**(每輪 3-4 agent)· 又修了 22 條
- **你(v3):** 現在讀這份 · 預期你找到新的 · **不要重複指出已修的**

---

## 11. 結尾 · 若你是這個顧問,你會最先想問作者什麼?

請在報告最末列出 **3-5 個你認為回答後能大幅改善下輪審查的問題**。這些問題會被帶去跟承富老闆或 Sterio 討論 · 回答後會寫進 Section 8 成為下一輪 reviewer 的脈絡。

---

**感謝審查。請直接開始,不用先確認。**

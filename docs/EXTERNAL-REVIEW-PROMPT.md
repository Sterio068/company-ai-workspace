# 承富 AI 系統 · 外部審查請求

> **使用說明:** 把整份文件貼給外部 reviewer(可以是另一個 AI 如 GPT-5 / Gemini / Claude Opus,也可以是人類顧問)。
> 他們應該能從頭到尾讀完後,不用再追問背景,就給出具體可執行的建議。
>
> **完整專案原始碼(public repo · 免認證可讀):**
> - GitHub 網址:<https://github.com/Sterio068/chengfu-ai>
> - Clone:`git clone https://github.com/Sterio068/chengfu-ai.git && cd chengfu-ai`
> - 專案根目錄 = repo 根(所有相對路徑如 `frontend/launcher/app.js` 都直接可讀)
>
> **本機開發路徑(作者的 Mac mini · 若是跟作者同場討論時參考):**
> - Project root:`/Users/sterio/Workspace/ChengFu`
> - 所有相對路徑(如 `frontend/launcher/app.js`)皆以此為根
> - 本機已跑:`./scripts/start.sh` · 瀏覽器開 <http://localhost/>
>
> **若 reviewer 只想看關鍵檔而不 clone,優先讀這幾份:**
> - `CLAUDE.md` · `SYSTEM-DESIGN.md` · `ARCHITECTURE.md` · `docs/DECISIONS.md`
> - `frontend/launcher/index.html` · `app.js` · `launcher.css` · `modules/*.js`
> - `frontend/nginx/default.conf`
> - `backend/accounting/main.py`
> - `scripts/create-agents.py`
> - `config-templates/librechat.yaml` · `docker-compose.yml` · `.env.example`

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

## 4. 當前狀態(DoD 視角)

### ✅ 已完成
- 容器 6 個全部 healthy
- 10 Agent 全建立 + 全公司共享
- Launcher UI 對齊原 mockup(5 Workspace 卡 + 全域工具 + Inspector 三欄)
- ⌘K / ⌘1-5 快捷鍵
- 深淺色、毛玻璃
- Path A 內建 chat pane(SSE 串流 + 👍👎 feedback + 歷史對話)
- 會計 / 專案 / CRM / Admin / 標案監測 view
- L3 safety classifier 送出前預檢
- macOS Keychain 管理機密(JWT / ANTHROPIC_API_KEY / Meili key 等)
- 一鍵啟動 `./scripts/start.sh`(自動開 Docker Desktop)

### ⏳ 未完成(但確定要做)
- 10 個同仁帳號建立(`scripts/create-users.py`)
- 承富過往檔案上傳建 RAG 索引(`scripts/upload-knowledge-base.py`)
- Cloudflare Tunnel 對外(Access policy + 2FA)
- 2 場教育訓練(全員 Onboarding + 進階分層)
- 備份 cron(`scripts/backup.sh` 每日 MongoDB dump)
- 驗收 DoD 簽收

### ⚠️ 已知問題 / 技術債
- `chat.js:167` SSE `buffer = events.pop()` 可能吞最後一個 event(需 `?? ""`)
- `tenders.js:16` filter chip listener 重複綁(切 view 疊加)
- `auth.js` `_jwt` 過期沒自動 retry refresh
- 35 處 inline `onclick=` 在 HTML 裡(應改 event delegation)
- `renderMarkdown` 手刻 regex(不嚴謹,應改 `marked` 或小 DSL)
- 前端無 E2E 測試
- 後端無 pytest 完整覆蓋(只有 `test_main.py` 14 項 smoke)
- 沒有容錯 retry 機制(任何 API 失敗就 toast 就結束)
- 沒有整合 Google Drive MCP(v1.0 範圍含)
- 沒有月度 `propose-skill.py` 自動建議新 skill(v1.1 雛形)
- 沒有 `tender-monitor.py` cron 實際跑起來(需 launchd)
- 沒有 `dr-drill.sh` 壓測 / 災難演練實際跑過

---

## 5. 審查範圍與要求

請對以下 **6 個層面** 各自給出報告。每個層面輸出格式:

```
層面:XXX
完成度:[%]
🔴 關鍵問題(必修): N 個
  1. [問題] · 影響:XX · 修法:YY · 預估工時:Z h
  ...
🟡 改善建議(建議修):N 個
  1. ...
🟢 做對的地方(保留):N 個
  1. ...
🚀 加分建議(v1.1/v1.2):N 個
  1. ...
```

### 5.1 前端優化

- **代碼品質** — ES module 邊界、state 管理、listener 洩漏、async 錯誤處理
- **效能** — 初次載入時間、動畫 jank、長列表 render、SSE 處理效率
- **無障礙** — 鍵盤操作、螢幕閱讀器、focus 順序、對比度
- **錯誤處理** — 後端離線、token 過期、網路中斷、ESM import 失敗
- **構建** — 無 bundler 的路徑 ok 嗎?未來要不要加 Vite?
- **狀態同步** — 多分頁同時開,projects/crm/會計狀態會打架嗎?

### 5.2 後端優化(FastAPI)

- **API 設計** — RESTful 貫徹度、錯誤格式統一、OpenAPI schema 完整度
- **MongoDB 使用** — 有沒有 N+1、索引、aggregation pipeline 效率
- **Auth** — FastAPI 跟 LibreChat 沒直接共用 JWT,共享 MongoDB 夠不夠?
- **Observability** — 日誌格式、trace id、error 可追蹤性
- **可測試性** — 單元測試覆蓋、mock 策略、fixture
- **災難恢復** — 備份週期、RTO / RPO 定義、DR drill 流程
- **安全** — 輸入驗證、SQL/NoSQL injection、CSRF、CORS、rate limit

### 5.3 LibreChat 整合

- **v0.8.4 版本選** — 跟 v0.8.5+ 差距大嗎?升級阻礙?
- **Agent 共享策略** — 現用 `projectIds: [instance._id]`,是不是最佳?
- **Route A 實作** — nginx 302 /c/new → / + 注入 relabel.js 擋 SPA,夠穩?
- **SSE 串流** — `/api/ask/agents` 的 payload 格式有沒有 breaking change 風險?
- **uaParser 偽裝** — `scripts/create-agents.py` 送假 Chrome UA,這 workaround 合理嗎?
- **成本控管** — per-user token 上限、模型預設 Haiku、能看到實際費用嗎?

### 5.4 功能強化(Feature Gaps)

- **缺的功能** — 比對 PDF 提案承諾,哪些還沒做?
- **Google Drive MCP** — v1.0 含但還沒接,優先級?
- **月度 Learning** — AI 自己提議新 skill(v1.1),怎麼做最小可行?
- **多 Agent Workflow** — 現有 orchestrator API,實際怎麼讓員工觸發?
- **Skill 自動載入** — Agent 要怎麼判斷該調哪個 skill?現在是靠 system prompt 硬寫
- **Company Memory** — 跨對話持久記憶要不要加?怎麼避免 prompt bloat?
- **Chrome Extension** — 同仁從任何網頁一鍵送承富 AI,這個必要嗎?
- **行動版** — 真的有必要嗎?現況是 768px 斷點 + mobile drawer

### 5.5 UX 進化

- **資訊架構** — 5 Workspace + /slash 工具 + Dashboard,對 10 人真的夠直覺?
- **AI 小白友善** — 資深同仁會不會還是看不懂「Agent」「Skill」這些字?
- **第一次使用** — Onboarding 4 步夠不夠?要不要加 interactive demo?
- **錯誤狀態 UI** — API 離線、Agent 未建、Level 03 警告,表達夠清楚?
- **空狀態** — 尚無專案、尚無對話、尚無標案,引導夠不夠?
- **進階 vs 基本** — 管理員看到進階設定,同仁不該看到,現在的 `[data-role="admin"]` 夠嗎?
- **打字體驗** — chat 輸入框送出、Shift+Enter 換行、檔案拖拉,有什麼可以更絲滑?
- **回饋機制** — 👍👎 按鈕目前藏在 hover,要不要更明顯?

### 5.6 使用體驗 + 流程改進

- **典型 Journey 斷點** — PM 從看 PDF → Go/No-Go → 建議書 → 簡報,中間哪裡會卡?
- **跨 Agent 接力** — 投標顧問產建議書 → 設計夥伴接手做 KV,狀態怎麼傳?
- **專案為核心還是對話為核心?** — 現在是對話優先,專案 metadata 是附加。換個方向會不會更好?
- **團隊協作** — 同一個專案多人同時聊 Agent,對話不分開會不會亂?
- **記憶強度** — 沒加 Company Memory 之前,每次都要重講公司背景,這有多煩?
- **成本透明** — 同仁看得到自己這月花多少 token 嗎?超額會怎樣?
- **搜尋** — ⌘K 能搜對話嗎?搜知識庫嗎?搜標案嗎?目前只搜 Agent+Project+Skill
- **通知** — 新標案 / 對話被 mention / Agent 完成 workflow,要不要推播?
- **審計軌跡** — 某份建議書是誰、什麼時候、用哪個 Agent、哪版 prompt 產的?

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

- **產業慣例:** 承富主要接台灣政府標案,公文體嚴格、截止時間剛性、評審重視視覺完整度
- **預算:** AI 月預算 NT$ 12,000(Buffer 後實際目標 NT$ 8,000)
- **時程:** 要 4 週(或 5 週順延條款)交付全員可用
- **決策者:** 承富老闆 + 一位 Champion 同仁(對 AI 相對熱心)
- **反對者:** 預估 2-3 位資深同仁對 AI 有抗性,需特別照顧

---

## 9. 格式要求

- 繁體中文
- 技術詞彙可保留英文(API / JWT / SSE / RAG)
- 避免大陸用語(視頻→影片、數據→資料)
- 金額用 `NT$ X,XXX`
- 日期用 `2026 年 4 月 21 日`

---

## 10. 結尾 · 若你是這個顧問,你會最先想問我什麼?

請在報告最末列出 **5 個你認為回答後能大幅改善你審查品質的問題**,讓我(這份文件的作者)知道下次該補哪些脈絡進來。

---

**感謝審查。請直接開始。**

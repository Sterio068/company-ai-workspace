# CLAUDE.md — 承富 AI 系統建置任務

> 這是 Claude Code 啟動時讀取的主控檔。
> 先讀 `docs/DECISIONS.md` 了解**最新決議**,再讀 `SYSTEM-DESIGN.md` 了解設計語言。
> 逐階段執行 `tasks/` 下的 week-0 → week-4。
> **決策優先順序**:`docs/DECISIONS.md` > 本檔 > 其他文件。若衝突,以 DECISIONS.md 最新條目為準。

---

## 0. 必讀檔案順序

1. **這份 `CLAUDE.md`**(先讀,了解目標與原則)
2. **`docs/DECISIONS.md`**(最新已決議 + 待決議項,與本檔衝突時以此為準)
3. **`SYSTEM-DESIGN.md`**(設計語言、UX 流程、macOS 設計規範)
4. **`ARCHITECTURE.md`**(技術架構、資料流、元件)
5. **`tasks/week-0-prep.md`**(動工前承富確認清單)
6. **`tasks/week-1-hardware-env.md`** ~ week-4(開始動手)

---

## 0.5 術語與版本說明(2026-04-18 更新)

LibreChat v0.8+ 將 Preset 功能退為次要,推薦以 **Agent** 為主要工作單位。
本專案文件為保持既有 JSON 命名連續性,仍稱「29 個 Agent」,實作一律建 Agent。

| 舊稱(文件內) | 新稱(實作中) | 說明 |
|---|---|---|
| Preset | **Agent** | LibreChat v0.8+ 官方主力載體 |
| `config-templates/presets/` | 同路徑,不改名 | JSON 為 Agent 的 **system prompt 來源**(source of truth) |
| 匯入 Preset | 建立 Agent | Week 3 透過 Agent Builder UI 或 LibreChat API 建立 |

JSON 檔欄位對應:`promptPrefix` → Agent `instructions`;`model` / `temperature` / `max_tokens` 直接映射;`tags` 用於 modelSpecs 分組。

---

## 0.6 已決議事項摘要(詳見 `docs/DECISIONS.md`)

- **D-001 · v1.0 範圍**:29 Agent **精簡為 10 職能 Agent**(Router + 9 專家 · 涵蓋 PDF 提案 100% 功能)
- **D-002 · Anthropic API**:Week 0 內升 Tier 2(預存 USD $50)
- **D-003 · Mac mini 規格**:採購 **24GB RAM** 版本
- **D-004 · 會計系統**:**內建** FastAPI 模組(不接外部)· 台灣格式支援
- **D-005 · 外部工具**:Fal.ai 生圖(Recraft v3 繁中最好)· g0v PCC API 查標案
- **D-006 · Claude 全功能**:Artifacts / Vision / Extended Thinking / Web Search / Code Interpreter 全開
- **D-007 · LibreChat 版本**:pin `v0.8.4`(2026-03-20 釋出穩定版)
- **D-008 · Skills 體系**:承富 12 + Anthropic 官方 17 + OpenClaw 參考 + SKILL-AGENT-MATRIX 中央路由
- **D-009 · Level 4 Learning 雛形**:Prompt Caching 啟用、monthly-report API、propose-skill.py AI 建議新 skill
- **D-010 · Level 5 Autonomous 雛形**:主管家 Orchestrator + 3 個預設 workflow(投標全閉環 / 活動完整企劃 / 新聞發布閉環)
- **D-011 · 自動化運維**:tender-monitor cron(每日查新標案)、Uptime Kuma、dr-drill.sh、k6 壓測、GitHub Actions CI
- **D-012 · Chrome Extension**:同仁從任何網頁一鍵送到承富 AI(右鍵選單 + ⌘⇧C 快捷鍵)

---

## 1. 專案目標

為**承富創意整合行銷有限公司**(10 人公關行銷公司,台灣)建置一套**本地部署的 AI 協作系統**,以 LibreChat 為協作中樞、Claude API 為主力模型,四週內讓全員可用(若 D-001 觸發順延條款,可延至第 5 週)。

**核心成功條件**:
- 部署於承富辦公室的 Mac mini M4,系統完全自有
- 同時支援 10 位同仁並行使用
- 對話紀錄、知識庫、用量統計 100% 本地儲存,不上雲
- 從公司內網或 Cloudflare Tunnel 遠端皆可使用
- 第 28 天(或順延至第 35 天)全員上線並實際產出

**UX 成功條件(macOS 設計語言)**:
- 5 個 Workspace 資訊架構,29 個 Agent 有邏輯分群,不是平鋪下拉
- ⌘K 全域指令面板可用
- ⌘1-5 快速切換 Workspace
- 深 / 淺色模式支援
- 系統感官接近 macOS 原生 app(毛玻璃、圓角、SF 字體、輕陰影)

---

## 2. 技術棧(不可替換)

| 組件 | 選擇 | 理由 |
|---|---|---|
| 硬體 | **Mac mini M4 (24GB/512GB)** | D-003 決議升級,避免尖峰瓶頸 |
| UPS | APC/飛瑞入門款 | 防停電資料損壞 |
| 作業系統 | macOS Sequoia(隨機) | 無須改 OS |
| 容器化 | Docker Desktop for Mac | LibreChat 官方推薦 |
| AI 協作平台 | LibreChat(v0.7.6+ 穩定版) | 開源、多供應商、Claude 原生支援、原生 Agent/file_search/STT |
| 主力模型 | Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 | 依任務複雜度切換 |
| API 級別 | Anthropic Tier 2(D-002) | 10 人尖峰需要 1000 RPM |
| 遠端連線 | Cloudflare Tunnel | 免費、免開 port、加密 |
| 語音轉文字 | LibreChat 原生 STT | v0.8+ 內建,不需單獨 whisper 容器 |
| 階段二(選) | Ollama + Qwen 2.5 / TAIDE | 極敏感資料離線推論 |

**不要**自行引入其他框架(如 Open WebUI、LobeChat、AnythingLLM)。

---

## 3. 交付定義(Definition of Done)

整個專案在**第 28 個工作日結束**時必須滿足(若 D-001 順延觸發,延至第 35 日):

### 功能層
- [ ] 10 個同仁帳號已建立,密碼以安全方式交付各同仁
- [ ] LibreChat 可透過公司內網 `http://承富-ai.local` 存取
- [ ] 可透過 Cloudflare Tunnel `https://ai.<承富domain>.com` 存取
- [ ] 承富專屬的 **29 個 Agent**(source-of-truth 在 `config-templates/presets/`)已透過 Agent Builder / API 建立完畢
- [ ] 承富公司知識庫已上傳並由 LibreChat 原生 `file_search` 建立索引(含過往標書、結案報告、公司手冊)
- [ ] 用量控管後台可由管理員設 per-user 每月 token 上限
- [ ] 資料分級 SOP 文件印出貼牆(Level 01/02/03)
- [ ] 每個 Agent 有 3 個測試案例紀錄(Happy / Edge / Adversarial),詳見 `tasks/week-3-customization.md`

### UX 層(macOS 設計語言,見 SYSTEM-DESIGN.md)
- [ ] 首頁 Dashboard(不是直接進對話畫面),顯示 5 Workspace 卡片 + 最近對話 + 用量
- [ ] 5 Workspace 以 LibreChat modelSpecs 分組(方案 A)或客製 UI(方案 B)實現
- [ ] ⌘K 全域指令面板可用(支援 fuzzy search)
- [ ] ⌘1-5 快速切換 Workspace
- [ ] 深 / 淺色模式支援(跟隨系統或手動切換)
- [ ] 字型系統使用 SF Pro / PingFang TC(繁中)
- [ ] 毛玻璃側邊欄(backdrop-filter blur)
- [ ] 滑鼠 hover 反饋柔順(transition 200ms)

### 訓練與交付
- [ ] 2 場教育訓練完成,每位同仁實際產出至少 1 份真實工作成果
- [ ] 完整 SOP 手冊、交付說明書,以 PDF 給予承富
- [ ] 來自承富的**驗收簽收單**

---

## 4. 工作順序(改為「直接交付」架構)

> **不再分週**。以下為 `DEPLOY.md` 的 6 個 Phase,Mac mini 到貨後 1-2 個工作日內執行完 Phase 1-4,Phase 5-6 為訓練與驗收。

- **Phase 0 · 承富前置**(Mac mini 到貨前可做):採購 24GB、API 升 Tier 2、IT 配合、Baseline 量測、Champion 指派、10 同仁資料、知識庫檔案、合規確認
- **Phase 1 · 硬體作業系統**:Mac mini 開箱、UPS、FileVault、Docker Desktop、網路、主機名
- **Phase 2 · 部署平台**:Keychain 機密、`.env` 填值、`./scripts/start.sh`(nginx + LibreChat + Mongo + Meili)、smoke test
- **Phase 3 · Agent 與資料**:`create-agents.py`(29 個 Agent)、`upload-knowledge-base.py`、`create-users.py`
- **Phase 4 · 對外與安全**:Cloudflare Tunnel + Access + 2FA、備份 cron
- **Phase 5 · 教育訓練**:2 場(全員 Onboarding + 進階分層)見 `docs/03-TRAINING.md`
- **Phase 6 · 交付簽收**:驗收 DoD、交付 PDF、承富老闆簽收

**D-001 順延條款**:若 Phase 3 連續 2 天落後 > 20%,觸發與承富老闆順延討論(29 Agent 可分 v1.0 核心 10 + v1.1 延伸 19)。

---

## 5. 關鍵原則

### 資料主權
所有使用者對話、上傳檔案、向量索引**一律儲存在承富 Mac mini 本地**。
若 API 需要上傳檔案(例如給 Claude 分析 PDF),要先確認檔案屬於 Level 01(公開)或 Level 02(一般)。
Level 03(機敏)資料**絕不**送到雲端 API,改用階段二的 Ollama 本地模型處理。

### 成本控管
LibreChat 後台必須設定:
- 每位同仁每月 token 上限(輕度 200 萬 / 中度 150 萬 / 重度 300 萬)
- 全公司月預算上限 NT$ 12,000(預留 50% buffer 給推薦中度的 NT$ 8,000)
- 超過 80% 時 email 通知管理員
- 超過 100% 時自動暫停該使用者

### 模型選擇原則
- **預設 Haiku 4.5**:日常對話、簡短回覆、大多數任務
- **Sonnet 4.6 手動切換**:長文件分析、建議書初稿、複雜推理
- **Opus 4.7 例外用**:僅限重大決策輔助、關鍵提案、極複雜任務
- 管理後台依用量逐月調整模型比例

### 安全最低要求
- 所有服務帳號密碼不得明文存檔,使用 macOS Keychain
- Claude API key 必須存 Keychain(見 `scripts/setup-keychain.sh` 與 `docs/05-SECURITY.md`)
- `.env` 只存非機密欄位;機密由 `scripts/start.sh` 啟動時從 Keychain 注入
- Cloudflare Tunnel 必須加上 Access policy(Email 白名單 + 2FA)
- Mac mini 全盤加密(FileVault)必開

---

## 6. 承富特定配置

### 承富公司資訊
- 公司名:承富創意整合行銷有限公司
- 團隊規模:10 位同仁
- 產業:公關行銷、活動規劃、政府標案承接
- 據點:台灣(具體地址待確認)
- 主要客戶類型:政府機關(預估標案佔比待確認)、企業客戶

### 資料分級 SOP
| Level | 類型 | 處理路徑 |
|---|---|---|
| 01 · 公開 | 行銷文案、通案研究、已公告政府資訊 | → 雲端 Claude API |
| 02 · 一般 | 招標須知、服務建議書、預算分析、客戶會議紀錄(去識別化後) | → 雲端 Claude(去識別化) |
| 03 · 機敏 | 選情分析、客戶機敏、未公告標案內情、競爭對手情報 | → 階段一人工處理 · 階段二本地 Ollama |

### 29 個 Agent 以 5 Workspace 組織(詳見 `SYSTEM-DESIGN.md` 第 2 節)

**不要把 29 個 Agent 平鋪下拉選單**。必須以 5 個 Workspace 為單位設計 UI:

#### 🎯 Workspace 1:投標(⌘1)
完整閉環:看到招標須知 → 送件前最後一哩
- 25 標案 Go / No-Go 評估 ← 入口
- 01 招標須知解析器
- 02 服務建議書初稿助手
- 24 競品視覺研究
- 22 簡報視覺架構

#### 🎪 Workspace 2:活動執行(⌘2)
完整閉環:企劃到現場到驗收
- 09 3D 場景 Brief(A1)
- 11 舞台技術配置(A2)
- 12 活動動線與交通規劃(A3)
- 13 現場體驗流程設計(A4)
- 10 廠商比價表(B1)
- 14 委外合約初稿(B1 深化)

#### 🎨 Workspace 3:設計協作(⌘3)
完整閉環:PM ↔ 設計師溝通
- 20 主視覺概念發想(D1)
- 21 設計 Brief 結構化(D2)
- 27 AI 圖像生成輔助(D3)
- 28 多渠道素材適配(D4)
- 29 活動視覺系統(D7)

#### 📣 Workspace 4:公關溝通(⌘4)
對外發聲全流程
- 04 新聞稿生成器
- 05 社群貼文生成器
- 23 月度社群內容企劃(D6)
- 26 Email / 客戶溝通草稿
- 06 會議速記

#### 📊 Workspace 5:營運後勤(⌘5)
內部管理中樞
- 03 結案報告助手
- 15 專案報價與毛利試算(B2)
- 16 里程碑與風險追蹤(B3)
- 17 客戶 CRM 紀錄助手(B4)
- 18 NDA / 授權書 / 合約模板(B4)
- 08 稅務合約諮詢
- 19 新進同仁 Onboarding(B4)
- 07 公司知識庫查詢(原生 file_search)

**Workspace 設計不是 tag,是完整情境封裝**:每個 Workspace 有自己的封面、標準流程排序、近期對話、進階工具。使用者進入 Workspace 就像進入一個工作空間,不用跨 Workspace 尋找功能。

### 全域工具(從任何 Workspace 都能 inline 呼叫)
這些 Agent 用 **slash command** 呼叫,不進特定 Workspace:
- `/know` → 07 知識庫(跨 Workspace 查資料)
- `/email` → 26 Email 草稿
- `/vendor` → 10 廠商比價
- `/tax` → 08 稅務諮詢
- `/meet` → 06 會議速記

### 品牌語氣(全公司共用 system prompt)
- 用**繁體中文**回答
- 公文體例參照承富過往服務建議書
- 避免大陸用語(「視頻」→「影片」、「數據」→「資料」、「云」→「雲」)
- 金額固定用 NT$ 格式,如 NT$ 12,345
- 日期用西元年月日,如 2026 年 4 月 18 日

### MCP 整合(D-001 配套 · v1.0 含 Google Drive)
詳見 `docs/08-MCP-INTEGRATION.md`:
- **v1.0**:Google Drive(讀檔) — 降低「上傳 → 下載 → 貼入」摩擦
- **v1.1**:Gmail(寄草稿)、Calendar(排程會議)
- 所有 MCP 透過 LibreChat Actions / Agent tools 機制介接

---

## 7. 遇到問題怎麼辦

- **環境類問題**(Docker 起不來、Mac mini 網路): 參考 `docs/06-TROUBLESHOOTING.md`
- **LibreChat 設定**: 官方文檔 https://docs.librechat.ai
- **Claude API**: 官方文檔 https://docs.anthropic.com
- **Cloudflare Tunnel**: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks
- **災難復原(RTO/RPO)**: `docs/04-OPERATIONS.md`
- **人員異動 / PDPA**: `docs/05-SECURITY.md`
- **無法決定的設計決策**: STOP,寫進 `docs/DECISIONS.md` 並列為待確認項,不要擅自假設

---

## 8. 文件結構(2026-04-19 更新為 10 Agent + 會計 + Admin + Skills 體系)

```
ChengFu/
├── CLAUDE.md                           ← 你現在讀的這份(專案主控)
├── README.md                           ← 給承富老闆看的概覽
├── DEPLOY.md                           ← 【主運行手冊】Mac mini 到貨後的 1-2 天部署
├── SYSTEM-DESIGN.md                    ← 設計語言 · IA · UX · macOS 規範
├── ARCHITECTURE.md                     ← 技術架構詳解(已精簡為 3+1 容器)
├── mockup-launcher.html                ← macOS 風格首頁視覺 mockup(設計參考)
├── DESIGN-REVIEW.md  / v2 / v3         ← 五輪審視紀錄(75 個發現)
│
├── docs/
│   ├── DECISIONS.md                   ← 【優先】已決議 + 待決議項
│   ├── 03-TRAINING.md                 ← 2 場教育訓練教案(分層)
│   ├── 04-OPERATIONS.md               ← Day-2 維運 + RTO/RPO + 升級 SOP
│   ├── 05-SECURITY.md                 ← Keychain + PDPA + 人員異動
│   ├── 06-TROUBLESHOOTING.md          ← 常見問題集
│   ├── 08-MCP-INTEGRATION.md          ← Google Drive(v1.0)/ Gmail(v1.1)
│   └── DATA-CLASSIFICATION-POSTER.md  ← A3 海報內容(Level 01/02/03)
│
├── scripts/
│   ├── setup-keychain.sh              ← 首次:將機密寫入 Keychain
│   ├── start.sh                       ← 啟動:從 Keychain 注入並啟動 compose
│   ├── stop.sh                        ← 停止
│   ├── backup.sh                      ← 每日:MongoDB 備份(cron)
│   ├── create-agents.py               ← 批次建立 29 個 Agent via LibreChat API
│   ├── create-users.py                ← 批次建立 10 同仁帳號
│   ├── upload-knowledge-base.py       ← 承富知識庫批次上傳
│   └── smoke-test.sh                  ← 部署後驗收
│
├── frontend/                           ← 承富客製前端
│   ├── launcher/                      ← 首頁(Dashboard / Projects / Skills / Accounting / Admin)
│   │   ├── index.html                 ← 5 個 view · ⌘K palette · Onboarding tour
│   │   ├── styles.css                 ← macOS 設計 tokens
│   │   ├── app.js                     ← Projects API + Feedback API + Admin 儀表 + L3 classifier
│   │   └── onboarding.js              ← 首次 4 步引導
│   ├── custom/                        ← LibreChat 注入
│   │   ├── librechat-custom.css       ← 承富藍 / 放大字體 / 隱藏進階
│   │   └── librechat-relabel.js       ← 術語中文化 + 👍👎(POST MongoDB)+ 回首頁
│   └── nginx/                         ← 反向代理
│
├── backend/                            ← 【新】統一 FastAPI 後端
│   └── accounting/                    ← 會計 + 專案 + 回饋 + 管理 + L3 classifier
│       ├── main.py                    ← 全部 API endpoints
│       ├── test_main.py               ← pytest 基礎測試(14 項)
│       ├── requirements.txt
│       └── Dockerfile                 ← Python 3.12 · uvicorn
│
├── knowledge-base/                     ← RAG 資料源
│   ├── company/                       ← Company Memory(品牌/禁用詞/稱謂/格式 · 4 份)
│   ├── skills/                        ← 承富 12 Skills(投標/寫作/活動/營運)
│   ├── claude-skills/                 ← 【新】Anthropic 官方 17 Skills(pdf/docx/pptx/...)
│   ├── openclaw-reference/            ← 【新】OpenClaw 生態參考(marketing/comms/...)
│   └── SKILL-AGENT-MATRIX.md          ← 【新】Skill-Agent 中央路由表(主管家必讀)
│
└── config-templates/
    ├── librechat.yaml                 ← v0.8.4 + Artifacts/Vision/WebSearch 全開
    ├── docker-compose.yml             ← nginx + LibreChat + Mongo + Meili + accounting
    ├── docker-compose.override.yml    ← 本機開發專用(localhost 路由)
    ├── .env.example                   ← 機密標 🔐(Keychain 注入)
    ├── actions/                       ← 【新】OpenAPI Action Schemas
    │   ├── fal-ai-image-gen.json      ← Recraft v3 / Ideogram / Flux 三模型
    │   ├── pcc-tender.json            ← g0v 政府電子採購網 API
    │   └── accounting-internal.json   ← 承富會計 API 對 Agent 開放
    └── presets/
        ├── 00-09 · 10 Agent JSON      ← 當前 v1.0 建立的
        └── legacy/                    ← 舊 29 Agent(保留參考,不建立)
```

---

## 9. 現在從哪裡開始

1. 先讀完這份 `CLAUDE.md`(你正在做)
2. 讀 `docs/DECISIONS.md` 了解最新決議與待決議阻塞點
3. 讀 `DEPLOY.md` 看 Phase 0-6 的完整部署運行手冊
4. 讀 `SYSTEM-DESIGN.md` 了解設計語言與 IA
5. 讀 `ARCHITECTURE.md` 理解技術藍圖
6. 打開 `mockup-launcher.html`(或 `frontend/launcher/index.html`)看目標 UX
7. 承富 Phase 0 打勾完成 → 開始 Phase 1
8. 每完成一個 Phase 項目,在 `DEPLOY.md` 對應 checkbox 打勾
9. 遇到不確定,寫進 `docs/DECISIONS.md`「待決議事項」,向 Sterio 確認

**進度追蹤**:Phase 結束或重要里程碑時,產出一份快訊(Markdown),放在 `reports/milestone-<日期>.md`,包含:
- 已完成事項
- 未完成事項與原因
- 需要承富配合的事項
- **若 Phase 3**:Agent 建立累計進度(目標 29 個)+ 是否觸發 D-001 順延條款

---

## 10. Workspace 與前端架構(2026-04-18 升級為方案 A+B 混合)

> 原規劃 v1.0 只做方案 A(emoji prefix 分組),v1.1 才做方案 B(客製 UI)。
> 因承富明確要求「對 AI 小白友善、老闆要看到價值」,**v1.0 直接做方案 A + B**。

### 10.1 v1.0 實作架構(已交付檔案)

```
nginx(port 80 · 對外唯一入口)
    ├─ /                 → 承富 Launcher(frontend/launcher/)
    ├─ /chat, /c/*       → LibreChat(注入 CSS + JS)
    ├─ /api/*            → LibreChat API
    └─ /chengfu-custom/* → 客製 CSS/JS 靜態檔
```

**已交付元件**:

- **`frontend/launcher/`**:承富 macOS 風客製首頁
  - Sidebar(承富藍品牌、5 Workspace、全域工具、使用者)
  - Dashboard(問候、激勵卡片「本週省 X 小時」、常用、5 Workspace 卡、最近對話)
  - Inspector(本月用量、提示、系統狀態)
  - ⌘K 全域 palette(搜 Workspace / Agent / Slash)
  - ⌘1-5 快速切 Workspace · ⌘0 回 Dashboard
  - 深 / 淺色(跟隨系統或手動)
  - 首次登入 4 步 Onboarding Tour

- **`frontend/custom/`**:LibreChat 介面客製(nginx sub_filter 注入)
  - `librechat-custom.css`:承富藍、放大字體(15→16px)、隱藏 Temperature/Top P 等進階設定、管理員才看得到 Raw 參數
  - `librechat-relabel.js`:術語中文化(Endpoint → AI 引擎、Preset → 助手模板、Agent → 助手 等),加「← 承富首頁」按鈕

- **`frontend/nginx/`**:反向代理(sub_filter 注入 + SSE 長連線)

### 10.2 29 個 Agent 的實作方式(Phase 3 完成)

- 透過 `scripts/create-agents.py` 批次建立,30 秒完成(非手動 10 小時)
- Agent 名稱加 emoji prefix:`🎯 投標 · 招標須知解析器`
- `librechat.yaml` 的 `modelSpecs.list[]` 填 agent_id 作為 LibreChat 原生選單入口

### 10.3 AI 小白友善 · 七條鐵律(前端設計核心)

1. **繁中優先 + 生活化詞彙**(librechat-relabel.js 執行)
2. **首頁 = 選擇工作情境**(Launcher 取代 LibreChat 預設空白對話框)
3. **每個 Agent 配「一句話 + 試試看」**(Workspace 卡片有流程 tag)
4. **首次登入 4 步 Onboarding**(onboarding.js)
5. **隱藏進階設定**(CSS 覆蓋,`html[data-role="admin"]` 才解鎖)
6. **激勵回饋**(本週 X 次、全公司 Y 項任務)
7. **永遠 1-2 click**(Launcher 卡片 → 直接進對話,不二度選單)

### 10.4 不做的(v1.1 再評估)

- **Fork LibreChat**(方案 C)— 維運成本過高
- 行動 app
- Gmail / Calendar MCP(v1.1)
- 深度 macOS 風主題(視覺已匹配,行為細節如毛玻璃在 LibreChat 部分保留原樣)

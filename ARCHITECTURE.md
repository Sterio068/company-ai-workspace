# ARCHITECTURE.md — 技術架構

> **本檔已於 2026-04-18 依 DESIGN-REVIEW T-2/T-3/T-5 重整:**
> - 移除 `rag-api` / `vectordb` / `whisper` 三個多餘容器(LibreChat 原生已支援)
> - Mac mini 規格升 24GB(D-003)
> - LibreChat image pin 具體版本

---

## 系統拓樸

```
┌───────────────────────────────────────────────────────────┐
│                     使 用 者 端                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │同仁瀏覽器│    │ 桌機/筆電 │    │ 手機/平板 │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
└───────┼────────────────┼────────────────┼──────────────────┘
        │                │                │
        ▼ (公司內網 HTTP)  ▼ (外部 HTTPS)   ▼ (外部 HTTPS)
┌───────────────────────────────────────────────────────────┐
│                    連 線 層                                  │
│                                                            │
│   公司內網:http://承富-ai.local:3080                        │
│           ↓                                                 │
│   Cloudflare Tunnel(加密通道 · 免費 · 免開 port)            │
│   公開網址:https://ai.<承富domain>.com                     │
│   內含 Access Policy:Email 白名單 + 2FA(必要)              │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│              應 用 層(Mac mini 24GB 內)                     │
│                                                            │
│   ┌──────────────────────────────────────────────────┐    │
│   │  Docker Desktop for Mac(記憶體上限 10G)          │    │
│   │                                                   │    │
│   │  ┌──────────────────────┐  ┌─────────────────┐   │    │
│   │  │      LibreChat        │  │    MongoDB       │   │    │
│   │  │  ─────────────────    │◄─┤   (對話紀錄 +    │   │    │
│   │  │  介面 + Agent         │  │    Agent 定義 +  │   │    │
│   │  │  原生 file_search     │  │    檔案中繼資料) │   │    │
│   │  │  原生 code_interpreter│  └─────────────────┘   │    │
│   │  │  原生 STT(語音)     │                        │    │
│   │  │  原生 Web Search      │  ┌─────────────────┐   │    │
│   │  │  Actions / MCP 工具   │─►│   Meilisearch    │   │    │
│   │  │                       │  │  (對話全文檢索)  │   │    │
│   │  └──────────────────────┘  └─────────────────┘   │    │
│   │                                                   │    │
│   │  記憶體配額(約):                                 │    │
│   │    LibreChat     ~3-4 GB(mem_limit 6g)           │    │
│   │    MongoDB       ~500M-1GB                        │    │
│   │    Meilisearch   ~300-500 MB                      │    │
│   └──────────────────────────────────────────────────┘    │
│                                                            │
│   macOS Keychain(機密儲存 · 見 docs/05-SECURITY.md)        │
│     ├─ chengfu-ai-openai-key                               │
│     ├─ chengfu-ai-anthropic-key(選配備援)                  │
│     ├─ chengfu-ai-jwt-secret                               │
│     ├─ chengfu-ai-creds-key / creds-iv                     │
│     └─ chengfu-ai-meili-master-key                         │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│              AI 模 型 層                                    │
│                                                            │
│   主力:OpenAI API(前端預設,雲端)                           │
│   ├─ gpt-5.4             (重大決策、極複雜任務)             │
│   ├─ gpt-5.4-mini        (推薦中度、長文件與日常產出)        │
│   └─ gpt-5.4-nano        (快速任務、會議摘要、短回覆)        │
│                                                            │
│   備援:Anthropic Claude API(前端可切換)                    │
│   ├─ claude-opus-4-7      (重大決策、極複雜任務)            │
│   ├─ claude-sonnet-4-6    (長文件分析)                      │
│   └─ claude-haiku-4-5     (快速備援)                        │
│                                                            │
│   圖像生成:Claude 內建 vision + 外部工具(如 DALL-E 為選配)   │
│                                                            │
│   MCP 整合(v1.0 含 Google Drive,v1.1 含 Gmail/Calendar)    │
│                                                            │
│   階段二(可選):Ollama + Qwen 2.5 7B / TAIDE 繁中模型       │
│              ↑ 處理 Level 03 機敏資料,完全離線(需 32GB+)  │
└───────────────────────────────────────────────────────────┘
```

---

## 資料流

### 情境 1:同仁日常對話(Level 01 公開資料)
```
使用者輸入訊息
    ↓
LibreChat(Mac mini · HTTPS)
    ↓
OpenAI API(預設)或 Anthropic Claude API(前端切換,TLS)
    ↓ 回應
LibreChat(紀錄於本地 MongoDB)
    ↓
使用者看到回應
```

### 情境 2:上傳標書 PDF 解析(Level 02 一般資料)
```
使用者上傳 PDF
    ↓
LibreChat 原生 file_search capability:
    ├─ 本地抽文字(PDF.js / OCR)
    ├─ 分塊與 embedding(LibreChat 內部管線)
    └─ 中繼資料存於 MongoDB(不需 pgvector 容器)
    ↓
使用者選「招標須知解析器 Agent」發問
    ↓
Agent 呼叫 file_search → 取回相關段落
    ↓
文字片段(去識別化)+ Agent 指令一起送 Claude API
    ↓
Claude 回應結構化重點表
    ↓
儲存於本地 MongoDB
```

### 情境 3:知識庫查詢(RAG · 原生 file_search)
```
使用者在「公司知識庫查詢 Agent」輸入:「去年環保局案的預算結構」
    ↓
Agent 已預載承富知識庫檔案(Week 3 上傳,LibreChat 自動索引)
    ↓
file_search 對已索引內容做語意檢索
    ↓
取回 top-k 最相關過往結案報告片段
    ↓
片段 + 查詢 + Agent 指令送 Claude API
    ↓
Claude 根據承富自家資料回答,附上**檔案引用**(LibreChat 原生支援)
    ↓
儲存查詢紀錄
```

> 與舊架構差異:**不再需要** 單獨的 rag-api 容器或 pgvector 資料庫。
> LibreChat v0.7.6+ 將檔案檢索作為 Agent 原生能力,
> embedding/檢索內部管線維護,對使用者與 Sterio 皆透明。

### 情境 4:機敏資料處理(Level 03,階段二才啟用)
```
使用者選擇「Level 03 模式」
    ↓
LibreChat 自動切換到本地 Ollama 模型(需額外部署)
    ↓
所有運算在 Mac mini 完成,不出網路
    ↓
回應儲存於本地(標記 L3)
```

### 情境 5:會議錄音轉稿(LibreChat 原生 STT)
```
使用者錄音或上傳音檔(mp3/m4a/wav)
    ↓
LibreChat 原生 Speech-to-Text
    ├─ 預設使用 OpenAI Whisper API(需 OPENAI_API_KEY,僅作 STT)
    └─ 或設定本地 Whisper endpoint(可選,階段二)
    ↓
回傳逐字稿
    ↓
「會議速記 Agent」進一步結構化
```

---

## 元件細節

### LibreChat
- 官方 Docker image:`ghcr.io/danny-avila/librechat:v0.7.6`(TODO Week 2 確認最新穩定版再 pin)
- 暴露 port:3080(僅限本機與 Cloudflare Tunnel 存取)
- 資料卷:`./uploads`(檔案)、`./logs`(日誌)、`./images`(自訂圖)
- 設定檔:`librechat.yaml`(掛載 read-only)
- 記憶體上限:6 GB(docker-compose mem_limit)
- **原生能力(不需額外容器)**:
  - `file_search`:RAG / 知識庫檢索
  - `code_interpreter`:Python 執行(毛利試算、Excel)
  - `web_search`:即時網路搜尋
  - `speech_to_text`:語音轉文字
  - `actions`:呼叫外部 API / MCP

### MongoDB
- 版本:7.0
- 資料卷:`./data/mongo`
- 備份策略:每日 02:00 自動 `mongodump` 到 `~/chengfu-backups/mongo/YYYY-MM-DD.gz`(詳見 `docs/04-OPERATIONS.md`)
- 保留:30 天(每週日再滾動一份到週備份,保留 12 週)
- 記憶體上限:2 GB
- License:SSPL(承富內部 10 人使用,無商業轉售,視為低風險 · 見 `docs/05-SECURITY.md`)

### Meilisearch
- 版本:v1.12.0
- 用途:LibreChat 對話歷史的全文檢索(非 RAG)
- 資料卷:`./data/meili`
- 記憶體上限:1 GB

### Cloudflare Tunnel
- 安裝方式:`brew install cloudflared`
- 設定:`~/.cloudflared/config.yml`
- 啟動:`launchctl` 開機自啟
- 公開域名:`ai.<承富domain>.com`
- Access Policy(必要):
  - Email 白名單(10 個同仁 email)
  - **2FA 必開**(One-time PIN 或 Google Authenticator · S-2)
  - 可選:工作時間限制(週一至週五 08:00-22:00)

### macOS Keychain(S-1 · 機密儲存)
- 不是容器,是 macOS 原生服務
- 儲存以下項目(見 `scripts/setup-keychain.sh`):
  - `chengfu-ai-openai-key`(OPENAI_API_KEY,主力 AI / STT / embedding)
  - `chengfu-ai-anthropic-key`(ANTHROPIC_API_KEY,Claude 備援)
  - `chengfu-ai-jwt-secret` / `chengfu-ai-jwt-refresh-secret`
  - `chengfu-ai-creds-key` / `chengfu-ai-creds-iv`
  - `chengfu-ai-meili-master-key`
  - `chengfu-ai-email-password`(Resend / SMTP)
- 容器啟動時由 `scripts/start.sh` 從 Keychain 讀取並注入環境變數,
  `.env` 僅存非機密設定

---

## 硬體規格

### Mac mini M4(主機 · D-003)
- CPU:M4 10 核心
- **RAM:24 GB**(Round 1 T-3 警示 16GB 在 10 人尖峰邊界太緊;D-003 決議升 24GB)
- SSD:512 GB(足夠 3 年 MongoDB 與檔案儲存)
- 網路:有線乙太網路(不要用 Wi-Fi)
- 電源:接 UPS

### UPS 不斷電系統
- 規格:1000VA 以上
- 品牌:APC Back-UPS 或飛瑞 FC1000
- 用途:停電時保護 Mac mini 正常關機
- 建議:接 USB 連線讓 macOS 能監測電池狀態,自動關機前觸發 mongodump

### 網路
- 建議固定 IP(從承富網路設備配置)
- 主機名:`承富-ai.local`(Bonjour/mDNS)

---

## 效能預估

| 指標 | 預估值 |
|---|---|
| 同時併發使用者 | 10(24GB 充裕) |
| 對話回應延遲(GPT-5.4 nano / Haiku) | < 2 秒 |
| 對話回應延遲(GPT-5.4 mini / Sonnet) | 3-6 秒 |
| 60 頁 PDF 解析(GPT-5.4 mini / Sonnet) | 10-15 分鐘 |
| 會議 60 分鐘錄音轉稿(OpenAI Whisper API) | 3-5 分鐘 |
| 知識庫查詢(原生 file_search) | < 3 秒 |
| Mac mini CPU 平均佔用 | 5-15% |
| Mac mini RAM 平均佔用 | 10-14 GB(含 macOS + Docker + 容器) |
| Mac mini RAM 尖峰佔用 | 18-20 GB(24GB 有 4-6GB 緩衝) |
| OpenAI / Claude API RPM 需求 | 尖峰 200-300(需依實測調整額度與 rate limit) |
| 每日平均 API token 用量 | ~50 萬 token(10 人中度使用) |

---

## 擴充性

### 增加使用者(例:10 人 → 20 人)
- RAM 24GB 仍可支撐,但建議監控
- LibreChat 後台新增帳號即可
- OpenAI / Claude API 費用隨用量線性增加
- 超過 15 人需評估升 Mac Studio

### 增加模型(例:加入 Gemini 或新 OpenAI / Claude 模型)
- 修改 `librechat.yaml` 新增 endpoints(或在 .env 加對應 API key)
- 在各 Agent 指定使用模型

### 階段二升級:加入本地 Ollama
- 觸發條件:承富處理 Level 03 資料頻率增加、或客戶要求完全離線
- 需求:Mac mini RAM **建議升至 32 GB 或改 Mac Studio**
- 新增模型:Qwen 2.5 7B(通用)、TAIDE(繁中特化)
- 儲存空間:模型檔案約 20-40 GB
- LibreChat 支援 Ollama endpoint,在 `librechat.yaml` 宣告即可

### 備援方案
若 Mac mini 硬體損壞:
- UPS 確保不掉電
- 每日 MongoDB 備份可從 `~/chengfu-backups/` 還原
- 重建時間預估 2-4 小時(硬體送修期間可用替代機)
- 詳細 RTO / RPO 見 `docs/04-OPERATIONS.md`

---

## 技術債與已知限制

1. **依賴雲端 AI API**:若 OpenAI 或 Anthropic 服務中斷,對應引擎不可用。
   → 緩解:前端可切換另一家 provider；階段二加入本地 Ollama 做 fallback
2. **單點部署**:無負載均衡、無熱備援。10 人規模不需要,20+ 人才考慮叢集。
3. **中文 embedding 表現**:LibreChat 原生 file_search 對繁中支援足夠,但若承富大量用行業術語(如特定政府專案代碼),Week 3 需抽樣驗證檢索準度。
4. **繁中文語音辨識**:OpenAI Whisper API 對繁中辨識率約 92-95%,含口語專有名詞(人名、機關簡稱)時需人工校正。
5. **MongoDB SSPL License**:承富 10 人內部使用、無商業轉售,視為低風險。
   若未來有轉售或服務外部客戶計畫,需評估替代(FerretDB 等) · 見 `docs/05-SECURITY.md`。

---

## 安全設計

見 `docs/05-SECURITY.md`。核心原則:
- 傳輸全程 TLS(Cloudflare Tunnel + HTTPS)
- 儲存全盤加密(FileVault 必開)
- 帳號強密碼 + 2FA(Cloudflare Access **必要**)
- 金鑰永不明文(macOS Keychain + `scripts/start.sh` 啟動時注入)
- 備份加密(gpg symmetric)
- 人員異動 SOP(見 `docs/05-SECURITY.md` 第 5 節)
- Prompt Injection 防護(Agent system prompt 內建)

---

## 變更紀錄

| 日期 | 變更 | 對應 REVIEW 編號 |
|---|---|---|
| 2026-04-18 | 初版定稿,含全套容器(rag-api / vectordb / whisper) | — |
| 2026-04-18 | 移除 rag-api / vectordb / whisper,改用 LibreChat 原生能力 | T-2 |
| 2026-04-18 | 硬體 16GB → 24GB | T-3 / D-003 |
| 2026-04-18 | LibreChat image pin v0.7.6(待 Week 2 確認) | T-5 |
| 2026-04-18 | Keychain 納入架構圖,取代 `.env` 明文 | S-1 |
| 2026-04-18 | Cloudflare 2FA 從可選改必要 | S-2 |

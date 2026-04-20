# docs/DECISIONS.md — 承富 AI 系統決策紀錄

> 本檔記錄專案執行期間的所有關鍵決策。
> 每筆決策包含:決策內容、決策者、決策日期、理由、風險備註。
> 當 CLAUDE.md / SYSTEM-DESIGN.md / ARCHITECTURE.md 與本檔衝突時,以**本檔最新條目**為準。

---

## 一、已決議事項

### D-001 · v1.0 範圍:29 Agent 全部做
- **決策**:v1.0 完整交付 29 個 Agent,不分階段
- **決策者**:Sterio(代表承富專案)
- **決策日期**:2026-04-18
- **背景**:DESIGN-REVIEW Round 1 (P-1) 曾建議分階段(v1.0 10 個 + v1.1 19 個),因原 4 週時程對單人顧問超載
- **承擔代價**:
  - Week 3 工作量預估 60-80 hr(高強度週)
  - 若 Week 3 無法於時程內完成,**允許順延到 Week 5**,不壓縮品質
  - Agent 品質測試(每個 3 案例 × 29 = 87 案例)需納入 Week 3 或分散到 Week 2 尾聲
- **風險緩解**:
  - Week 2 平台穩定後,部分 Agent prompt 撰寫可與 Week 3 平行
  - 若時程真的卡死,依優先級順序交付(核心 10 個先上,剩 19 個跟進)
  - Week 3 每日產出監測,連續 2 天落後超過 20% 就觸發順延討論
- **後續影響**:
  - `tasks/week-3-customization.md` 保持 29 Agent 工作量規劃
  - `CLAUDE.md` 第 3 節交付定義維持 29 Agent
  - Sterio 需預留 Week 3 的工作日延長空間

### D-002 · Anthropic API 升 Tier 2
- **決策**:Week 0 內完成 Tier 2 升級
- **決策者**:Sterio
- **決策日期**:2026-04-18
- **背景**:DESIGN-REVIEW Round 2 (A-1) 警示 Tier 1 的 50 RPM 會在 10 人同時使用時爆掉
- **執行步驟**:
  1. 承富 IT 或老闆到 https://console.anthropic.com 預存 USD $50
  2. 系統自動升級到 Tier 2(1000 RPM / 80,000 TPM for Claude Sonnet 4.6)
  3. Sterio 確認升級完成後才啟動 Week 2
- **驗收**:console 顯示 Tier 2,`curl` 測 rate limit header 回傳 `anthropic-ratelimit-requests-limit: 1000` 以上
- **責任人**:承富 IT / 老闆執行,Sterio 驗收

### D-003 · Mac mini M4 採購規格:24GB
- **決策**:採購 24GB RAM 版本(非原計畫 16GB)
- **決策者**:Sterio 建議 → 承富老闆採購
- **決策日期**:2026-04-18
- **背景**:DESIGN-REVIEW Round 1 (T-3) 警示 16GB 在 10 人尖峰 + Docker + 本地模型可能吃緊
- **預估差價**:約 NT$ 5,000(一次性支出,3 年折舊攤提月均 < NT$ 140)
- **額外效益**:預留階段二 Ollama 本地模型推論空間(Level 03 機敏資料)
- **儲存容量**:維持 512GB(若要跑大模型再評估 1TB)
- **責任人**:承富老闆下單

---

## 二、待決議事項(按優先級)

> 以下為 DESIGN-REVIEW Round 1-5 找出的 **16 個重大問題**,尚待決策。
> 未決議前 Sterio 不得擅自假設實作方式。

### P-0 · 動工前必定(Week 0 內須決議)

| # | 問題代碼 | 決議項目 | 阻塞點 | 建議方向 |
|---|---|---|---|---|
| 1 | **X-1** | MCP 整合範圍(Google Drive / Gmail / Calendar) | 省 20-30% 工時 | v1.0 最少含 Google Drive MCP |
| 2 | **F-1** | Baseline 量測執行方式 | 無法驗 ROI | Week 0 請 10 人填工時表 |
| 3 | **GP-1** | 政府採購法對 AI 的規範查證 | 違法風險(承富主客戶是政府) | 承富法務 Week 0 查 |
| 4 | **C-1** | 分層訓練與 1:1 配對(資深同仁) | 採納率影響 | Week 4 訓練分 2 場 × 5 人 |
| 5 | **C-2** | 老闆全員溝通會(反 AI 情緒) | 月 1 採納率 | Week 0 或 Week 1 第一天安排 |
| 6 | **C-3** | 2 位 AI Champion 指派 | 月 1-3 支援承接 | 承富老闆 Week 0 指定 |

### P-1 · Week 1-3 執行前須決議

| # | 問題代碼 | 決議項目 | 影響週次 |
|---|---|---|---|
| 7 | **T-1** | LibreChat Preset vs Agent 實作(REVIEW 指 Preset 已棄用) | Week 3 |
| 8 | **T-2** | docker-compose 是否移除 rag-api/vectordb/whisper 三容器 | Week 1-2 |
| 9 | **T-4** | librechat.yaml 語法對照官方 example.yaml 校正 | Week 2 |
| 10 | **S-1** | `.env` 分機密(API key)與非機密(DOMAIN/PORT)欄位,機密用 Keychain | Week 1 |
| 11 | **D-1** | 災難復原 RTO/RPO 定義與備份策略 | Week 2 |
| 12 | **U-1** | 5 Workspace 實作方案(A=modelSpecs / B=JS 注入 / C=Fork) | Week 3 |
| 13 | **Q-1** | 29 Agent × 3 測試案例(共 87 案)的撰寫時程 | Week 3 |

### P-2 · 交付前須補完

| # | 問題代碼 | 決議項目 | 影響週次 |
|---|---|---|---|
| 14 | **H-1** | 事故分級 L1-L5 與 Champion → Sterio 升級流程 | Week 4 |
| 15 | **D-2/D-3** | 監控告警(Uptime Kuma / Grafana)部署 | Week 2-4 |
| 16 | **K-2/K-3** | 每任務驗收清單 + rollback 指南 | Week 1-4 |

---

## 三、已採納的 REVIEW 審視發現(原則性接受)

以下為 DESIGN-REVIEW 三輪審視(共 75 個發現)中 **Sterio 已認同** 的改善方向,
具體實作時機與方式待上述 P-0/P-1/P-2 決議後排入 `tasks/week-*.md`:

- **品牌語料庫先做**:Week 3 匯入 Agent 前,先建立承富過往服務建議書、新聞稿、結案報告的語料庫,Agent prompt 以此為 few-shot 範例(Round 2 B-1)
- **資料分級 SOP 文件先印後用**:Week 1 內印出貼牆,Week 4 前每位同仁能指認(Round 1 S-2)
- **FileVault + Keychain + Cloudflare Access 三道保護**:Week 1 全部開啟,`.env` 機密欄位改放 Keychain(Round 1 S-1, S-3)
- **用量告警分三階**:80% email / 100% 暫停 / 150% 強制終止(Round 2 A-2)
- **新同仁 Onboarding 流程**:若未來有新人入職,需有對應 AI 帳號開通 SOP(Round 3 H-2)

---

## 四、決策修訂紀錄

| 日期 | 修訂項 | 原決策 | 新決策 | 理由 |
|---|---|---|---|---|
| 2026-04-18 | 初版 | — | 建立本檔 | 專案啟動 |

---

**檔案維護原則**:
- 每筆決策進入 `tasks/*.md` 前先寫入本檔
- 決策變更時,在本檔新增「D-XXX-v2」條目,舊條目標註「已棄用,見 D-XXX-v2」
- 每週週報(`reports/week-N.md`)須檢視本檔並確認是否有待決議項變成阻塞點

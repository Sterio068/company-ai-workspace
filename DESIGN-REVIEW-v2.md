# DESIGN-REVIEW-v2.md — 第二輪深度審視

> **接續 `DESIGN-REVIEW.md` 的第一輪審視**。
> 第一輪找出 24 個技術/實作問題;這第二輪用**不同角度**挖結構性缺口。
> 目的:確保不是表面修一修就上線,而是真的能跑 3-5 年。

---

## 🎯 第二輪的特別發現 · 3 個被第一輪漏掉的重大點

1. **🔴 完全沒有規劃 MCP 整合** — 錯過 LibreChat 最強大的能力,省工時可能再加 40%
2. **🔴 10 人同時使用會爆 API rate limit** — 第一輪只討論成本,沒討論併發
3. **🔴 投資報酬的 baseline 未建立** — 6 個月後承富問「省了多少」時無從答起

這三點若不處理,開發完成後才發現 —— 白做。

---

## 代理 9 · 承富創辦人視角(CEO)

### 🔴 問題 F-1:沒有 baseline 就沒有 ROI 證明
**使用者心聲**:「你說每月省 280 hr、NT$ 126 萬。6 個月後我怎麼驗證?」

**缺口**:
- 導入前沒有量測「現在寫一份建議書花幾小時」
- 導入後也沒有量測「現在花幾小時」
- 兩個都沒有,就永遠無法證明 AI 的價值
- 承富老闆如果 6 個月後問:「這東西真的值嗎?」,Sterio 只能說「感覺變快了」

**修正**:Week 0 新增「baseline 量測週」,請承富各角色填寫:

```
╭──────────────────────────────╮
│ 現況量測(導入前基準)          │
│                                │
│ 姓名:________  角色:________  │
│                                │
│ 過去一週,下列任務實際耗時:      │
│ □ 寫一份建議書初稿:____ 小時    │
│ □ 解析一份招標須知:____ 小時    │
│ □ 寫一則新聞稿:____ 小時       │
│ □ 寫一則社群貼文:____ 分鐘      │
│ □ 做一份結案報告:____ 小時      │
│ □ 會議紀錄整理:____ 小時        │
│                                │
│ 上週總工時:____ 小時             │
│ 上週加班時數:____ 小時            │
│ 上週工作滿意度:1-5 分 ____       │
╰──────────────────────────────╯
```

**每月重覆填**,連 6 個月。產出的趨勢圖是**無法造假的證據**。

### 🟡 問題 F-2:沒有「為何不用 ChatGPT Plus」的說服
**使用者心聲**:「我可以給每人訂一份 $20 ChatGPT Plus,一年 NT$ 60K 包全公司。為什麼要這套 NT$ 115K 的?」

**缺口**:提案沒有「SaaS vs 本地部署」實戰比較表。業務在講單一數字,承富老闆要的是決策對照。

**修正**:新增 `docs/07-WHY-NOT-SAAS.md`:

| 面向 | ChatGPT Team | 承富 AI 系統 |
|---|---|---|
| 首年成本 | NT$ 60K (10 人 × $20 × 12 月) | NT$ 263K (NT$ 115K + NT$ 148K API) |
| **資料主權** | 存 OpenAI 伺服器 | 100% 本地 |
| **客製深度** | 只能 Custom GPT | Agent + RAG + MCP 全客製 |
| **PDPA 合規** | 跨境傳輸需告知 | 同上但傳輸量可控 |
| **承富 CIS** | 無 | 新聞稿等產出自動套承富風格 |
| **既有資料整合** | 要每次上傳 | 知識庫自動檢索 |
| **離線備用** | 完全無 | 階段二可加 Ollama |
| **政府標案敏感度** | 風險高 | 可分級管理 |

真正的論述:「前兩年 ChatGPT 便宜,但承富是公關業,**資料主權 + 客製化**價值遠超 NT$ 50K/年 差距」。

### 🟡 問題 F-3:投標勝率 +12% 的數字從哪來?
**使用者心聲**:「你 README 裡寫『勝率 62%』是幻想還是實據?」

**缺口**:mockup 上秀「勝率 62%」,但沒有資料支撐。這是**過度承諾**。

**修正**:mockup 改成「本月投標 ____ 次」「勝率 ____」等空白欄位,讓承富自己填數據。不要預設數字,尤其是勝率這種難以歸因給 AI 的指標。

---

## 代理 10 · Anthropic API 專家

### 🔴 問題 A-1:Tier 1 的 50 RPM 在 10 人同時用會爆
**技術實情**:
- 新開 Anthropic 帳號起始為 Tier 1(需先存 $5 激活)
- Tier 1 rate limit:**50 RPM**(requests per minute)
- LibreChat 單次對話送出,**實際觸發 1-3 個 API calls**(system prompt、streaming chunks、title generation)
- 10 位同仁早上 9:00 同時按「解析這份 PDF」→ 瞬間 30+ RPM,**逼近上限**
- 再加上 Agent 工具呼叫(file_search、code_execution),每個工具呼叫又是 1-2 個 API call → **容易爆**

**承富實際場景模擬**:
```
09:00 晨會結束,同仁回座開始工作
  ↓
09:05 5 位同仁同時上傳招標 PDF 解析
  → 5 × 3 API calls = 15 RPM
  + 5 個 file_search 呼叫 = 10 RPM
  = 約 25 RPM(單瞬間)
  
09:10 另外 3 位同仁開會議速記 Agent
  → +15 RPM
  
09:15 總監跑 Go/No-Go (Opus) + 另一位開社群企劃 (Sonnet)
  → +8 RPM
  
= 48 RPM(接近 Tier 1 上限)
```

**Tier 1 爆掉後**:429 Too Many Requests 錯誤,同仁看到「系統忙碌,請稍後」,體驗糟糕,信心崩塌。

**修正**:
- **Week 2 開始前必須升級 Anthropic 帳戶到 Tier 2**(需預存 $50 = 約 NT$ 1,600)
- Tier 2 提供 1,000 RPM,足以應付 10 人任何使用情境
- 在 `tasks/week-2-platform.md` 加入「驗證 Tier 級別」check point
- 在 `librechat.yaml` 設定 rate limit 保護(內部 per-user 上限),避免單人洪水

### 🟡 問題 A-2:沒討論 Prompt Caching 節費機會
**發現**:Anthropic 提供 **prompt caching** ~90% 折扣(2026 生效)。

對承富場景特別重要:
- 每個 Agent 的 system prompt 是固定的(2,000-4,000 tokens)
- 10 人同時用同一個 Agent,system prompt 可共享 cache
- 開啟後可省約 **30-50% API 成本**

**修正**:在 Agent 設定開啟 `cache_control` beta header。month 1 後估算實際節費。

### 🟡 問題 A-3:未預留「Opus 吃爆預算」的防護
**情境**:有同仁(可能老闆本人)發現 Opus 4.7 寫建議書寫得特別好,於是所有東西都用 Opus。**單次 30K tokens × Opus 單價 = NT$ 600/次**,一週用 5 次 = NT$ 3,000/週 = **一個人吃掉 NT$ 12,000/月預算**。

**修正**:
- librechat.yaml 設 per-user 成本上限(NT$ 1,500/月)
- Opus 只開放給 2 位「總監級」角色
- Admin panel 每日掃描,若單人超標自動降級到 Sonnet

---

## 代理 11 · LibreChat 社群老用戶

### 🔴 問題 L-1:v0.8.3 還是 release candidate
**事實**:
- LibreChat 2026 roadmap 顯示 v0.8.3-rc1 於 2026 初發佈
- **rc 版本不是穩定版**,可能有已知/未知 bug
- 承富要用於正式生產環境不該用 rc

**修正**:
- 鎖定最後一個 **stable 版本**(如 v0.8.2 或更早),非 rc
- 在 `docker-compose.yml` 明確 tag:`librechat:v0.8.2`
- 待 v0.8.3 正式版發佈後再規劃升級(Week 5+)

### 🟡 問題 L-2:LibreChat 月月有 breaking changes
**觀察**:查 LibreChat GitHub release notes 可見:
- 過去 6 個月共 7 個版本
- 其中 3 個有 breaking changes(config 格式變、環境變數 rename、API endpoint 改)

**對承富意義**:若啟用自動更新,某天早上開不起來是常態,不是例外。

**修正**:
- Docker image 版本**明確鎖定**,不用 `latest` tag
- `docs/04-OPERATIONS.md` 新增「季度升級 SOP」:
  1. 先在 staging(Sterio 本機)試跑新版
  2. 讀 release notes 找 breaking changes
  3. 承富 Mac mini 排一次維運時段升級
  4. 升級後 2 小時 hypercare,有問題立刻 rollback

### 🟡 問題 L-3:繁中 OCR 品質未驗證
**觀察**:LibreChat `ocr` capability 使用底層 tesseract / Google Vision。
- Tesseract 繁中準確率約 **85-92%**(良好掃描)、**60-75%**(舊影本)
- 若承富有大量早年掃描標案 PDF,OCR 錯誤會讓 RAG 查詢錯亂

**修正**:Week 3 灌入知識庫**前**,抽樣 5-10 份代表性文件做 OCR 測試,結果不佳的改用 PDF2Text + 手動校對。

---

## 代理 12 · MCP 整合專家 🚨

### 🔴 問題 X-1:完全沒規劃 MCP(最大遺珠)
**重大發現**:
- LibreChat 原生支援 MCP servers(Model Context Protocol)
- **Google Workspace MCP** 開源可用,讓 AI 能:
  - 直接讀取同仁 Gmail(客戶來信自動分類)
  - 查詢 Google Calendar(找會議空檔)
  - 操作 Google Drive(讀舊案、存新稿)
- **Filesystem MCP** 讓 AI 能讀承富 NAS / 雲端硬碟的所有檔案
- **Slack / Line MCP** 可自動發布或監聽訊息

**我們目前的做法**:
- 會議速記 Agent → 使用者手動上傳錄音檔 ❌
- 知識庫查詢 → 使用者先把檔案上傳到 LibreChat ❌
- CRM Agent → 使用者手動貼 email 內容 ❌
- 里程碑追蹤 → 使用者手動描述行程 ❌

**有 MCP 的理想做法**:
- 「這週我有哪幾場會議?」→ AI 直接查 Google Calendar ✓
- 「客戶 A 最近寫了什麼?」→ AI 直接查 Gmail 搜尋 ✓
- 「去年環保局案預算怎麼配?」→ AI 直接從 Google Drive 找檔案 ✓
- 「安排下週 2 小時的會議」→ AI 直接建立 Calendar event ✓

**量級差異**:
- 無 MCP:每次任務使用者要花 3-5 分鐘上傳 / 貼內容
- 有 MCP:使用者直接問,AI 自己找資料,**再省 20-30% 時間**

**修正**:新增 `docs/08-MCP-INTEGRATION.md`:
- **Phase 1**(v1.0 Week 3 必做):Google Drive MCP(讀檔)、Filesystem MCP(讀本地文件)
- **Phase 2**(v1.1):Gmail MCP、Google Calendar MCP
- **Phase 3**(v1.2):Slack / Line MCP(若承富有用)
- 每個 MCP 建置前,評估 OAuth 安全性與承富 IT 許可

### 🟡 問題 X-2:MCP 的隱私風險需預先評估
**現實**:MCP 讓 AI 有權存取同仁郵件、行事曆、檔案。若 Agent prompt 寫法不慎,可能:
- 把某人機敏郵件摘要貼到另一人對話
- 查詢後把商業資訊寫進 AI 回應被其他人看到
- OAuth token 被 prompt injection 濫用

**修正**:
- MCP 整合前寫 `docs/05-SECURITY.md` 增補章節「MCP 使用規範」
- 每個 MCP 工具預設「讀取」權限,不預設「修改/刪除」
- Agent prompt 明確「不可揭露其他同仁資料」
- 稽核 log 必須包含 MCP 呼叫紀錄

---

## 代理 13 · 變革管理顧問

### 🔴 問題 C-1:對資深同仁的學習曲線低估
**現實觀察**:
- 10 人公關公司可能有 30% 為 45 歲以上資深同仁
- 這些人很可能是「Office 精通但 SaaS 陌生」
- ChatGPT 都沒用過的話,學 Agent、⌘K、Slash command 是 3 週的事,不是 2 場訓練

**修正**:
- Week 0 加一項「使用者調查」:調查 10 人各自的數位熟練度
- 針對 50+ 歲同仁:
  - 1:1 專屬 2 小時訓練(不與全員一起)
  - 配對「數位同桌」(年輕同仁當小師傅)
  - 首月每週 check-in
- 首月 KPI 改為「**使用者滿意度**」而非「使用次數」

### 🟡 問題 C-2:沒有「反 AI 情緒」應對預案
**現實**:有同仁會想:
- 「AI 是不是想取代我?」
- 「我現在寫得慢是不是會被開除?」
- 「老闆會不會用 AI 監視我工作?」

**修正**:
- Week 0 老闆對全員溝通會(不是 Sterio 主持):
  - 明確聲明「**AI 是工具,不是替代**」
  - 「使用 AI 是新標準,但學習過程中不會有責難」
  - 「用量數據**不用於績效考核**,只用於優化」(若老闆能承諾)
- 書面白紙黑字。文字的儀式感重要。

### 🟡 問題 C-3:AI Champion 角色太重
**現實**:
- 現在計畫 AI Champion 一個人負責訓練 + 日常支援 + 使用優化 + 月度回饋
- 這個人還要做他的本職工作
- **過勞風險高**,3 個月後可能崩潰

**修正**:
- Week 2 起指派 **2 位 AI Champions**(PM 類 + 設計類各一)
- 明確寫入承富內部:Champion 每週有 4 小時「AI 支援時間」,不算其他工作超時
- Sterio 的月度維運包含「Champion 支援」1 小時/月

---

## 代理 14 · 2 年後的承富視角

### 🟡 問題 Y-1:Prompt drift(提示詞漂移)
**現實**:
- Claude 會從 4.7 升級到 5.x、6.x
- 2 年後,現在寫得完美的 Agent prompt 可能不再最適合新模型
- 承富同仁不會自己調 prompt,這事落在 Sterio 身上

**修正**:
- 每個 Agent JSON 加入 `promptVersion` 與 `testedOnModel` 元資料
- `tasks/` 新增「季度 prompt 健檢」:用固定測試案例跑一輪,比對輸出品質
- 品質下降 > 15% 觸發 prompt 優化工作

### 🟡 問題 Y-2:Bus factor = 1(單點依賴 Sterio)
**現實**:若 Sterio 因故無法服務(生病、換職涯、不合作),承富:
- 系統還在跑,但遇到問題沒人修
- Agent 不能優化,逐漸過時
- LibreChat 升級無人處理

**修正**:
- 建 `docs/09-BUSINESS-CONTINUITY.md`:
  - 所有系統密碼、keys 放承富老闆的 1Password
  - 系統文件完整,第三方工程師 2 天內可接手
  - 備用顧問名單(至少 1 位 Sterio 推薦的同業)
  - 合約明列「若 Sterio 不可服務,協助尋找接手者」

### 🟡 問題 Y-3:知識庫積累導致搜索品質下降
**現實**:
- Year 1:500 份文件,RAG 查詢精準
- Year 2:2000 份文件,結果變雜
- Year 3:5000 份文件,相關度大幅下降

**修正**:
- 加入「知識庫衛生 SOP」:
  - 每季歸檔超過 2 年的舊文件到 `archive/` collection
  - 重要文件加 `tag: evergreen` 永不歸檔
  - 每半年重新索引(re-embedding)

---

## 代理 15 · 資料遷移 / Exit Strategy

### 🟡 問題 M-1:承富若要換平台,資料能拿走嗎?
**現實**:承富 3 年後可能想換到 OpenAI Enterprise 或其他平台。

**現有資產**:
- ✅ 對話歷史(MongoDB)→ 可匯出 JSON
- ✅ 上傳檔案(本地 volume)→ 直接拿
- ✅ Agent system prompts → handoff 包 JSON 有
- ❌ **向量索引**(Meilisearch + file_search embeddings)→ 綁定 LibreChat 格式,換平台要重建
- ❌ 使用習慣與優化累積 → 無法攜出

**修正**:
- 合約明列「資料匯出協助」為 Sterio 退場義務
- Year 1 結束提供「年度資料封存」:把所有對話匯出成 PDF(人類可讀),每年一次
- 這也符合 PDPA 資料可攜權

---

## 代理 16 · Claude Code 自省(元層級)

### 🔴 問題 K-1:我無法替 Sterio 做「需要判斷」的決策
**現實檢視 tasks/**:
- Week 1 說「請承富提供固定 IP」—— 若承富 IT 人員不配合怎麼辦?
- Week 2 說「收集 10 人 email 建帳號」—— email 格式承富還沒決定?
- Week 3 說「灌入承富知識庫」—— 承富要提供哪些檔案?還沒盤點

**修正**:新建 `tasks/week-0-prep.md`(動工前承富需確認清單):

```markdown
# Week 0 — 動工前承富需確認事項

**必須在 Week 1 開始前完成,否則 Week 1 會卡住**

## 採購決策
- [ ] Mac mini:16GB / 24GB / 32GB(建議 24GB)
- [ ] UPS 品牌與型號
- [ ] 採購時程(貨到時間?)

## IT 配合
- [ ] 承富 IT 聯絡人是誰?
- [ ] 網路設備:誰能配發固定 IP?
- [ ] 防火牆政策是否允許 Cloudflare Tunnel?
- [ ] WiFi vs 有線:Mac mini 會接哪一個?

## 帳號與域名
- [ ] 承富 email 格式:name@chengfu.com.tw?
- [ ] 10 位同仁正式名單與 email
- [ ] 域名 ai.chengfu.com.tw 是否已在 Cloudflare?若無需註冊

## 資料準備(Week 3 會用)
- [ ] 預計灌入知識庫的檔案清單(多少份?大約多大?)
- [ ] 承富 CIS 手冊(logo、色票、字型規範)
- [ ] 承富過往優質新聞稿、建議書樣本

## 合約與合規
- [ ] 員工 PDPA 告知書(由承富法務準備)
- [ ] 系統使用守則
- [ ] 承富法律顧問是否需審閱?

## 變革管理
- [ ] 老闆對全員的溝通會時間
- [ ] 10 位同仁的數位熟練度調查
- [ ] 現況量測 baseline(F-1)

## AI Champion
- [ ] 指派 2 位 AI Champions(主 + 備)
- [ ] 安排其每週 4 小時 AI 支援時間
```

### 🟡 問題 K-2:acceptance criteria 應該可量測
**現實檢視**:原 tasks/ 多用「XX 完成」「XX 建立」等動詞,沒有**可量測驗收**。

**修正**:每個任務加 acceptance test。例:
```diff
- [ ] 任務 2.6:建立管理員帳號
+ [ ] 任務 2.6:建立管理員帳號
+     驗收:Sterio 用管理員帳號登入 admin panel,能看到 user list,截圖存證
```

### 🟡 問題 K-3:沒有 rollback 指南
**現實**:當 Claude Code 執行一個步驟失敗,沒有「倒退一步」的明確做法。

**修正**:每個 tasks/week-N.md 底部加「Rollback 指南」區塊:
- 若 Docker 起不來:docker compose down 後做什麼
- 若 Cloudflare Tunnel 連不上:如何退回本機連線
- 若 LibreChat config 改壞:從 git 還原上一版

---

## 📊 第二輪發現彙總

### 🔴 動工前必修(5 個新增)

| # | 問題 | 影響 | 修正動作 |
|---|---|---|---|
| F-1 | 無 baseline | 無法證明 ROI | Week 0 量測週 |
| A-1 | Tier 1 rate limit 會爆 | 10 人同時當機 | Week 2 前升 Tier 2 |
| X-1 | 完全沒有 MCP | 錯過 20-30% 再省工時 | 新增 docs/08-MCP-INTEGRATION.md |
| C-1 | 資深同仁學習曲線低估 | 採納率僅 50% | Week 0 調查 + 分層訓練 |
| K-1 | 動工前承富需確認項未列 | Week 1 會卡住 | 新增 tasks/week-0-prep.md |

### 🟡 Week 1-4 進行中修(6 個新增)

| # | 問題 | 修正動作 |
|---|---|---|
| F-2 | ChatGPT 比較缺失 | 新增 docs/07-WHY-NOT-SAAS.md |
| F-3 | 勝率數字無據 | mockup 改空白欄位 |
| A-2 | 未啟用 prompt caching | Agent 設定加 cache_control |
| A-3 | Opus 預算失控風險 | per-user 上限 |
| L-1 | v0.8.3 是 RC | 鎖 v0.8.2 stable |
| L-3 | 繁中 OCR 未驗證 | Week 3 先測 |
| C-2 | 反 AI 情緒無預案 | Week 0 老闆溝通會 |
| C-3 | AI Champion 單人負擔重 | 改 2 位 |
| Y-1/Y-2/Y-3 | 長期 drift | 季度健檢、BCP、知識庫衛生 |
| M-1 | Exit strategy | 合約明列匯出義務 |
| K-2 | acceptance 未量測 | 每任務加驗收 |
| K-3 | 無 rollback | 每週任務加 rollback |

---

## 🎯 執行順序建議

**今天到動工前(Week 0)必做 5 件事**:
1. 🔴 與承富確認 `tasks/week-0-prep.md` 所有事項
2. 🔴 先升級 Anthropic 帳戶到 Tier 2
3. 🔴 做 baseline 量測(每位同仁填表)
4. 🔴 確認 10 人資深程度,規劃分層訓練
5. 🔴 初步研究 Google Drive MCP(Week 3 會接)

**Week 3 內新增**:
6. MCP 整合(至少 Google Drive + Filesystem)
7. Prompt caching 開啟
8. Rate limit per-user 設定
9. 繁中 OCR 品質抽測
10. 每個 Agent 寫 3 個測試案例 + 期望輸出

**合約層級處理**:
11. 合約加入「退場協助」條款
12. 員工 PDPA 告知書(承富法務辦)
13. AI Champion 2 人制度書面化

---

## 💬 結論

第一輪 24 個問題多半是**技術層面可修的小洞**。
第二輪這 16 個問題是**結構性的大洞**,不處理會在 3-6 個月後才爆:

- **F-1 不修**:ROI 無從證明 → 承富懷疑投資
- **A-1 不修**:第一週爆 rate limit → 信任危機
- **X-1 不修**:少了 MCP 的 AI 像「被綁住手」→ 同仁回去用 ChatGPT
- **C-1 不修**:資深同仁不用 → 採納率卡 50%
- **Y-2 不修**:Bus factor = 1 → 承富一輩子被 Sterio 綁住

**這一輪的價值**:把 30% 的「可能會出問題」轉成「提前防掉了」。

建議行動:
1. 今天讀完 Round 1 + Round 2,做**範圍決策**(v1.0 要不要包含 MCP?)
2. 這週與承富開**Week 0 確認會議**,用 `tasks/week-0-prep.md` 當議程
3. 下週正式啟動前,做完 baseline 量測

— 第二輪多代理審視 · 2026/04/18

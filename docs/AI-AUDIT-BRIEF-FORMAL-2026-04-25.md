# 承富 AI 系統 · 正式審計文件與提示詞

> 文件日期:2026-04-25  
> 用途:交給外部 AI / 設計 AI / 產品顧問 AI 進行系統審計  
> 審計重點:UI/UX 為最高優先;其餘面向除「安全性」外皆納入  
> 明確排除:資安、滲透測試、密鑰管理、個資保護、權限繞過、攻擊面分析

---

## 1. 審計目標

請審計「承富 AI 系統」是否真的能成為公司內部日常 AI 工作台,並判斷它是否比直接使用 ChatGPT / Claude 網頁版更適合承富同仁完成工作。

本次最重要的審計問題:

1. 使用者是否能在 3 秒內理解這套系統可以幫他做什麼?
2. 使用者是否能不選模型、不選 Agent、不研究功能分類,直接把工作丟進來?
3. UI 是否太複雜、太長、太像後台或太像功能堆疊?
4. 工作流是否能從「輸入資料」一路走到「交付品」與「交棒」?
5. 資料來源、系統判斷、分派結果與下一步是否清楚可信?
6. 正式版與新版 UI/UX demo 之間,哪一個方向更接近可交付產品?
7. 除安全性外,產品、功能、架構、可維護性、測試、效能、文件、部署與交付流程是否有明顯缺口?

---

## 2. 系統摘要

承富 AI 系統是為「承富創意整合行銷有限公司」建置的本地部署 AI 協作平台。

公司背景:

- 地區:台灣
- 團隊規模:約 10 人
- 產業:公關行銷、活動企劃、政府標案、專案執行
- 使用者組成:老闆、PM、企劃、設計、社群、公關、營運、財會
- 使用者特性:多數不是 AI 專家,不應要求他們理解模型、Agent、RAG、MCP 等技術詞

產品目標:

- 讓同仁用工作情境完成任務,而不是進入一般聊天機器人。
- 把「標案、活動、設計、公關、營運」等公司日常工作變成可重複流程。
- 讓使用者只需要輸入需求或附件,系統自動整理、判斷、分派、產出與交棒。
- 提供公司內部知識庫、工作包、會議速記、CRM、社群排程、場勘、會計、管理後台等能力。
- 本地部署於 Mac mini,並透過瀏覽器給 10 位同仁使用。

核心設計原則:

- 繁體中文優先。
- 介面要讓 AI 小白也能使用。
- 不要要求使用者先選 Agent。
- 不要把 29 個功能平鋪成選單。
- UI 應該以「任務」與「交付品」為中心。
- 系統應該像工作台,不是一般聊天框或後台管理系統。

---

## 3. 目前版本與狀態

目前產品狀態:

- 正式版:v1.3.0 已完成一輪交付前硬化。
- 優化線:vNext Phase A-E 已進行第一輪大幅推進。
- 正式入口:`http://localhost/`
- 新版 UI/UX demo:`http://localhost/ui-demo`
- AI 引擎策略:OpenAI 為預設主力,Claude / Anthropic 可作前端切換備援。
- 前端策略:Launcher 使用 vanilla ES modules,不使用 React / Next.js / Tailwind。
- LibreChat 保持上游可升級,客製化透過 nginx / 靜態注入 / 自製 launcher 完成。

已知測試狀態:

- 後端 pytest 曾達成 `246 passed / 13 skipped`
- smoke test 曾達成 `10 passed / 0 failed`
- Playwright desktop/mobile 曾達成 `25 passed / 1 skipped`
- 多分頁深連結巡檢曾達成 `10 passed / 0 failed`

請審計時注意:

- 以上代表已有工程驗證基礎,但不代表 UI/UX 已達可交付品質。
- 使用者已明確反映:目前 UI 太複雜、難懂、太長,需要重新規劃。
- `/ui-demo` 是探索方向,尚未代表正式產品已完成。

### 3.1 vNext Phase A-E 完成度表

外部 AI 審計時請把下表視為「已做過第一輪,但仍需 UI/UX 重新收斂」的現況,不要誤判為純規劃。

| Phase | 目標 | 已完成狀態 | 審計時應注意 |
|---|---|---|---|
| Phase A · 決策與文件基準 | 讓接手者讀到同一個現況 | 已完成第一輪同步:`DECISIONS.md`、`AI-HANDOFF.md`、`ROADMAP-vNext.md` 已對齊 v1.3 + vNext | 檢查文件是否仍有舊語彙或誤導,例如 29 Agent 平鋪、舊模型策略 |
| Phase B · Hardening 與驗收可信度 | 修掉會破壞信任的真問題 | 已完成第一輪 hardening:LibreChat endpoint、Chrome Extension 草稿策略、nginx 權限 header、smoke 文件同步 | 不做安全審計,但可審計「錯誤狀態、等待狀態、驗收證據是否讓使用者信任」 |
| Phase C · Workspace 工作閉環 | 把首頁從工具列表升級成每日工作台 | 已完成今日工作台第一版、Workspace 草稿入口、Chat 回答可存回 handoff 或列下一步 | UI/UX 仍是最大缺口:入口是否仍太像功能清單?工作閉環是否真的順? |
| Phase D · 管理、權限、回饋與學習 | 讓老闆與 Champion 可營運系統 | 已完成第一批權限 enforcement、Project collaborators / next_owner、回饋可接月報與 skill proposal | 排除安全審計;只審計管理 UI、權限文案、老闆儀表板可理解性 |
| Phase E · 半自動 Workflow | 先做可控 workflow,不急著全自動 | 已完成 draft-first UI、workflow draft 可寫入 project handoff、adoption tracking | 審計 workflow 是否對使用者清楚、是否太像技術流程、是否能帶來比 ChatGPT 更好的接續感 |

目前系統開發成熟度參考:

| 面向 | 近期完成度 | 主要缺口 |
|---|---:|---|
| Launcher 前端 / AI Work OS | 84% | Chat context banner、mobile polish、UI/UX 收斂 |
| Chat runtime / feedback | 82% | 對話與 project/workspace context 顯示不足 |
| Project Memory / Handoff | 84% | 缺版本歷史、衝突提示、變更 diff |
| Workflow orchestrator | 81% | 尚未做真正多 Agent execution 與 rollback |
| Knowledge / RAG / Skills / Agents | 80% | 缺 10 Agent × 3 dry-run 品質紀錄 |
| Mobile / Site Survey / PWA | 80% | iPhone 實機流程未完整驗收 |
| Testing / CI / QA | 88% | Browser Use 驗收尚未 script 化 |

---

## 4. 技術架構摘要

部署:

- Mac mini M4 24GB / 512GB
- Docker Desktop for Mac
- nginx 單一入口
- Cloudflare Tunnel 遠端連線
- 本地 MongoDB 儲存對話、設定、專案資料
- Meilisearch 提供全文搜尋

主要服務:

- LibreChat v0.8.4:AI 對話、Agent、檔案、工具能力
- FastAPI / Python 3.12:`backend/accounting` 提供會計、專案、CRM、回饋、管理、工作流、知識庫等 API
- MongoDB 7:LibreChat 與自製後端共用資料層
- Meilisearch v1.12:搜尋
- nginx 1.27-alpine:反向代理與客製靜態資源

前端:

- `frontend/launcher/index.html`:正式主入口
- `frontend/launcher/launcher.css`:正式版樣式
- `frontend/launcher/app.js`:正式版主控
- `frontend/launcher/modules/*.js`:功能模組
- `frontend/launcher/ui-vnext-demo.html`:新版 UI/UX demo
- `frontend/launcher/ui-vnext-demo.css`:新版 UI/UX demo 樣式
- `frontend/launcher/ui-vnext-demo.js`:新版 UI/UX demo 互動

設計與維護限制:

- 不應改成 React / Next.js / Tailwind。
- 應維持 vanilla ES modules,讓未來承富 IT 可直接維護。
- 可以使用 esbuild 打包,但 source 應保持簡單。
- 設計應能漸進套回正式 Launcher,不是只做孤立 demo。

---

## 5. 正式版主要功能範圍

### 5.1 主工作區

正式版目前以 5 個 Workspace 組織:

1. 投標:標案判斷、招標解析、建議書、競品視覺、簡報架構
2. 活動執行:活動企劃、舞台、動線、現場體驗、廠商、合約
3. 設計協作:主視覺、設計 brief、AI 圖像、多渠道素材、視覺系統
4. 公關溝通:新聞稿、社群、月度內容、Email、會議速記
5. 營運後勤:結案、報價、里程碑、CRM、合約、稅務、onboarding、知識庫

審計重點:

- 5 Workspace 是否仍然太像功能分類?
- 是否需要改成「任務收件箱 / 工作包 / 資料來源 / 交付品」為主?
- 使用者是否仍被迫理解 Workspace / Agent / 模組?
- Workspace 是否真的形成閉環,還是只是多個入口?

### 5.2 Agent 與 AI 對話

目前 production surface 是 10 核心 Agent,legacy 29 Agent 保留為能力拆解與 prompt 來源。

審計重點:

- 是否應弱化 Agent 概念,改由系統自動分派?
- Agent 名稱與功能說明是否使用者能懂?
- 使用者是否知道什麼時候要用哪個 Agent?
- AI 回覆是否能回寫到工作包、下一步、交付品?

### 5.3 工作包與交棒

工作包用於保存:

- 任務背景
- 附件
- 對話
- 決策
- 風險
- 下一步
- 負責人
- workflow draft

審計重點:

- 工作包是否應成為首頁第一層心智模型?
- 使用者是否清楚「工作包」和「對話」的差異?
- 交棒資訊是否足夠支援同事接續?
- AI 產出是否有明確保存位置?

### 5.4 知識庫與資料來源

系統支援公司知識庫、檔案檢索、引用來源。

審計重點:

- 資料來源是否可見、可信、可追溯?
- 使用者是否知道目前 AI 參考了哪些附件或公司資料?
- 錯誤引用、資料不足、缺件狀態是否有清楚 UI?
- 上傳附件、引用、回寫之間流程是否順?

### 5.5 半自動 Workflow

目前策略是 draft-first:

- 先產生步驟草稿
- 人工確認
- 再寫入 project handoff 或後續流程

審計重點:

- workflow 是否應出現在主介面?
- 使用者是否知道系統下一步會做什麼?
- draft-first 是否有足夠 UI 表達?
- 工作流是否能比一般 ChatGPT 更省時間?

### 5.6 管理與後勤功能

包含:

- 同仁管理
- 權限勾選
- 用量與成本儀表板
- 會計模組
- CRM
- 社群排程
- 場勘 PWA
- 會議速記
- 使用教學

審計重點:

- 是否太多功能擠在同一側欄?
- 管理功能是否應與一般使用者工作台分離?
- 老闆、PM、一般同仁是否應有不同首頁?
- 次要功能是否可以收進「工具箱」或「搜尋」,降低日常干擾?

---

## 6. 新版 UI/UX Demo 說明

目前 `/ui-demo` 方向:

- 三欄任務工作台
- 左側:任務輸入與附件
- 中央:系統自動處理狀態與交付預覽
- 右側:資料來源、自動分派結果、可輸出內容、存成工作包

demo 核心理念:

- 使用者不先選功能。
- 使用者不先選 Agent。
- 使用者不猜資料放哪裡。
- 使用者只輸入需求或加入附件。
- 系統自動建立摘要、來源、分工與交付草稿。

目前 demo 的已知問題:

- 視覺仍可能太重、太像展示頁。
- 三欄資訊密度可能仍高。
- 「自動分派」與「交付預覽」的關係仍需更自然。
- 是否要保留頂部 mode switcher 有待評估。
- 行動版可能需要改成分步式,不是三欄堆疊。
- demo 的互動仍是前端模擬,尚未完全接正式資料與 API。

請審計:

- 此方向是否比正式版更適合承富?
- 是否應將正式版整體改為任務收件箱模式?
- 哪些元素應保留、刪除、合併、重命名?
- 如何把 demo 收斂成正式可用設計?

### 6.1 正式版首頁文字替代描述

如果外部 AI 無法讀取截圖,請用以下文字 wireframe 理解正式版首頁:

```text
正式版 http://localhost/

整體:
- 左側固定 sidebar,上方品牌「承富智慧助理」。
- sidebar 第一層包含:今日、工作包、資料庫、中控。
- sidebar 另有可展開區塊:流程模板、次層功能、快速工具。
- 流程模板包含 5 Workspace:投標、活動執行、設計協作、公關溝通、營運後勤。
- 次層功能包含工作包、商機漏斗、標案監測、會計、技能庫、建議下一步、知識庫、管理面板、同仁管理、會議速記、媒體名單、社群排程、場勘、使用教學。
- 快速工具包含 /know、/meet 等 slash command。

可能問題:
- sidebar 功能多,一般同仁第一眼可能不知道該從哪裡開始。
- 「今日 / 工作包 / 資料庫 / Workspace / 次層功能 / 快速工具」心智模型混在一起。
- 功能很完整,但容易像營運後台,而不是任務工作台。
- 如果沒有引導,使用者可能退回 ChatGPT 式用法:自己開聊天、自己貼資料、自己整理結果。
```

請依此判斷正式版 UI density 與 IA 問題,不要只依程式碼檔案推測。

### 6.2 新版 UI/UX demo 文字替代描述

如果外部 AI 無法讀取截圖,請用以下文字 wireframe 理解 `/ui-demo`:

```text
新版 demo http://localhost/ui-demo

頂部:
- 左上品牌「承富 AI 工作台」
- 中間 mode switcher:任務處理、交付預覽、資料來源、流程設定
- 右上:明暗、正式版

主畫面三欄:

左欄 · 任務輸入:
- 標題「輸入任務」
- 說明:不用先選功能或 Agent,把需求和附件放進來
- textarea:輸入需求
- 範例任務 chips:標案判斷、會議交棒、活動企劃
- 附件 drop zone
- CTA:建立任務草稿

中欄 · 自動處理:
- 標題「自動整理、分派與產出」
- 狀態 pill:待輸入 / 處理中 / 草稿完成
- 系統判斷卡:任務類型、建議處理模組、需要人工確認
- 四步流程:讀取需求、檢查附件與知識庫、自動分派模組、建立交付草稿
- 交付預覽:摘要 / 任務 / 交付 / 交棒

右欄 · 來源與輸出:
- 資料來源卡:來源完整度、招標須知.pdf、公司履約案例、承富語氣規則
- 自動分派結果:投標模組、營運模組、設計模組
- 可輸出內容:任務摘要、缺件清單、分工表、提案大綱、存成工作包

可能問題:
- 比正式版更接近「任務工作台」,但仍可能資訊密度偏高。
- mode switcher 是否必要仍待評估。
- 三欄在手機上需改成分步流程,不能只是垂直堆疊。
- demo 互動仍為前端模擬,尚未完全接正式 API 與資料模型。
```

請將正式版與 demo 視為兩個方向:正式版功能完整但可能太複雜;demo 任務導向但尚未產品化。

### 6.3 使用者日常真實情境 timeline

請外部 AI 用這個日常情境評估「是否比 ChatGPT / Claude 網頁版好用」:

```text
角色:承富 PM,非工程背景,熟悉公關活動但不熟 AI 工具。
日期:週二,一般工作日。

09:30 · 收到客戶 Email
客戶說:「下週五要提案,主題是中秋節品牌主視覺與快閃活動,今天下午想先看方向。」
PM 需要:
1. 整理客戶需求
2. 找過往類似案例
3. 建立提案大綱
4. 分派設計初步方向
5. 列出待確認問題
6. 寫一封回覆客戶的確認信

10:00 · 客戶補傳附件
附件包含:品牌手冊 PDF、去年活動照片、預算範圍、會議錄音。
PM 需要:
1. 上傳或拖入附件
2. 知道系統讀了哪些資料
3. 知道哪些資料還缺
4. 產出可交給設計師的 brief

11:30 · 內部站會
老闆問:「這案子值不值得接?今天誰要做什麼?」
PM 需要:
1. 快速得到風險與價值判斷
2. 有分工表
3. 有今天 17:00 前的待辦
4. 能把結果存成工作包

14:00 · 設計師接手
設計師不想重讀整段聊天。
她需要:
1. 看工作包摘要
2. 看使用資料來源
3. 看設計相關任務
4. 看到 AI 建議的視覺方向

16:30 · 回覆客戶
PM 需要:
1. 客戶信草稿
2. 提案大綱
3. 明天前待確認事項
4. 不要重新複製貼上到 ChatGPT 自己整理

審計問題:
- 目前正式版能否讓這條 timeline 順利完成?
- demo 方向是否更適合?
- 哪些步驟目前仍需要使用者自己思考、複製、整理、切頁?
- 要怎樣才真的比 ChatGPT 網頁版好用?
```

---

## 7. UI/UX 審計要求

請以最高優先級審計 UI/UX。請不要只給主觀美感評論,必須指出具體問題、原因、影響、建議改法。

### 7.1 使用者心智模型

請判斷目前系統更像:

- 聊天工具
- 功能後台
- Agent 選單
- 任務工作台
- 知識庫入口
- 公司營運系統

並回答:

- 它應該像什麼?
- 現在最混亂的心智模型是什麼?
- 使用者第一眼該看到什麼?
- 是否應把「今天要完成什麼?」作為唯一主入口?

### 7.2 資訊架構

請審計:

- 側欄層級是否過多?
- 5 Workspace 是否仍適合?
- 次層功能是否需要重新收納?
- 工作包、資料庫、流程模板、AI 對話、功能模組之間是否有清楚關係?
- 管理者與一般使用者是否應完全不同 IA?

請提出新的 IA 建議,至少包含:

- 一般同仁首頁
- PM / 企劃首頁
- 老闆 / Admin 首頁
- 任務建立流程
- 工作包列表與細節
- 交付品預覽
- 資料來源檢查

### 7.3 互動流程

請審計以下核心流程:

1. 登入後開始第一個任務
2. 上傳招標 PDF 並要求 Go / No-Go
3. 把會議紀錄整理成客戶信與內部分工
4. 建立活動企劃與廠商清單
5. 查詢公司過往案例並引用
6. 把 AI 回覆存回工作包
7. 將工作包交給同事
8. 管理者建立新同仁帳號

對每個流程請指出:

- 現在可能卡在哪裡
- 多餘步驟
- 缺少的回饋
- 缺少的錯誤恢復
- 如何縮短到最少操作

### 7.4 視覺設計

請審計:

- 版面是否太滿或太長?
- 視覺焦點是否明確?
- 字級是否適合繁體中文長文?
- 卡片、陰影、毛玻璃是否過度?
- 顏色是否有清楚語意?
- CTA 是否清楚?
- 工作台是否像正式產品,還是像 demo?
- 是否有「AI SaaS 模板感」?

請提供:

- 建議色彩系統
- 建議字級層級
- 建議間距節奏
- 建議卡片密度
- 建議桌機 / 手機版 layout

### 7.5 文案與術語

請審計所有使用者可見文案:

- 是否全部繁體中文?
- 是否有大陸用語?
- 是否有抽象口號?
- 是否有技術詞讓使用者困惑?
- Agent、Workspace、工作包、流程模板、資料庫等詞是否一致?
- 是否應改成更生活化的詞?

禁止方向:

- 革命性
- 魔法
- 作戰圖
- 解放生產力
- 重新定義工作
- AI 超能力
- 任何不具體的行銷口號

請提出更好的命名與文案。

### 7.6 可用性與可近用性

請審計:

- 鍵盤操作
- 焦點狀態
- 對比
- 點擊目標大小
- 表單 label
- empty state
- loading state
- error state
- mobile navigation
- PWA / iPhone 場勘情境

注意:可近用性屬 UI/UX 審計範圍;但不要延伸到資安或隱私審計。

### 7.7 AI 信任與可控性

請審計:

- 使用者是否知道 AI 正在做什麼?
- 使用者是否知道 AI 用了哪些資料?
- 產出是否可編輯、可保存、可交棒?
- 錯誤回答時是否有修正路徑?
- AI 自動分派是否透明?
- 系統是否避免「黑箱自動化」?

---

## 8. 非安全面向審計要求

安全性不在本次範圍。請不要分析資安、攻擊面、權限繞過、密鑰、個資、隱私、法遵。

請審計以下非安全面向:

### 8.1 產品策略

- 產品定位是否清楚?
- 是否真的比 ChatGPT / Claude 網頁版更有價值?
- 哪些功能是核心,哪些是干擾?
- v1.4 應優先做什麼?
- 哪些功能應延期或隱藏?

### 8.2 功能完整度

- 投標、活動、設計、公關、營運是否各自形成閉環?
- 會議、CRM、社群、場勘、會計是否該在同一主介面?
- 工作包與 workflow 是否足以支撐真實工作?
- 附件與資料來源流程是否完整?

### 8.3 技術架構與可維護性

- vanilla ES modules 架構是否仍可維護?
- `app.js` 是否過大?
- module 邊界是否合理?
- frontend / backend / LibreChat 分工是否清楚?
- demo 如何逐步併回正式版?
- 是否需要設計系統 tokens 與元件清單?

### 8.4 API 與資料模型

- Project / handoff / workflow draft / source / artifact 之間資料關係是否清楚?
- API envelope 是否一致?
- 前端錯誤處理是否足夠?
- API 是否支援 UI 需要的狀態?
- 是否缺少 artifact / task / source / handoff 的正式資料模型?

### 8.5 測試與品質

- 目前測試是否覆蓋主要使用者旅程?
- 是否缺 UI regression / visual snapshot?
- 是否缺 a11y smoke?
- 是否缺 mobile/PWA 旅程?
- 是否缺 demo-to-production migration 測試?

### 8.6 效能與體驗速度

- 首屏是否太重?
- 前端模組載入是否過多?
- UI 是否需要 skeleton / progressive loading?
- AI 回覆等待過程是否有足夠狀態?
- 大附件、長文件、慢 API 時體驗是否合理?

### 8.7 文件與交付

- 使用者手冊是否和實際 UI 對得上?
- 管理者文件是否足夠?
- 安裝、升級、回復文件是否清楚?
- vNext 計畫是否能被外部團隊理解?
- 是否缺 UI/UX spec、設計系統、元件文件、任務流程圖?

### 8.8 部署與營運

- 安裝流程是否對非工程師友善?
- DMG / installer 是否降低部署摩擦?
- 本機資料保留與升級流程是否清楚?
- smoke test 是否足以代表可交付?
- 監控與維運儀表是否對老闆可理解?

---

## 9. 請外部 AI 參考的主要檔案

請優先閱讀:

1. `AI-HANDOFF.md`
2. `docs/DECISIONS.md`
3. `SYSTEM-DESIGN.md`
4. `ARCHITECTURE.md`
5. `frontend/launcher/index.html`
6. `frontend/launcher/launcher.css`
7. `frontend/launcher/app.js`
8. `frontend/launcher/modules/README.md`
9. `frontend/launcher/ui-vnext-demo.html`
10. `frontend/launcher/ui-vnext-demo.css`
11. `frontend/launcher/ui-vnext-demo.js`
12. `frontend/launcher/user-guide/quickstart-v1.3.md`
13. `docs/UI-UX-COMPETITIVE-TEARDOWN-2026-04-25.md`
14. `docs/UI-UX-SIMPLIFICATION-PLAN-2026-04-25.md`

若時間有限,至少閱讀:

1. `AI-HANDOFF.md`
2. `docs/DECISIONS.md`
3. `frontend/launcher/index.html`
4. `frontend/launcher/ui-vnext-demo.html`
5. `frontend/launcher/ui-vnext-demo.css`
6. `frontend/launcher/ui-vnext-demo.js`

---

## 10. 正式審計提示詞

以下提示詞可直接貼給其他 AI。

```text
你是一位資深產品審計顧問、B2B SaaS UI/UX 設計審計專家、AI 工作流產品架構師、繁體中文企業軟體顧問。請審計「承富 AI 系統」。

重要限制:
本次審計不要做安全性審計。請不要分析資安、滲透測試、攻擊面、密鑰、個資、隱私、法遵、權限繞過等安全議題。安全性完全排除。

最高優先審計目標:
UI/UX。請特別檢查介面是否太複雜、太長、太像後台、太像功能堆疊、太要求使用者理解 Agent / Workspace / 模型。請判斷它是否真的能讓非 AI 專家同仁「把工作丟進來,系統自動判斷、分派、產出、交棒」。

產品背景:
承富是台灣 10 人公關行銷與活動企劃公司,工作包含政府標案、活動企劃、設計協作、公關溝通、營運後勤、會議、CRM、社群排程、場勘、會計。使用者多數不是 AI 專家,不應要求他們理解模型、Agent、RAG、MCP 等技術詞。

系統定位:
這不是一般聊天機器人,也不應只是 Agent 選單。目標是公司內部 AI 工作台。使用者應能輸入需求或加入附件,系統自動整理、判斷任務類型、分派處理模組、產生摘要/任務/交付草稿,並可存成工作包交給同事接續。

目前系統:
- 正式入口:http://localhost/
- 新版 UI/UX demo:http://localhost/ui-demo
- 前端:vanilla ES modules,不使用 React / Next.js / Tailwind
- 對話底層:LibreChat v0.8.4
- 後端:FastAPI + MongoDB + Meilisearch
- AI:OpenAI 預設主力,Claude 可切換備援
- 主要資訊架構:5 Workspace,包含投標、活動、設計、公關、營運
- 目前 production surface:10 核心 Agent,legacy 29 Agent 作為能力參考

請閱讀這些文件與程式:
1. AI-HANDOFF.md
2. docs/DECISIONS.md
3. SYSTEM-DESIGN.md
4. ARCHITECTURE.md
5. frontend/launcher/index.html
6. frontend/launcher/launcher.css
7. frontend/launcher/app.js
8. frontend/launcher/modules/README.md
9. frontend/launcher/ui-vnext-demo.html
10. frontend/launcher/ui-vnext-demo.css
11. frontend/launcher/ui-vnext-demo.js
12. frontend/launcher/user-guide/quickstart-v1.3.md

如果你無法實際開啟 localhost 或讀取截圖,請改用本 brief 的「正式版首頁文字替代描述」、「新版 UI/UX demo 文字替代描述」與「使用者日常真實情境 timeline」進行判斷。請不要因為看不到圖片就跳過 UI/UX 審計。

請回答以下問題:

一、總體判斷
1. 這套系統目前比較像「AI 工作台」、「聊天工具」、「功能後台」、「Agent 選單」還是「營運系統」?
2. 它是否比直接使用 ChatGPT / Claude 網頁版更適合承富同仁?為什麼?
3. 最大 5 個產品問題是什麼?
4. 最大 5 個 UI/UX 問題是什麼?
5. 哪些功能應該保留在第一層?哪些應該隱藏或延後?

二、UI/UX 深度審計
請從以下角度逐項審計:
- 首屏理解度
- 任務輸入流程
- 附件上傳與資料來源
- 自動分派是否清楚
- Agent / Workspace 概念是否造成負擔
- 工作包與交棒流程
- 交付品預覽
- 側欄與導航
- 資訊密度
- 視覺階層
- 繁體中文文案與術語
- empty / loading / error state
- 手機版與 PWA 體驗
- 可近用性,例如鍵盤、焦點、對比、點擊目標

三、正式版 vs UI demo
請比較正式版 http://localhost/ 與新版 demo http://localhost/ui-demo:
1. 哪個方向更接近承富真正需要?
2. demo 哪些部分應該導入正式版?
3. demo 哪些部分仍然太複雜或不適合?
4. 正式版哪些部分應該被刪除、合併或移到次層?
5. 請提出一個更短、更清楚、更可交付的首頁 IA。

四、非安全面向審計
請審計下列面向,但不要包含安全性:
- 產品策略
- 功能完整度
- 技術架構與可維護性
- 前端 module 邊界
- API 與資料模型是否支援 UI
- 測試與品質
- 效能與體驗速度
- 文件完整度
- 部署與營運可用性
- 教育訓練與上線準備

五、請提出重構方案
請提出一份可執行的 UI/UX 重構方案,分成:
- 立即修正:1-3 天
- 第一階段:1 週
- 第二階段:2-3 週
- 第三階段:1-2 個月

每個階段請包含:
- 目標
- 要刪除或合併的東西
- 要新增或保留的東西
- 需要修改的主要檔案
- 驗收標準
- 風險

六、輸出格式
請用繁體中文輸出。請務必具體,不要給泛泛而談的設計建議。

請使用以下格式:

1. Executive Summary
- 一段話說明整體判斷
- 交付狀態:可交付 / 有條件可交付 / 不建議交付
- 最重要的 3 個修正

2. Findings
用表格列出所有問題:
欄位:編號、嚴重度(P0/P1/P2/P3)、面向、位置/檔案、問題、影響、建議修正。

3. UI/UX 重構建議
請提供新版資訊架構、首頁 wireframe 文字描述、主要流程、元件清單、文案建議。

4. 非安全面向審計
請依產品、功能、架構、測試、效能、文件、部署、訓練逐項列出。

5. Prioritized Roadmap
請列出 1-3 天、1 週、2-3 週、1-2 個月路線圖。

6. Acceptance Criteria
請列出如何判斷 UI/UX 重構成功,包含可觀察指標與測試方式。

請不要提供安全性建議。
```

---

## 10.1 三份 mini-prompt

如果要把審計拆給不同 AI,可分別使用以下三份 prompt。三份都排除安全性。

### Mini-prompt A · 產品策略審計

```text
你是 B2B SaaS 產品策略顧問。請只審計承富 AI 系統的產品策略,不要做安全性審計。

背景:
承富是台灣 10 人公關行銷與活動企劃公司。系統目標是成為內部 AI 工作台,讓同仁不用選模型、不用選 Agent,只要輸入需求或附件,系統自動整理、判斷、分派、產出與交棒。

請閱讀:
- AI-HANDOFF.md
- docs/DECISIONS.md
- docs/ROADMAP-vNext.md
- docs/AI-AUDIT-BRIEF-FORMAL-2026-04-25.md

請回答:
1. 這套產品是否比 ChatGPT / Claude 網頁版有明確差異化?
2. 它真正的核心產品價值是什麼?
3. 哪些功能是核心,哪些是干擾?
4. 5 Workspace 是否仍是正確第一層 IA?
5. 工作包是否應成為主心智模型?
6. Agent 是否應完全降到背景?
7. v1.4 最小可交付範圍應該是什麼?
8. 哪些功能應延後、隱藏或移到管理區?

輸出格式:
- Executive Summary
- P0/P1/P2 Findings 表格
- 建議產品定位
- 建議首頁 IA
- 1-3 天、1 週、2-3 週、1-2 個月 roadmap

請用繁體中文,不要提供安全性建議。
```

### Mini-prompt B · UI/UX 審計

```text
你是繁體中文 B2B SaaS UI/UX 審計專家。請只審計承富 AI 系統的 UI/UX,不要做安全性審計。

最高目標:
判斷這個系統是否能讓非 AI 專家的承富同仁「直接丟工作進來,系統自動整理、分派、產出、交棒」。請特別檢查 UI 是否太複雜、太長、太像後台、太像功能堆疊。

請閱讀:
- frontend/launcher/index.html
- frontend/launcher/launcher.css
- frontend/launcher/app.js
- frontend/launcher/ui-vnext-demo.html
- frontend/launcher/ui-vnext-demo.css
- frontend/launcher/ui-vnext-demo.js
- docs/AI-AUDIT-BRIEF-FORMAL-2026-04-25.md

如果看不到畫面,請使用 brief 裡的:
- 正式版首頁文字替代描述
- 新版 UI/UX demo 文字替代描述
- 使用者日常真實情境 timeline

請審計:
1. 首屏理解度
2. 導航與側欄複雜度
3. 任務輸入流程
4. 附件與資料來源
5. 自動分派狀態
6. 交付品預覽
7. 工作包與交棒
8. 文案與術語
9. 視覺階層、資訊密度、卡片密度
10. 手機版與 PWA 體驗
11. empty / loading / error state
12. 可近用性:鍵盤、焦點、對比、點擊目標

輸出格式:
- 一句話總評
- 可交付 / 有條件可交付 / 不建議交付
- 至少 15 個 findings,其中至少 10 個 UI/UX findings
- 每個 finding 包含:嚴重度、位置/檔案、問題、影響、建議修正
- 新首頁 wireframe 文字描述
- 新手機版流程描述
- 可直接替換的繁中文案建議

請用繁體中文,不要提供安全性建議。
```

### Mini-prompt C · 架構與可維護性審計

```text
你是前端架構與產品工程審計顧問。請審計承富 AI 系統的非安全架構、可維護性、測試、效能與交付流程,不要做安全性審計。

限制:
Launcher 維持 vanilla ES modules,不改成 React / Next.js / Tailwind。審計重點是如何在現有約束下改善架構與 UI/UX 落地。

請閱讀:
- AI-HANDOFF.md
- ARCHITECTURE.md
- frontend/launcher/modules/README.md
- frontend/launcher/index.html
- frontend/launcher/app.js
- frontend/launcher/modules/*.js
- frontend/launcher/ui-vnext-demo.html
- frontend/launcher/ui-vnext-demo.css
- frontend/launcher/ui-vnext-demo.js
- backend/accounting/main.py
- backend/accounting/routers/
- tests/e2e/

請審計:
1. vanilla ES modules 是否仍可維護?
2. app.js 是否過大?應如何拆?
3. demo 如何漸進併回正式版?
4. 是否缺少設計系統 tokens / components / layout primitives?
5. Project / handoff / workflow draft / source / artifact 的資料模型是否支援 UI?
6. API 是否提供 UI 需要的 loading/error/progress/source 狀態?
7. 測試是否涵蓋主要使用者旅程?
8. 是否需要 visual regression / a11y smoke / mobile E2E?
9. 首屏與前端載入是否可能太重?
10. 文件與安裝交付是否足以支撐外部團隊接手?

輸出格式:
- 架構總評
- P0/P1/P2 Findings 表格
- 建議檔案拆分計畫
- demo-to-production migration plan
- 測試補強計畫
- 1-3 天、1 週、2-3 週 roadmap

請用繁體中文,不要提供安全性建議。
```

---

## 11. 外部 AI 輸出評分規準

收到外部 AI 審計後,可用以下標準判斷品質:

| 分數 | 標準 |
|---|---|
| 5 | 明確指出 UI/UX 核心問題,有檔案位置,有可執行改法,能區分正式版與 demo |
| 4 | 問題清楚,建議可執行,但缺少部分檔案層級細節 |
| 3 | 有合理觀察,但偏泛用建議 |
| 2 | 大量空泛設計語言,沒有對應承富工作情境 |
| 1 | 只講美感或只講技術,沒有產品判斷 |
| 0 | 聚焦到安全性或與本次需求無關 |

最低可接受審計輸出:

- 至少 15 個 findings
- 至少 8 個 UI/UX findings
- 至少 1 個新首頁 IA
- 至少 1 個任務工作流 wireframe
- 至少 1 份分階段 roadmap
- 不得包含安全性審計

---

## 12. 建議補充給外部 AI 的截圖

若外部 AI 可看圖片,請提供:

1. 正式版首頁截圖:`http://localhost/`
2. 工作包頁截圖:`http://localhost/#projects`
3. 工作流頁截圖:`http://localhost/#workflows`
4. 新版 demo 截圖:`http://localhost/ui-demo`
5. 手機版 demo 截圖

目前已有 demo 截圖:

- `reports/ui-vnext-demo-v5-final-2026-04-25.png`
- `reports/ui-vnext-demo-v4-mobile-2026-04-25.png`

若外部 AI 無法看圖片,請直接使用本文件第 6.1 與 6.2 的文字 wireframe。審計時仍應完整回答 UI density、資訊架構、手機版與 task flow 問題,不能因為無圖而只做程式碼審查。

---

## 13. 審計後預期決策

外部 AI 審計完成後,應能幫助決定:

1. 正式版是否繼續沿用 5 Workspace,或改成任務收件箱主導。
2. `/ui-demo` 是否作為 vNext 主方向。
3. 哪些功能應從第一層移除。
4. 工作包是否成為主心智模型。
5. Agent 是否完全降級成背景處理模組。
6. 哪些 UI/UX 修正是交付前必要項。
7. v1.4 的最小可交付範圍。

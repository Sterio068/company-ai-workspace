# UI/UX Refactor Plan · 2026-04-24

> 目標:把承富 AI 從「功能很多的入口頁」重構成「每天真的拿來工作的 AI 作業系統」。
> 視角:系統設計 / 產品 UX / 前端資訊架構,不是單純美化。

## 一句話結論

目前 UI 難用的核心不是視覺風格,而是**功能平鋪 + 概念重疊 + 任務路徑不夠單一**。

現在的 Launcher 同時承擔:

- AI 聊天入口
- 5 Workspace
- Project / Handoff
- Workflow
- 標案 / CRM / 會計
- 知識庫 / Skills
- 會議 / 媒體 / 社群 / 場勘
- Admin / 使用者管理 / 教學

這些功能都合理,但不應該都在同一層讓使用者選。下一輪應該從「找功能」改成「接續一件工作」。

## 目前功能地圖

| 類別 | 現有功能 | 目前問題 |
|---|---|---|
| 開始工作 | Dashboard、今日工作台、5 Workspace、常用、全域工具 | 同時有太多起點,使用者不知道哪個才是主入口 |
| AI 對話 | 主管家、9 專家、Chat pane、歷史、附件、L1/L2/L3 提示 | Chat 是核心,但像浮動插件,沒有穩定任務脈絡 |
| 專案脈絡 | Projects、Handoff、collaborators、next_owner、project drawer | Project 很重要,但不是全產品的主舞台 |
| 工作流 | Workflow draft-first、adoption tracking | 概念好,但和 Workspace / Chat / Project 的關係還要靠使用者理解 |
| 業務工具 | Tenders、CRM、Accounting | 應屬「營運中樞」,不該和日常 AI 任務同層 |
| 內容與資料 | Knowledge、Skills、Agent source、Help docs | 知識庫是背景能力,不該讓一般使用者像在管理 CMS |
| 外部輸入 | Chrome Extension、Meeting、Site Survey、Media、Social | 都是「資料進入專案」的入口,目前被拆成多個目的地 |
| 管理 | Admin、Users、Permissions、Budget、Audit | 老闆 / Champion 需要,一般同仁不該在主導航看到 |

## 主要 UX 痛點

### 1. 導航層級過載

目前 sidebar 有 Dashboard、5 Workspace、專案、CRM、標案、會計、技能庫、Workflow、知識庫、Admin、Users、會議、媒體、社群、場勘、教學等入口。這對 AI 小白不是「功能完整」,而是「不知道該按哪裡」。

### 2. Workspace、Workflow、Agent、全域工具概念互相打架

使用者真正想做的是「寫標案」「做活動」「整理會議」「回客戶」。但畫面同時問他要選 Workspace、Workflow、Agent、Slash command 或 Project。這會讓人覺得系統需要先學會分類法才能用。

### 3. Project 沒有成為第一級心智模型

承富的真實工作不是一次對話,而是一個案子。Project / Handoff 已經有後端能力,但 UI 還沒有把「每件工作都回到專案包」做成唯一主線。

### 4. Chat 是核心,但被做成側邊工具

Chat pane 可用,也能串流、回饋、存交棒,但它不是畫面中心。使用者需要先理解自己在哪個 view,再呼叫 chat。這和「AI 使用」的直覺相反。

### 5. 同一畫面出現過多層浮動物件

現有 UI 可能同時有 sidebar、mobile bottom nav、chat pane、project drawer、modal、palette、inspector。每個都合理,但疊在一起會造成「我現在在哪一層」的迷失。

### 6. 許多入口是名詞,不是動詞

「CRM」「Skills」「Knowledge」「Workflow」「Accounting」對開發者清楚,但對承富同仁更自然的是:

- 找標案
- 寫提案
- 整理會議
- 做活動 brief
- 存到專案
- 交給下一棒
- 看本週卡點

### 7. Mobile 不是小版 desktop

現在 mobile 仍承載 Dashboard + hero + workbench + ROI + workspace grid + tools + projects。手機現場使用應該只做 3 件事:拍、說、存到專案。

## 跳出框架的重構方向

### 新核心物件:Work Packet 工作包

不要再讓使用者從功能開始。系統主體改成一個「工作包」:

```text
工作包 = 專案 + 目標 + 素材 + AI 對話 + 交棒卡 + 下一步 + 產出物
```

所有功能都變成工作包裡的能力:

- 標案監測 → 可建立投標工作包
- 會議速記 → 可追加到工作包
- 場勘 → 可追加到工作包
- Chat 回答 → 可存回工作包
- Workflow → 是工作包的建議流程
- CRM / 會計 → 是工作包的營運資料

### 新資訊架構:3 個主區 + 1 個全域 Composer

| 新主區 | 給誰 | 放什麼 | 舊功能收斂 |
|---|---|---|---|
| Today 今天 | 所有人 | 今天該接續的工作包、最近交棒、AI 建議下一步 | Dashboard、今日工作台、最近專案、常用 |
| Work 工作包 | PM / 設計 / 公關 | 每個案子的 cockpit,含 Chat、Handoff、素材、產出、Workflow | Projects、Workspace、Chat、Meeting、Site Survey |
| Library 資料庫 | PM / Champion | 知識、技能、媒體、CRM、過往標案、素材 | Knowledge、Skills、Media、CRM、Tenders |
| Ops 營運 | 老闆 / Admin | 費用、權限、使用者、採用率、品質、備份狀態 | Admin、Users、Accounting、Audit、Budget |

全域 Composer 固定存在:

```text
我要做什麼? [輸入需求 / 貼資料 / 上傳 / 錄音]
範例:幫我把這份會議記錄整理成下一步,存到環保局案
```

Composer 先判斷意圖,再引導到工作包或工具,而不是叫使用者先選工具。

## 目標體驗

### 首頁:不是 Dashboard,是「今天要接哪一棒」

首頁只保留 3 個區塊:

1. **今日接續**:你負責 / 下一棒是你 / 快到期 / 有新素材。
2. **一句話開始**:貼資料、輸入需求、拖檔案、錄音。
3. **最近工作包**:每張卡顯示目前狀態、下一步、最後產出。

拿掉或下沉:

- 大 hero 文案
- 全域工具卡
- Workspace 大卡牆
- ROI 三儀表,移到 Ops / 老闆視圖

### Work Packet Cockpit:所有工作只在一個地方接續

每個工作包的畫面分 4 欄或 4 tab:

| 區塊 | 用途 |
|---|---|
| Brief | 目標、客戶、期限、預算、資料敏感度 |
| Timeline | 會議、場勘、Chrome 帶入、標案、AI 回答紀錄 |
| Chat | 帶著此工作包脈絡的 AI 對話 |
| Handoff | 下一步、風險、素材、產出物、下一棒 |

這會把 Project、Chat、Workflow、Handoff 合成一個主舞台。

### Workspace 改成「Playbook」而不是頁面

Workspace 不再是主導航頁,而是工作包裡的 Playbook:

- 投標 Playbook
- 活動 Playbook
- 設計 Playbook
- 公關 Playbook
- 營運 Playbook

建立工作包時選 Playbook,之後它只影響建議步驟與模板,不再要求使用者一直切 Workspace。

### 工具變成「能力抽屜」

Meeting、Site Survey、Media、Social、Accounting 不再佔主導航。它們應該在工作包裡以能力出現:

- 加入會議紀錄
- 加入場勘照片
- 找媒體名單
- 排社群貼文
- 試算預算 / 毛利
- 查知識庫

這樣功能還在,但認知負荷少很多。

## 新視覺方向

### 方向:Calm Command Center

不是炫技的 AI UI,而是沉著、乾淨、有掌控感的作業室。

視覺原則:

- 大幅減少卡片數量,每頁最多 3 個主要決策。
- 用「狀態列 / 時間線 / 下一步」取代卡片牆。
- Chat 成為工作包核心區域,不是右側浮窗。
- 顏色只標示狀態和情境,不要每個功能一個顏色。
- Mobile 只保留現場捕捉模式,不塞完整桌面資訊。

### 介面隱喻

用「案場作戰室」取代「SaaS dashboard」:

- Today = 案件調度板
- Work Packet = 案件作戰室
- Library = 公司資料室
- Ops = 控制室

## 分階段重構計劃

### Phase UX-0 · 盤點與凍結

目標:先不加新 UI,凍結現有功能入口。

- 建立 UI route inventory。
- 標記每個功能屬於 Today / Work / Library / Ops 哪一層。
- 標記哪些入口一般同仁要看,哪些只給 Admin。
- 建立「舊入口 → 新位置」mapping。

交付:

- `docs/UI-UX-ROUTE-INVENTORY.md`
- `docs/UI-UX-REFACTOR-MAPPING.md`

### Phase UX-1 · 新首頁 Today

目標:把首頁從功能牆改成接續工作。

改動:

- 移除首頁大 hero / workspace card wall / global tools wall。
- 新增 Today queue:
  - 下一棒是我
  - 快到期
  - 最近有新素材
  - 有 AI 草稿待確認
- 新增 universal composer。
- 最近工作包取代進行中專案預覽。

驗收:

- 新同仁 10 秒內知道可以輸入需求或點一個工作包。
- 首頁主 CTA 不超過 2 個。

### Phase UX-2 · Work Packet Cockpit

目標:把 Project / Chat / Handoff / Workflow 合併成一個工作主畫面。

改動:

- Project drawer 升級為 full-page cockpit。
- Chat pane 可 dock 到工作包內。
- Handoff 四格卡成為右側固定面板。
- Workflow draft 顯示在 Timeline,不另開孤立頁。
- Meeting / Site Survey push 後出現在 Timeline。

驗收:

- 使用者能從一個工作包完成「看背景 → 問 AI → 存答案 → 指派下一棒」。

### Phase UX-3 · Navigation Collapse

目標:把 15+ 側邊欄入口壓成 4 個。

新導航:

- Today
- Work
- Library
- Ops

角色規則:

- USER 預設只看 Today / Work / Library。
- ADMIN 才看 Ops。
- Mobile 只看 Capture / Today / Work。

舊功能位置:

- Tenders → Library / Opportunity source,也可建立 Work Packet。
- CRM / Media → Library。
- Accounting → Ops + Work Packet finance tab。
- Skills / Knowledge → Library。
- Meeting / Site Survey / Social → Work Packet capability drawer。
- Help → Command menu / account menu。

驗收:

- sidebar 入口從 15+ 降到 4。
- 常用任務仍可 1-2 click 到達。

### Phase UX-4 · Mobile Field Mode

目標:手機不要像桌面縮小版。

Mobile 主功能:

- 拍照
- 錄音
- 文字備註
- 選 / 建立工作包
- 送 AI 分析

拿掉:

- ROI
- 大量 Workspace 卡
- Admin 表格
- 複雜 sidebar

驗收:

- 現場人員單手可完成場勘輸入。

### Phase UX-5 · Ops / Boss View

目標:老闆看價值,Champion 看維運。

Ops 分兩層:

- Boss:採用率、省時估算、熱門工作包、卡點、成本。
- Champion:使用者、權限、備份、錯誤、API key、知識庫維護。

驗收:

- 老闆 30 秒內知道本週 AI 是否有價值。
- Champion 30 秒內知道系統是否健康。

## 具體刪減建議

| 現在 | 建議 |
|---|---|
| Dashboard hero | 刪或縮成一句 status line |
| 5 Workspace 大卡 | 改成建立工作包時選 Playbook |
| 全域工具卡 | 改成 Composer slash / ability drawer |
| Projects drawer | 升級成 Work Packet full page |
| Workflows 獨立頁 | 改成 Work Packet 裡的建議流程 |
| Meeting / Site / Social 獨立入口 | 改成工作包內「加入素材 / 產出」能力 |
| Admin 混在主 nav | 只給 Admin 的 Ops 區 |
| Help 主 nav | 移到 command palette + account menu |

## 第一刀建議

先不要重寫全部。第一刀做最有槓桿的 3 件事:

1. **首頁改成 Today queue + Composer**。
2. **Project drawer 升級成 Work Packet cockpit prototype**。
3. **sidebar 壓成 Today / Work / Library / Ops,舊入口先藏在次層**。

這三刀會立刻降低複雜度,同時不刪任何既有功能。

## 成功指標

- 首頁可見主 CTA 從 10+ 降到 2。
- sidebar 主入口從 15+ 降到 4。
- 新使用者第一次有效任務從「找入口」改成「輸入一句話」。
- 每個 AI 回答都有明確去處:存到工作包、變下一步、變產出物、或丟棄。
- Mobile 首屏只服務現場捕捉,不承載桌面全功能。

## 風險與守門線

- 不要一次砍掉所有舊頁。先做新 IA,舊頁保留在 hidden/legacy route。
- 不要改 LibreChat fork。Launcher 仍維持外層整合。
- 不要讓 universal composer 自動送出敏感資料。仍要保留 L1/L2/L3 preflight。
- 不要把 Admin ROI 塞回一般使用者首頁。Boss value 與 daily work 要分開。

## 結論

承富 AI 下一階段不該再追求「看起來功能更多」。它應該變成:

```text
今天我要接哪一棒?
這個案子的脈絡是什麼?
AI 幫我把下一步做出來。
做完存回工作包,下一個人接得上。
```

只要這條主線成立,其他功能都可以退到背景。這就是讓系統真的比 GPT 網頁版好用的關鍵。

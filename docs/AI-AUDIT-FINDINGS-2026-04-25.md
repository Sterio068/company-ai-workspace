# 承富 AI 系統 · 4-Agent 審計結果彙整

> 日期:2026-04-25
> 方法:並行跑 3 個審計 agent(產品策略 / UI/UX / 架構)+ 1 個 meta-review agent
> 委託文件:`docs/AI-AUDIT-BRIEF-FORMAL-2026-04-25.md`
> 明確排除:資安 / 滲透 / 密鑰 / 個資 / 法遵 / 權限繞過

---

## TL;DR · 給老闆看的 3 問

### Q1 · 3 個 AI 都說要大改 · 真的該大改嗎?

**不要一次大改**。3 份報告有 70% 共識 · 但他們都讀同一份 brief · 集體往「更像 ChatGPT」的方向推。承富的價值**不在變得更像 ChatGPT**(因為 ChatGPT 免費)· 而在於「系統知道承富的客戶 / 標案 / 知識庫 / 上個月做過什麼」。這個差異化藏在會計 / CRM / 工作包 / 標案 cron 裡 · 不在輸入框長什麼樣。

### Q2 · 如果只能做 3 件事,建議做哪 3 件?

1. **拆 app.js 成模組 + esbuild cutover**(1 週 · 不改 UX · 技術債清理 · 全站載入 +30%)
2. **chat 完整綁 project_id · AI 回覆一鍵存工作包 · 交棒卡 AI 預填 + 一鍵複製 LINE/Email**(2 週 · 這是真正承富 > ChatGPT 的差異化)
3. **Agent 對同仁改名為「小編 / 投標顧問 / 會計師」等角色稱 · 保留可見(不叫 Agent)· 同時讓老闆儀表板更亮**(1 週 · ROI narrative)

合計 **4 週** · 不動 sidebar / 不動 Workspace / 不引進 intake-form。

### Q3 · 最可能的失敗模式是什麼?

- **Scenario A(最可能)**:同時做 6 件共識 MVP · v1.4 延到 v1.6 · 中間 3 版 half-finished · 老闆不耐
- **Scenario B(第二可能)**:照 3 AI 建議全改 intake-form + 3 項 sidebar · 變成「另一個 ChatGPT 皮膚」· 同仁回去用免費 ChatGPT
- **Scenario C(推薦)**:承認 3 AI 是對 UX 層審計 · 不是 product 層 · 聚焦後端差異化 · 文字視覺只小 polish · v1.5 再談結構性大改

---

## 審計方法

| Agent | 角色 | Prompt 來源 | Findings |
|---|---|---|---|
| **A · general-purpose** | B2B SaaS 產品策略顧問 | brief §10.1 Mini-prompt A | 20 |
| **B · general-purpose** | 繁中 UI/UX 審計專家 | brief §10.1 Mini-prompt B | 17 |
| **C · architect** | 前端架構與產品工程 | brief §10.1 Mini-prompt C | 24 |
| **Meta · general-purpose** | 審計者的審計 | 獨立 prompt · 讀 3 份結論 | 7 集體盲點 + 3 錯誤 + 3 矛盾 |

3 個審計 agent 並行執行 · meta-review 隨後獨立跑。全部繁體中文輸出 · 排除資安審計。

---

## 報告 A · 產品策略審計(20 findings)

### A · Executive Summary

系統已具備完整骨幹(10 Agent · 5 Workspace · Project Handoff · FastAPI 會計 · 半自動 workflow · v1.3 已 ship)· 工程驗收也過。但**產品定位仍在「功能後台 + Agent 選單 + 聊天工具」三者之間游移** · 使用者從 sidebar 看到 4 + 5 + 14 + 3 共 26 個入口 · 第一眼無法回答「我今天要做什麼」。`/ui-demo` 方向(任務導向三欄)比正式版更接近使用者真實情境 timeline · 但互動仍為前端模擬。

**交付狀態**:**有條件可交付**(可上線給 Champion + 2-3 位早期採用者試跑 · 但全員上線前必須收斂 IA)。

**3 個最重要修正方向**:
1. 把「工作包 + 下一棒」變成唯一主心智模型 · Agent 從前台詞彙消失
2. 首頁 sidebar 砍到 4 項(今日 / 工作包 / 資料庫 / 中控)· 15 個次層功能收進「工具箱」或 ⌘K
3. 把 `/ui-demo` 的「輸入 → 系統判斷 → 交付品 → 存工作包」接回真實 API · 變成正式版主入口

### A · Findings 表(20 項)

| 編號 | 嚴重度 | 面向 | 檔案/位置 | 問題 | 建議修正 |
|---|---|---|---|---|---|
| F01 | P0 | 定位 | `AI-HANDOFF.md` L11-14, `index.html` L7 | 自稱「AI 協作平台 / 智慧助理 / 10 人協作平台」· 定位散 | slogan 改「承富工作包 · 丟進來就有下一棒」 |
| F02 | P0 | IA | `index.html` L28-236 sidebar | 平鋪 4 主區 + 5 Workspace + 14 次層 + 3 快速工具 = 26 個入口 | sidebar 砍到 4 項:今日 / 工作包 / 資料庫 / 中控 |
| F03 | P0 | 心智 | `index.html` L362-406 projects + L509-525 workflows + `modules/chat.js` chat pane | 「對話 / 工作包 / 流程模板 / 建議下一步」四個入口是同一件事的不同切面,但各自獨立 | 以工作包為容器 · 對話 / workflow / handoff 全是 tab |
| F04 | P0 | Agent 揭露 | `config.js` L43-54 `CORE_AGENTS` | 前台到處「Agent / 主管家 / 專家 / 技能庫 29」 | 前台只留「輸入要做什麼」· Router 隱形 |
| F05 | P0 | 首屏 | `index.html` L290-310 + L312-336 + L338-350 | 首屏 7 個區塊 | 只留「今日接續 + 輸入框」· 其餘收合 |
| F06 | P1 | Workspace | `config.js` L57 `WORKSPACE_TO_AGENT` | 5 Workspace → Agent 1:1 hardcoded · 只是 Agent 換皮 | 降格為工作包建立時的流程模板選項 |
| F07 | P1 | 主心智 | `index.html` L781-837 `#project-drawer` | 工作包藏 drawer · handoff 4 格預設收合 | handoff 展開為預設 · 工作包改主 view |
| F08 | P1 | 命名 | `index.html` L40/44/48 | 幾何符號當 icon · 「資料庫」對 PM 太技術 | 改 SVG + 文字 · 「資料庫」改「資料櫃」· 「中控」改「老闆儀表板」 |
| F09 | P1 | 密度 | `index.html` L209-236 快速工具區 | sidebar 放 slash command 等於承認「已找不到功能」 | 刪除此區 · slash 由 ⌘K 觸發 |
| F10 | P1 | 次層 | `index.html` L104-205 | 14 項平鋪 · 工作包重複 | 拆工作包衍生 / 老闆功能 / CRM 三來源 |
| F11 | P1 | 差異化 | `AI-HANDOFF.md` L19-32 | 差異化在後台 · 前台體感 ≈ ChatGPT | 回答自動回寫工作包 / 交棒卡複製 LINE/Email / TODO 進儀表板 |
| F12 | P1 | 文案 | `index.html` L276-308 | 同時講 3 件事 | 簡化為「今天要做什麼?我幫你處理到可以交棒」+ 大輸入框 |
| F13 | P1 | app.js 大小 | `app.js` 1731 行 | 跨 Dashboard/Projects/Skills/鍵盤/導航多責任 | 拆 entry + views/*.js · 每檔 <400 行 |
| F14 | P1 | demo 對齊 | `ui-vnext-demo.html` L21-26 | mode switcher 多餘 · 四步 hardcoded | 刪 switcher · 四步改即時進度 skeleton |
| F15 | P2 | 隱藏元素 | `index.html` L353-359 | hidden 的 `hero-input / core-agents-grid / roi-row` | v1.4 清掉 |
| F16 | P2 | Inspector | `index.html` L727-775 | 右欄爭搶注意力 · 行動版完全沒用 | 預設收合 · 只 ADMIN 展開 |
| F17 | P2 | 工作包空態 | `index.html` L400-404 | 「選一個工作包」太抽象 | 改 3 個範例卡片(招標 Go/No-Go / 客戶會議 / 中秋活動)一點即建 |
| F18 | P2 | v1.4 範圍 | `docs/ROADMAP-vNext.md` L103-109 | 5 件事沒排序 | 鎖定「工作包主心智 + Agent 背景化 + IA 砍半 + chat-to-project 回寫」四件 |
| F19 | P2 | Agent JSON 命名 | `config-templates/presets/00-09*.json` | 檔名含中文 | 改 ASCII · 中文名留 JSON 欄位 |
| F20 | P2 | 技能庫揭露 | `index.html` L142-150 | 「技能庫 29」是內部實作詞 | 前台移除 · 管理區可保留 |

### A · 建議產品定位

**Slogan 三選項**(推薦 #1):
1. **「承富工作包 · 把今天的工作交給下一棒」** ← 推薦 · 對上 timeline
2. 「承富 AI 工作台 · 丟進來就有交付品與下一棒」
3. 「承富的公司大腦 · 每個工作都接得上」

**目標用戶 persona**:

| # | 角色 | 使用時間 | 日常情境 |
|---|---|---|---|
| P1 | Linda PM(30 歲女 · 政大公行 · 4 年) | 60% | 一天管 3-5 案子 · 不想開 2 個工具 |
| P2 | 王總(50 歲男 · 老闆) | 15% | 一週 2-3 次 · 只看儀表板 · 不寫字 |
| P3 | 小陳設計師(25 歲) | 15% | 看交棒卡 5 秒知道要做什麼 |
| P4 | 財會阿姨 | 5% | 只用會計模組 · 不碰 AI |
| P5 | 公關 Jay(重度 ChatGPT 用戶) | 5% | 要給他留下來的理由 |

**不是什麼(what we are NOT)**:
- 不是 ChatGPT 複製品
- 不是 Agent 選單
- 不是公司營運系統
- 不是 Notion / Asana
- 不是知識庫搜尋引擎
- 不是技術展示

### A · 建議首頁 IA

第一層 sidebar 只 4 項:
```
[今日]        · 今天要處理的工作包 + 輸入框(首屏)
[工作包]      · 所有工作包列表(搜尋 / 篩選 / 交棒狀態)
[資料櫃]      · 知識庫 + 過往案例 + 品牌規則
[儀表板]      · ADMIN 才見 · 成本 / 用量 / 團隊 / 會計 / 管理
```

角色化首頁:

| 角色 | 首頁第一屏 | 主 KPI |
|---|---|---|
| PM(Linda) | 今日接續:3 個工作包下一棒 + 大輸入框 | 今天要推的下一棒 |
| 設計師 / 同仁 | 我收到的交棒卡 + 大輸入框 | 別人丟給我什麼 |
| 老闆(王總) | 儀表板首頁 | 公司整體狀態 |
| 財會 | 會計首頁 | 本月帳 |

工作包內部(Tab):
```
[對話] [交棒卡] [素材] [產出] [下一步] [歷史]
```

### A · Roadmap

**1-3 天**:首頁收合 6 區塊 / sidebar 刪主管家 + 快速工具 / slogan 改 / CTA 簡化
**1 週**:sidebar 重構 4 項 / 工作包 drawer 改 view / handoff 預設展開 / chat 綁 project_id
**2-3 週**:chat 結束自動摘要寫 handoff / 交棒卡複製 LINE+Email 格式 / `/ui-demo` 接真 API / app.js 拆檔
**1-2 個月**:LINE/Email 整合 / 自動下一步偵測 / 跨工作包搜尋 / 老闆月報

---

## 報告 B · UI/UX 審計(17 findings)

### B · 一句話總評

系統目前更像:**功能後台**(接近「公司營運系統 + Agent 選單」的混合體)。

**交付狀態**:**有條件可交付**。功能達 DoD · 但 IA 過度堆疊 · 首屏與 sidebar 傳達「我們有很多工具」而不是「你把工作丟進來」。建議以 `ui-vnext-demo.html`「任務收件箱」收斂 · 保留正式版的工作包 / 權限 / 知識庫基礎。

### B · Findings 表(17 項)

| 編號 | 嚴重度 | 面向 | 檔案:行號 | 問題 | 建議修正 |
|---|---|---|---|---|---|
| F-01 | P0 | IA / 首屏 | `index.html:17-237` | 25 個入口 · 使用者必須建立「今日 vs 工作包 vs Workspace vs 次層 vs 快速工具」5 同層概念 | 砍到 4 個主要 entry:收件箱 / 工作包 / 知識庫 / 我的 |
| F-02 | P0 | 首屏 | `index.html:290-310` | textarea + 3 個按鈕(建立工作包 / 看所有 / 交給主管家)· 使用者停頓 | 改單一 CTA「送給承富 AI 處理」 |
| F-03 | P0 | 任務輸入 | `index.html:295-310` vs `ui-vnext-demo.html:35-68` | 正式版缺 drop zone / prompt bank / process preview | 把 demo 的 intake-form 整個搬進正式版首頁 |
| F-04 | P1 | 導航 | `index.html:104-205` | 次層 14 項並列 · 工作包重複 | 工作包內情境下拉 + 管理員中控二分 |
| F-05 | P1 | 術語 | `index.html:48/51/227/233/913` | 「中控 / 管理面板 / Ops」3 稱呼 · 「助手 / Agent / 主管家 / 智慧引擎」4 稱呼 | 全站只用:承富 AI / 助手 / 流程 |
| F-06 | P1 | 自動分派 | `index.html:934-978` vs `ui-vnext-demo.html:95-116` | 正式版 chat-pane 沒顯示系統做了什麼 | 採 demo 的 process-list + source-list 卡片 |
| F-07 | P1 | 附件 | `index.html:957/976-977` | 沒有「系統會讀這些」視覺確認 | 附檔後顯示「✔ 招標須知.pdf · 已讀取」chips |
| F-08 | P1 | 交付品 | `index.html:934-978` | AI 回覆塞聊天氣泡 · 不能分頁編輯 | 採 demo 的 artifact-window 分 4 tab(摘要/任務/交付/交棒) |
| F-09 | P1 | 交棒卡 | `index.html:780-836` | 交棒卡 details 預設收合 · AI 沒自動填 · PM 手填 4 textarea | AI 產出時直接預填 4 欄位草稿 · PM 只需檢查 |
| F-10 | P2 | 視覺階層 | `launcher.css:462-561,564-621` | 首屏連續兩個巨大 hero · 資訊密度高 | 一行品牌 + 大輸入框 + 4 chip + 3 縮圖 · 其餘折疊 |
| F-11 | P2 | 卡片密度 | `index.html:430-478,568-660` | 會計 view 4 stat + 2 block · admin 12 stat + 3 list · 無優先級視覺差 | 每 view 限 1 主 + 3-4 次 · 用大小/顏色引導 |
| F-12 | P1 | empty | `index.html:330/399/501` | 多處只「還沒有...」或「載入中」 | 每個 empty 要有:說明 + CTA + 1 分鐘 demo 資料 |
| F-13 | P1 | 文案 | 全站 | 「中控 / 次層功能 / 流程模板 / 技能庫 / 建議下一步 / 商機漏斗」都是內部分類 | 見 §5 文案替換表 |
| F-14 | P2 | 手機 | `launcher.css:155-158` | 直接隱藏 sidebar · 沒分步流程 | 分步 wizard(拍照→描述→結果)+ 底部 3-tab bar |
| F-15 | P2 | loading | `index.html:319/331/501` | 無 skeleton · 沒 timeout | 4 位置用 skeleton · 10 秒 timeout 顯示「連線變慢 · 重試」 |
| F-16 | P2 | 鍵盤 | `index.html:30-52` | `<a>` 沒 href · Tab 無法拾取 | 改 `<button>` 或補 href · WCAG 2.1.1 |
| F-17 | P2 | 對比 | `launcher.css:28` | `--text-tertiary: #C7C7CC` 白底 ≈ 1.5:1(AA 需 4.5) | 改 `#8E8E93`(≈ 4.6:1) |

### B · 新首頁 wireframe(ASCII)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [承富 AI]   收件箱     工作包     知識庫              [👤 小玉 / ⌘K]  │
└─────────────────────────────────────────────────────────────────────────┘

                 早安 小玉 · 今天是週二 4/24

┌─────────────────────────────────────────────────────────────────────────┐
│   把工作丟進來,我先幫你看、想、分配、寫出來                           │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  例:幫我看這份招標須知,整理缺件清單、判斷要不要接        │    │
│  │  ─────────────────────────────────────────────────────────     │    │
│  │  📎 把檔案拖進來 · PDF / Word / Excel / 圖片 / 錄音              │    │
│  └────────────────────────────────────────────────────────────────┘    │
│  快速開始:                                                              │
│  [ 標案判斷 ]  [ 會議交棒 ]  [ 活動企劃 ]  [ 寫新聞稿 ]  [ 場勘 ]       │
│                                           [ 送給承富 AI 處理 →  ⌘⏎ ]    │
└─────────────────────────────────────────────────────────────────────────┘

接續你昨天的工作                                  看全部工作包 →
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ 環境部宣導案    │  │ 中秋快閃提案   │  │ 文化局標案     │
│ 下一棒:阿銘   │  │ 下一棒:我    │  │ 已結案        │
│ ⏰ 5/2 截止    │  │ 草稿待確認    │  │                 │
└────────────────┘  └────────────────┘  └────────────────┘

最近 AI 幫你做的事                                看全部 →
  · 09:42  把昨天客戶會議整理成 3 個分工(→ 環境部宣導案)
  · 昨天   判斷新竹市標案不建議投
  · 昨天   產 2 份中秋節主視覺 brief(已傳給設計師)
```

任務進行中狀態(取代目前 chat-pane):

```
┌─ 任務:把這份招標須知做 Go/No-Go ───── [返回]  [存成工作包] ─┐
│  ①讀取 ✓      ②比對資料 ✓      ③分派模組 ●處理中    ④產出草稿         │
│  ─────────────────────────────────────────────────────────    │
│  📎 本次使用資料:                                                  │
│  ✓ 招標須知.pdf (你上傳的)                                          │
│  ✓ 承富 2024 文化活動履約案例 (公司知識庫)                         │
│  ◻ 預算表 (尚未上傳)                                              │
│  ┌─────────────────────────────────────────────────┐             │
│  │ [摘要] [任務清單] [送件檢查] [交棒卡]          │             │
│  ├─────────────────────────────────────────────────┤             │
│  │ 建議:有條件投標(信心度 72%)                │             │
│  │ 理由:履約足 · 但需補三份材料                │             │
│  │ [ 編輯 ]  [ 複製成客戶信 ]  [ 用 Word 匯出 ]    │             │
│  └─────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### B · 手機版分步 wizard

```
首頁(iPhone 14)        加附件?             處理中
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  承富 AI         │   │   加入附件?      │   │   處理中...      │
│  👋 早安 小玉    │   │   [📷 拍照]       │   │   ① 讀取 ✓       │
│                  │   │   [🖼 相簿]       │   │   ② 比對資料 ✓  │
│  今天要做什麼?   │   │   [📄 檔案]       │   │   ③ 分派 ●      │
│  ┌────────────┐  │   │   已加入:        │   │                   │
│  │           │  │   │   • 招標須知.pdf  │   │   本次讀了:      │
│  └────────────┘  │   │   [跳過] [下一步] │   │   ✓ 招標須知.pdf │
│  [🎯][🎪][📣][📸]│   │                   │   │   ✓ 歷年案例     │
│  [ 送出  →  ]    │   │                   │   │                   │
└──────────────────┘   └──────────────────┘   └──────────────────┘
 [收件] [包] [我]        [收件] [包] [我]         [收件] [包] [我]
```

場勘情境:step1 拍照 → step2 地點+描述 → step3 AI 生出風險/建議 → [存工作包][傳 PM]

### B · 繁中文案替換表(22 條)

| 舊文案 | 位置 | 新文案 | 理由 |
|---|---|---|---|
| 今日 | `index.html:36` | 收件箱 | PM 心智模型 |
| 資料庫 | `index.html:46` | 公司知識庫 | 「資料庫」像 IT |
| 中控 | `index.html:51` | 管理(移到 user menu) | 內部術語 |
| 流程模板 | `index.html:56,340` | 快速開始 / 常見任務 | 動作導向 |
| 次層功能 | `index.html:105` | (整段刪) | 暴露 IA 痕跡 |
| 商機漏斗 | `index.html:115,531` | 客戶案子追蹤 | 「漏斗」是業務術語 |
| 標案監測 | `index.html:124,485` | 新標案通知 | 「監測」像保全 |
| 技能庫 | `index.html:142` | (移除) | 一般人不懂「技能」 |
| 建議下一步 | `index.html:151` | (併入送出按鈕後顯示) | 獨立 view 不合理 |
| 管理面板 | `index.html:168` | 管理中控(admin) | 「面板」語義弱 |
| 主管家 | `index.html:227,924,1049` | 承富 AI | 「主管家 / Agent」打架 |
| 智慧引擎 | `index.html:238-248` | (刪元件) | 使用者不該看到「主力 / 備援」 |
| 承富智慧助理 | `index.html:22` | 承富 AI | 簡短有識別 |
| 今天要把哪一棒往前推? | `index.html:293` | 今天要做什麼?把需求丟進來 | 「棒」老闆語言 |
| 3 CTA(建立工作包/看所有/交給主管家) | `index.html:299-301` | (合併為 1 個)送給承富 AI | 同等權重沒主次 |
| 10 人協作平台 | `index.html:23` | (刪)或「承富創意整合行銷」 | 「10 人」是內部數字 |
| 幫我把今天客戶會議整理...(placeholder) | `index.html:297` | 例:幫我看這份招標須知,整理缺件清單、判斷接不接 | 具體到附件+動作 |
| 先接一件工作 · 不是先找工具 | `index.html:306` | (刪 sidecar 整個) | 看 10 次是雜訊 |
| 🤝 交棒卡 · 給下一位同事看 | `index.html:811` | 傳給下一位同事 | 「卡」Jira 術語 |
| 載入今日下一步… | `index.html:319` | (換 skeleton) | 無資訊 |
| 工作包 | (保留) | 保留 | 已經很好 |
| 建立工作包 | (保留 for 場景) | 保留 | 動作清楚 |

### B · a11y WCAG 2.2 違反點(8)

| WCAG | 等級 | 檔案:行號 | 問題 | 修補 |
|---|---|---|---|---|
| 1.4.3 Contrast | AA | `launcher.css:28` `--text-tertiary: #C7C7CC` | 白底 ≈ 1.5:1(< 4.5:1) | 改 `#8E8E93` |
| 2.1.1 Keyboard | A | `index.html:30-205` `<a>` 無 href | Tab 無法拾取 | 改 `<button>` 或補 href + role |
| 2.4.3 Focus Order | A | sidebar `<details>` 收合 | item 仍被 Tab 拾取 | 收合時加 `inert` 或 `tabindex=-1` |
| 2.4.7 Focus Visible | AA | `launcher.css:125-129` | focus ring 不清晰 | 加 `:focus-visible { outline: 2px solid var(--accent); }` |
| 2.5.8 Target Size | AA 新 | `launcher.css:213-216` sidebar-item min-height 38 | 手機 < 44px | 手機 media query 改 48px |
| 1.3.1 Labels | A | `index.html:297` textarea 只 sr-only label | 螢幕報讀資訊不足 | label 寫內容 · placeholder 放範例 |
| 4.1.2 Name/Role | A | `index.html:56` `<summary>` | 無 aria-expanded | 改 `<button aria-expanded>` |
| 3.3.2 Instructions | A | `index.html:296-297` | 不知能附檔 | textarea 下方固定「📎 可拖拉 · ⌘⏎ 送出」 |

---

## 報告 C · 架構審計(24 findings)

### C · 架構總評

Launcher 已具備成熟的 module 骨架(28 ES module + `app.js` 1732 行主控 + `launcher.css` 882 行 token system)。最大的結構風險不是「vanilla JS 本身」而是 `app.js` 單檔塞 6 個邏輯面向 / HTML 37 處 inline `onclick` 形成隱性耦合 / demo 與正式版 CSS token 雙軌定義。10 人承富場景 vanilla ES module 仍可維護無需上 React · 但不重構會在 v1.5 某 feature 同時改 Today / Projects / Work Detail 時崩潰。

**可維護性**:**需優化**(黃牌 · 不到警戒)

**前 3 結構風險**:
1. `app.js` 雙重角色(lifecycle + 多 view 渲染)
2. HTML `onclick` + `window.*` 全域 37 處(事件委派未全採用)
3. 設計系統雙軌 token · demo 併回時每條 rule 手動 remap

### C · Findings 表(24 項 · 節錄關鍵)

| 編號 | 嚴重度 | 面向 | 檔案:行號 | 問題 | 建議修正 |
|---|---|---|---|---|---|
| F-01 | P0 | 架構 | `app.js:72-1606` | app 物件 7 責任 · 1732 行 | 拆 5-8 module |
| F-02 | P0 | 模組 | `index.html:244/371/432/489/535/574...(37 處)` | inline `onclick="app.xxx()"` 耦合全域 | 全面改 `data-action` + 中央 dispatcher |
| F-03 | P0 | 模組 | `modules/README.md:14-27` | README 寫「v3.0 待拆」· 但 crm/tenders/workflows/admin 已拆 | 重寫 README 列 30 module 真實職責 |
| F-04 | P1 | 架構 | `app.js:286-301,247-282` | URL hash / data-view / `window.location` 三路 routing 並存 | 抽 `modules/router.js` · 單一入口 |
| F-05 | P1 | 模組 | `modules/knowledge.js:20-31` | knowledge → chat 隱性單向依賴 | 共同訂閱 projectStore · 不 import |
| F-06 | P1 | 模組 | `modules/config.js:43-54/136-170` | `STAGES`(CRM)獨立在 crm.js 定義 · 常數雙標準 | 所有 static data 歸 config.js 或拆 config/*.js |
| F-07 | P1 | 架構 | `app.js:1631-1700` | URL 意圖處理 3 個 DOMContentLoaded listener 順序脆 | 抽 `modules/boot.js · resolvePendingIntent()` |
| F-08 | P1 | 效能 | `index.html:1053` + module README | 31 個 HTTP/1.1 請求首屏 · Cloudflare Tunnel 慢 2-4 秒 | nginx 開 HTTP/2 + esbuild cutover 提前到 v1.4 |
| F-09 | P1 | 測試 | `tests/e2e/critical-journeys.spec.ts:1-188` | E2E 只 1 spec 13 case · PM timeline 8 步只 cover 2-3 | 加 3 spec:`project-handoff` / `workflow-draft` / `pm-timeline` |
| F-10 | P1 | 測試 | `tests/e2e/` | 無 visual regression · 無 axe-core a11y smoke | 加 `toHaveScreenshot` + `@axe-core/playwright` |
| F-11 | P1 | 模組 | `app.js:552-639` `renderTodayWorkbench` | 90 行函式 · 資料 + hardcode text + DOM 組裝混 | 抽 `today/workbench-cards.js` |
| F-12 | P1 | 架構 | `app.js:883-999` `renderWorkDetail` | 117 行 inline template-literal · `escapeHtml` 14 處漏一即 XSS | 用 `<template>` + `tpl()` |
| F-13 | P1 | 文件 | README / handoff / 模組數字 3 份文件 3 數字 | 外部團隊誤信結構 | 加 CI 檢查 · 對照 `ls modules/*.js` 結果 |
| F-14 | P1 | 架構 | `ui-vnext-demo.css:1-33` vs `launcher.css:7-50` | token 命名不交集(`--bg/--ink/--teal` vs `--accent/--text-primary`) | 先加 alias:`--panel: var(--bg-float)` 等 |
| F-15 | P2 | 模組 | `app.js:1517-1560` | `_paletteItems` hardcode 9 view · 跟 showView whitelist / sidebar 重複 | `const VIEWS = [{id,label,icon,shortcut,loader}]` 單 source |
| F-16 | P2 | 效能 | `launcher.css(882 rules · 48 token · 125 class)` | 單檔 CSS 無分段 | 拆 `styles/{tokens,sidebar,chat,projects,admin}.css` + HTTP/2 push |
| F-17 | P2 | 資料模型 | `routers/projects.py:44-74` | 缺 `priority / tags / ws_hint / draft_state / readiness_cached` | pydantic 加欄位 · UI 讀 cached score |
| F-18 | P2 | API | `app.js:440-452,487-495` | 3 端點 envelope 不統一 | 全後端用 `ApiResponse<T>` · 加 `wrap_response()` 裝飾器 |
| F-19 | P2 | 測試 | `test_main.py` + `tests/integration/` | 前端 JS unit test 0 個 | 加 vitest · cover util/tpl/projects/toast |
| F-20 | P2 | 文件 | `SYSTEM-DESIGN.md` vs `AI-HANDOFF.md:22` | 5 workspace 文件說法 vs index.html 實況有差 | 對照後更新 SYSTEM-DESIGN |
| F-21 | P2 | 架構 | `app.js:1609-1630` | 13 個 `window.*` 全域洩露 | 跟 F-02 一起處理 · 只留 `window.app` |
| F-22 | P2 | 效能 | `modules/crm/tenders/admin.js` | view init load-on-mount · 但 agents/conversations/usage/ROI/projects 在 init 並行 | inspector 內 lazy(IntersectionObserver) |
| F-23 | P2 | 模組 | `modules/chat.js:153-234 open()` | 6 步驟於單函式 · 新增 `openForProject` 要複製 | 拆 `_initConversation / _attachToView / _populateHandoffSave` |
| F-24 | P2 | 文件 | `DEPLOY.md` + installer | esbuild 未落地 + installer 版本漂移認知差 | DEPLOY.md 加「source vs installer 快照差異」一節 |

### C · app.js 拆分計畫

目前 1732 行。拆 7 module + 1 薄 entrypoint:

```
app.js(< 120 行 · 只 entry)
├── modules/app-init.js                (init / auth / user / hashchange / URL intent · 280 行)
├── modules/router.js                   (showView / VIEW_TO_WS / handleHashChange · 130 行)
├── modules/keyboard.js                 (setupKeyboard · 110 行)
├── modules/today/today-view.js         (greeting / renderFrequent / renderTodayWorkbench · 250 行)
├── modules/projects/projects-view.js   (CRUD / search / filter / render · 300 行)
├── modules/projects/work-detail.js     (_workReadiness / _workKind / runWorkAction · 280 行)
├── modules/projects/drawer.js          (openProjectDrawer / saveHandoff / insertHandoffToChat · 200 行)
├── modules/skills-view.js              (renderSkills 加試用 · 80 行)
└── modules/palette-items.js            (_paletteItems · VIEWS × AGENTS × PROJECTS × SKILLS · 80 行)
```

依賴圖:
```
app.js (entry)
 └─ app-init
      ├─ router           ← 所有 view 切換
      ├─ keyboard         ← call router
      ├─ today-view       ← Projects + chat
      ├─ projects-view    ← Projects + modal + toast
      │    └─ work-detail ← Projects + chat + runWorkAction
      ├─ projects/drawer  ← Projects + authFetch + chat
      ├─ skills-view      ← config.SKILLS + chat
      └─ palette-items    ← config + Projects(pure data)
```

拆分順序(6 天):Day1 palette-items + keyboard · Day2 router + skills-view · Day3 today · Day4 work-detail + drawer · Day5 projects-view · Day6 app-init。

### C · demo-to-production migration plan(3 phase)

**Phase 1 · 抽元件(1 週)**:demo 已成熟正式版缺的 3 個

| Demo 元件 | 搬到 | 共用方式 |
|---|---|---|
| `process-list`(4 步狀態) | `view-workflows` | 抽 `modules/ui/process-list.js` |
| `classification-card` | `today-workbench` 的 today-card | 抽 `modules/ui/task-classifier-card.js` |
| `artifact-toolbar`(4 tab) | `view-projects` drawer handoff | 抽 `modules/ui/artifact-tabs.js` |

**Phase 2 · token 對齊(1 週)**:demo 遷就正式版

| Demo token | 正式版 | 動作 |
|---|---|---|
| `--bg / --bg-2` | `--bg-base` | demo 用 `var(--bg-base, #081522)` |
| `--panel` | `--bg-float` | alias |
| `--ink` | `--text-primary` | alias |
| `--teal` | `--blue` 或新 `--accent-cyan` | 討論 |
| `--radius-xl/lg/md` | `--r-2xl/xl/lg` | 重命名對齊 |

**Phase 3 · 互動 pattern(2-3 週)**:

| Demo 互動 | 採納 | 搬到 |
|---|---|---|
| intake-form | ✅ | 取代 today-composer |
| process-list | ✅ | Workflows view 主體 |
| artifact-toolbar | ✅ | Projects detail tab bar |
| source-card | ✅ | Projects 右欄「素材」升級 |
| module-card | ✅ | Today「工作區起手式」升級 |
| confidence-meter | ✅ | 既有 ring 升級視覺 |
| mode-switcher | ❌ | 不採納(多一層) |

保留 `/ui-demo` route 當對照參考 · v1.5 後移除。

### C · 測試補強計畫

現有(2026-04-25):後端 246 pass / E2E 13 case / smoke 10 / **前端 JS unit test 0** / **visual regression 0** / **a11y smoke 0**

缺的 user journey(對照 brief §6.3):

| Timeline 步驟 | 有 E2E? | 建議補 |
|---|---|---|
| 09:30 建工作包 | 部分 | `project-create.spec.ts` |
| 10:00 上傳附件 + 來源 UI | 部分 | `knowledge-browse.spec.ts` |
| 11:30 Go/No-Go 判斷 | 無 | `tender-go-no-go.spec.ts` |
| 14:00 設計師接手看摘要 | 無 | `project-handoff.spec.ts` |
| 16:30 AI 草稿回寫 handoff | 無 | `chat-save-to-handoff.spec.ts` |
| 建立同仁帳號(admin) | 無 | `admin-user-mgmt.spec.ts` |
| Workflow draft-first | 無 | `workflow-draft.spec.ts` |
| 手機場勘 PWA | 極少 | `mobile-site-survey.spec.ts` |

補:
- **Visual regression**:Playwright `toHaveScreenshot` + 4 viewport × 5 view · 存 `tests/e2e/screenshots/` baseline
- **a11y smoke**:`@axe-core/playwright` · 6 頁各掃 1 次 · violations=[]
- **Mobile E2E matrix**:iPhone 13 / SE / iPad Mini / Pixel 7 · 每 device 跑 critical-journeys

### C · Roadmap

**1-3 天**:拆 palette-items + keyboard(-180 行)/ 更新 README / 加 vitest frontend unit / `project-create.spec.ts` / token alias / `/balance` envelope
**1 週**:拆 router / today-view / work-detail / 37 onclick delegation / a11y smoke spec / visual regression baseline
**2-3 週**:Phase 1 抽 3 元件 / Phase 2 token 對齊 / Phase 3 Today composer 三欄 + artifact tabs + confidence meter / CSS 分檔 + HTTP/2 / esbuild cutover 前置 / Mobile E2E matrix

---

## Meta-Audit · 審計的審計

3 個 agent 都讀同一份 brief · 容易有相同盲點。Meta-reviewer 獨立跑 · 專找 meta 問題。

### 集體盲點 · 7 個

#### 🔴 盲點 1 · 「3 秒理解」本身就是錯的量尺

3 AI 都接受 brief 的第一問「3 秒內理解」· 往「更像 ChatGPT」拉。但承富是**內部工具**不是 landing page · 有 training + Champion + 強制全員用。**真正該問的是同仁用 2 週後、一天敲鍵盤 3 小時,哪裡最煩?** 不是第一次登入卡在哪。

#### 🔴 盲點 2 · 5 Workspace 是老闆已決議的心智模型

DECISIONS.md `D-005` 明文定 5 Workspace 是主要 IA · SYSTEM-DESIGN.md §2 有 100 行 rationale。3 AI 全推「砍」= **推翻老闆 3 個月前簽過的決策**。沒人問:「Workspace 落地失敗是 IA 錯 · 還是 execution 錯?」**修 execution 比換骨架便宜 10 倍**。

#### 🔴 盲點 3 · intake-form 大輸入框就是 ChatGPT 的另一個名字

brief 第一句說「不是聊天工具」· 3 AI 集體走向「讓首頁更像 ChatGPT」然後宣稱「比 ChatGPT 好」。這是**路徑依賴**。真正差異化應是**「你不用輸入 · 系統已知道你今天要幹嘛」**(因為知道工作包 / 行事曆 / 你是 PM)· 不是更優雅的大輸入框。

#### 🔴 盲點 4 · Agent 背景化 = 放棄技術差異化賣點

老闆花錢蓋的正是「10 Agent」· DECISIONS.md `D-001-v2` 明文「10 核心 Agent 是 production surface」。前端藏掉 Agent 意味:
1. 出錯時同仁不知道要回報哪個 Agent 改 prompt
2. 老闆看不到他買的 10 Agent
3. 後端仍有 10 個但前端藏 = **可見的技術資產變後台細節**

修正版:**把 Agent 改名「小編 / 投標顧問 / 會計師」**· 保留分派可見 · 只是別叫 Agent。

#### 🔴 盲點 5 · demo 4 元件搬進 = 4000 行 vanilla JS 重寫

沒人算實際工作量。app.js 1732 行 + launcher.css 882 行 + 28 module。若 v1.4 同時拆 + 改角色首頁 + 搬 4 demo 元件 + chat 綁 project + handoff 預填 + intake-form = **8-12 週工作**。3 AI 暗示 v1.4 一輪可做完 · 實際 v1.4 容得下 2 項最多。

#### 🔴 盲點 6 · 沒人檢查 LibreChat 升級路徑

DECISIONS.md `D-007` pin v0.8.4。LibreChat v0.9 已在路上。前端大改「Workspace / Agent / 工作包」· 改 librechat-relabel.js 的 sub_filter 規則後 · v0.9 升級時規則可能整批失效。**前端改越多 · 升級成本越高**。

#### 🔴 盲點 7 · 10 人公司 KPI 不是 UX · 是老闆覺得 NT$ 12,000 花得值

3 AI 全從 UX 切入。但承富真正成敗判準:
1. 老闆 admin dashboard 能不能 show「本月省 X 小時 / 產 Y 報告 / 降 Z 次外包」?
2. 承富提案給客戶時能不能說「我們有內部 AI」?
3. NT$ 12,000/月 vs 10 人 ChatGPT Plus NT$ 6,800 差額值不值得?

B 提 22 條文案 / C 提 37 處 onclick · **改不了任何一項老闆 KPI**。admin dashboard polish 反而該是第一順位。

### 表面共識但實際錯誤 · 3 個

#### ❌ 錯誤 1 · sidebar 砍到 3-4 項違背 progressive disclosure

老闆管同仁 / 看會計 / 調 agent · 同仁看工作包 / 資料庫 / 會議 · PM 跟 CRM / 標案。sidebar 3 項 = admin 多 2 click。3 AI 一刀切沒分「日常 vs 後台」。

**正解**:主 sidebar 給同仁 4 項 · admin 專用 sidebar 另一組(如 Notion Settings)· 不是全砍 3 項。

#### ❌ 錯誤 2 · Agent 完全降級讓 feedback 失去著力點

同仁問「上次新聞稿語氣有點硬」· 前端看不到 Agent 要怎麼告訴 Champion 改哪個 prompt?目前 feedback 靠 `agent_id` 到月報 · 這正是 D-009 Level 4 Learning 基礎。藏 Agent → feedback 匿名化 → Level 4 廢。

**正解**:前端不叫 Agent · 但保留「這次回答由公關小編生成」metadata。

#### ❌ 錯誤 3 · 工作包主心智對一次性任務過度設計

「幫我翻譯一句英文」「這段文字哪裡不通順」被迫先開工作包 · 同仁會回 ChatGPT。

**正解**:默認不建工作包 · 對話 3 輪 / 有附件 / 觸發關鍵詞(標案 / 提案 / 活動)才**自動提示**「要存成工作包嗎?」· 不主動推。

### 互相矛盾 · 3 對

#### ⚡ 矛盾 1 · 角色化首頁(A)vs 統一 intake-form(B)vs 單一 router(C)

老闆看 intake-form 會罵「我要看儀表板」· PM 看儀表板會罵「我要輸入框」· router 走 A 分岔代碼比現在複雜 2 倍 · 跟 C 精簡目標打架。

**解法**:角色化優先 · 但老闆儀表板 / PM 收件箱 / 設計師素材 各自專屬 · intake-form 只在「+ 新任務」按鈕 · 不當首頁 hero。

#### ⚡ 矛盾 2 · demo 是終點還是過度?

B 說「4 元件搬進」· C 說「token 不對齊要 alias 層」· A 說「demo 是好方向」。衝突:搬進要 migrate token · alias 層在 migrate 期間 3 套並存維護 6 個月以上。**這不是 v1.4 能做完的**。

**解法**:要嘛 demo 當實驗場、正式版獨立演化 · 要嘛承認是 3-6 個月工程。

#### ⚡ 矛盾 3 · 拆 app.js vs 大改 UX · 誰先

並行 = **git conflict 地獄**。拆 module 的 PR 改結構 · UX PR 改行為 · 兩者都動 app.js · merge 一個另一個半天 rebase。

**解法**:**v1.4 只做拆 app.js(enabler only)**· v1.5 再 UX 大改。或反之。**同時做一定延誤**。

### v1.4 並行衝突地圖

| 併發項 A | 併發項 B | 衝突點 |
|---|---|---|
| 拆 app.js | chat 綁 project_id | 兩 PR 都動 chat.js / project.js |
| 交棒卡 AI 預填 | Agent 背景化 | 預填要看 Agent 名字 vs 藏掉 · 自相矛盾 |
| intake-form 首頁 | 角色化首頁 | 登入第一眼是哪個? |
| sidebar 砍 3 項 | 會計/CRM/社群入口 | 砍了去哪找? |
| 22 條文案替換 | chengfu_permissions 等技術詞保留 | admin 和同仁兩套詞彙? |
| 「今天要做什麼」首頁 | 工作包主心智 | 任務列表 vs 工作包列表 |

**結論**:6 項共識 MVP 並行 · **至少 3 對衝突**。實際可並行 ≤ 2。

### 對 6 件 MVP 的最終判決

| # | 共識項 | 判定 | 理由 | 建議 |
|---|---|---|---|---|
| 1 | Sidebar 砍到 3-4 項 | **採納但分階段** | 一次砍太激進 | v1.4 砍到 8 項 · v1.5 再評估 4 項 |
| 2 | 首頁改 intake-form | **拒絕當 default** | 違背「不是聊天工具」| 進 `+ 新任務` modal · 不當首頁 hero |
| 3 | chat 綁 project_id + 自動存 | **✅ 採納(優先)** | 真正承富 > ChatGPT | 對話 3 輪才提示存(避免過度設計) |
| 4 | 交棒卡 AI 預填 + 一鍵複製 | **✅ 採納** | Phase C 已有基礎 · 低成本高感知 | 預設展開限 7 天內 · 老的收起 |
| 5 | Agent / Workspace 從前台消失 | **修正採納** | 完全消失傷 feedback 分類 + 放棄賣點 | Agent 改名「小編 / 投標顧問」保留可見 · Workspace 保留 5 個換視覺 · Skill 只 admin 見 |
| 6 | app.js 拆分 | **✅ 採納(獨立 PR)** | 不與 UX 並行(矛盾 3) | v1.4 只做拆 + esbuild cutover · UX 改 v1.5 |

### Meta-Reviewer 最終推薦 · Scenario C

**v1.4 只做 3 件(4 週)**:

1. **拆 app.js 7 module + esbuild cutover**(1 週)
   - 不改 UX · 純技術債清理 · 全站載入 +30%
2. **chat 綁 project_id + AI 回覆一鍵存工作包 + 交棒卡 AI 預填 + 一鍵複製 LINE/Email**(2 週)
   - 真正承富 > ChatGPT 的差異化
3. **Agent 改名角色稱(小編 / 投標顧問 / 會計師)+ 儀表板 polish**(1 週)
   - 保留可見 · 儀表板給老闆 ROI narrative

**不做**:
- ❌ 不動 sidebar
- ❌ 不動 5 Workspace
- ❌ 不引進 intake-form
- ❌ 不全改 22 文案(只改「主管家 / 智慧引擎」一兩處)

---

## 總結:採納決策框架

### 4 份審計輸出共 65 findings · 如何取捨?

```
┌──────────────────────────────────────────────────────────────┐
│  決策原則                                                     │
│                                                               │
│  優先 1: 改後不會被老闆推翻的(D-005 D-007 D-009)            │
│  優先 2: 改了老闆儀表板會更好看的(admin dashboard polish)   │
│  優先 3: 4 週內能做完 · 且能 ship 的(工作包差異化 + 拆 js) │
│                                                               │
│  延後: 需要更多 UX research 才能決定的(intake-form / IA 大改)│
│  拒絕: 違背老闆決議 / 放棄差異化 / 過度 ChatGPT 化的         │
└──────────────────────────────────────────────────────────────┘
```

### 接下來 Sterio 要做的決策

1. **確認 v1.4 範圍**:是 Scenario C 的 3 件(Meta 推薦)· 還是共識 6 件(A+B+C 推薦)?
2. **確認 5 Workspace 存廢**:修 execution 還是推翻 D-005?
3. **確認 Agent 可見性**:角色化保留 vs 完全背景化?
4. **確認 demo 策略**:v1.5 基礎 vs 實驗場保留 · 不搬進?

建議:把這 4 個決策寫進 `docs/DECISIONS.md` 待決議區 · 等 Sterio 答完再啟動 v1.4 sprint。

---

## 附:相關檔案(絕對路徑)

### 審計文件
- `/Users/sterio/Workspace/ChengFu/docs/AI-AUDIT-BRIEF-FORMAL-2026-04-25.md` — 委託 brief
- `/Users/sterio/Workspace/ChengFu/docs/AI-AUDIT-FINDINGS-2026-04-25.md` — 本文件
- `/Users/sterio/Workspace/ChengFu/AI-HANDOFF.md` — 系統全貌
- `/Users/sterio/Workspace/ChengFu/docs/DECISIONS.md` — 歷史決議
- `/Users/sterio/Workspace/ChengFu/docs/ROADMAP-vNext.md` — 下一版計畫
- `/Users/sterio/Workspace/ChengFu/SYSTEM-DESIGN.md` — 設計語言

### 前端(審計標的)
- `/Users/sterio/Workspace/ChengFu/frontend/launcher/index.html`
- `/Users/sterio/Workspace/ChengFu/frontend/launcher/launcher.css`
- `/Users/sterio/Workspace/ChengFu/frontend/launcher/app.js`(1732 行)
- `/Users/sterio/Workspace/ChengFu/frontend/launcher/modules/README.md`
- `/Users/sterio/Workspace/ChengFu/frontend/launcher/ui-vnext-demo.html/css/js`

### 後端(審計標的)
- `/Users/sterio/Workspace/ChengFu/backend/accounting/main.py`
- `/Users/sterio/Workspace/ChengFu/backend/accounting/routers/*.py`
- `/Users/sterio/Workspace/ChengFu/tests/e2e/critical-journeys.spec.ts`

---

*文件產生 2026-04-25 · 4 個 AI agent 並行審計 + meta-review · 合計 65 findings · 繁體中文輸出*

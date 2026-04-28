# UI/UX Multi-Agent Audit · 2026-04-25

> 範圍:UI/UX 最高優先,並涵蓋產品策略、功能取捨、前端架構、測試與交付落地。  
> 明確排除:安全性、隱私、密鑰、權限繞過、攻擊面分析。  
> 方法:依 `docs/AI-AUDIT-BRIEF-FORMAL-2026-04-25.md` 拆成產品策略、UI/UX、架構維護三線只讀審計後合併。

---

## 1. Executive Summary

公司 AI 已經具備「比 ChatGPT / Claude 網頁版更貼近公司工作流」的基礎,但正式版目前仍卡在「AI 工作台 + 功能後台 + Agent 入口」的混合狀態。它不是不能交付,而是 **有條件可交付**:必須在 v1.4 前把首頁與主流程收斂為「輸入任務 → 建立工作包 → 產出交付草稿 → 保存來源與下一步 → 交棒」。

三條審計線的共識:

| 視角 | 核心判斷 |
|---|---|
| 產品策略 | 產品定位應從「內部版 ChatGPT / Agent 集合」改成「公司 AI 工作包系統」。 |
| UI/UX | 正式版功能完整但像功能後台;`/ui-demo` 方向正確但仍資訊密度過高。 |
| 架構維護 | 不需要換 React/Next/Tailwind;現有 vanilla ES modules 可支撐,但要抽出 `task-intake`、`work-detail`、`artifacts/sources` 等產品層模組。 |

交付狀態: **有條件可交付**。

最重要的 3 個修正:

1. 第一層 IA 收斂為「今日 / 工作包 / 公司資料 / 工具箱」。
2. 首頁主路徑改為「今天要完成什麼?」任務輸入,不再要求先選 Workspace / Agent / 模型。
3. 工作包升級成主心智模型,承載任務、附件、來源、交付品、下一步與交棒。

---

## 2. Consolidated Findings

| ID | 嚴重度 | 面向 | 位置 / 證據 | 問題 | 影響 | 建議修正 |
|---|---|---|---|---|---|---|
| F-01 | P0 | IA | `frontend/launcher/index.html:28`, `:104`, `:207` | 側欄同時有主區、流程模板、次層功能、快速工具。 | 使用者 3 秒內不知道從哪開始。 | 常駐側欄縮成「今日、工作包、公司資料、工具箱」。 |
| F-02 | P0 | 產品定位 | `frontend/launcher/index.html:238` | 正式版仍讓一般使用者看到智慧引擎、主力、備援。 | 使用者被迫思考模型/供應商。 | 前台只顯示「快速 / 深入」或完全隱藏到進階設定。 |
| F-03 | P0 | 首頁主路徑 | `frontend/launcher/index.html:290` | 首頁任務 CTA 是「交給主管家」。 | 非 AI 熟手不知道主管家是誰、會做什麼。 | 改成「建立工作草稿」,副文說明 AI 會自動整理。 |
| F-04 | P0 | 工作閉環 | `frontend/launcher/app.js:1131` | 任務輸入後仍開 chat pane,沒有直接形成來源、交付品、工作包。 | 使用者仍回到 ChatGPT 式複製整理。 | 提交後進「任務草稿」頁:摘要、缺件、分工、交付預覽、存工作包。 |
| F-05 | P0 | 工作包心智 | `frontend/launcher/index.html:367`, `frontend/launcher/app.js:946` | 工作包有強功能,但不是第一心智模型。 | 跨日、跨人接續價值不夠明顯。 | 首頁任務建立後自動建立或接續工作包。 |
| F-06 | P0 | Demo 落地 | `frontend/launcher/ui-vnext-demo.js:132`, `:177` | `/ui-demo` 是孤立原型,互動仍是前端模擬。 | 無法證明可交付,也會與正式版漂移。 | 抽 `task-intake` module,讓 demo 與正式首頁共用資料流程。 |
| F-07 | P1 | Demo 資訊密度 | `frontend/launcher/ui-vnext-demo.html:34` | 三欄同屏資訊量仍偏高。 | 小白會看到很多卡片,不知道先看哪裡。 | 首屏保留輸入、處理狀態、第一個交付預覽;來源與分派進抽屜。 |
| F-08 | P1 | 模式切換 | `frontend/launcher/ui-vnext-demo.html:21` | mode switcher 像產品導覽,不是自然流程。 | 使用者以為要手動切模式。 | 改成處理 stepper:收件、處理、交付、保存。 |
| F-09 | P1 | 輸出關係 | `frontend/launcher/ui-vnext-demo.html:163` | 「可輸出內容」與「交付預覽」關係不夠直覺。 | 使用者不知道點按後會更新哪裡。 | 按鈕改成動詞:「產生缺件清單」「產生客戶信」。 |
| F-10 | P1 | Mobile IA | `frontend/launcher/modules/mobile.js:9` | 手機底部導覽用 Workspace 名稱,但實際連到不同 view。 | 手機心智模型不一致。 | 底部改成「今日、工作包、拍照/附件、公司資料、我的」。 |
| F-11 | P1 | Mobile layout | `frontend/launcher/ui-vnext-demo.css:862` | demo 手機版主要是三欄變單欄堆疊。 | 手機流程很長,像表單清單。 | 改成 step flow:收件 → 附件 → 處理中 → 交付 → 存工作包。 |
| F-12 | P1 | 次要功能 | `frontend/launcher/index.html:104` | 會計、CRM、場勘、社群、教學等同層出現。 | 正式版像營運後台,削弱每日 AI 工作台定位。 | 收進「工具箱」,依角色只露 3 個常用入口。 |
| F-13 | P1 | 差異化內容 | `frontend/launcher/app.js:946` | AI 判斷、可交接度、缺口雷達藏在工作包細節。 | 最有價值的「比 GPT 好用」證據不在首屏。 | 搬到任務草稿頁與工作包首頁。 |
| F-14 | P1 | 資料模型 | `backend/accounting/routers/projects.py:44`, `:56`, `:303` | Project/Handoff 缺少一級 `Task / Source / Artifact` 模型。 | UI 難穩定呈現來源、交付物、下一棒。 | 在現有 Project/Handoff 上補 `task_items`、`source_refs`、`artifacts`。 |
| F-15 | P1 | 前端架構 | `frontend/launcher/app.js:82`, `:883`, `frontend/launcher/modules/chat.js:285` | `app.js` 與 `chat.js` 承擔過多 orchestration。 | UI、工作包、chat saveback 容易互相牽動。 | 拆 router、task-intake、work-detail、chat runtime、handoff-save。 |
| F-16 | P1 | Workflow 文案 | `frontend/launcher/modules/workflows.js:99`, `backend/accounting/orchestrator.py:351` | Workflow UI 仍暴露技術語彙。 | 使用者覺得像工程工具。 | 改成「會產出什麼、需要你補什麼、下一步誰接」。 |
| F-17 | P1 | E2E 覆蓋 | `tests/e2e/critical-journeys.spec.ts:48` | E2E 測頁面存在,但不足以證明「任務到交付」可用。 | UI 重構可能破壞核心體驗而測不到。 | 加「輸入任務 → 建工作包 → 開 chat → 儲存回 handoff」E2E。 |
| F-18 | P2 | 文案 | `frontend/launcher/launcher.css:606` | 正式版首頁文案偏抽象。 | 第一次使用者不容易理解。 | 改成「今天要完成什麼?」並附 3 個真實例子。 |
| F-19 | P2 | CSS 系統 | `frontend/launcher/launcher.css:6`, `frontend/launcher/ui-vnext-demo.css:1` | 正式版與 demo tokens 分裂。 | 視覺方向會漂移。 | 抽 `tokens.css`、`shell.css`、`components.css`、`views/*.css`。 |
| F-20 | P2 | Build hygiene | `frontend/launcher/build.config.js:1`, `frontend/launcher/index.html:1053` | esbuild 已準備,但 production 仍載入 source modules。 | release hygiene 與效能尚未收斂。 | v1.4 切 manifest-based bundle,hashed assets 才長效快取。 |
| F-21 | P2 | 文件 | `frontend/launcher/modules/README.md:15`, `:44` | 模組 README 落後實際狀態。 | 新工程師會依錯誤拆分地圖工作。 | 更新現況模組圖、v1.4 拆分順序、bundle cutover 規則。 |

---

## 3. Recommended IA

### 3.1 新產品定位

公司 AI 不應定位成「內部版 ChatGPT」或「10 個 Agent 集合」,而應定位成:

> **公司 AI 工作包系統**:同仁把任務、附件、會議、標案或客戶需求丟進來,系統自動整理成可交付草稿,並保存到工作包讓下一位同事接續。

### 3.2 新第一層 IA

| 導覽 | 用途 | 備註 |
|---|---|---|
| 今日 | 任務輸入、最近下一步、待交付工作 | 首頁主入口 |
| 工作包 | 每件事的資料、進度、交付品與交棒 | 主心智模型 |
| 公司資料 | 知識庫、引用來源、最近附件 | 不叫「資料庫」 |
| 工具箱 | 會議、場勘、CRM、社群、會計、標案監測、教學 | 次要功能收納 |
| 我的 | 個人設定、AI 模式、通知、帳號 | 模型/引擎放進這裡或進階 |

5 Workspace 保留,但改成「常用流程 / 流程模板」,在任務建立後由系統建議,不再常駐壓在第一層。

### 3.3 新首頁 Wireframe

```text
Top bar:
公司 AI 工作台 | 搜尋工作包 / 公司資料 / 功能 | 今日 | 工作包 | 公司資料 | 工具箱 | 我的

Main:
今天要完成什麼？
[ 大輸入框: 貼上客戶需求、招標文字、會議摘要,或直接描述任務 ]
[ 加入附件 ] [ 建立工作草稿 ]

快速起手:
[ 客戶來信 → 提案大綱 ]
[ 招標 PDF → Go / No-Go ]
[ 會議紀錄 → 客戶信 + 分工 ]

AI 正在整理:
1 讀取需求
2 檢查附件與公司資料
3 判斷任務類型
4 產生交付草稿

交付預覽:
摘要 | 缺件 | 分工 | 客戶信 | 設計 Brief
[ 可編輯預覽區 ]

右側抽屜:
本次使用資料
建議分派
待確認問題
存到哪個工作包
[ 存成工作包 ] [ 交給下一位同事 ]
```

### 3.4 手機版流程

1. 首頁只問「今天要完成什麼?」,下方一個輸入框、一個「加入附件」、一個固定底部 CTA「建立草稿」。
2. 送出後進入「處理中」頁,用 4 個步驟顯示目前做到哪。
3. 草稿完成後先顯示「摘要 + 3 個下一步」。
4. 使用者左右切換「缺件、分工、交付、交棒」。
5. 來源資料收在底部抽屜「本次參考資料」。
6. 最後只給兩個選擇:「存成工作包」或「複製/輸出交付品」。

---

## 4. Demo-To-Production Plan

### 4.1 核心資料 contract

新增或明確化 `TaskDraft`:

```json
{
  "input_text": "使用者輸入",
  "files": [],
  "suggested_workspace": "bid|event|design|pr|ops",
  "source_refs": [],
  "artifact_drafts": [],
  "project_id": "optional",
  "status": "draft|processing|ready|saved"
}
```

在 Project/Handoff 上補:

| 欄位 | 用途 |
|---|---|
| `task_items` | 本工作包內的任務與狀態 |
| `source_refs` | 本次 AI 使用的附件、知識庫與規則 |
| `artifacts` | 摘要、缺件、分工、客戶信、提案大綱等交付草稿 |

### 4.2 前端模組拆分

| 區域 | 建議檔案 | 目的 |
|---|---|---|
| App shell | `modules/app-core.js`, `modules/router.js`, `modules/view-registry.js` | 把 init、hash routing、view lifecycle 從 `app.js` 分離 |
| 今日工作台 | `modules/task-intake.js`, `modules/today-workbench.js`, `modules/work-suggestions.js` | 將 `/ui-demo` 的任務輸入心智正式化 |
| 工作包 | `modules/work-detail.js`, `modules/project-drawer.js`, `modules/handoff-editor.js` | 工作包 detail、handoff、下一步可獨立測試 |
| Chat | `modules/chat/runtime.js`, `modules/chat/stream.js`, `modules/chat/attachments.js`, `modules/chat/markdown.js`, `modules/chat/handoff-save.js`, `modules/chat/history.js` | 降低 `chat.js` 變更風險 |
| 交付物 | `modules/artifacts.js`, `modules/sources.js`, `modules/workflow-drafts.js` | 建立「資料來源 → 交付物 → 保存」產品層 |
| CSS | `styles/tokens.css`, `styles/shell.css`, `styles/components.css`, `styles/views/*.css` | 避免單一 CSS 持續膨脹 |

### 4.3 合併 `/ui-demo` 的順序

1. 抽 `task-intake.js`,先只接正式首頁輸入框與附件按鈕。
2. 將 demo 的 fake save 改接 `Projects.add` 與 `/projects/{id}/handoff/append`。
3. 將 demo 的來源卡抽成 `sources.js`,先顯示文字任務、附件名稱、公司規則。
4. 將 demo 的交付預覽抽成 `artifacts.js`,支援摘要、缺件、分工、交棒四類。
5. 將 Workspace 改成「常用流程推薦」,不再是開 Agent 的唯一入口。
6. `/ui-demo` 退為 showcase 或使用同一模組的 demo mode,避免兩套 UI 漂移。

---

## 5. Roadmap

| 時間 | 目標 | 動作 | 驗收 |
|---|---|---|---|
| 1-3 天 | 立即降低複雜度 | 側欄常駐入口縮到 4 個;首頁文案改成「今天要完成什麼?」;模型/Agent/引擎移到進階 | 新使用者 3 秒內知道可輸入任務 |
| 1-3 天 | 建立最小 task intake | 新增 `task-intake.js`;首頁輸入可建立工作草稿;「存成工作包」寫入 Projects/Handoff | 任務輸入後可在工作包看到摘要與下一步 |
| 1 週 | 做出 v1.4 最小閉環 | 任務輸入支援附件;AI 回覆固定提供「存回工作包 / 列下一步」;工作包 detail 以摘要、來源、交付、下一棒為主 | 完成 3 條流程 dry-run:標案、會議、活動 |
| 1 週 | 架構減風險 | 拆 `app.js` routing / task intake;拆 `chat.js` handoff-save;更新 modules README | 新模組有清楚 owner 與測試入口 |
| 2-3 週 | demo 精神併回正式版 | 導入任務判斷、來源完整度、交付預覽;新增 Task/Source/Artifact contract | `/ui-demo` 可退成 showcase,正式版可承接核心流程 |
| 2-3 週 | 測試補強 | 新增核心 E2E、mobile step flow、visual regression、API contract tests | CI 覆蓋「任務到交付」而不只頁面存在 |
| 1-2 個月 | 工作 OS 化 | 工作包版本歷史、老闆 ROI、Workflow 採用率、交付品管理 | 老闆能看 ROI,PM 能跨日接續,同仁能接棒 |

---

## 6. Acceptance Criteria

### 6.1 UI/UX 成功標準

| 指標 | 成功條件 |
|---|---|
| 3 秒理解 | 首屏只有一個主問題:「今天要完成什麼?」 |
| 首次任務 | 新使用者不需要選 Agent / Workspace / 模型即可建立草稿 |
| 工作閉環 | 任務輸入後可看到摘要、來源、缺件、分工、交付預覽 |
| 保存與交棒 | 任何 AI 產出都能一鍵存回工作包或列下一步 |
| 手機體驗 | 手機走 step flow,不是桌機三欄垂直堆疊 |
| 文案 | 不出現口號式文案;術語以任務、資料、交付、工作包為主 |

### 6.2 測試補強

| 層級 | 測試 |
|---|---|
| Playwright E2E | 輸入任務 → 建工作包 → 開 chat → 儲存回 handoff → 回工作包看到成果 |
| Playwright E2E | 標案任務 → 資料來源列表 → Go/No-Go 交付物 → 下一步 |
| Playwright E2E | 會議紀錄 → 客戶 email 草稿 → 內部 next actions |
| Mobile E2E | task intake 在手機為 step flow |
| API contract | 固定 Project、Task、Source、Artifact、Handoff response shape |
| Visual regression | Dashboard、task intake、work detail、chat saveback、mobile drawer |
| Performance | 設 JS bytes、request count、first usable interaction 預算 |

---

## 7. Recommended Next Implementation Slice

最建議下一步不是繼續改 `/ui-demo`,而是做 **v1.4 Slice 1 · 今日任務收件箱**:

1. 收斂正式側欄。
2. 首頁改成「今天要完成什麼?」。
3. 新增 `task-intake.js`。
4. 輸入任務後建立或接續工作包。
5. 先產出 4 類 artifact placeholder:摘要、缺件、分工、交棒。
6. Chat 回覆固定提供「存回工作包 / 列下一步」。
7. 新增 2 條 E2E:任務到工作包、會議到交棒。

這一片完成後,公司 AI 才會真正開始脫離「功能後台」,進入「可替代一般 AI 網頁版的公司工作台」。


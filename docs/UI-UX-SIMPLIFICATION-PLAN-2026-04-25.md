# UI/UX 極簡重構計劃 · 2026-04-25

## 背景

使用者回饋:現在前端太複雜、看不懂,且對話區無法插入附件。這代表目前 Launcher 已偏離「替代正常 AI 使用」的核心:使用者應該先把工作交給 AI,而不是先理解系統模組。

本輪先修正附件入口,再把 UI/UX 重新規劃成「一個工作台 + 少數清楚入口 + 進階功能漸進展開」。

## 參考來源與新增技能方向

- OpenAI curated `frontend-skill`:產品 UI 應以狀態、任務、動作為主,每個區塊只負責一件事,文案能刪 30% 就繼續刪。
  來源:https://github.com/openai/skills/blob/main/skills/.curated/frontend-skill/SKILL.md
- Anthropic `frontend-design`:介面要有明確視覺方向,但產品面要把創意服務於任務完成,不是堆裝飾。
  來源:https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md
- Microsoft `frontend-design-review`:用「少點擊、清楚狀態、可信錯誤」檢查 UI,每個畫面最多 1-2 個主動作。
  來源:https://github.com/microsoft/skills/blob/main/.github/skills/frontend-design-review/SKILL.md
- Accessibility file upload guidance:檔案上傳要有清楚 label / 限制說明 / 錯誤提示,拖曳不能是唯一方式。
  來源:https://design-system.agriculture.gov.au/components/file-upload/accessibility
- assistant-ui attachments guide:附件 UI 要有型別驗證、進度回饋與鍵盤可操作。
  來源:https://www.assistant-ui.com/docs/guides/attachments

本專案後續使用技能組合:
- `frontend-design`:定義視覺方向與極簡工作台。
- `ui-design-system`:收斂 token、元件與間距,避免每頁長不同樣子。
- `ux-researcher-designer`:用承富 10 人角色重畫 journey,不是按工程模組排 IA。
- `a11y-audit`:附件、modal、sidebar、快捷鍵都要鍵盤可用。
- `form-cro`:所有建立工作包 / 上傳 / 篩選表單都要減欄位與清楚錯誤。

## 新設計原則

1. 一進站只回答一個問題:「今天要把什麼工作往前推?」
2. 預設不展示模組清單,只展示「問 AI」「看工作包」「找資料」三件事。
3. 工作流程不再是獨立迷宮,而是工作包裡的「建議下一步」。
4. Agent 不讓使用者選,由主管家路由;專家只在進階模式看得到。
5. 附件是核心輸入能力,不可再做成 disabled 或半成品。
6. 管理、會計、CRM、社群、場勘等都放到「更多工具」,不是左側常駐壓迫使用者。
7. 所有錯誤訊息都要告訴使用者下一步,不顯示工程詞。

## 新資訊架構

### 第一層 · 永遠可見

- 今日工作台:一個大輸入框,支援文字、附件、拖放、語音。
- 工作包:目前所有專案與下一棒。
- 資料:知識庫搜尋與最近附件。
- 更多:進階工具抽屜。

### 第二層 · 更多工具

- 會議速記
- 場勘
- 媒體名單
- 社群排程
- 標案監測
- 會計
- 自動化流程
- 同仁 / 中控(admin only)

### 第三層 · 專家與設定

- 10 個 Agent
- 5 個 Workspace 模板
- AI 引擎切換
- 權限設定
- 系統健康

## 新核心畫面

### 1. 今日工作台

畫面只保留:
- 一個主輸入:「把檔案、想法或問題丟進來」
- 一個附件列:已選檔案、上傳狀態、移除
- 三個快速意圖:整理文件 / 建立工作包 / 找公司資料
- 最近 3 個下一棒

不顯示:
- Workspace 清單
- Agent 清單
- 大量數據卡
- 技能庫入口
- 會計 / CRM / 社群等次功能

### 2. 工作包

每個工作包只顯示:
- 目前狀態
- 下一步
- 負責人
- 最新 AI 草稿
- 素材/附件

進階內容改成抽屜:預算、CRM、風險、交棒紀錄、workflow adoption。

### 3. 對話區

對話區要像 ChatGPT 一樣直覺,但比 ChatGPT 更懂承富:
- 永遠可直接問
- 支援附件
- 回答後有兩個主動作:存回工作包 / 變成下一步
- 不要求先選 Agent
- L3 提醒只提醒,不阻擋

## 附件 UX 規格

必備:
- 迴紋針按鈕可鍵盤 focus 與 Enter/Space 啟動。
- 可拖放,但拖放不是唯一方式。
- 選檔後立即顯示 chip:檔名、狀態、移除。
- 送出前先上傳,失敗要保留附件並顯示原因。
- 支援 pdf/docx/pptx/xlsx/csv/txt/md/json/image。
- 單檔先限制 25MB,一次最多 6 檔。

短期已完成:
- Launcher chat 迴紋針不再 disabled。
- 使用 LibreChat 原生 `/api/files` 上傳 message attachment。
- `/api/agents/chat` 帶入 `files` 陣列。
- 補上格式/大小檢查、拖放、chip 狀態。
- API smoke 已確認 message attachment 可成功建立 `file_id`。
- E2E 已覆蓋「選檔 -> 顯示待送出 chip」。

待補:
- 上傳進度百分比。
- 圖片縮圖。
- 附件讀取失敗時的一鍵「改去完整對話上傳」。
- E2E 補齊「送出後 body.files 進入 `/api/agents/chat`」。

## 分階段落地

### Phase S1 · 立即止血

- 修附件不能用。
- 首頁文案砍半。
- 側邊欄只保留 3 個常用入口,其他折到「更多」。
- Workflow 頁改名為「建議下一步」,避免使用者以為要理解自動化。

### Phase S2 · 極簡主路徑

- 將 Dashboard 改為單一任務輸入。
- 工作包 detail 改成「下一步優先」。
- 對話回答統一加「存回工作包 / 列為下一步」。
- 專家、Workspace、Slash command 全部退到進階。

### Phase S3 · 功能重新歸位

- 會議速記、場勘、社群、CRM、會計改成工作包素材或工具,不再與主路徑平級。
- Admin only 項目只在管理者視角顯示。
- 每個工具都有一頁「我該怎麼用」空狀態。

### Phase S4 · 驗收

- 找 3 個 AI 小白同仁測:
  - 能否在 30 秒內丟檔案問 AI。
  - 能否在 60 秒內建立工作包。
  - 能否知道 AI 回答要存去哪。
- Playwright 覆蓋 desktop + mobile。
- 鍵盤測試:Tab 可到附件、送出、移除附件、更多工具。

## 成功標準

- 新使用者不看教學,30 秒內知道第一步。
- 常用任務 3 click 內完成。
- 首頁可見主入口不超過 4 個。
- 左側常駐 nav 不超過 4 個。
- 所有進階功能都可用,但不主動打擾。
- 附件上傳成功率與錯誤原因可觀測。

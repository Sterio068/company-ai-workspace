# GPT Replacement Experience Plan

> 目標:讓承富同仁覺得「承富 AI 比 GPT 網頁版更適合完成我的工作」。
> 範圍:使用者選定 1-7 + 9-16,暫不把資料分級作為主線,但既有安全邊界不得退步。

## 北極星

承富 AI 不是聊天框,而是承富的 AI 工作 OS。使用者不需要從空白 prompt 開始,也不需要每次重講公司背景、專案現況、承富語氣與交付格式。

## 成功指標

- 新同仁首次登入 30 秒內知道該點哪個 Workspace。
- 使用者從首頁到送出第一個有效任務不超過 2 click。
- 首頁核心入口可用 Tab / Enter / Space 操作,且焦點清楚可見。
- 每個主要任務都能產出「可直接修改」的工作成果,而不是泛泛建議。
- 至少 70% 的 AI 回答能被存回專案、workflow、handoff、月報或知識庫之一。
- 老闆能在 Dashboard 看見採用率、省時估算、熱門 workflow 與卡點。

## 已選面向

1. AI 工作台首頁。
2. 5 Workspace 任務流程化。
3. Chat 任務模式。
4. Project Memory / Handoff。
5. Workflow 產品化。
6. 可交付產出格式。
7. 知識庫 / Skills / Agent 品質。
9. 權限與協作。
10. 回饋與學習迴路。
11. 外部入口 / Chrome Extension。
12. Mobile / 場勘 PWA。
13. Admin / 老闆儀表板。
14. 部署與維運。
15. 測試 / CI / 品質保證。
16. 教育訓練與交付文件。

## 執行主線

### Track A · 比 GPT 更好開始

- Dashboard 改成 AI 工作 OS 首頁。
- 5 Workspace 顯示「貼什麼 / 產什麼 / 下一步」。
- 今日工作台顯示專案下一步、workflow 草稿、Workspace 起手式。
- 空狀態直接引導建立專案或貼需求。

### Track B · 比 GPT 更懂脈絡

- Chat 顯示目前任務、Workspace、關聯專案、已帶入背景。
- Project handoff 匯整人工欄位與系統欄位。
- Workflow draft / meeting / site survey / chat 草稿都能回寫 project。
- Knowledge / Skills / Agent prompt 持續對齊承富語氣與格式。

### Track C · 比 GPT 更適合團隊協作

- Project owner/admin 邊界維持為基本安全網。
- 專案卡新增「負責人 / 協作人 / 下一棒」概念。
- Handoff 明確區分人工欄位、會議欄位、場勘欄位、workflow 欄位。
- Admin 權限頁標示哪些權限已 enforcement、哪些仍 advisory。
- 未來可加 project sharing,但所有跨人接手都要有 audit。

### Track D · 比 GPT 更接近交付

- 每個 Workspace 定義固定交付格式。
- 回答旁提供「存到專案 / 做成交棒卡 / 產下一步 / 加入月報」。
- Workflow 增加採用、修改後採用、拒絕狀態。
- 月報統計採用率與常見卡點。

### Track E · 比 GPT 更容易進資料

- Chrome Extension 右鍵送內容到承富 AI 草稿。
- Mobile 場勘 PWA 支援照片、定位、錄音、推交棒卡。
- 未來延伸 Google Drive / Gmail / Calendar。

### Track F · 比 GPT 更能被公司營運

- 老闆儀表板顯示成本、採用率、省時、熱門 workflow。
- Champion SOP 和教育訓練讓非工程同仁會用。
- 部署維運 checklist、backup / restore、smoke tests 常態化。

## 第一刀

先做 Track A 的首頁與 Workspace 體感:

- 首頁新增 AI 工作 OS hero,直接講清楚「不是空白聊天框」。
- 今日工作台卡片加上「已帶入脈絡」與「可交付物」。
- Workspace 卡片呈現任務流程,不是只列 Agent。
- 點 Workspace 仍只帶入草稿,不自動送出。

## 暫緩

- 全自動 workflow execution:等採用率、audit、rollback 和 quota 成熟後再開。
- 深度權限協作模型:目前維持 owner/admin 與第一批 enforcement,不做複雜 sharing。
- 外部 Gmail / Calendar 寫入:先做草稿與人工確認。

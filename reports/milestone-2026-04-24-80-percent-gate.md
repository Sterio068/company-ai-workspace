# Milestone · 2026-04-24 · GPT Replacement 80% Gate

## 摘要

本輪把「比 GPT 網頁版更適合承富工作」從概念推進到可驗證的工作閉環。重點不是新增更多入口,而是讓使用者能從首頁、Workspace、Chat、Project、Workflow 之間形成接續:開始任務、產出答案、存回專案、交給下一棒、留下採用紀錄。

## 80% 完成度表

| # | 面向 | 完成度 | 已落地證據 | 下一個 90% 補強 |
|---|---:|---:|---|---|
| 1 | AI 工作台首頁 | 86% | 首頁已是 AI Work OS,有 Dashboard、今日工作台、專案/Workflow/Workspace 入口與 ⌘K | 接上真實 ROI、省時、卡點排行 |
| 2 | 5 Workspace 任務流程化 | 84% | Workspace 不再只是 Agent 列表,已能帶安全草稿與工作流程提示 | 每個 Workspace 補 3 個真實 dry-run 範例 |
| 3 | Chat 任務模式 | 82% | Chat 回答旁新增「存交棒」「列下一步」,可回寫 Project handoff | 讓 Chat 明確顯示目前 project/workspace/task context |
| 4 | Project Memory / Handoff | 84% | 新增 collaborator / next_owner,協作者可讀寫 handoff,Chat 可 append,刪除保留 owner/admin | Handoff drawer 加版本歷史與衝突提示 |
| 5 | Workflow 產品化 | 81% | Workflow draft-first 已可送主管家,採用/拒絕會寫入 `workflow_adoptions` | 加「修改後採用」UI 與月報統計卡 |
| 6 | 可交付產出格式 | 80% | Workspace 起手式與 workflow steps 已有預期交付物,答案可存成專案資產 | 對 10 Agent 建固定輸出模板驗收 |
| 7 | 知識庫 / Skills / Agent 品質 | 80% | Skill-Agent Matrix、公司語氣、知識庫文件已成 source-of-truth | 跑 10 Agent × 3 案例並紀錄品質分數 |
| 9 | 權限與協作 | 82% | project owner/collaborator/next_owner 邊界 enforced,協作者不能刪專案 | 權限矩陣補 E2E + admin UI 警示 |
| 10 | 回饋與學習迴路 | 82% | 👍/👎、workflow adoption、audit log 已可被月報/Level 4 使用 | 建月報採用率與 skill proposal pipeline |
| 11 | 外部入口 / Chrome Extension | 80% | Extension 內容只進草稿、不自動送出,manifest/host pattern 已修 | 真機安裝教學與右鍵送入 E2E |
| 12 | Mobile / 場勘 PWA | 80% | Site survey 與 PWA 權限 header 已打通,場勘可 push handoff | iPhone 真機拍照/錄音/定位驗收 |
| 13 | Admin / 老闆儀表板 | 83% | Admin 權限 catalog、使用者管理、audit/monthly report 路徑已成形 | 老闆版 ROI + adoption cards |
| 14 | 部署與維運 | 85% | Route A smoke 11/0,nginx/accounting healthz,Keychain/backup/runbook 文件完整 | backup restore drill + Cloudflare Access 驗收 |
| 15 | 測試 / CI / 品質保證 | 88% | 本輪 158 passed / 1 skipped,Launcher build pass,smoke 11/0 | 補 Browser Use E2E script 化 |
| 16 | 教育訓練與交付文件 | 83% | Handoff、Roadmap、使用者手冊、Milestone 報告已同步 | 轉成 Champion 30 分鐘演練腳本 |

## 本輪新增能力

- Chat 回答可以一鍵存回專案交棒卡,或列成下一步,形成 GPT 網頁版沒有的「答案 → 專案記憶」閉環。
- Project 新增協作者與下一棒負責人,專案列表與 drawer 可看到接手狀態。
- 後端權限補強為 owner / collaborators / next_owner 可協作,但刪除仍限 owner/admin。
- Workflow 採用、拒絕會寫入 `workflow_adoptions`,後續可接老闆月報與 Level 4 Learning。
- Modal async submit 會等待實際儲存結果,避免失敗時視窗關掉造成假成功。

## 驗證結果

- Backend targeted tests:9 passed。
- Backend full selected suite:`158 passed,1 skipped`。
- Frontend syntax:`node --check` pass。
- Frontend build:`npm run build` pass。
- Route A smoke:`11 pass / 0 fail`。
- Browser Use:localhost 首頁確認 Dashboard / Projects / Workflow / ⌘K 存在,專案 modal 有協作者與下一棒欄位,console error 0。

## 下一輪 90% 路線

- 先做「使用者看得見的信任感」:Chat context banner、Handoff 版本歷史、採用率卡片。
- 再做「老闆看得見 ROI」:workflow adoption、節省時間、熱門任務、卡點排行進 Dashboard。
- 最後做「交付前驗收」:10 Agent × 3 dry-run、Chrome Extension 真機、iPhone 場勘、backup restore drill。

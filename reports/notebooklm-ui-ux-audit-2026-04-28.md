# NotebookLM UI/UX 優化審計

日期:2026-04-28
範圍:NotebookLM 前端、專案筆記本策略、單檔/資料夾上傳流程、Agent 可用性。

## 審計結論

原版 NotebookLM 頁面一次露出主從架構、Source Pack、Enterprise 設定、API 狀態、歷史包與同步狀態,資訊正確但使用者第一眼不知道該做什麼。最佳化方向改為「一個主任務 + 兩個收合區」:

- 主任務:建立 NotebookLM 資料包。
- 直接上傳:單檔或整個專案資料夾,自動歸入專案筆記本。
- 收合區:最近資料包、管理員連線設定。

## 主要 Findings

| # | 問題 | 影響 | 修正 |
|---|---|---|---|
| F-01 | 技術詞過多(Source Pack / Enterprise / hash 同屏) | 新手不知道下一步 | 改成「選資料 → 預覽 → 建立資料包」三步 |
| F-02 | 設定表單佔據主要視線 | 一般使用者誤以為要先設定 API | 管理員設定改成收合區 |
| F-03 | 每次同步可能建立新 notebook | 專案資料分散 | 改為一個工作包一本 NotebookLM 筆記本 |
| F-04 | 無法直接上傳整個專案資料夾 | 仍要手動整理 | 加入資料夾選取與批次上傳 |
| F-05 | 單檔沒有自動歸屬 | 使用者要猜放哪裡 | 加入工作包選擇與自動比對 |
| F-06 | 資料等級造成心理阻力 | 功能被看成受限 | 改為標記,不阻擋建立或同步 |

## 已完成

- 移除底部 Dock 外框,保留 icon 本體與 active 狀態。
- NotebookLM 首屏重構為簡化 hero + 三步流程。
- 新增單檔 / 多檔 / 整個資料夾上傳入口。
- 新增「自動判斷工作包」與手動選工作包。
- 新增 `notebooklm_project_notebooks`:一個工作包對應一本 NotebookLM 筆記本。
- 新增 `notebooklm_file_uploads`:記錄每次檔案或資料夾上傳結果。
- Source Pack 同步時,若屬於工作包,自動歸入該工作包筆記本。
- 文件改為功能最大化語氣,資料等級只標記不阻擋。

## 驗證

- `pytest backend/accounting/test_main.py -q -k notebooklm`:5 passed
- `node --check frontend/launcher/modules/notebooklm.js`:passed
- `python3 -m py_compile backend/accounting/routers/notebooklm.py backend/accounting/services/notebooklm_client.py`:passed
- `python3 -m json.tool config-templates/actions/internal-services.json`:passed
- `python3 -m json.tool config-templates/actions/notebooklm-bridge.json`:passed

# docs/ROADMAP-vNext.md — Phase A-E 優化路線

> 本文件承接 v1.3.0 ship 後的開發線。
> 目標不是增加更多零散功能,而是把承富 AI 收斂成同仁每天能用、老闆看得到 ROI、IT 能維護的工作 OS。

---

## 北極星

承富同仁從任一入口進來,都能在 1-2 click 內完成一段真實工作:

- 找到正確 Workspace。
- 貼上資料或選擇範本。
- 產出可交付草稿。
- 按 👍/👎 或補一句原因。
- 結果回到專案、知識、月報或 workflow。

---

## Phase A · 決策與文件基準

**狀態 · 2026-04-24**:已完成第一輪同步。

**目標**:讓所有 AI / 人類接手者讀到同一個現況。

- `docs/DECISIONS.md` 改為 vNext 最高事實來源。
- `AI-HANDOFF.md` 標記 v1.3.0 已 ship + vNext Phase A-E 進行中。
- 10 核心 Agent / legacy 29 Agent / Skills / Workflows 的角色分清楚。
- 舊 endpoint、舊 Agent 策略、舊 v2.0 placeholder 文件逐步修正。

**完成定義**:新接手者讀 `AI-HANDOFF.md` + `docs/DECISIONS.md` 不會誤以為 production 要平鋪 29 Agent。

---

## Phase B · Hardening 與驗收可信度

**狀態 · 2026-04-24**:已完成第一輪 hardening。

**目標**:先修掉會破壞信任的真問題。

- LibreChat v0.8 endpoint 一律對齊 `/api/agents/chat`。
- Site Survey 需要的 geolocation / microphone / camera 權限不被 nginx header 擋掉。
- Chrome Extension 帶入內容只進草稿,不自動送出。
- 串流回答結束後也顯示 👍/👎。
- Chrome Extension manifest 權限、host pattern、icon reference 可安裝。

**完成定義**:smoke、build、unit tests 都過；外部帶入內容不會未確認送雲端。

---

## Phase C · Workspace 工作閉環

**狀態 · 2026-04-24**:已完成 Workspace 草稿入口 + 今日工作台第一版;Chat 回答可存回 project handoff 或列成下一步。

**目標**:把首頁從「工具列表」升級成「每日工作台」。

- 每個 Workspace 點開即帶入一份安全草稿,提示同仁貼資料與選交付物。
- Dashboard 新增「今日工作台」,依最近未結案專案提示下一步、投標 workflow、活動起手式。
- Chat 回答旁提供「存交棒 / 列下一步」,把一次性回答轉成 project memory。
- 投標 Workspace 以「招標須知 → Go/No-Go → 建議書 → 報價 → 送件」為主線。
- 活動 Workspace 以「活動目標 → 場地/動線 → 視覺 → 預算 → 風險」為主線。
- 設計、公關、營運 Workspace 顯示下一步與常用輸入。

**完成定義**:AI 小白不用知道 Agent 名稱,從 Workspace 就能開始。

---

## Phase D · 管理、權限、回饋與學習

**狀態 · 2026-04-24**:細部權限第一批已從 advisory 推進到 backend enforcement;Project collaboration 已有 owner / collaborators / next_owner 邊界。

**目標**:讓老闆和 Champion 可以安全營運系統。

- User permissions 由「可勾選」升級為「可查、可 audit、逐步 enforce」。
- Admin catalog 回傳 enforcement 狀態,避免 UI 誤導。
- 停用帳號已被一般 user guard 與 admin guard 全域擋下。
- Project collaborators / next_owner 可協作 handoff,但刪除仍限 owner/admin。
- 已 enforce:accounting.view/edit、social.post_own、site.survey、knowledge.manage、media_crm.edit/export、admin dashboard/audit/PDPA。
- Feedback 不只存 👍/👎,也能被月報與 skill proposal 使用。
- 高風險功能先納入權限檢查:admin、knowledge manage、accounting edit、social publish、site survey。

**完成定義**:後台能回答「誰能做什麼」、「哪些權限目前真的 enforce」、「哪些 Agent 需要優化」。

---

## Phase E · 半自動 Workflow

**狀態 · 2026-04-24**:已完成 draft-first UI + project handoff workflow draft 寫入 + workflow adoption tracking。

**目標**:先交付可控的工作流,不急著全自動。

- 預設 workflow:投標完整閉環、活動完整企劃、新聞發布閉環。
- Workflow 先產生「步驟草稿 + 主管家 prompt」,由使用者確認後送出。
- 若帶入 project_id,workflow 草稿會寫入 `project.handoff.workflow_draft`,並留下 `audit_log`。
- 採用 / 拒絕 workflow draft 會寫入 `workflow_adoptions`,供月報與 Level 4 Learning 使用。
- 每個 step 標記使用 Agent、輸入、預期交付物、人工確認點。
- 未來才把 step 執行升級為後端多 Agent orchestration。

**完成定義**:使用者可從「自動化流程」產生完整工作流草稿,並帶到主管家手動確認執行。

---

## 下一輪建議

- 把今日工作台接上 due date / risk / usage metrics,讓老闆首頁直接看到 ROI 與卡點。
- 把 `workflow_adoptions` 接到 Admin 月報,顯示採用率、拒絕原因、熱門 workflow。
- 補 Chat context banner 與 handoff 版本歷史,讓跨日接續更可信。
- 把 `social.post_all` 從 catalog advisory 推進成真正 enforcement,支援主管 / admin 管理全公司貼文。
- 視覺驗收繼續用 Browser Use 擴到 workflow modal、mobile layout 與 a11y focus。

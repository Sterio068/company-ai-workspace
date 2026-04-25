# Milestone · 2026-04-24 · vNext Phase A-E 大幅推進

## 摘要

本輪目標是把 v1.3.0 ship 後的接續開發線從「優化方案」推進到可驗證的產品能力。Phase A-E 已完成第一輪落地:文件基準、v0.8 hardening、Workspace 今日工作台、細部權限 enforcement、半自動 workflow draft-first。

## 已完成

- Phase A · 文件基準:更新 `docs/DECISIONS.md`、`AI-HANDOFF.md`,新增 `docs/ROADMAP-vNext.md`,明確宣告 production surface 是 10 核心 Agent,legacy 29 Agent 只作參考。
- Phase B · Hardening:LibreChat endpoint 對齊 `/api/agents/chat`,Chrome Extension 帶入內容只進草稿,nginx 權限政策讓場勘 camera/mic/geolocation 可用,smoke 文件同步。
- Phase C · Workspace 工作閉環:Dashboard 新增「今日工作台」,5 Workspace 點擊後帶入安全草稿,專案預覽顯示下一步。
- Phase D · 管理與權限:新增 `require_permission_dep()`,第一批 enforcement 涵蓋 accounting、social、site survey、knowledge、media CRM、admin 類高風險入口；停用帳號全域 fail-closed。
- Phase E · 半自動 workflow:Workflow view 從 placeholder 升級為 draft-first UI；`prepare-preset` 產生主管家 prompt,可寫入 `project.handoff.workflow_draft` 並留 audit log。

## 重要風險已關閉

- Project handoff 不再覆蓋場勘、會議、workflow 系統欄位。
- Handoff 人工欄位可刪,系統欄位分流到 `meeting_next_actions` / `site_asset_refs`,GET 時合併回傳。
- Project owner/admin 邊界已加到 list/update/delete/handoff 與 workflow draft 寫入。
- Meeting / site survey 建立與 push-to-handoff 會檢查目標 project owner/admin,避免用自有紀錄旁路寫入別人的專案。
- `users` 權限查詢失敗時回 503 fail-closed,不 fallback 成 legacy 權限。
- `Projects` 前端在 401/403 後不再落入 localStorage 離線假成功。
- Reviewer 兩輪複查未發現新的 high / medium regression。

## 驗證結果

- Backend unit:236 passed,3 skipped。
- Meeting / site survey 專項:25 passed,1 skipped。
- Frontend syntax + build:pass。
- `scripts/smoke-test.sh`:8 pass / 0 fail。
- `scripts/smoke-librechat.sh`:11 pass / 0 fail。
- `git diff --check`:pass。

## 驗證限制

- `smoke-test.sh` 的 API 功能段因未設定 `LIBRECHAT_ADMIN_EMAIL` / `LIBRECHAT_ADMIN_PASSWORD` 而略過。
- `smoke-librechat.sh` 的 SSE contract 因未設定 `SMOKE_ADMIN_EMAIL` / `SMOKE_ADMIN_PASSWORD` 而略過。
- 找不到備份檔警告屬首次部署可忽略項；正式上線前仍需跑一次 `scripts/backup.sh` 與 restore drill。
- Browser Use 真機 UX 驗收尚在下一步執行。

## 建議分包

- Slice 1 · docs + decision baseline:`AI-HANDOFF.md`,`docs/DECISIONS.md`,`docs/ROADMAP-vNext.md` 與升級 / smoke 文件。
- Slice 2 · backend hardening + permissions:`backend/accounting/**` 權限 helper、handoff atomic merge、orchestrator draft-first、tests。
- Slice 3 · frontend workflow + UX:`frontend/launcher/**`,Chrome Extension manifest,nginx policy。

## 下一步

- 用 Browser Use 驗收 Dashboard、今日工作台、5 Workspace、Workflow modal、Project handoff 與 mobile layout。
- 補 `social.post_all` 真 enforcement。
- 為 workflow draft 增加「採用 / 修改後採用 / 拒絕」回饋,接到 Level 4 Learning 月報。
- 正式部署前跑 agent dry-run、backup / restore drill、Cloudflare Access checklist。

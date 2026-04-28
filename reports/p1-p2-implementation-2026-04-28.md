# P1/P2 技術債推進紀錄

日期:2026-04-28
基準:`reports/system-optimization-plan-2026-04-28.md`
目標:先把可安全落地、可驗證、不破壞交付版的 P1/P2 項目往前推。

## 已完成

| 項目 | 狀態 | 主要檔案 |
|---|---|---|
| P1-2 Secret registry + env tier | 完成 | `backend/accounting/services/secret_registry.py`, `config-templates/.env.tiers.md` |
| P1-3 Actions registry 收斂 | 完成第一版 | `config-templates/actions/registry.json`, `scripts/validate-actions.py`, `scripts/wire-actions.py` |
| P1-5 Retention registry | 完成 | `backend/accounting/infra/retention_policy.py`, `backend/accounting/main.py` |
| P1-6 NotebookLM Agent 透明性 | 完成 | `backend/accounting/routers/notebooklm.py`, `frontend/launcher/modules/notebooklm.js` |
| P1-8 inline handler 清理 | 完成 | `frontend/launcher/modules/dom-actions.js`, `frontend/launcher/index.html`, dynamic template modules |
| P1-9 NotebookLM batch/resume | 完成 | `backend/accounting/routers/notebooklm.py`, `frontend/launcher/modules/notebooklm.js` |
| P2-4 OpenAPI client 接縫 | 完成第一版 | `frontend/launcher/lib/api-client.js`, `frontend/launcher/lib/api-types.ts`, `frontend/launcher/modules/chat.js` |
| P2-7 Mongo collection dashboard | 完成 | `backend/accounting/routers/admin/dashboard.py`, `frontend/launcher/modules/admin.js`, `frontend/launcher/styles/admin-observability.css` |
| P2-9 NotebookLM settings token 驗證 | 完成 | `backend/accounting/services/notebooklm_client.py`, `backend/accounting/routers/notebooklm.py` |

## 本輪驗證

- `pytest backend/accounting/test_main.py -q --tb=short` → 179 passed
- `npm run build` in `frontend/launcher` → PASS,產出 `dist/app.J5YR3CKP.js`
- `python3 scripts/validate-actions.py` → PASS
- `rg "onclick=|onsubmit=|onchange=|onkeydown=|oninput=" frontend/launcher` → 無結果
- `npm audit --omit=dev` → 0 vulnerabilities
- `curl -I http://localhost/` → 200 OK

## 尚未完全做完的 P1/P2

| 項目 | 剩餘原因 | 建議下一刀 |
|---|---|---|
| P1-1 main.py < 150 行 | 牽涉 lifespan index / system endpoint 大搬遷,需獨立 PR 避免交付版回歸 | 先把 `/admin/error-log`, `/admin/access-urls`, `/health/ai-providers` 搬進 `routers/system.py` |
| P1-7 CSS 拆模組 | 已先拆 admin observability;NotebookLM 與 view-specific CSS 還在 `launcher.css` | 把 `/* v1.7+ NotebookLM */` 區塊搬 `styles/notebooklm.css`,再改 view lazy load |
| P2-1 17 view → 8 view | Sidebar 已收斂成主區 + details,但 DOM view 容器仍保留 | 下一輪做「工作 / 知識 / 對外」in-view tabs,不急著刪 router |
| P2-5 chat.js 拆檔 | 已接 API client,但 streaming/history/handoff 還在同檔 | 抽 `chat-streaming.js`, `chat-history.js`, `chat-handoff.js` |
| P2-6 app.js 拆 views | God object 還在,但 data-action 後更容易拆 | 先抽 `views/projects.js`,再抽 `views/workspace.js` |
| P2-10 歷史 docs 白標化 | 目前正式前端已白標;內部歷史文件仍大量保留專案名與客戶語境 | 另開 docs-only cleanup,避免改壞部署/驗收路徑 |

## 判斷

本輪把會直接影響交付穩定性的 P1/P2 多數風險先落地,並留下測試。剩餘項目屬大型重構或 docs-only cleanup,建議拆成下一個獨立批次處理。

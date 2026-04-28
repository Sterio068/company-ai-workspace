# 多代理 UI/UX Hardening 審查 · 2026-04-28

> 目標:把目前系統狀態往正式交付推進,特別針對「前端太複雜、附件/工作流心智負擔、鍵盤與行動端可用性、交付可信度」做多代理審查與第一輪高優先修補。

## 1. 審查方式

使用既有 skill 與多代理視角,未額外下載新 skill。現有 `frontend-design` / `a11y-audit` / `e2e-testing` / `code-reviewer` / `skill-installer` 已覆蓋本輪需求,因此避免引入不必要依賴。

| 視角 | 產出重點 |
|---|---|
| Product / UX | 新手心智模型、首頁與 sidebar 密度、是否比 ChatGPT 網頁版更像工作系統 |
| A11y / Keyboard | mobile drawer、modal focus trap、ARIA、target size、table semantics |
| Frontend Maintainability | `app.js` / `launcher.css` / inline handler / dist build 風險 |
| QA / Delivery | clean install、RAG/file_search 實測、DMG manifest、E2E 憑證、交付 Gate |

## 2. 本輪已修正

| 類別 | 修正 |
|---|---|
| HTML correctness | 修正 sidebar「使用教學」錯誤 closing tag (`</a>` → `</button>`) |
| Mobile drawer | 補 `aria-controls` / `aria-expanded` / `aria-hidden` / `inert`,開啟後焦點進 sidebar,Esc 關閉並還原焦點 |
| Project modal | 補 `role="dialog"` / `aria-modal` / `aria-labelledby` / `aria-hidden`,加 Esc/Tab focus trap,初始焦點落到「專案名稱」欄位 |
| User modal | 統一關閉流程,移除 keydown leak,Esc/Tab focus trap,關閉後還原焦點 |
| Table semantics | 移除同仁列表不完整的 `role="grid"` 避免螢幕閱讀器誤判 |
| Touch target | `.btn-tiny` 提升最小點擊尺寸與 padding |
| Clipboard | `copyHandoff()` 改用 `copyToClipboard()` fallback,失敗才開手動複製 modal |
| E2E credentials | 移除 `tests/e2e/view-coverage.spec.ts` 的硬編碼個人密碼 fallback,改讀 env / macOS Keychain |
| Backend tests | 舊測試密碼改成符合 v1.69 強密碼政策,保留安全驗證 |
| Workflow UX | `run-preset` 被 kill switch 擋下時,訊息補上 `/workflow/prepare-preset` 人審草稿路徑 |
| Today composer | F++ dashboard 在 app 顯示前接管,legacy composer 預設隱藏,避免回首頁時輸入被舊 textarea 清空 |
| Handoff copy | 分享格式統一為「專案交棒」,「下一棒」改成「接手同仁」降低內部黑話感 |
| E2E drift | 關鍵流程測試改支援新版 Dashboard F++ IA,不再依賴舊 `#workspace-cards` |
| Browser bundle | 重跑 `frontend/launcher npm run build`,`index.html` 已指向最新 `dist/app.7QLMX72T.js` |
| RAG/file_search | 新增 accounting 內建 LibreChat RAG adapter,OpenAI 知識庫 Agent 實測可回來源檔名與引用內容 |

## 3. 驗證結果

| 驗證 | 結果 |
|---|---|
| `./scripts/smoke-test.sh http://localhost` | 16 passed / 0 failed |
| `cd tests/e2e && npx playwright test view-coverage --reporter=line` | 32 passed |
| `python3 -m pytest backend/accounting -q` | 374 passed / 10 skipped |
| `node --check frontend/launcher/app.js` | passed |
| `git diff --check` | passed |
| 自訂 mobile drawer + project modal keyboard smoke | `ok: true` |
| `./scripts/release-verify.sh http://localhost` | 13 passed / 0 failed |
| RAG/file_search E2E | OpenAI 知識庫 Agent + `file_search` PASS · 見 `reports/rag-verify/rag-verify-2026-04-28-100959.md` |

Artifacts:

| Artifact | 路徑 |
|---|---|
| Keyboard smoke JSON | `reports/qa-artifacts/v1.69-multi-agent-ui-audit/a11y-keyboard-smoke.json` |
| Mobile drawer screenshot | `reports/qa-artifacts/v1.69-multi-agent-ui-audit/mobile-drawer-after-fix.png` |
| Desktop dashboard screenshot | `reports/qa-artifacts/v1.69-multi-agent-ui-audit/desktop-dashboard-after-fix.png` |
| 正式 release manifest | 最新 `reports/release/release-manifest-*.md` |
| DMG | `installer/dist/Company-AI-Installer.dmg` · SHA-256 以最新 release manifest 記錄為準 |
| RAG report | `reports/rag-verify/rag-verify-2026-04-28-100959.md` |

## 4. 目前完成度評估

| 面向 | 本輪後狀態 | 百分比 |
|---|---|---:|
| 功能完整性 | 核心流程、admin、project、workflow draft、帳號管理可用 | 88% |
| UI/UX 可用性 | 高風險鍵盤/行動端/Today composer 清空問題已修,但 IA 仍偏複雜 | 84% |
| A11y / Keyboard | drawer + modal 主阻塞已修,仍需全站 axe/Tab order baseline | 88% |
| 前端維護性 | 有第一輪修補,但 `app.js` / `launcher.css` / inline handler 債仍高 | 72% |
| 測試可信度 | release-verify 13/13、Playwright 68 passed / 4 skipped、pytest 374 passed / 10 skipped | 96% |
| 部署交付可信度 | 本機 release gate + DMG SHA manifest 已統一,RAG 本機 E2E 已補;clean Mac/VM 仍需外部機器證據 | 89% |

總評:本輪後已可作為 Phase 1 pilot candidate。正式 10 人開放前仍需乾淨 Mac/VM 安裝證據與 4 人 pilot 觀察;RAG/file_search 已有本機 E2E 證據,現場需用去識別真實樣本複跑。

## 5. 仍阻擋正式交付的項目

| 優先 | 項目 | 原因 |
|---|---|---|
| P0 | 乾淨 Mac/VM 安裝 + 錄影 + screenshots | 外部審計 F-08 仍是最大交付風險 |
| P1 | Sidebar / 首頁 IA 再收斂 | 現在仍像「功能中控」多於「丟工作進來的助理」 |
| P1 | 移除 inline handlers | 目前仍有約 40+ inline handler,與 v1.69 handoff 規則不一致 |
| P1 | `app.js` / `launcher.css` 拆檔 | 維護性是下一個最容易拖垮速度的問題 |

## 6. 下一輪建議

1. v1.70 UI/UX Sprint:把 sidebar 收到 5 個主入口 + 1 個「更多」,首頁改成「今日工作台 / 丟工作 / 最近交棒」三區。
2. v1.70 Frontend Debt Sprint:先移除 project modal inline handlers,再把 `app.js` projects / dashboard / modal 拆成 modules。
3. Phase 1 Gate Sprint:乾淨 Mac/VM 安裝、RAG 實測、4 人 pilot checklist。

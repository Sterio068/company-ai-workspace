# 2026-04-25 · 交付前持續測試修正

## 已修正

- E2E 測試基準升級:未登入改驗證必須導回 `/login`;登入後才驗 Launcher、Projects、CRM、會計、快捷鍵與 mobile。
- E2E 登入方式改為真實 UI login,避免 API login 後 refresh session 不穩。
- Playwright mobile 專案改用 Chromium Pixel 5 viewport,避免交付環境還要額外下載 WebKit。
- 快捷鍵 `?` 改同時支援 `e.key === "?"` 與 `Shift+/`,解決不同鍵盤事件回報差異。
- Launcher 初始化 `refreshAuth()` 改成 `refreshAuthWithLock()`,讓多分頁一進站也走同一把跨分頁 refresh lock,避免 refresh token 輪換互撞。
- 前端 cache-bust 更新到 `/static/app.js?v=75`。
- `scripts/backup.sh` 的 Meilisearch dump URL 從 `localhost` 改成 `127.0.0.1`,修正 BusyBox `wget` 在容器內偶發走錯連線路徑、拿不到 `taskUid` 的問題。
- `installer/build.sh` source 快照排除清單補強,不再把 `.claude/`、`tmp/`、E2E 產物、QA traces/screenshots 與本機 installer helper 打進交付 DMG。
- `.gitignore` 補上 `tests/e2e/test-results/` 與 `tmp/`,避免測試產物污染工作樹。

## 驗證結果

- Playwright E2E 全專案:`25 passed / 1 skipped`
- 10 分頁深連結巡檢:`10 passed / 0 failed`
- 後端 pytest:`246 passed / 13 skipped`
- Smoke test:`10 passed / 0 failed`(含 admin API login + 最新備份檢查)
- 手動備份:`Mongo + KB + Meilisearch dump` 均成功產生;目前未設 GPG/rclone,所以只做本機明文備份且不異機上傳。
- npm audit:`frontend/launcher` 與 `tests/e2e` production dependencies 皆 0 vulnerabilities
- DMG verify:`hdiutil verify` VALID
- DMG source 快照檢查:未包含 `.env` / `.git` / `config-templates/data` / `.claude` / `tmp` / E2E test-results / QA artifacts;已包含 `/static/app.js?v=75`、`refreshAuthWithLock()`、Meili `127.0.0.1:7700` 備份修正。
- 最新 DMG SHA-256:`68541136bd214fc75dab018cb94980b4d0c7f2f1dbe84b95c0c855602ca25c43`

## QA Artifacts

- `reports/qa-artifacts/20260425002609-delivery-10tabs-v75/delivery-10tabs-summary.json`
- Playwright 本輪 console output:desktop + mobile 全專案 25/1
- 最新安裝檔:`installer/dist/Company-AI-Installer.dmg`

## 交付注意

- `smoke-test.sh` 的 LibreChat API 功能段仍需 `LIBRECHAT_ADMIN_EMAIL` / `LIBRECHAT_ADMIN_PASSWORD`;本輪已提供環境變數驗證通過。
- 測試過程為了清 LibreChat in-memory login limiter,多次重啟 `company-ai-librechat` / `company-ai-nginx`;未清 Mongo,未刪使用者資料。
- 先前備份 stream 暫存檔 `/tmp/company-ai-mongo-dump-stream.gz` 仍保留且權限 `600`;未擅自刪除本機資料。
- 異機加密備份仍需現場設定 GPG key `company-ai` 與 rclone remote;腳本已設計為未加密時不會上傳出門。

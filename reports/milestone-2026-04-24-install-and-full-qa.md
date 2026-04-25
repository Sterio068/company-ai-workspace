# 2026-04-24 · 安裝檔重包與全系統 QA

## 已完成

- 重包安裝檔：`installer/dist/ChengFu-AI-Installer.dmg`
- DMG 驗證：`hdiutil verify` 通過，checksum valid
- DMG SHA-256：`043285f962ededc0959687d2ac1c4e876986ea7bd99429e5859aba4b63e6e672`
- 安裝路徑：已走 `scripts/start.sh` 啟動 stack，沿用既有 `.env` 與 Keychain，不重填金鑰、不清 Mongo 資料
- 前端修補：CRM 非同步載入卡片會套用 `localizeVisibleText`，避免測試代號或英文殘留
- 前端 cache-bust：`index.html` 更新為 `/static/launcher.css?v=63` 與 `/static/app.js?v=71`
- DMG 內容抽驗：內含 `frontend/launcher/index.html`、`launcher.css`、`modules/modal.js`、`modules/user_mgmt.js`，且包含 `v=71`、modal select/value 修補、同仁管理 ID 修補

## 系統狀態

- 容器：`nginx`、`LibreChat`、`MongoDB`、`Meilisearch`、`accounting`、`uptime` 均運行中
- Keychain：OpenAI 主力金鑰存在；Anthropic 備援金鑰存在
- `.env`：`CHENGFU_DEFAULT_AI_PROVIDER=openai`
- Mongo：1 位使用者；20 個助手，其中 OpenAI 10 個、Anthropic 10 個

## 測試結果

- `./scripts/smoke-test.sh`：8 通過 / 0 失敗
- `python3 -m pytest backend/accounting`：245 passed / 13 skipped
- Playwright 登入後全頁面測試：14 / 14 路由通過
- Playwright 互動抽測：AI 引擎切換、`⌘K` 指令面板、`?` 快捷鍵、工作包 modal、CRM 8 欄、workflow 3 卡、mobile menu 均通過
- Playwright 主力模型實測：主管家使用 OpenAI 主力引擎成功回覆固定驗收句，無送出失敗
- API 抽測：`/healthz`、`/api/config`、`/api-accounting/healthz`、CRM stats、workflow presets、safety classifier 皆通過
- Console：扣除登入前預期 401 / iframe 防護噪音後，無非預期 console error

## 追加安裝確認

- 2026-04-24 晚間再次執行新版套用：`./scripts/start.sh` 成功，Accounting image 以目前程式碼重建並 healthy
- 再次確認 `http://localhost/` 服務 `/static/app.js?v=69`
- 再次執行 `./scripts/smoke-test.sh`：8 通過 / 0 失敗
- 再次執行 `python3 -m pytest backend/accounting`：245 passed / 13 skipped
- 再次執行 `hdiutil verify installer/dist/ChengFu-AI-Installer.dmg`：VALID
- 再次執行 Playwright 登入後回歸：14 / 14 路由、7 / 7 API、OpenAI 主力模型回覆皆通過；`?` 快捷鍵另以主內容焦點重測通過

## 追加手動 QA · 2026-04-24 晚間

- 修補 `modal.prompt`：支援 `value` / `select` / `submitText`，避免社群排程、媒體名單、Help 設定編輯時欄位不帶值或下拉變文字框。
- 修補 `.modal2-overlay` CSS：自製 modal 現在會持續可見，覆蓋同仁管理、會議速記、媒體推薦結果、場勘結果等非共用 modal。
- 修補同仁管理 modal：`aria-labelledby` 改用 `um-dialog-title`，避免與頭銜輸入框 `um-title` 重複 ID。
- 修補知識庫新增資料源提示：白名單文案改為 `/Volumes`、`/data`、`/tmp/chengfu-test-sources`，與後端限制一致。
- Playwright 手動資料流：登入、AI 引擎切換、工作包建立、交棒卡保存、CRM 商機詳情、流程草稿、媒體名單、社群排程、會計新交易引導、會議速記入口、場勘入口、Help、中文化掃描皆通過。
- Targeted retest：知識庫資料源以 `/tmp/chengfu-test-sources/qa-final-20260424151036` 建立並可在知識庫瀏覽；同仁管理建立 QA 帳號成功；console 0 非預期錯誤。
- QA artifacts：`reports/qa-artifacts/20260424150528/manual-qa-summary.json`、`reports/qa-artifacts/20260424150931-targeted/targeted-qa-summary.json`、`reports/qa-artifacts/20260424151036-final-targeted/final-targeted-summary.json`
- 產生 QA 資料但未刪除：工作包 3 筆、CRM 商機 2 筆、媒體聯絡人 1 筆、社群排程 1 筆、知識庫來源 2 筆、QA 同仁 1 筆，名稱皆有 `QA-勿刪` 或 `qa-` 前綴。

## 最新驗證

- `./scripts/smoke-test.sh`：8 通過 / 0 失敗
- `python3 -m pytest backend/accounting`：245 passed / 13 skipped
- `hdiutil verify installer/dist/ChengFu-AI-Installer.dmg`：VALID
- 最新 DMG SHA-256：`4ae1b68793bb412d5d1704874ec081ad79c492c691ce0fd0b8c275118e50771d`
- 最新 DMG 內容抽驗：source tar 含 `launcher.css?v=63`、`app.js?v=72`、modal select/value、同仁管理 `um-dialog-title`、`.modal2-overlay` CSS、對話訊息 404 防護

## 未完成 / 注意

- `smoke-test.sh` 的 LibreChat API 功能段仍因未提供 `LIBRECHAT_ADMIN_EMAIL` / `LIBRECHAT_ADMIN_PASSWORD` 環境變數而略過；Playwright 已用實際登入補測前端與 API。
- 備份檔尚未存在；首次部署可忽略，正式交付前建議執行一次 `./scripts/backup.sh` 驗證備份產物。

## 追加安裝後 QA · v72

- 保留資料套用新版：再次執行 `scripts/start.sh`，`.env` SHA-256 前後一致，Keychain 與 Mongo 既有資料未重設。
- Post-install 全功能手動流：13 通過 / 1 失敗；唯一失敗為新對話回填時預讀不存在的 `/api/messages/<conversationId>` 造成 console 404。
- 已修補：`frontend/launcher/modules/chat.js` 新增 `_conversationExists()`，在讀訊息前先確認對話存在；不存在時走最近對話回填，不再打出 404。
- Cache-bust：`frontend/launcher/index.html` 更新為 `/static/app.js?v=72`。
- 聚焦回歸：`reports/qa-artifacts/20260424152414-console-retarget/console-retarget-summary.json`，4 通過 / 0 失敗，OpenAI 主力模型實際回覆 `POSTPATCH_QA_OK`，console / network 0 非預期錯誤。
- 主頁巡檢：`reports/qa-artifacts/20260424152552-v72-nav-sweep/v72-nav-sweep-summary.json`，15 個主 view 皆可切換，17 通過 / 0 失敗。
- 重新打包安裝檔：`installer/dist/ChengFu-AI-Installer.dmg`，`hdiutil verify` VALID，source tar 已抽驗含 `app.js?v=72` 與 `_conversationExists`。
- 最終套用確認：重新執行 `scripts/start.sh`，`.env` SHA-256 仍為 `453d2e9011f6daf84378f0f8d55b659f04efb7e9df784fc4d481690866ef4307`，`http://localhost/` 服務 `launcher.css?v=63` / `app.js?v=72`。
- 最終驗證：`./scripts/smoke-test.sh` 8 通過 / 0 失敗；`python3 -m pytest backend/accounting` 245 passed / 13 skipped。
- 最新資料量：users 3、agents 20、projects 6、crmLeads 4、scheduledPosts 2、knowledgeSources 4；新增資料皆為 QA 前綴，未執行刪除、外送、正式發布。

## 交付前硬化測試 · v73

- Runtime 安全模式確認：`chengfu-accounting` 目前為 `NODE_ENV=production`、`ECC_ENV=production`、`ALLOW_LEGACY_AUTH_HEADERS=0`。
- 修補 production 設定：`config-templates/.env` 改為 production，`scripts/start.sh` 仍預設不合併 `docker-compose.override.yml`，避免本機交付誤開 legacy header。
- 修補未登入資料外洩：`/api-accounting/knowledge/list`、`/knowledge/read`、`/knowledge/search` 全部改為需登入；新增 pytest 覆蓋未登入 403。
- 修補 Uptime 暴露面：`chengfu-uptime` 從 `0.0.0.0:3001` 改為 `127.0.0.1:3001`，只允許本機查看。
- 修補內部工具預設 rate limit：整體 default 從過低值調整到適合 10 人內網 dashboard burst；admin email、quota preflight 等敏感 endpoint 仍保留專用限制。
- 修補多分頁 refresh 抖動：`frontend/launcher/modules/auth.js` 新增跨分頁 refresh lock，`index.html` cache-bust 更新為 `/static/app.js?v=73`。
- 修補安裝路徑安全預設：安裝精靈即使公司域名留空，也會寫入 `NODE_ENV=production`、`ECC_ENV=production`、`ALLOW_LEGACY_AUTH_HEADERS=0`；域名只影響 `DOMAIN_CLIENT` / `DOMAIN_SERVER`。
- 未登入 / 偽造 header / 安全標頭 / 登入後 API 矩陣：24 通過；原先 knowledge list 未登入 200 已修成 403。
- 全量後端測試：`python3 -m pytest backend/accounting`，246 passed / 13 skipped。
- Smoke test：`./scripts/smoke-test.sh`，8 通過 / 0 失敗。
- npm dependency audit：`frontend/launcher` 與 `tests/e2e` production dependencies 皆 0 vulnerabilities。
- DMG 重包：`installer/dist/ChengFu-AI-Installer.dmg`，`hdiutil verify` VALID，SHA-256 `317a7b950830d566a0700c9eeb452a75526662712230c36ae5be37c5fc4be320`。
- DMG 內容抽驗：source tar 未含 `.env` / `.git` / `config-templates/data`；內含 `app.js?v=73`、knowledge auth guard、`127.0.0.1:3001:3001`、安裝精靈 localhost production 預設。
- QA artifacts：`reports/qa-artifacts/20260424154701-pre-delivery-hardening-final/hardening-summary.json`、`reports/qa-artifacts/20260424155119-hardening-ui-login-10tabs/hardening-ui-login-10tabs-summary.json`、`reports/qa-artifacts/20260424235614-hardening-final/shell-hardening-final.txt`。

## 交付前剩餘風險

- 同帳號 10 分頁極限測試仍非完全通過：UI 登入後 10 tabs 快速掃 13 個 view 時約 5/10 通過，失敗主因是同一個 LibreChat refresh token 在多 context 同時輪換導致 401/abort，另有 dashboard burst 429。這不是「10 位同仁各自帳號」的真實模型；正式交付前若要把併發驗收到 100%，需建立 10 個測試帳號做真實 10-user session 測試。
- `smoke-test.sh` 的 LibreChat API 功能段仍因未提供 `LIBRECHAT_ADMIN_EMAIL` / `LIBRECHAT_ADMIN_PASSWORD` 環境變數而略過；前端登入與 accounting API 已用實際 session 補測。
- 備份流程已做 `mongodump` stream + `gzip -t` 驗證，但暫存檔 `/tmp/chengfu-mongo-dump-stream.gz` 仍保留且已設 `600` 權限；未刪除是為避免擅自刪除本機資料。

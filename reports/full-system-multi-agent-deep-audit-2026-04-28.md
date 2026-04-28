# 全系統全模組多代理深度審計報告

日期:2026-04-28 20:20 CST
更新:2026-04-28 22:39 CST · 最終檢查重跑 release gate 仍全綠
範圍:Launcher UI/UX、NotebookLM、本地資料庫、Agent Actions、後端 API、安裝包、E2E、release gate、安全與維運
結論:**本機 release gate 已通過,可進入乾淨機/現場驗收**。Sprint 0 已解除 E2E 紅燈、NotebookLM Action 契約缺口、前端切頁/重複 listener 與 Docker image 漏包 `infra/` 問題；Sprint 1 再補 Action 低權限 token、Help markdown sanitize、備份加密 fail-loud、OAuth prod origin pin。22:22 又完成商機追蹤 / 會計 / 會議速記 / 場勘 / 使用教學五大日常模組 UX 強化。正式多公司交付前剩餘主風險是乾淨 Mac/VM 首裝證據與真 NotebookLM Enterprise round-trip。

---

## 1. 多代理審計矩陣

| 面向 | 審計視角 | 判定 | 核心結論 |
|---|---|---:|---|
| Backend / NotebookLM / Actions | reviewer agent | No-Go | NotebookLM agent endpoints 要 `X-Acting-User` / `confirm_send_to_notebooklm`,但 action schema 未暴露；部分 internal actions 無法滿足後端 auth contract |
| Frontend / UI / UX / a11y | reviewer agent | No-Go | 產品方向正確,但 view 雙重載入、NotebookLM 重複 listener、首頁隱藏資料卻阻塞首屏會直接影響使用者感受 |
| QA / Release / Installer | reviewer agent | No-Go | 最新 release gate 明確失敗；乾淨 Mac/VM 首裝仍無實證；文件仍宣稱舊版全綠 |
| Security / Ops | reviewer agent | Gate Green locally | 已改 ACTION_BRIDGE_TOKEN 低權限接線、備份無 GPG 預設中止、help markdown sanitize、OAuth prod no fallback |
| Local verification | Codex 主控 | Gate Green | Sprint 1 + 五大日常模組 UX 後 `release-verify` 13/13,Playwright 73 passed / 5 skipped |

---

## 2. 最新驗證結果

| 類型 | 指令/來源 | 結果 |
|---|---|---:|
| Frontend build | `npm run build` in `frontend/launcher` | PASS |
| Action registry | `python3 scripts/validate-actions.py` | PASS · 8 specs · 4 wired |
| Backend focused pytest | `pytest backend/accounting/test_main.py -q --tb=short -k 'action_bridge or oauth_redirect_uri or oauth_token_plaintext or internal_token_with_acting_user or notebooklm_agent_routes'` | PASS · 8 passed |
| Release backend pytest | `./scripts/release-verify.sh http://localhost` 內部 | PASS · 406 passed / 10 skipped |
| Main smoke | release gate 內部 `scripts/smoke-test.sh` | PASS · 17/17 |
| LibreChat route smoke | release gate 內部 `scripts/smoke-librechat.sh` | PASS · 13/13 |
| Installer build + DMG inspect | release gate 內部 | PASS |
| Playwright E2E | release gate 內部 | PASS · 73 passed / 5 skipped |
| Release gate | `./scripts/release-verify.sh http://localhost` | PASS · 13 passed / 0 failed |

最新 release manifest:

- `/Users/sterio/Workspace/CompanyAI/reports/release/release-manifest-2026-04-28-223907.md`
- DMG:`/Users/sterio/Workspace/CompanyAI/installer/dist/Company-AI-Installer.dmg`
- SHA-256:`72260b17131d9d3b6b201609a5b1e03dac893e786d09e53d8a10aa51157ebf6a`
- Manifest 結論:`正式交付版驗收通過`

---

## 2.1 Sprint 0 已完成修復

1. L3 badge E2E 紅燈已修復:`chat.open()` / suggestion 塞入文字後改用 bubbling input event,document-level delegated classifier 能收到事件。
2. Admin view 404 已修復:重建 backend image 後 `/admin/storage-stats` 路由存在；並修正 monitored collection 名稱為實際會計 collection。
3. Docker image 漏包已修復:`backend/accounting/Dockerfile` 補 `COPY infra/ ./infra/`,避免正式容器啟動時 `ModuleNotFoundError: infra`。
4. NotebookLM resume 已補專案與 notebook scope,避免跨專案 batch id 相同時錯誤跳過檔案。
5. Internal Action acting-user 邊界已補:有效 `X-Internal-Token + X-Acting-User` 會成為 trusted acting user,再套用一般權限。
6. NotebookLM/internal action specs 已補 `X-Acting-User` header 與 `confirm_send_to_notebooklm` 欄位。
7. 前端 view 導覽已收斂:sidebar/nav 改走 hash route,`showView()` 統一負責 view lazy-load side effect。
8. NotebookLM root click listener 已加一次性 guard,避免反覆切頁後重複同步/複製。

## 2.2 Sprint 1 已完成硬化

1. Action credentials 降權:LibreChat 內部 Actions 改用 `ACTION_BRIDGE_TOKEN`,不再把全域 `ECC_INTERNAL_TOKEN` 寫入 action metadata；後端只在 action allowlist path + `X-Acting-User` 存在時接受。
2. Vendor key 預設不落 LibreChat DB:`wire-actions.py` 對 OpenAI/Fal raw key 需 `ALLOW_LIBRECHAT_ACTION_SECRET_PERSISTENCE=1` 明確 opt-in 才會接線。
3. Keychain / compose / secret registry 已補 `ACTION_BRIDGE_TOKEN`;`start.sh` 會自動產生缺漏的本機 action token,避免使用者重新輸入。

## 2.3 五大日常模組 UX 強化(22:22 補)

1. 商機追蹤:新增「今日追蹤 / 風險 / 跟進缺口 / 預期管線」四卡,商機詳情可直接改階段、勝率、截止日、摘要與跟進紀錄。
2. 會計:新增「今日財務接續」工作台,把待收款、報價追蹤、帳務健康與新增交易 / 開發票 / 建報價集中。
3. 會議速記:新增工作台 hero、三步流程、摘要複製,完成後可推工作包並標記教學進度。
4. 場勘:新增工作台 hero、三步流程、HEIC 前端可選、歷史紀錄可點開、場勘 brief 可複製,修正處理 banner 圖片數歸零問題。
5. 使用教學:新增「五大日常模組」內嵌教學與 `frontend/launcher/user-guide/daily-ops-modules.md`,角色進度也開始覆蓋商機、會計、會議、場勘任務。
4. Help markdown 已改為 `marked.parse` 後再走 `sanitizeRenderedHtml`,並同步收緊 URL protocol allowlist。
5. Launcher CSP 已移除 `script-src 'unsafe-inline'`,保留 inline style 相容現有視覺。
6. `backup.sh` 在沒有 GPG key `company-ai` 時預設 fail-loud,只允許明確 `ALLOW_PLAINTEXT_BACKUP=1` 的本機開發備份。
7. Social OAuth 在 production 未設定 `OAUTH_REDIRECT_BASE_URL` 時直接 500,不再 fallback `Host` / `X-Forwarded-Host`。
8. OAuth token encryption 在 production 無 `CREDS_KEY` 或缺 `cryptography` 時直接拒絕,不再明文 `PLAIN:` fallback。

---

## 3. P0 阻塞 Findings

### P0-1 · Release gate 紅燈

狀態:**已修復**。

最新 manifest 記錄 Playwright E2E 失敗,release 結論為不可交付:

- `/Users/sterio/Workspace/CompanyAI/reports/release/release-manifest-2026-04-28-201256.md:17`
- `/Users/sterio/Workspace/CompanyAI/reports/release/release-manifest-2026-04-28-201256.md:31`
- `/Users/sterio/Workspace/CompanyAI/reports/release/release-manifest-2026-04-28-201256.md:33`

失敗重點:

- L3 提醒 badge 測試期望「第三級提醒」,實際仍顯示「第一級 公開」。
- Admin view 測試抓到 404 console error。
- 失敗在 desktop 與 mobile 都重現。

相關測試:

- `/Users/sterio/Workspace/CompanyAI/tests/e2e/critical-journeys.spec.ts:197`
- `/Users/sterio/Workspace/CompanyAI/tests/e2e/critical-journeys.spec.ts:206`
- `/Users/sterio/Workspace/CompanyAI/tests/e2e/view-coverage.spec.ts:121`
- `/Users/sterio/Workspace/CompanyAI/tests/e2e/view-coverage.spec.ts:134`

### P0-2 · NotebookLM Agent Actions 規格與後端契約不一致

狀態:**已修復第一層契約**。Action specs 已補 `X-Acting-User` / `confirm_send_to_notebooklm`,後端也支援 internal token + acting user 進一般權限檢查。仍建議下一輪做真 LibreChat action round-trip。

後端要求 Agent action 明確提供 acting user 與二次同步確認:

- `/Users/sterio/Workspace/CompanyAI/backend/accounting/routers/notebooklm.py:179`
- `/Users/sterio/Workspace/CompanyAI/backend/accounting/routers/notebooklm.py:185`
- `/Users/sterio/Workspace/CompanyAI/backend/accounting/routers/notebooklm.py:609`
- `/Users/sterio/Workspace/CompanyAI/backend/accounting/routers/notebooklm.py:926`

但 action specs 沒有暴露 `X-Acting-User`,sync request body 也缺 `confirm_send_to_notebooklm`:

- `/Users/sterio/Workspace/CompanyAI/config-templates/actions/notebooklm-bridge.json:28`
- `/Users/sterio/Workspace/CompanyAI/config-templates/actions/internal-services.json:423`
- `/Users/sterio/Workspace/CompanyAI/config-templates/actions/internal-services.json:576`
- `/Users/sterio/Workspace/CompanyAI/config-templates/actions/internal-services.json:591`

影響:主管家或其他 Agent 看似能操作 NotebookLM,實際可能卡在 400 / 409,尤其 L3 或 Agent-created source pack 無法完成同步。

### P0-3 · 前端 view 導覽有雙重載入與 NotebookLM 重複 listener 風險

狀態:**已修復主要風險**。

`setupNavigation()` 點擊會直接 `showView()`,而 `activateLauncherView()` 又會改 hash 觸發路由,非 dashboard view 容易重複載入:

- `/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:474`
- `/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:479`
- `/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:644`
- `/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/router.js:49`

NotebookLM 每次 render/bind 都對同一 root 加 click listener,重複切頁後可能造成同步/複製重複觸發:

- `/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/notebooklm.js:67`
- `/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/notebooklm.js:334`
- `/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/notebooklm.js:376`

影響:這是 UI/UX 和功能穩定性的交會點,使用者會感覺「按一次做兩次」或切頁卡頓。

### P0-4 · Actions credential 與備份落地邊界不符合正式交付硬化

狀態:**已修復主要交付風險**。仍建議在正式現場檢查 live LibreChat `actions` collection 是否已清掉舊 `metadata.api_key` 紀錄,必要時重跑 `scripts/wire-actions.py` 以新 action id / metadata 覆蓋。

`wire-actions.py` 已改為:

- 內部 Actions 使用低權限 `ACTION_BRIDGE_TOKEN`。
- 外部 vendor key 預設不持久化到 LibreChat metadata。
- 後端只在 action allowlist path + `X-Acting-User` 下接受 action bridge token。

備份腳本已改為沒有 GPG key `company-ai` 時直接中止,除非明確 `ALLOW_PLAINTEXT_BACKUP=1`。明文 fallback 不再是正式預設。

驗證:

- `python3 scripts/validate-actions.py` → PASS
- backend focused action/oauth tests → 8 passed
- `./scripts/release-verify.sh http://localhost` → 13/13 PASS

### P0-5 · 沒有真正乾淨 Mac/VM 安裝證據

狀態:**未完成**。仍列交付前硬化。

目前 clean install 報告是 current-host rehearsal,不是乾淨機首裝:

- `/Users/sterio/Workspace/CompanyAI/reports/clean-install/clean-install-verify-2026-04-28-094351.md:7`
- `/Users/sterio/Workspace/CompanyAI/reports/clean-install/clean-install-verify-2026-04-28-094351.md:17`
- `/Users/sterio/Workspace/CompanyAI/reports/clean-install/clean-install-verify-2026-04-28-094351.md:48`

影響:DMG 已可產出,但尚不能證明第一次拿到的公司 IT 能完整裝起來。

---

## 4. P1 高優先 Findings

1. `/admin/storage-stats` 監控 collection 名稱錯誤。Dashboard 監控 `transactions/invoices/quotes`,但實際會計 collection 是 `accounting_transactions/accounting_invoices/accounting_quotes/accounting_projects_finance`。參考 `/Users/sterio/Workspace/CompanyAI/backend/accounting/routers/admin/dashboard.py:45` 與 `/Users/sterio/Workspace/CompanyAI/backend/accounting/main.py:65`。

2. NotebookLM resume 判斷只看 `batch_id + relative_path + status`,沒有納入 `project_id/notebook_id`。跨專案重用 batch id 可能錯誤跳過檔案。參考 `/Users/sterio/Workspace/CompanyAI/backend/accounting/routers/notebooklm.py:367`。

3. 首頁把 inspector 完全隱藏,但 init 仍等待 conversations / usage / ROI 等資料載入後才顯示 app。參考 `/Users/sterio/Workspace/CompanyAI/frontend/launcher/launcher.css:172`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/index.html:803`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:189`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:231`。

4. `⌘K` palette 缺 dialog/listbox 語意、focus restore 與 active descendant。參考 `/Users/sterio/Workspace/CompanyAI/frontend/launcher/index.html:987`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/palette.js:24`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/palette.js:73`。

5. Project drawer 是 modal 行為,但沒有 `role="dialog"`、`aria-modal` 與 focus trap。參考 `/Users/sterio/Workspace/CompanyAI/frontend/launcher/index.html:856`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:1761`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:1843`。

6. 動態 HTML 仍有 inline handler 殘留,事件模型尚未完全統一。參考 `/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/chat.js:1098`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/modules/chat.js:1100`、`/Users/sterio/Workspace/CompanyAI/frontend/launcher/app.js:720`。

7. Help markdown XSS 風險已修:使用手冊 markdown 已 sanitize,Launcher CSP 已移除 `script-src 'unsafe-inline'`。剩餘 inline style 屬視覺相容債,不是 script 執行債。

8. `api-types.ts` 仍是 bootstrap placeholder,不是真正由 backend OpenAPI 產生的型別。參考 `/Users/sterio/Workspace/CompanyAI/frontend/launcher/lib/api-types.ts:1`。

9. 安裝包與外部可見文件仍有固定「公司 / CompanyAI」字樣,與 D-016 白標決策衝突。參考 `/Users/sterio/Workspace/CompanyAI/docs/DECISIONS.md:123`、`/Users/sterio/Workspace/CompanyAI/installer/build.sh:21`、`/Users/sterio/Workspace/CompanyAI/installer/build.sh:84`、`/Users/sterio/Workspace/CompanyAI/installer/build.sh:140`。

10. Release 文件與最新狀態不一致。多份文件仍宣稱 release gate 全綠,但最新 manifest 是紅燈。需要先修文件,避免下一位接手者誤判。

---

## 5. P2 技術債與可信度缺口

| 類別 | 現況 | 影響 |
|---|---|---|
| 大型前端檔 | `app.js` 2210 行、`chat.js` 1308 行、`launcher.css` 6780 行 | 變更成本高,回歸風險高 |
| 大型後端檔 | `main.py` 957 行、`notebooklm.py` 942 行 | API 邏輯耦合,測試定位慢 |
| Retention policy | 新 registry 存在,但 startup TTL 仍有硬編碼 | 未完全單一來源 |
| E2E 真實度 | 核心 flows 有 route fulfill mock | 可驗 UI,但不能完全代表真實 AI/後端閉環 |
| Playwright harness | `webServer.command` 只是 echo,依賴外部 localhost | 不是真正自給自足 release harness |
| Visual/a11y gate | view coverage 只檢查 DOM + console + screenshot 保存 | 沒有 screenshot baseline,沒有 axe gate |
| OAuth callback | production 未設 `OAUTH_REDIRECT_BASE_URL` 會 fail closed | 現場需填正式 `https://...` 後才能開 OAuth |
| 密碼交付 | `create-users.py` 仍有 `scripts/passwords.txt` 暫存模式 | 需確保只作 legacy/一次性,release gate 已檢查不存在 |

---

## 6. 修復順序建議

### Sprint 0 · 先解除 No-Go 狀態

1. 修 L3 badge E2E:確認 composer → chat input 後 classifier 是否重新跑、文字是否改為測試期望或測試更新到新文案。
2. 修 admin view 404 console error:追來源 request,補 route 或靜音非致命資源 404。
3. 跑 `./scripts/release-verify.sh http://localhost` 到 13/13。
4. 更新所有宣稱全綠的文件,改成以最新 manifest 為準。

### Sprint 1 · Agent / NotebookLM 可用性

1. `notebooklm-bridge.json` 與 `internal-services.json` 補 `X-Acting-User` header。
2. Sync request body 補 `confirm_send_to_notebooklm`。
3. 加 action contract smoke:preview → create → sync local_ready / confirm_required / confirmed sync。
4. 修 NotebookLM resume query,加入 `project_id/notebook_id`。

### Sprint 2 · UI/UX 可交付硬化

1. Hash routing 成為唯一入口,避免 `showView()` 雙載入。
2. NotebookLM root listener 加一次性 guard。
3. 首頁改為先顯示 app,conversations/usage/ROI 延後載入或移回可見區。
4. NotebookLM UI 收斂成單一主 CTA,第二步再分「從專案建立」與「直接上傳」。
5. `⌘K`、Project drawer 補 dialog/focus/a11y。

### Sprint 3 · Security / Ops hardening

1. 現場清查舊 LibreChat `actions` collection 是否仍有歷史 `metadata.api_key`。
2. 現場建立 GPG key `company-ai`,跑一次 `scripts/backup.sh` 確認只產 `.gpg`。
3. 設定正式 `OAUTH_REDIRECT_BASE_URL=https://...`。
4. 用真 NotebookLM Enterprise token 跑 action round-trip。

### Sprint 4 · 交付可信度

1. 乾淨 Mac/VM 跑 DMG 首裝並錄影。
2. 補一條真 NotebookLM Enterprise token 的建立 notebook / 上傳 / 同步驗收。
3. 將 Playwright webServer 改成可自啟/自檢 stack,或 release gate 明確要求 stack precondition。
4. 補 visual regression baseline 與 axe smoke。

---

## 7. 交付判定

目前工程狀態:**本機 release gate 已通過,可進乾淨機/現場驗收**。
最短正式交付路徑是補 P0-5,再做一輪真 LibreChat Action → NotebookLM round-trip 與乾淨 Mac/VM 錄影驗收。

若要對內試用:可開放小圈試用。
若要對外或給不同公司正式安裝:建議先完成安全維運硬化、白標安裝命名與乾淨機驗收。

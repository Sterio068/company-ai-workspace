# NotebookLM v1.7 W1 Hardening Report

日期:2026-04-28
依據:`reports/system-optimization-plan-2026-04-28.md`
範圍:NotebookLM ship-ready / UI 簡化 / Agent 可操作性 / 可測試性

---

## 1. 完成項目

| Plan ID | 狀態 | 實作重點 |
|---|---|---|
| P0-2 | ✅ 完成 | Agent endpoints 需帶 `X-Acting-User`,並套 acting user 的工作包 ACL;不可再用 admin 身分跨專案建立/同步資料包 |
| P0-5 | ✅ 完成 | Source Pack hash 排除同日時間與小數財務雜訊;同一業務內容可正確 dedupe |
| P1-4 | ✅ 完成 | Source Pack 保存 `sensitivity`,建立與同步寫 audit/sync run;前端列表顯示資料等級;L3 同步前提示會送 NotebookLM Enterprise |
| P1-6 | ✅ 完成 | Agent 建立的資料包 `created_by=agent:{email}`;前端顯示 Agent 建立徽章 |
| P2-2 | ✅ 完成 | NotebookLM UI 拆成資料包、檔案/資料夾上傳、預覽/歷史三區塊,降低操作混淆 |
| P2-3 | ✅ 完成 | NotebookLM 首屏/區塊/step card 補 `role` / `aria-labelledby` / `aria-label` |
| P2-8 | ✅ 完成 | NotebookLM client 將 401/403/429/5xx 分成 `token_expired` / `permission_denied` / `quota_exceeded` / `api_down` |

---

## 2. 使用者體驗變更

- 首屏改成「本地資料庫 → 資料包/檔案 → 專案 Notebook」關係圖,一眼看出 NotebookLM 與本地資料庫的並行關係。
- 建立資料包與上傳檔案不再塞在同一張卡內,避免使用者誤以為選 A 工作包後一定會影響另一個上傳流程。
- 最近資料包顯示狀態、scope、字數、hash、資料等級、Agent 建立者。
- L3 資料不阻擋同步,但同步前明確提示會送 NotebookLM Enterprise。

---

## 3. 驗證結果

| 驗證 | 結果 |
|---|---|
| `python3 -m py_compile backend/accounting/routers/notebooklm.py backend/accounting/services/source_pack_renderer.py backend/accounting/services/notebooklm_client.py` | ✅ PASS |
| `pytest backend/accounting/test_main.py -q -k notebooklm --tb=short` | ✅ 12 passed |
| `pytest backend/accounting/test_main.py -q --tb=short` | ✅ 171 passed |
| `node --check frontend/launcher/modules/notebooklm.js` | ✅ PASS |
| `cd frontend/launcher && npm run build` | ✅ `dist/app.GUK3GAMQ.js` + `chunks/notebooklm.Y5JGBZUO.js` |
| `npx playwright test view-coverage.spec.ts -g "notebooklm" --project=chromium --reporter=line` | ✅ 1 passed |
| `./scripts/start.sh` | ✅ Keychain secrets 注入後重啟 Docker stack |
| `./scripts/release-verify.sh http://localhost` | ✅ 13/13 passed · manifest `reports/release/release-manifest-2026-04-28-190513.md` |

---

## 4. 剩餘風險

- 真 NotebookLM Enterprise token 尚未在乾淨 Mac/VM 跑「建立 notebook / 同步資料包 / 上傳資料夾」完整現場驗證。
- P1-9 batch resume 尚未完成;大量資料夾上傳若中途失敗,目前會逐檔留下 failed record,但尚未提供一鍵續傳。
- P2-9 token 寫入前 lightweight 驗證尚未完成;目前錯 token 會在同步或上傳時回 `recovery_hint`。
- 多公司白標化仍需 P0-1 tenant boundary,不可在第二家公司上線前跳過。

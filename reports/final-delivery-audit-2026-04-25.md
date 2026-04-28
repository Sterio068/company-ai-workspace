# 公司 AI · 交付前最終審計

日期:2026-04-25
結論:正式交付版驗收通過。已通過本機完整 release gate、E2E、smoke、安裝檔重建與 DMG 敏感檔抽查；可作為內部分發交付版。

補充:外部 AI 產品審計給出 770/1000「可帶條件交付」。本輪已補上其中可在開發機完成的高槓桿項目；LibreChat RAG/file_search 已有本機 E2E 證據。乾淨 Mac/VM 安裝驗收仍列為現場驗收,不在開發機上偽裝完成。

## 多代理審計面向

- Frontend Architecture:工作區路由、Service Worker、載入 race、mobile nav、onboarding、E2E 穩定性。
- UI/UX:5 工作區是否真的成為工作面、附件流程、繁中介面、手機可用性、認知負荷。
- Backend/API:專案權限、CRM owner policy、媒體 CRM PDPA 遮罩、場勘音訊 note lifecycle、協作者 access。
- Security/Release:admin fallback、機敏暫存檔、DMG snapshot 排除、Keychain、安裝器 fail-fast。
- QA/Deploy:smoke test、LibreChat route contract、E2E 登入狀態、DMG 打包、升級既有安裝。

## 本輪已修正的交付阻塞

- 前端改為真正 5 工作區頁面,桌面卡片與手機底部導覽都導向 `#workspace-1..5`,且 hash 不再被通用 router 清掉。
- 移除 runtime 清 Service Worker/cache 的危險行為,避免破壞同 origin 快取。
- 修正 conversations/agents 載入 race、錯誤 retry handler、onboarding 指向隱藏節點、meeting banner selector。
- 補上實際附件上傳 E2E:檔案會打到 `/api/files`,並帶入 `/api/agents/chat` payload。
- Backend 收緊專案更新權限,非 owner 不可改全專案 metadata。
- 媒體 CRM 非 admin 遮 email/phone/notes,同時保留 `id` alias 給 UI/API 穩定使用。
- 場勘 audio note 上傳立即回 `note_id`,讀取場勘會回 `audio_notes`,協作者/next_owner 可綁定相關資料。
- CRM 防止一般使用者偽造 owner/by,非 admin 只能操作自己名下 lead。
- 安裝器會 fail-fast 阻擋 `scripts/passwords.txt` / `config-templates/users.json`,DMG snapshot 排除 `.env`、uploads、images、reports、test artifacts。
- 安裝器「沿用既有」現在會先套用 DMG 內建新版程式碼,但保留 `.env`、data、uploads、images、node_modules。
- Smoke test 補真實瀏覽器 User-Agent,避免 LibreChat uaParser 將驗收腳本誤判為非法請求。
- E2E 登入失敗時會清空密碼欄再丟錯,避免 Playwright 失敗快照留下密碼。
- 外部審計補強:sidebar 移除重複入口並折疊 AI 模型切換,首頁 composer 支援選檔/拖放/file ribbon,Workspace 首屏改為接續工作包優先,首頁 H2 與 sidecar 改成直白操作文案。
- PM happy-path E2E 改為覆蓋首頁 composer → 首頁附檔 ribbon → chat 待送出附件 → `/api/agents/chat` payload → 交棒卡填寫 → 複製 LINE。

## 驗證結果

- `./scripts/release-verify.sh http://localhost`:13 passed,0 failed。最新 Manifest 以 `reports/release/release-manifest-*.md` 為準,DMG SHA 以最新 manifest 內記錄為準。
- `python3 -m pytest -q`:374 passed,10 skipped,7 warnings。
- `npm run build` in `frontend/launcher`:passed。
- `npm test -- --reporter=line` in `tests/e2e`:68 passed,4 skipped。
- `./scripts/smoke-test.sh http://localhost`:17 passed,0 failed。
- `./scripts/smoke-librechat.sh http://localhost`:13 passed,0 failed。
- `./installer/build.sh`:passed,產出新版 DMG。
- `npm audit --omit=dev` in `frontend/launcher` and `tests/e2e`:0 vulnerabilities。
- `git diff --check`:passed。
- DMG 抽查:只含 `/DMG/CompanyAI-source.tar.gz` 與 `/DMG/讀我.txt`;敏感檔匹配 0。
- DMG SHA-256:以最新 `reports/release/release-manifest-*.md` 記錄為準,避免將 SHA 寫死進 DMG source snapshot 造成自我引用 hash 循環。

## 現場交付注意

- 乾淨 Mac/公司目標機雙擊 GUI 安裝精靈全流程列為現場驗收項；目前已通過 AppleScript compile、DMG build、snapshot 抽查與本機 smoke。
- 安裝器尚未 Developer ID 簽名/Notarization,內部分發可用；若要對外或降低 Gatekeeper 提示,需補 Apple Developer ID 流程。
- LibreChat RAG/file_search 本機 E2E 已通:OpenAI 知識庫 Agent 呼叫 `file_search`,引用 `company-ai-rag-synthetic-20260428.txt` 回答主色 `#0F766E` 與 KPI；RAG adapter 需 LibreChat short-lived JWT,且 nginx 外部 `/api-accounting/rag/*` 回 403。
- Phase 1 試用前現場驗收包已補:`docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md`。交付前先跑 `./scripts/pre-pilot-verify.sh`,再依序完成乾淨 Mac/VM 安裝、去識別真實樣本 RAG 複跑、老闆 + Champion + 2 PM 的 4 人 pilot。

---

## 外部 AI 審計補充(2026-04-25 · 770/1000)

> 完整 30 findings + 10 評分維度詳見 `docs/EXTERNAL-AUDIT-2026-04-25.md`
> 委託 brief:`docs/AI-AUDIT-BRIEF-FORMAL-2026-04-25.md`

### 評分摘要

| 維度 | 分數 | 維度 | 分數 |
|---|---|---|---|
| UI/UX 可用性 | 70 | 後端可靠性 | 86 |
| 新手理解度 | 62 ← 最低 | 測試可信度 | 80 |
| 工作流閉環 | 78 | 部署交付可信度 | 72 |
| 功能完整性 | 84 | 文件完整度 | 88 ← 最高 |
| 前端可維護性 | 64 | ChatGPT 差異化 | 86 |

**總分 770 / 1000** · 落入「700-800 帶條件交付」區間。距 800 門檻差 30 分 · 修完必修 6 項可推到 820+。

### 交付前必修(2.5-3 天)

| # | 項目 | 對應 Finding | 估時 |
|---|---|---|---|
| 1 | Today composer 加附件拖放區 + file ribbon | F-03 | 已完成 |
| 2 | Sidebar 收斂(刪重複項 / 隱「智慧引擎」/ 4 項收進 Workspace) | F-01 / F-04 / F-06 | 已完成第一輪 |
| 3 | 首頁 hero H2 與 sidecar 文案修(「下一棒/棒」改一般用語) | F-10 / F-11 | 已完成 |
| 4 | 乾淨 Mac VM 跑完整 DMG 安裝 + smoke · 結果寫進 release manifest | F-08 | 待現場執行 |
| 5 | LibreChat RAG 上傳 + 引用實測 | F-24 | 本機 E2E 已完成 · 現場用去識別真實樣本複跑 |
| 6 | 補一條 PM happy-path E2E(composer → 上傳 → 存工作包 → 填 handoff → 複製) | §7.3#1 | 已完成 |

### 最大 3 個剩餘風險

1. **首頁複雜度仍是 ChatGPT 1.5x** · 新人第一週適應期可能負評
2. **乾淨 Mac 安裝沒驗 + 沒簽名** · IT 第一次裝可能卡 Gatekeeper / docker pull / npm run create-user
3. **乾淨 Mac/VM 安裝證據仍缺** · 本機 current-host rehearsal 不能取代乾淨機器驗收

### Go / No-Go 結論

- 是否可把目前 DMG 交公司 IT 安裝?**部分可以** · 前提是先在乾淨 macOS VM 跑驗 + 錄影 + 「右鍵開啟」說明
- 是否可讓 10 同仁開放試用?**不建議直接全員** · 建議分 3 phase:Phase 1(老闆+Champion+2 PM 共 4 人 1 週)→ Phase 2(再加設計+公關+會計共 8 人 1 週)→ Phase 3(全員)
- 是否需先做乾淨 Mac 安裝驗收?**強烈是**(F-08)

### Top 3 Blocker findings

| F | 標題 | 一句話 |
|---|---|---|
| F-08 | 乾淨 Mac DMG 全流程未在 release-verify 內覆蓋 | 對外交付前必補 · 防交付當天意外 |
| F-03 | 首頁 composer 不支援拖檔 | 違反「丟一件工作進來」承諾 |
| F-01 | sidebar 26 項過載 | 一般同仁第一眼被淹沒 |

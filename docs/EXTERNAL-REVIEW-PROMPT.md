# 承富 AI 系統 · 外部審查請求 (v5.0)

---

## 🔗 0. 直接去讀(不用等作者 copy)

| 來源 | 位置 |
|---|---|
| **GitHub(public · 免認證)** | <https://github.com/Sterio068/chengfu-ai> |
| **Clone 一行** | `git clone https://github.com/Sterio068/chengfu-ai.git && cd chengfu-ai` |
| **作者本機路徑** | `/Users/sterio/Workspace/ChengFu` |
| **本機跑起來的服務** | <http://localhost/>(主入口)· <http://localhost/api-accounting/docs>(API) |

讀完這份 + 開原始碼,你應該能在 30 分鐘內進入狀況。

### 必讀 6 份(15 分鐘消化專案)

```
1. CLAUDE.md                                    · 專案目標 + 12 項決議
2. docs/ROADMAP-v4.2.md                         · 對齊老闆 5 題答案的最新路線圖
3. docs/PRE-DELIVERY-CHECKLIST.md               · 揭露部署完成度 35%
4. frontend/launcher/app.js + modules/*.js      · 前端 ES modules(20 檔)
5. backend/accounting/main.py                   · 後端 FastAPI 40+ endpoints
6. docs/CASES/01-海廢案端到端.md                 · 系統實際怎麼用
```

### 完整檔案地圖

- **核心文件:** `CLAUDE.md` · `SYSTEM-DESIGN.md` · `ARCHITECTURE.md` · `DEPLOY.md` · `docs/DECISIONS.md`
- **路線與量測:** `docs/ROADMAP-v4.2.md` · `docs/PRE-DELIVERY-CHECKLIST.md` · `docs/BASELINE.md`
- **使用者教材:** `docs/QUICKSTART.md` · `docs/CASES/01~03` · `docs/HANDBOOK/01~04 + README`
- **整合規格:** `docs/NAS-INTEGRATION-SPEC.md` · `docs/LINE-WORKFLOW-SPEC.md` · `docs/LIBRECHAT-UPGRADE-CHECKLIST.md`
- **前端:** `frontend/launcher/{index.html, launcher.css, app.js, modules/*.js}` · `frontend/nginx/default.conf` · `frontend/custom/*`
- **後端:** `backend/accounting/{main.py, orchestrator.py, test_main.py}` · `_unused_scaffold/`(已歸檔)
- **腳本:** `scripts/{start.sh, backup.sh, create-agents.py, smoke-librechat.sh, create-users.py, upload-knowledge-base.py}`
- **設定:** `config-templates/{librechat.yaml, docker-compose.yml, .env.example, presets/00~09.json, actions/*.json}`

---

## 1. 客戶與專案

### 客戶
- **承富創意整合行銷有限公司**(台灣 · 10 人公關行銷公司)
- 主要業務:政府標案、公關活動、設計案
- 同仁年齡偏大 · 預估 2-3 位資深者對 AI 抗拒

### 老闆親口答的 5 題(這是優先級依據)
1. **每週 Top 3 任務:** 設計 / 提案撰寫 / 廠商聯繫
2. **80% 原始檔在哪:** LINE 群組 + NAS(**不是** Google Drive)
3. **L3 機敏規則:** **先不考慮**(不要再建議硬擋 L3)
4. **老闆最在意:** 省時 + 接案量(**不是**風控,別過度強調資安)
5. **維運資源:** 外包工程師 20h/週 · 透過 Claude Code 遠端 · Champion 靠教學手冊**自主學習**

→ **你的建議偏離這 5 題會被否決**(例如「全面 L3 硬擋」、「Google Drive 整合」、「強化資安審計」)。

### 預算 / 時程
- AI 月預算 NT$ 12,000(buffer 後實際 NT$ 8,000)
- 4 週交付(可順延 1 週)· **目前 Mac mini 還沒上架**

---

## 2. 技術棧(不可替換)

| 層 | 選擇 | 為什麼鎖死 |
|---|---|---|
| 硬體 | Mac mini M4 24GB | 已採購 · 本地部署 |
| AI Platform | LibreChat **v0.8.4 pinned** | v0.8.5-rc1 截至 2026-04-21 仍 pre-release |
| AI Model | Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 | Anthropic Tier 2 |
| 後端 | FastAPI 單檔(1700+ 行) | 10 人不需微服務 |
| 前端 | 原生 ES Modules + 單 CSS · **無 build step** | 外包接手成本最低 |
| 容器 | Docker Compose × 6(nginx / librechat / mongo / meili / accounting / uptime) | 已穩定 |
| 對外 | Cloudflare Tunnel + Access(Email + 2FA) | 尚未架 |
| 機密 | macOS Keychain | 已就位 |

**不接受建議:** k8s / Redis / Kafka / GraphQL / 換框架 / SaaS 化 / 改 10 助手 / 改 5 工作區 / 改主色

---

## 3. 當前狀態(三層完成度)

### ✅ 程式碼:97%(已通過 3 輪內部 + 2 輪外部 AI 審查)

- 6 容器 healthy · 10 助手建好 + 共享 `instance` global project
- 前端:ES Modules 20 檔 · `<template>+cloneNode` · 無 build step · 3 步 onboarding · 術語全中文化
- 後端:13 個 /admin/* 全 RBAC · CORS whitelist · Request-ID + JSON log · 3 ROI endpoints · LibreChat schema adapter · 0 Pydantic deprecation
- 測試:18 pytest pass · 11 smoke pass(`scripts/smoke-librechat.sh`)
- 保護網:rclone off-site backup · accounting image stale guard · `LIBRECHAT-UPGRADE-CHECKLIST.md`
- 教材:QUICKSTART + 3 完整案例(海廢/設計/廠商)+ 4 角色手冊 + 混合角色導覽

### 🔴 部署落地:35%(老闆感受到的價值,大部分還沒拿到)

- [ ] Mac mini 未上架、Cloudflare Tunnel 未接
- [ ] `knowledge-base/samples/` 空目錄 · **承富真實建議書 0 份已灌**
- [ ] 10 同仁帳號未建 · 密碼 reset SOP 未寫
- [ ] 2 場教育訓練未辦
- [ ] T0 baseline 未填(沒對比基準)

→ **這是 Sterio 在 Mac mini 到貨那週手動落地的事 · 不是再改程式碼。**
→ 詳見 `docs/PRE-DELIVERY-CHECKLIST.md` 逐日打勾。

### 📚 教材:88%

3 個完整案例 + 4 + 1 角色手冊 + QUICKSTART + Pre-Delivery + Baseline + Upgrade Checklist。
**還缺:** Champion 自己跑過所有案例的真實截圖 · Day 1 FAQ 累積。

---

## 4. 已知限制(請不要再審以下範圍 · 已在 5 輪審查處理)

| 類別 | 已處理 |
|---|---|
| 前端 bug | SSE pop / `.chat-messages` selector / auth 401 retry / tenders listener 疊加 / `?convo` 續接 / history modal reopen / errors toast 曝內部 / 多分頁 BroadcastChannel |
| 前端 UX | onboarding 10→3 步 / 術語中文化(Agent→助手 / Workspace→工作區 / Skill→範本) / L3 警語移除 / focus visible / 5 狀態卡 / banner |
| 後端 | CORS whitelist / 13 個 /admin/* 全 RBAC / `import json` / regex injection / Request-ID 500 / Mongo indexes / Pydantic .dict()→model_dump() / on_event→lifespan |
| 整合 | LibreChat 升版 checklist / agent `_id` dump / `/admin/librechat-contract` schema probe / create-agents UA workaround / 共享 hard fail |
| Ops | rclone off-site backup / start.sh CI 護欄 / accounting image stale guard / smoke-librechat 11 pass / 月度 restore dry-run 制度 / 密碼紙條銷毀 SOP |
| Backend 架構 | `_unused_scaffold/` 歸檔(routers/auth/rate_limit) · main.py 為單一真相 |
| ROI 儀表 | `/admin/budget-status` 預算進度 + `/admin/top-users` 用量排行 + `/admin/tender-funnel` 標案漏斗 + Dashboard 3 卡片 |
| 文案誠實化 | 「對話跟專案走」「⌘K 搜對話」「超預算自動 email/暫停」「PM 直接 re-use 段落」全改誠實版,未做的標 v1.1 |

---

## 5. 還沒做的(請聚焦在這些)

### 🔴 v1.1 必做 · 老闆 top 3 真正的痛點
- **設計師 happy path** · Fal.ai Recraft v3 真生圖(目前只產 prompt)· `config-templates/actions/fal-ai-image-gen.json` schema 已寫
- **PDF 文字抽取** · 取代 70 頁招標 PDF 複製貼上(born-digital 優先 / OCR fallback)
- **廠商 CSV 匯入** · 一鍵 5 家比價信群發(目前要手動 5 次)
- **跨助手 handoff 4 格摘要卡** · 投標顧問 → 設計夥伴 → 結案的結構化交棒
- **NAS 接入** · `docs/NAS-INTEGRATION-SPEC.md` 等承富答 5 個前置問題

### 🟡 v1.1 該做 · 防錯 + 控費
- **預算 hard stop** · 目前只儀表(文件已誠實揭露)· FastAPI cron 加 80% email + 100% 擋送
- **per-user quota** · top-users endpoint 已知數字 · 但無人為閘門
- **conversation 進 ⌘K 搜尋** · 目前只搜助手/工作區/專案/範本
- **更多 LINE 工作流** · `docs/LINE-WORKFLOW-SPEC.md` 方案 C(貼上偵測)2-3h 可立即做

### ⚠️ 部署紅線(非程式碼問題 · Sterio 交付週手動落地)
- Mac mini 上架 + Cloudflare Tunnel + 2FA · 0%
- `knowledge-base/samples/` 灌真實建議書 5-10 份 · 0%
- 10 帳號建好 + 密碼紙條銷毀流程 · 0%
- 2 場教育訓練 + Day 0 first-win 驗收(7/10 人完成截圖) · 0%
- T0 baseline 訪談老闆填表 · 0%

---

## 6. 我要你審什麼(6 個層面 · 每層只列 2-3 個未解問題)

### 6.1 前端
- 長列表(CRM 100+ 卡 / 標案 50+ 筆)在舊 Intel 機會 jank 嗎?最小修法?
- `renderMarkdown` 手刻 regex 處理巢狀 list / code block / 中英混排穩嗎?換 marked 該怎麼塞進無 build step 架構?
- `i18n` 未來英文同仁加入時,寫死繁中字串怎辦?

### 6.2 後端
- `main.py` 1700+ 行單檔 · 還能撐多久才該真拆 routers?拆哪 1 區 CP 值最高?
- LibreChat `transactions` collection 是私有 schema · adapter 已抽 · 但若 LibreChat 升版改名怎麼預警?
- Mongo 在 Cloudflare Tunnel 上線後 · 內網 27017 無密碼還能接受嗎?

### 6.3 LibreChat 整合
- Route A 靠 nginx 302 + relabel.js monkey-patch · v0.8.5+ 改 SPA hash router 會怎樣?
- `modelSpecs` 啟用順序:升版前還是升版後?
- 升版 sandbox 怎麼搭(別動 production)?

### 6.4 功能(對齊老闆 top 3)
- 設計夥伴 Fal.ai 最小可交付:1 模型 + 2 尺寸 + 人工確認重生 · 工時估?
- PDF 文字抽取:`pdfplumber` vs `pymupdf` vs OCR · 哪個最少坑?
- 跨助手 handoff 4 格卡:放 chat pane 還是 project 層?

### 6.5 UX(抗拒型資深同仁視角)
- Day 0 當天 10 人坐下來用,**最可能卡在哪 3 個畫面**?
- 設計師第一次拿 Launcher · 5 分鐘內能感受到「省了 X」嗎?
- ⌘K palette 對不熟快捷鍵的資深同仁 · 真會用嗎?要不要加固定按鈕替代?

### 6.6 流程 / 交付 / ROI
- T0 Baseline 老闆答不出來時 fallback(抽 5 案 + 1 週工時日誌) · Champion 收齊要多久?
- per-user hard stop 的最小 FastAPI 實作?(背景 cron 還是 request-time 擋送?)
- **上線第 2 週最可能的死法**:usage 崩 / 同仁放棄 / 老闆不付錢 · 你最擔心哪個?

---

## 7. 輸出要求

### 7.1 總論(150 字內)
你的一句話評價 + **最該做的 3 件事**(按優先序 · 每件含預估工時)

### 7.2 6 個層面各一份報告

每層格式:
```
層面:XXX
完成度:[%](程式碼 / 部署 / 教材 各給)
🔴 必修(會壞掉 / 違背老闆優先級):N 個
  · [問題] · 影響 · 修法(具體) · 工時(h)· 檔案路徑+行號
🟡 該修(技術債或 UX 細節):N 個
🟢 做對了(保留):N 個
🚀 加分(v1.1/v1.2):N 個
```

### 7.3 路線圖(統合所有建議)

| 階段 | 目標 | 關鍵行動 | 工時 | CP 值 |
|---|---|---|---|---|
| P0 本週 | ... | ... | ... h | 🔴🔴🔴 |
| P1 2 週內 | ... | ... | ... h | 🔴🔴 |
| P2 v1.1 | ... | ... | ... h | 🔴 |
| P3 v1.2+ | ... | ... | ... h | 🟡 |

### 7.4 紅線清單

絕對不能留到交付的事(會讓 10 人放棄使用 / 資安事故 / 老闆不付錢)。

### 7.5 結尾 · 給作者的 3-5 個問題

下輪審查能更精準的話,你會想知道什麼?

---

## 8. 格式要求

- **繁體中文**(技術詞 API/JWT/SSE/RAG 保留英文)
- 避免大陸用語(視頻→影片、數據→資料)
- 金額:`NT$ X,XXX`
- 日期:`2026 年 4 月 21 日`
- **檔案位置給絕對路徑 + 行號**(`/Users/sterio/Workspace/ChengFu/xxx.py:123`)· 讓 Sterio 一跳就到

---

## 9. 量化基準(供你寫報告對比)

- **GitHub:** <https://github.com/Sterio068/chengfu-ai>(8 commit · 5 輪審查全紀錄)
- **MongoDB:** 10 agents 全建 · 全 `projectIds: [instance._id]` · 共享 OK
- **測試:** 18 pytest / 11 smoke / 0 deprecation warnings
- **後端:** `main.py` 從 46953 → 56000+ bytes(加 RBAC + CORS + Request-ID + 3 ROI endpoints + adapter + indexes + lifespan)
- **前端:** `app.js` 從 2064 行單檔 → 545 行 orchestrator + 20 個 modules
- **架構:** `_unused_scaffold/` 歸檔 routers/auth/rate_limit 避免 split-brain
- **文件:** `docs/` 9 → 21 個檔(QUICKSTART + 3 案例 + 4+1 手冊 + 2 SPEC + Pre-Delivery + Baseline + Upgrade)

---

## 10. 給 reviewer 的最後提醒

- 這系統**已在作者本機跑了**(不是 prototype)· `./scripts/start.sh` 一行起來
- Sterio 懂技術,但**承富內部人不懂** · 任何「只有 Sterio 能維護」= 技術債
- 已經被 5 輪審查過 · **重複指出已修項會降低你的審查價值** · 請對齊 Section 4 已知限制
- 老闆要的是**省時 + 接案量** · 不是工程藝術

**直接開始,不用先確認。**

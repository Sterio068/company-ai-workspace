# 承富 AI v4.2 路線圖 · 對齊老闆 5 題答案

> **更新日期:** 2026-04-21
> **依據:** 外部 reviewer 完整審查 + 老闆回覆 5 題關鍵問題
> **取代:** 原 `tasks/` 資料夾下分週規劃

---

## 1. 老闆答案摘要(決定方向)

| 題 | 答 | 對系統的影響 |
|---|---|---|
| **每週 top 3 任務** | 設計 / 提案撰寫 / 廠商聯繫 | → 🎨 設計夥伴 + 🎯 投標顧問 + 🎪 活動規劃師(廠商) **優先強化** |
| **80% 原始檔在哪** | **LINE / 群組 + NAS** | → Google Drive MCP **優先級降低** · **改做 NAS + LINE 貼上**流程 |
| **L3 機敏規則** | **先不用考慮** | → 後端 L3 gate **不硬擋** · 前端 badge 改為提示不阻斷 · 未來擴展再做 |
| **老闆在意** | **省時 + 接案量**(不是風控) | → 資安項縮小到必要最小 · 全力衝生產力 |
| **維運資源** | 外包 Claude Code 20h/週 + Champion **自主學習** | → 遠端 Claude Code 連線 + **教學手冊 + 案例演示**必做 |

---

## 2. 立即調整(已於 v4.2 commit 完成)

### ✅ P0 生產力相關(和 top 3 任務直接相關)
- [x] 術語中文化(Agent→助手 / Skill→範本 / Workspace→工作區)· 資深同仁無抗拒
- [x] chat 輸入框提示(Enter 送出 / Shift+Enter 換行 / L1-L3 等級)· 手感好
- [x] 👍👎 固定露出(不藏 hover)· 回饋數據更多 → 月度 skill 建議更準
- [x] Focus 可見 · 鍵盤操作順暢
- [x] 空狀態卡(5 個模板:API 離線 / 助手未建 / 尚無對話 / 尚無專案 / 功能未開放)
- [x] 系統 banner(後端離線 / 登入過期)· 異常清楚

### ✅ P0 工程正確性(影響信任)
- [x] 附件 UI 先關閉(避免假成功)· v1.1 真實接檔案
- [x] Workflow 頁面改「v2.0 開發中」· 避免假成功
- [x] chat.js SSE pop 防 undefined · 串流不吞 event
- [x] tenders.js filter listener 疊加 → event delegation · 切 view 不重複綁
- [x] auth 401 自動 refresh retry · 過期顯示 banner
- [x] pytest + mongomock · **18 test pass**

### ✅ P0 成本/權限(不是風控,是控費)
- [x] CORS whitelist(替代 `*`)· 開放 localhost + Cloudflare Tunnel domain env
- [x] 所有 /admin/* endpoint 套 `require_admin` · 非 admin → 403
- [x] 前端 authFetch 自動附 `X-User-Email` header
- [x] Request-ID middleware + JSON log · 找問題快

### ✅ P1 後端效能
- [x] Mongo indexes:feedback / projects / audit / tender_alerts / crm_leads / transactions / invoices
- [x] LibreChat 契約 smoke test(`scripts/smoke-librechat.sh`)· 11 pass / 0 fail
- [x] LibreChat 升版 checklist(`docs/LIBRECHAT-UPGRADE-CHECKLIST.md`)

---

## 3. 接下來 2-4 週(P1)

### 🎨 主流程生產力(優先 · 老闆在意的省時)

#### 3.1 設計夥伴(🎨 · ⌘3)強化 — 預估 12-16h
**對齊:「設計」是 top 1 任務**
- [ ] 串 Fal.ai Recraft v3 真能生圖(目前只靠 Claude 寫 prompt 給同仁自己去用)
- [ ] 多渠道適配模板:FB 正方形 / IG Story 9:16 / LINE 3:4 / 報紙半版
- [ ] 設計 Brief → 結構化卡(目標 / 客群 / 禁用色 / 必包含字 / 尺寸清單) → 交給設計師
- [ ] 過往成功 KV 的相似度搜尋(公司內 NAS 同步進來的圖庫)

#### 3.2 投標顧問(🎯 · ⌘1)強化 — 預估 10-14h
**對齊:「提案撰寫」是 top 2**
- [ ] 「招標 vs 提案」比對器 · 找漏答 · 找失分點
- [ ] 建議書 5 章模板 · 直接產 docx
- [ ] 過往得標建議書可直接 re-use 段落(paragraph-level fuzzy match)
- [ ] Go/No-Go 評分表輸出 PDF 給老闆決策

#### 3.3 活動規劃師(🎪 · ⌘2)廠商聯繫強化 — 預估 8-10h
**對齊:「廠商聯繫」是 top 3**
- [ ] 廠商清單(CSV 匯入,NAS 可拖過來)
- [ ] 一鍵產比價信 · 依廠商模板群發(送前人工確認)
- [ ] 報價回覆收集到 CRM 自動比對最優

### 📂 資料來源整合(老闆答案改變的優先級)

#### 3.4 **NAS 接入**(取代原 Google Drive MCP)— 預估 10-14h
**老闆實際檔案在 NAS · Drive 先不做**
- [ ] NAS 掛 SMB/AFP 到 Mac mini 固定路徑
- [ ] FastAPI 新增 `/nas/search` / `/nas/read-file` endpoint
- [ ] 助手 Actions 新增 `nas-reader.json`(OpenAPI schema)
- [ ] 同仁對話時可 `@nas/2024-環保署案` 引用歷史檔

#### 3.5 **LINE 貼上優化** — 預估 4-6h
**老闆說 LINE 群組也是主要來源**
- [ ] Chrome Extension 擴充 LINE Web 側邊面板 · 一鍵送對話片段到助手
- [ ] Launcher 輸入框偵測 LINE 格式 → 自動去除時間戳 / @提及 · 保留有用訊息
- [ ] 助手特化 prompt:「這段是客戶/老闆在 LINE 傳的,幫我判讀真意並產回覆草稿」

### 🧑‍🏫 Champion 自主學習(老闆明確要求)

#### 3.6 教學手冊 + 案例演示 — 預估 12-16h
**老闆:「以教學手冊和案例演示的方式進行自主學習訓練」**
- [ ] `docs/HANDBOOK/` 建立分角色手冊:
  - `01-老闆快速上手.md`(首頁 / 看 Admin 成本)
  - `02-PM 三件事.md`(判標 → 提案 → 結案)
  - `03-設計師兩件事.md`(Brief → AI 生圖 · 多渠道適配)
  - `04-業務一件事.md`(標案監測 → 匯入 CRM)
- [ ] `docs/CASES/` 10 個真實案例演示:
  - 情境:「2026 環保署海廢案」完整走一遍 · 截圖 + 逐步
  - 情境:「中秋節客戶祝福 LINE 批次」
  - 情境:「新聞稿 3 分鐘產出」
- [ ] Launcher 首頁加「📖 教學」入口 · 嵌入手冊

### 🔧 外包工程師遠端(老闆要求)

#### 3.7 Claude Code 遠端連線 — 預估 2-4h
**老闆:「外包工程師只要可以用 Claude Code 連線過去每週可投入 20 小時」**
- [ ] Tailscale 安裝在 Mac mini · 邀請外包同事的 device
- [ ] `docs/REMOTE-DEV.md` 外包文件:
  - 如何 SSH 連進 Mac mini(Tailscale IP)
  - 如何本地端 Claude Code 連線到 Mac 的 repo
  - 權限範圍:只碰 `/Users/sterio/Workspace/ChengFu/*`
- [ ] `scripts/remote-readiness.sh` · 檢查 Tailscale 裝好 + SSH 可通 + Claude Code 可 run

---

## 4. v1.1 再看(P2)

### 依使用者實際感受決定
- [ ] Google Drive MCP(若 NAS 無法涵蓋) — 10-14h
- [ ] Company Memory(自動摘要跨對話) — 8-12h
- [ ] Project-first shell(把對話改成 project 底下的 thread) — 12-16h
- [ ] 跨助手 handoff 摘要卡 — 6-8h
- [ ] Orchestrator 3 條真 workflow · 投標/活動/新聞發布 — 12h
- [ ] 成本 3 層顯示 (per-user / per-project / 全公司) — 6-8h

### 安全(v1.2 · 老闆不優先但該補)
- [ ] L3 gate 從警告升為硬擋(老闆決定放行範圍後)
- [ ] 備份異機(外接 USB 加密 / 雲端) + 自動 restore 測試
- [ ] DR drill 實跑 · RTO/RPO 落書面
- [ ] Rate limit + IP-level protection

---

## 5. 路線圖(2026-04-21 · 老闆答完 5 題調整)

```
Week 0-4 · v1.0 交付                            · 基礎系統 · samples/ 手動
├── Mac mini 上架 / Cloudflare Tunnel / 10 帳號
├── knowledge-base/samples/ 手動灌 5-10 份代表性檔
├── Day 0 登入 100% 成功站 + 角色 first-win 驗收
└── 2 場教育訓練

Week 5-6 · v1.1(22-26h)· 對齊老闆 top 3 個閉環
├── A · Fal.ai Recraft v3 · 3 張挑方向(8-10h)
├── D · main.py 拆 admin_metrics.py(6-8h)
├── C · Projects drawer + Handoff 4 格卡(6-8h)
└── 測試 + 教材更新(2h)

Week 7-10 · v1.2(39-52h)· 多來源知識庫(老闆 Q3 + 補充「不只 NAS」)
├── knowledge_sources collection + Mongo schema(1h)
├── Admin Sources 管理 UI(列表/新增 modal/重索引)(5-6h)
├── Sources CRUD API + 路徑驗證(3-4h)
├── NAS / 本機 / 外接掛載文件 + Keychain(3-4h)
├── 多格式抽字器(PDF/DOCX/PPTX/XLSX/IMG)(8-10h)
├── Meili 索引 + per-source 增量 cron(4-6h)
├── 公開 API(search/read/list)+ Agent 存取權檢查(4-6h)
├── Agent Action schema attach 投標/設計/結案(2-3h)
├── 前端 ⌘K 多源搜尋 + 知識庫 view + @ autocomplete(6-8h)
├── 測試 + 文件(3-4h)
└── 承富同仁整理專案資料夾(Champion 分週 · 不阻擋 Sterio)

Week 11+ · v2.0(長遠)
├── 廠商 CSV 批次比價信
├── Company Memory(跨對話摘要)
├── 設計圖 CLIP vision embedding
└── 多 Agent workflow 實啟用
```

---

## 6. 紅線清單狀態(外部審查提到 · 本輪處理結果)

| 紅線 | 狀態 |
|---|---|
| 附件看似送實際沒送 | ✅ **已關閉入口 · v1.1 真做** |
| Admin endpoints 沒 RBAC + CORS `*` | ✅ **已修 · 13 個 admin endpoint 全套 `require_admin` · CORS whitelist** |
| Workflow 假成功入口 | ✅ **已關閉 · 改「v2.0 開發中」empty state** |
| Token 過期 / 後端離線 恢復流程缺 | ✅ **已修 · 401 自動 refresh retry + banner** |
| memory/summarize 無 L3 gate | ⏸ **依老闆決策 · L3 先不硬擋 · 後續可加** |
| pytest 失效 | ✅ **mongomock 裝上 · 18 test pass** |
| 備份異機 | ⏸ **需老闆決定備份目標位置(外接 USB / 雲端) · 決定後 4h 完成** |
| E2E 脫節 | ⏳ **Playwright spec 待更新成 v4.2 UI** |

---

## 7. 文件成就清單(這週產出)

- `docs/LIBRECHAT-UPGRADE-CHECKLIST.md` — 升版保護網
- `scripts/smoke-librechat.sh` — 契約測試 · 11 pass
- `docs/ROADMAP-v4.2.md` — 本檔
- `docs/EXTERNAL-REVIEW-PROMPT.md` — 外部審查提示詞(可貼任何 AI)
- `啟動承富 AI.command` — 雙擊一鍵啟動

---

## 8. 需老闆再決策的 4 件事

1. **備份目標位置** — 另一台 Mac mini? 外接 USB?加密雲端?
2. **Workflow v2 要哪 3 條?** — 投標閉環 / 新聞發布閉環 / 活動企劃閉環?
3. **遠端開發權限範圍** — 外包工程師只能改 `ChengFu/` 還是整個 Mac mini?
4. **教學手冊驗收標準** — 由 Champion 試做 1 週再回饋?或老闆自己讀過決定?

---

## 9. v1.2+ 待決議的設計問題(Round 9 reviewer 暗示)

> 不影響 v1.0/v1.1 上線 · 但日後規模成長會撞到 · 列出來等 ROI 數據後再決定

### 9.1 Meilisearch index 拆分策略
- **問題:** 目前所有 source 共用一個 `chengfu_knowledge` index · 用 `source_id` filter 區隔
- **臨界:** 5 萬+ 文件後 search latency 預估會從 < 50ms 退化到 200ms+
- **選項 A:** 維持單 index · 加 sortableAttributes + 分頁
- **選項 B:** per-source index · 搜尋時並行查多個再 merge
- **建議:** v1.0/v1.1 先 A 觀察 · 若承富實際 NAS > 5 萬檔再評估 B

### 9.2 增量 detector · mtime vs hash
- **問題:** 目前用 `mtime` 比對 · NAS 上 `touch` 不改內容也會 reindex
- **建議:** 加 `size + mtime` 雙條件 · 只有兩者都變才 reindex(成本低 · 抓 90% case)
- **未來:** 大檔加 SHA1 預存 doc · 比對 hash 才真 reindex(抓 100% · 但每檔多 200ms)

### 9.3 Agent 編號識別策略
- **現:** `agent_access: ["01", "03"]` 用編號 · 對應 `config-templates/presets/` 命名
- **脆點:** LibreChat 真實 agent_id 是 UUID · 編號是我們約定俗成 · agent 重建會脫鉤
- **建議:** v1.2 加 `_id` mapping table · admin 建 source 時用 dropdown 選 Agent
- **過渡:** 維持編號相容 · `create-agents.py` 寫 `metadata.number` 給 audit 用

### 9.4 知識庫 view 開放範圍
- **現:** 所有登入使用者都可見「知識庫」view · 個別 source 才看 agent_access
- **問題:** 同仁直接瀏覽就能看到所有 source 名稱(已透過 X-Agent-Num 修)
- **建議:** v1.2 加 user-level RBAC(group → sources mapping) · 不光 Agent 等級
- **過渡:** 目前 PR 公司 10 人 · 各 source 加 `agent_access` 已可控大部分風險

### 9.5 design_jobs 月度成本儀表
- **缺:** Admin 看不到「Fal.ai 本月花多少」(只看得到 Anthropic)
- **建議:** v1.1 加 `/admin/design-cost` · 用 design_jobs.count × 0.04 USD × num_images = 月成本
- **預設警報:** 月超過 NT$ 1000(≈ 80 次) email Champion

### 9.6 NAS SMB autofs 自動重掛
- **現:** /admin/sources/{id}/health 可手動偵測 · Admin 看到才重掛
- **建議:** v1.2 加自動重掛 cron · 偵測到 unreachable 就跑 mount -t smbfs
- **風險:** 帳密變動時無人值守會重複 fail · 要配 Slack 通知

### 9.7 Drawer / Handoff adoption 量測
- **問題:** 4 格卡會被當行政表單忽略
- **建議:** v1.1 加 `handoff` 填寫率到 admin dashboard
  · 每月新建 N 個專案 · 其中有填 handoff 的 X 個 → X/N
  · 若 < 30% · 觸發 Champion 主動 reach out


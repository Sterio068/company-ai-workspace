# 全系統整體優化計劃 · v1.7 / v1.8

日期:2026-04-28
依據:Architecture agent + NotebookLM agent 完整深度審計 + UI/a11y/Perf grep 驗證
範圍:本機正式交付 gate 通過(13/13)後 · 下一輪結構性優化(不修當下 ship-ready 的 v1.69+)
原則:**只計劃 · 不修 code** · 排序 priority + 預估工時 + 前置依賴

---

## 0. 量化現況

| 指標 | 實際 | 風險 |
|---|---:|---|
| `backend/accounting/main.py` | **951 行** | god-module · 32 routers + 18 lifespan index 區塊 + 自帶 endpoint |
| `frontend/launcher/launcher.css` | **6695 行** | 單檔 CSS · critical/non-critical 沒拆 · dark mode 散落 |
| `frontend/launcher/index.html` view 容器 | **17 個** | 比原宣稱 14 多 3 個 · cognitive load 過高 |
| `dist/app.<hash>.js` 主 bundle | **~340 KB** | 首屏載 · chunks 共 150 個 / 1.46 MB 等待 lazy import |
| `create_index` 散在 main.py | **55 處** | TTL / unique / compound 全混 · 改 retention 政策要 grep 55 處 |
| inline `onclick=` 殘留 | **48 處** | v1.69 規則只對新加 code · 歷史 view 仍是 inline handler |
| `setInterval` 散落 | **8 處** | refresh / poll / cleanup 各自 setInterval · 缺中央 lifecycle manager |
| `notebooklm.js` `aria-*` 數 | **1** · `role=` **0** | a11y 嚴重不足(對比 v1.69 user_mgmt.js 已含 aria-modal/labelledby/describedby) |
| docker-compose accounting env | **32** | 無 T0/T1/T2 分層 · 管理員無法分必要 vs 可選 |
| Action JSON | **7 個** | `internal-services` + `accounting-internal` 重複 7 endpoint · `openai-image-gen` + `fal-ai-image-gen` 該由 backend route |

---

## 1. 優先順序總覽

### 🔴 P0 · 在做白標化 / scaling / chat.js 拆檔之前要先補(架構債)

| # | 動作 | 工時 | enabler | 來源 |
|---|---|---:|---|---|
| P0-1 | **Tenant boundary** · 加 `tenant_id` 到 audit_col / projects / accounting_* / feedback · `get_db(tenant_id)` 抽象 · `_admin_allowlist` per-tenant | 24h | 多公司白標化(D-016 落實前提) | Architecture HIGH |
| P0-2 | **NotebookLM Agent ACL 漏洞修補** · `routers/notebooklm.py:638-682` agent endpoint 全 admin 身分繞過 owner 檢查 → 改用 `X-Acting-User` header 用該 user ACL | 6h | NotebookLM 安全 ship-ready | NotebookLM HIGH |
| P0-3 | **Anti-corruption layer · LibreChat collection** · `services/librechat_admin.py` 擴成 LibreChat read/write 唯一入口 + 啟動 schema probe(v0.8.5 fields exist · fail loud) | 16h | LibreChat v0.9 升版安全 + PDPA delete 不 silent break | Architecture HIGH |
| P0-4 | **Redis container + slowapi storage 切換** · `_AI_HEALTH_CACHE` 移 Redis SETEX · rate limiter `memory://` → redis | 8h | scaling 50 人 · 多 worker 配額正確 | Architecture HIGH |
| P0-5 | **NotebookLM stable hash 修穩** · `source_pack_renderer.py` datetime normalize 到 `.date()` · finance round 整數元 · 排除波動欄位 | 4h | dedup 真有效 · audit「pack 沒變」可信 | NotebookLM HIGH |

**P0 小計:58h** · 共 7-8 個工作天

---

### 🟡 P1 · 結構性收斂(不擋 ship · 但拖越久越貴)

| # | 動作 | 工時 | 收益 |
|---|---|---:|---|
| P1-1 | **main.py 拆 router** · 18 段 `create_index` 移 `infra/db_indexes.py` `apply_indexes(db)` · `report_frontend_error` / `access_urls` / `ai_providers_health` 移 `routers/system.py` · main.py 砍至 < 150 行 | 12h | 可讀性 + 升 LibreChat 不踩雷 |
| P1-2 | **Secret registry + .env tier 分層** · `secret_registry.py` 標 reader/writer/source · UI 只允改 reader=accounting · `.env.tiers.md` T0 必填 / T1 推薦 / T2 選配 + docker-compose 註解 OPTIONAL | 8h | 管理員自助運維 · 再無 OpenAI key drift |
| P1-3 | **Actions 收斂為 2 個** · 廢 `accounting-internal.json`(重複 7 endpoint)/ `openai-image-gen.json` / `fal-ai-image-gen.json` / `vision-ocr.json` · 只留 `internal-services.json` + `pcc-tender.json` · 生圖統一 `/design/generate` 由 backend 看 IMAGE_PROVIDER routing | 8h | Spec drift 消失 · Agent 不需自己挑 image provider |
| P1-4 | **NotebookLM sensitivity 真實落實** · 寫進 `notebooklm_source_packs.sensitivity` + audit_log · history 列表顯示等級徽章 · sync L3 強制 confirm modal 凸顯「正在送 L3 到 GCP」 | 6h | D-015「只標記不阻擋」不再是裝飾品 |
| P1-5 | **Retention registry** · `infra/retention_policy.py` 集中 `RETENTION = {...}` · `apply_indexes()` 套用 · stale TTL detect + drop+recreate(目前只 knowledge_audit 有) | 6h | 改 retention 政策不再 grep 17 處 |
| P1-6 | **NotebookLM agent action 透明性** · `created_by` 寫成 `agent:{actor}` · 前端顯示「由 Agent 建立 · 待你確認」 · sync endpoint require user 二次 confirm token | 4h | Agent 不再黑魔法地把資料送 GCP |
| P1-7 | **CSS 拆模組** · launcher.css 6695 行 → critical 600 行(sidebar / dashboard / typography)+ lazy(modal / chart / dock / mobile / view-specific) | 16h | 首屏 CSS 從 ~120KB 降至 ~25KB |
| P1-8 | **inline `onclick` 48 處清** · 全改 `data-act="..."` + delegated `addEventListener` · 同 v1.69 規則 | 12h | XSS 攻擊面收斂 · 一致性 |
| P1-9 | **NotebookLM build pack 上傳/同步 batch_id + resume** · 失敗中斷可恢復 · UI 顯示「N/M 個成功」非「成功 N 個」(可能假象) | 6h | NotebookLM 真生產可用 |

**P1 小計:78h** · 共 10 個工作天

---

### 🟢 P2 · UX / 可觀測性 / 開發者體驗

| # | 動作 | 工時 | 收益 |
|---|---|---:|---|
| P2-1 | **17 view IA 收斂為 8 view + 9 in-view tabs** · 重看 sidebar:dashboard/今日 / projects / 一個「工作」入口含 workflows + tenders + crm / 知識(knowledge + notebooklm) / 對外(public + meeting + media + social + site) / 中控 / 同仁 / 教學 | 16h | cognitive load 大降 · 老闆 5 分鐘上手目標真實達成 |
| P2-2 | **NotebookLM UI 兩塊分區** · `notebooklm.js:100-174` 建包跟上傳 project picker 分開 · 加邊框 + 不同底色 + heading「上傳檔案到 NotebookLM(獨立區塊)」 | 4h | 老闆不會選 A 專案後傳到 B |
| P2-3 | **NotebookLM a11y 補齊** · aria-modal / role=dialog / aria-labelledby / 對 stepCard 加 role=group · 鍵盤 Tab 順序 | 4h | 跟 v1.69 user_mgmt.js 標準一致 |
| P2-4 | **OpenAPI client 產生** · 啟用 `ECC_DOCS_ENABLED` · 用 `openapi-typescript` 產 `frontend/launcher/lib/api-types.ts` + `lib/api-client.js` | 8h | chat.js 拆檔 type-safe · 新 module 不再 grep 找 endpoint |
| P2-5 | **chat.js 拆檔** · 1300+ 行 → chat-streaming.js + chat-history.js + chat-handoff.js | 12h | 可維護性 · 已抽 chat-sanitize / chat-attachments |
| P2-6 | **app.js 拆檔成 views/*** · 2000+ 行 → views/today.js + views/projects.js + views/work-detail.js | 12h | 同 P2-5 · 模組化 |
| P2-7 | **Mongo collection 大小儀表** · admin dashboard 加「對話量 / collection 大小 / index 命中率」+ admin alert 條件(任 collection > 1GB) | 6h | 可觀測性 · 老闆看得到容量壓力 |
| P2-8 | **NotebookLM token 失敗區分** · `notebooklm_client.py` catch `httpx.HTTPStatusError` 區分 401/403/429/5xx · 各自回 `recovery_hint`(token_expired / quota_exceeded / api_down) | 4h | Agent 失敗時知道下一步 |
| P2-9 | **NotebookLM settings 寫前 token 驗證** · admin 貼 token 時 lightweight GET 驗證 · 失敗 412 不寫入 · 防貼錯到別公司 GCP | 2h | 設定階段不會把公司資料送錯地方 |
| P2-10 | **歷史 docs 白標化掃** · `公司 / CompanyAI` 殘留(內部 docs 還有)· grep + sed + 人工確認 · 不動 git history | 12h | 多公司可用真的可賣 |

**P2 小計:80h** · 共 10 個工作天

---

## 2. v1.7 sprint 建議(2 週)

| 週 | 主題 | 動作 |
|---|---|---|
| W1 (40h) | **NotebookLM ship-ready + 安全修補** | P0-2 (ACL) · P0-5 (hash) · P1-4 (sensitivity) · P1-6 (agent 透明) · P1-9 (batch/resume) · P2-2 (UI 分區) · P2-3 (a11y) · P2-8 (token 區分) · P2-9 (token 驗證) |
| W2 (40h) | **架構基礎打底** | P0-1 (tenant) · P0-3 (anti-corruption) · P0-4 (Redis) · P1-1 (main.py 拆) |

W1 完 → NotebookLM 可進真 pilot
W2 完 → 多公司白標化 / 50 人 scaling 有路徑

剩餘 P1-2 / P1-3 / P1-5 / P1-7 / P1-8 + P2 全留 v1.8 sprint(2 週)。

---

## 3. v1.8 sprint 建議(2 週)

| 週 | 主題 | 動作 |
|---|---|---|
| W1 (40h) | **設定 + Action 收斂 + retention** | P1-2 (secret registry) · P1-3 (action 收斂) · P1-5 (retention registry) · P2-7 (collection 儀表) |
| W2 (40h) | **前端模組化 + IA 收斂** | P1-7 (CSS 拆模組) · P1-8 (inline onclick 清) · P2-1 (17 view → 8 view) · P2-4 (OpenAPI client) |

剩 P2-5 / P2-6 / P2-10(chat.js 拆 + app.js 拆 + 歷史 docs 白標化)留 v1.9 收尾。

---

## 4. 不做的事(明確)

- **不改 React/Vue** · vanilla ES module 是 D-006 決議
- **不改 LibreChat upstream** · pin v0.8.5 · 升 v0.9 走 anti-corruption layer
- **不開 Workflow 全自動** · D-010 半自動 draft-first 不變
- **不一次清歷史 v1.0-v1.66 所有死碼** · YAGNI · 看到再清
- **不為 50 人前 build 100 人 scaling** · Redis 是合理門檻 · 不做 sharding

---

## 5. 風險登記

| 風險 | 機率 | 影響 | 緩解 |
|---|---|---|---|
| LibreChat v0.9 改 messages schema | 中 | PDPA 刪除 silent break | P0-3 anti-corruption layer 啟動時 schema probe fail-loud |
| 多公司同時上線資料混 | 高 | 資料外洩 / 合規違反 | P0-1 tenant_id 必先做 · 第 2 家公司前 hard gate |
| NotebookLM Enterprise quota 用爆 | 低 | 該公司 sync 失敗 | P2-8 token 失敗區分 + admin alert |
| 50 人並用 OpenAI 額度爆 | 中 | 對話 503 | 中控加 budget cap alert(已有 quota mgmt 但需 admin 看儀表) |

---

## 6. 度量標準

v1.7 結束驗收:
- [ ] NotebookLM agent endpoint 不再用 admin 身分(grep `is_admin=True` 應 = 0)
- [ ] 連續同步 10 次同一 pack · `_store_source_pack.deduped` 路徑命中率 ≥ 80%
- [ ] L3 sync 必跳 confirm modal(E2E 測)
- [ ] 加 2nd tenant 的 mock test 不污染 1st tenant data
- [ ] LibreChat container 重啟後 schema probe PASS
- [ ] Redis container up 且 rate limiter 切過去

v1.8 結束驗收:
- [ ] main.py < 150 行
- [ ] launcher.css 拆 ≥ 5 檔 · critical < 800 行
- [ ] sidebar view 數 ≤ 8 + in-view tabs
- [ ] inline `onclick=` grep 結果 = 0
- [ ] OpenAPI client `lib/api-types.ts` exists 且 chat.js 有 import

---

## 7. 不在這份計劃但仍重要的 ship 前最後 Gate(現場)

(複製自 `docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md` · v1.7 開工前必先過完)

1. 乾淨 Mac/VM DMG 首裝錄影
2. 真 NotebookLM Enterprise token 跑建立 notebook / 上傳單檔 / 同步資料包
3. RAG/file_search 在乾淨環境補截圖證據
4. 4 人 Phase 1 pilot:老闆 + Champion + 2 PM
5. nginx X-User-Email 強制覆寫 smoke 通過

這些是「V0 真上線」前提 · 跟 v1.7 / v1.8 結構性優化平行做不衝突。

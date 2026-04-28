# 企業 AI v1.1 · 現有功能強化 / 優化建議

> **範圍:** 17 個 ROADMAP 外的盲點 · 按嚴重度排
> **掃描:** 11 router + main.py + 25 前端 module + 7 cron + docker-compose + nginx + tests
> **總工時:** ~18 小時(不含測試)
> **互補:** v1.2 FEATURE-PROPOSALS(8 新功能)在另一份 doc · 本份只講「現有強化」

---

## 🔴 紅線類(3 項 · 2.5h)· 必修

### 1. `/feedback` list + stats 無 pagination(0.5h)
**file:** `routers/feedback.py:61, 85` · limit=100 固定 · 無 `skip`/`page`
**影響:** 爬蟲發 `?limit=10000` · memory spike · 10 人 × 50 feedback/月 = 6k doc/年
**修:** 加 skip/page · 最大 500 · 用 Mongo projection 只撈 `{verdict, agent_name, created_at}`

### 2. `/crm/leads` + `/crm/stats` 無 limit · full-scan(1h)
**file:** `routers/crm.py:78, 164-190`
**問題:** stats 全撈 `db.crm_leads` Python for-loop 加總 · 100 leads × 10 req/min × 8h = 48k full scan/日
**影響:** 尖峰 memory +100MB · ROI reporting 延遲
**修:** leads 加 limit=500 · stats 改 Mongo `$group` aggregate

### 3. 前端 addEventListener 未 cleanup · memory leak(1h)
**file:** `frontend/launcher/modules/knowledge.js:59,94,302,328,331,368,470` (8 處)
**問題:** modal 開關 10 次 = 80 個重複 click handler · 同一按鈕觸發 10 次
**影響:** 用戶多次操作後 UI 反應怪異
**修:** 用 `{ once: true }` 或 event delegation root-level + 提取 cleanup

---

## 🟠 資料膨脹 / 合規(3 項 · 2.5h)

### 4. `knowledge_audit` TTL index 可能沒生效(1h)
**file:** `main.py:128-135`
**問題:** `try/except` 靜默過 · 知識庫一年讀 50k 次 · 全留
**影響:** 月 +4GB 存儲 · query 變慢(無 TTL index · full scan · 3 個月爆)
**修:** drop & recreate index · fail-loud · 或外移到獨立 collection

### 5. `/admin/audit-log` 無 pagination(0.5h)
**file:** `routers/admin.py:242`
**問題:** admin 頁 refresh 一秒 5 次 = 500 doc 掃描/秒 · 一年百萬條
**影響:** admin 頁 +200ms latency
**修:** 加 skip/page/limit + start_date/end_date filter

### 6. Settings 散落 main.py · 無集中 config.py(1h)
**file:** `main.py:582-586` · `routers/admin.py` lazy 各處
**問題:** `QUOTA_MODE`, `_USD_TO_NTD`, `_MONTHLY_BUDGET_NTD` 等 7 個 · 改一個 grep 全檔
**影響:** v1.2 加 rate limit 設定 · 現已有 2 處相同常數 · 改錯一處 prod 爆
**修:** 抽 `backend/accounting/config.py` dataclass + validation · main.py import once

---

## 🟡 效能類(4 項 · 5.5h)

### 7. Accounting list endpoints 無 pagination(1.5h)
**file:** `routers/accounting.py:165, 209`
**問題:** `/transactions` limit=10 hardcoded · `/accounts` 完全無 limit · 1 年 50k txn = O(N)
**影響:** 月末 PnL 報表花 500ms 轉圖表(該 100ms)
**修:** skip/limit query params + /reports/aging 加 date range filter

### 8. 前端 25 module 啟動全 import · 大模組該 lazy(2h)
**file:** `frontend/launcher/app.js`(進入點)
**問題:** knowledge.js (60KB) + design.js (40KB) 使用率 < 20% · 每頁浪費 100KB
**影響:** 3G 網路首屏 +2s · mobile 跳出率 +15%
**修:** 動態 import · 點知識庫時才 `await import('./knowledge.js')`

### 9. `/admin/cost` + `/admin/adoption` Python for-loop(1.5h)
**file:** `routers/admin.py:448-503`
**問題:** 迴圈內 find · N 個月份 = N 次 DB roundtrip
**影響:** 月度成本報表 +300ms
**修:** 改 Mongo pipeline `[$match, $group, $sort]`

### 10. frontend `/knowledge/search` 無 AbortController(0.5h)
**file:** `frontend/launcher/modules/knowledge.js:331`
**問題:** 打字快時舊 request 仍載入 · network 慢時結果順序亂
**影響:** UX 困惑 · 搜尋結果與輸入不符
**修:** 加 AbortController · 新 request 前 abort 舊的

---

## 🟢 維運 / UX 類(4 項 · 4h)

### 11. `/admin/monthly-report` dict merge 無 validation(1h)
**file:** `routers/admin.py:378-410`
**問題:** 5 個 dict 手工 `{...}` · 某 key 消失無人知
**影響:** 月底 JSON 遺漏 field · launcher 前端白屏
**修:** Pydantic `MonthlyReportData` validate · 各 service 回 typed dict

### 12. Docker 無容器 resource limit(0.5h)
**file:** `config-templates/docker-compose.yml`
**問題:** accounting 無 `limits: {memory: 1G, cpus: 2}`
**影響:** 1 個爛 query 吃滿 RAM · OOM kill LibreChat / nginx
**修:** 加 `resources.limits` + `requests`

### 13. nginx `/api-accounting/*` 無 rate limit(0.5h)
**file:** `frontend/nginx/default.conf`
**問題:** 只 `/admin/email/send` 有 20/hour · 其他 endpoint 無全域防禦
**影響:** 攻擊 1000 req/s 直接拖垮 Mongo
**修:** `limit_req_zone $binary_remote_addr zone=api_limit:10m rate=50r/s` + `limit_req zone=api_limit`

### 14. Cron 無 notify on success(0.5h)
**file:** `scripts/daily-digest.py:92-120`
**問題:** 只 notify on failure · success silent · 管理員看不出漏跑
**影響:** 5 成功 + 1 失敗(網路抖動) · admin 找不出哪天漏
**修:** 加 success webhook · return code 驗證 · 或 `X-Company-AI-Cron-Success` header

---

## 🟢 測試 / 監控類(3 項 · 5h)

### 15. `test_main.py` 1072 行 · 拆 + 加 E2E / load test(3h)
**file:** `backend/accounting/test_main.py`
**問題:** 全 unit · 無 auth flow E2E · 無 load test
**影響:** v1.3 改 auth 規則 · 無人驗「10 人同時不爆」
**修:** 拆 `tests/{unit,integration,load}/` + pytest-load + concurrent scenario

### 16. nginx log 無 rotation(0.5h)
**file:** `frontend/nginx/default.conf:21`
**問題:** `company_ai.{access,error}.log` 無 logrotate
**影響:** 3 個月 disk full 系統掛
**修:** `/etc/logrotate.d/company-ai-nginx` daily rotate + 90 天保留

### 17. Scripts 假資料無 shared fixture(1.5h)
**file:** `scripts/{create-users,seed-demo-data,upload-knowledge-base}.py`
**問題:** 各自造 User / Project mock · 改一個欄位 3 處都要改
**影響:** v1.2 加 `user.department` · 3 script 遺漏
**修:** 抽 `scripts/fixtures.py` · Faker + `create_fake_*()` 共用

---

## 📊 優先度總表

| # | 項目 | 類別 | 工時 | ROI |
|---|---|---|---|---|
| 2 | CRM pagination + stats aggregate | 🔴 紅線 | 1h | ⭐⭐⭐⭐⭐ |
| 1 | Feedback pagination | 🔴 紅線 | 0.5h | ⭐⭐⭐⭐⭐ |
| 3 | Frontend event listener leak | 🔴 紅線 | 1h | ⭐⭐⭐⭐⭐ |
| 13 | nginx api-accounting rate limit | 🟢 維運 | 0.5h | ⭐⭐⭐⭐⭐ |
| 14 | Cron notify on success | 🟢 維運 | 0.5h | ⭐⭐⭐⭐ |
| 12 | Docker resource limit | 🟢 維運 | 0.5h | ⭐⭐⭐⭐ |
| 16 | nginx logrotate | 🟢 維運 | 0.5h | ⭐⭐⭐⭐ |
| 4 | knowledge_audit TTL | 🟠 合規 | 1h | ⭐⭐⭐⭐ |
| 5 | Admin audit-log pagination | 🟠 合規 | 0.5h | ⭐⭐⭐ |
| 10 | Frontend AbortController | 🟡 效能 | 0.5h | ⭐⭐⭐ |
| 6 | Config 集中 dataclass | 🟠 合規 | 1h | ⭐⭐⭐ |
| 7 | Accounting pagination | 🟡 效能 | 1.5h | ⭐⭐⭐ |
| 9 | Admin cost/adoption aggregate | 🟡 效能 | 1.5h | ⭐⭐⭐ |
| 11 | Monthly report Pydantic | 🟢 UX | 1h | ⭐⭐ |
| 8 | Frontend lazy import | 🟡 效能 | 2h | ⭐⭐ |
| 17 | Scripts shared fixtures | 🟢 測試 | 1.5h | ⭐⭐ |
| 15 | Test 檔拆 + E2E + load | 🟢 測試 | 3h | ⭐⭐ |

**總計:** 18 小時 · 分 3 個 sprint

---

## 🚀 建議 Sprint 規劃(接 v1.1 release)

### Sprint 1(3h · 立刻)· 安全 + 基礎維運
- R14#1 + #2 + #3 紅線全修(pagination × 2 + event leak)
- R14#12 + #13 docker limit + nginx rate limit
- R14#16 nginx logrotate

**產出:** v1.1.1(pagination 穩 / rate limit 守 / 日誌不爆)

### Sprint 2(6.5h · 本週)· 效能 + 合規
- R14#4 knowledge_audit TTL(防爆)
- R14#5 admin audit-log pagination
- R14#6 config.py 抽 dataclass(改設定不用 grep 全檔)
- R14#7 accounting list pagination
- R14#9 admin cost/adoption aggregate
- R14#10 frontend AbortController
- R14#14 cron success notify

**產出:** v1.2.0(大量資料時仍穩 · 設定好維護 · 成本報表快)

### Sprint 3(8h · 下週)· 進階 / 測試
- R14#8 frontend lazy import(首屏 -2s)
- R14#11 monthly report Pydantic validate
- R14#15 test 檔拆 + E2E auth + load test
- R14#17 scripts fixtures.py

**產出:** v1.2.1(測試覆蓋足 + UX 最佳化)

---

## 📋 v1.2 做什麼?兩條路

> **路 A · 新功能導向(FEATURE-PROPOSALS-v1.2.md):** #1 + #2 + #3 共 3.5 天
> → 老闆看得到新價值 · 本公司業務拿新工具 · 月省 67h(會議速記)
>
> **路 B · 現有強化導向(本檔):** Sprint 1 + 2 共 9.5h ≈ 1.5 天
> → 使用者感覺「變穩了」· 維運更輕鬆 · 但老闆看不到「新」
>
> **推薦混合:**
> - Day 1:Sprint 1(3h 維運基礎)+ Feature #3 PII(1 天)
> - Day 2:Feature #1 會議速記(1 天)
> - Day 3:Sprint 2 優先項(knowledge TTL · pagination)
> - Day 4:Feature #2 LINE notify(0.5 天)+ 整合 test
>
> **結果:** 4 天做完 3 新功能 + 大半維運優化 · v1.2 release 同時兼顧創新與可靠

---

## 🚫 低優先(不建議先做)

- R14#8 lazy import · 3G 網路本公司幾乎沒人用 · 公司內網 / Mac 都夠快
- R14#15 load test · 10 人公司 unit test + smoke 夠 · load test 過度工程
- R14#17 fixtures · scripts 不常改 · 維護成本可接受

這 3 項全合計 6.5h · 可延到 v1.4 有空再做。

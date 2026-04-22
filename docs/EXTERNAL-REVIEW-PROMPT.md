# 承富 AI 系統 · 外部審查請求 (v8.1)

> **第 12 輪審查 · 2026-04-22 下午**
> **本輪跨過的里程碑:** Round 10 reviewer(交付閉環)+ Codex R5/R6/R7 共 17 紅黃 + 5 routers 抽出(§11.1 B-1~B-5)+ RELEASE-NOTES-v1.0(老闆簽收版)+ /api/ask nginx 預算 gate 真接 · **全部已實作 push**
> **本輪重點:v1.2 sprint 剩餘卡(knowledge + admin routers · X-Agent-Num server-side derivation · ALLOW_LEGACY_AUTH_HEADERS=0 全 endpoint 切換)**
> **R7 找到 R6#1 仍是「假修一半」(refresh payload 是 {id, sessionId} 不是 {email})· 已用 LibreChat v0.8.4 原始碼驗證並修完(commit `54d4955`)**

---

## ⚠️ **在你下筆之前 · 強制讀這段**

前 11 輪 reviewer 平均重複指出 70% **我們已修過的項目**。
**若你的報告出現下列「已修 51 項」任一條 · 該項直接視為 0 分。**

### 🚫 已修 51 項 · 嚴禁再指為紅線

#### Round 1-7 修的(14 項)

| # | reviewer 常指的 | 修在哪 | commit |
|---|---|---|---|
| 1 | CRM 整區重繪掉幀 | `frontend/launcher/modules/crm.js:86-108` 分批 + idleCallback | `9903d55` |
| 2 | tenders 整區重繪 | `modules/tenders.js:47-85` event delegation | `9903d55` |
| 3 | chat renderMarkdown regex | `modules/chat.js:252-284` vendor-marked.js | `9903d55` |
| 4 | auth 401 沒 retry | `modules/auth.js:20-44` SessionExpiredError + Web Locks | `bedf413` |
| 5 | Day 0 登入卡關 | `PRE-DELIVERY-CHECKLIST.md:112-125` | `9903d55` |
| 6 | Baseline 老闆答不出 | `BASELINE.md:9-20` + `192-236` Champion 1 週日誌 | `9903d55` |
| 7 | per-user hard stop 只儀表 | `main.py /quota/check` + `chat.js:160-175` 送前擋 | `9903d55` |
| 8 | transactions schema 默默回 0 | fingerprint + `/admin/budget-status` 黃牌降級 | `9903d55` |
| 9 | Route A hash router 未防 | `librechat-relabel.js:14-70` listener + `_matchChatPath` | `9903d55` |
| 10 | on_event / .dict() deprecation | `main.py` lifespan + 全檔 model_dump() | `08cf827` |
| 11 | overpromise 文案 | index.html / QUICKSTART / BOSS 手冊三處 | `5b5859c` |
| 12 | split-brain(routers/ + auth.py) | `_unused_scaffold/` 歸檔 | `5b5859c` |
| 13 | 密碼紙條沒銷毀 SOP | `PRE-DELIVERY-CHECKLIST.md:100-107` | `08cf827` |
| 14 | 備份沒異機 / restore | `scripts/backup.sh` rclone + 月度 drill | `bedf413` |

#### Round 8-10 修的(13 項)

| # | 項目 | commit | 新測試 |
|---|---|---|---|
| 15 | D · main.py 拆 admin_metrics | `65de9bf` | +15 unit |
| 16 | C · Projects drawer + Handoff | `051dbed` | +3 integration |
| 17 | A · Fal.ai Recraft(num_images=3) | `9dc7302` | +6 integration |
| 18 | E-1 · 多來源知識庫 CRUD | `fb84566` | +9 integration |
| 19 | E-2 · 多格式抽字 + Meili 索引 | `115f049` | +14 unit |
| 20 | E-3 · 前端 Admin UI + 知識庫 view | `8f91f76` | node check |
| 21 | **Q1** · quota_check fail-safe | `916d142` | +5 pytest |
| 22 | **Q3** · X-Agent-Num source 過濾 | `916d142` | +2 pytest |
| 23 | **Q4** · Meili 兩階段時間戳 | `916d142` + `d6299be` 真 wait | +3 pytest |
| 24 | **Q2** · Handoff sessionStorage | `2305dd0` | node check |
| 25 | **A polling** · 前端 design.js 閉環 | `2305dd0` | node check |
| 26 | **palette stale guard** · `_queryVersion` | `2305dd0` | node check |
| 27 | **Round 10 紅線 5 項** · sandbox alias / Q4 wait / Meili backup poll+GPG / 隱私治理 / OCR probe | `d6299be` `8a499c8` | +6 pytest |

#### Round 10.5 + Codex R1-R6(12 項 · 本輪重點)

| # | 項目 | commit | 新測試 |
|---|---|---|---|
| 28 | R2 · 6 個假修(NAS root narrow / cron plist real / etc.) | `e40f07b` | smoke pass |
| 29 | R3 · 10 項全系統掃(JWT 真驗 / Fal queue / Meili wait / etc.) | `018d4c2` | +8 pytest |
| 30 | R4.3 · Markdown XSS + CSP 強化 | `29b136c` | smoke pass |
| 31 | R4.5 · LibreChat image digest pin | `29b136c` | docker-compose validate |
| 32 | R4.6 · restore tmp swap atomicity | `29b136c` | dr-drill pass |
| 33 | **6 skill audit 並行**(tech-debt / sec / py / perf / dep / arch · 找 45 修 10) | `993d0cd` | +45 issue 列 ROADMAP §11 |
| 34 | **§11.5/7/9/10** · sources cache · librechat.yaml · 死 endpoint 註解 · anthropic 0.49 | `6ab5bbd` | smoke pass |
| 35 | **§11.11/12/14** · log redact · cookie 嚴格 · export streaming | `15d70c2` | +2 pytest |
| 36 | **§11.3/4/6** · NAS 平行 reindex · OCR 上限 · Chrome Ext modal | `766ac23` | +3 pytest |
| 37 | **§11.8/13** · cron plist 真部署 · Playwright L3 真 assert | `2818b9a` | tests/e2e |
| 38 | **§11.1/2/15** · launcher project-store 骨架 · uvicorn workers=2 · main.py refactor plan | `5d39605` | node check |
| 39 | **R5 7 紅黃** · cookie 嚴 / internal token / cache version / per-file timeout / history backfill / CI / limiter user key | `5626b2c` | +6 pytest |

#### Round 11 修的 7 項(R6 + routers + release notes)

| # | 項目 | commit | 新測試 |
|---|---|---|---|
| 40 | **R6#1** · `_verify_librechat_cookie` 改驗 `refreshToken` + `JWT_REFRESH_SECRET`(R5#1 假修 · LibreChat v0.8.4 真實情) | `aa54ea2` | +1 contract |
| 41 | **R6#2** · `_user_or_ip` slowapi key_func 直接 verify cookie(state 在 middleware 階段是空的) | `aa54ea2` | smoke pass |
| 42 | **R6#3** · `/design/recraft` + `/design/history` 強制要 trusted email · 防匿名爆 Fal | `aa54ea2` | +1 contract |
| 43 | **R6#4** · `/feedback` list/stats 改 admin-only · `/feedback` create 用 trusted email override · `/tender-alerts` 必登入 | `aa54ea2` | +2 contract |
| 44 | **R6#5** · 4 個 auth contract test(blocks_anonymous / uses_trusted_email / requires_admin) | `aa54ea2` | +4 pytest |
| 45 | **§11.1 B-1~B-5** · safety + feedback + users + tenders + design routers 抽出 | `c119317`-`c9e572e` | 97 pass + 2 skip |
| 46 | **RELEASE-NOTES-v1.0.md** · 老闆 1 頁簽收版 + Day 0 18 項 + 三層接受標準 | `cc47064` | n/a |

#### Round 12 本輪新增 5 項(R7 修真假修 + nginx auth_request 真接)

| # | 項目 | commit | 新測試 |
|---|---|---|---|
| 47 | **R7#1** · `_verify_librechat_cookie` 真完整 · LibreChat refresh payload 是 `{id, sessionId}` 不是 `{email}` · 加 `_users_col` lookup by ID + LRU cache 60s | `54d4955` | smoke pass |
| 48 | **R7#2** · `_user_or_ip` ECC_INTERNAL_TOKEN 真比對 secret · R6#2 只看 header 存在 · 任何人 curl 都能打 internal bucket | `54d4955` | smoke pass |
| 49 | **R7#4** · `/feedback` create 完全不信 `fb.user_email` · 無 trusted_email 直接 403(R6#4 fallback 仍可偽造他人回饋) | `54d4955` | +1 contract |
| 50 | **R7#9** · `/api/ask` LibreChat 預算 gate · `/quota/preflight` 204/429 endpoint + nginx auth_request · 防同事繞 launcher 直打 LibreChat | `54d4955` | +2 contract |
| 51 | **R7#10** · `ALLOW_LEGACY_AUTH_HEADERS` env gate(prod 預設關)+ `_is_prod()` + nginx `/api/` strip X-User-Email · prod startup 強制 raise 若 JWT_REFRESH_SECRET 未設 | `54d4955` | smoke pass |

**所以本輪 reviewer 不要再說** 「cookie 沒驗 / slowapi 假裝 / Fal 沒擋匿名 / feedback 任寫 / main.py 太肥 / 沒老闆驗收文 / routers 沒抽 / refresh payload 沒驗 ID / internal token 沒比對 / /api/ask 沒 quota gate / X-User-Email 還能偽造 / dev mode 沒區分」—— **全部已 push**。

---

### ✅ 第 12 輪 reviewer 該做的事 · 審「R7 後剩餘 v1.2 sprint 卡」

**v1.0 工程已過 12 輪 · R7 把認證體系從「假修一半」修到真實 LibreChat 規格。**
**本輪重點變成:**

1. **§11.1 routers 還剩 2 個沒抽**(knowledge ~600 行 + admin ~500 行) · 先建 `routers/_deps.py` 集中 `_serialize` / `current_user_email` / `require_admin` 才不會抽完之後到處改?
2. **§10.3 X-Agent-Num server-side derivation** · 前端 header 仍可被 user 改 1-29 拿到沒授權的 source · v1.2 該怎麼從 `conversationId` 反查 LibreChat agent_id?(R7#11 codex 已抓)
3. **prod ALLOW_LEGACY_AUTH_HEADERS=0 切換的 break 範圍** · launcher 從 dev → prod · 哪些 module 仍依賴 `X-User-Email` header?(grep `current_user_email` 看一遍)
4. **R7#1 的 LRU cache 安全性** · `_lookup_user_email_cached` 60s TTL · 若 user 被 LibreChat 改名 / 砍 admin · accounting 端最多差 60s 才生效 · 對嗎?
5. **`/quota/preflight` 在 nginx auth_request 的 perf** · 每個 `/api/ask` 都打 accounting · MongoDB transactions sum + Mongo lookup user · 95-percentile 是否 < 50ms?

**絕不做的事:**
- 不要再指「🚫 已修 51 項」
- 不要建議換框架 / 換 LibreChat / 加 k8s / 加 Redis
- 不要再說「initial 實作建議」— 工程已 100 pytest × 多層驗
- 不要再審 §4 教材 / §5 ROI 公式 / §6 Champion 機制(Round 10 已答覆 · v1.2 不動)
- 不要再說「LibreChat refresh payload 是 email」(R7 已用原始碼證明是 {id, sessionId})

---

## 🔗 0. 直接去讀

| 來源 | 位置 |
|---|---|
| **GitHub(public)** | <https://github.com/Sterio068/chengfu-ai> |
| **Clone** | `git clone https://github.com/Sterio068/chengfu-ai.git && cd chengfu-ai` |
| **作者本機** | `/Users/sterio/Workspace/ChengFu` |
| **本機跑** | <http://localhost/> · <http://localhost/api-accounting/docs> |
| **commit 歷史** | `git log --oneline -40`(35+ commit · 11 輪審查) |
| **Round 10→11 新提交** | `git log --oneline 7839624..HEAD` 看本輪 14 個 commit |

### 必讀 13 份(28 分鐘消化)

```
[v1.2 sprint 重點](本輪第一次審)
1. backend/accounting/main.py          · 2270 行 · 待抽 knowledge + admin
2. backend/accounting/routers/         · 5 個已抽:safety / feedback / users / tenders / design
3. backend/accounting/routers/__init__.py  · §11.1 進度 5/7 + 抽法 pattern
4. docs/REFACTOR-PLAN-§11.1.md         · v1.2 sprint 7 步 plan
5. docs/RELEASE-NOTES-v1.0.md          · 老闆簽收版 1 頁

[R7 認證新架構](本輪重點)
6. backend/accounting/main.py:30-65    · `_is_prod / _jwt_refresh_configured / _legacy_auth_headers_enabled` env helpers
7. backend/accounting/main.py:325-410  · `_verify_librechat_cookie + _lookup_user_email_cached` (R7#1 ID lookup)
8. backend/accounting/main.py:166-188  · `_user_or_ip` slowapi 真用 user(R7#2 internal token secret-equal)
9. backend/accounting/main.py:1383-1428 · `/quota/preflight` (R7#9 給 nginx auth_request)
10. frontend/nginx/default.conf:147-178 · `/api/ask` auth_request gate

[ROADMAP §11](v1.1 + v1.2 全 15 項分配)
11. docs/ROADMAP-v4.2.md §11            · 15 項分批 commit 對照
12. backend/accounting/test_main.py    · 100 pytest + 5 個 auth contract test(R6 4 + R7 1)

[交付層](Round 10 已過 · 本輪不重審)
13. docs/PRE-DELIVERY-CHECKLIST.md     · Sterio Day -7 ~ Day +30 清單
```

---

## 1. 客戶與專案(維持)

### 客戶
- **承富創意整合行銷有限公司**(台灣 · 10 人)
- 政府標案 / 公關活動 / 設計案
- 2-3 位資深者對 AI 抗拒

### 老闆親答 14 題(優先級依據 · Round 4-9 既定 · 本輪不再加問)
1-5 同前(設計 / 提案 / 廠商 / 省時 / Champion 自主)
6-10:PDF OCR / Fal 3 張 / NAS 全 scope / +6 lib OK / Drawer 42%
Q1-Q4:預算異常 admin only / handoff 自動帶 / source 完全藏 / Meili 兩階段時間戳

→ **偏離這 14 題的建議會被否決**

---

## 2. 技術棧(不可替換)

| 層 | 選擇 |
|---|---|
| 硬體 | Mac mini M4 24GB |
| AI Platform | LibreChat **v0.8.4 pinned + @sha256 digest** |
| AI Model | Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 |
| 後端 | FastAPI(`main.py` 2206 行 · `routers/` 5 個 · `services/` 3 純 function) |
| 前端 | 原生 ES Modules · **無 build step** |
| 容器 | Docker Compose × 6(production)+ 6(sandbox)· **5 image @sha256 pinned** |
| 對外 | Cloudflare Tunnel + Access(未架) |
| 機密 | macOS Keychain + GPG(off-site backup) |
| 全文搜尋 | Meilisearch v1.12 + primaryKey + `_submit_and_wait` |
| 抽字 | PyMuPDF + tesseract-chi-tra + python-docx/pptx/openpyxl/Pillow |
| **Auth(本輪改)** | LibreChat refreshToken cookie + JWT_REFRESH_SECRET + slowapi user-key + 三路徑(cookie / internal-token / X-User-Email legacy) |

**不接受:** k8s / Redis / Kafka / GraphQL / 換框架 / SaaS / 改 10 助手 / 改 5 工作區

---

## 3. 當前狀態

### ✅ 程式碼:**99.95%**(本輪 +0.05%)

- 6 容器 healthy · sandbox 6 容器完整 compose · accounting healthcheck 已綠
- **100 pytest pass + 2 skip · 8 smoke pass · 0 deprecation**(原 7/1 · 本輪修了 launcher pipefail bug)
  - tests/test_admin_metrics.py · 20 unit
  - tests/test_knowledge_indexer.py · 17 unit + 2 skip
  - test_main.py · 63 integration(本輪 +3 R7 contract)
- **後端 endpoint:** ~56(本輪 +1 · `/quota/preflight` 給 nginx auth_request)
- **routers/ 抽出 5 個** · 共 ~545 行從 main.py 移走
  - `safety.py`(56) · `feedback.py`(104) · `users.py`(80) · `tenders.py`(73) · `design.py`(235)
  - 待抽:`knowledge.py`(~600) · `admin.py`(~500)→ v1.2 sprint
- **前端:** 25 個 ES modules · CSS +400 行
- **services/:** `admin_metrics.py` / `knowledge_extract.py` / `knowledge_indexer.py` pure function
- **R7 新 nginx 區塊:** `/api/ask` auth_request quota gate + `/_quota_gate` internal location

### 🟡 部署落地:**45%**(本輪 +0%)

- Mac mini **仍未上架**
- Cloudflare Tunnel 仍未接
- `knowledge-base/samples/` 仍空(等 Day -5 真實案例灌)
- 10 帳號仍未建
- 2 場教育訓練仍未辦(投影片準備好了)
- T0 baseline B 路仍未跑(模板備好了)
- NAS 掛載 SMB Keychain 仍未配
- knowledge-cron.sh 仍未排 launchd plist
- FAL_API_KEY 仍未設
- **JWT_REFRESH_SECRET** 仍未從 LibreChat .env 同步(R6 後新增依賴 · v1.2 sprint 第 1 件)
- **Champion 人選仍未指定** ← Round 10 已給 SOP · 本輪不重審

### 📚 教材:**100%**(本輪 +4%)

- 3 完整案例 + 4+1 角色手冊 + QUICKSTART + Pre-Delivery + Baseline + Upgrade
- DAY0-DRY-RUN + TRAINING-SLIDES + CHAMPION-WEEK1-LOG + BOSS-VIEW
- **本輪新:** RELEASE-NOTES-v1.0.md(老闆簽收版 · 1 頁 + ROI 公式 + Day 0 18 項)+ REFACTOR-PLAN-§11.1.md(v1.2 sprint plan)

---

## 4. 我要你審什麼(本輪主軸:R7 後剩餘 v1.2 sprint 卡)

### 4.1 routers 還剩 2 個沒抽 · 是否可解?

**讀 `backend/accounting/main.py` 找 `db.knowledge_*` 與 `db.admin_*` 的 endpoint:**

- knowledge router 預估 ~600 行 · endpoint 約 12 個(`/knowledge/list,read,search,delete,reindex,sources/*`)
  - 重度依賴:`services/knowledge_extract.py` + `services/knowledge_indexer.py` + `_serialize` helper + Meili index
  - **疑問 1:** `_serialize` 在 main.py / safety.py / feedback.py / tenders.py / design.py **重複定義 5 次**(commit `99308f3` 標 TODO)。v1.2 sprint 抽 knowledge 前要不要先建 `routers/_deps.py`?
- admin router 預估 ~500 行 · endpoint 約 18 個(`/admin/dashboard,users,sources,budget-status,adoption-metrics,...`)
  - 重度依賴:`services/admin_metrics.py`(本身已抽) · `_compute_feedback_stats`(本輪剛抽到 feedback router)
  - **疑問 2:** `admin_dashboard` 內部直接呼 `_compute_feedback_stats()` bypass Depends · v1.2 抽 admin router 後 · 這個 bypass 要不要改 `from routers.feedback import _compute_feedback_stats`?跨 router 內部 import 是否反而增加耦合?

**輸出:** 1-2 句意見 · 是「v1.2 真該抽完」還是「stop at 5/7 · 不值得抽 last 2」?

### 4.2 LibreChat `/api/ask` 預算 gate · R7 已接 · 但實戰會炸嗎?

**R7 已實作(commit `54d4955`):**
- `frontend/nginx/default.conf:147-178` · `/api/ask` → `auth_request /_quota_gate` → `/quota/preflight` 204/429
- `backend/accounting/main.py:1383-1428` · `/quota/preflight` 從 cookie 拿 user · 走 admin_metrics.quota_check
- 401 / 429 各有自定 error_page 回 user friendly JSON

**疑問(本輪審):**
1. **每個 /api/ask 都打 accounting + Mongo · perf 是否會被打爆?**
   - 同事 10 人 · 假設每人每天 50 次對話 = 500 次 /api/ask /day
   - quota_check 內部聚合 `transactions_col.aggregate` · index 已建?(`backend/accounting/main.py:67`)
   - 95-percentile 是否 < 50ms?
2. **gate 失敗 → 整個 LibreChat 對話卡 · 是不是 single point of failure?**
   - 若 accounting 容器掛 · 全公司不能對話
   - nginx auth_request 預設 fail-closed · 該不該設 `proxy_intercept_errors off` 讓它 graceful?
3. **僅擋 /api/ask · 沒擋 /api/edit/* / /api/files/* / /api/agents/*** · 漏網嗎?
   - 看 `frontend/nginx/default.conf:189-198` · 其他 /api/* 完全不過 gate

### 4.3 全 endpoint JWT 強制遷移 · 哪些還靠 X-User-Email?

**現狀(R6 後):** `current_user_email(request, header_email)` 兩路徑:
1. cookie 有 refreshToken + JWT_REFRESH_SECRET 設 → 用 cookie 認
2. 否則 fallback 用 X-User-Email header(launcher 自己塞)

**疑問:** v1.2 要不要把 fallback 砍掉?
- 砍掉 → 開發環境(沒 LibreChat)launcher 完全壞
- 不砍 → prod 若 launcher 被 XSS · 攻擊者塞任意 X-User-Email

**搜尋:** `grep -rn "current_user_email\|X-User-Email" backend/accounting/`
列出哪些 endpoint 是「cookie 必擋」vs「cookie 可繞」· 給出該改的 endpoint 清單

### 4.4 §10.3 X-Agent-Num server-side derivation 的可行性

**現狀:** `/knowledge/list?agent_num=7` 前端傳 1-29 · server 用它過濾 source visibility(R5 R3 修)。

**問題:** 攻擊者可以 `?agent_num=11`(投標 Workspace 全部 source)拿到沒授權的標案資訊。

**選項:**
- A · server 從 conversationId 反查 LibreChat 的 agent_id · 再 map 1-29
  - 缺點:LibreChat agent_id 是 string `agent_xxx` · 沒對應 1-29 · 要建 map 表
- B · 前端送 agent_id (string) · server 自己 map
  - 缺點:前端拿到 agent_id · 仍可改
- C · 不擋 · 標案這類 source 移到 admin-only knowledge index
  - 缺點:Workspace 1 投標就沒 RAG 了

**輸出:** v1.2 哪個方向?要不要拖到 v1.3?

### 4.5 R7 cookie+ID lookup 在 prod 的副作用

**現狀(R7 後):** `_verify_librechat_cookie` 讀 refreshToken cookie · decode payload · 若有 `email` 直接用 · 否則走 `_users_col.find_one({_id: ObjectId(payload.id)})` 反查 + LRU cache 60s。

**疑問:**
1. **R7#1 cache 安全性** · 60s TTL 是否夠短?
   - 若 LibreChat admin 砍某 user · accounting 端最多差 60s 才生效
   - 該不該收緊到 30s?
   - 該不該加 `_USER_EMAIL_CACHE.pop()` 在某些 admin endpoint 強制刷新?
2. **R7#1 fallback path 是否完整** · payload 沒 `id` 也沒 `sub` 也沒 `userId` 時 · `_lookup_user_email_cached` 不會被叫到 · 直接 None
   - 若 LibreChat 升級 v0.9 改成 `payload.user_id` · 我們會 silent fail
   - 要不要 raise warn 「未知 payload schema」?
3. **R7#10 prod startup raise** · `JWT_REFRESH_SECRET` 沒設 → 容器啟動失敗 · accounting healthcheck 紅
   - 部署人員若忘了 sync env · Mac mini 直接無法上線
   - 該不該在 `scripts/start.sh` 加 LibreChat .env 同步 sanity check?
4. **R7#2 internal token 比對** · `ECC_INTERNAL_TOKEN` 沒設 → cron silently 失敗
   - daily-digest cron 隔天 09:00 才會發現 · 中間 24h log 不會通知
   - 該不該加 startup `ECC_INTERNAL_TOKEN` 必設(prod)?

### 4.6(可選)v1.0 release 後第 2 週的死法 · v9 版

Round 7-10 列了:NAS 斷線 / Handoff 沒人填 / Fal 爆預算 / Meili 損毀 / Cookie 不同步
R7 新風險:
- accounting 容器掛 · `/api/ask` 全公司停擺(R7#9 副作用)
- LibreChat `JWT_REFRESH_SECRET` 換 · accounting 沒同步換 · cookie auth 全壞
- 60s LRU cache · admin 砍 user 後仍可繼續打 admin endpoint 60s
**這些都已有警告 · 你有 v1.2 sprint 期間新 candidate 嗎?**

---

## 5. 輸出要求

### 5.1 總論(150 字內)
1 句話評價 + 3 件 v1.2 sprint 最該先做的事

### 5.2 針對 §4.1-4.5 各出評分 + 1 個具體改動

```
審查項:4.1 / 4.2 / 4.3 / 4.4 / 4.5
評分:1-5 ⭐
做對了什麼:
最該補一件事:(file:line · 100 字內)
v1.2 後會怎樣:(預測)
```

### 5.3 v1.2 sprint 第一週的 clear-cut 清單

給 Sterio 一張 **v1.2 sprint Day 1 ~ Day 7** 的清單 · 每項 ≤ 4h · 抽完 routers + 接好 quota gate + 同步 JWT secret · 全部做完才能宣稱 v1.2 完成。

### 5.4 給作者的 3 個問題

下輪能更精準的話你想知道什麼?

---

## 6. 格式要求

- 繁體中文(技術詞 API/JWT/SSE 保留)
- 避免大陸用語
- 金額:`NT$ X,XXX`
- 日期:`2026 年 4 月 22 日`
- **檔案位置絕對路徑 + 行號**(`/Users/sterio/Workspace/ChengFu/xxx.py:123`)

---

## 7. 量化基準(本輪更新)

| 項目 | v7.0 (Round 10) | v8.0 (Round 11) | v8.1 (本輪 R7) | Δ v8→v8.1 |
|---|---|---|---|---|
| **GitHub commits** | 22 | 36 | **37** | +1 |
| **pytest** | 81 pass + 2 skip | 97 pass + 2 skip | **100 pass + 2 skip** | +3 |
| **smoke** | 11 pass | 11 pass | **8 pass / 0 fail**(修了 launcher pipefail) | 1 fix |
| **main.py 行數** | ~2200 | 2206 | **2270**(+helpers + /quota/preflight) | +64 |
| **routers/ 抽出** | 0 | 5 | 5 | - |
| **services/ 模組** | 3 | 3 | 3 | - |
| **後端 endpoint** | ~55 | ~55 | **~56**(+/quota/preflight) | +1 |
| **前端 modules** | 25 | 25 | 25 | - |
| **後端依賴** | 17 | 17 | 17 | - |
| **CSS 新增** | +400 | +400 | +400 | - |
| **文件** | 25 | 27 | **27** | - |
| **Image @sha256 pinned** | 0 | 5 | 5 | - |
| **Cookie auth strategy** | refreshToken (R5#1 假修) | refreshToken + JWT_REFRESH_SECRET (R6#1 假修一半) | **refreshToken + JWT_REFRESH_SECRET + ID lookup + LRU cache (R7#1 真完整)** | 修正 R6#1 假修 |
| **Auth contract tests** | 0 | 4 | **5**(+R7#4 anonymous block) | +1 |
| **nginx auth_request gate** | 0 | 0 | **1(/api/ask → /quota/preflight)** | +1 |
| **legacy header gate** | always allow | always allow | **`ALLOW_LEGACY_AUTH_HEADERS` env(prod 預設關)** | 新策略 |
| **意外驗證** | sandbox alias / Q4 真 wait | R5#1 cookie 假修 → R6 真驗 LibreChat | **R6#1 仍假修一半 · R7 用 LibreChat session.ts 證明 payload 是 {id, sessionId} 不是 {email}** | - |
| **部署落地完成度** | 45% | 45% | **45%** | - |

---

## 8. 最後提醒

- 這系統**已跑** · 6 production + 6 sandbox compose · 100 pytest pass
- Sterio 懂技術 · **承富內部人不懂** · 任何「只有 Sterio 能維護」= 技術債
- 已 12 輪審查 · **重複指 Section「🚫 已修 51 項」會被作者直接刪掉**
- 老闆要**省時 + 接案量** · 不是工程藝術
- **本輪 reviewer 請只審 §4.1-4.5 R7 後剩餘 v1.2 sprint 卡 · 不再提交付閉環 / cookie 假修**
- R7 已用 LibreChat v0.8.4 GitHub 原始碼驗證認證體系 · 若 reviewer 認為仍假修 · 必附原始碼 link 證明

**直接開始審 §4 · 不用先確認。**

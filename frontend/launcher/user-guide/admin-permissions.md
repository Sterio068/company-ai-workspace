# 🔐 Admin vs 一般同事 · 權限對照表

> v1.3.0 · 誰能看 / 操作什麼 · 權限邊界一覽

> vNext Phase D 更新:同仁管理 UI 的 28 個權限勾選已可儲存與套用 preset,且第一批高風險功能已接上 backend enforcement。後台仍會顯示哪些權限已真正強制,避免把 advisory 權限誤認為完整 RBAC。

---

## 3 層權限模型

承富 AI 採 **3 層簡化模型** · 10 人規模夠用 · 不搞過度複雜的 RBAC

| 層級 | 誰 | 權限 |
|---|---|---|
| 🔴 **ADMIN** | 老闆 + IT(安裝精靈建的第一個 + `ADMIN_EMAILS` 白名單) | 全部 |
| 🟡 **USER** | 9 位同仁 | 自己的資料 + 共用 10 Agent |
| ⚪ **匿名** | 沒登入的瀏覽器 | 只能看登入頁 · `/healthz` |

---

## Admin 從哪定?(2 條路徑 · OR 關係)

**路徑 1 · `ADMIN_EMAILS` 白名單(推薦)**
- `config-templates/.env` 設 `ADMIN_EMAILS=老闆@公司.com,IT@公司.com`
- 逗號分隔 · 改完 restart `docker compose` 生效
- v1.3 移除 hardcode · 沒設 = admin 全鎖死(安全預設)

**路徑 2 · LibreChat `users.role=ADMIN`**
- LibreChat 第一個註冊者自動 ADMIN(DB layer)
- 安裝精靈會自動建這個 admin · 不用手動註冊
- 加入 `users.role=ADMIN` 的 user 也會被承富後端認為是 admin

**優先順序**:`ADMIN_EMAILS` > `users.role` > 一律當 USER

---

## 完整對照表

### 目前已強制的權限邊界

| 類型 | 狀態 |
|---|---|
| Admin-only endpoints | 已由 `ADMIN_EMAILS` / `users.role=ADMIN` 強制 |
| 知識庫管理 `/admin/sources/*` | 已強制 admin |
| 媒體 CRM 編輯 / 匯出 | 已強制 admin |
| PDPA delete-all / audit log / admin dashboard | 已強制 admin |
| 28 個細部 `chengfu_permissions` | 第一批已 enforcement,其餘以後台 catalog 標示為準 |

目前已由 backend 實際強制的細部權限:
- `accounting.view` / `accounting.edit`
- `social.post_own`
- `site.survey`
- `knowledge.manage`
- `media_crm.edit` / `media_crm.export`
- `admin.dashboard` / `admin.audit` / `admin.pdpa`

仍屬 advisory / 待下一輪接上的代表項:
- `social.post_all`:尚未拆出「可管理全公司貼文」的跨作者權限。
- 部分 Agent 使用權限如 `press.draft`,目前主要作為 UI / preset 管理資訊。

| 功能 | 匿名 | 一般同事 | Admin |
|---|---|---|---|
| **登入頁** | ✅ | ✅ | ✅ |
| **Launcher 首頁(dashboard)** | ❌ 401 | ✅ 看自己 | ✅ 看自己 + admin badge |
| **5 Workspace + Agent 對話** | ❌ | ✅ | ✅ |
| **Project CRUD(自己的)** | ❌ | ✅ | ✅ |
| **Project handoff 4 格卡** | ❌ | ✅ 改自己 | ✅ 改任何人 |
| **CRM 商機(自己 owner)** | ❌ | ✅ | ✅ |
| **CRM 商機(別人 owner)** | ❌ | 👀 看 · 不能改 | ✅ 全可改 |
| **會議速記上傳 + 看自己** | ❌ | ✅ | ✅ |
| **會議速記看別人** | ❌ | ❌ 403 | ✅ |
| **媒體 CRM 列表** | ❌ | ✅(phone 遮) | ✅(phone 顯) |
| **媒體 CRM 編輯 / 推薦 / 匯出 CSV** | ❌ | 需 `media_crm.edit/export` | ✅ |
| **場勘 PWA 拍照 + 看自己** | ❌ | ✅ | ✅ |
| **場勘看別人** | ❌ | ❌ 403 | ✅ |
| **場勘 audio_note(只 owner)** | ❌ | ✅ 自己的 survey | ✅ 任何 survey |
| **社群排程貼文(自己 author)** | ❌ | 需 `social.post_own` | ✅ |
| **社群排程看別人** | ❌ | ❌ | ✅ |
| **社群 OAuth 連 FB/IG/LinkedIn** | ❌ | ✅ 連自己 | ✅ |
| **社群 OAuth status(誰連了什麼)** | ❌ | ❌ | ✅ |
| **知識庫搜 / 讀** | ❌ | ✅ | ✅ |
| **知識庫管理(/admin/sources)** | ❌ | 需 `knowledge.manage` 或 admin | ✅ |
| **回饋 👍👎** | ❌ | ✅ | ✅ |
| **回饋 stats** | ❌ | ❌ | ✅ |
| **設計助手生圖** | ❌ | ✅(用自己 quota) | ✅ |
| **設計助手 history** | ❌ | ✅ 自己 | ✅ |
| **/healthz** | ✅ | ✅ | ✅ |

---

## 🔴 Admin 專屬(同事看不到此選單)

| 功能 | endpoint | 用途 |
|---|---|---|
| **儀表板** | /admin/dashboard | 總覽 KPI |
| **本月成本** | /admin/cost | Anthropic + Whisper |
| **預算進度** | /admin/budget-status | 80% 警告線 |
| **用量 Top 10** | /admin/top-users | 誰花最多 |
| **採納率** | /admin/adoption | 同事真用沒 |
| **標案漏斗** | /admin/tender-funnel | 進入 → 提案 → 得標 |
| **LibreChat schema 驗** | /admin/librechat-contract | 升版後跑 |
| **匯出全資料** | /admin/export | 跨機遷移 |
| **匯入** | /admin/import | append 模式 |
| **demo 資料清** | DELETE /admin/demo-data | 上線前必跑 |
| **OCR 重 probe** | /admin/ocr/reprobe | tesseract 沒裝補 |
| **audit log 查** | /admin/audit-log | 維運看誰做了什麼 |
| **audit actions 列表** | /admin/audit-log/actions | dropdown 用 |
| **email 寄(rate limit)** | POST /admin/email/send | 月報外發 |
| **月報生成** | /admin/monthly-report | PDF 老闆看 |
| **Agent prompt 線上調** | /admin/agent-prompts | 不用改 JSON |
| **secret 管理** | /admin/secrets/* | FAL_API_KEY 等 |
| **PDPA delete-all(離職)** | POST /admin/users/{email}/delete-all | 跨 20+ collection 清 |
| **cron 跑紀錄** | /admin/cron-runs | 昨天 digest 有跑? |
| **社群 OAuth status** | /admin/social/oauth/status | 誰連了哪 platform |
| **社群 cron run-queue** | /admin/social/run-queue | 手動觸發發文 |
| **知識庫管理** | /admin/sources/* | CRUD source + reindex |

---

## 怎麼判斷自己是不是 admin?

打開 launcher · 看左上角:
- 🟢 admin · 名字旁邊有 `[admin]` badge · sidebar 多「📊 管理面板」
- 🟡 一般同事 · 沒 badge · sidebar 沒管理面板

或 console 跑:
```js
console.log(document.documentElement.dataset.role)
// "admin" 或 undefined
```

---

## 一般同事看到「權限不足」怎麼辦?

UI 不該顯示 admin 功能給你 · 若意外點到回 403:
1. 確認你的角色(看左上角)
2. 真要做 → 找 Champion / Sterio
3. 別 hack(不會給你過)

---

## Admin 升降權怎麼做?

**升新 admin**:
- 現有 admin 改 `config-templates/.env` `ADMIN_EMAILS` 加新 email
  ```
  ADMIN_EMAILS=老闆@公司.com,IT@公司.com,新admin@公司.com
  ```
- `./scripts/start.sh` 或 `docker compose up -d accounting` 重啟生效
- 該 user 重新整理 launcher · 看到管理面板

**降 admin**:
- 同上 · 移除 email
- 該 user 下次 request 即失去 admin 權

---

## 怎麼建新同仁帳號?

安裝精靈只建第一個 admin。其他 9 位同仁 2 種方式(admin 選一):

### A · 同仁自己註冊(最省事)

```bash
# 1. admin 編輯 config-templates/.env
ALLOW_REGISTRATION=true  # 原本 false · 改 true

# 2. 重啟 LibreChat
cd config-templates && docker compose up -d librechat

# 3. 通知同仁:訪問 http://ai.公司.com/chat 點「註冊」
#    自己填 email + 密碼 + 顯示名稱

# 4. 全員建好後 · 改回 ALLOW_REGISTRATION=false 關窗
docker compose up -d librechat
```

⚠ 開 `ALLOW_REGISTRATION=true` 期間任何人知道網址都能註冊 · 建議只開短時間

### B · admin 批次建(產密碼表分發)

```bash
# 1. 編輯 scripts/create-users.py 裡 USERS list
#    填 10 個同仁:email + name
USERS = [
    {"email": "alice@chengfu.com", "name": "王小明", "role": "USER"},
    {"email": "bob@chengfu.com",   "name": "李小華", "role": "USER"},
    # ...
]

# 2. 跑 script(用 admin 登入 token 建)
LIBRECHAT_ADMIN_EMAIL=admin@chengfu.com \
LIBRECHAT_ADMIN_PASSWORD=<剛設的密碼> \
python3 scripts/create-users.py

# 3. 產 scripts/passwords.txt · 分給同仁
#    交付完 shred -u scripts/passwords.txt 安全刪
```

### C · 不建同仁帳號只自己用

- 什麼都不做 · 一個 admin 帳號就好
- 缺:同仁共用 1 帳號 · 用量 + audit log 混在一起
- 僅適合 solo founder 或前期試用

**完全移除帳號(離職)**:
- 走 `docs/05-SECURITY.md §5.4` 完整 SOP
- 含 LibreChat disable + Cloudflare 移白 + PDPA delete-all

---

## 安全護欄

- **admin 不能刪自己**(防 lockout · `[E-209]`)
- **PDPA delete 必 confirm_email 完整 type**(防 mis-click)
- **內部 token 只給 cron**(`X-Internal-Token` 跨 service)· user 不該知道
- **Webhook URL 必 https + 拒內網 IP**(R27#4 SSRF guard)

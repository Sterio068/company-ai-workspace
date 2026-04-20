# Week 2 — 平台部署

> **目標**:第 14 日結束時,LibreChat 可用、Claude API 串上、10 組帳號建立、管理後台可用。
> **前置**:Week 1 驗收項全部打勾。

---

## Day 8-9:LibreChat 部署

### 任務 2.1:取得官方 LibreChat
```bash
cd ~/chengfu-ai
git clone https://github.com/danny-avila/LibreChat.git librechat-source
cd librechat-source
```
- [ ] 確認 README 顯示最新版本
- [ ] 看 `docker-compose.override.yml.example` 理解官方建議的 override 用法

### 任務 2.2:複製設定範本到專案
```bash
cd ~/chengfu-ai
mkdir -p config
# 從 config-templates 複製
cp [handoff]/config-templates/librechat.yaml config/
cp [handoff]/config-templates/docker-compose.yml config/
cp [handoff]/config-templates/.env.example config/.env
```

### 任務 2.3:填 `.env` 設定
- [ ] 取得 Anthropic API key(https://console.anthropic.com)
  - [ ] 建立新 key,標籤為 `chengfu-production`
  - [ ] 設定 usage limit:每月 NT$ 12,000(折算約 $400 USD)
  - [ ] 填入 `.env` 的 `ANTHROPIC_API_KEY=sk-ant-...`
- [ ] 取得 OpenAI API key(for embeddings only,不作為主力模型)
  - [ ] 建立 key,usage limit $10/月(只用來做 embeddings)
  - [ ] 填入 `OPENAI_API_KEY=sk-...`
- [ ] 生成其他密鑰(依 `.env.example` 內說明):
  - [ ] `CREDS_KEY`、`CREDS_IV`、`JWT_SECRET`、`JWT_REFRESH_SECRET`
  - [ ] 用 `openssl rand -hex 32` 生成
- [ ] 設定 `DOMAIN_CLIENT` 與 `DOMAIN_SERVER` 為 `https://ai.<承富domain>.com`

### 任務 2.4:啟動 Docker Compose
```bash
cd ~/chengfu-ai/config
docker compose pull
docker compose up -d
```
- [ ] 第一次啟動約 2-5 分鐘(拉 image)
- [ ] 確認所有容器都是 Up:`docker compose ps`
  - librechat(API + UI)
  - mongodb
  - meilisearch
  - rag-api(後續 Week 3 再接)
- [ ] 測試:`curl http://localhost:3080` 回應 HTML

### 任務 2.5:透過 Cloudflare Tunnel 驗證
- [ ] 瀏覽器開 `https://ai.<承富domain>.com`
- [ ] 通過 Cloudflare Access 驗證(白名單 email)
- [ ] 看到 LibreChat 登入頁 → 部署成功

---

## Day 10:帳號與權限

### 任務 2.6:建立管理員帳號
- [ ] 在登入頁點「註冊」,先註冊 `sterio@<承富domain>.com`(或 Sterio 既有 email)
- [ ] 登入後進入 `localhost:3080/admin` 或 admin console
- [ ] 將此帳號設為 ADMIN

### 任務 2.7:關閉公開註冊
- [ ] 在 `.env` 設定 `ALLOW_REGISTRATION=false`
- [ ] 重啟:`docker compose restart librechat`
- [ ] 測試:登出後嘗試註冊新帳號應失敗
- [ ] 新增同仁只能由管理員在後台建立

### 任務 2.8:建立 10 個同仁帳號
從承富取得 10 位同仁名單,依以下原則建立:
- [ ] Email:使用公司域名 email(若無就建立 @chengfu.com)
- [ ] 初始密碼:亂數生成 12 碼(大小寫+數字+符號)
- [ ] 角色:USER(非 ADMIN)
- [ ] Token 上限設定(依職務分類):
  - 重度使用者(2 位):每月 300 萬 token
  - 中度使用者(6 位):每月 150 萬 token
  - 輕度使用者(2 位):每月 80 萬 token

帳號清單範本:
| Email | 姓名 | 角色 | Token 上限/月 |
|---|---|---|---|
| CEO@... | 老闆 | USER | 150 萬 |
| pm1@... | PM 組長 | USER | 300 萬 |
| ... | ... | ... | ... |

- [ ] 將初始密碼以**安全管道**(非 LINE 群組)寄給各同仁
- [ ] 建議用 1Password 共享功能或加密 zip

---

## Day 11:API 連線與模型驗證

### 任務 2.9:確認三個 Claude 模型都可用
登入 LibreChat,建立新對話,分別測試:
- [ ] `claude-haiku-4-5` — 送「你好」,應 1-2 秒回應
- [ ] `claude-sonnet-4-6` — 送一段約 500 字文字做摘要,應成功
- [ ] `claude-opus-4-7` — 送複雜推理題,應成功

### 任務 2.10:驗證檔案上傳
- [ ] 上傳一份範例 PDF(10-20 頁,可用政府採購網抓一份招標須知範本)
- [ ] 請 Claude 摘要
- [ ] 確認能正確解析繁中內容

### 任務 2.11:驗證會話歷史儲存
- [ ] 建立 3-5 個對話
- [ ] 登出後重新登入
- [ ] 側邊欄應顯示對話歷史

### 任務 2.12:驗證全文檢索
- [ ] 前一步建立的對話中輸入特定關鍵字
- [ ] 使用 LibreChat 側邊的搜尋功能
- [ ] 應能搜到包含該關鍵字的對話

---

## Day 12:管理後台與監控

### 任務 2.13:設定用量監控
- [ ] LibreChat admin panel → Settings → Usage tracking:啟用
- [ ] 確認能看到每位使用者:
  - 每日/每月 token 消耗
  - 分 input/output tokens
  - 按模型區分(Haiku/Sonnet/Opus)
  - 對應 API 成本(USD)

### 任務 2.14:設定用量告警
- [ ] 寫一個 shell script `scripts/check-usage.sh`,每日 09:00 由 cron 執行:
  - 查詢各 user 當月 token 使用率
  - 若超過 80% → 寄 email 告警到管理員
  - 若超過 100% → 暫時降級該 user(改只能用 Haiku)
- [ ] 設定 cron job:
  ```
  0 9 * * * /Users/steadmin/chengfu-ai/scripts/check-usage.sh
  ```

### 任務 2.15:設定 MongoDB 備份
建立 `scripts/backup-mongo.sh`:
```bash
#!/bin/bash
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/Users/steadmin/chengfu-ai/backups/mongo/$DATE"
mkdir -p $BACKUP_DIR
docker exec chengfu-mongo mongodump --archive --gzip > $BACKUP_DIR/mongo.archive.gz
find /Users/steadmin/chengfu-ai/backups/mongo -mtime +30 -type d -exec rm -rf {} \;
```
- [ ] chmod +x 並排入 cron:每日 02:00 執行
- [ ] 手動測試一次,確認產出檔案正常

### 任務 2.16:設定使用者自助功能
- [ ] 允許使用者自行:
  - 修改密碼
  - 設定暱稱、頭像
  - 匯出自己的對話(JSON 格式)
- [ ] 禁止使用者:
  - 修改 token 上限
  - 看到其他使用者的對話
  - 存取 admin panel

---

## Day 13:品牌客製化

### 任務 2.17:上傳承富 logo
- [ ] 向承富取得 logo(PNG,透明背景,512x512 以上)
- [ ] 放到 `client/public/assets/chengfu-logo.png`
- [ ] 修改 LibreChat client branding:
  - 登入頁顯示「承富創意整合行銷 · AI 協作平台」
  - 側邊欄 logo 用承富 logo
  - 瀏覽器 favicon 用承富 logo

### 任務 2.18:客製化登入頁文案
修改 `src/localization/languages/zh-Hant.ts` 或等效 i18n 檔:
- [ ] 登入頁標題:「承富 AI 協作平台」
- [ ] 副標:「讓 AI 成為承富的第 11 位同事」
- [ ] 歡迎訊息加上品牌口吻

---

## Day 14:驗收與週報

### 任務 2.19:本週驗收項
- [ ] 10 位同仁都能用 Cloudflare Tunnel 連上,並登入自己的帳號
- [ ] 3 種 Claude 模型都可用
- [ ] 對話歷史、全文檢索、檔案上傳都正常
- [ ] 管理後台可看到所有同仁的用量
- [ ] 自動備份已設定並運作
- [ ] 用量告警機制已運作

### 任務 2.20:產出週報
在 `reports/week-2.md` 建立報告,格式同 Week 1。

- [ ] 寄給 Sterio 與承富老闆
- [ ] 下週 Week 3 開始客製化(10 個 Preset、知識庫灌入)

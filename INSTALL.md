# 承富 AI 系統 v1.1 · 安裝指引

> **給承富 IT 看 · 5 分鐘讀完 · 30-45 分鐘裝完**

---

## 你需要什麼

### 硬體
- Mac mini M4 **24GB / 512GB**
- UPS 不斷電(APC Back-UPS 1000VA 或同等)
- 網路線(CAT6+ · 接公司路由器)

### 軟體(自動裝)
- macOS Sequoia 或更新
- Docker Desktop for Mac · <https://www.docker.com/products/docker-desktop/>
- Python 3.10+(macOS Sonoma 內建 3.9 · 跑 `xcode-select --install` 後 brew install python3.12)

### 帳號 / Key
- **Anthropic API Key** · <https://console.anthropic.com> · **預存 USD $50 升 Tier 2**
- (選配)OpenAI API Key · STT 語音轉文字
- 公司域名 · 計畫用 `ai.<承富domain>.com`
- Cloudflare 帳號 · 之後設 Tunnel 用

---

## 一鍵安裝(30-45 分鐘)

```bash
# 1. clone repo
git clone https://github.com/Sterio068/chengfu-ai.git
cd chengfu-ai

# 2. 跑安裝(會引導你輸入 API key 等機密)
chmod +x scripts/install.sh
./scripts/install.sh
```

腳本會做:
1. **環境檢查** · macOS / Docker / Git / Python / 磁碟 / RAM
2. **Keychain 機密設定** · API key / JWT / Meili / SMTP(互動式)
3. **建 .env** · 從 Keychain 注入
4. **抓 image** · 5 個 image @sha256 pinned(LibreChat / Mongo / Meili / nginx / uptime-kuma)
5. **建 accounting** · Python 3.12 + tesseract-chi-tra + 17 deps
6. **啟動全 stack** · 6 容器
7. **Healthcheck loop** · 等所有容器 healthy(最多 90 秒)
8. **Smoke test** · 8 項基礎驗證
9. **印出 IT 接手手冊** · URL + 下一步 + Sterio 聯絡

**失敗了重跑就好** · 腳本是 idempotent · 跳過已完成步驟。

---

## 安裝完成後 · IT 要做的 6 件事

```bash
# 1. 建 10 個同仁帳號
python3 scripts/create-users.py

# 2. 建 10 個 Agent(原 PDF 提案的 9 + 主管家)
python3 scripts/create-agents.py

# 3. 上傳承富知識庫(過往標書 / 結案報告 / 公司手冊)
python3 scripts/upload-knowledge-base.py

# 4. 排 launchd cron(每日備份 / 標案監測 / daily digest)
./scripts/install-launchd.sh

# 5. 設 Cloudflare Tunnel(對外網域)
#    見 docs/04-OPERATIONS.md §「Cloudflare Tunnel 設定」

# 6. 安排兩場教育訓練(全員 Onboarding + 進階分層)
#    見 docs/03-TRAINING.md
```

---

## 訪問入口(內網)

| 用途 | URL |
|---|---|
| Launcher 首頁(承富 macOS 風) | http://承富-ai.local/ 或 http://本機 IP/ |
| 健康檢查 | http://本機 IP/healthz |
| 會計 API docs | http://本機 IP/api-accounting/docs(prod 預設關 · 設 `ECC_DOCS_ENABLED=1` 開) |
| Uptime Kuma 監控 | http://本機 IP:3001(首次進建管理員) |

---

## 維運(每日)

```bash
# 看健康狀態
./scripts/smoke-test.sh

# 看 6 容器狀態
docker ps --filter name=chengfu-

# 看某容器 log
docker logs chengfu-accounting -f

# 停 / 啟
./scripts/stop.sh
./scripts/start.sh
```

---

## 災難復原

```bash
# 月度演練(備份還原)
./scripts/dr-drill.sh

# Mongo 還原
gpg --decrypt ~/chengfu-backups/daily/mongo-YYYY-MM-DD.gz.gpg | gunzip | mongorestore --archive

# Meili 還原
./scripts/restore-meili.sh ~/chengfu-backups/daily/meili-dump-YYYY-MM-DD.dump
```

---

## 遇到問題

| 問題 | 看哪 |
|---|---|
| Docker 起不來 | `docs/06-TROUBLESHOOTING.md` §「Docker」 |
| 容器某個 unhealthy | `docker logs chengfu-<容器名>` |
| LibreChat 升版 | `docs/LIBRECHAT-UPGRADE-CHECKLIST.md` |
| 認證 / 權限問題 | `docs/05-SECURITY.md` |
| 完整部署 SOP | `DEPLOY.md` |
| v1.1 工程進展 | `docs/RELEASE-NOTES-v1.1.md` |
| **找 Sterio** | sterio068@gmail.com |

---

## 安全提示

- **🔐 機密都在 macOS Keychain**(`security find-generic-password -s 'chengfu-ai-*'`)
- **`.env` 不可進 git**(已在 .gitignore)
- **prod 模式啟動會強制驗** `ECC_ENV=production` + `JWT_REFRESH_SECRET` + `ECC_INTERNAL_TOKEN` 全有 · 沒設容器啟不了
- **Cloudflare Tunnel 必加 Access policy**(Email 白名單 + 2FA)
- **資料分級 SOP** · 機敏 Level 03 不送雲端 API · 見 `docs/DATA-CLASSIFICATION-POSTER.md`

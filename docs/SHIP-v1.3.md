# 企業 AI 工作台 v1.3 · Ship Checklist

> 出貨日期:2026-04-25
> 交付對象:使用公司(10 人)· Mac mini 部署
> 路徑:跳過 dogfood · 直接 ship · 信任 auto-update 救火

---

## 0 · 出貨包含什麼

### 新功能(v1.3 vs v1.2)

| 模組 | 內容 |
|---|---|
| **任務式 FTUE**(PR #27)| 取代舊 click-through · 6 步任務式教學(welcome → compose → save → handoff → share → done)|
| **5 角色教學**(PR #27)| 老闆 / PM / 設計 / 公關 / 會計 · 各自的 priority_tasks 學習路徑 |
| **Inline tip**(PR #27)| 14 個 view 各自的 ❓ 按鈕 + 第一次自動 fade-in |
| **進度追蹤**(PR #27)| 角色 task 完成度視覺化進度條 |
| **教學搜尋**(PR #27)| 20+ index · 找不到時不用滾 sidebar |
| **系統自助更新**(PR #28)| Admin sidebar 紅點 → modal → 一鍵升級 + auto rollback |
| **每日新版檢查**(PR #28)| launchd 03:00 daily cron 自動跑 |
| **更新審計**(PR #28)| reports/update-history.jsonl · 可追每次升降 |

### Bug fix

- **PR #29** · esbuild dynamic import 字串拼接(build verify 過)
- **PR #30** · helpTip ❓ 按鈕 overlap workspace-start-btn(E2E 過)+ release-verify python venv

### 統計

```
Sprint 期間:2026-04-25(1 day)
新檔:11 (3 help modules · 1 update notifier · 1 backend update router · 3 update scripts · 1 launchd plist · 2 docs)
改檔:5 (app.js · launcher.css · onboarding.js · admin/__init__.py · release-verify.sh)
總行數:+2900 / -130
PR 數:5 (#27 #28 #29 #30 + 本檔即將是的 ship doc)
```

---

## 1 · Pre-ship 驗證(本機已過)

### Gate 1 · clean-install-verify.sh

```
═══════════════════════════════════════════
  29 / 29 passed · 0 failed
═══════════════════════════════════════════
```

涵蓋:
- ✅ 5 容器(nginx / librechat / mongo / meili / accounting)healthy
- ✅ 5 入口(healthz / launcher / lc-config / acc-healthz / manifest)200
- ✅ 13 user-guide 全 200
- ✅ admin user 已建立
- ✅ 10+ core agent 已建立
- ✅ /safety/l3-preflight L1 + L3 雙向偵測
- ✅ release-verify.sh 13/13(含 frontend build / backend pytest 249 / E2E 34)
- ✅ admin endpoint 認證(無 admin → 403)

### Gate 2 · rag-verify.sh(部署當天 IT 跑)

需要公司實際 PDF 檔(含 PDPA 限制)· 不能在 dev 機跑。

部署當天公司 IT:

```bash
mkdir -p tests/rag-fixtures/{sample-1..5}
# 每個 sample 放一份去識別化過的 PDF/DOCX
# 編輯 scripts/rag-verify.sh 的 SAMPLES_LIST · 寫正向 / 負向 query
bash scripts/rag-verify.sh
```

通過條件:5 樣本中 ≥ 4 正向 + ≥ 4 負向通過(80%)。

---

## 2 · 安裝路徑(主推一行安裝 · DMG 留 backup)

### 主路徑 A · macOS curl 一行(2026-04-25 改主推)

公司 IT 在 Mac mini 開 Terminal · 貼:

```bash
curl -fsSL https://raw.githubusercontent.com/Sterio068/company-ai-workspace/main/installer/install.sh | bash
```

優點:
- **0 macOS Gatekeeper**(沒下載 .app/.command 沒簽章問題)
- **含 Docker Desktop 檢查/安裝**(沒裝會互動確認後用 Homebrew 安裝並啟動)
- 永遠拉最新 main · 不用重打 DMG
- 6 步流程清楚 · 哪步炸看 step heading
- 自動 cp `.env` + 啟容器 + health check + 開瀏覽器

詳見 `installer/install.sh` 開頭註解。

### 主路徑 B · Windows PowerShell 一行

公司 IT 在 Windows 10/11 開 PowerShell · 貼:

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://raw.githubusercontent.com/Sterio068/company-ai-workspace/main/installer/install.ps1 | iex"
```

優點:
- **含 Git / Docker Desktop 檢查與 winget 安裝**(第一次 Docker Desktop 可能要求 WSL2 / 授權 / 重開機)
- API Key 輸入時會顯示取得網址(OpenAI / Claude / NotebookLM)
- 第一位管理員 email/password 由對方現場設定
- 機密用 Windows DPAPI 加密後放在 `config-templates/.secrets/`,不寫入 `.env` / repo / log
- 後續重啟用:
  ```powershell
  powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\CompanyAIWorkspace\scripts\start-windows.ps1"
  ```

### 備援路徑 · DMG(若 IT 無法用 curl · 例如離線部署)

```
installer/dist/Company-AI-Installer.dmg  ·  59 MB
GitHub Release · https://github.com/Sterio068/company-ai-workspace/releases/tag/v1.3.0
```

包含:
- `Company-AI-Installer.app` · 7 步 .applescript 安裝精靈
- `打開我.command` · 自動清 quarantine + 跑 .app
- `CompanyAI-source.tar.gz`(58M)· 完整 repo 快照
- `讀我.txt` · 中文 README

⚠ DMG 因沒 Apple Developer 簽章 · 第一次必須:
```bash
xattr -cr "/Volumes/企業 AI 安裝精靈/Company-AI-Installer.app"
open "/Volumes/企業 AI 安裝精靈/Company-AI-Installer.app"
```
或對 .app 右鍵 →「打開」→ 跳警告再「打開」。

---

## 3 · 公司 IT 部署 SOP(印給 IT)

### Day 0 · 前 2 天(Mac mini 到貨前)

- [ ] **API tier 升級** · console.anthropic.com → Settings → Billing → 預存 USD $50 升 Tier 2
- [ ] **Cloudflare DNS** · 開 ai.<company-ai-domain>.com 子網域(不指 IP · 留給 Tunnel)
- [ ] **10 同仁 email 列表** · 用來建 LibreChat user
- [ ] **公司既有 PDF 知識庫** · 拷到隨身碟(投標 / 結案 / SOP)

### Day 1 · Mac mini 到 → 安裝(預估 30 分鐘 · 跌停 1 小時)

1. **拆機** · 接電 + 網路 + UPS · 開機設 macOS 帳號
2. **跑 curl 一行**(會自動檢查/安裝 Docker Desktop · 第一次會要求 macOS 授權):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/Sterio068/company-ai-workspace/main/installer/install.sh | bash
   ```
3. **6 步自動跑完**:
   - Step 1 · 環境預檢(git / Docker Desktop 安裝與啟動 / disk / RAM)
   - Step 2 · git clone 到 ~/CompanyAIWorkspace
   - Step 3 · setup-keychain 互動輸 API key(OpenAI 必填)
   - Step 4 · cp .env + 啟容器(`docker compose up -d --build`)
   - Step 5 · 30 秒 warmup + health check 兩個 endpoint
   - Step 6 · 自動開瀏覽器 http://localhost
4. **建 admin user**(進 launcher 第一次 setup wizard)
5. **安裝 launchd cron**:
   ```bash
   cd ~/company-ai
   ./scripts/install-launchd.sh
   # 載入 6 plist:backup / digest / dr-drill / knowledge-cron / social-scheduler / tender-monitor / update-check
   launchctl list | grep tw.company-ai  # 應該看 7 個
   ```
6. **首次 update check**(不等 03:00):
   ```bash
   ./scripts/check-update.sh
   cat reports/update-status.json
   ```
7. **建 9 同仁 user**:用老闆 admin 登入 → 中控 → 建同仁(可批次)

### Day 1 · 知識庫匯入(預估 1 小時)

```bash
# 把 USB 上的 PDF 拷到 ~/Desktop/company-ai-kb/
# Launcher → 中控 → 知識庫 → 「新增資料源」逐一加
# 或批次:
bash scripts/upload-knowledge-base.py ~/Desktop/company-ai-kb/
```

驗證 Meilisearch 索引:Launcher → 資料 → 全文搜「中秋」(or 任一已上傳關鍵字)→ 應該有結果。

### Day 1 · Gate 2 RAG 驗證(預估 30 分鐘 · 必跑)

照 §1.2 的步驟 · 跑 5 樣本 · 填 manifest。

### Day 2 · 教育訓練(預估 2 小時)

- 上午 1 小時 · 全員 Onboarding(showup 簽到、發 user 帳號 / 密碼)
  - 走任務式 FTUE 6 步(welcome → compose → save → handoff → share → done)
  - 選自己角色 · 看自己的 priority_tasks
- 下午 1 小時 · 進階(老闆 + admin 各 1 位)
  - 用量管理 / 預算上限 / per-user quota
  - admin 看「中控」+「會計」+「商機」
  - **教 admin 看 sidebar 紅點 = 系統有新版**
  - 點紅點 → 看 commit list → 確認 → 點「立即更新」
  - 失敗會自動 rollback · 不用怕

### Day 3 · 遠端設定(選配)

- Cloudflare Tunnel + Access policy
- 2FA + Email 白名單(公司 10 同仁 email)
- 給老闆 https://ai.<company-ai>.com

---

## 4 · Day+1 Go/No-Go

部署後第二天 IT / Sterio 檢查:

| 項目 | 通過條件 |
|---|---|
| 6 容器全 running | `docker ps` |
| 10 同仁全部登入過 | `db.users.find({lastLoginAt:{$exists:true}}).count()` |
| 至少 5 同仁送過對話 | feedback collection ≥ 5 |
| 沒任何 P0 bug 卡住 | Slack / LINE 詢問 |
| Cloudflare Tunnel 可遠端連 | 老闆手機開 https://ai... 能登 |

若任一不過 → 找 Sterio · 用 auto-update 救火(改 main → 老闆點紅點 → 1 hour 內生效)。

---

## 5 · 失敗處理 / Rollback

### 安裝失敗

```bash
docker compose -f config-templates/docker-compose.yml ps
docker compose logs --tail 50
```

詳見 `docs/06-TROUBLESHOOTING.md` 21 症狀對應修法。

### 升級失敗

`update.sh` 自帶 auto rollback · 系統自動回到上一 commit。
若連 rollback 都失敗:

```bash
git log --oneline -10
git reset --hard <known-good-sha>
docker compose up -d --build
```

詳見 `docs/UPDATE.md` §6 失敗處理。

### 資料損壞 / 災難

- `scripts/backup.sh` 每日 02:00 cron 備份 MongoDB
- 還原:`scripts/restore-meili.sh <YYYY-MM-DD>`
- 詳見 `docs/04-OPERATIONS.md` RTO/RPO

---

## 6 · 後續(v1.4 候選)

照 dogfood 結果排:

- [ ] DB migration 自動偵測 + 跑(目前手動)
- [ ] Slack / LINE 通知有新版
- [ ] Beta channel(訂閱 main vs release tag)
- [ ] Email release notes 自動寄全 10 同仁
- [ ] Update history admin UI(目前 read JSONL)
- [ ] 5 + 5 canary(10 人切兩半 · 先升一半看 24h)

---

## 7 · 交付物清單

| 檔案 | 給誰 | 怎麼給 |
|---|---|---|
| `installer/dist/Company-AI-Installer.dmg`(59 MB)| 公司 IT | USB / Drive / 安全 mail |
| 本檔 `docs/SHIP-v1.3.md` | 公司 IT + 老闆 | repo 內可看 |
| `docs/UPDATE.md` | 老闆 + admin | 印 + repo 內可看 |
| `docs/03-TRAINING.md` | 全 10 同仁 | 教育訓練教案 |
| `docs/05-SECURITY.md` | 老闆 | PDPA + Keychain SOP |
| `docs/DATA-CLASSIFICATION-POSTER.md` | 全員 | A3 印 · 貼牆 |
| Anthropic API key(Tier 2)| IT 在裝機時自輸 | 不外流 |
| 10 同仁初始密碼 | 一同仁 1 紙 · 專人交付 | 不集中 mail |

---

## 8 · 簽收

```
我使用公司確認:

  [ ] DMG 安裝完成 · 6 容器 healthy
  [ ] 10 同仁 user 已建 · 都能登入
  [ ] Gate 2 RAG 驗證 · 5 樣本 ≥ 80% 通過
  [ ] 教育訓練 2 場已上(全員 + 進階)
  [ ] 知道有新版怎麼點紅點升級
  [ ] 知道升級失敗會自動 rollback
  [ ] Sterio 聯絡方式 · sterio068@gmail.com

簽收人:____________     日期:____________
公司印:____________
```

# 企業 AI · 安裝器

> Mac 原生 .app · 雙擊跑 · GUI 對話框引導 IT 輸入 .env · 不用碰 Terminal
> Windows 則提供 PowerShell 一行安裝,同樣會引導 IT 輸入 API Key 與第一位管理員密碼。

---

## Windows 一行安裝

公司 IT 在 Windows 10/11 開 PowerShell · 貼:

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://raw.githubusercontent.com/Sterio068/company-ai-workspace/main/installer/install.ps1 | iex"
```

流程:
1. 檢查 Git / Docker Desktop；缺少時用 winget 安裝。
2. 拉 GitHub repo 到 `%USERPROFILE%\CompanyAIWorkspace`。
3. 顯示 API Key 取得網址並讓 IT 貼入 OpenAI / Claude / NotebookLM key。
4. 讓 IT 現場設定第一位管理員 email/password。
5. 用 Windows DPAPI 加密保存機密到 `config-templates\.secrets\`。
6. 啟動 Docker Compose,建立第一位 admin,開 `http://localhost`。

之後重啟:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\CompanyAIWorkspace\scripts\start-windows.ps1"
```

停止:

```powershell
cd "$env:USERPROFILE\CompanyAIWorkspace\config-templates"
docker compose down
```

---

## 給公司 IT(收到 .dmg 的人)

雙擊 **`Company-AI-Installer.dmg`** · 從 Finder 視窗拖出 **`Company-AI-Installer.app`** 到桌面或 `/Applications/`。

**雙擊 `.app` 啟動**。

若這台 Mac mini 已安裝過,安裝器會先偵測既有 `config-templates/.env` 與 macOS Keychain:
- 選「沿用既有」:不重填 API Key / 網域 / admin / NAS,直接沿用既有 Mongo 帳號、對話與 Agent。
- 選「重新設定」:走第一次安裝流程,可更換 API Key、admin email、網域或 NAS。

第一次安裝或選「重新設定」時,跟隨對話框輸入(7 個步驟):

| 對話框 | 輸入什麼 |
|---|---|
| 1/7 · OpenAI API Key | 主力 AI 引擎 · 從 <https://platform.openai.com/api-keys> 拿 · `sk-...` 格式(隱藏輸入) |
| 2/7 · Anthropic API Key | Claude 備援用 · 從 <https://console.anthropic.com/settings/keys> 拿 · 可留空,前端仍可先用 OpenAI |
| 3/7 · 公司域名 | 例 `ai.company.example.com` · 留空用本機 `localhost`，仍維持 production 安全模式 |
| 4/7 · 管理員 email | 必填 · 請輸入公司管理信箱 |
| 5/7 · 管理員密碼 | 至少 8 字 · 用於第一個 admin 登入 |
| 6/7 · 顯示名稱 | LibreChat 左上角顯示名稱 |
| 7/7 · NAS 路徑 | 例 `/Volumes/company-nas/projects` · 留空用本機測試 |

設計生圖若要啟用 Fal.ai,裝完後可在中控「使用教學 → 服務金鑰管理」設定；Key 取得網址:<https://fal.ai/dashboard/keys>。

之後自動完成:
0. 若本機沒有 project repo,先從 `.dmg` 內建的 `CompanyAI-source.tar.gz` 展開新版程式碼
1. 寫入或沿用 macOS Keychain(API key + JWT + CREDS + Meili + Internal token 共 7 項)
2. 建 `.env` 或沿用既有 `.env`(只做 CR→LF 正規化)· 保留 Mongo volume 內既有資料
3. 開 Terminal 視窗(讓 IT 看 docker 進度)
4. 抓 5 個 image @sha256 pinned
5. 啟動 6 容器
6. 等 healthz 回 200(最多 90s)
7. 跑 smoke test
8. **彈最終對話框** · 印維運手冊 + 開瀏覽器到 `http://localhost/`

**失敗了?** 重雙擊 `.app` · idempotent · 選「沿用既有」會跳過已完成的帳號 / Agent 建立。若 Mongo volume 已被清空,請選「重新設定」。

---

## 給開發者(打包 .dmg 的人 · Sterio)

```bash
cd installer
./build.sh
```

產出:
- `installer/dist/Company-AI-Installer.app` · 可直接 open 測試
- `installer/dist/Company-AI-Installer.dmg` · 可 USB / mail / Slack 給 IT

**打包流程:**
1. `osacompile` 把 `Company-AI-Installer.applescript` 轉成 .app
2. 套 icon(若有 `installer/icon.icns`)
3. 改 `Info.plist` 中文名 + 版本 1.3.0
4. `hdiutil create` 包成 .dmg(含 .app + 「讀我.txt」)
5. `.dmg` 會內含 `CompanyAI-source.tar.gz`,避免 GitHub 尚未更新時安裝到舊版

**測試:**
```bash
open installer/dist/Company-AI-Installer.app
# 或
hdiutil attach installer/dist/Company-AI-Installer.dmg
# 然後從 Finder 跑
```

---

## 為什麼 .app 不是 .pkg?

| | .pkg | .app(我們的選擇) |
|---|---|---|
| GUI 對話框 | 預設無 · 要寫 InstallerJS XML | ✅ AppleScript `display dialog` 原生 |
| 隱藏密碼輸入 | 麻煩 | ✅ `with hidden answer` 一鍵 |
| 改流程 | 改 XML + Distribution.dist | ✅ 改 .applescript 重 osacompile |
| 簽名 | 必 Apple Developer Cert($99/年) | ⚠️ 可不簽 · IT 第一次跑 GateKeeper 警告 |
| 體積 | ~2-5 MB | ~50 KB(.app) · 100 KB(.dmg) |
| 維護 | 高 · XML + JS + script | 低 · 一個 .applescript |
| 適合 | 大型企業 multi-host 部署 | 一台 Mac mini · 1 次安裝 |

公司場景 = 1 台 Mac mini · IT 跑 1 次 · `.app` 完勝。

---

## GateKeeper 警告處理

第一次雙擊 `.app` · macOS 會擋:

> 「Company-AI-Installer.app」未經驗證 · 無法開啟

**繞法 A · Finder 右鍵開啟(最簡單):**
1. 在 Finder 對 `Company-AI-Installer.app` 按右鍵或 Control+點按
2. 選「開啟」
3. macOS 再問一次時,按「開啟」

**繞法 B · 系統設定放行:**
1. 關掉警告
2. 系統設定 → 隱私權與安全性 → 拉到底找「Company-AI-Installer.app 已被擋」
3. 按「強制打開」

**繞法 C · 終端機(Sterio 用):**
```bash
sudo xattr -dr com.apple.quarantine ~/Desktop/Company-AI-Installer.app
```

**根治 · v1.2 sprint:** Apple Developer ID 簽名 + notarization($99/年)

---

## 檔案結構

```
installer/
├── README.md                          ← 你正在讀
├── Company-AI-Installer.applescript   ← 安裝精靈原始碼(編 .app 來源)
├── build.sh                           ← 打包 → .app + .dmg
├── icon.icns                          ← (選填)公司 icon · 套到 .app
└── dist/                              ← build.sh 產出(.gitignore)
    ├── Company-AI-Installer.app       ← Mac 雙擊跑
    └── Company-AI-Installer.dmg       ← 分發給 IT
```

---

## 維護注意

- `.env` template 內容若改 · 同步改 `Company-AI-Installer.applescript` 的 `envContent` block
- 5 個 docker image 名若改 · 不影響 .applescript(透過 docker-compose 抓)
- repo 路徑邏輯:精靈先試 `~/Workspace/CompanyAIWorkspace` `~/CompanyAIWorkspace` `~/Desktop/CompanyAIWorkspace` `~/Documents/CompanyAIWorkspace` · 找不到就展開 `.dmg` 內建 source 快照 · 再找不到才自動 clone / 手動指定

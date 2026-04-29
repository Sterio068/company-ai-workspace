# Electron 私有自動更新 Proxy

> 目標:GitHub repository 保持 private,macOS / Windows 正式 Electron 包仍可透過自架 proxy 取得最新版。

## 架構

```text
Electron App
  -> Authorization: Bearer <proxy token>
  -> /api/updates/*
  -> accounting FastAPI update proxy
  -> Authorization: Bearer <server-side GitHub token>
  -> private GitHub Releases / assets
```

原則:
- App 不直接呼叫 GitHub private Release。
- App 只保存 update proxy URL 與 proxy token。
- GitHub token 只存在 server-side env,不可打進 app。
- Windows `latest.yml` 與 macOS `latest-mac.yml` 由 proxy 改寫 asset URL,不可指向 private GitHub asset URL。
- macOS 未簽章時只下載並開啟 DMG,不宣稱靜默覆蓋安裝。

## 伺服器設定

`config-templates/docker-compose.yml` 會把下列 env 傳給 accounting:

| env | 用途 |
|---|---|
| `VOTER_SERVICE_UPDATE_PROXY_URL` | 對 app 可連線的 update proxy base URL |
| `VOTER_SERVICE_UPDATE_PROXY_TOKEN` | App 呼叫 proxy 的 bearer token |
| `UPDATE_PROXY_GITHUB_TOKEN` | Server-side GitHub token,用來讀 private Releases/assets |
| `UPDATE_PROXY_GITHUB_REPOSITORY` | private repo,格式 `owner/repo` |
| `UPDATE_PROXY_CACHE_TTL_SECONDS` | release metadata 短快取秒數,預設 60 |

正式機請由 Keychain / DPAPI / service env 注入,不要把 token 寫入 git 或文件。

## Proxy Endpoints

所有 endpoint 都需要:

```http
Authorization: Bearer <proxy token>
```

| endpoint | 說明 |
|---|---|
| `GET /api/updates/latest?current=<version>&platform=<darwin\|win32>&arch=<arm64\|x64>` | 回最新版 metadata、是否可更新、proxy asset URL |
| `GET /api/updates/generic/mac/latest-mac.yml` | 回 macOS generic feed,asset URL 已改成 proxy |
| `GET /api/updates/generic/win/latest.yml` | 回 Windows generic feed,asset URL 已改成 proxy |
| `GET /api/updates/assets/<asset-name>` | 串流下載 private GitHub release asset |

手動「檢查更新」請加 `refresh=true` 或 `Cache-Control: no-cache`,避免 metadata cache 誤判已是最新版。

## Electron 端

新增桌面殼位置:

| 路徑 | 說明 |
|---|---|
| `desktop/src/main.cjs` | Electron main process |
| `desktop/src/preload.cjs` | 安全暴露 `companyAIUpdates.checkNow()` |
| `desktop/src/update-config.cjs` | 啟動後讀 bundled / installed `update-proxy.json` |
| `desktop/src/updater.cjs` | Windows generic updater + macOS DMG manual open |
| `desktop/electron-builder.yml` | macOS/Windows 打包設定與 `extraResources` |
| `desktop/scripts/write-update-proxy-config.mjs` | CI 由 secrets 產生 `build/update-proxy.json` |
| `desktop/scripts/rewrite-release-feeds.mjs` | 發布前改寫 `latest*.yml` asset URL 為 proxy |

Runtime 行為:
- module load 時不讀 `process.env` 當 updater 設定。
- `resolveUpdateProxyConfig(app)` 在 app ready 後讀 `Resources/update-proxy.json`。
- 第一次啟動會 seed 到 `userData/update-proxy.json`。
- 若 installed config 標記 `installerManaged:true`,下次升級會用 bundled config 覆寫。
- 若現場手動改成 `installerManaged:false`,升級時保留現場設定。

## CI Release

`.github/workflows/release-desktop.yml` 為手動 workflow:

1. macOS job 建 DMG 與 `latest-mac.yml`。
2. Windows job 建 NSIS/portable 與 `latest.yml`。
3. CI secrets 注入 `VOTER_SERVICE_UPDATE_PROXY_URL` / `VOTER_SERVICE_UPDATE_PROXY_TOKEN`。
4. `write-update-proxy-config.mjs` 產生 Electron extraResources 設定。
5. `rewrite-release-feeds.mjs` 確保 feed 內 URL 指向 `/api/updates/assets/*`。
6. `publish-release` job 上傳 asset 到 private GitHub Release。

## 驗證

本機:

```bash
npm run typecheck
npm test
npm run build
git diff --check
```

GitHub release:

```bash
gh run watch <release-run-id> --exit-status
gh release view vX.Y.Z --json tagName,isDraft,isPrerelease,assets,url
```

Proxy smoke test,請在 shell 內使用環境變數,不要把 token 貼到 log:

```bash
curl -fsS -H "Authorization: Bearer $PROXY_TOKEN" \
  "$PROXY_URL/api/updates/latest?current=0.0.0&platform=darwin&arch=arm64"

curl -fsS -H "Authorization: Bearer $PROXY_TOKEN" \
  "$PROXY_URL/api/updates/latest?current=<latest-version>&platform=win32&arch=x64"

curl -fsSI -H "Authorization: Bearer $PROXY_TOKEN" \
  "$PROXY_URL/api/updates/generic/mac/latest-mac.yml"

curl -fsSI -H "Authorization: Bearer $PROXY_TOKEN" \
  "$PROXY_URL/api/updates/generic/win/latest.yml"
```

期望:
- old version 回 `has_update:true`。
- current version 回 `has_update:false`。
- `latest.yml` / `latest-mac.yml` 回 200。
- feed 內容沒有 `github.com/.../releases/download/...` private asset URL。

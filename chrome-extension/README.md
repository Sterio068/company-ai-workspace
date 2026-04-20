# 承富 AI · Chrome Extension

讓同仁從任何網頁一鍵送內容到承富 AI。

## 功能

- **右鍵選單 · 4 種送出方式**:
  - 送到承富 AI · 主管家(智慧路由)
  - 當作標案 PDF(投標顧問)
  - 當作事實稿(公關寫手)
  - 送整頁網址(讓 AI 讀網頁)
- **快捷鍵**:選文字後 `⌘⇧C`(Mac)/ `Ctrl+Shift+C`(Win)
- **設定承富位址**:本機 / 公司內網 / Cloudflare Tunnel

## 安裝

### 開發模式(承富 IT 安裝)
1. Chrome → `chrome://extensions`
2. 右上角打開「開發人員模式」
3. 點「載入未封裝項目」→ 選 `chrome-extension/` 目錄
4. 點擴充功能 icon → 設定承富 AI 位址

### Chrome Web Store(未來)
v1.1 後上架 Chrome Web Store,10 位同仁可直接搜尋安裝。

## 典型使用情境

| 情境 | 做法 |
|---|---|
| PM 看政府電子採購網新標案 | 選標案描述 → 右鍵「當作標案 PDF」→ 投標顧問自動解析 |
| 設計看競品 IG | 右鍵「送整頁網址」→ 設計夥伴分析視覺 |
| 業務看同業新聞 | 選文字 → ⌘⇧C → 主管家判斷是否要做回應新聞稿 |
| 財務看報價 Email | 選金額 → 右鍵 → 財務試算毛利 |

## 需要 icon 檔(承富設計師產)

`icons/` 目錄下需要:
- icon16.png(16 × 16)
- icon48.png(48 × 48)
- icon128.png(128 × 128)

暫時使用 Chrome 預設圖示,上架前需替換。

## 隱私

- 擴充功能**不會**把資料傳給第三方
- 只會傳到設定的承富 AI 位址(localhost / 公司內網 / Cloudflare Tunnel)
- 不儲存歷史內容
- 權限只有 `activeTab`(只看當前分頁) + `contextMenus` + `storage`(存設定)

## 開發計畫

- v1.0:基本右鍵 + 快捷鍵 ✅
- v1.1:上下文偵測(PDF 頁自動建議投標顧問)
- v1.2:Options 頁面(可存不同 profile · 本機 / 遠端)
- v1.3:Side panel(Chrome 原生 side panel,即時對話)

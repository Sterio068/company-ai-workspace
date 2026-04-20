# docs/08-MCP-INTEGRATION.md — MCP 整合規劃

> **MCP**(Model Context Protocol):Anthropic 推的開放協定,讓 LLM 能安全地存取外部系統(Google Drive、Gmail、Calendar、資料庫等)。
>
> 承富專案透過 LibreChat 的 **Actions / Agent Tools** 機制介接 MCP server,
> 讓 Agent 直接讀寫使用者 Google 帳號內容,不用手動 copy-paste。

---

## 1. 整合範圍(依交付階段)

| 階段 | MCP | 用途 | 預估省工時 |
|---|---|---|---|
| **v1.0**(本次交付) | **Google Drive** | 從 Drive 讀檔(建議書模板、過往案例) | 每人每週 +2-3 小時 |
| **v1.1** | Gmail | 寄送 / 讀取草稿 | 每人每週 +1-2 小時 |
| **v1.1** | Google Calendar | 查詢會議、建立事件 | 每人每週 +0.5-1 小時 |
| **v1.2** | Notion / Slack(視承富實際用的工具) | 同步專案管理工具 | 視情況 |

---

## 2. Google Drive MCP(v1.0)

### 2.1 用途
承富 PM 常遇到:
> 「我要寫新建議書,想參考去年環保局那個案的結構 → 打開 Google Drive → 找檔案 → 下載 → 貼進 AI → 發問」

有 Google Drive MCP 後:
> 「@drive 找『環保局 結案報告』→ 用它當範例幫我寫新的」
> AI 直接從 Drive 讀檔案、讀完就進對話上下文。

### 2.2 部署方式

**方案 A · LibreChat Actions(v1.0 採用)**
LibreChat v0.7+ 內建「Actions」機制,可掛任何 OpenAPI spec 的 API。
Google Drive 有官方 REST API,可直接用。

步驟:
1. 承富老闆建立 Google Cloud Platform 專案
2. 啟用 Google Drive API
3. 建 OAuth Client(Web 應用程式)
   - Redirect URI: `https://ai.<公司域名>.com/api/actions/callback`
4. 下載 `client_secret.json`
5. 存入 Keychain:`chengfu-ai-google-oauth-client`
6. LibreChat admin panel → Actions → Add Action:
   - 載入 Google Drive OpenAPI spec
   - 綁定 OAuth
   - 分配給「07 公司知識庫查詢」「02 服務建議書助手」Agent

**方案 B · 官方 MCP server**
Anthropic 有釋出 `@modelcontextprotocol/server-gdrive`。
v1.0 不用,等 v1.1 評估(LibreChat MCP 整合可能更完整後再切)。

### 2.3 OAuth 範圍(最小化)
只申請:
- `https://www.googleapis.com/auth/drive.readonly`(唯讀)
- `https://www.googleapis.com/auth/drive.file`(只存取 AI 自己建立的檔案,v1.1 再開)

**不申請**:
- `drive`(全權限)
- `drive.metadata`(過度)

### 2.4 權限模型
- 每位同仁首次用 Drive MCP 時,個別授權自己的 Google 帳號
- 不是承富統一一個帳號(避免權限過大)
- OAuth token 儲存在 LibreChat MongoDB 的 user 欄位,加密存
- 同仁離職時,該 token 會隨帳號刪除(見 `docs/05-SECURITY.md` 第 5 節)

### 2.5 安全邊界
**會發生的**:
- Agent 讀取使用者 Drive 檔案內容 → 送 Claude API
- 若檔案含 Level 03 機敏,會送雲端(**使用者自己負責分級!**)

**不會發生的**:
- Agent 寫入他人的 Drive
- Agent 刪除任何 Drive 檔案(唯讀)
- Agent 分享檔案給外部

**Agent system prompt 加強句**:
```
你可呼叫 @drive 工具讀取使用者 Google Drive 檔案。
呼叫前,**必須**向使用者確認「這份檔案屬 Level 01 / 02 可送 Claude 嗎?」
若使用者標記 Level 03 或不確定,拒絕讀取,建議改為手動摘要貼上。
```

---

## 3. Gmail MCP(v1.1)

### 3.1 用途
- 「把這封草稿寄給[客戶]」
- 「整理我本週收到客戶的回信,摘要重點」

### 3.2 OAuth 範圍
- `https://www.googleapis.com/auth/gmail.compose`(建草稿)
- `https://www.googleapis.com/auth/gmail.readonly`(讀信)
- **不開** `gmail.send`(需使用者按 Send 鍵,避免誤發)

### 3.3 v1.1 部署(本次不做)
等 v1.0 穩定、承富實際評估需求後再決定。

---

## 4. 故障排查

### 4.1 OAuth 授權後立即失敗
**原因**:Redirect URI 不對。
**解法**:GCP Console → OAuth → Authorized redirect URIs 必須**精確**包含 LibreChat 的 callback URL。

### 4.2 Agent 說「我沒有存取 Drive 的權限」
**原因**:OAuth token 過期或 scope 不足。
**解法**:LibreChat UI → Settings → Actions → 該 Action → Re-authorize。

### 4.3 Drive 檔案讀取慢(> 30 秒)
**原因**:檔案太大 / Drive API rate limit。
**解法**:
- 檔案 > 10MB 建議先在 UI 下載貼上,不走 MCP
- 若 rate limit:GCP Console 申請 API quota 提升

### 4.4 同仁抱怨「我授權後每次都要重新授權」
**原因**:Refresh token 沒存下來或過期。
**解法**:LibreChat 設定確認「offline access」勾選;若仍失敗改 Long-lived token。

---

## 5. 成本影響

Google Drive API:
- 一般用量免費(Free tier 1,000 requests/100 秒/user)
- 10 人每日共用約 500-1000 requests → 免費範圍內

Gmail API:
- 一般用量免費(250 quota units/user/second)
- 10 人正常用不會超過

**結論**:v1.0 加 MCP 成本為 0(不算 GCP 專案設定時間)。

---

## 6. 實作檢核表(Sterio 照做)

### 6.1 v1.0 Google Drive(1-2 小時)
- [ ] 承富老闆建 GCP 專案(給 Sterio Editor 權限)
- [ ] 啟用 Drive API
- [ ] 建 OAuth Client(Web 應用程式)
- [ ] Redirect URI 填 `https://ai.<公司域名>.com/api/actions/callback`
- [ ] 下載 client_secret.json → `security add-generic-password -s 'chengfu-ai-google-oauth' -w "$(cat client_secret.json)"`
- [ ] LibreChat admin panel → Actions → 新增 Google Drive Action
- [ ] 測試:用自己帳號授權,在 Agent 對話中 `@drive 找我的檔案`
- [ ] 分配給「07 知識庫查詢」「02 建議書助手」兩個 Agent
- [ ] 更新 Agent instructions 加上 Level 分級確認句
- [ ] 第 1 場訓練示範

### 6.2 v1.1 Gmail + Calendar(暫不做)
等 v1.0 穩定後規劃。

---

## 7. 中長期:MCP 生態展望

Anthropic 的 MCP 生態近期增長快,未來可能加入:
- **GitHub MCP**:承富若有程式碼交付(雖然不太像),可加
- **Slack MCP**:若承富改用 Slack 溝通,整合可省下「查群組訊息」時間
- **資料庫 MCP**:承富若有 CRM 系統,可讓 AI 查客戶歷史
- **會計系統 MCP**:報價、毛利試算可直接從會計系統抓數字

v1.2+ 再評估,v1.0 不做。

---

## 8. 其他注意

- MCP 是很新的技術(2025 下半年才普及),LibreChat 支援度會持續演進
- 若 LibreChat MCP 原生支援比 Actions 機制更完整,v1.1 會切換
- 任何 MCP 新增前,必須先過「資料分級 + PDPA 告知」兩關(見 `docs/05-SECURITY.md`)

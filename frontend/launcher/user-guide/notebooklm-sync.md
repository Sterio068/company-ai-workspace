# NotebookLM 知識庫操作手冊

> 目標:讓 NotebookLM 幫團隊做深度閱讀、簡報、播客、教學與研究,但不讓它取代本地資料庫。

---

## 先記住一句話

**智慧助理 / MongoDB 是主資料庫。NotebookLM 是同步後的副本與閱讀工具。**

也就是說:

- 工作包、會議、場勘、會計、商機仍以智慧助理為準。
- NotebookLM 只讀「資料包(Source Pack)快照」,不是即時連資料庫。
- 按「同步」或直接上傳檔案時,資料會送到 NotebookLM Enterprise 雲端服務；未連線時不會送出,只保留本地紀錄。
- 同步前先預覽,確認內容與檔案範圍正確。
- 若 NotebookLM Enterprise API 尚未設定,仍可產生本地資料包,再人工貼到 NotebookLM。

---

## 適合拿去 NotebookLM 的內容

| 類型 | 適合程度 | 說明 |
|---|---:|---|
| 單一工作包摘要 | 高 | 讓 NotebookLM 幫你整理脈絡、產出簡報/問答/播客 |
| 標案 + 商機雷達 | 高 | 每週整理新標案趨勢、機關需求、可投方向 |
| 公司 SOP / 品牌語氣 | 高 | 做新人訓練與內部問答 |
| 教育訓練手冊 | 高 | 做 quiz、mind map、快速導讀 |
| 原始會議逐字稿 | 中 | 建議先讓智慧助理結構化後再同步摘要 |
| 原始會計明細 | 高 | 可直接同步；若檔案太大再拆批 |
| 完整專案資料夾 | 高 | 直接選整個資料夾,歸入該專案筆記本 |

---

## 建立資料包

1. 左側點 **NotebookLM**。
2. 在「建立 NotebookLM 資料包」選資料範圍。
3. 如果選「單一工作包」,再選工作包。
4. 選資料等級標記:預設 `完整資料`。
5. 先按 **預覽**。
6. 確認內容與範圍正確後,按 **建立資料包**。

資料包會包含:

- 標題
- 資料範圍
- 內容 hash
- 字數 / 字元數
- 建立人
- 同步狀態
- Markdown 內容

---

## 上傳單檔或整個專案資料夾

NotebookLM 頁面支援兩種直接上傳:

1. **選檔案**:可一次選多個檔案。
2. **選整個資料夾**:Chrome 會讀取資料夾內檔案與相對路徑。

歸入規則:

- 如果先選了工作包,檔案會直接進該工作包的 NotebookLM 筆記本。
- 如果選「自動判斷」,系統會用資料夾名稱、檔名、路徑去比對工作包名稱與客戶名稱。
- 一個工作包只會建立一本 NotebookLM 筆記本；後續資料包、單檔與資料夾都會歸入同一本。
- 如果 NotebookLM Enterprise 尚未連線,系統會保留本地上傳紀錄,不會把檔案送出,也不會中斷操作流程。

技術上限依 NotebookLM Enterprise 官方限制與瀏覽器上傳能力而定；過大檔案請拆批上傳。

---

## 同步到 NotebookLM

如果管理員已設定 NotebookLM Enterprise:

1. 在「最近資料包」找到要同步的包。
2. 按 **同步 NotebookLM**。
3. 系統會建立 Notebook,並把資料包當文字來源加進去。
4. 同步完成後,狀態會變成「已同步」。

如果尚未設定:

1. 按同步時不會把資料送出去。
2. 系統會顯示「Enterprise API 未設定」。
3. 你可以按 **複製 Markdown**。
4. 到 NotebookLM 手動建立 notebook 並貼上內容。

---

## 資料等級標記

資料等級只作為辨識標記,不會阻擋 NotebookLM 建立或同步；同步或上傳時仍會送到 NotebookLM Enterprise:

| 標記 | 是否可同步 | 例子 |
|---|---|---|
| L1 公開 | 可以 | 公開標案、公開新聞、公開活動資訊 |
| L2 一般 | 可以 | 已整理會議摘要、提案方向、教育訓練 |
| L3 機敏 | 可以 | 選情、未公告內情、客戶資料、帳務明細 |
| 完整資料 | 可以 | 整個專案資料夾、完整標案文件、完整會議資料 |

若 NotebookLM 官方 API 拒絕某個格式或檔案太大,請拆檔或改用資料包 Markdown。

---

## 和本地知識庫差在哪?

| 問題 | 用本地知識庫 | 用 NotebookLM |
|---|---|---|
| 我要快速找一份檔案 | ✅ | 不是首選 |
| 我要在對話中引用公司資料 | ✅ | 不是首選 |
| 我要把一整個專案做成研究 notebook | 可 | ✅ |
| 我要產生簡報、播客、教學問答 | 可 | ✅ |
| 我要回寫工作包 / 會議 / 場勘 | ✅ | 不適合 |
| 我要保存正式資料 | ✅ | 不適合 |

---

## 管理員設定

管理員可直接在 **NotebookLM** 頁面設定；access token 為寫入後不回顯。也可在部署環境設定:

```env
NOTEBOOKLM_ENTERPRISE_ENABLED=true
NOTEBOOKLM_PROJECT_NUMBER=<Google Cloud project number>
NOTEBOOKLM_LOCATION=global
NOTEBOOKLM_ENDPOINT_LOCATION=global
NOTEBOOKLM_ACCESS_TOKEN=<OAuth access token>
```

官方文件:

- Notebook API: https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks
- Sources API: https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources

建議把 access token 由前端管理員設定、Keychain 或部署腳本注入,不要寫入 git。

---

## 常見問答

### Q · NotebookLM 會直接讀 MongoDB 嗎?

不會。智慧助理先產生資料包,NotebookLM 只讀這份快照。

### Q · 資料包建錯了怎麼辦?

重新建立即可。同內容會用 hash 去重。正式資料仍在本地資料庫。

### Q · NotebookLM 裡修改內容會回寫智慧助理嗎?

不會。NotebookLM 是副本。需要正式更新時,回到智慧助理的工作包、會議、場勘或知識庫修改。

### Q · 可以把 NotebookLM 當主要知識庫嗎?

不建議。NotebookLM 適合深度閱讀與學習素材,但本系統需要權限控管、正式回寫、會計/商機/會議資料關聯、審計紀錄與可測試 API。主知識庫仍應維持本地資料庫與本地檔案索引,NotebookLM 作為「可同步副本」並行。

### Q · 可以模仿影片中的 Hermes Agent + notebooklm-py 嗎?

可以作為實驗軌,但不要當正式核心。正式交付以 NotebookLM Enterprise 官方 API 為主。

### Q · 什麼時候最值得用?

投標前、週會前、教育訓練前、需要把一堆資料整理成簡報/播客/問答時。

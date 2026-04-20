# NAS 接入規格(老闆明確:80% 檔案在 NAS)

> 取代原 Google Drive MCP 計畫。目標:同仁在對話中能直接 `@nas/...` 引用過往檔。

---

## 1. 必須承富先確認的 5 項

在工程師動手前 · 問承富:

| 項目 | 為何要問 | 未確認動工會怎樣 |
|---|---|---|
| **NAS 機型 + IP + 通訊協定** (SMB / AFP / WebDAV) | 掛載方式不同 | 掛不上或效能差 |
| **NAS 有哪些資料夾、大約容量** (e.g. `/projects` 500GB, `/kv` 200GB) | 決定哪些要索引 | 全掃會把 NAS 跟 Meili 打掛 |
| **NAS 帳密誰管、有沒有可給 AI 用的唯讀帳號** | 避免用老闆個人帳號 | 資安漏洞 |
| **同仁最常引用哪幾類檔** (建議書 / KV 原稿 / 圖庫) | 優先索引這些 | 80% 索引工作浪費在沒用的檔 |
| **NAS 有沒有每日備份 · 誰負責** | 承富 AI 不擴增 NAS 備份責任 | 承富 AI 等於背鍋 |

---

## 2. 技術規格(承富答完再看)

### 2.1 掛載

```bash
# macOS Mac mini 上
mkdir -p /Volumes/ChengFu-NAS
mount -t smbfs //<ai-ro-user>:<pwd>@<nas-ip>/<share> /Volumes/ChengFu-NAS
# 自動掛載:寫進 /etc/auto_master · 開機自動 mount
```

**帳密存哪:**
- Keychain(與其他機敏同位置):`chengfu-ai-nas-user` / `chengfu-ai-nas-password`
- `start.sh` 啟動時讀出,環境變數給 accounting 容器

### 2.2 檔案索引(Meili)

**首批索引範圍**(承富答完 5 項才填):
```
/Volumes/ChengFu-NAS/projects/**/*.docx    <- 建議書
/Volumes/ChengFu-NAS/projects/**/*.pdf     <- 招標附件
/Volumes/ChengFu-NAS/kv/**/*.ai            <- KV 原稿(讀不了,只記 metadata)
/Volumes/ChengFu-NAS/photos/**/*.jpg       <- 活動照片(之後做 CLIP vision 索引)
```

**索引 schema** (`backend/accounting/nas_index.py` 會做 cron):
```python
{
    "path": "/Volumes/ChengFu-NAS/projects/2024-淨灘案/建議書v3.docx",
    "filename": "建議書v3.docx",
    "project": "2024-淨灘案",
    "content_preview": "承富創意...(前 2000 字)",
    "size": 1284392,
    "modified_at": "2024-03-15T10:23:00",
    "mime": "application/vnd.openxmlformats...",
}
```

**索引策略:**
- 每日凌晨 02:00 增量 scan(比對 mtime)
- 純文字類(.txt/.md/.docx/.pdf)抓前 2000 字進 Meili
- 圖/設計檔只記 metadata
- **不** 存檔案內容到 Mongo (NAS 永遠是 source of truth)

### 2.3 API 端點

```python
# backend/accounting/main.py 新增
@app.get("/nas/search")
def nas_search(q: str, project: Optional[str] = None, limit: int = 10):
    """Meili 全文搜尋 NAS 索引"""

@app.get("/nas/read")
def nas_read(path: str):
    """取回檔案純文字內容(讓 Agent 讀 build 建議書引用)
    · 只允許 /Volumes/ChengFu-NAS 底下的路徑
    · 避免 path traversal 攻擊
    """
```

### 2.4 Agent Action

`config-templates/actions/nas-reader.json`(OpenAPI schema):
```json
{
  "info": { "title": "承富 NAS 檔案讀取", "version": "v1" },
  "paths": {
    "/nas/search": {
      "get": {
        "summary": "搜 NAS 全文",
        "parameters": [{"name":"q","in":"query","required":true,"schema":{"type":"string"}}]
      }
    },
    "/nas/read": {
      "get": {
        "summary": "讀 NAS 檔案純文字",
        "parameters": [{"name":"path","in":"query","required":true,"schema":{"type":"string"}}]
      }
    }
  }
}
```

投標顧問 / 設計夥伴 / 結案營運 的 Agent 都可 attach 這個 Action · prompt 加指示「看過往案例先 `/nas/search`」。

---

## 3. 預估工時(需 NAS 訪問才能準)

| 項目 | 樂觀 | 悲觀 | 備註 |
|---|---|---|---|
| 確認 5 項 + 建 ro 帳號 | 0h(承富) | 2h | 要承富做 |
| macOS 自動掛載設定 | 1h | 3h | SMB 掛穩就好 |
| `nas_index.py` 增量 scan + Meili | 4h | 8h | 檔多 scan 慢 |
| `/nas/search` + `/nas/read` API + path traversal guard | 2h | 4h | |
| Agent Action schema + attach | 1h | 2h | |
| 測試 + 文件 | 2h | 4h | |
| **合計** | **10h** | **23h** | 比原 ROADMAP 的 10-14h 保守 |

---

## 4. 不做的事(明確界線)

- **寫檔案到 NAS** — 讀是唯讀 · 要寫請同仁手動
- **NAS 備份** — NAS 自己要備份,承富 AI 不擔這個
- **索引所有檔** — 只索引承富答案指定的資料夾
- **Vision 索引圖片** — v1.1 + CLIP 再做

---

## 5. 真正開工前的 Checklist

- [ ] 承富確認 5 項問題
- [ ] NAS ro 帳號建好 + 密碼進 Keychain
- [ ] 承富 IT 確認「AI 掛 NAS」不違反內部 policy
- [ ] 工程師在 staging NAS(或測試資料夾)先跑一遍 indexer
- [ ] Meili index 大小評估(< 5GB 就 OK)
- [ ] 確認 Agent Action 不會讓 LLM 誤叫到 traversal
- [ ] 正式上線前 · 先只開 PM / Champion 試用一週

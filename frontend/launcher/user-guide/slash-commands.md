# ⌨️ Slash 命令 + 快捷鍵 完整表

> 對話框打 `/` 觸發 · 或全域鍵盤跳 view
> 都記住 · 速度快 3 倍

---

## ⌘ 全域鍵盤(任何畫面)

| 快捷 | 動作 |
|---|---|
| `⌘K` | 開全域 palette · fuzzy search 跳任何 view / Agent / project |
| `⌘0` | 跳 🏠 首頁 dashboard |
| `⌘1` | 跳 🎯 投標 workspace |
| `⌘2` | 跳 🎪 活動執行 workspace |
| `⌘3` | 跳 🎨 設計協作 workspace |
| `⌘4` | 跳 📣 公關溝通 workspace |
| `⌘5` | 跳 📊 營運後勤 workspace |
| `⌘P` | 跳 📁 專案 |
| `⌘L` | 跳 📚 技能庫(SKILL list) |
| `⌘A` | 跳 💰 會計 |
| `⌘T` | 跳 📢 標案 |
| `⌘I` | 跳 💼 商機 Pipeline(CRM) |
| `⌘W` | 跳工作流程(workflows) |
| `⌘M` | 跳 📊 管理面板(admin only) |
| `⌘⇧L` | 切深淺色(auto → light → dark) |
| `?` | 顯示鍵盤快捷 overlay |
| `Esc` | 關 modal / palette / drawer |

---

## ⌘K palette 用法

按 `⌘K` 跳 palette · 打字 fuzzy search:
- 「投」→ 投標相關 view + agents
- 「環保」→ 找含此字的 project / 知識庫文章
- 「邦邦」→ 找 user / Agent 名

palette 內按 `Enter` 跳 · `↑↓` 選 · `Esc` 關。

---

## /命令(對話框內 · 任何 Workspace)

格式:對話框打 `/xxx` · Enter 觸發

### 投標 workspace
| /命令 | 對應 Agent / 功能 |
|---|---|
| `/bid` | 招標須知解析(01) |
| `/draft` | 服務建議書初稿(02) |
| `/visual` | 競品視覺研究(24) |

### 公關溝通 workspace
| /命令 | 對應 |
|---|---|
| `/news` | 新聞稿生成(04) |
| `/social` | 社群貼文生成(05) |
| `/meet` | 會議速記(06 + Whisper) |

### 設計協作 workspace
| /命令 | 對應 |
|---|---|
| `/brief` | 設計 Brief 結構化(21) |
| `/design` | AI 圖像生成(27 · Fal Recraft v3) |
| `/visual` | 主視覺概念發想(20) |

### 營運後勤 workspace
| /命令 | 對應 |
|---|---|
| `/report` | 結案報告助手(03) |
| `/quote` | 報價毛利試算(15) |
| `/crm` | CRM 紀錄(17) |
| `/contract` | NDA / 合約模板(18) |
| `/tax` | 稅務諮詢(08) |

### 全域(任何 workspace)
| /命令 | 對應 |
|---|---|
| `/know` | 知識庫查詢(07) · 跨 workspace 找資料 |
| `/email` | Email 草稿生成(26) |
| `/vendor` | 廠商比價表(10) |

---

## 進階 · 對話內小技巧

### Markdown 支援
- ` `` ` 代碼
- `**粗體**`
- `> 引用`
- `1. 項目`(自動有序列)
- ```` ```python ```` (語法 highlight)

### 拖曳檔案上傳
- 對話框 drag & drop · PDF / docx / pptx / xlsx / 圖片
- 上限 50MB / 個 · 多檔可
- 上傳後 Agent 自動讀(file_search · v1.0 設計)

### 中斷 streaming
- Agent 講太久 · 右下 ⏹ 按一次停
- 已產生內容保留 · 可繼續對話

### Regenerate
- 不滿意 · 訊息底下 ↻ 點重新產(同 prompt 不同 sample)

### 👍👎 回饋(R6#5)
- 訊息下方 👍 / 👎 · 收進 admin feedback stats
- 👎 可加 note 說明哪裡不好(>= 3 次同 Agent 月報自動列改進建議)

---

## URL hash 跳轉(不用點 sidebar)

直接打網址:
- `https://launcher/#meeting` → 跳會議速記
- `#site` → 場勘
- `#admin` → 管理面板(若你 admin)
- `#help` → 此說明頁

放書籤:常用的功能加 hash 存書籤。

---

## 常見問

### Q · ⌘K 沒反應
- 焦點是否在 input 框內(內部捕捉了)
- 點空白處再按
- 確認瀏覽器沒 extension 攔截 ⌘K

### Q · /命令打了沒跳 Agent
- 確認對話框是空的(已有文字 / 不會 trigger)
- 確認 / 開頭 · 沒空格
- 不認識的 / 命令 · 當普通文字送

### Q · 我想加自定 / 命令
- 改 `frontend/launcher/modules/config.js` 的 SLASH_COMMANDS
- 各 view 對應 → app.slashCmd handler
- 改完重整 launcher

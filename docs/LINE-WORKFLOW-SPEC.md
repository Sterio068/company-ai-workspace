# LINE 工作流規格(老闆明確:檔案來源之二)

> 目標:同仁從 LINE 群組 / 跟客戶的對話,最短路徑送到 AI · 避免複製貼上 10 次。

---

## 1. 現況與痛點

- 承富 80% 訊息來自 LINE 群組 + 跟客戶 1-1 LINE
- 同仁處理 LINE 訊息的典型動作:
  1. 看到客戶訊息
  2. 想該怎麼回
  3. 切到瀏覽器打開承富 AI
  4. 複製 LINE 訊息 · 貼到對話框
  5. 打自己的問題 + 送出
  6. 複製 AI 回答 · 切回 LINE
  7. 貼上 · 送出
- 痛:**7 步都是手動,每則訊息耗 5 分鐘**

---

## 2. 方案(按優先序)

### 方案 A · 瀏覽器 LINE Web + Chrome Extension(v1.1 主推)

**情境:** 同仁用 <https://line.me> LINE Web

**Extension 行為:**
- 在 LINE 訊息旁加「🤖 丟承富」按鈕
- 點一下 · 自動開承富 AI 新分頁 · 訊息已 pre-fill
- 同仁只需補「幫我回」等指令 + Enter

**技術:**
- Manifest v3 Chrome Extension
- Content script 偵測 LINE 訊息 DOM · 插入按鈕
- Background script 開新分頁 `http://localhost/?pending=<urlencoded>`
- Launcher 已支援 `?pending=` query param(`app.js` 已實作)

**工時預估:** 8-12h(比原 4-6h 誠實)
- Manifest + permissions: 1h
- Content script DOM 注入 · LINE Web 改版會壞 · 要抗改版: 3-4h
- URL 轉發 + URL encode: 1h
- Extension icon / 設定頁: 1h
- 測試(多個瀏覽器 / LINE Web 改版): 2-4h
- 文件 + 安裝指引: 1h

**注意:** LINE Web 沒有正式 API · 靠 DOM scrape · 一年可能得修 1-2 次(LINE Web 改版)。

### 方案 B · LINE 手機版 Share Sheet(v1.2 · 複雜度高)

**情境:** 同仁手機用 LINE app

**可行性:**
- iOS / Android LINE app 的 Share Sheet 允許分享到自訂 app
- 需要建承富 AI 的 iOS/Android wrapper (PWA + Add to Home Screen 可以取巧)
- 承富 AI Launcher 做 PWA manifest(v4.0 已建立但 dev 階段關掉了)

**工時:** 16-24h · 不建議 v1.0 做

### 方案 C · 貼上偵測(簡單、立刻可做)

**情境:** 不裝 extension,同仁手動貼 LINE 訊息

**邏輯:** 在 launcher 輸入框加 `onpaste` handler 偵測 LINE 格式,自動:
- 去除時間戳(`14:32`、`今天`)
- 合併多行成段落
- 移除系統訊息(`已讀`、`XXX 離開群組`)
- 保留 `@提及` 但轉中文

**工時:** 2-3h(今天就能做)

---

## 3. 建議順序

1. **v1.0 立刻做:** 方案 C · 貼上偵測(2-3h)· 低成本 · 全員受惠
2. **v1.1 (1-2 週內):** 方案 A · Chrome Extension(8-12h)· Champion + PM 先試用
3. **v1.2 (未來):** 方案 B · 手機 LINE 分享 · 看 Champion 回饋需求度

---

## 4. 方案 C · 貼上偵測實作細節

### 前端 · `modules/line-paste.js` 新檔

```js
/**
 * 偵測 LINE 貼上格式 · 自動清理時間戳 / 系統訊息
 *
 * LINE 常見格式:
 *   [LINE] 承富 AI 討論
 *   2026/04/21 (三)
 *   ----------------
 *   14:32 Alice  客戶說下週要更新
 *   14:33 Bob    OK,我處理
 *   14:35 Alice  記得加ESG那段
 */
const LINE_PATTERNS = {
  header: /^\[LINE\]|^\-{3,}$/,
  dateLine: /^\d{4}\/\d{1,2}\/\d{1,2}/,
  messageLine: /^(\d{1,2}:\d{2})\s+(\S+)\s+(.+)$/,
  systemLine: /^(.+)(加入|離開|已讀|unsent).*$/,
};

export function cleanLinePaste(raw) {
  if (!raw.includes("[LINE]") && !raw.match(/^\d{1,2}:\d{2}\s/m)) {
    return raw;  // 不是 LINE 格式,不處理
  }
  const lines = raw.split("\n");
  const cleaned = [];
  for (const line of lines) {
    const t = line.trim();
    if (!t || LINE_PATTERNS.header.test(t) || LINE_PATTERNS.dateLine.test(t)) continue;
    if (LINE_PATTERNS.systemLine.test(t)) continue;
    const m = t.match(LINE_PATTERNS.messageLine);
    if (m) {
      const [, time, speaker, msg] = m;
      cleaned.push(`${speaker}:${msg}`);
    } else {
      cleaned.push(t);
    }
  }
  return cleaned.join("\n");
}

export function bindPasteListener(textareaId) {
  const ta = document.getElementById(textareaId);
  if (!ta) return;
  ta.addEventListener("paste", (e) => {
    const text = e.clipboardData?.getData("text/plain");
    if (!text) return;
    const cleaned = cleanLinePaste(text);
    if (cleaned === text) return;  // 不是 LINE 格式
    // 只清理,不取代原事件(讓使用者自己決定要不要修)
    e.preventDefault();
    const start = ta.selectionStart;
    ta.value = ta.value.slice(0, start) + cleaned + ta.value.slice(ta.selectionEnd);
    ta.selectionStart = ta.selectionEnd = start + cleaned.length;
    // Toast 提示
    import("./toast.js").then(({toast}) => toast.info("偵測到 LINE 格式 · 已自動清理時間戳"));
  });
}
```

### 啟用

`modules/chat.js` 的 `open()` 裡呼叫:
```js
import { bindPasteListener } from "./line-paste.js";
// ... in open() after input focus:
bindPasteListener("chat-input");
```

### 測試

貼這段 LINE 範例驗證:
```
[LINE] 承富 AI 討論
2026/04/21 (三)
---------------
14:32 Alice 客戶說下週要更新建議書
14:33 Bob OK,我處理
14:34 Alice 加入已讀
```

應該變成:
```
Alice:客戶說下週要更新建議書
Bob:OK,我處理
```

---

## 5. 不做的事

- **不做 LINE bot** — 承富 AI 是內部工具 · LINE bot 會暴露對話到 LINE Server
- **不轉發客戶 LINE 訊息到對外** — 純內部處理
- **不存 LINE 原文到 Mongo** — 只存同仁處理後的 prompt

---

## 6. 隱私提醒(納入教學手冊)

同仁貼 LINE 客戶訊息到 AI 前 · 基本認知:
- 訊息會送到 Claude 雲端(L2 處理)· 可接受
- **客戶個資(身份證 / 私人電話)要先去除**
- 客戶商業機密(還沒公開的活動、合約內容)須用同仁判斷 · 系統不替你決定(L3 先不硬擋)

這段請寫進 `docs/HANDBOOK/02-PM.md` 與 `docs/HANDBOOK/04-SALES.md` 的「LINE 貼上」tips 底下。

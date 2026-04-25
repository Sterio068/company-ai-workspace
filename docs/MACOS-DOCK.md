# macOS Dock 使用手冊(v1.4 Sprint A)

> 承富智慧助理 v1.4 開始 · 底部新加 macOS 風 Dock。
> 預設放 7 個常用 AI 助手 · 滑鼠 hover 會放大 · 點擊開對話。

---

## 你會看到什麼

```
┌───────────────────────────────────────────────┐
│                                                │
│         (此處是你正在用的 view)              │
│                                                │
│                                                │
│   👑   🎯   📅   🎨   📣   📈   📚            │
│  主管家 投標 活動 設計 公關 財務 知識           │
│            ⚪ 點亮 = 此助手有 active 對話      │
└───────────────────────────────────────────────┘
```

正中央底部浮現的就是 Dock · 7 個高質感漸變色 squircle icon。

---

## 7 個預設助手

| icon | 名字 | 編號 | 用途 |
|---|---|---|---|
| 👑 | 主管家 | #00 | 跨工作區協調 · 不知道找誰問就找它 |
| 🎯 | 投標顧問 | #01 | 招標須知解析 · 服務建議書 |
| 📅 | 活動策劃 | #02 | 場景 brief · 動線 · 流程 |
| 🎨 | 設計夥伴 | #03 | 主視覺 · 配色 · Fal.ai 生圖 |
| 📣 | 公關文案 | #04 | 新聞稿 · 社群 · Email |
| 📈 | 財務報價 | #06 | 專案報價 · 毛利試算 |
| 📚 | 知識查手 | #09 | 全文搜尋公司 NAS / 過往標書 |

---

## 操作方式

### 鼠標

| 動作 | 結果 |
|---|---|
| Hover | icon 放大(高斯衰減 · 鄰近 icon 連動) |
| 左鍵點 | 開該助手對話 |
| **右鍵** | 跳 macOS 風 menu(開啟 / 從 Dock 移除 / 顯示資訊) |
| **拖曳** | 重新排序 · 拖到別的 icon 上會交換位置 |

### 鍵盤 a11y

按 Tab 進到 dock(從 launcher 內某 button 連按 Tab)· 第一個 icon focus:

| 按鍵 | 動作 |
|---|---|
| ← / ↑ | 上一個 icon |
| → / ↓ | 下一個 icon |
| Home | 第一個 |
| End | 最後一個 |
| Enter / Space | 開該助手對話 |
| Delete / Backspace | 從 Dock 移除 |
| Shift+F10 | 開 context menu(等同右鍵) |
| Esc | 離開 dock(blur) |

---

## 自訂 Dock

### 移除助手

- 右鍵 icon → 從 Dock 移除
- 或鍵盤 focus + Delete

### 加回助手

目前(Sprint A)沒 UI 直接加 · 需:

```js
// 開 DevTools console
window.dock.dockStore?.pin("agent", "07", { label: "法務合約", icon: "📄", color: "#FF3B30" });
```

Sprint B 會做「Pin to Dock」按鈕(在每 agent 對話畫面右上角)。

### 重設成預設 7 個

```js
// DevTools console
window.dock.dockStore?.reset();
```

---

## Dock 在哪些頁面顯示

| View | 顯示? |
|---|---|
| 首頁 / Today | ✅ |
| 工作包 / 知識庫 / 教學 | ✅ |
| 工作區(投標 / 活動 / 設計 / 公關 / 營運) | ✅ |
| 中控 / 商機 / 會計 | ✅ |
| 對話畫面(Chat / LibreChat) | ❌ 隱(LibreChat 自有 sidebar · 重複) |
| 手機 < 768px | ❌ 隱(已有 mobile bottom nav) |

---

## PWA 模式 + 頂部 Menu Bar(Sprint B 才完整)

把承富智慧助理加到 macOS Dock(Chrome / Safari):

### Chrome / Edge
1. 進 http://localhost(或承富域名)
2. 右上角 ⋮ → **「安裝『承富智慧助理』」**
3. 之後從 Launchpad / Spotlight 開 · 變獨立 app

### Safari
1. 進 http://localhost
2. 分享 (□↑) → **「加入主畫面」**(macOS Sonoma+)

進 PWA 模式後:
- ✅ 全螢幕 · 無瀏覽器 chrome
- ✅ Dock 顯示(同瀏覽器版)
- 🔜 **頂部 Menu Bar 出現**(Sprint B render 內容 · 目前空)

---

## 常見問題

### Q: Dock 怎麼不見了?

可能原因:
1. **手機**:< 768px 自動隱 · 用底部 mobile nav
2. **Chat view**:對話畫面隱 · 退出對話即出現
3. **localStorage 被清**:重新整理會自動載入 default 7 個
4. **JS 錯誤**:F12 看 Console

### Q: Hover 不放大 / 動畫卡?

- 系統「減少動態效果」開了:System Settings → Accessibility → Reduce Motion
- prefers-reduced-motion 偵測到 · dock 會跳過動畫(設計上的)

### Q: 拖曳沒反應?

- HTML5 native DnD 在 iPad 不支援(macOS Safari 完美)
- 桌面版 Chrome/Safari/Firefox/Edge 都 OK

### Q: 我把所有 icon 都移掉了?

DevTools console:
```js
window.dock.dockStore?.reset();
```

---

## 開發者 · 內部 API

```js
import { dockStore } from "/static/modules/state/dock-store.js";

// 看目前
dockStore.getItems();

// 加
dockStore.pin("agent", "07", { label: "新助手", icon: "🌟", color: "#FF3B30" });

// 移
dockStore.unpin("agent", "07");

// 重排
dockStore.reorder(0, 6);  // 把第 0 個移到最後

// 重設
dockStore.reset();

// 訂閱變動
const unsub = dockStore.subscribe(items => console.log("dock changed", items));
unsub();  // 取消訂閱
```

---

## 後續計畫(Sprint B)

- [ ] 頂部 Menu Bar 內容(承富 / 檔案 / 編輯 / 顯示 / 視窗 / 說明)
- [ ] PWA 自動安裝提示
- [ ] Window 系統(對話 = 獨立 window · cmd+W 關 · cmd+M 最小化)
- [ ] Mission Control overview(cmd+↑ 看所有對話)

## Sprint C(完美層)

- [ ] Notification Center(右滑出)
- [ ] Control Center(模型切 · 主題切)
- [ ] macOS keyboard shortcuts 全套
- [ ] 細節 polish(spring 尾韻 / cursor effect)

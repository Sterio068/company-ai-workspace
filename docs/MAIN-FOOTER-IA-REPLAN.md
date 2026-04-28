# 主畫面 + 底頁 IA 重新規劃 · macOS 風推進

> 出檔:2026-04-26
> 範圍:重新設計 launcher 主畫面(現 dashboard view)+ 底頁(原 caption 已收 · 留空)
> 目標:更貼近 macOS 真原生體驗 · 3 方案讓你選

---

## 0 · 現狀盤點

### 現主畫面結構(v1.4.0)
```
┌─ menubar(藍底白字 28px)
├─ sidebar(260px)│ main(1fr)
│                │ ├ greeting + 本週激勵
│                │ ├ 今日 composer(大輸入框)
│                │ ├ 5 workspace 卡片 grid
│                │ ├ 最近對話 list
│                │ └ 用量小卡
└─ dock(底部居中)
```

### 痛點
1. **資訊堆疊** · greeting + composer + workspace + recent 全擠首屏
2. **重複 sidebar** · 5 workspace 卡片 vs sidebar「流程模板」5 入口
3. **不像 macOS native** · 像一般 SaaS dashboard
4. **底頁空白** · caption 拿掉後 dock 上方一片空 · 浪費

---

## 1 · 三方案總覽

| 方案 | macOS 原生比喻 | 強項 | 風險 |
|---|---|---|---|
| **A** Finder 視圖 | macOS Finder window | 階層清楚 · IT-friendly | 偏工具感 · 老闆 demo 不 wow |
| **B** Stage Manager | macOS Sonoma Stage Manager | 多對話並列 · 工作流可見 | 需配 Window 系統(v1.5)· 過度抽象 |
| **C** Today + Launchpad ⭐ | macOS Today widget + Launchpad | 商務感 + 實用 + macOS 風 | 仍是 dashboard · 但結構清楚 |

---

## 2 · 方案 A · Finder 視圖

### 結構圖
```
┌─ menubar
├─ ─────────────────────────────────────────────
├─ sidebar │ ┌ Finder toolbar(工作區 tabs · 視圖切換 · 排序)
│          │ ├ Path bar(麵包屑 · 主畫面 > 投標 > 中秋案)
│          │ ├ Main(grid view of 對話 / 工作包 · 像 Finder 圖示)
│          │ └ Status bar(N 個項目 · 排序方式 · 已選 X)
└─ dock
```

### Main 區內容
- **Toolbar**(40px)· 切換 Icon View / List View / Column View
- **5 個 segments** · 全部 / 投標 / 活動 / 設計 / 公關 / 營運
- **Main grid** · 每個對話 = 一個圖示卡(縮圖 + 標題 + 日期)
- **Path bar**(28px)· 顯示當前位置 · 可點上一層

### 底頁
**macOS Finder status bar**(24px · 灰底)
```
─────────────────────────────────────────
 12 個工作包 · 7 GB 知識庫 · 排序:近用優先  ⌘1-5 切工作區
─────────────────────────────────────────
   👑 🎯 📅 🎨 📣 📈 📚  (Dock 在 status bar 上方)
```

### 適合
- 給 IT / admin 用 · 像 macOS Finder 自然
- 對話多時(>50)· 階層瀏覽方便
- 不適合 demo(老闆看不出 wow)

---

## 3 · 方案 B · Stage Manager 風

### 結構圖
```
┌─ menubar
├─ sidebar │ ┌─────────────────┬───────────────┐
│ │ Stage  │  Active Stage    │  Inspector    │
│ │ Stack  │  (current chat   │  (context     │
│ │        │   full attention) │   panel)      │
│ │ ▲ A    │                  │               │
│ │ ▲ B    │                  │               │
│ │ ▲ C    │                  │               │
│ │ ▲ D    │                  │               │
└─ dock
```

### 解釋
- **Stage Stack**(左側 96px)· 每個進行中對話一個小縮圖 · 點切換
- **Active Stage**(主區)· 當前對話放大 · 全注意力
- **Inspector**(右側 280px · 可收)· 該對話的 context (素材/連結)

### 底頁
**macOS Sonoma Workflow bar**(36px · 含 stage tabs 縮圖)
```
─────────────────────────────────────────
 □ □ □ □ □  ← Active stages 縮圖 · 點切換
─────────────────────────────────────────
   👑 🎯 📅 🎨 📣 📈 📚  (Dock 在 workflow bar 上方)
```

### 適合
- 同時跑多對話(設計師 + PM 並行)
- 視覺有 wow factor · 老闆 demo 印象深
- **需 v1.5 對話多開 + Window 系統才完整** · 現在做太空

---

## 4 · 方案 C · Today + Launchpad ⭐ 推薦

### 結構圖
```
┌─ menubar
├─ sidebar │ ┌─────────────────────────────────┐
│ │       │  🌅 Today (上 35%)                │
│ │       │  ┌─ Hero · 大時間 + 問候          │
│ │       │  ├─ 今日活動 widget(3 cards)      │
│ │       │  │  • 今日對話 N 次               │
│ │       │  │  • 本週省 X 小時               │
│ │       │  │  • 待回應 N 件                  │
│ │       │  └─ 大 composer(主輸入)          │
│ │       │                                    │
│ │       │  🚀 Launchpad (下 65%)            │
│ │       │  ┌─ 最近用 5 個 agent(快速啟動)   │
│ │       │  ├─ 收藏的工作包(過期暗化)        │
│ │       │  └─ 5 workspace 大圖卡            │
└─ dock(底部固定)
   ↑ status bar(28px · macOS 風)
```

### Main 區詳細
**上半 · Today**(35vh)
- **Hero** · 大鐘(類 macOS Today widget)+ 「早安 Sterio」
- **3 widget 橫排** · 今日活動 / 本週節省 / 待辦 (玻璃 vibrancy 卡片)
- **大 composer** · 中央輸入框 +「交給主管家」按鈕

**下半 · Launchpad**(65vh)
- **最近用 5 agent** · 大方塊(SVG icon + 名 + 上次用時間)
- **收藏的工作包** · 4 個橫排卡片
- **5 workspace 大圖卡** · 漸變色 + icon + 描述 + 「進入」按鈕

### 底頁 · macOS Status bar(28px)
**Dock 上方多一條 status bar**(像 macOS Finder bottom)
```
─────────────────────────────────────────
 🟢 6 容器 healthy │ 用量 $0.45 / $20 月 │ 2 待回應 │ 同步:剛剛 │ ⌘K 快速搜
─────────────────────────────────────────
   👑 🎯 📅 🎨 📣 📈 📚  (Dock)
```

Status bar 內容:
- **連線狀態**(🟢/🟡/🔴)
- **用量**(今日/月度)
- **待辦**(待回應對話 N 件)
- **同步**(最後 sync 時間)
- **提示**(常用快捷)

### 適合
- 既有商務感 · 又像 macOS native
- 老闆一打開:時間 + 鼓勵 + 一個輸入框 = 進入工作狀態
- 同仁日用:點 Launchpad agent 直接開
- **不需新功能** · 純 UI 重組

---

## 5 · 對比表

| 維度 | A Finder | B Stage Mgr | C Today+Launchpad ⭐ |
|---|---|---|---|
| macOS 原生感 | 8/10 | 9/10 | 9/10 |
| Wow factor(老闆 demo)| 5/10 | 9/10 | 8/10 |
| 同仁日用 friction | 4/10 | 6/10 | 9/10 |
| 需 v1.5 配合 | ❌ 不需 | ✅ Window 系統 | ❌ 不需 |
| 工(估)| 1.5 天 | 3-4 天 | 2 天 |
| 風險 | 低 | 高(撞 chat.js)| 低(純 UI 重組)|

---

## 6 · 我推 · 方案 C(Today + Launchpad)

理由:
1. **不需 v1.5 配合** · 現有資料 + 元件夠用
2. **2 天交付** · 跟 v1.4 一樣快節奏 ship v1.5.0
3. **底頁 status bar** 解 caption 留空問題 · 實用資訊
4. **Hero 大時鐘 + 問候** · 老闆早上開立即上手
5. **Launchpad 區** 自然取代「workspace cards 重複 sidebar」

---

## 7 · 三方案 mockup HTML 預覽

我已準備 3 個 standalone HTML(可直接 file:// 開):

```
docs/mockups/
├── plan-a-finder.html         · macOS Finder 風
├── plan-b-stage-manager.html  · Stage Manager 風
└── plan-c-today-launchpad.html · Today + Launchpad ⭐
```

```bash
# 你 mac mini 預覽 3 個
open docs/mockups/plan-a-finder.html
open docs/mockups/plan-b-stage-manager.html
open docs/mockups/plan-c-today-launchpad.html
```

每個 mockup:
- 完整 macOS Sequoia 視覺
- 含 menubar + sidebar + main + dock + status bar
- 假資料 + 實互動(hover / 切換)
- 看了立刻知道是不是你要的方向

---

## 8 · 你拍板 → 我做

選一條:
- **「A」** · Finder 風(IT 工具感)· 1.5 天
- **「B」** · Stage Manager(等 v1.5 對話多開)· 3-4 天
- **「C」** · Today + Launchpad(現在做)· 2 天 ⭐
- **「D 客製」** · 三方案混搭 · 告訴我要哪些元素

或先看完 mockup 再決定。

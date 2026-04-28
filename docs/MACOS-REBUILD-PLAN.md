# macOS 風重構 · 完整規格(v1.4 sprint)

> 確認的範圍:**1A · 2C · 3B(改動)**
> - 1A · Dock 在底部
> - 2C · Menu bar 只在 PWA 全螢幕模式才出
> - 3B · 沿用 vanilla JS · **加 Motion One**(GSAP 暫不引入 · architect 建議簡化)

---

## 0 · 全範圍時程(3 sprint · 2-3 週)

| Sprint | Phase | 工 | 交付 | Release |
|---|---|---|---|---|
| **A · 視覺** | 1 tokens · 2 Dock | **2-3 天**(現實 14hr 純 code + CI/PR/QA) | macOS 風 + Dock 起來 | v1.3.1 |
| **B · 結構** | 3 menubar · 4 windows | 4-5 天 | 完整 macOS 殼 | v1.4.0 |
| **C · 完美** | 5 NC/CC · 6 shortcuts · 7 polish | 2-3 天 | 細節到位 | v1.4.1 |

> **Issue 4 修(USER 視角)**:原 1.5-2 天太樂觀(沒算 PR / CI / QA / 你 review 時間)· 改 2-3 天

本檔 = **Sprint A 完整規格**(Phase 1 + 2)· Sprint B/C 寫骨架後續細化。

---

## 1 · 視覺基礎決策(Phase 1 · 4 hr)

### 1.1 字型 stack(Apple official)

```css
--font-system: -apple-system, BlinkMacSystemFont,
               "SF Pro Display", "SF Pro Text",
               "PingFang TC", "Helvetica Neue", sans-serif;
--font-mono:   "SF Mono", "Menlo", "Monaco",
               "Roboto Mono", monospace;
```

繁中 fallback 走 PingFang TC(macOS 原生 · Windows / Linux 用戶用通用 sans)。

### 1.2 顏色系統(macOS Sequoia 對齊)

```css
:root {
  /* 主色 · macOS system blue */
  --accent: #007AFF;
  --accent-pressed: #0051D5;

  /* Vibrancy / 毛玻璃 */
  --vibrancy-light: rgba(246, 246, 246, 0.72);
  --vibrancy-dark:  rgba(30, 30, 30, 0.72);
  --blur-vibrancy:  saturate(180%) blur(20px);

  /* macOS labels(語義色) */
  --label-primary:    #000000E6;  /* 90% black */
  --label-secondary:  #00000099;  /* 60% black */
  --label-tertiary:   #0000004D;  /* 30% black */
  --label-quaternary: #00000026;  /* 15% black */

  /* Surface 層 */
  --bg-base:    #ECECEC;          /* 桌面 */
  --bg-content: rgba(255,255,255,0.8);
  --bg-elevated: #FFFFFF;
  --bg-overlay: rgba(0,0,0,0.4);
}

/* Dark mode · Apple 官方 dark labels */
[data-theme="dark"] {
  --vibrancy-light: rgba(40, 40, 40, 0.72);
  --label-primary:   #FFFFFFE6;
  --label-secondary: #FFFFFF99;
  --bg-base:    #1E1E1E;
  --bg-content: rgba(40,40,40,0.8);
  --bg-elevated: #2C2C2E;
}
```

### 1.3 Spacing · 8px grid

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--space-12: 48px;

/* macOS standard */
--menubar-h: 24px;
--dock-h:    72px;       /* 56 icon + 16 padding */
--dock-icon: 56px;
--dock-icon-hover: 80px; /* scale 1.43 · macOS Sequoia 默認 */
```

### 1.4 Radius

```css
--r-sm: 6px;       /* button / chip */
--r-md: 10px;      /* card */
--r-lg: 16px;      /* sheet / modal */
--r-xl: 22px;      /* dock icon · macOS squircle */
--r-2xl: 28px;     /* window */
--r-full: 9999px;  /* avatar */
```

### 1.5 Motion(Apple-like spring)

```css
/* 對齊 Apple Spring(Sonoma SwiftUI default) */
--ease-spring:    cubic-bezier(0.34, 1.56, 0.64, 1);
--ease-out-expo:  cubic-bezier(0.16, 1, 0.3, 1);
--ease-out-quart: cubic-bezier(0.25, 1, 0.5, 1);

--dur-fast:    150ms;  /* hover / tap */
--dur-normal:  280ms;  /* sheet / view transition */
--dur-slow:    480ms;  /* mission control */
--dur-spring:  500ms;  /* spring 完整週期 */

/* prefers-reduced-motion 全套縮 0.001ms */
@media (prefers-reduced-motion: reduce) {
  :root { --dur-fast:0.001ms; --dur-normal:0.001ms;
          --dur-slow:0.001ms; --dur-spring:0.001ms; }
}
```

### 1.6 Shadow(macOS layered)

```css
/* 三層 shadow stack · 模仿 macOS window */
--shadow-window: 0 10px 30px rgba(0,0,0,0.18),
                 0 4px 12px rgba(0,0,0,0.10),
                 0 0 0 0.5px rgba(0,0,0,0.10);
--shadow-dock:   0 -8px 32px rgba(0,0,0,0.12),
                 0 0 0 0.5px rgba(0,0,0,0.08);
--shadow-card:   0 1px 3px rgba(0,0,0,0.08),
                 0 0 0 0.5px rgba(0,0,0,0.04);
```

---

## 2 · Dock 規格(Phase 2 · 8 hr)

### 2.1 結構

```
位置 · position: fixed · bottom: 12px · left: 50% · translateX(-50%)
高度 · 72px(56 icon + 8 padding 上下)
背景 · vibrancy(blur 20 · sat 180%)+ 0.5px 邊
圓角 · 22px(squircle approximation)
陰影 · shadow-dock
```

### 2.2 Icon 規格

```
預設大小 · 56 × 56
hover 大小 · 80 × 80(scale 1.43)
hover 衰減 · 高斯曲線 · 鄰近 icon 80 / 70 / 62 / 56
gap · 8px · hover 時自動撐開
indicator · 4px 圓點 · 在 icon 下方 4px · active 時亮(白 / 黑依主題)
```

### 2.3 三組 icon(改)

| 組 | 內容 | 數量 | 來源 |
|---|---|---|---|
| **Pinned agents** | user 收藏 + **default seed 7 個**(主管家 #00 + 知識查 #09 + 5 workspace 入口) | 7+ | `localStorage` |
| **Active chats** | 開著的對話(Sprint B 才有 window 系統) | 0-N | in-memory |

> **Issue 1 修(USER 視角)**:初版 dock 空 → demo 沒 wow factor。
> 改:default seed **7 個 icon**(承富 10 agent 的核心 7 個)· 開機就滿 · 老闆一登入看到漂亮 dock
> User 可右鍵移除任一 default · 動作 persist 到 localStorage

中間用「分隔線」(2px 寬 · 36px 高 · 半透明)隔開「pinned」跟「active chats」。

### 2.4 Magnification 算法(architect 推 · 不用 rAF)

```js
const SIGMA = 60;  // px · 高斯衰減半徑
dock.addEventListener('pointermove', throttle((e) => {
  const rect = dock.getBoundingClientRect();
  const cursorX = e.clientX - rect.left;
  icons.forEach((icon, i) => {
    const iconCenter = icon.offsetLeft + icon.offsetWidth / 2;
    const dist = Math.abs(cursorX - iconCenter);
    const scale = 1 + 0.43 * Math.exp(-(dist*dist) / (SIGMA*SIGMA));
    icon.style.setProperty('--scale', scale);
  });
}, 16));
dock.addEventListener('pointerleave', () => {
  icons.forEach(i => i.style.setProperty('--scale', 1));
});
```

CSS:
```css
.dock-icon {
  --scale: 1;
  transform: scale(var(--scale));
  transform-origin: bottom center;
  transition: transform var(--dur-fast) var(--ease-spring);
  will-change: transform;
}
.dock:not(:hover) .dock-icon { will-change: auto; }  /* 離開回收 RAM */
```

### 2.5 Right-click context menu

| Action | Icon |
|---|---|
| 開啟 | ↗ |
| 從 Dock 移除 | × |
| 顯示在工作區 | ⌘1-5 |
| 鎖定/解鎖排序 | 📌 |

### 2.6 Drag 重排 · HTML5 native DnD

不引 lib。`draggable=true` + `dragstart/over/drop` · 100 行內。

### 2.7 Sidebar 雙導覽分工(architect 重點)

| 元件 | 責任 | 認知方向 |
|---|---|---|
| **Sidebar** | 完整階層樹 · 中控 / 商機 / 會計 / 知識 | 「我要找 X」 |
| **Dock** | 常用 agent + 進行中對話 · 扁平 | 「我要快速開」 |

> **Issue 1 改進**:Dock seed 7 個 agent(主管家 + 知識查 + 5 workspace 入口的代表 agent · #01 招標 / #02 活動 / #03 設計 / #04 公關 / #06 結案)· 不重複 sidebar 既有「流程模板」(那是 workspace 階層樹)。

### 2.8 Dock 何時顯示(Issue 6 修)

| View | Dock 顯示? |
|---|---|
| Dashboard / Today | ✅ 顯示 |
| Workspace / Project / Knowledge / Help | ✅ 顯示 |
| Chat(LibreChat 內 iframe)| ❌ **隱藏**(LibreChat 自己有 sidebar · 重複) |
| Mobile(< 768px)| ❌ 隱藏(已有 mobile bottom nav) |

實作:`body[data-view="chat"] .dock-shell { display: none; }`

### 2.9 Dock a11y(Issue 7 修)

- Tab 進 dock · 第一個 icon 拿 focus
- ← / → 切 icon · Enter 開
- Esc 離開 dock · focus 回到上次 view
- Screen reader: 每 icon `aria-label="助手 N · 描述"` · indicator dot 用 `aria-current="true"` 標 active
- prefers-reduced-motion: magnification 改 instant scale(無 transition)· 進場動畫 skip

---

## 3 · Menu Bar 規格(Phase 3 · Sprint B)

> Sprint A **不做** · 只佈線 · Phase 1.2 加 PWA detection + `--menubar-h` CSS var
>
> **Issue 2 修(USER 視角)**:Plan 沒講「PWA 模式怎麼進」· 承富 IT / 老闆會卡住。
> 答:**Sprint A dock 不需 PWA · 一般瀏覽器就出**(menubar 才需 PWA)
> 進 PWA 步驟(Sprint B 寫進 docs/SHIP-v1.3.md):
>   - Chrome/Edge:右上 ⋮ → 安裝承富智慧助理
>   - Safari:分享 → 加入主畫面
>   - 後 launcher 變獨立 app · 自動全螢幕 · menu bar 出

### 3.1 PWA detection

```js
const isPWA = window.matchMedia('(display-mode: standalone), (display-mode: fullscreen)').matches;
document.documentElement.dataset.pwa = isPWA ? '1' : '0';

window.matchMedia('(display-mode: standalone)').addEventListener('change', e => {
  document.documentElement.dataset.pwa = e.matches ? '1' : '0';
});
```

### 3.2 CSS bridge

```css
:root { --menubar-h: 0; }
[data-pwa="1"] { --menubar-h: 24px; }

body { padding-top: var(--menubar-h); }
.sidebar, .main { top: var(--menubar-h); }
```

Sprint A 只佈這個 var · menubar DOM 留空 div · Sprint B 才 render 內容。

---

## 4 · 檔案結構(增量 · 不打掉 v1.3)

```
frontend/launcher/
├── index.html                      [改 · 加 dock div · menubar div]
├── launcher.css                    [改 · :root tokens 重置]
├── styles/
│   ├── tokens-macos.css            [新 · Phase 1.1]
│   ├── dock.css                    [新 · Phase 2.1]
│   └── menubar.css                 [新 · Sprint B]
├── modules/
│   ├── macos/
│   │   ├── dock.js                 [新 · Phase 2.1-2.3]
│   │   ├── pwa-detect.js           [新 · Phase 1.2]
│   │   ├── menubar.js              [新 · Sprint B]
│   │   ├── motion.js               [新 · Motion One wrapper]
│   │   └── window-manager.js       [新 · Sprint B]
│   ├── state/
│   │   └── dock-store.js           [新 · localStorage adapter]
│   └── ...既有 30 module 全保留
├── vendor/
│   └── motion-one.js               [新 · 8KB · CDN or npm copy]
└── app.js                          [改 · import dock + pwa-detect · 8 行]
```

---

## 5 · Risk · Rollback · Compat

### Risks

| 風險 | 機率 | 影響 | Mitigation |
|---|---|---|---|
| 既有 sidebar `top:0` hardcode 多 | 高 | menubar 重疊 | grep 全 case · sed 換 `top: var(--menubar-h)` |
| Vibrancy blur 在 Firefox / Safari < 16 | 低 | 看不到 blur · 但 fallback rgba 可看 | `@supports (backdrop-filter)` 包 · fallback solid bg |
| Pointer event 在 mobile | 中 | dock 在 iPhone 顯示異常 | mobile media query 隱藏 dock · 已有 mobile bottom nav |
| Motion One 8KB 載入失敗 | 極低 | 動畫降級到 CSS transition | try/catch import · 不擋頁面 |
| 既有 ⌘K palette 跟 Cmd+Space 衝突 | 低 | 衝突 | Sprint A 不改 · Sprint B 評估 |

### Rollback

每 phase 一個 PR · merge 前 manual QA + Playwright · 失敗 close PR 即可(不 force-push main)。

### v1.3 既有功能不動

- 任務式 FTUE · 不改
- 自助更新 sidebar 紅點 · 不改(放在 sidebar 中控按鈕 · 跟 dock 不衝突)
- 5 workspace · 不改(留 sidebar 流程模板)
- 中控 / 會計 / 商機 / 知識 / 教學 · 不改
- ⌘K palette · 不改

---

## 6 · 實作順序(Sprint A 細到 commit)

### Day 1(8 hr)

| commit | 內容 | 估時 |
|---|---|---|
| `feat(macos): tokens.css 設計 token 重置` | 1.1-1.6 全進 :root | 1 hr |
| `feat(macos): launcher.css :root 引用新 token + grep 替換 hardcode` | replace_all `0.15s ease` 等 | 1 hr |
| `feat(macos): pwa-detect.js + --menubar-h CSS var 全域佈線` | 1.2 + 3.1 + 3.2 | 1.5 hr |
| `feat(macos): dock.js shell + DOM render + localStorage store` | 2.1 + 2.3 + dock-store.js | 2 hr |
| `feat(macos): dock magnification + active indicator` | 2.2 + 2.4 | 2.5 hr |

### Day 2(6 hr)

| commit | 內容 | 估時 |
|---|---|---|
| `feat(macos): Motion One 進場動畫 dock 上滑` | dock 從底滑出 | 1 hr |
| `feat(macos): dock right-click context menu` | 2.5 | 1.5 hr |
| `feat(macos): dock drag reorder + persistence` | 2.6 + dock-store save | 2 hr |
| `feat(macos): dock a11y(Tab/Arrow/Enter)+ chat view 隱藏` | 2.8 + 2.9 | 1 hr |
| `docs(macos): 5 秒 demo GIF + onboarding tour 加 step 講 dock` | Issue 5 + Issue 3 | 0.5 hr |

---

## 7 · 驗收標準

Phase 1(tokens):
- [ ] launcher.css 變數 100% 走 `:root` · 沒 hardcode hex / rgba
- [ ] dark mode 切換無視覺爆炸
- [ ] prefers-reduced-motion 真的關所有動畫
- [ ] PWA mode `data-pwa="1"` toggle 正確 · `--menubar-h` 切到 24px

Phase 2(Dock):
- [ ] Dock 出現在底部中央 · 含 vibrancy
- [ ] Hover icon 平順放大(60fps · 不卡)
- [ ] 鄰近 icon 連動放大(高斯衰減)
- [ ] active 對話有藍點 indicator
- [ ] 右鍵跳 context menu · 「從 Dock 移除」work
- [ ] Drag 重排 · localStorage 記住
- [ ] 離開瀏覽器再回來 · 排序保持
- [ ] mobile(< 768px)隱藏 dock · 不影響既有 mobile bottom nav
- [ ] Playwright critical-journeys 全綠(34 pass · 4 skip)

---

## 8 · 後續 Sprint 骨架(本檔再寫)

### Sprint B(3-4 天)
- Phase 3 Menu bar(承富 / 檔案 / 編輯 / 顯示 / 視窗 / 說明 + 右側 status)
- Phase 4 Window 系統(traffic light · drag · cmd+W · Mission Control)

### Sprint C(2-3 天)
- Phase 5 Notification Center + Control Center
- Phase 6 macOS keyboard shortcuts 全套
- Phase 7 polish(spring 動畫細節 / 音效 / cursor effect)

---

## 9 · 不在 Sprint A 範圍

- 換 React / TS(已決定不換)
- Window 系統(Sprint B)
- Menu bar 內容 render(只佈 var · 內容 Sprint B)
- macOS Spotlight 取代 ⌘K(Sprint B 評估)
- Sound effects(Sprint C)

---

## 10 · 簽核

```
[ ] 你 review · 確認 Sprint A 範圍 + 設計 token + 風險清單
[ ] Sprint A 開動 · 預估 2 天 · 每 commit 你看 · 中途可拍版改方向
[ ] Sprint A 完工 · ship v1.3.1 · 看實際效果再決定 Sprint B 內容
```

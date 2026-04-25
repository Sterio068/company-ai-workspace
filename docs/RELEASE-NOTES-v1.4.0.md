# 承富智慧助理 v1.4.0 · macOS 大重構

> 出貨日期:2026-04-26
> 對應 PR:#37 ~ #45(9 個 PR)
> 參考 plan:`docs/MACOS-REBUILD-PLAN.md`

---

## ✨ 一句話

**整套 launcher 改成 macOS Sequoia 風 native 應用** · 看起來、用起來都像真的 mac app。

---

## 大改動 · 4 大件

### 1. 頂部 Menu Bar(藍底白字)

```
承富智慧助理 │ 檔案 │ 編輯 │ 顯示 │ 視窗 │ 說明      🤖 OpenAI · $0.45 · 🔔 · S · 22:30
```

- 左:6 個 menu(承富 / 檔案 / 編輯 / 顯示 / 視窗 / 說明)
- 右:5 個 status(模型切 / API 用量 / 通知 / 用戶 / 時間)
- 點 menu → macOS NSMenu 風 dropdown(含 ⌘ shortcut hint)
- Hover 切相鄰 menu(macOS 經典)
- 永遠顯示(不需 PWA 模式)

### 2. 底部 Dock(7 個高質感 SVG)

```
👑   🎯   📅   🎨   📣   📈   📚
主管家 投標 活動 設計 公關 財務 知識
```

- 真 squircle SVG icon(對齊 Sequoia 22% radius)
- 多層漸變 + 高光 + 內陰影 + drop shadow
- Hover 微 lift(translateY -3px)· 不再放大
- Click → bounce(macOS App opening 風 · 跳 14px)
- Active 對話有藍點 indicator + 微發光
- 右鍵 context menu(從 Dock 移除 / 顯示資訊)
- 拖曳重排 · localStorage 記
- 鍵盤 Tab + Arrow + Enter 全 a11y

### 3. 右側 Notification Center(🔔 click)

從右滑入 360px 面板 · 4 widget:
- 本月用量(progress bar + budget %)
- 系統狀態(3 service health)
- 自助升級提醒(有新版 → 直接點按鈕觸發)
- 小提示(隨機 6 個)

⌃⌘N 鍵盤 toggle。

### 4. Control Center(模型 status click)

從右上滑入 320px 快選 panel · 5 區塊:
- AI 引擎(OpenAI / Claude 大按鈕)
- 主題(自動 / 淺 / 深 segmented)
- Toggle row(全螢幕 / 重整)
- 快速動作(新對話 / 知識庫 / 教學 / 檢查更新)
- 登出

⌃⌘C 鍵盤 toggle。

---

## 浮動 Window 系統(MVP)

點頂部 menu「承富智慧助理 → 關於 承富智慧助理」:
- 浮動視窗 spring 進場
- macOS traffic lights(🔴 close / 🟡 minimize / 🟢 maximize)
- 拖 titlebar 移動
- 雙擊 titlebar = maximize
- ⌘W 關
- 同 id 重複 open · focus 不重建
- 多 window z-index 自動堆疊

v1.5 規劃對話多開 + Mission Control。

---

## ⌘K Spotlight 風 palette

- 大字輸入(22px Helvetica light)
- macOS Spotlight 玻璃 vibrancy
- Hover item 全色 accent + 白字
- Spring 進場(scale + translateY)

---

## 全套鍵盤快捷

| 快捷 | 功能 |
|---|---|
| ⌘0 | 今日 |
| ⌘P | 工作包 |
| ⌘1-5 | 5 工作區 |
| ⌘N | 新對話(主管家)|
| ⌘⇧N | 新工作包 |
| ⌘K | Spotlight 搜尋 |
| ⌘⇧L | 切深淺色 |
| ⌃⌘F | 全螢幕 |
| ⌃⌘N | 通知中心 |
| ⌃⌘C | 控制中心 |
| ⌘W | 關當前 window |
| ⌘? | 教學 |
| ⌘, | 偏好設定 |
| ⌘⇧Q | 登出 |

---

## CJK 排版優化

- SF Pro Display + PingFang TC fallback
- letter-spacing 0.04-0.05em(中文呼吸甜蜜點)
- font-feature-settings palt + kern(PingFang 標點寬度)
- 行距 1.6(漢字較鬆)
- text-rendering optimizeLegibility

---

## v1.3 既有功能 0 動

- LibreChat iframe / 自助升級 / 5 workspace / 中控 / 商機 / 會計
- FTUE 任務式教學 / 紅點通知 / ⌘K palette
- 全部保留 · 純 additive

---

## 設計 token 系統

完整 macOS Sequoia 對齊:
- Vibrancy(blur 20-40 + saturate 180)
- Spring easing(cubic 0.34, 1.56)
- 8px grid spacing
- Squircle 22% radius
- Three-layer shadow stack
- Light + Dark mode 完整對應
- prefers-reduced-motion 全縮 0.001ms

---

## Bug fix

- Window drag 第二次跳回原位(spring transform 殘留)· 修
- Menu bar 從 vibrancy 改藍底白字(品牌)· 改
- 右側 inspector 收起(浪費空間)· 改 NC
- 底頁 caption 移除(重複)· 改

---

## 不在 v1.4 範圍(後續)

- Mission Control(⌘↑ window overview)
- 對話多開(LibreChat iframe 包 window)
- minimize 飛回 dock 動畫
- Window resize handle
- Sound effects

---

## 升級

```bash
# Mac mini 上
cd ~/ChengFu && git pull origin main
docker compose -f config-templates/docker-compose.yml restart nginx
# 開瀏覽器 Cmd+Shift+R 強制重整
```

或:Admin sidebar 中控 → 紅點 → 「立即更新」(自助升級)。

---

## 統計(v1.3.0 → v1.4.0)

```
9 PR · 1.5 天 sprint
新檔 14 (4 macOS module · 4 style · 1 store · 5 docs)
改檔 8 (app · launcher.css · index · menubar · dock · onboarding · ...)
+3500 行 / -350 行
0 v1.3 既有功能影響
```

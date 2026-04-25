# Launcher ES Modules

`app.js` 是 Launcher entry/controller,但 v1.4 開始會把獨立責任逐步拆出,避免所有 view 與快捷鍵都綁在單檔。

## 目前模組

| Module | 職責 |
|---|---|
| `config.js` | API path / AI provider / Agent / Skill / Workspace 靜態設定 |
| `util.js` | 日期、金額、escape、skeleton、前端中文化等純工具 |
| `tpl.js` | HTML template clone/render helper |
| `auth.js` | LibreChat JWT refresh、`authFetch`、session 過期處理 |
| `projects.js` | 工作包 CRUD、MongoDB API 優先、localStorage fallback、多分頁同步 |
| `state/project-store.js` | 跨模組 current project 狀態 |
| `chat.js` | 內建 chat pane、附件、SSE、feedback、回答回寫工作包 |
| `palette.js` | ⌘K palette UI 與 async source |
| `palette-items.js` | ⌘K 指令資料源(v1.4 從 `app.js` 拆出) |
| `keyboard.js` | 全域快捷鍵(v1.4 從 `app.js` 拆出) |
| `router.js` | hash routing、view active 狀態、Workspace sync(v1.4 從 `app.js` 拆出) |
| `work-package.js` | 工作包排序、搜尋、可交接度、類型判斷、AI 動作建議與回寫設定 |
| `theme.js` | 深淺色切換與持久化 |
| `toast.js` | Toast 通知 |
| `modal.js` | Modal v2(alert/confirm/prompt async 版) |
| `health.js` | Service health 指示器 |
| `mobile.js` | 漢堡選單、mobile shell |
| `shortcuts.js` | `?` 快捷鍵 overlay |
| `voice.js` | 語音輸入 |
| `errors.js` | 全域錯誤處理 |
| `accounting.js` | 會計 view |
| `admin.js` | 管理儀表板 |
| `user_mgmt.js` | 同仁帳號管理 |
| `knowledge.js` | 公司知識庫瀏覽、搜尋、管理 |
| `tenders.js` | 標案通知 |
| `workflows.js` | Workflow 草稿與執行 |
| `crm.js` | CRM / 客戶案子追蹤 |
| `meeting.js` | 會議速記 |
| `media.js` | 生圖/素材工具 |
| `social.js` | 社群 OAuth / 發文 |
| `site_survey.js` | 場勘流程 |
| `design.js` | `/design` 生圖入口 |
| `help.js` | 使用教學 |

## 仍在 `app.js`

- Bootstrap / user setup / data loading orchestration
- Dashboard / Today workbench render
- Projects list / work detail DOM render
- Project drawer / handoff form
- View-specific side effects(accounting/admin/workflow lazy load 等)

## v1.4 拆分順序

1. `palette-items.js` + `keyboard.js` 已拆出。
2. `router.js` 已拆出,view-specific lazy load 仍留 `app.js`。
3. `work-package.js` 已拆出純邏輯,下一步拆 `today-view.js`、`projects/work-detail.js`、`projects/drawer.js` DOM render。
4. 最後讓 `app.js` 收斂到 bootstrap + dependency injection。

## 載入方式

`index.html`:
```html
<script type="module" src="/static/app.js"></script>
```

`app.js`:
```javascript
import { toast }    from "./modules/toast.js";
import { modal }    from "./modules/modal.js";
import { Projects } from "./modules/projects.js";
// ...
```

## 為什麼不用 webpack / vite

- 10 人使用,沒必要 bundle
- 原生 ES modules Chrome/Safari 支援好
- 本機 dev 改檔即時生效
- 無 build step = 無 CI 壓力
- 若未來真要 · `vite build` 一行就 OK

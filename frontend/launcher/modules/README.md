# Launcher ES Modules

app.js(1400+ 行)太大,拆成 modules:

| Module | 職責 | 依賴 |
|---|---|---|
| `util.js` | fetchJSON / formatDate / greetingFor / timeAgo / escapeHtml / formatMoney / skeletonCards | 無 |
| `toast.js` | Toast 通知(success/warn/error/info) | util |
| `modal.js` | Modal v2(alert/confirm/prompt async 版) | util |
| `health.js` | Service Health 指示器 | 無 |
| `mobile.js` | 漢堡選單 + Drawer | 無 |
| `projects.js` | Projects CRUD(API + localStorage fallback) | 無 |
| `errors.js` | Error boundary + global handler | toast, util |

## v3.0 待拆(目前仍在 app.js 中)

- `app-core.js` - app init / user / theme / keyboard
- `agents.js` - CORE_AGENTS 定義 + render
- `accounting.js` - accounting view
- `admin.js` - admin dashboard
- `tenders.js` - 標案監測
- `workflows.js` - Workflow 執行
- `crm.js` - Kanban
- `onboarding.js`(已獨立)
- `voice.js` - 語音輸入
- `palette.js` - ⌘K palette
- `shortcuts.js` - ? overlay

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

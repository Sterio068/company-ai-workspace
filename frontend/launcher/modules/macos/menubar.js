/**
 * macOS Menu Bar · v1.4 Sprint B Phase 3
 * =====================================
 * 頂部選單列 · 永遠顯示(USER 反饋 · 不再 PWA-gated)
 *
 * 結構:
 *   [App] | 檔案 | 編輯 | 顯示 | 視窗 | 說明        🤖 模型 · $0.45 · 🔔 · 👤 · 22:30
 *
 * 行為:
 *   - 點任一 menu → dropdown
 *   - 按 Esc 關 dropdown
 *   - 移到相鄰 menu(若 dropdown 開著)→ 自動切過去(macOS 風)
 */
import { springEnter, slideUp } from "./motion.js";
import { openWindow } from "./window.js";

// ============================================================
// Menu 結構定義
// ============================================================
const APP_NAME = "承富智慧助理";

const MENUS = [
  {
    label: APP_NAME,
    bold: true,
    items: [
      { label: "關於 承富智慧助理", action: () => _openAboutWindow(), shortcut: "" },
      { sep: true },
      { label: "偏好設定...", action: () => window.app?.showView?.("admin"), shortcut: "⌘," },
      { sep: true },
      { label: "登出", action: () => _confirmLogout(), shortcut: "⌘⇧Q", danger: true },
    ],
  },
  {
    label: "檔案",
    items: [
      { label: "新對話", action: () => window.app?.openAgent?.("00"), shortcut: "⌘N" },
      { label: "新工作包", action: () => window.app?.showView?.("projects"), shortcut: "⌘⇧N" },
      { sep: true },
      { label: "開啟工作包...", action: () => window.app?.showView?.("projects"), shortcut: "⌘O" },
      { label: "知識庫搜尋", action: () => window.app?.showView?.("knowledge"), shortcut: "⌘K" },
      { sep: true },
      { label: "匯出對話", action: () => _todo("匯出"), shortcut: "⌘E" },
    ],
  },
  {
    label: "編輯",
    items: [
      { label: "復原", action: () => document.execCommand?.("undo"), shortcut: "⌘Z" },
      { label: "重做", action: () => document.execCommand?.("redo"), shortcut: "⌘⇧Z" },
      { sep: true },
      { label: "剪下", action: () => document.execCommand?.("cut"), shortcut: "⌘X" },
      { label: "複製", action: () => document.execCommand?.("copy"), shortcut: "⌘C" },
      { label: "貼上", action: () => document.execCommand?.("paste"), shortcut: "⌘V" },
      { label: "全選", action: () => document.execCommand?.("selectAll"), shortcut: "⌘A" },
    ],
  },
  {
    label: "顯示",
    items: [
      { label: "今日", action: () => window.app?.showView?.("dashboard"), shortcut: "⌘0" },
      { label: "工作包", action: () => window.app?.showView?.("projects"), shortcut: "⌘P" },
      { label: "知識庫", action: () => window.app?.showView?.("knowledge"), shortcut: "⌘K" },
      { sep: true },
      { label: "投標", action: () => window.app?.openWorkspace?.(1), shortcut: "⌘1" },
      { label: "活動執行", action: () => window.app?.openWorkspace?.(2), shortcut: "⌘2" },
      { label: "設計協作", action: () => window.app?.openWorkspace?.(3), shortcut: "⌘3" },
      { label: "公關溝通", action: () => window.app?.openWorkspace?.(4), shortcut: "⌘4" },
      { label: "營運後勤", action: () => window.app?.openWorkspace?.(5), shortcut: "⌘5" },
      { sep: true },
      { label: "切換深淺色", action: () => _toggleTheme(), shortcut: "⌘⇧L" },
      { label: "進入全螢幕", action: () => _toggleFullscreen(), shortcut: "⌃⌘F" },
    ],
  },
  {
    label: "視窗",
    items: [
      { label: "最小化", action: () => _todo("最小化(Sprint B Phase 4)"), shortcut: "⌘M" },
      { label: "縮放", action: () => _todo("縮放"), shortcut: "" },
      { sep: true },
      { label: "Mission Control", action: () => _todo("Mission Control · Sprint B Phase 4"), shortcut: "⌘↑" },
      { sep: true },
      { label: "回到承富主畫面", action: () => window.app?.showView?.("dashboard"), shortcut: "⌘0" },
    ],
  },
  {
    label: "說明",
    items: [
      { label: "使用教學", action: () => window.app?.showView?.("help"), shortcut: "" },
      { label: "重看 5 分鐘任務式教學", action: () => window.tour?.start?.(), shortcut: "" },
      { sep: true },
      { label: "Slash 命令 / 快捷鍵", action: () => window.app?.showView?.("help"), shortcut: "⌘?" },
      { label: "資料分級 SOP", action: () => window.app?.showView?.("help"), shortcut: "" },
      { sep: true },
      { label: "找 IT / Sterio", action: () => _contactSupport(), shortcut: "" },
    ],
  },
];

// ============================================================
// Helpers
// ============================================================
function _todo(msg) {
  window.toast?.info?.(`${msg} · 即將推出`);
}

function _confirmLogout() {
  if (confirm("確定要登出?未送出的對話會丟失。")) {
    window.location.href = "/chat/logout";
  }
}

function _toggleTheme() {
  const html = document.documentElement;
  const cur = html.dataset.theme;
  html.dataset.theme = cur === "dark" ? "light" : "dark";
  localStorage.setItem("chengfu-theme", html.dataset.theme);
  window.toast?.info?.(`已切到 ${html.dataset.theme === "dark" ? "深色" : "淺色"}`);
}

function _toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
}

function _contactSupport() {
  window.toast?.info?.("Sterio · sterio068@gmail.com");
}

// ============================================================
// 「關於 承富智慧助理」浮動視窗(Sprint B Phase 4 demo)
// ============================================================
function _openAboutWindow() {
  openWindow({
    id: "about",
    title: "關於 承富智慧助理",
    width: 480,
    height: 420,
    content: `
      <div style="text-align:center; padding-top: 12px">
        <div style="display:grid; place-items:center; margin-bottom:12px">
          <div style="
            width:96px; height:96px;
            background: linear-gradient(135deg, #007AFF, #5856D6);
            border-radius:22%;
            display:grid; place-items:center;
            font-size:48px; color:white;
            box-shadow: 0 6px 20px rgba(0, 122, 255, 0.3);
          ">承</div>
        </div>
        <h2 style="margin: 0 0 4px; font-size:20px; font-weight:600; letter-spacing:0.05em">承富智慧助理</h2>
        <p style="margin: 0 0 16px; color: var(--label-secondary); font-size: 13px; letter-spacing: 0.05em">v1.4.0 · macOS 風重構</p>
        <div style="
          display:inline-block;
          padding:6px 14px;
          background: rgba(0, 122, 255, 0.1);
          color: var(--accent);
          border-radius: 20px;
          font-size: 12px;
          font-weight: 500;
          margin-bottom: 20px;
        ">本地部署 · 100% 資料留在公司</div>

        <div style="text-align:left; padding: 0 20px; margin-top: 12px; line-height: 1.8">
          <p>承富 10 人協作專屬 · AI 助手系統</p>
          <ul style="padding-left: 20px; color: var(--label-secondary); font-size: 13px; margin: 8px 0">
            <li>10 個 AI 助手 · 5 個工作區</li>
            <li>5 分鐘任務式 FTUE 教學</li>
            <li>系統自助升級 · admin 點紅點即可</li>
            <li>完整 macOS 設計語言(v1.4)</li>
          </ul>
        </div>

        <p style="
          margin-top: 24px;
          padding-top: 16px;
          border-top: 0.5px solid var(--separator);
          font-size: 11px;
          color: var(--label-tertiary);
          letter-spacing: 0.05em
        ">
          Made with ❤️ by Sterio · sterio068@gmail.com
        </p>
      </div>
    `,
  });
}

// ============================================================
// Render
// ============================================================
let _menubarEl = null;
let _activeDropdown = null;
let _activeMenuIdx = -1;

function _ensureMenubar() {
  _menubarEl = document.getElementById("macos-menubar");
  if (!_menubarEl) return null;
  return _menubarEl;
}

function _renderMenubar() {
  if (!_ensureMenubar()) return;
  _menubarEl.innerHTML = "";

  // Left · App + 5 menu
  const left = document.createElement("div");
  left.className = "menubar-left";
  MENUS.forEach((menu, idx) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "menubar-item" + (menu.bold ? " bold" : "");
    item.textContent = menu.label;
    item.dataset.idx = String(idx);
    item.addEventListener("click", (e) => {
      e.stopPropagation();
      _toggleDropdown(idx, item);
    });
    item.addEventListener("mouseenter", () => {
      // 若有 dropdown 開著 · hover 自動切(macOS 風)
      if (_activeDropdown && _activeMenuIdx !== idx) {
        _toggleDropdown(idx, item);
      }
    });
    left.appendChild(item);
  });
  _menubarEl.appendChild(left);

  // Right · status items
  const right = document.createElement("div");
  right.className = "menubar-right";
  right.appendChild(_renderStatusModel());
  right.appendChild(_renderStatusUsage());
  right.appendChild(_renderStatusNotif());
  right.appendChild(_renderStatusUser());
  right.appendChild(_renderStatusTime());
  _menubarEl.appendChild(right);
}

// ============================================================
// Right side · status items
// ============================================================
function _renderStatusModel() {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "menubar-status-item engine-toggle";
  el.title = "控制中心(⌃⌘C)";
  const cur = localStorage.getItem("chengfu-engine") || "openai";
  el.innerHTML = `
    <span class="status-icon">🤖</span>
    <span class="status-label">${cur === "openai" ? "OpenAI" : "Claude"}</span>
    <span class="status-chevron">▾</span>
  `;
  // 改開 Control Center · 點 → 完整快速設定 panel(模型 / 主題 / 全螢幕 / 動作)
  el.addEventListener("click", (e) => {
    e.stopPropagation();
    import("./control-center.js").then(m => m.toggle()).catch(err => {
      // 退回舊行為 · 直接 toggle 引擎
      const next = cur === "openai" ? "anthropic" : "openai";
      localStorage.setItem("chengfu-engine", next);
      _renderMenubar();
    });
  });
  // 監聽 engine-changed · 重 render 顯示新名字
  document.addEventListener("engine-changed", () => _renderMenubar(), { once: true });
  return el;
}

function _renderStatusUsage() {
  const el = document.createElement("div");
  el.className = "menubar-status-item readonly";
  el.id = "menubar-status-usage";
  // 載入時 fetch · 5 分鐘 refresh
  el.innerHTML = `<span class="status-label">— USD 今日</span>`;
  _refreshUsage(el);
  return el;
}

let _usageTimer = null;
async function _refreshUsage(el) {
  try {
    const r = await fetch("/api-accounting/admin/cost/today", {
      headers: { Accept: "application/json" },
      credentials: "include",
    });
    if (r.ok) {
      const data = await r.json();
      const usd = data.today_usd ?? data.usd ?? 0;
      el.innerHTML = `<span class="status-label">$${usd.toFixed(2)} 今日</span>`;
      el.title = `本月累計 $${(data.month_usd || 0).toFixed(2)} / $${data.budget_usd || "∞"}`;
    } else if (r.status === 403) {
      // 非 admin · 隱起來
      el.style.display = "none";
    }
  } catch (e) {
    el.innerHTML = `<span class="status-label">— USD</span>`;
  }
  // 5 分鐘再 refresh
  if (_usageTimer) clearTimeout(_usageTimer);
  _usageTimer = setTimeout(() => _refreshUsage(el), 5 * 60 * 1000);
}

function _renderStatusNotif() {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "menubar-status-item notif";
  el.id = "menubar-status-notif";
  el.title = "通知中心(⌃⌘N)";
  el.innerHTML = `<span class="status-icon">🔔</span>`;
  el.addEventListener("click", (e) => {
    e.stopPropagation();
    // 動態 import NC · 不擋首屏
    import("./notification-center.js").then(m => m.toggle()).catch(err => {
      window.toast?.warn?.("通知中心未載入 · " + err.message);
    });
  });
  return el;
}

function _renderStatusUser() {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "menubar-status-item user";
  // 從 app.user 拿 email / name
  const user = window.app?.user;
  const initial = (user?.name || user?.email || "?").charAt(0).toUpperCase();
  el.innerHTML = `
    <span class="status-avatar">${initial}</span>
  `;
  el.title = user?.email || "未登入";
  el.addEventListener("click", () => window.app?.showView?.("admin"));
  return el;
}

function _renderStatusTime() {
  const el = document.createElement("div");
  el.className = "menubar-status-item readonly time";
  el.id = "menubar-status-time";
  _updateTime(el);
  setInterval(() => _updateTime(el), 30 * 1000);  // 每 30 秒 refresh
  return el;
}

function _updateTime(el) {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  el.innerHTML = `<span class="status-label">${h}:${m}</span>`;
}

// ============================================================
// Dropdown
// ============================================================
function _closeDropdown() {
  if (_activeDropdown) {
    _activeDropdown.remove();
    _activeDropdown = null;
  }
  if (_activeMenuIdx >= 0) {
    document.querySelectorAll(".menubar-item.open").forEach(el => el.classList.remove("open"));
    _activeMenuIdx = -1;
  }
  document.removeEventListener("click", _onDocClick);
  document.removeEventListener("keydown", _onDocKey);
}

function _onDocClick(e) {
  if (_activeDropdown && !_activeDropdown.contains(e.target)) {
    _closeDropdown();
  }
}

function _onDocKey(e) {
  if (e.key === "Escape") _closeDropdown();
}

function _toggleDropdown(idx, btn) {
  // 同一個 · 關
  if (_activeMenuIdx === idx) {
    _closeDropdown();
    return;
  }
  _closeDropdown();

  const menu = MENUS[idx];
  if (!menu) return;

  const dropdown = document.createElement("div");
  dropdown.className = "menubar-dropdown";
  dropdown.setAttribute("role", "menu");

  menu.items.forEach(mi => {
    if (mi.sep) {
      const sep = document.createElement("div");
      sep.className = "menubar-dropdown-sep";
      dropdown.appendChild(sep);
      return;
    }
    const it = document.createElement("button");
    it.type = "button";
    it.className = "menubar-dropdown-item" + (mi.danger ? " danger" : "");
    it.setAttribute("role", "menuitem");
    it.innerHTML = `
      <span class="dd-label">${mi.label}</span>
      ${mi.shortcut ? `<span class="dd-shortcut">${mi.shortcut}</span>` : ""}
    `;
    it.addEventListener("click", () => {
      _closeDropdown();
      try { mi.action?.(); } catch (e) { console.warn("menu action failed", e); }
    });
    dropdown.appendChild(it);
  });

  // 定位 · 直接掛在 btn 下方
  const rect = btn.getBoundingClientRect();
  dropdown.style.top = `${rect.bottom + 2}px`;
  dropdown.style.left = `${rect.left}px`;
  document.body.appendChild(dropdown);

  // 防超出 viewport · 右側
  const ddRect = dropdown.getBoundingClientRect();
  if (ddRect.right > window.innerWidth - 8) {
    dropdown.style.left = `${window.innerWidth - ddRect.width - 8}px`;
  }

  btn.classList.add("open");
  _activeDropdown = dropdown;
  _activeMenuIdx = idx;

  slideUp(dropdown, { distance: 4, duration: 180 });

  setTimeout(() => {
    document.addEventListener("click", _onDocClick);
    document.addEventListener("keydown", _onDocKey);
  }, 0);
}

// ============================================================
// Public API
// ============================================================
export const menubar = {
  init() {
    if (!_ensureMenubar()) return;
    _renderMenubar();

    // 動態 refresh user info(login 後)
    document.addEventListener("user-loaded", () => _renderMenubar());
  },
};

if (typeof window !== "undefined") {
  window.menubar = menubar;
}

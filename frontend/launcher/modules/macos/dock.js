/**
 * macOS Dock · v1.4 · Phase 2.1-2.2
 * =====================================
 * 底部 Dock · workspace + agent icon · hover magnification · active 指示
 *
 * 結構:
 *   <div class="dock-shell" data-active-view="...">
 *     <div class="dock">
 *       <button class="dock-icon" data-type="agent" data-id="00">...</button>
 *       <div class="dock-separator"></div>
 *       <button class="dock-icon" ...></button>
 *       ...
 *     </div>
 *   </div>
 *
 * 行為:
 *   - dockStore 變動 → re-render
 *   - hover icon · 高斯放大(σ=60)
 *   - 點擊 → app.openAgent() 或 app.openWorkspace()
 *   - active 對話有 4px indicator dot
 *
 * 不在此檔(Sprint A 後續 commit):
 *   - right-click context menu(commit 6)
 *   - drag reorder(commit 7)
 *   - Motion One 進場動畫(commit 6)
 *   - a11y 鍵盤導航(commit 8)
 */
import { dockStore } from "../state/dock-store.js";
import { getDockIconSVG } from "./dock-icons.js";
import { springEnter, slideUp, pulse } from "./motion.js";

// USER 反饋(2026-04-26):
// - icon 不要圓 → squircle 改方(dock-icons.js radius 22%)
// - 互動不用連動和放大 → 拿掉高斯 magnification
// - 按的時候跳一下 → 點擊 bounce 動畫(macOS Sequoia 默認)
let _shellEl = null;
let _dockEl = null;
let _icons = [];           // current rendered icons
let _activeId = null;      // 當前 active(view 切換時更新)

// ============================================================
// Render
// ============================================================
function _ensureShell() {
  if (_shellEl) return _shellEl;
  _shellEl = document.createElement("div");
  _shellEl.className = "dock-shell";
  _shellEl.setAttribute("aria-label", "macOS 風 Dock");

  _dockEl = document.createElement("nav");
  _dockEl.className = "dock";
  _dockEl.setAttribute("role", "toolbar");
  _dockEl.setAttribute("aria-label", "Dock");

  _shellEl.appendChild(_dockEl);
  document.body.appendChild(_shellEl);
  return _shellEl;
}

// v1.50 · 委派 keydown 到 dockEl 一次 · 取代每個 icon 一個 closure
let _delegatedKeydown = false;
function _ensureDelegatedKeydown() {
  if (_delegatedKeydown || !_dockEl) return;
  _delegatedKeydown = true;
  _dockEl.addEventListener("keydown", (e) => {
    const btn = e.target.closest(".dock-icon");
    if (!btn) return;
    const idx = parseInt(btn.dataset.idx, 10);
    if (!Number.isFinite(idx)) return;
    const focusables = Array.from(_dockEl.querySelectorAll(".dock-icon"));
    const cur = focusables.indexOf(btn);
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      focusables[(cur + 1) % focusables.length]?.focus();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      focusables[(cur - 1 + focusables.length) % focusables.length]?.focus();
    } else if (e.key === "Home") {
      e.preventDefault();
      focusables[0]?.focus();
    } else if (e.key === "End") {
      e.preventDefault();
      focusables[focusables.length - 1]?.focus();
    } else if (e.key === "Escape") {
      btn.blur();
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      const item = _icons[idx]?._item;
      if (!item) return;
      const removed = dockStore.unpin(item.type, item.id);
      if (removed && window.toast) window.toast.info(`已從 Dock 移除 · ${item.label}`);
    } else if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
      e.preventDefault();
      const item = _icons[idx]?._item;
      if (!item) return;
      const rect = btn.getBoundingClientRect();
      _showContextMenu(
        { clientX: rect.left + rect.width / 2, clientY: rect.top, preventDefault() {} },
        item,
        idx,
      );
    }
  });
}

function _render(items) {
  _ensureShell();
  _ensureDelegatedKeydown();
  _dockEl.innerHTML = "";
  _icons = [];

  items.forEach((item, idx) => {
    const btn = _renderIcon(item, idx);
    btn._item = item;  // for delegated handler
    _dockEl.appendChild(btn);
    _icons.push(btn);
  });

  // 後續加 active chats 區段(Sprint B window 系統再來)· 此處保留 hook
  // _renderSeparator();
  // active chats render here

  _refreshActiveIndicators();
}

function _renderIcon(item, idx) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "dock-icon";
  btn.dataset.type = item.type;
  btn.dataset.id = item.id;
  btn.dataset.idx = String(idx);
  btn.setAttribute("aria-label", `${item.label} · 助手 ${item.id}`);
  btn.title = item.label;
  btn.style.setProperty("--icon-color", item.color || "var(--accent)");

  // icon 內容 · 真 macOS 風 SVG · squircle + gradient + pictogram
  const iconWrap = document.createElement("span");
  iconWrap.className = "dock-icon-glyph";
  if (item.type === "agent") {
    iconWrap.innerHTML = getDockIconSVG(item.id, item.color || "var(--accent)");
  } else {
    // workspace / view fallback · 用 emoji 暫代
    iconWrap.textContent = item.icon || "🟦";
    iconWrap.classList.add("emoji-fallback");
  }
  btn.appendChild(iconWrap);

  // active indicator dot
  const dot = document.createElement("span");
  dot.className = "dock-icon-indicator";
  dot.setAttribute("aria-hidden", "true");
  btn.appendChild(dot);

  // tooltip · CSS-only 出現 hover 上方
  const tooltip = document.createElement("span");
  tooltip.className = "dock-icon-tooltip";
  tooltip.textContent = item.label;
  tooltip.setAttribute("aria-hidden", "true");
  btn.appendChild(tooltip);

  // click → bounce + 開 agent
  btn.addEventListener("click", () => {
    _bounce(btn);
    if (item.type === "agent" && window.app?.openAgent) {
      window.app.openAgent(item.id);
    } else if (item.type === "workspace" && window.app?.openWorkspace) {
      window.app.openWorkspace(parseInt(item.id, 10));
    } else if (item.type === "view" && window.app?.showView) {
      window.app.showView(item.id);
    }
  });

  // right-click → context menu
  btn.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    _showContextMenu(e, item, idx);
  });

  // ===== Drag & Drop reorder · HTML5 native(0 dep)=====
  btn.draggable = true;
  btn.addEventListener("dragstart", (e) => {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(idx));
    btn.classList.add("dragging");
  });
  btn.addEventListener("dragend", () => {
    btn.classList.remove("dragging");
    document.querySelectorAll(".dock-icon.drop-target").forEach(el => el.classList.remove("drop-target"));
  });
  btn.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    btn.classList.add("drop-target");
  });
  btn.addEventListener("dragleave", () => {
    btn.classList.remove("drop-target");
  });
  btn.addEventListener("drop", (e) => {
    e.preventDefault();
    btn.classList.remove("drop-target");
    const fromIdx = parseInt(e.dataTransfer.getData("text/plain"), 10);
    const toIdx = parseInt(btn.dataset.idx, 10);
    if (Number.isFinite(fromIdx) && Number.isFinite(toIdx) && fromIdx !== toIdx) {
      dockStore.reorder(fromIdx, toIdx);
    }
  });

  // v1.50 · keydown 委派到 _dockEl(_ensureDelegatedKeydown)· 此處不再每 icon 註冊
  return btn;
}

// ============================================================
// Context Menu(right-click)
// ============================================================
let _menuEl = null;

function _closeContextMenu() {
  if (_menuEl) {
    _menuEl.remove();
    _menuEl = null;
  }
  document.removeEventListener("click", _closeContextMenu);
  document.removeEventListener("keydown", _onMenuKey);
}

function _onMenuKey(e) {
  if (e.key === "Escape") _closeContextMenu();
}

function _showContextMenu(event, item, idx) {
  _closeContextMenu();  // 關之前的

  const menu = document.createElement("div");
  menu.className = "dock-context-menu";
  menu.setAttribute("role", "menu");

  const items = [
    {
      label: `開啟 ${item.label}`,
      icon: "↗",
      action: () => {
        if (item.type === "agent") window.app?.openAgent(item.id);
        else if (item.type === "workspace") window.app?.openWorkspace(parseInt(item.id, 10));
      },
    },
    { separator: true },
    {
      label: "從 Dock 移除",
      icon: "−",
      danger: true,
      action: () => {
        const removed = dockStore.unpin(item.type, item.id);
        if (removed && window.toast) window.toast.info(`已從 Dock 移除 · ${item.label}`);
      },
    },
    {
      label: "顯示資訊",
      icon: "ⓘ",
      action: () => {
        if (window.toast) window.toast.info(`#${item.id} · ${item.label}`);
      },
    },
  ];

  items.forEach((mi) => {
    if (mi.separator) {
      const sep = document.createElement("div");
      sep.className = "dock-context-menu-sep";
      menu.appendChild(sep);
      return;
    }
    const it = document.createElement("button");
    it.type = "button";
    it.className = "dock-context-menu-item" + (mi.danger ? " danger" : "");
    it.setAttribute("role", "menuitem");
    it.innerHTML = `<span class="cm-icon" aria-hidden="true">${mi.icon}</span><span class="cm-label">${mi.label}</span>`;
    it.addEventListener("click", () => {
      mi.action();
      _closeContextMenu();
    });
    menu.appendChild(it);
  });

  document.body.appendChild(menu);

  // 定位 · 滑鼠位置 · 不超出 viewport
  const rect = menu.getBoundingClientRect();
  let x = event.clientX;
  let y = event.clientY;
  if (x + rect.width > window.innerWidth - 8) x = window.innerWidth - rect.width - 8;
  if (y + rect.height > window.innerHeight - 8) y = window.innerHeight - rect.height - 8;
  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;

  _menuEl = menu;
  slideUp(menu, { distance: 6, duration: 200 });

  // 點外面 / Esc 關
  setTimeout(() => {
    document.addEventListener("click", _closeContextMenu);
    document.addEventListener("keydown", _onMenuKey);
  }, 0);
}

function _refreshActiveIndicators() {
  _icons.forEach(icon => {
    const isActive = icon.dataset.id === _activeId;
    icon.classList.toggle("active", isActive);
    if (isActive) icon.setAttribute("aria-current", "true");
    else icon.removeAttribute("aria-current");
  });
}

// ============================================================
// Bounce · macOS Sequoia 點擊跳一下動畫(取代 magnification)
// USER 反饋:不要連動放大 · 按的時候跳一下
// ============================================================
function _bounce(el) {
  if (!el || !el.animate) return;
  // 模仿 macOS Sequoia App opening · icon 往上跳 + 微縮回
  el.animate(
    [
      { transform: "translateY(0) scale(1)" },
      { transform: "translateY(-14px) scale(1.05)", offset: 0.4 },
      { transform: "translateY(0) scale(1)" },
    ],
    {
      duration: 360,
      easing: "cubic-bezier(0.34, 1.56, 0.64, 1)",
    },
  );
}

// ============================================================
// Public API
// ============================================================
export const dock = {
  init() {
    _ensureShell();
    _render(dockStore.getItems());

    // 進場動畫 · 從底部彈入(Spring · 0 dependency · WAAPI)
    springEnter(_shellEl, { fromY: 80, toY: 0, duration: 600 });

    // 訂閱 store 變動(unpin / reorder / reset)· 重 render 不重彈
    dockStore.subscribe(items => _render(items));

    // USER 反饋(2026-04-26):拿掉 magnification + 連動放大
    // hover 改 CSS 微微 lift(dock.css 處理 · 不在此 JS)
    // 點擊 bounce 在 button click handler 跑 _bounce()

    // 監聽 view 切換 · 更新 active indicator
    document.addEventListener("ws-changed", (e) => {
      // 當前 view 對應的 agent id
      const view = e.detail?.view;
      const ws = e.detail?.ws;
      if (view === "workspace" && ws) {
        // workspace n 對應 agent id(0n)· 例 ws=1 → agent 01
        _activeId = String(ws).padStart(2, "0");
      } else {
        _activeId = null;
      }
      _refreshActiveIndicators();
    });
  },
};

// expose for ⌘K palette + manual trigger
if (typeof window !== "undefined") {
  window.dock = dock;
}

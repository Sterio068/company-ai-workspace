/**
 * macOS Window · v1.4 Sprint B Phase 4 (MVP)
 * =====================================
 * 浮動視窗元件 · 帶 traffic lights · drag · z-index 堆疊
 *
 * MVP 範圍(本 PR):
 *   - Window 元件(traffic lights · 拖移 · z-index)
 *   - ⌘W 關 active window
 *   - 套 「關於 智慧助理」 demo
 *
 * 後續(v1.5):
 *   - 對話多開(用 Window 包 LibreChat iframe)
 *   - ⌘M minimize 飛回 dock 動畫
 *   - Mission Control overview
 *   - 視窗 resize handles
 *
 * Usage:
 *   import { openWindow } from "./window.js";
 *   openWindow({ id: "about", title: "關於", content: "<p>...</p>" });
 */
import { springEnter, slideUp } from "./motion.js";

let _topZ = 1100;       // 起始 z · 比 modal 略高
const _windows = new Map();  // id → window instance

class MacWindow {
  constructor({ id, title, content, width = 480, height = 360, x, y, onClose }) {
    this.id = id;
    this.title = title;
    this.content = content;
    this.width = width;
    this.height = height;
    this.onClose = onClose;
    // 默認居中(menubar 28 + 距上 20%)
    this.x = x ?? Math.max(20, (window.innerWidth - width) / 2);
    this.y = y ?? Math.max(60, window.innerHeight * 0.2);
    this.z = ++_topZ;
    this.minimized = false;
    this.maximized = false;
    this._origRect = null;
    this.el = this._render();
    document.body.appendChild(this.el);
    this._wireEvents();
    // 修 2026-04-26 · 必傳 translateX:0 否則 spring 預設 -50% 會把 window 平移
    const anim = springEnter(this.el, { fromY: 20, toY: 0, duration: 320, translateX: "0" });
    // 動畫結束後清 transform · 防殘留影響後續 drag 計算
    if (anim) anim.onfinish = () => { this.el.style.transform = ""; };
  }

  _render() {
    const w = document.createElement("div");
    w.className = "macos-window";
    w.dataset.windowId = this.id;
    w.style.cssText = `
      width:${this.width}px;
      height:${this.height}px;
      left:${this.x}px;
      top:${this.y}px;
      z-index:${this.z};
    `;
    w.innerHTML = `
      <div class="window-titlebar" data-drag-handle>
        <div class="window-traffic">
          <button class="window-tl tl-close"   data-action="close"    aria-label="關閉"></button>
          <button class="window-tl tl-min"     data-action="minimize" aria-label="最小化"></button>
          <button class="window-tl tl-max"     data-action="maximize" aria-label="放大/還原"></button>
        </div>
        <div class="window-title">${this.title}</div>
        <div class="window-titlebar-spacer"></div>
      </div>
      <div class="window-body">${this.content}</div>
    `;
    return w;
  }

  _wireEvents() {
    // Traffic lights
    this.el.querySelectorAll(".window-tl").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        if (action === "close") this.close();
        else if (action === "minimize") this.minimize();
        else if (action === "maximize") this.toggleMaximize();
      });
    });

    // Click anywhere → focus
    this.el.addEventListener("mousedown", () => this.focus());

    // Drag titlebar
    const titlebar = this.el.querySelector("[data-drag-handle]");
    let startX, startY, startLeft, startTop;
    let dragging = false;

    const onMove = (e) => {
      if (!dragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      // 防拖到 menubar 上方
      const newTop = Math.max(28, startTop + dy);
      this.el.style.left = `${startLeft + dx}px`;
      this.el.style.top = `${newTop}px`;
    };
    const onUp = () => {
      dragging = false;
      this.el.classList.remove("dragging");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };

    titlebar.addEventListener("mousedown", (e) => {
      // 不對 traffic lights 拖
      if (e.target.closest(".window-tl")) return;
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = this.el.getBoundingClientRect();
      startLeft = rect.left;
      startTop = rect.top;
      this.el.classList.add("dragging");
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      this.focus();
    });

    // Double-click titlebar = maximize
    titlebar.addEventListener("dblclick", (e) => {
      if (e.target.closest(".window-tl")) return;
      this.toggleMaximize();
    });
  }

  focus() {
    if (this.z !== _topZ) {
      this.z = ++_topZ;
      this.el.style.zIndex = String(this.z);
    }
    document.querySelectorAll(".macos-window").forEach(w => {
      w.classList.toggle("focused", w === this.el);
    });
  }

  minimize() {
    // MVP · 純 hide(v1.5 加飛回 dock 動畫)
    this.el.style.display = "none";
    this.minimized = true;
    if (window.toast) window.toast.info(`${this.title} 已最小化(v1.5 加恢復)`);
  }

  toggleMaximize() {
    if (this.maximized) {
      // 還原
      const rect = this._origRect;
      if (rect) {
        this.el.style.left = `${rect.left}px`;
        this.el.style.top = `${rect.top}px`;
        this.el.style.width = `${rect.width}px`;
        this.el.style.height = `${rect.height}px`;
      }
      this.maximized = false;
      this.el.classList.remove("maximized");
    } else {
      // 記原狀
      const rect = this.el.getBoundingClientRect();
      this._origRect = { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
      // 全螢幕(避讓 menubar 28 + 邊 12 + dock 80)
      this.el.style.left = "12px";
      this.el.style.top = "40px";
      this.el.style.width = `${window.innerWidth - 24}px`;
      this.el.style.height = `${window.innerHeight - 130}px`;
      this.maximized = true;
      this.el.classList.add("maximized");
    }
  }

  close() {
    // Spring out · 用 absolute 定位 · 不用 translateX
    if (this.el.animate) {
      this.el.animate(
        [
          { opacity: 1, transform: "scale(1)" },
          { opacity: 0, transform: "scale(0.94)" },
        ],
        { duration: 200, easing: "cubic-bezier(0.4, 0, 1, 1)", fill: "forwards" },
      ).onfinish = () => this._destroy();
    } else {
      this._destroy();
    }
  }

  // 修 2026-04-26 · 確認沒殘餘 transform · 給 drag 用乾淨座標
  _resetTransform() {
    this.el.style.transform = "";
  }

  _destroy() {
    this.el.remove();
    _windows.delete(this.id);
    if (this.onClose) try { this.onClose(); } catch {}
  }
}

// ============================================================
// Public API
// ============================================================
let _cssLoaded = false;
function _ensureCss() {
  // v1.20 perf · lazy load window CSS · 沒 openWindow 的 user 不付 ~4KB CSS
  if (_cssLoaded || document.querySelector('link[data-lazy-css="window"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "/static/styles/window.css?v=2";
  link.dataset.lazyCss = "window";
  document.head.appendChild(link);
  _cssLoaded = true;
}

export function openWindow(opts) {
  _ensureCss();  // v1.20 · 第一次 open 才注入 CSS
  // 同 id 已開 · 直接 focus
  if (_windows.has(opts.id)) {
    const w = _windows.get(opts.id);
    w.focus();
    if (w.minimized) {
      w.el.style.display = "";
      w.minimized = false;
    }
    return w;
  }
  const w = new MacWindow(opts);
  _windows.set(opts.id, w);
  return w;
}

export function closeWindow(id) {
  const w = _windows.get(id);
  if (w) w.close();
}

export function getActiveWindow() {
  let active = null;
  let topZ = 0;
  _windows.forEach(w => {
    if (!w.minimized && w.z > topZ) {
      topZ = w.z;
      active = w;
    }
  });
  return active;
}

// ============================================================
// Global ⌘W · 關 active window(若有)
// ============================================================
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "w") {
    const active = getActiveWindow();
    if (active) {
      e.preventDefault();
      active.close();
    }
  }
});

// expose for menubar / debug
if (typeof window !== "undefined") {
  window.macWindow = { openWindow, closeWindow, getActiveWindow };
}

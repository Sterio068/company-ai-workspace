/**
 * Mobile 漢堡選單 + Sidebar Drawer + Bottom Nav · 手機可用
 *
 * v1.3 batch4 P1#6 · 加底部 nav · 5 工作區一鍵切
 *   pattern 同 Twitter / Instagram · 拇指可達
 */

// 5 個 workspace 對應的底部 nav · 加 + Dashboard 共 6 個
const BOTTOM_NAV = [
  { ws: "0", icon: "🏠", label: "首頁", href: "#dashboard" },
  { ws: "1", icon: "🎯", label: "投標", href: "#workspace-1" },
  { ws: "2", icon: "🎪", label: "活動", href: "#workspace-2" },
  { ws: "3", icon: "🎨", label: "設計", href: "#workspace-3" },
  { ws: "4", icon: "📣", label: "公關", href: "#workspace-4" },
  { ws: "5", icon: "📊", label: "營運", href: "#workspace-5" },
];

export const mobile = {
  overlay: null,
  bottomNav: null,
  menuButton: null,
  sidebar: null,
  _lastFocus: null,
  _boundKeyHandler: null,
  _boundResizeHandler: null,

  init() {
    const btn = document.createElement("button");
    btn.className = "mobile-menu-btn";
    btn.type = "button";
    btn.innerHTML = "☰";
    btn.setAttribute("aria-label", "開啟選單");
    btn.setAttribute("aria-controls", "app-sidebar");
    btn.setAttribute("aria-expanded", "false");
    btn.onclick = () => this.toggle();
    document.body.appendChild(btn);
    this.menuButton = btn;

    this.sidebar = document.getElementById("app-sidebar") || document.querySelector(".sidebar");
    if (this.sidebar && !this.sidebar.id) this.sidebar.id = "app-sidebar";

    this.overlay = document.createElement("div");
    this.overlay.className = "mobile-overlay";
    this.overlay.onclick = () => this.close();
    document.body.appendChild(this.overlay);

    // 選 sidebar 項目後自動關閉 drawer
    document.addEventListener("click", (e) => {
      if (e.target.closest(".sidebar .nav-item, .sidebar [data-agent], .sidebar a[href]")) {
        if (window.innerWidth <= 768) setTimeout(() => this.close(), 100);
      }
    });

    this._buildBottomNav();
    this._boundKeyHandler = e => {
      if (e.key === "Escape" && document.body.classList.contains("mobile-drawer-open")) {
        e.preventDefault();
        this.close({ restoreFocus: true });
      }
    };
    document.addEventListener("keydown", this._boundKeyHandler);
    this._boundResizeHandler = () => this._syncSidebarA11y(document.body.classList.contains("mobile-drawer-open"));
    window.addEventListener("resize", this._boundResizeHandler);
    this._syncSidebarA11y(false);
  },

  // v1.3 batch4 · 行動端底部 nav · 拇指區可達
  _buildBottomNav() {
    const nav = document.createElement("nav");
    nav.className = "mobile-bottom-nav";
    nav.setAttribute("role", "navigation");
    nav.setAttribute("aria-label", "工作區快選");
    nav.innerHTML = BOTTOM_NAV.map(item => `
      <a class="mobile-bottom-item" href="${item.href}" data-ws="${item.ws}" aria-label="${item.label}">
        <div class="mobile-bottom-icon" aria-hidden="true">${item.icon}</div>
        <div class="mobile-bottom-label">${item.label}</div>
      </a>
    `).join("");
    document.body.appendChild(nav);
    this.bottomNav = nav;

    // 高亮當前 workspace
    nav.addEventListener("click", e => {
      const item = e.target.closest(".mobile-bottom-item");
      if (!item) return;
      e.preventDefault();
      if (item.dataset.ws === "0") window.app?.showView?.("dashboard");
      else window.app?.openWorkspace?.(Number(item.dataset.ws));
      nav.querySelectorAll(".mobile-bottom-item").forEach(el => {
        el.classList.remove("active");
        el.removeAttribute("aria-current");
      });
      item.classList.add("active");
      item.setAttribute("aria-current", "page");  // v1.3 batch6 · SR 唸「目前頁面」
    });

    // 監聽 workspace 切換 · sync active state
    document.addEventListener("ws-changed", (e) => {
      this._syncBottomNav(String(e.detail?.ws || "0"));
    });
    this._syncBottomNav(this._currentWsFromLocation());
  },

  toggle() {
    const open = document.body.classList.toggle("mobile-drawer-open");
    if (open) this._lastFocus = document.activeElement;
    this.overlay.classList.toggle("open", open);
    this._syncSidebarA11y(open);
    if (open) {
      requestAnimationFrame(() => {
        this.sidebar?.querySelector(".sidebar-item:not([style*='display:none']), a[href], button")?.focus();
      });
    }
  },

  close({ restoreFocus = false } = {}) {
    document.body.classList.remove("mobile-drawer-open");
    this.overlay.classList.remove("open");
    this._syncSidebarA11y(false);
    if (restoreFocus) {
      const target = this._lastFocus instanceof HTMLElement ? this._lastFocus : this.menuButton;
      requestAnimationFrame(() => target?.focus?.());
    }
  },

  _syncSidebarA11y(open) {
    const isMobile = window.innerWidth <= 768;
    this.menuButton?.setAttribute("aria-expanded", open ? "true" : "false");
    this.menuButton?.setAttribute("aria-label", open ? "關閉選單" : "開啟選單");
    if (!this.sidebar) return;
    if (isMobile && !open) {
      this.sidebar.setAttribute("aria-hidden", "true");
      this.sidebar.inert = true;
    } else {
      this.sidebar.removeAttribute("aria-hidden");
      this.sidebar.inert = false;
    }
  },

  _syncBottomNav(ws) {
    if (!this.bottomNav) return;
    this.bottomNav.querySelectorAll(".mobile-bottom-item").forEach(el => {
      const isActive = el.dataset.ws === ws;
      el.classList.toggle("active", isActive);
      if (isActive) el.setAttribute("aria-current", "page");
      else el.removeAttribute("aria-current");
    });
  },

  _currentWsFromLocation() {
    const hash = window.location.hash || "";
    const match = hash.match(/workspace-(\d)/);
    if (match) return match[1];
    return "0";
  },
};

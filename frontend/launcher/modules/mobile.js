/**
 * Mobile 漢堡選單 + Sidebar Drawer · 手機可用
 */
export const mobile = {
  overlay: null,

  init() {
    const btn = document.createElement("button");
    btn.className = "mobile-menu-btn";
    btn.innerHTML = "☰";
    btn.setAttribute("aria-label", "開啟選單");
    btn.onclick = () => this.toggle();
    document.body.appendChild(btn);

    this.overlay = document.createElement("div");
    this.overlay.className = "mobile-overlay";
    this.overlay.onclick = () => this.close();
    document.body.appendChild(this.overlay);

    // 選 sidebar 項目後自動關閉
    document.addEventListener("click", (e) => {
      if (e.target.closest(".sidebar .nav-item, .sidebar [data-agent], .sidebar a[href]")) {
        if (window.innerWidth <= 768) setTimeout(() => this.close(), 100);
      }
    });
  },

  toggle() {
    const open = document.body.classList.toggle("mobile-drawer-open");
    this.overlay.classList.toggle("open", open);
  },

  close() {
    document.body.classList.remove("mobile-drawer-open");
    this.overlay.classList.remove("open");
  },
};

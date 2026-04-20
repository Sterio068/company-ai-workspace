/**
 * ⌘K 全域搜尋 palette
 * 動態來源由 app 注入(views / agents / projects / skills)
 */
import { escapeHtml } from "./util.js";

export const palette = {
  _actions: [],
  _source: null,   // () => [{icon, label, hint, action}]

  bind(sourceFn) { this._source = sourceFn; },

  open() {
    document.getElementById("palette-backdrop")?.classList.add("open");
    document.getElementById("palette")?.classList.add("open");
    const input = document.getElementById("palette-input");
    if (input) {
      input.value = "";
      input.focus();
    }
    this.render("");
    this._bindInputOnce();
  },

  close() {
    document.getElementById("palette-backdrop")?.classList.remove("open");
    document.getElementById("palette")?.classList.remove("open");
  },

  render(q) {
    const items = this._source?.() || [];
    const filtered = q
      ? items.filter(i => (i.label + i.hint).toLowerCase().includes(q.toLowerCase()))
      : items;
    const root = document.getElementById("palette-results");
    if (!root) return;
    root.innerHTML = filtered.slice(0, 10).map((it, i) => `
      <div class="palette-item ${i === 0 ? "active" : ""}" data-idx="${i}">
        <div class="palette-icon">${it.icon}</div>
        <div class="palette-label">${escapeHtml(it.label)}</div>
        <div class="palette-hint">${escapeHtml(it.hint || "")}</div>
      </div>
    `).join("");
    root.querySelectorAll(".palette-item").forEach((el, i) => {
      el.addEventListener("click", () => { this.close(); filtered[i].action(); });
    });
    this._actions = filtered;
  },

  _bindInputOnce() {
    if (this._bound) return;
    this._bound = true;
    const input = document.getElementById("palette-input");
    if (!input) return;
    input.addEventListener("input", e => this.render(e.target.value));
    input.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        const active = document.querySelector(".palette-item.active");
        if (active && this._actions) {
          const idx = parseInt(active.dataset.idx);
          this.close();
          this._actions[idx]?.action();
        }
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const items = [...document.querySelectorAll(".palette-item")];
        const curr = items.findIndex(x => x.classList.contains("active"));
        const next = e.key === "ArrowDown"
          ? Math.min(items.length - 1, curr + 1)
          : Math.max(0, curr - 1);
        items.forEach(x => x.classList.remove("active"));
        items[next]?.classList.add("active");
        items[next]?.scrollIntoView({ block: "nearest" });
      }
    });
  },
};

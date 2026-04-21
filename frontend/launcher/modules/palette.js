/**
 * ⌘K 全域搜尋 palette
 * 動態來源由 app 注入(views / agents / projects / skills)
 */
import { escapeHtml } from "./util.js";

export const palette = {
  _actions: [],
  _source: null,   // () => [{icon, label, hint, action}]
  _asyncSources: [],  // [async (q) => items[]] · V1.1 §E-3 知識庫加入
  _asyncTimer: null,

  bind(sourceFn) { this._source = sourceFn; },

  /**
   * 加 async 資料源(例如 /knowledge/search)· debounce 300ms
   * 回傳 items 會 append 到結果底部 · 分隔線區分
   */
  addAsyncSource(searchFn) { this._asyncSources.push(searchFn); },

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
    this._renderItems(filtered.slice(0, 10));
    this._actions = filtered.slice(0, 10);

    // V1.1 §E-3 · 觸發 async 來源(知識庫全文)· debounce 300ms
    if (this._asyncTimer) clearTimeout(this._asyncTimer);
    if (q && q.length >= 2 && this._asyncSources.length) {
      this._asyncTimer = setTimeout(async () => {
        const async_items = (await Promise.all(
          this._asyncSources.map(fn => fn(q).catch(() => []))
        )).flat();
        if (async_items.length) {
          const combined = [...filtered.slice(0, 8), ...async_items.slice(0, 5)];
          this._actions = combined;
          this._renderItems(combined, { asyncStart: Math.min(8, filtered.length) });
        }
      }, 300);
    }
  },

  _renderItems(items, opts = {}) {
    const root = document.getElementById("palette-results");
    if (!root) return;
    const asyncStart = opts.asyncStart ?? -1;
    root.innerHTML = items.map((it, i) => `
      ${i === asyncStart ? '<div class="palette-sep">📚 知識庫結果</div>' : ''}
      <div class="palette-item ${i === 0 ? "active" : ""}" data-idx="${i}">
        <div class="palette-icon">${it.icon}</div>
        <div class="palette-label">${escapeHtml(it.label)}</div>
        <div class="palette-hint">${escapeHtml(it.hint || "")}</div>
      </div>
    `).join("");
    root.querySelectorAll(".palette-item").forEach((el, i) => {
      el.addEventListener("click", () => { this.close(); items[i].action(); });
    });
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

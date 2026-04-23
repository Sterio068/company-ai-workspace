/**
 * Tenders view · g0v 政府採購網每日新標案監測
 */
import { escapeHtml, skeletonCards } from "./util.js";

const BASE = "/api-accounting/tender-alerts";

export const tenders = {
  filter: "all",
  _filterBound: false,

  async load() {
    await this.refresh();
    this.bindFilter();  // 內部 guard · 只綁一次
  },

  bindFilter() {
    if (this._filterBound) return;
    this._filterBound = true;
    // Event delegation · 綁在父容器 · 避免元素重繪後 listener 丟失
    const parent = document.querySelector(".view-tenders .projects-filter");
    if (!parent) return;
    parent.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-tender-filter]");
      if (!btn) return;
      parent.querySelectorAll("[data-tender-filter]").forEach(x => x.classList.remove("active"));
      btn.classList.add("active");
      this.filter = btn.dataset.tenderFilter;
      await this.refresh();
    });
  },

  async refresh() {
    const root = document.getElementById("tenders-list");
    if (!root) return;
    root.innerHTML = skeletonCards(3);
    const q = this.filter === "all" ? "" : `?status=${this.filter}`;
    try {
      const r = await fetch(`${BASE}${q}`);
      const items = await r.json();
      const count = document.getElementById("tender-count");
      if (count) count.textContent = items.filter(i => i.status === "new").length;
      if (!items.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🎯</div>
            <div class="empty-state-title">尚無符合標案</div>
            <div class="empty-state-hint">每日 06:00 自動抓 · 或按上方「🔄 重新抓取」立即跑</div>
          </div>`;
        return;
      }
      // v4.6 · 分批 render(Round 6 reviewer 紅線:舊 Intel 機長列表掉幀)
      // 先 render 前 20 筆 · 剩下用 requestIdleCallback 補
      const FIRST_BATCH = 20;
      const renderItem = (t) => {
        const typeLabel = t.brief_type || "公告";
        const date = t.date ? String(t.date).slice(0, 8) : "";
        return `
          <div class="recent-item" data-tender-key="${escapeHtml(t.tender_key)}">
            <div class="recent-title">${escapeHtml(t.title)}</div>
            <span class="recent-agent">${escapeHtml(t.unit_name)} · ${typeLabel}</span>
            <div class="recent-time">${date} · ${escapeHtml(t.keyword)}</div>
            <div style="display:flex;gap:4px;margin-left:auto">
              <button class="btn-ghost" style="padding:2px 8px;font-size:11px"
                      data-tender-action="interested" data-tender-key="${escapeHtml(t.tender_key)}">✨</button>
              <button class="btn-ghost" style="padding:2px 8px;font-size:11px"
                      data-tender-action="skipped" data-tender-key="${escapeHtml(t.tender_key)}">🗑</button>
            </div>
          </div>
        `;
      };
      root.innerHTML = items.slice(0, FIRST_BATCH).map(renderItem).join("");
      if (items.length > FIRST_BATCH) {
        const ric = window.requestIdleCallback || ((cb) => setTimeout(cb, 16));
        ric(() => {
          const more = document.createElement("div");
          more.innerHTML = items.slice(FIRST_BATCH).map(renderItem).join("");
          while (more.firstChild) root.appendChild(more.firstChild);
        });
      }
      // event delegation 綁在 root · 後續分批 append 也能吃到
      if (!root.dataset.delegated) {
        root.dataset.delegated = "1";
        root.addEventListener("click", e => {
          const btn = e.target.closest("[data-tender-action]");
          if (!btn) return;
          e.stopPropagation();
          this.mark(btn.dataset.tenderKey, btn.dataset.tenderAction);
        });
      }
    } catch (e) {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">😓</div>
          <div class="empty-state-title">無法載入標案</div>
          <div class="empty-state-hint">${(e?.message || "政府電子採購網可能暫時連不上")}</div>
          <button class="btn-ghost" onclick="window.tenders?.refresh?.()" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  async mark(tenderKey, status) {
    await fetch(`${BASE}/${encodeURIComponent(tenderKey)}?status=${status}`, { method: "PUT" });
    await this.refresh();
  },
};

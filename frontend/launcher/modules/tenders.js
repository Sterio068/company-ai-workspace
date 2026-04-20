/**
 * Tenders view · g0v 政府採購網每日新標案監測
 */
import { escapeHtml, skeletonCards } from "./util.js";

const BASE = "/api-accounting/tender-alerts";

export const tenders = {
  filter: "all",

  async load() {
    await this.refresh();
    this.bindFilter();
  },

  bindFilter() {
    document.querySelectorAll("[data-tender-filter]").forEach(el => {
      el.addEventListener("click", async () => {
        document.querySelectorAll("[data-tender-filter]").forEach(x => x.classList.remove("active"));
        el.classList.add("active");
        this.filter = el.dataset.tenderFilter;
        await this.refresh();
      });
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
        root.innerHTML = '<div class="chip-empty">尚無標案符合條件 · 可能 cron 還沒跑</div>';
        return;
      }
      root.innerHTML = items.map(t => {
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
      }).join("");
      // 用 event delegation 綁動作按鈕,不走 inline onclick
      root.querySelectorAll("[data-tender-action]").forEach(btn => {
        btn.addEventListener("click", e => {
          e.stopPropagation();
          this.mark(btn.dataset.tenderKey, btn.dataset.tenderAction);
        });
      });
    } catch {
      root.innerHTML = '<div class="chip-empty">❌ 無法載入標案</div>';
    }
  },

  async mark(tenderKey, status) {
    await fetch(`${BASE}/${encodeURIComponent(tenderKey)}?status=${status}`, { method: "PUT" });
    await this.refresh();
  },
};

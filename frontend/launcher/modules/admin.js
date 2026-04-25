/**
 * Admin Dashboard · 成本 / 品質 / 用量總覽
 */
import { escapeHtml } from "./util.js";
import { authFetch } from "./auth.js";

const BASE = "/api-accounting";

export const admin = {
  async load() { await this.refresh(); },

  async refresh() {
    await Promise.all([this.loadDashboard(), this.loadAgentStats(), this.loadCost()]);
  },

  async loadDashboard() {
    try {
      const r = await authFetch(`${BASE}/admin/dashboard`);
      if (!r.ok) throw new Error(r.statusText);
      const d = await r.json();
      setText("admin-income",          (d.accounting.month_income  / 10000).toFixed(1) + "萬");
      setText("admin-expense",         (d.accounting.month_expense / 10000).toFixed(1) + "萬");
      setText("admin-net",             (d.accounting.month_net     / 10000).toFixed(1) + "萬");
      setText("admin-projects",        d.projects.active);
      setText("admin-satisfaction",    d.feedback.satisfaction_rate + "%");
      setText("admin-feedback-total",  d.feedback.total);
      setText("admin-convos",          d.conversations.this_month);
      setText("admin-convos-total",    d.conversations.total);
    } catch {
      ["admin-income", "admin-expense", "admin-net", "admin-projects",
       "admin-satisfaction", "admin-feedback-total", "admin-convos", "admin-convos-total"]
       .forEach(id => setText(id, "⚠"));
    }
  },

  async loadAgentStats() {
    const root = document.getElementById("admin-agent-stats");
    if (!root) return;
    try {
      const r = await authFetch(`${BASE}/feedback/stats`);
      const stats = await r.json();
      if (!stats.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">👍</div>
            <div class="empty-state-title">尚無回饋資料</div>
            <div class="empty-state-hint">同仁在對話按 👍 👎 累積一段時間後才會有統計</div>
          </div>`;
        return;
      }
      stats.sort((a, b) => b.score - a.score);
      root.innerHTML = stats.map(s => {
        const color = s.score >= 80 ? "#34C759" : s.score >= 60 ? "#FF9500" : "#FF3B30";
        return `
          <div class="recent-item">
            <div class="recent-title">${escapeHtml(s.agent)}</div>
            <span class="recent-agent">👍 ${s.up} · 👎 ${s.down}</span>
            <div class="recent-time" style="color:${color}">${s.score}% 滿意</div>
          </div>
        `;
      }).join("");
    } catch {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔌</div>
          <div class="empty-state-title">無法連線介接服務</div>
          <div class="empty-state-hint">檢查 <code>docker compose ps</code> 會計服務是否啟動</div>
          <button class="btn-ghost" onclick="window.admin?.loadAgentStats()" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  async loadCost() {
    const root = document.getElementById("admin-cost-stats");
    if (!root) return;
    try {
      const r = await authFetch(`${BASE}/admin/cost?days=30`);
      const d = await r.json();
      if (d.error || !d.by_model) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <div class="empty-state-title">尚無成本資料</div>
          <div class="empty-state-hint">對話交易紀錄尚未累積 · 有對話後才有統計</div>
          </div>`;
        return;
      }
      root.innerHTML = d.by_model.map(m => `
        <div class="recent-item">
          <div class="recent-title">${escapeHtml(m._id || "unknown")}</div>
          <span class="recent-agent">${(m.input_tokens || 0).toLocaleString()} 輸入 / ${(m.output_tokens || 0).toLocaleString()} 輸出</span>
          <div class="recent-time">${m.count} 次呼叫</div>
        </div>
      `).join("");
    } catch {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔌</div>
          <div class="empty-state-title">無法載入成本</div>
          <div class="empty-state-hint">檢查會計服務是否啟動</div>
          <button class="btn-ghost" onclick="window.admin?.loadCost()" style="margin-top:12px">重試</button>
        </div>`;
    }
  },
};

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

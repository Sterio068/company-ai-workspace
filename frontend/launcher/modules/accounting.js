/**
 * Accounting view · 承富內建會計模組前端
 */
import { escapeHtml } from "./util.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting";

export const accounting = {
  async load() {
    await Promise.all([this.loadStats(), this.loadTransactions(), this.loadInvoices()]);
  },

  async loadStats() {
    try {
      const today = new Date();
      const from = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
      const to = today.toISOString().slice(0, 10);
      const r = await fetch(`${BASE}/reports/pnl?date_from=${from}&date_to=${to}`);
      if (r.ok) {
        const d = await r.json();
        setText("acc-month-income",  (d.total_income  / 10000).toFixed(1) + "萬");
        setText("acc-month-expense", (d.total_expense / 10000).toFixed(1) + "萬");
        setText("acc-month-profit",  (d.net_profit    / 10000).toFixed(1) + "萬");
      }
    } catch {}
    try {
      const r = await fetch(`${BASE}/reports/aging`);
      if (r.ok) {
        const d = await r.json();
        setText("acc-aging-90", ((d.buckets["90+"] || 0) / 10000).toFixed(1) + "萬");
      }
    } catch {}
  },

  async loadTransactions() {
    const root = document.getElementById("acc-transactions");
    if (!root) return;
    try {
      const r = await fetch(`${BASE}/transactions?limit=10`);
      const txs = await r.json();
      setText("accounting-tx-count", txs.length);
      if (!txs.length) {
        root.innerHTML = '<div class="chip-empty">尚無交易 · 找財務試算 Agent 記第一筆</div>';
        return;
      }
      root.innerHTML = txs.map(tx => `
        <div class="recent-item">
          <div class="recent-title">${escapeHtml(tx.memo)}</div>
          <span class="recent-agent">${tx.debit_account} / ${tx.credit_account}</span>
          <div class="recent-time">${tx.date} · NT$ ${Number(tx.amount).toLocaleString()}</div>
        </div>
      `).join("");
    } catch {
      root.innerHTML = '<div class="chip-empty">❌ 會計服務未就緒 · 檢查 docker compose ps accounting</div>';
    }
  },

  async loadInvoices() {
    const root = document.getElementById("acc-invoices");
    if (!root) return;
    try {
      const r = await fetch(`${BASE}/invoices`);
      const invs = await r.json();
      if (!invs.length) { root.innerHTML = '<div class="chip-empty">尚無發票</div>'; return; }
      root.innerHTML = invs.slice(0, 6).map(inv => `
        <article class="project-card">
          <div class="project-card-name">${inv.invoice_no}</div>
          <div class="project-card-client">${escapeHtml(inv.customer)}</div>
          <div class="project-card-meta">
            <span>${inv.date}</span>
            <span>NT$ ${Number(inv.total).toLocaleString()}</span>
            <span>${inv.status}</span>
          </div>
        </article>
      `).join("");
    } catch {}
  },

  newTransaction() {
    modal.alert(
      "新交易請透過 <strong>💰 財務試算</strong> Agent 輸入,它會自動呼叫會計 API 處理。<br><br>或直接用 API:<code>POST /api-accounting/transactions</code>",
      { title: "新交易", icon: "💰", primary: "知道了" }
    );
  },
};

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

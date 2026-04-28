/**
 * Accounting view · 內建會計模組前端
 */
import { escapeHtml, formatMoney } from "./util.js";
import { authFetch } from "./auth.js";
import { modal } from "./modal.js";
import { toast, networkError, operationError } from "./toast.js";
import { markTaskDone } from "./help-state.js";

const BASE = "/api-accounting";

export const accounting = {
  overview: null,
  invoices: [],
  quotes: [],

  async load() {
    await Promise.all([this.loadStats(), this.loadTransactions(), this.loadInvoices()]);
  },

  async loadStats() {
    try {
      const r = await authFetch(`${BASE}/reports/overview`);
      if (r.ok) {
        const d = await r.json();
        this.overview = d;
        setText("acc-month-income",  toWan(d.pnl?.total_income));
        setText("acc-month-expense", toWan(d.pnl?.total_expense));
        setText("acc-month-profit",  toWan(d.pnl?.net_profit));
        setText("acc-aging-90", toWan(d.aging?.buckets?.["90+"] || 0));
        this.renderCommandCenter();
      }
    } catch {}
  },

  renderCommandCenter() {
    const root = document.getElementById("accounting-command-center");
    if (!root) return;
    const o = this.overview || {};
    const net = Number(o.pnl?.net_profit || 0);
    const unpaidTotal = Number(o.unpaid?.total || 0);
    const quoteTotal = Number(o.quotes?.active_total || 0);
    const unpaidCount = Number(o.unpaid?.count || 0);
    const quoteCount = Number(o.quotes?.active_count || 0);
    const txCount = Number(o.recent_transactions_count || 0);
    const health = net >= 0 ? "本月目前為正毛利" : "本月目前為負毛利";
    const nextAction = unpaidCount > 0
      ? "先追應收款"
      : quoteCount > 0
      ? "檢查報價有效期"
      : "補今天交易";
    root.innerHTML = `
      <div class="ops-command-card primary">
        <span class="ops-command-kicker">今日財務接續</span>
        <strong>${escapeHtml(nextAction)}</strong>
        <p>${escapeHtml(health)} · ${txCount ? `最近已有 ${txCount} 筆交易` : "今天還沒有近期交易,建議先補帳。"}</p>
        <div class="ops-command-actions">
          <button class="btn-primary" type="button" data-action="accounting.newTransaction">新增交易</button>
          <button class="btn-ghost" type="button" data-action="accounting.newInvoice">開發票</button>
          <button class="btn-ghost" type="button" data-action="accounting.newQuote">建報價</button>
        </div>
      </div>
      <div class="ops-command-card">
        <span class="ops-command-kicker">待收款</span>
        <strong>${formatMoney(unpaidTotal)}</strong>
        <p>${unpaidCount} 張草稿/已開發票${o.unpaid?.oldest_date ? ` · 最早 ${escapeHtml(o.unpaid.oldest_date)}` : ""}</p>
      </div>
      <div class="ops-command-card">
        <span class="ops-command-kicker">報價追蹤</span>
        <strong>${formatMoney(quoteTotal)}</strong>
        <p>${quoteCount} 張草稿/已送出${o.quotes?.next_expiring ? ` · 最近 ${escapeHtml(o.quotes.next_expiring)} 到期` : ""}</p>
      </div>
      <div class="ops-command-card">
        <span class="ops-command-kicker">帳務健康</span>
        <strong>${net >= 0 ? "可交付" : "需檢查毛利"}</strong>
        <p>${net >= 0 ? "本月淨利為正,持續確認應收。" : "本月為負,先檢查外包與場地費是否歸到正確專案。"}</p>
      </div>
    `;
  },

  async loadTransactions() {
    const root = document.getElementById("acc-transactions");
    if (!root) return;
    try {
      const r = await authFetch(`${BASE}/transactions?limit=10`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const txs = await r.json();
      setText("accounting-tx-count", txs.length);
      if (!txs.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">💰</div>
            <div class="empty-state-title">尚無會計交易</div>
            <div class="empty-state-hint">找「財務試算助手」記第一筆(收入 / 支出 / 發票)</div>
          </div>`;
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
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚠️</div>
          <div class="empty-state-title">會計服務未就緒</div>
          <div class="empty-state-hint">執行 <code>docker compose ps accounting</code> 檢查</div>
        </div>`;
    }
  },

  async loadInvoices() {
    const root = document.getElementById("acc-invoices");
    if (!root) return;
    try {
      const [invR, quoteR] = await Promise.all([
        authFetch(`${BASE}/invoices`),
        authFetch(`${BASE}/quotes`),
      ]);
      if (!invR.ok || !quoteR.ok) throw new Error(`HTTP ${invR.status}/${quoteR.status}`);
      const invs = await invR.json();
      const quotes = await quoteR.json();
      this.invoices = invs;
      this.quotes = quotes;
      const cards = [
        ...invs.slice(0, 4).map(inv => ({ type: "發票", no: inv.invoice_no, customer: inv.customer, date: inv.date, total: inv.total, status: inv.status })),
        ...quotes.slice(0, 4).map(q => ({ type: "報價", no: q.quote_no, customer: q.customer, date: q.valid_until, total: q.total, status: q.status })),
      ].slice(0, 6);
      if (!cards.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🧾</div>
            <div class="empty-state-title">尚無發票</div>
            <div class="empty-state-hint">用「+ 開發票」或請財務試算助手建立第一筆</div>
          </div>`;
        return;
      }
      root.innerHTML = cards.map(item => `
        <article class="project-card">
          <div class="project-card-name">${escapeHtml(item.no || item.type)}</div>
          <div class="project-card-client">${escapeHtml(item.customer)} · ${item.type}</div>
          <div class="project-card-meta">
            <span>${escapeHtml(item.date || "—")}</span>
            <span>${formatMoney(item.total)}</span>
            <span>${escapeHtml(item.status)}</span>
          </div>
        </article>
      `).join("");
    } catch {}
  },

  async newTransaction() {
    const today = new Date().toISOString().slice(0, 10);
    const data = await modal.prompt([
      { name: "date", label: "日期", type: "date", value: today, required: true },
      { name: "memo", label: "摘要", placeholder: "例:收文化局期中款 / 外包設計費", required: true },
      { name: "type", label: "類型", type: "select", value: "income", options: [
        { value: "income", label: "收入 · 銀行存款 / 服務收入" },
        { value: "outsource", label: "外包支出 · 外包支出 / 應付帳款" },
        { value: "venue", label: "場地費 · 場地費 / 應付帳款" },
        { value: "software", label: "軟體訂閱 · 軟體訂閱 / 應付帳款" },
        { value: "misc", label: "雜項費用 · 雜項費用 / 應付帳款" },
      ] },
      { name: "amount", label: "金額", type: "number", min: "1", required: true },
      { name: "counterparty", label: "客戶 / 廠商", placeholder: "例:臺北市文化局 / 王小明設計" },
      { name: "project_id", label: "工作包 ID(選填)", placeholder: "從工作包頁複製" },
    ], { title: "新增會計交易", icon: "💰", primary: "建立交易" });
    if (!data) return;
    const map = accountMap(data.type);
    const payload = {
      date: data.date,
      memo: data.memo,
      amount: Number(data.amount),
      debit_account: map.debit,
      credit_account: map.credit,
      project_id: data.project_id || null,
      customer: data.type === "income" ? data.counterparty || null : null,
      vendor: data.type !== "income" ? data.counterparty || null : null,
      tags: [data.type],
    };
    if (!payload.amount || payload.amount <= 0) {
      toast.warn("金額必須大於 0");
      return;
    }
    await this.postTransaction(payload);
  },

  async postTransaction(payload, retrySeed = true) {
    try {
      const r = await authFetch(`${BASE}/transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        if (retrySeed && String(err.detail || "").includes("科目")) {
          await authFetch(`${BASE}/accounts/seed`, { method: "POST" });
          return this.postTransaction(payload, false);
        }
        operationError("建立交易", err);
        return;
      }
      toast.success("交易已建立");
      markTaskDone("tutorial-accounting-transaction");
      await this.load();
    } catch (e) {
      networkError("建立交易", e, () => this.postTransaction(payload, retrySeed));
    }
  },

  async newInvoice() {
    const today = new Date().toISOString().slice(0, 10);
    const data = await modal.prompt([
      { name: "date", label: "日期", type: "date", value: today, required: true },
      { name: "customer", label: "客戶名稱", required: true },
      { name: "customer_tax_id", label: "統一編號(選填)", placeholder: "例:12345678" },
      { name: "description", label: "品項", value: "專案服務費", required: true },
      { name: "amount", label: "未稅金額 / 含稅總額", type: "number", min: "1", required: true },
      { name: "tax_included", label: "金額是否含稅", type: "select", value: "false", options: [
        { value: "false", label: "未稅 · 系統加 5%" },
        { value: "true", label: "含稅 · 系統拆稅額" },
      ] },
      { name: "project_id", label: "工作包 ID(選填)", placeholder: "從工作包頁複製" },
    ], { title: "開立發票草稿", icon: "🧾", primary: "建立發票" });
    if (!data) return;
    const amount = Number(data.amount);
    if (!amount || amount <= 0) {
      toast.warn("金額必須大於 0");
      return;
    }
    try {
      const r = await authFetch(`${BASE}/invoices`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: data.date,
          customer: data.customer,
          customer_tax_id: data.customer_tax_id || null,
          project_id: data.project_id || null,
          tax_included: data.tax_included === "true",
          items: [{ description: data.description, quantity: 1, unit_price: amount }],
        }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("建立發票", err);
        return;
      }
      const body = await r.json();
      toast.success(`發票草稿已建立 · ${body.invoice_no}`);
      markTaskDone("tutorial-accounting-invoice");
      await this.load();
    } catch (e) {
      networkError("建立發票", e);
    }
  },

  async newQuote() {
    const today = new Date();
    const date = today.toISOString().slice(0, 10);
    const validUntil = new Date(today.getTime() + 14 * 86400000).toISOString().slice(0, 10);
    const data = await modal.prompt([
      { name: "date", label: "報價日期", type: "date", value: date, required: true },
      { name: "customer", label: "客戶名稱", required: true },
      { name: "description", label: "品項", value: "專案服務費", required: true },
      { name: "amount", label: "未稅金額 / 含稅總額", type: "number", min: "1", required: true },
      { name: "tax_included", label: "金額是否含稅", type: "select", value: "false", options: [
        { value: "false", label: "未稅 · 系統加 5%" },
        { value: "true", label: "含稅 · 系統拆稅額" },
      ] },
      { name: "valid_until", label: "有效期限", type: "date", value: validUntil, required: true },
      { name: "terms", label: "付款 / 交付條件(選填)", type: "textarea", rows: 3, placeholder: "例:簽約後 50%,結案後 50%;報價 14 天內有效。" },
      { name: "project_id", label: "工作包 ID(選填)", placeholder: "從工作包頁複製" },
    ], { title: "建立報價草稿", icon: "📄", primary: "建立報價" });
    if (!data) return;
    const amount = Number(data.amount);
    if (!amount || amount <= 0) {
      toast.warn("金額必須大於 0");
      return;
    }
    try {
      const r = await authFetch(`${BASE}/quotes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: data.date,
          customer: data.customer,
          project_id: data.project_id || null,
          tax_included: data.tax_included === "true",
          valid_until: data.valid_until,
          terms: data.terms || null,
          items: [{ description: data.description, quantity: 1, unit_price: amount }],
        }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("建立報價", err);
        return;
      }
      const body = await r.json();
      toast.success(`報價草稿已建立 · ${body.quote_no}`);
      markTaskDone("tutorial-accounting-quote");
      await this.load();
    } catch (e) {
      networkError("建立報價", e);
    }
  },
};

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function toWan(value) {
  return (Number(value || 0) / 10000).toFixed(1) + "萬";
}

function accountMap(type) {
  const map = {
    income: { debit: "1102", credit: "4111" },
    outsource: { debit: "5101", credit: "2101" },
    venue: { debit: "5201", credit: "2101" },
    software: { debit: "5403", credit: "2101" },
    misc: { debit: "5901", credit: "2101" },
  };
  return map[type] || map.misc;
}

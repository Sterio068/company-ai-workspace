/**
 * CRM Pipeline · Kanban 拖拉 · 標案 → 得標 → 執行 閉環
 */
import { escapeHtml, localizeVisibleText } from "./util.js";
import { modal } from "./modal.js";
import { toast, networkError, operationError } from "./toast.js";
import { tpl } from "./tpl.js";
// v1.3 batch6 · 全 fetch 改 authFetch · 過去未帶 cookie · prod 嚴格 auth 會 401
import { authFetch } from "./auth.js";

const BASE = "/api-accounting/crm";
const STAGES = [
  { key: "lead",       label: "🆕 新機會",   color: "#8E8E93" },
  { key: "qualifying", label: "🔍 評估中",   color: "#D8851E" },
  { key: "proposing",  label: "📝 提案撰寫", color: "#D14B43" },
  { key: "submitted",  label: "📤 已送件",   color: "#8C5CB1" },
  { key: "won",        label: "🏆 得標",     color: "#5AB174" },
  { key: "lost",       label: "❌ 未得標",   color: "#D14B6F" },
  { key: "executing",  label: "⚙️ 執行中",   color: "#3F86C9" },
  { key: "closed",     label: "✅ 結案",     color: "#30D158" },
];

export const crm = {
  leads: [],
  draggedId: null,
  _currentUserEmail: "",

  setUser(email) { this._currentUserEmail = email || ""; },

  async load() {
    this.renderSkeleton();
    await Promise.all([this.loadLeads(), this.loadStats()]);
    this.render();
  },

  async loadLeads() {
    try {
      // R17#1 修 · backend 改 {items,total,...} shape · 加 limit=500 取足
      const r = await authFetch(`${BASE}/leads?limit=500`);
      const body = await r.json();
      // 向後相容 · 新舊 shape 都吃
      this.leads = Array.isArray(body) ? body : (body.items || []);
      const count = document.getElementById("crm-count");
      if (count) {
        count.textContent = this.leads.filter(l =>
          !["won", "lost", "closed"].includes(l.stage)).length;
      }
    } catch (e) {
      this.leads = [];
      networkError("讀取商機漏斗", e, () => this.load());
    }
  },

  async loadStats() {
    try {
      const r = await authFetch(`${BASE}/stats`);
      const s = await r.json();
      setText("crm-stat-total", s.total_leads || 0);
      setText("crm-stat-win-rate", (s.win_rate ?? "—") + (s.win_rate != null ? "%" : ""));
      setText("crm-stat-pipeline",
        s.active_pipeline_value ? (s.active_pipeline_value / 10000).toFixed(0) + "萬" : "—");
      const executingCount = (s.by_stage?.find(x => x.stage === "executing") || {}).count || 0;
      setText("crm-stat-active", executingCount);
    } catch {}
  },

  renderSkeleton() {
    const root = document.getElementById("kanban-board");
    if (!root) return;
    root.innerHTML = STAGES.map(s => `
      <div class="kanban-col" data-stage="${s.key}">
        <div class="kanban-col-head"><span>${s.label}</span></div>
        <div class="skeleton" style="height:60px;margin-bottom:8px"></div>
        <div class="skeleton" style="height:60px"></div>
      </div>
    `).join("");
  },

  render() {
    const root = document.getElementById("kanban-board");
    if (!root) return;

    // v1.3 batch4 · 全空態 · 提示先建第一筆
    if (this.leads.length === 0) {
      root.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          <div class="empty-state-icon">💼</div>
          <div class="empty-state-title">商機漏斗目前是空的</div>
          <div class="empty-state-hint">點上方「+ 新商機」開始 · 或「📢 從標案匯入」一鍵帶入「有興趣」標案</div>
        </div>`;
      localizeVisibleText(root);
      return;
    }

    // 建 column skeleton · column-level event delegation(避免每卡綁 listener)
    root.innerHTML = STAGES.map(stage => `
      <div class="kanban-col" data-stage="${stage.key}">
        <div class="kanban-col-head">
          <span>${escapeHtml(stage.label)}</span>
          <span class="kanban-col-count">${this.leads.filter(l => l.stage === stage.key).length}</span>
        </div>
      </div>
    `).join("");
    // v4.6 · 分批 render · 先塞前 20 卡(每 column)立刻可見
    // 剩下用 requestIdleCallback 在閒置時補上 · 舊 Intel 機不卡
    const FIRST_BATCH = 20;
    const stageGroups = STAGES.map(stage => ({
      stage, col: root.querySelector(`[data-stage="${stage.key}"]`),
      leads: this.leads.filter(l => l.stage === stage.key),
    }));
    stageGroups.forEach(({ col, leads }) => {
      leads.slice(0, FIRST_BATCH).forEach(lead => col.appendChild(this.renderCard(lead)));
      if (leads.length > FIRST_BATCH) {
        const ric = window.requestIdleCallback || ((cb) => setTimeout(cb, 16));
        ric(() => {
          leads.slice(FIRST_BATCH).forEach(lead => col.appendChild(this.renderCard(lead)));
          localizeVisibleText(col);
        });
      }
    });
    this.bindDnD(root);
    localizeVisibleText(root);
  },

  renderCard(lead) {
    const id = lead._id || lead.id;
    const budget   = lead.budget ? `💰 ${(lead.budget / 10000).toFixed(0)}萬` : "";
    const deadline = lead.deadline ? `📅 ${lead.deadline.slice(5)}` : "";
    const prob     = lead.probability ? `${Math.round(lead.probability * 100)}%` : "";
    const source   = lead.source === "tender_alert" ? "📢 採購網" : "";
    const card = tpl("tpl-lead-card", {
      title:    lead.title || "未命名",
      client:   lead.client || "",
      budget,
      deadline,
      source,
      prob,
    }, {
      attrs: { "data-lead-id": id },
    });
    localizeVisibleText(card);
    return card;
  },

  bindDnD(root) {
    root.querySelectorAll(".lead-card").forEach(card => {
      card.addEventListener("dragstart", e => {
        this.draggedId = card.dataset.leadId;
        card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
      });
      card.addEventListener("dragend", () => card.classList.remove("dragging"));
      card.addEventListener("click", () => this.openLead(card.dataset.leadId));
    });
    root.querySelectorAll(".kanban-col").forEach(col => {
      col.addEventListener("dragover", e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        col.classList.add("drag-over");
      });
      col.addEventListener("dragleave", () => col.classList.remove("drag-over"));
      col.addEventListener("drop", e => this.onDrop(e, col.dataset.stage));
    });
  },

  async onDrop(e, newStage) {
    e.preventDefault();
    e.currentTarget.classList.remove("drag-over");
    if (!this.draggedId) return;
    try {
      const r = await authFetch(`${BASE}/leads/${this.draggedId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: newStage, _by: this._currentUserEmail }),
      });
      if (!r.ok) {
        operationError("移動商機", await r.json().catch(() => ({})));
        return;
      }
      toast.success(`已移到「${STAGES.find(s => s.key === newStage).label}」`);
      this.draggedId = null;
      await this.load();
    } catch (e) {
      networkError("移動商機", e);
    }
  },

  async newLead() {
    const r = await modal.prompt([
      { name: "title",  label: "商機名稱",   required: true,  placeholder: "例:2026 環保局 AI 推廣案" },
      { name: "client", label: "客戶單位",   placeholder: "例:環境部環境管理署" },
      { name: "budget", label: "預算(NT$)", type: "number",  placeholder: "3000000" },
    ], { title: "新商機", primary: "建立", icon: "💼" });
    if (!r) return;
    try {
      const resp = await authFetch(`${BASE}/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: r.title,
          client: r.client,
          budget: r.budget ? parseInt(r.budget) : null,
          stage: "lead",
        }),
      });
      if (!resp.ok) {
        operationError("建立商機", await resp.json().catch(() => ({})));
        return;
      }
      toast.success("新商機已加入 · 拖到對應階段");
      await this.load();
    } catch (e) {
      networkError("建立商機", e);
    }
  },

  async importFromTenders() {
    try {
      const r = await authFetch(`${BASE}/import-from-tenders`, { method: "POST" });
      if (!r.ok) {
        operationError("從標案匯入", await r.json().catch(() => ({})));
        return;
      }
      const d = await r.json();
      toast.success(`已匯入 ${d.imported} 筆「有興趣」標案(共 ${d.total_interested} 筆標記)`);
      await this.load();
    } catch (e) {
      networkError("從標案匯入", e);
    }
  },

  openLead(leadId) {
    const lead = this.leads.find(l => (l._id || l.id) === leadId);
    if (!lead) return;
    const stageLabel = STAGES.find(s => s.key === lead.stage)?.label || lead.stage;
    const body = `
      <table style="width:100%;font-size:14px;line-height:1.8">
        <tr><td style="color:var(--text-secondary);width:80px">客戶</td><td><strong>${escapeHtml(lead.client || "—")}</strong></td></tr>
        <tr><td style="color:var(--text-secondary)">預算</td><td><strong>${lead.budget ? "NT$ " + lead.budget.toLocaleString() : "—"}</strong></td></tr>
        <tr><td style="color:var(--text-secondary)">期限</td><td>${lead.deadline || "—"}</td></tr>
        <tr><td style="color:var(--text-secondary)">勝率</td><td>${lead.probability ? Math.round(lead.probability * 100) + "%" : "—"}</td></tr>
        <tr><td style="color:var(--text-secondary)">階段</td><td>${stageLabel}</td></tr>
        <tr><td style="color:var(--text-secondary)">來源</td><td>${lead.source || "—"}</td></tr>
      </table>
      ${lead.description ? `<div style="margin-top:12px;padding:10px;background:var(--bg-base);border-radius:6px;font-size:13px;line-height:1.5">${escapeHtml(lead.description)}</div>` : ""}
    `;
    modal.alert(body, { title: lead.title, icon: "💼", primary: "關閉" });
  },
};

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

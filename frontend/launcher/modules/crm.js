/**
 * CRM Pipeline · Kanban 拖拉 · 標案 → 得標 → 執行 閉環
 */
import { escapeHtml, localizeVisibleText } from "./util.js";
import { modal } from "./modal.js";
import { toast, networkError, operationError } from "./toast.js";
import { tpl } from "./tpl.js";
import { markTaskDone } from "./help-state.js";
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
  stats: null,
  draggedId: null,
  _currentUserEmail: "",

  setUser(email) { this._currentUserEmail = email || ""; },

  async load() {
    this.renderSkeleton();
    await Promise.all([this.loadLeads(), this.loadStats()]);
    this.renderInsights();
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
      this.stats = s;
      setText("crm-stat-total", s.total_leads || 0);
      setText("crm-stat-win-rate", (s.win_rate ?? "—") + (s.win_rate != null ? "%" : ""));
      setText("crm-stat-pipeline",
        s.active_pipeline_value ? (s.active_pipeline_value / 10000).toFixed(0) + "萬" : "—");
      const executingCount = (s.by_stage?.find(x => x.stage === "executing") || {}).count || 0;
      setText("crm-stat-active", executingCount);
    } catch {}
  },

  renderInsights() {
    const root = document.getElementById("crm-insights");
    if (!root) return;
    const active = this.leads.filter(l => !["won", "lost", "closed"].includes(l.stage));
    const dueSoon = active
      .filter(l => daysUntil(l.deadline) !== null && daysUntil(l.deadline) <= 7)
      .sort((a, b) => (daysUntil(a.deadline) ?? 999) - (daysUntil(b.deadline) ?? 999));
    const stale = active
      .filter(l => daysSince(l.updated_at || l.created_at) >= 7)
      .sort((a, b) => daysSince(b.updated_at || b.created_at) - daysSince(a.updated_at || a.created_at));
    const nextLead = dueSoon[0]
      || active.find(l => l.stage === "submitted")
      || active.find(l => l.stage === "proposing")
      || active.find(l => l.stage === "qualifying")
      || active[0];
    const expected = Number(this.stats?.active_pipeline_value || 0);

    root.innerHTML = `
      <div class="ops-command-card primary">
        <span class="ops-command-kicker">今日追蹤</span>
        <strong>${nextLead ? escapeHtml(nextLead.title || "未命名商機") : "目前沒有待追商機"}</strong>
        <p>${nextLead
          ? `${escapeHtml(nextLead.client || "未填客戶")} · ${stageLabel(nextLead.stage)}${nextLead.deadline ? ` · 截止 ${escapeHtml(nextLead.deadline)}` : ""}`
          : "可先從標案匯入,或手動建立客戶機會。"}
        </p>
        <div class="ops-command-actions">
          ${nextLead ? `<button class="btn-primary" type="button" data-crm-open="${escapeHtml(nextLead._id || nextLead.id)}">打開商機</button>` : ""}
          <button class="btn-ghost" type="button" data-action="crm.importFromTenders">匯入標案</button>
        </div>
      </div>
      <div class="ops-command-card">
        <span class="ops-command-kicker">風險</span>
        <strong>${dueSoon.length} 件 7 天內到期</strong>
        <p>${dueSoon[0] ? escapeHtml(dueSoon[0].title || "未命名") : "沒有迫近期限,可以整理新機會或補客戶紀錄。"}</p>
      </div>
      <div class="ops-command-card">
        <span class="ops-command-kicker">跟進缺口</span>
        <strong>${stale.length} 件超過 7 天未更新</strong>
        <p>${stale[0] ? `最久未更新:${escapeHtml(stale[0].title || "未命名")}` : "目前沒有久未更新的進行中商機。"}</p>
      </div>
      <div class="ops-command-card">
        <span class="ops-command-kicker">預期管線</span>
        <strong>${formatMoney(expected)}</strong>
        <p>依預算與勝率估算,用來判斷本週追蹤優先順序。</p>
      </div>
    `;
    root.querySelectorAll("[data-crm-open]").forEach(btn => {
      btn.addEventListener("click", () => this.openLead(btn.getAttribute("data-crm-open")));
    });
    localizeVisibleText(root);
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
      { name: "deadline", label: "截止日(選填)", type: "date" },
      { name: "description", label: "目前狀態 / 需求摘要(選填)", type: "textarea", rows: 3, placeholder: "例:客戶希望 5 月初看第一版企劃,需先確認預算與場地。" },
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
          deadline: r.deadline || null,
          description: r.description || null,
          stage: "lead",
        }),
      });
      if (!resp.ok) {
        operationError("建立商機", await resp.json().catch(() => ({})));
        return;
      }
      toast.success("新商機已加入 · 拖到對應階段");
      markTaskDone("tutorial-crm-create-lead");
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
      markTaskDone("tutorial-crm-import-tender");
      await this.load();
    } catch (e) {
      networkError("從標案匯入", e);
    }
  },

  async openLead(leadId) {
    const lead = this.leads.find(l => (l._id || l.id) === leadId);
    if (!lead) return;
    const id = lead._id || lead.id;
    const pct = lead.probability ? Math.round(lead.probability * 100) : 50;
    const notes = (lead.notes || []).slice(-4).reverse();
    const body = `
      <div class="crm-detail">
        <div class="crm-detail-grid">
          <div><span>客戶</span><strong>${escapeHtml(lead.client || "未填")}</strong></div>
          <div><span>預算</span><strong>${lead.budget ? "NT$ " + Number(lead.budget).toLocaleString() : "未填"}</strong></div>
          <div><span>來源</span><strong>${escapeHtml(sourceLabel(lead.source))}</strong></div>
          <div><span>目前階段</span><strong>${stageLabel(lead.stage)}</strong></div>
        </div>

        <label>階段
          <select id="crm-detail-stage">
            ${STAGES.map(s => `<option value="${s.key}" ${s.key === lead.stage ? "selected" : ""}>${escapeHtml(s.label)}</option>`).join("")}
          </select>
        </label>
        <label>勝率(%)
          <input id="crm-detail-prob" type="number" min="0" max="100" step="5" value="${pct}">
        </label>
        <label>截止日
          <input id="crm-detail-deadline" type="date" value="${escapeHtml(lead.deadline || "")}">
        </label>
        <label>需求摘要 / 最新狀態
          <textarea id="crm-detail-desc" rows="3">${escapeHtml(lead.description || "")}</textarea>
        </label>
        <label>新增一筆跟進紀錄
          <textarea id="crm-detail-note" rows="3" placeholder="例:4/30 已電話確認預算,PM 週五前補企劃大綱。"></textarea>
        </label>

        <div class="crm-note-list">
          <b>最近紀錄</b>
          ${notes.length ? notes.map(n => `
            <div class="crm-note-item">
              <span>${escapeHtml(n.at ? new Date(n.at).toLocaleDateString("zh-TW") : "—")}</span>
              <p>${escapeHtml(n.text || "")}</p>
            </div>
          `).join("") : `<p class="muted">尚無跟進紀錄</p>`}
        </div>
      </div>
    `;
    await modal.openForm({
      title: lead.title || "商機詳情",
      icon: "💼",
      bodyHTML: body,
      primary: "儲存更新",
      cancel: "關閉",
      onSubmit: async () => {
        const stage = document.getElementById("crm-detail-stage")?.value || lead.stage;
        const probability = Math.max(0, Math.min(100, Number(document.getElementById("crm-detail-prob")?.value || 0))) / 100;
        const deadline = document.getElementById("crm-detail-deadline")?.value || null;
        const description = document.getElementById("crm-detail-desc")?.value?.trim() || null;
        const note = document.getElementById("crm-detail-note")?.value?.trim();
        try {
          const r = await authFetch(`${BASE}/leads/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stage, probability, deadline, description }),
          });
          if (!r.ok) {
            operationError("更新商機", await r.json().catch(() => ({})));
            return false;
          }
          if (note) {
            const nr = await authFetch(`${BASE}/leads/${id}/notes`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ note, by: this._currentUserEmail }),
            });
            if (!nr.ok) {
              operationError("新增跟進紀錄", await nr.json().catch(() => ({})));
              return false;
            }
          }
          toast.success("商機已更新");
          markTaskDone("tutorial-crm-followup");
          await this.load();
          return true;
        } catch (e) {
          networkError("更新商機", e);
          return false;
        }
      },
    });
  },
};

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function stageLabel(stage) {
  return STAGES.find(s => s.key === stage)?.label || stage || "未分類";
}

function sourceLabel(source) {
  if (source === "tender_alert") return "政府採購網";
  if (source === "referral") return "客戶轉介紹";
  if (source === "manual") return "手動建立";
  return source || "手動建立";
}

function formatMoney(value) {
  const n = Number(value || 0);
  if (!n) return "NT$ 0";
  if (Math.abs(n) >= 10000) return `NT$ ${(n / 10000).toFixed(1)} 萬`;
  return `NT$ ${n.toLocaleString()}`;
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const d = new Date(`${dateStr}T23:59:59`);
  if (Number.isNaN(d.getTime())) return null;
  return Math.ceil((d.getTime() - Date.now()) / 86400000);
}

function daysSince(value) {
  if (!value) return 0;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 0;
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

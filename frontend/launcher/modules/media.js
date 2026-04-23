/**
 * Media · Feature #6 · 媒體 CRM 前端
 * ==========================================================
 * View 結構:
 *   Header(統計 · 新增按鈕 · CSV import 按鈕 · 推薦按鈕)
 *   Filter(outlet / beat / search)
 *   Table(name / outlet / beats / accepted/pitched / 操作)
 *   Modal:
 *     - 新增 / 編輯 contact
 *     - CSV import(預覽 → 確認)
 *     - 推薦 modal(輸入 topic · 顯示 top 10)
 */
import { authFetch } from "./auth.js";
import { escapeHtml, skeletonCards } from "./util.js";
import { toast, networkError, operationError, permissionError } from "./toast.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting";

export const media = {
  _contacts: [],
  _filters: { search: "", outlet: "", beat: "" },
  _isAdmin: false,

  async init(isAdmin) {
    this._isAdmin = isAdmin;
    const root = document.getElementById("view-media-content");
    if (root) root.innerHTML = `<div class="skeleton-list">${skeletonCards(3)}</div>`;
    await this.load();
    this.render();
  },

  async load() {
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (this._filters.search) params.set("search", this._filters.search);
      if (this._filters.outlet) params.set("outlet", this._filters.outlet);
      if (this._filters.beat) params.set("beat", this._filters.beat);
      const r = await authFetch(`${BASE}/media/contacts?${params}`);
      if (!r.ok) throw new Error(r.status);
      const body = await r.json();
      this._contacts = body.items || [];
    } catch (e) {
      this._contacts = [];
      networkError("讀取媒體 CRM", e, () => this.init(this._isAdmin));
    }
  },

  render() {
    const root = document.getElementById("view-media-content");
    if (!root) return;

    const outlets = [...new Set(this._contacts.map(c => c.outlet).filter(Boolean))].sort();
    const allBeats = new Set();
    this._contacts.forEach(c => (c.beats || []).forEach(b => allBeats.add(b)));

    root.innerHTML = `
      <div class="media-toolbar">
        <div class="media-stats">
          <span class="media-stat-item">📇 <b>${this._contacts.length}</b> 位記者</span>
          <span class="media-stat-item">🏢 <b>${outlets.length}</b> 媒體</span>
          <span class="media-stat-item">🏷️ <b>${allBeats.size}</b> 主題</span>
        </div>
        <div class="media-actions">
          <button class="btn-secondary" id="media-recommend-btn">🎯 推薦記者</button>
          ${this._isAdmin ? `
            <button class="btn-secondary" id="media-import-btn">📥 CSV 匯入</button>
            <button class="btn-primary" id="media-new-btn">+ 新增記者</button>
          ` : ""}
        </div>
      </div>

      <div class="media-filters">
        <input type="text" id="media-search" placeholder="搜尋姓名/媒體/備註..." value="${escapeHtml(this._filters.search)}">
        <select id="media-outlet-filter">
          <option value="">所有媒體</option>
          ${outlets.map(o => `<option value="${escapeHtml(o)}" ${this._filters.outlet === o ? "selected" : ""}>${escapeHtml(o)}</option>`).join("")}
        </select>
        <select id="media-beat-filter">
          <option value="">所有主題</option>
          ${[...allBeats].sort().map(b => `<option value="${escapeHtml(b)}" ${this._filters.beat === b ? "selected" : ""}>${escapeHtml(b)}</option>`).join("")}
        </select>
      </div>

      <table class="media-table">
        <thead><tr>
          <th>姓名</th><th>媒體</th><th>負責主題</th><th>email</th>
          <th>發過 / 接受</th><th>操作</th>
        </tr></thead>
        <tbody>
          ${this._contacts.length === 0 ? `
            <tr><td colspan="6" class="media-empty">
              <div class="empty-state">
                <div class="empty-state-icon">📰</div>
                <div class="empty-state-title">尚無媒體記者</div>
                <div class="empty-state-hint">${this._isAdmin ? "點「+ 新增」或「CSV 匯入」開始" : "請 Champion 建檔"}</div>
              </div>
            </td></tr>
          ` : this._contacts.map(c => `
            <tr>
              <td><b>${escapeHtml(c.name || "")}</b></td>
              <td>${escapeHtml(c.outlet || "")}</td>
              <td>${(c.beats || []).map(b => `<span class="media-beat">${escapeHtml(b)}</span>`).join(" ")}</td>
              <td><a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a></td>
              <td><b>${c.pitched_count || 0}</b> / <b>${c.accepted_count || 0}</b>
                  ${c.pitched_count > 0 ? `<small>(${Math.round(c.accepted_count / c.pitched_count * 100)}%)</small>` : ""}
              </td>
              <td>
                ${this._isAdmin ? `
                  <button class="btn-tiny" data-edit="${c._id}">編輯</button>
                  <button class="btn-tiny btn-danger" data-del="${c._id}">停用</button>
                ` : ""}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    this._bindEvents();
  },

  _bindEvents() {
    const root = document.getElementById("view-media-content");
    if (!root) return;

    root.querySelector("#media-search")?.addEventListener("input", e => {
      this._filters.search = e.target.value;
      clearTimeout(this._searchTimer);
      this._searchTimer = setTimeout(() => this.load().then(() => this.render()), 300);
    });
    root.querySelector("#media-outlet-filter")?.addEventListener("change", e => {
      this._filters.outlet = e.target.value;
      this.load().then(() => this.render());
    });
    root.querySelector("#media-beat-filter")?.addEventListener("change", e => {
      this._filters.beat = e.target.value;
      this.load().then(() => this.render());
    });
    root.querySelector("#media-recommend-btn")?.addEventListener("click", () => this.openRecommendModal());
    root.querySelector("#media-import-btn")?.addEventListener("click", () => this.openImportModal());
    root.querySelector("#media-new-btn")?.addEventListener("click", () => this.openContactModal());
    root.querySelectorAll("[data-edit]").forEach(b => {
      b.addEventListener("click", () => {
        const c = this._contacts.find(x => x._id === b.dataset.edit);
        if (c) this.openContactModal(c);
      });
    });
    root.querySelectorAll("[data-del]").forEach(b => {
      b.addEventListener("click", () => this.deactivateContact(b.dataset.del));
    });
  },

  async openContactModal(existing = null) {
    const r = await modal.prompt(
      [
        { name: "name", label: "姓名", type: "text", value: existing?.name || "" },
        { name: "outlet", label: "媒體", type: "text", value: existing?.outlet || "" },
        { name: "beats", label: "負責主題(用 | 分隔)", type: "text", value: (existing?.beats || []).join("|") },
        { name: "email", label: "email", type: "email", value: existing?.email || "" },
        { name: "phone", label: "手機(選配 · 只 admin 看)", type: "text", value: existing?.phone || "" },
        { name: "notes", label: "備註", type: "textarea", value: existing?.notes || "", rows: 3 },
      ],
      { title: existing ? "編輯記者" : "新增記者", icon: "📇" },
    );
    if (!r) return;

    const payload = {
      name: r.name,
      outlet: r.outlet,
      beats: r.beats.split("|").map(b => b.trim()).filter(Boolean),
      email: r.email,
      phone: r.phone || null,
      notes: r.notes || null,
    };

    try {
      const url = existing ? `${BASE}/media/contacts/${existing._id}` : `${BASE}/media/contacts`;
      const method = existing ? "PUT" : "POST";
      const resp = await authFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        operationError("儲存記者", err);
        return;
      }
      toast.success(existing ? "已更新" : "已新增");
      await this.load();
      this.render();
    } catch (e) {
      networkError("儲存記者", e);
    }
  },

  async deactivateContact(id) {
    if (!confirm("確定停用此記者?(可日後復原 · 不真刪)")) return;
    try {
      const r = await authFetch(`${BASE}/media/contacts/${id}`, { method: "DELETE" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("停用記者", err);
        return;
      }
      toast.success("已停用");
      await this.load();
      this.render();
    } catch (e) {
      networkError("停用記者", e);
    }
  },

  async openRecommendModal() {
    const r = await modal.prompt(
      [
        { name: "topic", label: "新聞稿主題(用 | 分隔多個 tags)", type: "text",
          placeholder: "例:環保|減塑|政府" },
      ],
      { title: "🎯 記者推薦", icon: "🎯", submitText: "推薦" },
    );
    if (!r || !r.topic) return;

    const topics = r.topic.split("|").map(t => t.trim()).filter(Boolean);
    try {
      const resp = await authFetch(`${BASE}/media/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topics, limit: 10 }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        if (resp.status === 403) {
          permissionError("記者推薦");
        } else {
          operationError("記者推薦", err);
        }
        return;
      }
      const body = await resp.json();
      this._showRecommendResult(body, topics);
    } catch (e) {
      networkError("記者推薦", e);
    }
  },

  _showRecommendResult(body, topics) {
    const root = document.getElementById("modal-root") || document.body;
    const m = document.createElement("div");
    m.className = "modal2-overlay";
    m.innerHTML = `
      <div class="modal2-box" style="max-width:720px; max-height:80vh; overflow-y:auto">
        <div class="modal2-header">🎯 推薦結果 · ${topics.join(" + ")}</div>
        <p style="color:var(--text-tertiary); font-size:13px">
          從 ${body.total_candidates} 位 active 記者推 · ${body.recommended} 位匹配
        </p>
        ${body.items.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <div class="empty-state-title">找不到匹配記者</div>
            <div class="empty-state-hint">試試其他 topic · 例如「環保 / 政策 / AI」</div>
          </div>
        ` : `
          <table class="media-table">
            <thead><tr><th>#</th><th>姓名</th><th>媒體</th><th>分數</th><th>理由</th></tr></thead>
            <tbody>
              ${body.items.map((c, i) => `
                <tr>
                  <td>${i + 1}</td>
                  <td><b>${escapeHtml(c.name)}</b><br><small>${escapeHtml(c.email)}</small></td>
                  <td>${escapeHtml(c.outlet)}</td>
                  <td><b>${c.score}</b></td>
                  <td><small>
                    匹配:${(c.reason.matched_topics || []).join("/")} · jaccard=${c.reason.jaccard}<br>
                    接受率 ${c.accepted_count}/${c.pitched_count} · recency=${c.reason.recency_weight}
                  </small></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `}
        <div class="modal2-actions">
          <button type="button" data-close>關閉</button>
        </div>
      </div>
    `;
    root.appendChild(m);
    m.querySelector("[data-close]").addEventListener("click", () => m.remove());
  },

  async openImportModal() {
    const root = document.getElementById("modal-root") || document.body;
    const m = document.createElement("div");
    m.className = "modal2-overlay";
    m.innerHTML = `
      <div class="modal2-box" style="max-width:480px">
        <div class="modal2-header">📥 CSV 匯入</div>
        <form id="csv-form" class="modal2-form">
          <p style="font-size:13px; color:var(--text-secondary)">
            必含欄位:<code>name, outlet, email</code><br>
            選填:<code>beats(用 | 分隔)、phone, notes</code><br>
            重複 email 自動 update(不覆寫 pitched_count)
          </p>
          <input type="file" name="file" accept=".csv,text/csv" required>
          <div class="modal2-actions">
            <button type="button" data-cancel>取消</button>
            <button type="submit" class="primary">上傳</button>
          </div>
        </form>
      </div>
    `;
    root.appendChild(m);
    m.querySelector("[data-cancel]").addEventListener("click", () => m.remove());
    m.querySelector("form").addEventListener("submit", async e => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        const r = await authFetch(`${BASE}/media/contacts/import-csv`, {
          method: "POST",
          body: fd,
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          operationError("CSV 匯入", err);
          return;
        }
        const body = await r.json();
        toast.success(`匯入 ${body.imported} 筆 · 更新 ${body.updated} 筆 · 錯 ${body.errors.length} 筆`);
        m.remove();
        await this.load();
        this.render();
      } catch (e) {
        networkError("CSV 匯入", e);
      }
    });
  },
};

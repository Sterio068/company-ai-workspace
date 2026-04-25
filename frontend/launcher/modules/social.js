/**
 * Social · Feature #5 · 社群排程前端
 * ==========================================================
 * View 結構:
 *   Header(統計 · 新建按鈕 · platform filter)
 *   List(排程中 / 已發 / 失敗 · 各分區)
 *   Modal:
 *     - 新建排程(platform / content / schedule_at / image_url)
 *     - 編輯(僅 queued)
 *     - 立刻發按鈕
 */
import { authFetch } from "./auth.js";
import { escapeHtml, formatDate, skeletonCards } from "./util.js";
import { toast, networkError, operationError } from "./toast.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting";

const PLATFORM_META = {
  facebook:  { icon: "📘", color: "#1877F2", name: "Facebook" },
  instagram: { icon: "📷", color: "#E4405F", name: "Instagram" },
  linkedin:  { icon: "💼", color: "#0A66C2", name: "LinkedIn" },
};

const STATUS_META = {
  queued:    { icon: "⏰", label: "排程中", color: "var(--text-secondary)" },
  publishing:{ icon: "🚀", label: "發送中", color: "var(--blue)" },
  published: { icon: "✅", label: "已發出", color: "#22c55e" },
  failed:    { icon: "❌", label: "失敗",   color: "#ef4444" },
  cancelled: { icon: "🚫", label: "取消",   color: "var(--text-tertiary)" },
};

export const social = {
  _posts: [],
  _filter: { platform: "", status: "" },

  async init() {
    const root = document.getElementById("view-social-content");
    if (root) root.innerHTML = `<div class="skeleton-list">${skeletonCards(3)}</div>`;
    await this.load();
    this.render();
  },

  async load() {
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (this._filter.platform) params.set("platform", this._filter.platform);
      if (this._filter.status) params.set("status", this._filter.status);
      const r = await authFetch(`${BASE}/social/posts?${params}`);
      if (!r.ok) throw new Error(r.status);
      const body = await r.json();
      this._posts = body.items || [];
    } catch (e) {
      this._posts = [];
      networkError("讀取社群排程", e, () => this.init());
    }
  },

  render() {
    const root = document.getElementById("view-social-content");
    if (!root) return;

    const queued = this._posts.filter(p => p.status === "queued");
    const published = this._posts.filter(p => p.status === "published");
    const failed = this._posts.filter(p => p.status === "failed");

    root.innerHTML = `
      <div class="social-toolbar">
        <div class="social-stats">
          <span class="social-stat-item">⏰ <b>${queued.length}</b> 排程中</span>
          <span class="social-stat-item">✅ <b>${published.length}</b> 已發出</span>
          <span class="social-stat-item">❌ <b>${failed.length}</b> 失敗</span>
        </div>
        <div class="social-actions">
          <select id="social-platform-filter">
            <option value="">所有平台</option>
            <option value="facebook" ${this._filter.platform === "facebook" ? "selected" : ""}>Facebook</option>
            <option value="instagram" ${this._filter.platform === "instagram" ? "selected" : ""}>Instagram</option>
            <option value="linkedin" ${this._filter.platform === "linkedin" ? "selected" : ""}>LinkedIn</option>
          </select>
          <button class="btn-primary" id="social-new-btn">+ 新排程</button>
        </div>
      </div>

      ${this._posts.length === 0 ? `
        <div class="empty-state">
          <div class="empty-state-icon">📣</div>
          <div class="empty-state-title">尚無社群排程</div>
          <div class="empty-state-hint">點「+ 新排程」發一篇臉書 / Instagram / 領英貼文</div>
        </div>
      ` : `
        ${this._renderSection("⏰ 排程中", queued, true)}
        ${this._renderSection("✅ 已發出", published, false)}
        ${this._renderSection("❌ 失敗", failed, true)}
      `}
    `;

    this._bindEvents();
  },

  _renderSection(title, posts, allowActions) {
    if (!posts.length) return "";
    return `
      <h3 class="social-section-title">${title}</h3>
      <div class="social-grid">
        ${posts.map(p => this._renderCard(p, allowActions)).join("")}
      </div>
    `;
  },

  _renderCard(p, allowActions) {
    const pm = PLATFORM_META[p.platform] || {};
    const sm = STATUS_META[p.status] || {};
    return `
      <div class="social-card" style="border-left:3px solid ${pm.color}">
        <div class="social-card-head">
          <span class="social-platform">${pm.icon} ${pm.name}</span>
          <span class="social-status" style="color:${sm.color}">${sm.icon} ${sm.label}</span>
        </div>
        <div class="social-card-body">
          <div class="social-content">${escapeHtml((p.content || "").substring(0, 200))}${p.content?.length > 200 ? "…" : ""}</div>
          <div class="social-meta">
            <span>📅 ${this._formatTime(p.schedule_at)}</span>
            ${p.attempts > 0 ? `<span>🔁 ${p.attempts} 次</span>` : ""}
            ${p.last_error ? `<span class="social-error" title="${escapeHtml(p.last_error)}">⚠️ 有錯</span>` : ""}
            ${p.platform_url && /^https?:\/\//.test(p.platform_url) ? `<a href="${escapeHtml(p.platform_url)}" target="_blank" rel="noopener noreferrer">查看</a>` : ""}
          </div>
        </div>
        ${allowActions ? `
          <div class="social-card-actions">
            ${p.status === "queued" ? `<button class="btn-tiny" data-edit="${p._id}">編輯</button>` : ""}
            <button class="btn-tiny" data-now="${p._id}">立即發</button>
            <button class="btn-tiny btn-danger" data-cancel="${p._id}">取消</button>
          </div>
        ` : ""}
      </div>
    `;
  },

  _formatTime(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = (d - now) / 1000;
      if (Math.abs(diff) < 3600) return `${Math.round(diff / 60)} 分後`;
      if (diff > 0 && diff < 86400) return `${Math.round(diff / 3600)} 小時後`;
      return d.toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
  },

  _bindEvents() {
    const root = document.getElementById("view-social-content");
    if (!root) return;
    root.querySelector("#social-platform-filter")?.addEventListener("change", e => {
      this._filter.platform = e.target.value;
      this.load().then(() => this.render());
    });
    root.querySelector("#social-new-btn")?.addEventListener("click", () => this.openNewModal());
    root.querySelectorAll("[data-edit]").forEach(b =>
      b.addEventListener("click", () => {
        const p = this._posts.find(x => x._id === b.dataset.edit);
        if (p) this.openNewModal(p);
      }));
    root.querySelectorAll("[data-now]").forEach(b =>
      b.addEventListener("click", () => this.publishNow(b.dataset.now)));
    root.querySelectorAll("[data-cancel]").forEach(b =>
      b.addEventListener("click", () => this.cancelPost(b.dataset.cancel)));
  },

  async openNewModal(existing = null) {
    // R24#1 修 · datetime-local 必須 LOCAL formatter · toISOString 會把本地轉 UTC 偏 8 小時
    const localIso = (d) => {
      // YYYY-MM-DDTHH:mm · 本地時區 · 不轉 UTC
      const pad = n => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };
    const defaultTime = new Date(Date.now() + 3600 * 1000);
    const defaultIso = localIso(defaultTime);
    const r = await modal.prompt(
      [
        { name: "platform", label: "平台", type: "select",
          options: ["facebook", "instagram", "linkedin"],
          value: existing?.platform || "facebook" },
        { name: "content", label: "貼文內容(< 3000 字)", type: "textarea",
          value: existing?.content || "", rows: 6 },
        { name: "image_url", label: "圖片連結(Instagram 必填)", type: "text",
          value: existing?.image_url || "" },
        { name: "schedule_at", label: "排定時間(本地時區)", type: "datetime-local",
          value: existing ? localIso(new Date(existing.schedule_at)) : defaultIso },
      ],
      { title: existing ? "編輯排程" : "+ 新排程", icon: "📅", submitText: "排程" },
    );
    if (!r) return;

    // datetime-local 是本地 naive · 後端 _to_utc 會視為 Asia/Taipei
    // 補 :00 秒給 ISO 完整格式
    const payload = {
      platform: r.platform,
      content: r.content,
      schedule_at: r.schedule_at + ":00",
      image_url: r.image_url || null,
    };

    try {
      const url = existing ? `${BASE}/social/posts/${existing._id}` : `${BASE}/social/posts`;
      const method = existing ? "PUT" : "POST";
      const resp = await authFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        operationError("儲存社群排程", err);
        return;
      }
      toast.success(existing ? "已更新" : "已排程");
      await this.load();
      this.render();
    } catch (e) {
      networkError("儲存社群排程", e);
    }
  },

  async publishNow(id) {
    // v1.3 batch6 · 取代 window.confirm · 一致 UX + Electron 安全
    if (!await modal.confirm("立刻發此貼文?(繞過排程)", { title: "立即發出", icon: "🚀", primary: "立刻發" })) return;
    try {
      const r = await authFetch(`${BASE}/social/posts/${id}/publish-now`, { method: "POST" });
      const body = await r.json();
      if (body.published) {
        toast.success("發送成功", { detail: body.url || "" });
      } else {
        toast.error("社群發送失敗", { detail: body.error || "未知錯誤" });
      }
      await this.load();
      this.render();
    } catch (e) {
      networkError("發送社群貼文", e);
    }
  },

  async cancelPost(id) {
    if (!await modal.confirm("取消此排程?", { title: "取消排程", icon: "🚫", primary: "確定取消", danger: true })) return;
    try {
      const r = await authFetch(`${BASE}/social/posts/${id}`, { method: "DELETE" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("取消排程", err);
        return;
      }
      toast.success("已取消");
      await this.load();
      this.render();
    } catch (e) {
      networkError("取消排程", e);
    }
  },
};

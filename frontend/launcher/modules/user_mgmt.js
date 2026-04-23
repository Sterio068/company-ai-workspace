/**
 * User Management · admin 在 UI 建同仁帳號
 * ==========================================================
 * v1.3 · 老闆不用 shell · launcher 點一點建人 + 改頭銜 + 勾權限
 *
 * View 結構:
 *   Header(統計 · 新建按鈕)
 *   Table(email / name / title / role / permissions count / active / 操作)
 *   Modal:
 *     - 新建 / 編輯 user
 *     - 頂部:email + name + 密碼(隨機產 / 手輸)+ 顯示名稱
 *     - 中間:頭銜 input(自訂 · 預設 7 個 preset 快捷)
 *     - 下方:28 個 permissions 勾選樹(8 組)
 *     - 右上「套 preset」下拉 · 7 個預設模板(老闆 / 企劃 / 設計 / 公關 / 會計 / 業務 / 新人)
 *
 * Backend:
 *   GET  /admin/users/permission-catalog
 *   GET  /admin/users
 *   POST /admin/users
 *   PATCH /admin/users/:email
 *   DELETE /admin/users/:email
 */
import { authFetch } from "./auth.js";
import { escapeHtml, skeletonCards } from "./util.js";
import { toast, networkError, operationError } from "./toast.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting";

export const userMgmt = {
  _users: [],
  _catalog: null,  // lazy load
  _presets: null,

  async init() {
    const root = document.getElementById("view-users-content");
    if (root) root.innerHTML = `<div class="skeleton-list">${skeletonCards(3)}</div>`;
    await this._loadCatalog();
    await this.load();
    this.render();
  },

  async _loadCatalog() {
    if (this._catalog) return;
    try {
      const r = await authFetch(`${BASE}/admin/users/permission-catalog`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      this._catalog = body.catalog;
      this._presets = body.presets;
    } catch (e) {
      networkError("讀取權限 catalog", e, () => this._loadCatalog());
    }
  },

  async load() {
    try {
      const r = await authFetch(`${BASE}/admin/users`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      this._users = body.items || [];
    } catch (e) {
      this._users = [];
      networkError("讀取同仁列表", e, () => this.load());
    }
  },

  render() {
    const root = document.getElementById("view-users-content");
    if (!root) return;

    const activeCount = this._users.filter(u => u.active).length;
    const adminCount = this._users.filter(u => u.role === "ADMIN").length;

    root.innerHTML = `
      <div class="users-toolbar">
        <div class="users-stats">
          <span class="users-stat-item">👥 <b>${activeCount}</b> 活躍</span>
          <span class="users-stat-item">🔴 <b>${adminCount}</b> admin</span>
          <span class="users-stat-item">💤 <b>${this._users.length - activeCount}</b> 停用</span>
        </div>
        <div class="users-actions">
          <button class="btn-primary" id="users-new-btn">+ 建新同仁</button>
        </div>
      </div>

      ${this._users.length === 0 ? `
        <div class="empty-state">
          <div class="empty-state-icon">👥</div>
          <div class="empty-state-title">尚無同仁帳號</div>
          <div class="empty-state-hint">點右上「+ 建新同仁」建第一個</div>
        </div>
      ` : `
        <table class="users-table" role="grid">
          <thead>
            <tr>
              <th>Email</th>
              <th>姓名</th>
              <th>頭銜</th>
              <th>角色</th>
              <th>權限</th>
              <th>狀態</th>
              <th>建立</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${this._users.map(u => `
              <tr class="${u.active ? "" : "users-row-inactive"}">
                <td><code>${escapeHtml(u.email)}</code></td>
                <td><b>${escapeHtml(u.name)}</b></td>
                <td>${u.title ? `<span class="users-title-badge">${escapeHtml(u.title)}</span>` : "—"}</td>
                <td>
                  ${u.role === "ADMIN"
                    ? `<span class="users-role-badge users-role-admin">🔴 ADMIN</span>`
                    : `<span class="users-role-badge users-role-user">🟡 USER</span>`}
                </td>
                <td><span title="${escapeHtml(u.permissions.join(", "))}"><b>${u.permissions.length}</b> 項</span></td>
                <td>${u.active ? "✅" : "💤 停用"}</td>
                <td><small>${this._formatTime(u.created_at)}</small></td>
                <td>
                  <button class="btn-tiny" data-edit="${escapeHtml(u.email)}">編輯</button>
                  ${u.active
                    ? `<button class="btn-tiny btn-danger" data-deactivate="${escapeHtml(u.email)}">停用</button>`
                    : `<button class="btn-tiny" data-reactivate="${escapeHtml(u.email)}">復用</button>`}
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `}
    `;
    this._bindEvents();
  },

  _formatTime(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("zh-TW", {
        year: "numeric", month: "numeric", day: "numeric",
      });
    } catch { return iso; }
  },

  _bindEvents() {
    const root = document.getElementById("view-users-content");
    if (!root) return;
    root.querySelector("#users-new-btn")?.addEventListener("click", () => this.openModal());
    root.querySelectorAll("[data-edit]").forEach(el => {
      el.addEventListener("click", () => {
        const u = this._users.find(x => x.email === el.dataset.edit);
        if (u) this.openModal(u);
      });
    });
    root.querySelectorAll("[data-deactivate]").forEach(el => {
      el.addEventListener("click", () => this.deactivate(el.dataset.deactivate));
    });
    root.querySelectorAll("[data-reactivate]").forEach(el => {
      el.addEventListener("click", () => this.reactivate(el.dataset.reactivate));
    });
  },

  _generatePassword(len = 14) {
    // 人類可讀 + 強度夠 · 排掉 o/0/l/1 等混淆
    const charset = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789!@#$%";
    let pw = "";
    const arr = new Uint32Array(len);
    crypto.getRandomValues(arr);
    for (let i = 0; i < len; i++) pw += charset[arr[i] % charset.length];
    return pw;
  },

  openModal(existing = null) {
    const isEdit = !!existing;
    const root = document.getElementById("modal-root") || document.body;
    const m = document.createElement("div");
    m.className = "modal2-overlay";
    m.setAttribute("role", "dialog");
    m.setAttribute("aria-modal", "true");
    m.setAttribute("aria-labelledby", "um-title");

    const initialPerms = existing?.permissions || [];
    const initialTitle = existing?.title || "";

    m.innerHTML = `
      <div class="modal2-box" style="max-width:720px; max-height:90vh; overflow-y:auto">
        <div class="modal2-header" id="um-title">${isEdit ? "✏️ 編輯同仁" : "➕ 建新同仁"}</div>

        <div class="um-section">
          <h4>基本資料</h4>
          <div class="um-grid-2">
            <label>Email <em style="color:var(--red)" aria-hidden="true">*</em>
              <input type="email" id="um-email" required value="${escapeHtml(existing?.email || "")}"
                     placeholder="alice@chengfu.com"
                     ${isEdit ? "disabled title='建後不能改 email · 要改請刪了重建'" : ""}>
            </label>
            <label>顯示名稱 <em style="color:var(--red)" aria-hidden="true">*</em>
              <input type="text" id="um-name" required value="${escapeHtml(existing?.name || "")}"
                     placeholder="王小明">
            </label>
          </div>

          ${!isEdit ? `
            <label>初始密碼 <em style="color:var(--red)" aria-hidden="true">*</em>(≥ 8 字 · 建完分給同仁 · 她/他登入後可自己改)
              <div class="um-pwd-row">
                <input type="text" id="um-password" required minlength="8" value=""
                       placeholder="至少 8 字">
                <button type="button" class="btn-secondary" id="um-gen-pwd">🎲 隨機產</button>
              </div>
            </label>
          ` : `
            <p style="color:var(--text-secondary);font-size:12px">
              💡 密碼不能在這邊改 · 請同仁自己登入後走 LibreChat reset 流程
            </p>
          `}
        </div>

        <div class="um-section">
          <h4>頭銜 + 角色</h4>
          <div class="um-grid-2">
            <label>頭銜(自訂 · 可留空)
              <input type="text" id="um-title" value="${escapeHtml(initialTitle)}"
                     placeholder="例:會計 / 企劃 / 設計"
                     list="um-title-suggest">
              <datalist id="um-title-suggest">
                ${Object.keys(this._presets || {}).map(t => `<option value="${escapeHtml(t)}">`).join("")}
              </datalist>
            </label>
            <label>角色
              <select id="um-role">
                <option value="USER" ${existing?.role !== "ADMIN" ? "selected" : ""}>🟡 USER(一般同仁)</option>
                <option value="ADMIN" ${existing?.role === "ADMIN" ? "selected" : ""}>🔴 ADMIN(全權)</option>
              </select>
            </label>
          </div>
        </div>

        <div class="um-section">
          <h4>
            權限
            <select id="um-preset" style="float:right;font-size:12px">
              <option value="">套 preset 模板 ↓</option>
              ${Object.keys(this._presets || {}).map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("")}
            </select>
          </h4>
          <div id="um-perms-tree">
            ${(this._catalog || []).map(group => `
              <details open class="um-perm-group">
                <summary>${escapeHtml(group.group)}</summary>
                <div class="um-perm-items">
                  ${group.items.map(item => `
                    <label class="um-perm-item">
                      <input type="checkbox" name="permission" value="${escapeHtml(item.key)}"
                             ${initialPerms.includes(item.key) ? "checked" : ""}>
                      <span>${escapeHtml(item.label)}</span>
                      <code>${escapeHtml(item.key)}</code>
                    </label>
                  `).join("")}
                </div>
              </details>
            `).join("")}
          </div>
          <p style="font-size:11px;color:var(--text-tertiary);margin-top:8px">
            💡 ADMIN 角色自動有全部權限 · 這邊勾選只對 USER 生效。Backend 強制 enforcement 逐步展開中(v1.3 先 admin.* 擋)
          </p>
        </div>

        <div class="modal2-actions">
          <button type="button" data-cancel>取消</button>
          <button type="button" class="primary" id="um-save">${isEdit ? "儲存" : "建立"}</button>
        </div>
      </div>
    `;
    root.appendChild(m);

    // 綁事件
    m.querySelector("[data-cancel]").addEventListener("click", () => m.remove());

    if (!isEdit) {
      m.querySelector("#um-gen-pwd")?.addEventListener("click", () => {
        m.querySelector("#um-password").value = this._generatePassword();
      });
    }

    // preset 下拉 · 套權限
    m.querySelector("#um-preset")?.addEventListener("change", e => {
      const key = e.target.value;
      if (!key || !this._presets?.[key]) return;
      const perms = this._presets[key];
      m.querySelectorAll('input[name="permission"]').forEach(cb => {
        cb.checked = perms.includes(cb.value);
      });
      // 順便填 title(若空)
      const titleInput = m.querySelector("#um-title");
      if (titleInput && !titleInput.value) titleInput.value = key.split(" / ")[0];
    });

    m.querySelector("#um-save")?.addEventListener("click", () => this._save(m, existing));

    // ESC 關
    const escHandler = e => { if (e.key === "Escape") { m.remove(); document.removeEventListener("keydown", escHandler); } };
    document.addEventListener("keydown", escHandler);

    // 自動 focus 第一個可用 input
    setTimeout(() => m.querySelector(isEdit ? "#um-name" : "#um-email")?.focus(), 50);
  },

  async _save(m, existing) {
    const email = m.querySelector("#um-email").value.trim().toLowerCase();
    const name = m.querySelector("#um-name").value.trim();
    const title = m.querySelector("#um-title").value.trim();
    const role = m.querySelector("#um-role").value;
    const permissions = Array.from(m.querySelectorAll('input[name="permission"]:checked')).map(cb => cb.value);

    if (!email || !name) {
      toast.warn("Email 與姓名必填");
      return;
    }

    const saveBtn = m.querySelector("#um-save");
    saveBtn.disabled = true;
    saveBtn.textContent = "⏳ 儲存中...";

    if (!existing) {
      // 新建 · 要密碼
      const password = m.querySelector("#um-password").value;
      if (password.length < 8) {
        toast.warn("密碼至少 8 字");
        saveBtn.disabled = false;
        saveBtn.textContent = "建立";
        return;
      }
      try {
        const r = await authFetch(`${BASE}/admin/users`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, name, password, title, permissions, role }),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          operationError("建立同仁", err);
          saveBtn.disabled = false;
          saveBtn.textContent = "建立";
          return;
        }
        // 成功 · 顯示密碼給 admin 複製
        m.remove();
        await this._showCreatedCredentials(email, password);
        await this.load();
        this.render();
      } catch (e) {
        networkError("建立同仁", e);
        saveBtn.disabled = false;
        saveBtn.textContent = "建立";
      }
    } else {
      // 編輯
      try {
        const r = await authFetch(`${BASE}/admin/users/${encodeURIComponent(existing.email)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, title, permissions, role }),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          operationError("更新同仁", err);
          saveBtn.disabled = false;
          saveBtn.textContent = "儲存";
          return;
        }
        toast.success("已更新");
        m.remove();
        await this.load();
        this.render();
      } catch (e) {
        networkError("更新同仁", e);
        saveBtn.disabled = false;
        saveBtn.textContent = "儲存";
      }
    }
  },

  async _showCreatedCredentials(email, password) {
    return modal.alert(
      `<div style="font-family:var(--font-mono);padding:12px;background:var(--surface-2);border-radius:8px;margin:8px 0">
        <div><b>Email:</b> ${escapeHtml(email)}</div>
        <div><b>密碼:</b> <span id="um-cred-pwd">${escapeHtml(password)}</span>
             <button onclick="navigator.clipboard.writeText('${password.replace(/'/g, "\\'")}')"
                     style="margin-left:8px;font-size:12px">📋 複製</button></div>
      </div>
      <p style="color:var(--red);font-weight:600">⚠ 這組密碼只顯示一次 · 請立刻複製分給同仁</p>
      <p style="color:var(--text-secondary);font-size:13px">
        同仁首次登入後可以自己改密碼。若忘了只能你這邊刪了重建。
      </p>`,
      { title: "✅ 同仁帳號已建立", icon: "🔐", primary: "我已複製密碼" }
    );
  },

  async deactivate(email) {
    const ok = await modal.confirm(
      `確定停用 <code>${escapeHtml(email)}</code>?<br><br>
       停用後該同仁無法登入 · 但資料保留(歷史對話 / 專案 / 場勘)<br>
       若要徹底清資料(離職)· 要走 PDPA 流程`,
      { title: "停用同仁", icon: "💤", primary: "停用", danger: true }
    );
    if (!ok) return;

    try {
      const r = await authFetch(`${BASE}/admin/users/${encodeURIComponent(email)}`, { method: "DELETE" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("停用同仁", err);
        return;
      }
      toast.success(`已停用 ${email}`);
      await this.load();
      this.render();
    } catch (e) {
      networkError("停用同仁", e);
    }
  },

  async reactivate(email) {
    try {
      const r = await authFetch(`${BASE}/admin/users/${encodeURIComponent(email)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: true }),
      });
      if (!r.ok) {
        operationError("復用同仁", await r.json().catch(() => ({})));
        return;
      }
      toast.success(`已復用 ${email}`);
      await this.load();
      this.render();
    } catch (e) {
      networkError("復用同仁", e);
    }
  },
};

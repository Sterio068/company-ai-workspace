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
import { escapeHtml, skeletonCards, copyToClipboard } from "./util.js";
import { toast, networkError, operationError } from "./toast.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting";

export const userMgmt = {
  _users: [],
  _catalog: null,  // lazy load
  _presets: null,
  _enforcement: null,

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
      this._enforcement = body.enforcement || null;
    } catch (e) {
      networkError("讀取權限目錄", e, () => this._loadCatalog());
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
          <span class="users-stat-item">🔴 <b>${adminCount}</b> 管理員</span>
          <span class="users-stat-item">💤 <b>${this._users.length - activeCount}</b> 停用</span>
        </div>
        <div class="users-actions">
          <button class="btn-primary" id="users-new-btn">+ 建新同仁</button>
        </div>
      </div>

      ${this._renderEnforcementNotice()}

      ${this._users.length === 0 ? `
        <div class="empty-state">
          <div class="empty-state-icon">👥</div>
          <div class="empty-state-title">尚無同仁帳號</div>
          <div class="empty-state-hint">點右上「+ 建新同仁」建第一個</div>
        </div>
      ` : `
        <table class="users-table">
          <thead>
            <tr>
              <th>電子郵件</th>
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
                    ? `<span class="users-role-badge users-role-admin">🔴 管理員</span>`
                    : `<span class="users-role-badge users-role-user">🟡 一般同仁</span>`}
                </td>
                <td><span title="${escapeHtml(u.permissions.join(", "))}"><b>${u.permissions.length}</b> 項</span></td>
                <td>${u.active ? "✅" : "💤 停用"}</td>
                <td><small>${this._formatTime(u.created_at)}</small></td>
                <td>
                  <button class="btn-tiny" data-edit="${escapeHtml(u.email)}">編輯</button>
                  ${u.active
                    ? `<button class="btn-tiny btn-danger" data-deactivate="${escapeHtml(u.email)}">停用</button>`
                    : `<button class="btn-tiny" data-reactivate="${escapeHtml(u.email)}">復用</button>
                       <button class="btn-tiny btn-danger" data-delete-permanent="${escapeHtml(u.email)}"
                               data-name="${escapeHtml(u.name || "")}" title="永久刪除(無法復原)">🗑 刪除</button>`}
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `}
    `;
    this._bindEvents();
  },

  _renderEnforcementNotice() {
    const enf = this._enforcement;
    if (!enf) return "";
    const count = (enf.enforced_permissions || []).length;
    const summary = String(enf.summary || "逐步啟用")
      .replace(/\bADMIN\b/g, "管理員角色")
      .replace(/\bchengfu_permissions\b/g, "權限設定");
    return `
      <div class="v10-notice" style="margin:12px 0">
        權限狀態:${escapeHtml(summary)}
        <br><small>目前後端強制 ${count} 項高風險權限；其餘勾選先作為職務配置與後續啟用依據。</small>
      </div>
    `;
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
    root.querySelectorAll("[data-delete-permanent]").forEach(el => {
      el.addEventListener("click", () => this.deletePermanent(el.dataset.deletePermanent, el.dataset.name));
    });
  },

  _generatePassword(len = 16) {
    // 人類可讀 + 強度夠 · 排 o/0/l/1 混淆字元
    // 4 類字元各保證至少 1 個 · 確保通過後端複雜度檢查(大寫 + 小寫 + 數字 + 符號)
    const lower = "abcdefghjkmnpqrstuvwxyz";
    const upper = "ABCDEFGHJKMNPQRSTUVWXYZ";
    const digit = "23456789";
    const symbol = "!@#$%";
    const all = lower + upper + digit + symbol;
    const pickFrom = pool => {
      const arr = new Uint32Array(1);
      crypto.getRandomValues(arr);
      return pool[arr[0] % pool.length];
    };
    // 強制 4 類各 1 + 剩餘 random
    const required = [pickFrom(lower), pickFrom(upper), pickFrom(digit), pickFrom(symbol)];
    const remaining = Math.max(0, len - required.length);
    const rest = Array.from({ length: remaining }, () => pickFrom(all));
    const pwArr = required.concat(rest);
    // Fisher-Yates 洗牌(防 4 類字元固定在前 4 位)
    for (let i = pwArr.length - 1; i > 0; i--) {
      const j = new Uint32Array(1);
      crypto.getRandomValues(j);
      const k = j[0] % (i + 1);
      [pwArr[i], pwArr[k]] = [pwArr[k], pwArr[i]];
    }
    return pwArr.join("");
  },

  openModal(existing = null) {
    const isEdit = !!existing;
    const root = document.getElementById("modal-root") || document.body;
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const m = document.createElement("div");
    m.className = "modal2-overlay";
    m.setAttribute("role", "dialog");
    m.setAttribute("aria-modal", "true");
    m.setAttribute("aria-labelledby", "um-dialog-title");

    const initialPerms = existing?.permissions || [];
    const initialTitle = existing?.title || "";

    m.innerHTML = `
      <div class="modal2-box" style="max-width:720px; max-height:90vh; overflow-y:auto">
        <div class="modal2-header" id="um-dialog-title">${isEdit ? "✏️ 編輯同仁" : "➕ 建新同仁"}</div>

        <div class="um-section">
          <h4>基本資料</h4>
          <div class="um-grid-2">
            <label>電子郵件 <em style="color:var(--red)" aria-hidden="true">*</em>
              <input type="email" id="um-email" required value="${escapeHtml(existing?.email || "")}"
                     placeholder="輸入公司電子郵件"
                     ${isEdit ? "disabled title='建後不能改電子郵件 · 要改請刪了重建'" : ""}>
            </label>
            <label>顯示名稱 <em style="color:var(--red)" aria-hidden="true">*</em>
              <input type="text" id="um-name" required value="${escapeHtml(existing?.name || "")}"
                     placeholder="王小明">
            </label>
          </div>

          ${!isEdit ? `
            <label>初始密碼 <em style="color:var(--red)" aria-hidden="true">*</em>(≥ 10 字 · 含 3 類:大寫 / 小寫 / 數字 / 符號 · 建完分給同仁)
              <div class="um-pwd-row">
                <input type="text" id="um-password" required minlength="10" value=""
                       placeholder="至少 10 字 · 建議按 🎲 隨機產">
                <button type="button" class="btn-secondary" id="um-gen-pwd">🎲 隨機產</button>
              </div>
            </label>
          ` : `
            <div class="um-reset-row">
              <p style="color:var(--text-secondary);font-size:12px;margin:0">
                🔑 密碼:同仁忘記了 / 老闆要硬覆蓋 → 點下方按鈕重設
              </p>
              <button type="button" class="btn-secondary" id="um-reset-pwd"
                      data-target-email="${escapeHtml(existing?.email || "")}">
                🔑 重設密碼
              </button>
            </div>
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
                <option value="USER" ${existing?.role !== "ADMIN" ? "selected" : ""}>🟡 一般同仁</option>
                <option value="ADMIN" ${existing?.role === "ADMIN" ? "selected" : ""}>🔴 管理員(全權)</option>
              </select>
            </label>
          </div>
        </div>

        <div class="um-section">
          <h4>
            權限
            <select id="um-preset" style="float:right;font-size:12px">
              <option value="">套用預設模板 ↓</option>
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
            💡 管理員角色自動有全部權限 · 這邊勾選只對一般同仁生效。伺服器端強制權限會逐步展開(v1.3 先擋管理高風險操作)
          </p>
        </div>

        <div class="modal2-actions">
          <button type="button" data-cancel>取消</button>
          <button type="button" class="primary" id="um-save">${isEdit ? "儲存" : "建立"}</button>
        </div>
      </div>
    `;
    root.appendChild(m);
    const close = ({ restoreFocus = true } = {}) => {
      document.removeEventListener("keydown", onKey);
      m.remove();
      if (restoreFocus) requestAnimationFrame(() => returnFocus?.focus?.());
    };
    const onKey = _modalKeyHandler(m, () => close());
    m.__close = close;
    document.addEventListener("keydown", onKey);

    // 綁事件
    m.querySelector("[data-cancel]").addEventListener("click", () => close());

    if (!isEdit) {
      m.querySelector("#um-gen-pwd")?.addEventListener("click", () => {
        m.querySelector("#um-password").value = this._generatePassword();
      });
    } else {
      m.querySelector("#um-reset-pwd")?.addEventListener("click", () => {
        // 關掉編輯 modal · 避免兩層 modal 疊住難看
        close({ restoreFocus: false });
        this.openResetPasswordModal(existing);
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
      toast.warn("電子郵件與姓名必填");
      return;
    }

    const saveBtn = m.querySelector("#um-save");
    saveBtn.disabled = true;
    saveBtn.textContent = "⏳ 儲存中...";

    if (!existing) {
      // 新建 · 要密碼
      const password = m.querySelector("#um-password").value;
      if (password.length < 10) {
        toast.warn("密碼至少 10 字 · 含 3 類字元");
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
        m.__close?.({ restoreFocus: false }) || m.remove();
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
        m.__close?.() || m.remove();
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
    return _showPasswordOnce({
      title: "✅ 同仁帳號已建立",
      email,
      password,
      extraNote: "同仁首次登入後可以自己改密碼。若忘了,管理員可在同仁管理中重設密碼。",
    });
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

  openResetPasswordModal(target) {
    const root = document.getElementById("modal-root") || document.body;
    const m = document.createElement("div");
    m.className = "modal2-overlay";
    m.setAttribute("role", "dialog");
    m.setAttribute("aria-modal", "true");
    m.setAttribute("aria-labelledby", "um-reset-title");
    m.setAttribute("aria-describedby", "um-reset-desc um-reset-warn");
    // 預設密碼類型 password · 加「顯示」toggle 防螢幕讀取器朗讀
    m.innerHTML = `
      <div class="modal2-box" style="max-width:480px">
        <div class="modal2-header" id="um-reset-title">🔑 重設 ${escapeHtml(target.name || target.email)} 的密碼</div>
        <div class="um-section">
          <p id="um-reset-desc" style="color:var(--text-secondary);font-size:13px;margin:0 0 12px">
            打新密碼或按「隨機產」自動產 · 同仁登入後可自己再改
          </p>
          <label for="um-new-pwd">新密碼(≥ 10 字 · 含 3 類:大寫 / 小寫 / 數字 / 符號)</label>
          <div class="um-pwd-row">
            <input type="password" id="um-new-pwd" required minlength="10" value="${this._generatePassword()}"
                   autocomplete="new-password" aria-describedby="um-reset-warn">
            <button type="button" class="btn-secondary" id="um-show-pwd" aria-label="顯示密碼" aria-pressed="false">👁</button>
            <button type="button" class="btn-secondary" id="um-regen-pwd">🎲 重新產</button>
          </div>
          <p id="um-reset-warn" style="color:var(--orange);font-size:12px;margin-top:8px" role="note">
            ⚠ 舊密碼會立即失效 · 同仁需要用新密碼重新登入(伺服器會踢登入 session)
          </p>
        </div>
        <div class="modal2-actions">
          <button type="button" data-cancel>取消</button>
          <button type="button" class="primary" id="um-reset-confirm">確認重設</button>
        </div>
      </div>
    `;
    // 焦點還原 · 先記下開啟前焦點
    const prevFocus = document.activeElement;
    root.appendChild(m);

    const close = () => {
      m.remove();
      document.removeEventListener("keydown", onKey);
      // 還原焦點 (a11y · WCAG 2.4.3)
      if (prevFocus && typeof prevFocus.focus === "function") prevFocus.focus();
    };

    // Esc 關 + Tab focus trap · 用共用 _modalKeyHandler
    const onKey = _modalKeyHandler(m, close);
    document.addEventListener("keydown", onKey);

    m.querySelector("[data-cancel]").addEventListener("click", close);
    m.querySelector("#um-regen-pwd").addEventListener("click", () => {
      m.querySelector("#um-new-pwd").value = this._generatePassword();
    });
    // 顯示 / 隱藏 密碼 toggle
    const showBtn = m.querySelector("#um-show-pwd");
    showBtn.addEventListener("click", () => {
      const input = m.querySelector("#um-new-pwd");
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      showBtn.setAttribute("aria-pressed", showing ? "false" : "true");
      showBtn.setAttribute("aria-label", showing ? "顯示密碼" : "隱藏密碼");
      showBtn.textContent = showing ? "👁" : "👁‍🗨";
    });
    m.querySelector("#um-reset-confirm").addEventListener("click", () => this._submitResetPassword(m, target.email, close));

    // 初始焦點進 modal · 預設聚焦 input(scrren reader 會宣告 dialog + label)
    requestAnimationFrame(() => m.querySelector("#um-new-pwd")?.focus());
  },

  async _submitResetPassword(m, email, close) {
    const newPwd = m.querySelector("#um-new-pwd").value;
    if (!newPwd || newPwd.length < 10) {
      toast.warn("密碼至少 10 字 · 含 3 類字元");
      return;
    }
    const btn = m.querySelector("#um-reset-confirm");
    btn.disabled = true;
    btn.textContent = "⏳ 重設中...";
    try {
      const r = await authFetch(`${BASE}/admin/users/${encodeURIComponent(email)}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: newPwd }),
      });
      if (!r.ok) {
        operationError("重設密碼", await r.json().catch(() => ({})));
        btn.disabled = false;
        btn.textContent = "確認重設";
        return;
      }
      // 透過 close() 同時清 keydown listener + 還原焦點
      if (typeof close === "function") close(); else m.remove();
      await _showPasswordOnce({
        title: "✅ 密碼已重設",
        email,
        password: newPwd,
      });
    } catch (e) {
      networkError("重設密碼", e);
      btn.disabled = false;
      btn.textContent = "確認重設";
    }
  },

  async deletePermanent(email, name) {
    // 兩階段確認 · 第一階段:警告
    const proceed = await modal.confirm(
      `<p style="color:var(--red);font-weight:600">⚠ 永久刪除無法復原</p>
       將刪除 <code>${escapeHtml(email)}</code>(${escapeHtml(name || "")})及連帶資料:
       <ul style="margin:8px 0;padding-left:20px;font-size:13px">
         <li>同仁帳號(users)</li>
         <li>登入 session / refresh token</li>
         <li>👍👎 回饋紀錄</li>
       </ul>
       <p style="font-size:12px;color:var(--text-secondary)">
         保留:對話紀錄(可法律抗辯)+ audit log(操作歷史)
       </p>`,
      { title: "永久刪除同仁", icon: "🗑", primary: "我了解 · 下一步", danger: true }
    );
    if (!proceed) return;

    // 第二階段:打字驗證 email · case-sensitive(WCAG 3.3.4 重要交易需嚴格防誤)
    const r = await modal.prompt(
      [{
        name: "confirm",
        label: `為確認你不是手滑 · 請完整輸入 ${email}(區分大小寫)`,
        placeholder: email,
        required: true,
      }],
      { title: "二段式確認", primary: "永久刪除", icon: "🗑" }
    );
    if (!r) return;
    if ((r.confirm || "").trim() !== email) {
      toast.warn("輸入不符 · 取消(請確認大小寫)");
      return;
    }

    try {
      const r = await authFetch(`${BASE}/admin/users/${encodeURIComponent(email)}/permanent`, {
        method: "DELETE",
      });
      if (!r.ok) {
        operationError("永久刪除", await r.json().catch(() => ({})));
        return;
      }
      const body = await r.json();
      const cleaned = body.related_cleaned || {};
      toast.success(
        `已永久刪除 ${email}(連帶清 sessions=${cleaned.sessions || 0} / feedback=${cleaned.feedback || 0})`
      );
      await this.load();
      this.render();
    } catch (e) {
      networkError("永久刪除", e);
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

/**
 * 自建 dialog · admin 看到一次密碼用
 *
 * 比 modal.alert 安全的點:
 * - 自己控制 DOM root 元素 · scope 鎖定(.querySelector 都 from local m)
 * - 密碼明文存 closure · 永遠不寫入 DOM attribute / textContent 之外的地方
 * - 多 modal 並發時不會抓錯 button(C9 修)
 *
 * @param {{title:string, email:string, password:string, extraNote?:string}} args
 * @returns {Promise<void>}
 */
function _showPasswordOnce({ title, email, password, extraNote }) {
  return new Promise(resolve => {
    const root = document.getElementById("modal-root") || document.body;
    const m = document.createElement("div");
    m.className = "modal2-overlay";
    m.setAttribute("role", "dialog");
    m.setAttribute("aria-modal", "true");
    m.setAttribute("aria-labelledby", "um-cred-title");
    m.innerHTML = `
      <div class="modal2-box" style="max-width:520px">
        <div class="modal2-header" id="um-cred-title">🔐 ${escapeHtml(title)}</div>
        <div style="padding:0 4px">
          <div style="font-family:var(--font-mono);padding:12px;background:var(--surface-2,var(--bg-base));border-radius:8px;margin:8px 0">
            <div><b>電子郵件:</b> ${escapeHtml(email)}</div>
            <div style="margin-top:6px"><b>密碼:</b>
              <span class="um-cred-pwd-text">${escapeHtml(password)}</span>
              <button type="button" class="btn-tiny" data-act="copy" style="margin-left:8px">📋 複製</button>
            </div>
          </div>
          <p style="color:var(--red);font-weight:600">⚠ 這組密碼只顯示一次 · 請立刻複製分給同仁</p>
          ${extraNote ? `<p style="color:var(--text-secondary);font-size:13px">${escapeHtml(extraNote)}</p>` : ""}
        </div>
        <div class="modal2-actions">
          <button type="button" class="primary" data-act="ok">我已複製密碼</button>
        </div>
      </div>
    `;
    const prevFocus = document.activeElement;
    root.appendChild(m);

    const close = () => {
      m.remove();
      document.removeEventListener("keydown", onKey);
      if (prevFocus && typeof prevFocus.focus === "function") prevFocus.focus();
      resolve();
    };
    const onKey = _modalKeyHandler(m, close);
    document.addEventListener("keydown", onKey);

    // scope-local query · 永遠抓自家 modal · 不會被並發其他 modal 干擾
    m.querySelector('[data-act="copy"]').addEventListener("click", e =>
      copyToClipboard(password, e.currentTarget)
    );
    m.querySelector('[data-act="ok"]').addEventListener("click", close);

    requestAnimationFrame(() => m.querySelector('[data-act="ok"]')?.focus());
  });
}

/** 共用 modal keyboard handler · Esc 關 + Tab focus trap
 * J5 · reset password modal + showPasswordOnce 都用 · 不重複實作
 * @param {HTMLElement} m modal root element
 * @param {() => void} close close callback
 * @returns {(e: KeyboardEvent) => void} keydown handler
 */
function _modalKeyHandler(m, close) {
  const FOCUSABLE = 'a[href], input:not([disabled]), button:not([disabled]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  return e => {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "Tab") return;
    const focusable = m.querySelectorAll(FOCUSABLE);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };
}

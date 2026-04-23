/**
 * Knowledge · V1.1-SPEC §E-3
 * ==================================
 * 負責:
 *   · Admin Sources 管理(list / create / patch / delete / reindex)
 *   · 「知識庫」view(sources 樹 + 點資料夾用 drawer pattern 顯示檔)
 *   · ⌘K palette 加「從知識庫搜」來源
 *
 * 不處理:上傳檔(永遠 NAS 為 source of truth)· 抽字在後端
 */
import { authFetch } from "./auth.js";
import { chat } from "./chat.js";
import { escapeHtml } from "./util.js";
import { toast, networkError, operationError } from "./toast.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting";

/**
 * R9#1 / ROADMAP §10.3 · 所有 /knowledge/* 必帶 conversation_id
 * 後端 _resolve_agent_num 從 conversation_id → LibreChat agent → derive agent_num
 * 沒帶 conversation_id 時 prod 拿不到 agent_num · 白名單 source 全藏
 *
 * 用法:`withConvId("/api-accounting/knowledge/list?source_id=xxx")`
 */
function withConvId(url) {
  const id = (chat?.currentConvoId || "").trim();
  if (!id) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}conversation_id=${encodeURIComponent(id)}`;
}

export const knowledge = {
  _sources: [],       // {id, name, type, path, enabled, ...}
  _publicSources: [], // /knowledge/list(無 source_id)回的輕量版
  _drawerState: null,

  // ---------- Admin 側 ----------
  async loadAdmin() {
    const root = document.getElementById("admin-sources-list");
    if (!root) return;
    root.innerHTML = `<div class="chip-empty">載入中…</div>`;
    try {
      const r = await authFetch(`${BASE}/admin/sources`);
      if (!r.ok) throw new Error("fetch fail: " + r.status);
      this._sources = await r.json();
      this._renderAdmin(root);
    } catch (e) {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">😓</div>
          <div class="empty-state-title">無法載入資料源</div>
          <div class="empty-state-hint">${escapeHtml(e.message || "後端 API 可能未啟動")}</div>
          <button class="btn-ghost" onclick="window.knowledge?.loadAdmin()" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  _renderAdmin(root) {
    if (!this._sources.length) {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📂</div>
          <div class="empty-state-title">尚無資料源</div>
          <div class="empty-state-hint"><a href="#" class="link" data-new-source>+ 新增第一個資料源</a></div>
        </div>`;
      root.querySelector("[data-new-source]")?.addEventListener("click", e => {
        e.preventDefault();
        this.openCreateModal();
      });
      return;
    }
    root.innerHTML = this._sources.map(s => {
      const stats = s.last_index_stats || {};
      const last = s.last_indexed_at
        ? `上次:${new Date(s.last_indexed_at).toLocaleString("zh-TW")} · ${stats.file_count || 0} 檔 · ${stats.errors || 0} 錯`
        : "尚未索引";
      const statusCls = s.enabled ? "active" : "closed";
      const statusTxt = s.enabled ? "✓ 啟用" : "⏸ 停用";
      return `
        <article class="source-card" data-source-id="${s.id}">
          <header class="source-head">
            <span class="source-icon">${s.type === "smb" ? "🗄️" : s.type === "usb" ? "💾" : "📁"}</span>
            <div class="source-name">${escapeHtml(s.name)}</div>
            <span class="drawer-status ${statusCls}">${statusTxt}</span>
          </header>
          <div class="source-path"><code>${escapeHtml(s.path)}</code></div>
          <div class="source-meta">${escapeHtml(last)}</div>
          <div class="source-actions">
            <button class="btn-ghost" data-act="health" data-id="${s.id}">🩺 健康</button>
            <button class="btn-ghost" data-act="reindex" data-id="${s.id}">🔄 重索引</button>
            <button class="btn-ghost" data-act="toggle" data-id="${s.id}">
              ${s.enabled ? "暫停" : "啟用"}
            </button>
            <button class="btn-ghost" data-act="delete" data-id="${s.id}">刪除</button>
          </div>
        </article>`;
    }).join("");

    // 事件代理
    root.querySelectorAll("[data-act]").forEach(btn => {
      btn.addEventListener("click", e => {
        const id = btn.dataset.id;
        const act = btn.dataset.act;
        if (act === "reindex") this.reindex(id);
        else if (act === "toggle") this.toggle(id);
        else if (act === "delete") this.remove(id);
        else if (act === "health") this.checkHealth(id);
      });
    });
  },

  openCreateModal() {
    const form = `
      <form id="kb-source-form" class="modal2-form">
        <label>
          <span>名稱 <em>(必填)</em></span>
          <input type="text" name="name" placeholder="例:主 NAS · 所有專案" required>
        </label>
        <label>
          <span>類型</span>
          <select name="type">
            <option value="local">本機 / 外接</option>
            <option value="smb">SMB(NAS)</option>
            <option value="symlink">Symlink</option>
            <option value="usb">USB</option>
          </select>
        </label>
        <label>
          <span>絕對路徑 <em>(必填)</em></span>
          <input type="text" name="path"
                 placeholder="/Volumes/ChengFu-NAS/projects/"
                 required
                 style="font-family:var(--font-mono)">
          <small class="hint">必須在 KNOWLEDGE_ALLOWED_ROOTS 白名單內(預設 /Volumes, /Users, /mnt, /data)</small>
        </label>
        <label>
          <span>排除 pattern(逗號分隔)</span>
          <input type="text" name="excludes"
                 value="*.lock, ~$*, .DS_Store, Thumbs.db, .git/*"
                 style="font-family:var(--font-mono)">
        </label>
        <div class="field-row">
          <label>
            <span>單檔上限 (MB)</span>
            <input type="number" name="max_size_mb" value="50" min="1" max="500">
          </label>
          <label>
            <span>Agent 可讀(空=所有 · 逗號分隔編號)</span>
            <input type="text" name="agent_access" placeholder="例:01,03,09">
          </label>
        </div>
      </form>`;
    modal.openForm({
      title: "+ 新增資料源",
      bodyHTML: form,
      primary: "建立",
      onSubmit: async () => {
        const f = document.getElementById("kb-source-form");
        if (!f.reportValidity()) return false;
        const payload = {
          name: f.name.value.trim(),
          type: f.type.value,
          path: f.path.value.trim(),
          exclude_patterns: f.excludes.value.split(",").map(x => x.trim()).filter(Boolean),
          agent_access: f.agent_access.value.split(",").map(x => x.trim()).filter(Boolean),
          max_size_mb: parseInt(f.max_size_mb.value) || 50,
        };
        try {
          const r = await authFetch(`${BASE}/admin/sources`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText }));
            operationError("建立資料源", err);
            return false;
          }
          toast.success("資料源已建立 · 開始索引…");
          await this.loadAdmin();
          // 立刻觸發 reindex
          const { id } = await r.json();
          this.reindex(id, { silent: true });
          return true;
        } catch (e) {
          networkError("建立資料源", e);
          return false;
        }
      },
    });
  },

  async reindex(id, opts = {}) {
    const btn = document.querySelector(`[data-act="reindex"][data-id="${id}"]`);
    // Round 9 implicit · 同步索引可能 30s+ 卡前端
    // 從現有 last_index_stats.file_count 預估 · > 500 檔給警告
    const src = this._sources.find(s => s.id === id);
    const lastCount = (src?.last_index_stats || {}).file_count || 0;
    if (lastCount > 500 && !opts.silent && !opts.confirmed) {
      const ok = await modal.confirm(
        `這個資料源上次有 ${lastCount} 個檔 · 重索引可能要 1-3 分鐘 · 期間視窗會卡住。<br>` +
        `<small style='color:var(--text-secondary)'>大 source 建議改用每日 02:00 cron 自動跑,不用手動。</small>`,
        { title: "重索引耗時警告", icon: "⏳", primary: "我知道,繼續", cancel: "取消" }
      );
      if (!ok) return;
    }

    if (btn) {
      btn.disabled = true;
      btn.textContent = lastCount > 500 ? "索引中(可能 1-3 分鐘)…" : "索引中…";
    }
    try {
      const r = await authFetch(`${BASE}/admin/sources/${id}/reindex`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        operationError("索引資料源", err, () => this.reindex(id, opts));
        return;
      }
      const stats = await r.json();
      if (!opts.silent) {
        const meili = stats.meili === "indexed" ? "已進全文索引"
                    : stats.meili === "unavailable" ? "已抽字但搜尋暫未啟用 · 下次 cron 補" : "已抽字";
        const took = stats.index_seconds ? ` · ${stats.index_seconds}s` : "";
        toast.success(`索引完成 · ${stats.file_count} 檔 · ${stats.errors} 錯${took} · ${meili}`);
      }
      await this.loadAdmin();
    } catch (e) {
      networkError("索引資料源", e, () => this.reindex(id, opts));
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "🔄 重索引"; }
    }
  },

  async checkHealth(id) {
    const btn = document.querySelector(`[data-act="health"][data-id="${id}"]`);
    if (btn) { btn.disabled = true; btn.textContent = "檢查中…"; }
    try {
      const r = await authFetch(`${BASE}/admin/sources/${id}/health`);
      if (!r.ok) {
        operationError("健康檢查", `HTTP ${r.status}`, () => this.checkHealth(id));
        return;
      }
      const h = await r.json();
      if (h.status === "ok") {
        toast.success(`✓ 路徑正常 · ${h.entry_count} 個 top-level 項`);
      } else {
        toast.warn("資料源狀態異常", { detail: `${h.status} · ${h.issue || ""}` });
      }
    } catch (e) {
      networkError("健康檢查", e, () => this.checkHealth(id));
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "🩺 健康"; }
    }
  },

  async toggle(id) {
    const s = this._sources.find(x => x.id === id);
    if (!s) return;
    try {
      const r = await authFetch(`${BASE}/admin/sources/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !s.enabled }),
      });
      if (!r.ok) throw new Error(r.statusText);
      toast.success(s.enabled ? "已暫停" : "已啟用");
      await this.loadAdmin();
    } catch (e) { operationError("切換啟用狀態", e); }
  },

  async remove(id) {
    const s = this._sources.find(x => x.id === id);
    if (!s) return;
    const ok = await modal.confirm(
      `確定刪除資料源「${escapeHtml(s.name)}」?<br><small style='color:var(--text-secondary)'>檔案本身不會刪,只會從索引移除,無法搜到。</small>`,
      { title: "刪除資料源", icon: "⚠️", primary: "刪除", danger: true }
    );
    if (!ok) return;
    try {
      const r = await authFetch(`${BASE}/admin/sources/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error(r.statusText);
      toast.success("已刪除 · Meili 清除中");
      await this.loadAdmin();
    } catch (e) { operationError("刪除資料源", e); }
  },

  // ---------- 使用者側:知識庫 view ----------
  async loadBrowser() {
    const root = document.getElementById("kb-browser");
    if (!root) return;
    root.innerHTML = `<div class="chip-empty">載入中…</div>`;
    try {
      const r = await authFetch(withConvId(`${BASE}/knowledge/list`));
      if (!r.ok) throw new Error(r.status);
      const { sources } = await r.json();
      this._publicSources = sources || [];
      this._renderBrowser(root);
    } catch (e) {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">😓</div>
          <div class="empty-state-title">無法載入知識庫</div>
          <div class="empty-state-hint">${escapeHtml(e?.message || "網路或後端錯")}</div>
          <button class="btn-ghost" onclick="window.knowledge?.loadBrowser()" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  _renderBrowser(root) {
    if (!this._publicSources.length) {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📚</div>
          <div class="empty-state-title">尚無資料源</div>
          <div class="empty-state-hint">${isAdmin() ? '到 <a href="#" class="link" data-goto-admin>Admin</a> 新增資料源' : "請 Champion 新增"}</div>
        </div>`;
      root.querySelector("[data-goto-admin]")?.addEventListener("click", e => {
        e.preventDefault();
        window.app?.showView?.("admin");
      });
      return;
    }
    root.innerHTML = `
      <header class="kb-head">
        <h3>📚 知識庫 · ${this._publicSources.length} 個資料源 · ${this._publicSources.reduce((a, s) => a + (s.file_count || 0), 0)} 檔</h3>
        <input type="search" id="kb-search-input" placeholder="🔎 搜尋所有資料源…" class="kb-search">
      </header>
      <div id="kb-search-results"></div>
      <div class="kb-sources-list">
        ${this._publicSources.map(s => `
          <article class="kb-source" data-src-id="${s.id}">
            <header>
              <span>${s.type === "smb" ? "🗄️" : s.type === "usb" ? "💾" : "📁"}</span>
              <strong>${escapeHtml(s.name)}</strong>
              <span class="kb-count">(${s.file_count || 0} 檔)</span>
            </header>
            <div class="kb-children" data-placeholder>點選展開…</div>
          </article>
        `).join("")}
      </div>`;
    // 點 source 名稱展開
    root.querySelectorAll(".kb-source header").forEach(h => {
      h.addEventListener("click", () => this._expandSource(h.closest(".kb-source")));
    });
    // 搜尋 · R14#10 · AbortController + debounce · 防打字快時舊 request 先到導致結果亂序
    let _searchAbort = null;
    let _searchDebounce = null;
    root.querySelector("#kb-search-input")?.addEventListener("input", e => {
      const q = e.target.value.trim();
      // 新 request 先 abort 舊的
      if (_searchAbort) { try { _searchAbort.abort(); } catch {} }
      if (_searchDebounce) clearTimeout(_searchDebounce);

      if (q.length < 2) {
        document.getElementById("kb-search-results").innerHTML = "";
        return;
      }
      // 200ms debounce 避免打字快時連 5 個 request
      _searchDebounce = setTimeout(() => {
        _searchAbort = new AbortController();
        this._searchAll(q, _searchAbort.signal);
      }, 200);
    });
  },

  async _expandSource(cardEl) {
    const sid = cardEl.dataset.srcId;
    const children = cardEl.querySelector(".kb-children");
    if (!children.dataset.placeholder && cardEl.classList.contains("open")) {
      cardEl.classList.remove("open");
      return;
    }
    cardEl.classList.add("open");
    children.innerHTML = "載入中…";
    try {
      const r = await authFetch(withConvId(`${BASE}/knowledge/list?source_id=${sid}`));
      if (!r.ok) throw new Error(r.statusText);
      const { entries } = await r.json();
      delete children.dataset.placeholder;
      if (!entries.length) {
        children.innerHTML = `<span class="kb-empty">(空)</span>`;
        return;
      }
      children.innerHTML = entries.map(e => `
        <div class="kb-entry ${e.is_dir ? 'dir' : 'file'}"
             data-src="${sid}" data-path="${encodeURIComponent(e.rel_path)}" data-is-dir="${e.is_dir}">
          <span class="kb-entry-icon">${e.is_dir ? "📂" : "📄"}</span>
          <span>${escapeHtml(e.name)}</span>
          ${e.size ? `<span class="kb-entry-size">${formatSize(e.size)}</span>` : ""}
        </div>
      `).join("");
      children.querySelectorAll(".kb-entry").forEach(el => {
        el.addEventListener("click", () => {
          const isDir = el.dataset.isDir === "true";
          const path = decodeURIComponent(el.dataset.path);
          if (isDir) this._browseFolder(sid, path);
          else this._openFile(sid, path);
        });
      });
    } catch (e) {
      children.innerHTML = `<span class="kb-empty">❌ ${escapeHtml(e.message)}</span>`;
    }
  },

  async _browseFolder(sid, path) {
    try {
      const r = await authFetch(withConvId(`${BASE}/knowledge/list?source_id=${sid}&project=${encodeURIComponent(path)}`));
      if (!r.ok) throw new Error(r.statusText);
      const body = await r.json();
      // 用 drawer 顯示資料夾內容(reuse C 的 drawer)
      const existingTitle = document.getElementById("drawer-project-name");
      if (existingTitle) existingTitle.textContent = `📂 ${path}`;
      const existing = document.getElementById("dr-description");
      if (existing) {
        existing.textContent = body.entries.map(e =>
          `${e.is_dir ? "📂" : "📄"} ${e.name}${e.size ? " (" + formatSize(e.size) + ")" : ""}`
        ).join("\n");
      }
      document.getElementById("dr-description-section").style.display = "";
      // hide handoff 區塊 · 知識庫瀏覽不適用
      // Round 9 bug fix · 標記為「知識庫模式」· app.openProjectDrawer 會在開專案時復原
      const handoffEl = document.getElementById("dr-handoff");
      if (handoffEl) {
        handoffEl.style.display = "none";
        handoffEl.dataset.hiddenByKnowledge = "1";
      }
      const drawer = document.getElementById("project-drawer");
      if (drawer) drawer.dataset.mode = "knowledge";
      document.getElementById("project-drawer-backdrop")?.classList.add("open");
      drawer?.classList.add("open");
    } catch (e) { operationError("開啟資料夾", e); }
  },

  async _openFile(sid, rel) {
    try {
      const r = await authFetch(withConvId(`${BASE}/knowledge/read?source_id=${sid}&rel_path=${encodeURIComponent(rel)}`));
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("讀取檔案", err);
        return;
      }
      const body = await r.json();
      const preview = body.content_preview || "(無法抽字)";
      // 用 modal 顯示 preview(很短 · 不用 drawer)
      modal.show({
        title: `📄 ${body.filename}`,
        bodyHTML: `
          <div class="kb-file-meta">
            <span>${body.mime}</span>
            <span>${formatSize(body.size)}</span>
            <span>修改:${new Date(body.modified_at).toLocaleString("zh-TW")}</span>
          </div>
          <pre class="kb-file-preview">${escapeHtml(preview.substring(0, 2000))}</pre>
          ${body.content_preview?.length > 2000 ? '<p class="hint">已截前 2000 字 · 完整檔請到 NAS 開</p>' : ""}`,
        primary: "複製預覽",
        onSubmit: async () => {
          try {
            await navigator.clipboard.writeText(preview);
            toast.success("已複製");
          } catch { toast.info("請手動複製"); }
          return true;
        },
      });
    } catch (e) { operationError("開啟檔案", e); }
  },

  async _searchAll(q, signal) {
    const root = document.getElementById("kb-search-results");
    if (!root) return;
    root.innerHTML = `<div class="chip-empty">搜尋中…</div>`;
    try {
      const r = await authFetch(withConvId(`${BASE}/knowledge/search?q=${encodeURIComponent(q)}&limit=20`), { signal });
      if (!r.ok) throw new Error(r.status);
      const body = await r.json();
      const hits = body.hits || [];
      if (!hits.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <div class="empty-state-title">找不到結果</div>
            <div class="empty-state-hint">${body.message ? escapeHtml(body.message) : "試試其他關鍵字 · 或縮短搜尋"}</div>
          </div>`;
        return;
      }
      root.innerHTML = `
        <h4 style="margin:12px 0 8px; font-size:12px; color:var(--text-tertiary)">
          ${body.estimatedTotalHits || hits.length} 個結果
        </h4>
        ${hits.map(h => `
          <div class="kb-hit" data-src="${h.source_id}" data-path="${encodeURIComponent(h.rel_path)}">
            <div class="kb-hit-head">
              <span>📄 ${escapeHtml(h.filename)}</span>
              <span class="kb-hit-source">${escapeHtml(h.source_name || "")}</span>
            </div>
            <div class="kb-hit-path"><code>${escapeHtml(h.rel_path)}</code></div>
            ${h.content_preview ? `<div class="kb-hit-preview">${escapeHtml(h.content_preview.substring(0, 150))}…</div>` : ""}
          </div>
        `).join("")}`;
      root.querySelectorAll(".kb-hit").forEach(el => {
        el.addEventListener("click", () => {
          this._openFile(el.dataset.src, decodeURIComponent(el.dataset.path));
        });
      });
    } catch (e) {
      // R17#3 · AbortError 是 debounce/新輸入觸發的主動 abort · 不是真錯 · 不閃紅
      if (e?.name === "AbortError") return;
      root.innerHTML = `<div class="chip-empty">❌ 搜尋失敗</div>`;
    }
  },

  // ---------- ⌘K palette 整合 ----------
  async paletteSearch(q) {
    if (!q || q.length < 2) return [];
    try {
      const r = await authFetch(withConvId(`${BASE}/knowledge/search?q=${encodeURIComponent(q)}&limit=5`));
      if (!r.ok) return [];
      const body = await r.json();
      return (body.hits || []).map(h => ({
        icon: "📁",
        label: h.filename,
        hint: `${h.source_name || ""}${h.project ? " · " + h.project : ""} · ${h.type || "file"}`,
        action: () => this._openFile(h.source_id, h.rel_path),
      }));
    } catch { return []; }
  },
};

function formatSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

function isAdmin() {
  return document.documentElement.dataset.role === "admin";
}

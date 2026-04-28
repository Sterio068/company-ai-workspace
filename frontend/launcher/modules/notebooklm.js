/**
 * NotebookLM simple knowledge bridge.
 *
 * UX rule: users should only need to understand three actions:
 * choose local data, preview it, then create/sync a readable pack.
 */
import { authFetch } from "./auth.js";
import { escapeHtml, copyToClipboard } from "./util.js";
import { toast, networkError, operationError } from "./toast.js";
import { Projects } from "./projects.js";

const BASE = "/api-accounting/notebooklm";
const DOCS = {
  overview: "https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/overview",
  notebooks: "https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks",
  sources: "https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources",
};

export const notebooklm = {
  status: null,
  settings: null,
  packs: [],
  preview: null,
  lastUpload: null,
  lastUploadFiles: [],
  lastUploadKind: "files",

  async load() {
    await Promise.all([this.loadStatus(), this.loadPacks(), this.loadSettings()]);
    this.render();
  },

  async loadStatus() {
    try {
      const r = await authFetch(`${BASE}/status`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      this.status = await r.json();
    } catch (e) {
      this.status = { _error: e?.message || "讀取失敗" };
    }
  },

  async loadSettings() {
    try {
      const r = await authFetch(`${BASE}/settings`);
      if (r.status === 403) {
        this.settings = null;
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      this.settings = await r.json();
    } catch {
      this.settings = null;
    }
  },

  async loadPacks() {
    try {
      const r = await authFetch(`${BASE}/source-packs`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      this.packs = (await r.json()).items || [];
    } catch {
      this.packs = [];
    }
  },

  render() {
    const root = document.getElementById("notebooklm-content");
    if (!root) return;
    const cfg = this.status?.notebooklm || {};
    root.innerHTML = `
      <section class="nlm-simple-hero" role="region" aria-labelledby="notebooklm-title">
        <div>
          <div class="nlm-kicker">NotebookLM</div>
          <h2 id="notebooklm-title">本地資料庫並行 NotebookLM</h2>
          <p>工作包、會議、會計、商機仍在本地管理；需要深讀、摘要或教學素材時，建立資料包或上傳檔案到專案筆記本。</p>
        </div>
        <div class="nlm-simple-status">
          <span><b>正式資料</b>本地資料庫</span>
          <span><b>NotebookLM</b>${cfg.configured ? "已連線" : "未連線"}</span>
        </div>
      </section>

      <section class="nlm-relation-map" role="region" aria-labelledby="notebooklm-relation-title">
        <h3 id="notebooklm-relation-title">資料怎麼流動</h3>
        ${relationCard("本地資料庫", "工作包、會議、會計、商機、教學")}
        <span class="nlm-relation-arrow" aria-hidden="true">→</span>
        ${relationCard("資料包 / 檔案", "可預覽、可複製、可同步")}
        <span class="nlm-relation-arrow" aria-hidden="true">→</span>
        ${relationCard("專案 Notebook", "一個工作包一本筆記本")}
      </section>

      <section class="nlm-simple-steps" aria-label="NotebookLM 操作流程">
        ${stepCard("1", "選本地資料", "選工作包、商機、公司知識或教學")}
        ${stepCard("2", "確認內容", "先預覽資料包或檢查檔案範圍")}
        ${stepCard("3", "送到筆記本", cfg.configured ? "同步到專案 Notebook" : "先保存在本地，也可手動貼入")}
      </section>

      <section class="nlm-simple-grid" aria-label="NotebookLM 主要操作">
        ${this.renderCreateForm()}
        ${this.renderUploadPanel()}
        ${this.renderPreview()}
      </section>

      ${this.renderHistory()}
      ${this.renderSettings()}
    `;
    this.bind(root);
  },

  renderCreateForm() {
    const projects = Projects.load();
    return `
      <article class="nlm-panel nlm-main-task" role="region" aria-labelledby="notebooklm-pack-title">
        <div class="nlm-panel-head">
          <div>
            <div class="nlm-section-kicker">資料包</div>
            <h3 id="notebooklm-pack-title">從本地資料建立資料包</h3>
          </div>
          <span class="nlm-badge">一專案一本筆記本</span>
        </div>
        <form id="notebooklm-pack-form" class="nlm-form">
          <label>要整理哪種資料?
            <select name="scope">
              <option value="project">單一工作包</option>
              <option value="tenders">商機與標案摘要</option>
              <option value="company">公司知識與 SOP</option>
              <option value="training">使用教學</option>
            </select>
          </label>
          <label data-project-row>選擇工作包
            <select name="project_id">
              ${projects.length ? projects.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name || p.id)}</option>`).join("") : `<option value="">尚無工作包</option>`}
            </select>
          </label>

          <details class="nlm-mini-details">
            <summary>進階選項</summary>
            <label>自訂標題(可不填)
              <input name="title" placeholder="例: 文化節提案深讀包">
            </label>
            <div class="nlm-form-row">
              <label>最多讀取筆數
                <input name="max_items" type="number" min="1" max="100" value="20">
              </label>
              <label>資料等級
                <select name="sensitivity">
                  <option value="all">完整資料</option>
                  <option value="L2">一般資料</option>
                  <option value="L1">公開資料</option>
                  <option value="L3">機敏資料</option>
                </select>
              </label>
            </div>
          </details>

          <div class="nlm-actions">
            <button type="button" class="btn-ghost" data-nlm-preview>先預覽</button>
            <button type="submit" class="btn-primary">建立資料包</button>
          </div>
          <p class="nlm-form-help">資料包會歸入同一個工作包的 NotebookLM 筆記本。</p>
        </form>
      </article>
    `;
  },

  renderUploadPanel() {
    const projects = Projects.load();
    return `
      <article class="nlm-panel nlm-upload-panel" role="region" aria-labelledby="notebooklm-upload-title">
        <div class="nlm-panel-head">
          <div>
            <div class="nlm-section-kicker">檔案上傳</div>
            <h3 id="notebooklm-upload-title">直接送檔案或整個資料夾</h3>
          </div>
          <span class="nlm-badge ok">自動歸檔</span>
        </div>
        <p class="nlm-form-help">選工作包後會進同一本專案 Notebook；不選時，系統會用資料夾與檔名比對工作包。</p>
        <label>歸入工作包
          <select id="notebooklm-upload-project">
            <option value="">自動判斷</option>
            ${projects.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name || p.id)}</option>`).join("")}
          </select>
        </label>
        <input id="notebooklm-file-input" type="file" multiple hidden>
        <input id="notebooklm-folder-input" type="file" multiple webkitdirectory directory hidden>
        <div class="nlm-upload-actions">
          <button type="button" class="btn-ghost" data-nlm-pick-files>選檔案</button>
          <button type="button" class="btn-primary" data-nlm-pick-folder>選整個資料夾</button>
        </div>
        ${this.renderUploadResult()}
      </article>
    `;
  },

  renderUploadResult() {
    if (!this.lastUpload) {
      return `<div class="nlm-upload-result muted">尚未上傳檔案。</div>`;
    }
    const result = this.lastUpload;
    const notebook = result.notebook || {};
    const total = Number(result.total || result.items?.length || 0);
    const uploaded = Number(result.uploaded || 0);
    const failed = Number(result.failed || 0);
    const skipped = Number(result.skipped || 0);
    const note = result.configured === false
        ? "NotebookLM 尚未連線,檔案未送出,已保留本地紀錄。"
      : `批次 ${escapeHtml(shortBatch(result.batch_id))}:成功 ${uploaded} / 失敗 ${failed} / 略過 ${skipped}`;
    return `
      <div class="nlm-upload-result">
        <strong>${escapeHtml(note)}</strong>
        ${total ? `<div class="nlm-upload-progress" aria-label="上傳進度"><span style="width:${progressWidth(uploaded + skipped, total)}%"></span></div>` : ""}
        <span>工作包:${escapeHtml(result.project_id || "未判斷")} · 筆記本:${escapeHtml(notebook.title || notebook.notebook_id || "尚未建立")}</span>
        ${notebook.web_url ? `<a href="${escapeHtml(notebook.web_url)}" target="_blank" rel="noreferrer">開啟 NotebookLM</a>` : ""}
        ${failed && this.lastUploadFiles.length ? `<button type="button" class="btn-ghost" data-nlm-retry-upload>重試失敗檔</button>` : ""}
      </div>`;
  },

  renderPreview() {
    if (!this.preview) {
      return `
        <article class="nlm-panel nlm-preview is-empty" role="region" aria-labelledby="notebooklm-preview-title">
          <div class="nlm-section-kicker">預覽</div>
          <h3 id="notebooklm-preview-title">這裡會顯示 NotebookLM 將讀到的內容</h3>
          <p>預覽通過後再建立資料包。NotebookLM 不會直接讀本地資料庫,也不會直接改正式資料；同步時會把資料包送到 NotebookLM Enterprise。</p>
        </article>`;
    }
    return `
      <article class="nlm-panel nlm-preview" role="region" aria-labelledby="notebooklm-preview-title">
        <div class="nlm-panel-head">
          <div>
            <div class="nlm-section-kicker">預覽</div>
            <h3 id="notebooklm-preview-title">${escapeHtml(this.preview.title)}</h3>
          </div>
          <button class="btn-ghost" data-nlm-copy-preview>複製預覽</button>
        </div>
        <div class="nlm-preview-meta">
          <span>${scopeLabel(this.preview.scope)}</span>
          <span>${escapeHtml(this.preview.sensitivity || "L2")}</span>
          <span>${Number(this.preview.char_count || 0).toLocaleString()} 字</span>
        </div>
        <pre class="nlm-preview-pre">${escapeHtml(this.preview.preview_md || "")}</pre>
      </article>`;
  },

  renderHistory() {
    return `
      <details class="nlm-details">
        <summary>
          <span>最近資料包</span>
          <small>${this.packs.length ? `${this.packs.length} 筆` : "尚無資料包"}</small>
        </summary>
        ${this.renderPacks(this.status?.notebooklm || {})}
      </details>`;
  },

  renderSettings() {
    if (!this.settings) {
      return `
        <details class="nlm-details">
          <summary>
            <span>管理員連線設定</span>
            <small>需管理員權限</small>
          </summary>
          <p class="nlm-details-note">只有管理員可設定 NotebookLM Enterprise。一般使用者只需要建立資料包。</p>
        </details>`;
    }
    const cfg = this.settings;
    return `
      <details class="nlm-details">
        <summary>
          <span>管理員連線設定</span>
          <small>${cfg.configured ? "已可同步" : "尚未完成"}</small>
        </summary>
        <form id="notebooklm-settings-form" class="nlm-settings-form">
          <label class="nlm-check">
            <input type="checkbox" name="enabled" ${cfg.enabled ? "checked" : ""}>
            啟用 NotebookLM Enterprise API
          </label>
          <label>Google Cloud 專案編號
            <input name="project_number" value="${escapeHtml(cfg.project_number || "")}" placeholder="例: 123456789012">
          </label>
          <div class="nlm-form-row">
            <label>Location
              <input name="location" value="${escapeHtml(cfg.location || "global")}" placeholder="global / us / eu">
            </label>
            <label>Endpoint Location
              <input name="endpoint_location" value="${escapeHtml(cfg.endpoint_location || "global")}" placeholder="global / us / eu">
            </label>
          </div>
          <label>存取權杖(寫入後不回顯)
            <input name="access_token" type="password" autocomplete="off" placeholder="${escapeHtml(cfg.access_token_preview || "貼上 gcloud access token")}">
          </label>
          <label class="nlm-check">
            <input type="checkbox" name="clear_access_token">
            清除目前權杖
          </label>
          ${cfg.missing?.length ? `<div class="nlm-missing">尚缺:${cfg.missing.map(escapeHtml).join("、")}</div>` : ""}
          <div class="nlm-doc-links">
            <a href="${DOCS.overview}" target="_blank" rel="noreferrer">產品總覽</a>
            <a href="${DOCS.notebooks}" target="_blank" rel="noreferrer">Notebook API</a>
            <a href="${DOCS.sources}" target="_blank" rel="noreferrer">Sources API</a>
          </div>
          <button class="btn-primary" type="submit">儲存設定</button>
        </form>
      </details>`;
  },

  renderPacks(cfg) {
    if (!this.packs.length) {
      return `<div class="empty-state compact"><div class="empty-state-title">尚無資料包</div><div class="empty-state-hint">建立第一包後會顯示在這裡。</div></div>`;
    }
    return `<div class="nlm-pack-list">${this.packs.map(pack => `
      <article class="nlm-pack-card">
        <div class="nlm-pack-main">
          <span class="status-pill ${pack.status === "synced" ? "ok" : "warn"}">${pack.status === "synced" ? "已同步" : "本地"}</span>
          <div>
            <div class="nlm-pack-title">${escapeHtml(pack.title)}</div>
            <div class="nlm-pack-meta">
              ${scopeLabel(pack.scope)} · ${Number(pack.char_count || 0).toLocaleString()} 字 · ${shortHash(pack.content_hash)}
              <span class="nlm-mini-badge">${escapeHtml(pack.sensitivity || "all")}</span>
              ${agentBadge(pack.created_by)}
            </div>
          </div>
        </div>
        <div class="nlm-pack-actions">
          <button class="btn-ghost" data-nlm-copy="${escapeHtml(pack._id)}">複製</button>
          <button class="btn-primary" data-nlm-sync="${escapeHtml(pack._id)}" data-nlm-sensitivity="${escapeHtml(pack.sensitivity || "all")}" data-nlm-created-by="${escapeHtml(pack.created_by || "")}" ${cfg.configured ? "" : "title=\"尚未設定 NotebookLM,會保留本地資料包\""}>同步</button>
        </div>
      </article>
    `).join("")}</div>`;
  },

  bind(root) {
    const form = root.querySelector("#notebooklm-pack-form");
    const scopeSelect = form?.querySelector('[name="scope"]');
    const projectRow = form?.querySelector("[data-project-row]");
    const syncProjectRow = () => {
      if (projectRow) projectRow.style.display = scopeSelect?.value === "project" ? "" : "none";
    };
    scopeSelect?.addEventListener("change", syncProjectRow);
    syncProjectRow();

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      await this.createPack(new FormData(form));
    });
    root.querySelector("[data-nlm-preview]")?.addEventListener("click", async () => {
      if (form) await this.previewPack(new FormData(form));
    });
    root.querySelector("[data-nlm-copy-preview]")?.addEventListener("click", async (e) => {
      await copyToClipboard(this.preview?.preview_md || "", e.currentTarget);
    });
    root.querySelector("#notebooklm-settings-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      await this.saveSettings(new FormData(e.currentTarget));
    });
    const fileInput = root.querySelector("#notebooklm-file-input");
    const folderInput = root.querySelector("#notebooklm-folder-input");
    root.querySelector("[data-nlm-pick-files]")?.addEventListener("click", () => fileInput?.click());
    root.querySelector("[data-nlm-pick-folder]")?.addEventListener("click", () => folderInput?.click());
    root.querySelector("[data-nlm-retry-upload]")?.addEventListener("click", async () => {
      await this.uploadFiles(this.lastUploadFiles, this.lastUploadKind, {
        batchId: this.lastUpload?.batch_id,
        resumeFailedOnly: true,
      });
    });
    fileInput?.addEventListener("change", async () => {
      await this.uploadFiles(Array.from(fileInput.files || []), "files");
      fileInput.value = "";
    });
    folderInput?.addEventListener("change", async () => {
      await this.uploadFiles(Array.from(folderInput.files || []), "folder");
      folderInput.value = "";
    });
    if (root.dataset.nlmClickBound !== "true") {
      root.dataset.nlmClickBound = "true";
      root.addEventListener("click", async (e) => {
        const copyBtn = e.target.closest("[data-nlm-copy]");
        if (copyBtn) {
          await this.copyPack(copyBtn.dataset.nlmCopy, copyBtn);
          return;
        }
        const syncBtn = e.target.closest("[data-nlm-sync]");
        if (syncBtn) {
          await this.syncPack(syncBtn.dataset.nlmSync, syncBtn);
        }
      });
    }
  },

  payload(fd) {
    const scope = fd.get("scope");
    return {
      scope,
      project_id: scope === "project" ? clean(fd.get("project_id")) || null : null,
      title: clean(fd.get("title")) || null,
      max_items: Number(fd.get("max_items") || 20),
      sensitivity: fd.get("sensitivity") || "L2",
    };
  },

  settingsPayload(fd) {
    return {
      enabled: fd.get("enabled") === "on",
      project_number: clean(fd.get("project_number")),
      location: clean(fd.get("location")) || "global",
      endpoint_location: clean(fd.get("endpoint_location")) || "global",
      access_token: clean(fd.get("access_token")) || null,
      clear_access_token: fd.get("clear_access_token") === "on",
    };
  },

  async previewPack(fd) {
    try {
      const r = await authFetch(`${BASE}/source-packs/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.payload(fd)),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("預覽資料包", err);
        return;
      }
      this.preview = await r.json();
      this.render();
      toast.success("預覽已產生", { detail: this.preview.title });
    } catch (e) {
      networkError("預覽資料包", e);
    }
  },

  async createPack(fd) {
    try {
      const r = await authFetch(`${BASE}/source-packs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.payload(fd)),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("建立資料包", err);
        return;
      }
      const body = await r.json();
      toast.success(body.deduped ? "資料包已存在,已更新時間" : "資料包已建立");
      await this.load();
    } catch (e) {
      networkError("建立資料包", e);
    }
  },

  async saveSettings(fd) {
    try {
      const r = await authFetch(`${BASE}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.settingsPayload(fd)),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("儲存 NotebookLM 設定", err);
        return;
      }
      const body = await r.json();
      this.settings = body.notebooklm || null;
      toast.success("NotebookLM 設定已儲存");
      await this.load();
    } catch (e) {
      networkError("儲存 NotebookLM 設定", e);
    }
  },

  async uploadFiles(files, kind = "files", options = {}) {
    if (!files.length) return;
    const projectSelect = document.getElementById("notebooklm-upload-project");
    const projectId = projectSelect?.value || "";
    const fd = new FormData();
    if (projectId) fd.append("project_id", projectId);
    if (options.batchId) fd.append("batch_id", options.batchId);
    if (options.resumeFailedOnly) fd.append("resume_failed_only", "true");
    for (const file of files) {
      fd.append("files", file);
      fd.append("relative_paths", file.webkitRelativePath || file.name);
    }
    this.lastUploadFiles = files;
    this.lastUploadKind = kind;
    toast.info(kind === "folder" ? "資料夾上傳中" : "檔案上傳中", {
      detail: options.resumeFailedOnly
        ? `${files.length} 個檔案 · 只重試上一批失敗項目`
        : `${files.length} 個檔案 · 會自動歸入工作包筆記本`,
      duration: 2500,
    });
    try {
      const r = await authFetch(`${BASE}/uploads/auto`, {
        method: "POST",
        body: fd,
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("上傳到 NotebookLM", err);
        return;
      }
      this.lastUpload = await r.json();
      toast.success("上傳流程完成", {
        detail: this.lastUpload.configured === false
          ? "NotebookLM 尚未連線,檔案未送出,已保留本地紀錄"
          : `成功 ${this.lastUpload.uploaded || 0} 個 · 失敗 ${this.lastUpload.failed || 0} 個`,
      });
      await this.load();
    } catch (e) {
      networkError("上傳到 NotebookLM", e);
    }
  },

  async copyPack(packId, btn) {
    try {
      const r = await authFetch(`${BASE}/source-packs/${encodeURIComponent(packId)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      await copyToClipboard(body.content_md || "", btn);
    } catch (e) {
      networkError("複製資料包", e);
    }
  },

  async syncPack(packId, btn) {
    const sensitivity = btn?.dataset?.nlmSensitivity || "";
    const createdBy = btn?.dataset?.nlmCreatedBy || "";
    const needsConfirm = sensitivity === "L3" || createdBy.startsWith("agent:");
    let confirmed = false;
    if (needsConfirm) {
      const reason = sensitivity === "L3" ? "這份資料包標示為 L3。" : "這份資料包由 Agent 建立。";
      confirmed = window.confirm(`${reason}同步後會送到 NotebookLM Enterprise。確定要同步嗎?`);
      if (!confirmed) return;
    }
    const old = btn?.textContent;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "同步中…";
    }
    try {
      const r = await authFetch(`${BASE}/source-packs/${encodeURIComponent(packId)}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ create_notebook: true, confirm_send_to_notebooklm: confirmed }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("同步 NotebookLM", err);
        return;
      }
      const body = await r.json();
      toast.success(body.configured === false ? "已保留本地資料包" : "已同步 NotebookLM", {
        detail: body.reason || body.notebook_id || "完成",
      });
      await this.load();
    } catch (e) {
      networkError("同步 NotebookLM", e);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = old || "同步";
      }
    }
  },
};

function stepCard(num, title, body) {
  return `
    <article class="nlm-step-card" role="group" aria-label="${escapeHtml(title)}">
      <span>${escapeHtml(num)}</span>
      <strong>${escapeHtml(title)}</strong>
      <small>${escapeHtml(body)}</small>
    </article>`;
}

function relationCard(title, body) {
  return `
    <div class="nlm-relation-card">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(body)}</span>
    </div>`;
}

function agentBadge(createdBy) {
  const value = String(createdBy || "");
  if (!value.startsWith("agent:")) return "";
  return `<span class="nlm-agent-badge">Agent 建立 · ${escapeHtml(value.replace("agent:", ""))}</span>`;
}

function shortHash(hash) {
  return hash ? String(hash).slice(0, 8) : "no-hash";
}

function shortBatch(batchId) {
  return batchId ? String(batchId).slice(0, 8) : "local";
}

function progressWidth(done, total) {
  if (!total) return 0;
  return Math.max(4, Math.min(100, Math.round((done / total) * 100)));
}

function clean(value) {
  return String(value || "").trim();
}

function scopeLabel(scope) {
  return {
    project: "工作包",
    tenders: "商機",
    company: "公司知識",
    training: "使用教學",
  }[scope] || String(scope || "未分類");
}

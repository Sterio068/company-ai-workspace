/**
 * Workflows view · Phase E 下一步草稿入口
 *
 * 先產生「步驟 + 主管家 prompt」,由使用者確認後再送出。
 * 不在前端暴露一鍵跑完,避免繞過人工確認、quota 與 audit。
 */
import { escapeHtml } from "./util.js";
import { modal } from "./modal.js";
import { toast } from "./toast.js";
import { authFetch } from "./auth.js";
import { chat } from "./chat.js";

const BASE = "/api-accounting/orchestrator";

export const workflows = {
  async load() {
    const root = document.getElementById("workflows-grid");
    if (!root) return;
    root.innerHTML = `<div class="chip-empty">載入下一步模板中…</div>`;
    try {
      const r = await authFetch(`${BASE}/workflow/presets`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const list = await r.json();
      if (!Array.isArray(list) || !list.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">⚡</div>
            <div class="empty-state-title">尚無下一步模板</div>
            <div class="empty-state-hint">目前預期有投標整理 / 活動企劃 / 新聞發布</div>
          </div>`;
        return;
      }
      root.innerHTML = list.map(w => `
        <article class="workspace-card" style="--ws-color:${_colorFor(w.id)};cursor:pointer"
                 data-workflow-id="${escapeHtml(w.id)}">
          <div class="ws-head">
            <div class="ws-icon">${_iconFor(w.id)}</div>
            <div class="ws-name">${escapeHtml(w.name)}</div>
          </div>
          <div class="ws-desc">${escapeHtml(w.description)}</div>
          <div class="ws-next">先產草稿,你確認後才送出</div>
          <div class="ws-deliverable">產出:${escapeHtml(_deliverableFor(w.id))}</div>
          <div class="ws-meta">
            <span>${w.step_count} 個步驟</span>
            <span>不會自動送出</span>
          </div>
          <div class="ws-cta">幫我拆下一步 →</div>
        </article>
      `).join("");
      root.querySelectorAll("[data-workflow-id]").forEach(card => {
        card.addEventListener("click", () => this.prepare(card.dataset.workflowId));
      });
    } catch (e) {
      console.warn("[workflows] load failed", e);
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🧪</div>
          <div class="empty-state-title">下一步建議暫時無法載入</div>
          <div class="empty-state-hint">請稍後重試;若持續發生,再請管理員檢查後端服務。</div>
          <button class="btn-ghost" onclick="window.workflows?.load?.()" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  async prepare(presetId, options = {}) {
    const r = await modal.prompt([
      {
        name: "input",
        label: "初始輸入",
        type: "textarea",
        rows: 5,
        required: true,
        placeholder: "例:貼入招標摘要 / 活動主題 / 新聞事實。先不用整理,主管家會幫你拆步驟。",
      },
    ], { title: `產生下一步草稿 · ${presetId}`, icon: "⚡", primary: "產生草稿" });
    if (!r) return;

    try {
      const resp = await authFetch(`${BASE}/workflow/prepare-preset/${encodeURIComponent(presetId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          initial_input: r.input,
          project_id: options.projectId || null,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const draft = await resp.json();
      await this.showDraft(draft);
      if (draft.saved_to_project) {
        toast.success("下一步草稿已寫入專案交棒卡");
      }
    } catch (e) {
      console.warn("[workflows] prepare failed", e);
      toast.error("下一步草稿產生失敗 · 請稍後重試");
    }
  },

  async showDraft(draft) {
    const steps = (draft.steps || []).map(s => `
      <li style="margin:8px 0">
        <strong>${escapeHtml(s.id)}</strong>
        <span style="color:var(--text-secondary)"> · 助手 ${escapeHtml(s.agent_id)} · ${escapeHtml(s.expected_output || "步驟產出")}</span>
      </li>
    `).join("");
    const preview = escapeHtml(draft.supervisor_prompt || "").slice(0, 1400);
    const ok = await modal.confirm(
      `<div style="display:grid;gap:12px">
        <div style="color:var(--text-secondary)">這份草稿只會帶入主管家輸入框,你仍可修改後再送出。</div>
        <ol style="padding-left:20px;margin:0">${steps}</ol>
        <pre style="white-space:pre-wrap;background:var(--bg-base);border:1px solid var(--border);border-radius:10px;padding:10px;max-height:260px;overflow:auto">${preview}</pre>
      </div>`,
      {
        title: draft.name || "下一步草稿",
        icon: "⚡",
        primary: "帶到主管家",
        cancel: "先不要",
      }
    );
    if (ok) {
      await this.recordAdoption(draft, "adopted");
      chat.open("00", draft.supervisor_prompt || "");
      toast.info("下一步草稿已帶入主管家 · 檢查後再送出");
    } else {
      await this.recordAdoption(draft, "rejected", "使用者暫不帶到主管家");
    }
  },

  async recordAdoption(draft, status, note = "") {
    try {
      await authFetch(`${BASE}/workflow/adoptions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preset_id: draft.id,
          preset_name: draft.name,
          status,
          project_id: draft.saved_to_project?.project_id || null,
          note,
        }),
      });
    } catch (e) {
      console.warn("[workflows] adoption record failed", e);
    }
  },
};

function _iconFor(id) {
  return id === "tender-full" ? "🎯" :
         id === "event-planning" ? "🎪" :
         id === "news-release" ? "📣" : "⚡";
}

function _colorFor(id) {
  return id === "tender-full" ? "#FF3B30" :
         id === "event-planning" ? "#FF9500" :
         id === "news-release" ? "#34C759" : "#AF52DE";
}

function _deliverableFor(id) {
  return id === "tender-full" ? "承接評估、建議書大綱、報價風險" :
         id === "event-planning" ? "場景需求單、主視覺方向、預算分配" :
         id === "news-release" ? "新聞稿、媒體邀請電子郵件" : "多步驟交付草稿";
}

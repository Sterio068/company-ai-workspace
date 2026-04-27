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
      // v1.54 · 同步問 kill switch · 決定要不要顯示「直接執行」
      let canExecute = false;
      try {
        const k = await authFetch(`${BASE}/workflow/kill-switch`).then(r => r.ok ? r.json() : null);
        canExecute = !!k?.execution_enabled;
      } catch {}

      root.innerHTML = list.map(w => `
        <article class="workspace-card" style="--ws-color:${_colorFor(w.id)}"
                 data-workflow-id="${escapeHtml(w.id)}">
          <div class="ws-head">
            <div class="ws-icon">${_iconFor(w.id)}</div>
            <div class="ws-name">${escapeHtml(w.name)}</div>
          </div>
          <div class="ws-desc">${escapeHtml(w.description)}</div>
          <div class="ws-deliverable">產出:${escapeHtml(_deliverableFor(w.id))}</div>
          <div class="ws-meta">
            <span>${w.step_count} 個步驟</span>
          </div>
          <div class="ws-actions" style="display:flex;gap:8px;margin-top:10px">
            <button type="button" class="btn-ghost wf-prepare-btn" data-wf-prepare="${escapeHtml(w.id)}" style="flex:1">
              拆下一步草稿
            </button>
            ${canExecute ? `
              <button type="button" class="btn-primary wf-execute-btn" data-wf-execute="${escapeHtml(w.id)}" style="flex:1"
                      title="主管家會自動串接所有步驟 · 每日 5 次上限">
                🚀 直接執行
              </button>
            ` : ""}
          </div>
        </article>
      `).join("");
      root.querySelectorAll("[data-wf-prepare]").forEach(btn => {
        btn.addEventListener("click", () => this.prepare(btn.dataset.wfPrepare));
      });
      root.querySelectorAll("[data-wf-execute]").forEach(btn => {
        btn.addEventListener("click", () => this.execute(btn.dataset.wfExecute));
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

  // v1.54 · 直接執行 · 主管家自動串接所有 Agent · 結果顯示在 modal
  async execute(presetId) {
    const r = await modal.prompt([
      {
        name: "input",
        label: "初始輸入",
        type: "textarea",
        rows: 5,
        required: true,
        placeholder: "貼入招標摘要 / 活動主題 / 新聞事實。執行後 AI 會串接多個專家自動跑完。",
      },
    ], {
      title: `🚀 直接執行 · ${presetId}`,
      icon: "⚡",
      primary: "確認執行 · 不再回頭",
      cancel: "先用草稿模式",
    });
    if (!r) return;

    const confirmed = await modal.confirm(
      `<div style="display:grid;gap:10px">
        <div>主管家會 <strong>自動呼叫多個專家 Agent</strong> 串接執行,完成前不會中斷。</div>
        <div style="color:var(--text-secondary);font-size:13px">
          · 每日上限 5 個 workflow(防失控)<br>
          · 全程紀錄在中控可查<br>
          · 涉及機敏資料 / 對外承諾,主管家會標「需人工確認」
        </div>
      </div>`,
      { title: "確認自動執行?", icon: "🚀", primary: "執行", cancel: "取消", danger: false }
    );
    if (!confirmed) return;

    // v1.64 #2 · DAG progress 視覺化 · 取代純 spinner · 顯示每 step 狀態
    const presetMeta = await this._fetchPresetMeta(presetId);
    const progress = this._renderDagProgress(presetId, presetMeta);
    document.body.appendChild(progress);
    // 進度動畫:每 4 秒提示「主管家正在派工 step N 的專家...」
    let elapsedSec = 0;
    const tick = setInterval(() => {
      elapsedSec += 1;
      const note = progress.querySelector(".dag-elapsed");
      if (note) note.textContent = `已 ${elapsedSec}s / 預估 30-90s`;
    }, 1000);

    try {
      const resp = await authFetch(`${BASE}/workflow/run-preset/${encodeURIComponent(presetId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_input: r.input }),
      });
      clearInterval(tick);
      clearInterval(tick); progress.remove();
      if (!resp.ok) {
        if (resp.status === 429) {
          const data = await resp.json().catch(() => ({}));
          toast.error(data.detail || "今日 workflow 用量已達上限");
          return;
        }
        if (resp.status === 403) {
          toast.error("workflow 執行已被管理員暫停");
          return;
        }
        throw new Error(`HTTP ${resp.status}`);
      }
      const result = await resp.json();
      await this.showExecutionResult(result, presetId);
    } catch (e) {
      clearInterval(tick); progress.remove();
      console.warn("[workflows] execute failed", e);
      toast.error("執行失敗 · 請稍後重試");
    }
  },

  // v1.64 #2 · 取 preset 的 step DAG metadata · 給視覺用
  async _fetchPresetMeta(presetId) {
    try {
      const r = await authFetch(`${BASE}/workflow/presets/${encodeURIComponent(presetId)}`);
      if (!r.ok) return { steps: [] };
      return await r.json();
    } catch { return { steps: [] }; }
  },

  // v1.64 #2 · DAG 流程圖 · 取代純 spinner
  // 顯示每 step 的 agent 與依賴關係 · 執行中可看哪步在跑
  _renderDagProgress(presetId, meta) {
    const overlay = document.createElement("div");
    overlay.className = "modal2-overlay dag-overlay";
    const steps = meta?.steps || [];
    const stepHtml = steps.map((s, i) => {
      const deps = (s.depends_on || []).map(d => d.replace("step_", "#")).join(", ") || "起點";
      const color = _colorFor(presetId);
      return `
        <div class="dag-step" data-dag-step="${s.id}"
             style="display:grid;grid-template-columns:32px 1fr;gap:10px;padding:10px;border-radius:10px;border:2px solid color-mix(in srgb, ${color} 20%, var(--border));background:color-mix(in srgb, ${color} 6%, var(--bg-content));margin:6px 0;transition:border-color 0.3s">
          <div class="dag-step-status" style="display:grid;place-items:center;font-size:18px">⏳</div>
          <div>
            <div style="font-weight:600;font-size:13px">Step ${i + 1} · ${escapeHtml(_agentNameFromId(s.agent_id))}</div>
            <div style="color:var(--text-secondary);font-size:12px;margin-top:2px">產出:${escapeHtml(s.expected_output || "?")} · 依賴:${deps}</div>
          </div>
        </div>`;
    }).join("");

    overlay.innerHTML = `
      <div style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--bg-content);padding:24px 28px;border-radius:14px;min-width:480px;max-width:90vw;max-height:80vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.2)">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
          <span style="font-size:24px">⚡</span>
          <div style="flex:1">
            <div style="font-weight:600">${escapeHtml(meta?.name || presetId)}</div>
            <div style="color:var(--text-secondary);font-size:12px;margin-top:2px">主管家正在串接 ${steps.length} 個專家... · <span class="dag-elapsed">已 0s / 預估 30-90s</span></div>
          </div>
        </div>
        <div class="dag-steps">${stepHtml}</div>
        <div style="margin-top:12px;color:var(--text-tertiary);font-size:11px;text-align:center">執行中無法取消 · 失敗會自動標紅 · 可從中控 resume</div>
      </div>`;
    return overlay;
  },

  async showExecutionResult(result, presetId) {
    const steps = (result.results || []).map((s, i) => `
      <div style="margin:10px 0;padding:10px;background:var(--bg-base);border-radius:8px;border-left:3px solid var(--accent)">
        <div style="font-weight:600;font-size:13px;color:var(--text-secondary)">Step ${i + 1} · Agent ${escapeHtml(s.agent_id)}</div>
        <div style="margin-top:6px;font-size:13px;line-height:1.6;white-space:pre-wrap">${escapeHtml(s.output_preview || "(無內容)")}</div>
      </div>
    `).join("");
    const quota = result.quota
      ? `<div style="color:var(--text-secondary);font-size:12px">今日已用 ${result.quota.used}/${result.quota.cap} 個</div>`
      : "";

    await modal.show({
      title: `✅ 已執行 · ${result.workflow}`,
      icon: "🎉",
      bodyHTML: `
        <div style="display:grid;gap:10px">
          <div>${result.steps_executed} 個步驟全部完成</div>
          ${quota}
          <div style="max-height:50vh;overflow-y:auto">${steps}</div>
        </div>`,
      cancel: "關閉",
      primary: "帶最終結果到主管家繼續",
      onSubmit: () => {
        chat.open("00", `工作流「${result.workflow}」已自動執行完畢,以下是最終整合結果,請協助我下一步:\n\n${result.final_output || ""}`);
        return true;
      },
    });
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

function _agentNameFromId(id) {
  const map = {
    "00": "✨ 主管家", "01": "🎯 投標顧問", "02": "🎪 活動規劃師",
    "03": "🎨 設計夥伴", "04": "📣 公關寫手", "05": "🎙️ 會議速記",
    "06": "📚 知識庫", "07": "💰 財務試算", "08": "⚖️ 合約法務",
    "09": "📊 結案營運",
  };
  return map[id] || id;
}

function _iconFor(id) {
  return id === "tender-full" ? "🎯" :
         id === "event-planning" ? "🎪" :
         id === "news-release" ? "📣" : "⚡";
}

function _colorFor(id) {
  return id === "tender-full" ? "#D14B43" :
         id === "event-planning" ? "#D8851E" :
         id === "news-release" ? "#5AB174" : "#8C5CB1";
}

function _deliverableFor(id) {
  return id === "tender-full" ? "承接評估、建議書大綱、報價風險" :
         id === "event-planning" ? "場景需求單、主視覺方向、預算分配" :
         id === "news-release" ? "新聞稿、媒體邀請電子郵件" : "多步驟交付草稿";
}

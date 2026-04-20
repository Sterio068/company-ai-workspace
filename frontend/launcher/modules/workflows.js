/**
 * Workflows view · Orchestrator 多 Agent 串接預設流程(v2.0)
 */
import { escapeHtml } from "./util.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting/orchestrator";

export const workflows = {
  async load() {
    const root = document.getElementById("workflows-grid");
    if (!root) return;
    try {
      const r = await fetch(`${BASE}/workflow/presets`);
      const list = await r.json();
      if (!list.length) { root.innerHTML = '<div class="chip-empty">無 workflow</div>'; return; }
      root.innerHTML = list.map(w => `
        <article class="workspace-card" style="--ws-color:#AF52DE;cursor:pointer"
                 data-workflow-id="${escapeHtml(w.id)}">
          <div class="ws-head">
            <div class="ws-icon">⚡</div>
            <div class="ws-name">${escapeHtml(w.name)}</div>
          </div>
          <div class="ws-desc">${escapeHtml(w.description)}</div>
          <div class="ws-meta">
            <span>🔗 ${w.step_count} 個步驟</span>
            <span>點擊執行</span>
          </div>
        </article>
      `).join("");
      root.querySelectorAll("[data-workflow-id]").forEach(card => {
        card.addEventListener("click", () => this.run(card.dataset.workflowId));
      });
    } catch {
      root.innerHTML = '<div class="chip-empty">❌ Orchestrator API 未就緒(需 httpx 安裝)</div>';
    }
  },

  async run(presetId) {
    const r = await modal.prompt([
      { name: "input", label: "初始輸入", type: "textarea", rows: 4, required: true,
        placeholder: "例:貼入招標 PDF 文字 / 活動主題說明 / 新聞事實" },
    ], { title: `執行 workflow · ${presetId}`, icon: "⚡", primary: "執行" });
    if (!r) return;
    modal.alert(
      "⚡ Workflow 執行需 LibreChat JWT + 複數 Agent 呼叫。<br>目前為 v2.0 實驗功能,請先從「✨ 主管家」對話試用,告訴它你要跑這個 workflow。",
      { title: "v2.0 實驗功能", icon: "🧪", primary: "回主管家" }
    );
  },
};

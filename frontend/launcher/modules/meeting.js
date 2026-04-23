/**
 * Meeting · Feature #1 會議速記自動化
 * ==========================================================
 * 流程:
 *   1. 選音檔(m4a/mp3/wav)
 *   2. 選 project(選配)
 *   3. 上傳 → /memory/transcribe · 回 meeting_id
 *   4. 每 3 秒 poll /memory/meetings/{id} 看 status
 *   5. status=done → 顯示結構化紀錄
 *   6. 一鍵「推到 Handoff」
 */
import { authFetch } from "./auth.js";
import { escapeHtml } from "./util.js";
import { toast } from "./toast.js";

const BASE = "/api-accounting";

export const meeting = {
  _currentId: null,
  _pollTimer: null,
  _meetings: [],

  async init() {
    await this.loadList();
    this.renderView();
  },

  async loadList() {
    try {
      const r = await authFetch(`${BASE}/memory/meetings?limit=30`);
      const body = await r.json();
      this._meetings = body.items || [];
    } catch (e) {
      this._meetings = [];
    }
  },

  renderView() {
    const root = document.getElementById("view-meeting-content");
    if (!root) return;
    root.innerHTML = `
      <div class="meeting-toolbar">
        <h2>🎤 會議速記</h2>
        <button class="btn-primary" id="meeting-upload-btn">+ 上傳音檔</button>
      </div>

      <p class="meeting-help">
        音檔(m4a/mp3/wav · ≤ 25MB)→ Whisper STT → Haiku 整理 → 自動填 Handoff<br>
        🔒 PDPA · 處理完音檔自動刪 · 只留逐字稿 + 結構化
      </p>

      <h3>📋 我的會議</h3>
      ${this._meetings.length === 0 ? `
        <p class="meeting-empty">沒會議 · 點上面「上傳音檔」開始</p>
      ` : `
        <div class="meeting-list">
          ${this._meetings.map(m => `
            <div class="meeting-item meeting-status-${m.status}" data-id="${m.meeting_id}">
              <div class="meeting-title">${escapeHtml(m.title)}</div>
              <div class="meeting-meta">
                <span>${this._statusBadge(m.status)}</span>
                ${m.action_items_count > 0 ? `<span>✓ ${m.action_items_count} 待辦</span>` : ""}
                ${m.project_id ? `<span>📁 ${escapeHtml(m.project_id.substring(0,8))}...</span>` : ""}
                <span class="meeting-time">${this._formatTime(m.created_at)}</span>
              </div>
            </div>
          `).join("")}
        </div>
      `}
    `;
    document.getElementById("meeting-upload-btn")?.addEventListener("click", () => this.openUpload());
    document.querySelectorAll("[data-id]").forEach(el => {
      el.addEventListener("click", () => this._openDetail(el.dataset.id));
    });
  },

  _statusBadge(s) {
    const m = {
      transcribing: "🎤 轉錄中",
      structuring: "🤖 整理中",
      done: "✅ 完成",
      failed: "❌ 失敗",
    };
    return m[s] || s;
  },

  _formatTime(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
  },

  async _openDetail(id) {
    try {
      const r = await authFetch(`${BASE}/memory/meetings/${id}`);
      if (!r.ok) {
        toast.error("讀取失敗");
        return;
      }
      const body = await r.json();
      this._currentId = id;
      this._showResult(body);
    } catch (e) {
      toast.error(`網路錯:${String(e)}`);
    }
  },

  async openUpload() {
    // 建 modal · 簡單版:上傳 + project 選
    const root = document.getElementById("modal-root") || document.body;
    const modal = document.createElement("div");
    modal.className = "modal2-overlay";
    modal.innerHTML = `
      <div class="modal2-box" style="max-width: 480px">
        <div class="modal2-header">🎤 會議速記 · 上傳音檔</div>
        <form id="meeting-upload-form" class="modal2-form">
          <label>音檔(m4a / mp3 / wav · ≤ 25MB)
            <input type="file" name="audio" accept="audio/*,video/mp4" required>
          </label>
          <label>專案 ID(選填 · 完成後可一鍵推到 Handoff)
            <input type="text" name="project_id" placeholder="留空也 OK">
          </label>
          <div style="font-size:12px; color: var(--text-tertiary); margin:8px 0">
            ⏱ 處理時間約 音檔長度 × 0.3(10 分鐘音檔 → 3 分鐘)<br>
            🔒 PDPA · 處理完音檔自動刪 · 只留逐字稿 + 結構化 JSON
          </div>
          <div class="modal2-actions">
            <button type="button" data-cancel>取消</button>
            <button type="submit" class="primary">開始 · Whisper + Haiku</button>
          </div>
        </form>
      </div>
    `;
    root.appendChild(modal);

    const form = modal.querySelector("form");
    modal.querySelector("[data-cancel]").addEventListener("click", () => modal.remove());
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const fd = new FormData(form);
      try {
        const r = await authFetch(`${BASE}/memory/transcribe`, {
          method: "POST",
          body: fd,
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          toast.error(`上傳失敗:${err.detail || r.status}`);
          return;
        }
        const body = await r.json();
        toast.success(`已上傳 ${body.size_mb}MB · 處理中...`);
        modal.remove();
        this._currentId = body.meeting_id;
        this._startPolling();
      } catch (e) {
        toast.error(`網路錯:${String(e)}`);
      }
    });
  },

  _startPolling() {
    if (this._pollTimer) clearInterval(this._pollTimer);
    let attempts = 0;
    this._pollTimer = setInterval(async () => {
      attempts++;
      if (attempts > 60) {  // 3 分鐘
        clearInterval(this._pollTimer);
        toast.error("超時 · 到「使用教學 → API Key」看 OpenAI 是否有效");
        return;
      }
      try {
        const r = await authFetch(`${BASE}/memory/meetings/${this._currentId}`);
        if (!r.ok) return;
        const body = await r.json();
        if (body.status === "done") {
          clearInterval(this._pollTimer);
          this._showResult(body);
        } else if (body.status === "failed") {
          clearInterval(this._pollTimer);
          toast.error(`處理失敗:${body.error || "未知錯"}`);
        }
      } catch {}
    }, 3000);
  },

  _showResult(body) {
    const s = body.structured || {};
    const root = document.getElementById("modal-root") || document.body;
    const modal = document.createElement("div");
    modal.className = "modal2-overlay";
    modal.innerHTML = `
      <div class="modal2-box" style="max-width:640px; max-height:80vh; overflow-y:auto">
        <div class="modal2-header">✅ 會議紀錄完成</div>
        <h3 style="margin:0 0 8px">${escapeHtml(s.title || "(未命名會議)")}</h3>
        ${s.attendees?.length ? `
          <p style="color:var(--text-secondary); font-size:13px">
            👥 與會:${s.attendees.map(escapeHtml).join(", ")}
          </p>
        ` : ""}

        ${s.decisions?.length ? `
          <h4>📌 決議</h4>
          <ul>${s.decisions.map(d => `<li>${escapeHtml(d)}</li>`).join("")}</ul>
        ` : ""}

        ${s.action_items?.length ? `
          <h4>✓ 待辦</h4>
          <ul>
            ${s.action_items.map(a => `
              <li>
                <b>${escapeHtml(a.who || "?")}</b> · ${escapeHtml(a.what || "")}
                ${a.due ? ` <span style="color:var(--red)">(期限 ${escapeHtml(a.due)})</span>` : ""}
              </li>
            `).join("")}
          </ul>
        ` : ""}

        ${s.key_numbers?.length ? `
          <h4>💰 關鍵數字</h4>
          <ul>${s.key_numbers.map(n => `<li><b>${escapeHtml(n.label)}</b>:${escapeHtml(n.value)}</li>`).join("")}</ul>
        ` : ""}

        ${s.next_meeting ? `
          <p><b>📅 下次會議:</b> ${escapeHtml(s.next_meeting)}</p>
        ` : ""}

        <details style="margin-top:16px">
          <summary style="cursor:pointer; color:var(--text-tertiary); font-size:12px">
            逐字稿 (${body.transcript_length} 字)
          </summary>
          <pre style="white-space:pre-wrap; font-size:11px; color:var(--text-secondary); max-height:200px; overflow-y:auto; background:var(--surface-2); padding:8px; border-radius:6px">${escapeHtml(body.transcript_preview)}</pre>
        </details>

        <div class="modal2-actions">
          <button type="button" data-close>關閉</button>
          ${body.project_id ? `<button type="button" class="primary" data-push>推到 Handoff</button>` : ""}
        </div>
      </div>
    `;
    root.appendChild(modal);
    modal.querySelector("[data-close]").addEventListener("click", () => modal.remove());
    modal.querySelector("[data-push]")?.addEventListener("click", async () => {
      try {
        const r = await authFetch(
          `${BASE}/memory/meetings/${this._currentId}/push-to-handoff`,
          { method: "POST" }
        );
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          toast.error(`推失敗:${err.detail || r.status}`);
          return;
        }
        const body = await r.json();
        toast.success(`已推 ${body.next_actions_count} 項待辦到 Handoff`);
        modal.remove();
      } catch (e) {
        toast.error(`網路錯:${String(e)}`);
      }
    });
  },
};

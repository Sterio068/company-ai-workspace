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
import { escapeHtml, skeletonCards } from "./util.js";
import { toast, networkError, operationError } from "./toast.js";

const BASE = "/api-accounting";

export const meeting = {
  _currentId: null,
  _pollTimer: null,
  _meetings: [],

  async init() {
    // v1.3 batch3 · 載入前顯 skeleton · 不讓 view 短暫空白
    const root = document.getElementById("view-meeting-content");
    if (root) root.innerHTML = `<div class="skeleton-list">${skeletonCards(3)}</div>`;
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
        音檔(m4a/mp3/wav · ≤ 25MB)→ 語音轉文字 → 快速模型整理 → 自動填交棒卡<br>
        🔒 PDPA · 處理完音檔自動刪 · 只留逐字稿 + 結構化
      </p>

      <h3>📋 我的會議</h3>
      ${this._meetings.length === 0 ? `
        <div class="empty-state">
          <div class="empty-state-icon">🎤</div>
          <div class="empty-state-title">尚無會議紀錄</div>
          <div class="empty-state-hint">點上方「+ 上傳音檔」開始</div>
        </div>
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
        operationError("讀取會議", `HTTP ${r.status}`, () => this._openDetail(id));
        return;
      }
      const body = await r.json();
      this._currentId = id;
      this._showResult(body);
    } catch (e) {
      networkError("讀取會議", e, () => this._openDetail(id));
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
          <label>專案 ID(選填 · 完成後可一鍵推到交棒卡)
            <input type="text" name="project_id" placeholder="留空也 OK">
          </label>
          <div style="font-size:12px; color: var(--text-tertiary); margin:8px 0">
            ⏱ 處理時間約 音檔長度 × 0.3(10 分鐘音檔 → 3 分鐘)<br>
            🔒 PDPA · 處理完音檔自動刪 · 只留逐字稿 + 結構化內容
          </div>
          <div class="modal2-actions">
            <button type="button" data-cancel>取消</button>
            <button type="submit" class="primary">開始 · 轉錄並整理</button>
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
      // UX 改善 · 鎖 submit 按鈕防 double-click + 顯示上傳進度
      const submitBtn = form.querySelector("button[type=submit]");
      const cancelBtn = form.querySelector("[data-cancel]");
      submitBtn.disabled = true;
      submitBtn.innerHTML = "⏳ 上傳中...";
      cancelBtn.disabled = true;
      try {
        const r = await authFetch(`${BASE}/memory/transcribe`, {
          method: "POST",
          body: fd,
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          operationError("上傳音檔", err);
          submitBtn.disabled = false;
          cancelBtn.disabled = false;
          submitBtn.innerHTML = "開始 · 轉錄並整理";
          return;
        }
        const body = await r.json();
        toast.success(`已上傳 ${body.size_mb}MB · STT 處理中(約 ${Math.ceil(body.size_mb * 6)}s)`);
        modal.remove();
        this._currentId = body.meeting_id;
        this._startPolling();
        // 主 view 顯示 in-progress banner
        this._showProcessingBanner(body.meeting_id);
      } catch (e) {
        networkError("上傳音檔", e);
        submitBtn.disabled = false;
        cancelBtn.disabled = false;
        submitBtn.innerHTML = "開始 · 轉錄並整理";
      }
    });
  },

  _showProcessingBanner(meetingId) {
    // UX 改善 · main view 上方加 banner · 不只 toast 一閃即失
    const root = document.getElementById("view-meeting-content");
    if (!root) return;
    let banner = document.getElementById("meeting-processing-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "meeting-processing-banner";
      banner.style.cssText = "padding:14px 18px; background:var(--surface-2); border:1px solid var(--accent); border-radius:var(--r-md); margin-bottom:16px; display:flex; align-items:center; gap:12px;";
      root.prepend(banner);
    }
    let elapsed = 0;
    banner.innerHTML = `<div class="loading-spinner" style="width:18px; height:18px; border:2px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:spin 0.8s linear infinite;"></div>
      <div style="flex:1">
        <div style="font-weight:600">🎤 處理中(meeting_id ${meetingId.slice(-6)})</div>
        <div id="meeting-banner-timer" style="font-size:12px; color:var(--text-secondary)">已 ${elapsed}s · 語音轉文字中 · 完成自動跳結果</div>
      </div>`;
    if (this._bannerTimer) clearInterval(this._bannerTimer);
    this._bannerTimer = setInterval(() => {
      elapsed += 1;
      const t = document.getElementById("meeting-banner-timer");
      if (t) t.textContent = `已 ${elapsed}s · 語音轉文字中 · 完成自動跳結果`;
    }, 1000);
  },

  _hideProcessingBanner() {
    const banner = document.getElementById("meeting-processing-banner");
    if (banner) banner.remove();
    if (this._bannerTimer) {
      clearInterval(this._bannerTimer);
      this._bannerTimer = null;
    }
  },

  _startPolling() {
    if (this._pollTimer) clearInterval(this._pollTimer);
    let attempts = 0;
    // v1.3 batch6 · stale closure 修 · 把 ID 局部存 · 防中途 _currentId 被新 upload 蓋掉
    const pollId = this._currentId;
    this._pollTimer = setInterval(async () => {
      attempts++;
      if (attempts > 60) {  // 3 分鐘
        clearInterval(this._pollTimer);
        this._hideProcessingBanner();
        toast.error("處理超時(3 分鐘)", {
          detail: "語音服務金鑰可能無效或過期",
          action: { label: "看設定", onClick: () => location.hash = "#help" },
        });
        return;
      }
      try {
        const r = await authFetch(`${BASE}/memory/meetings/${pollId}`);
        if (!r.ok) return;
        const body = await r.json();
        if (body.status === "done") {
          clearInterval(this._pollTimer);
          this._hideProcessingBanner();
          this._showResult(body);
        } else if (body.status === "failed") {
          clearInterval(this._pollTimer);
          this._hideProcessingBanner();
          toast.error("會議處理失敗", {
            detail: body.error || "未知錯誤",
            action: { label: "故障排除", onClick: () => location.hash = "#help" },
          });
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
          ${body.project_id ? `<button type="button" class="primary" data-push>推到交棒卡</button>` : ""}
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
          operationError("推到交棒卡", err);
          return;
        }
        const body = await r.json();
        toast.success(`已推 ${body.next_actions_count} 項待辦到交棒卡`);
        modal.remove();
      } catch (e) {
        networkError("推到交棒卡", e);
      }
    });
  },
};

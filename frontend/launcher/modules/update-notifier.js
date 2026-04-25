/**
 * 系統更新通知 · vNext C(2026-04-25)
 *
 * 流程:
 *   1. 載入後 · 立刻 GET /admin/update/status(只 admin 拉)
 *   2. 若 status.status === "available" → 顯示 sidebar 紅點 + 桌面 toast
 *   3. 點紅點 → 開更新 modal(顯示 commits + 確認按鈕)
 *   4. 確認 → POST /admin/update/run · 拿 task_id
 *   5. 每 3 秒 poll /admin/update/run/{task_id} · 顯示 log tail
 *   6. 完成 → 自動 reload(window.location.reload)
 *
 * 安全:
 *   - 只 admin 看得到通知(其他 role 直接 noop)
 *   - 每 4 小時最多檢查一次(localStorage timestamp)
 *   - 更新中前端 lock(防雙擊)
 */
import { authFetch } from "./auth.js";
import { toast } from "./toast.js";
import { escapeHtml } from "./util.js";

const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000;  // 4 hours
const POLL_INTERVAL_MS = 3000;
const STATE_KEY = "chengfu-update-last-checked-at";
const DISMISS_KEY = "chengfu-update-dismissed-sha";

let _polling = false;
let _modalOpen = false;

export const updateNotifier = {
  /** 入口 · admin 才呼叫(由 app.js 在 setupUser 後決定) */
  async init(isAdmin) {
    if (!isAdmin) return;
    this._injectBadge();
    // 不馬上跑 · 等 1.5 秒 · 不擋首屏
    setTimeout(() => this._checkIfDue(), 1500);
  },

  _injectBadge() {
    if (document.querySelector(".update-notifier-badge")) return;
    // 找 sidebar 「中控」(ops-nav)右邊放紅點 · 沒有就用 brand
    const target = document.getElementById("ops-nav")
                || document.querySelector(".sidebar-header");
    if (!target) return;
    const badge = document.createElement("button");
    badge.className = "update-notifier-badge";
    badge.type = "button";
    badge.title = "系統有新版可更新";
    badge.setAttribute("aria-label", "系統有新版可更新");
    badge.style.cssText = `
      display:none; position:absolute; right:8px; top:8px;
      width:8px; height:8px; border-radius:50%;
      background:#FF3B30; border:2px solid var(--bg-base, #fff);
      cursor:pointer; padding:0; z-index:10;
      box-shadow:0 0 0 0 rgba(255,59,48,0.4);
      animation: pulse-update 2s infinite;
    `;
    if (getComputedStyle(target).position === "static") {
      target.style.position = "relative";
    }
    badge.onclick = (e) => {
      e.stopPropagation();
      this._openModal();
    };
    target.appendChild(badge);

    // 加 keyframes(避免改 launcher.css)
    if (!document.getElementById("update-notifier-style")) {
      const style = document.createElement("style");
      style.id = "update-notifier-style";
      style.textContent = `
        @keyframes pulse-update {
          0% { box-shadow: 0 0 0 0 rgba(255,59,48,0.6); }
          70% { box-shadow: 0 0 0 8px rgba(255,59,48,0); }
          100% { box-shadow: 0 0 0 0 rgba(255,59,48,0); }
        }
      `;
      document.head.appendChild(style);
    }
  },

  _showBadge() {
    const badge = document.querySelector(".update-notifier-badge");
    if (badge) badge.style.display = "block";
  },
  _hideBadge() {
    const badge = document.querySelector(".update-notifier-badge");
    if (badge) badge.style.display = "none";
  },

  /** 4 小時內檢查過 · 跳過(避免 nuisance) */
  async _checkIfDue() {
    const last = parseInt(localStorage.getItem(STATE_KEY) || "0", 10);
    if (Date.now() - last < CHECK_INTERVAL_MS) return;
    await this.check({ silent: true });
  },

  /** 主動檢查 · silent=true 不彈 toast(只 badge) */
  async check({ silent = false } = {}) {
    try {
      const r = await authFetch("/api-accounting/admin/update/status");
      if (!r.ok) return;  // 不是 admin 或 API 還沒部署 · 靜默
      const data = await r.json();
      localStorage.setItem(STATE_KEY, String(Date.now()));
      this._lastStatus = data;

      const status = data.status?.status;
      if (status === "available") {
        const targetSha = data.status.latest;
        const dismissed = localStorage.getItem(DISMISS_KEY);
        // 同一版若已 dismiss · 不再彈 toast(badge 仍顯示)
        this._showBadge();
        if (!silent && dismissed !== targetSha) {
          toast.info(
            `🚀 系統有新版可更新(${data.status.commits_behind} 個 commit)· 點右上角紅點查看`,
            { duration: 6000 }
          );
        }
      } else {
        this._hideBadge();
      }
    } catch (e) {
      // 不是 admin 或網路 · 靜默
    }
  },

  /** 開更新 modal · 顯示 commit list + 確認按鈕 */
  async _openModal() {
    if (_modalOpen) return;
    _modalOpen = true;

    const data = this._lastStatus;
    const status = data?.status?.status;
    const latest = data?.status?.latest || "—";
    const current = data?.current_commit?.short || "—";
    const commits = data?.status?.commits || [];
    const commitsBehind = data?.status?.commits_behind || 0;
    const checkedAt = data?.status?.checked_at || "—";

    const overlay = document.createElement("div");
    overlay.className = "update-modal-overlay";
    overlay.style.cssText = `
      position:fixed; inset:0; background:rgba(0,0,0,0.5);
      z-index:9000; display:flex; align-items:center; justify-content:center;
      backdrop-filter:blur(4px);
    `;
    const box = document.createElement("div");
    box.className = "update-modal";
    box.style.cssText = `
      width:min(560px, 92vw); max-height:84vh; overflow:auto;
      background:var(--bg-content, #fff); color:var(--text, #111);
      border-radius:16px; padding:24px; box-shadow:0 24px 64px rgba(0,0,0,0.3);
      font-family:-apple-system, "Helvetica Neue", sans-serif;
    `;
    box.innerHTML = `
      <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px">
        <div style="font-size:32px">🚀</div>
        <div>
          <h2 style="margin:0; font-size:20px; line-height:1.2">系統更新</h2>
          <p style="margin:4px 0 0; color:var(--text-secondary,#666); font-size:13px">
            上次檢查:${escapeHtml(checkedAt)}
          </p>
        </div>
      </div>

      ${status === "available" ? `
        <div style="margin:20px 0; padding:14px; background:var(--bg-base,#f7f7f7); border-radius:10px">
          <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:14px">
            <div><b>目前:</b><code style="font-family:Menlo,monospace">${escapeHtml(current)}</code></div>
            <div><b>最新:</b><code style="font-family:Menlo,monospace">${escapeHtml(latest)}</code></div>
            <div><b>落後:</b>${commitsBehind} 個 commit</div>
          </div>
        </div>

        <div style="margin:16px 0">
          <h3 style="margin:0 0 8px; font-size:14px; color:var(--text-secondary,#666)">本次更新內容</h3>
          <ul style="margin:0; padding-left:20px; font-size:13px; line-height:1.7">
            ${commits.slice(0, 10).map(c => `<li>${escapeHtml(c)}</li>`).join("")}
          </ul>
          ${commitsBehind > 10 ? `<p style="margin:8px 0 0; color:var(--text-secondary,#666); font-size:12px">…還有 ${commitsBehind - 10} 個</p>` : ""}
        </div>

        <div style="margin:16px 0; padding:12px; background:#FFF8E1; border-left:4px solid #FFA000; border-radius:6px; font-size:13px; line-height:1.6">
          <b>⚠ 注意</b><br>
          • 預計需時 1-3 分鐘(rebuild + restart)<br>
          • 期間 Web UI 暫時無法使用<br>
          • 失敗會自動回滾到目前版本
        </div>

        <div id="update-task-progress" style="display:none; margin:16px 0">
          <div style="font-size:13px; color:var(--text-secondary,#666); margin-bottom:6px">更新進度</div>
          <pre id="update-task-log" style="margin:0; padding:10px; background:#1a1a1a; color:#7CB342; font-family:Menlo,monospace; font-size:11px; border-radius:6px; max-height:240px; overflow:auto; white-space:pre-wrap"></pre>
        </div>

        <div style="display:flex; gap:8px; justify-content:flex-end; margin-top:20px" id="update-modal-actions">
          <button id="update-dismiss" type="button" style="padding:10px 16px; border:1px solid var(--border,#ddd); background:transparent; border-radius:8px; cursor:pointer; color:var(--text-secondary,#666)">下次再說</button>
          <button id="update-run" type="button" style="padding:10px 18px; border:none; background:#007AFF; color:white; border-radius:8px; cursor:pointer; font-weight:600">立即更新</button>
        </div>
      ` : `
        <div style="margin:20px 0; padding:20px; text-align:center; background:var(--bg-base,#f7f7f7); border-radius:10px">
          <div style="font-size:36px; margin-bottom:8px">${status === "up_to_date" ? "✅" : "ℹ"}</div>
          <p style="margin:0; font-size:14px">${escapeHtml(data?.status?.message || "目前狀態未知")}</p>
        </div>
        <div style="display:flex; gap:8px; justify-content:flex-end; margin-top:20px">
          <button id="update-recheck" type="button" style="padding:10px 16px; border:1px solid var(--border,#ddd); background:transparent; border-radius:8px; cursor:pointer">立即檢查</button>
          <button id="update-close" type="button" style="padding:10px 18px; border:none; background:#007AFF; color:white; border-radius:8px; cursor:pointer">關閉</button>
        </div>
      `}
    `;

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    const close = () => {
      overlay.remove();
      _modalOpen = false;
    };
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay && !_polling) close();
    });

    // bind
    const dismissBtn = box.querySelector("#update-dismiss");
    const runBtn = box.querySelector("#update-run");
    const recheckBtn = box.querySelector("#update-recheck");
    const closeBtn = box.querySelector("#update-close");

    dismissBtn?.addEventListener("click", () => {
      const sha = data?.status?.latest;
      if (sha) localStorage.setItem(DISMISS_KEY, sha);
      close();
    });
    closeBtn?.addEventListener("click", close);
    recheckBtn?.addEventListener("click", async () => {
      recheckBtn.disabled = true;
      recheckBtn.textContent = "檢查中...";
      try {
        const r = await authFetch("/api-accounting/admin/update/check", { method: "POST" });
        if (r.ok) {
          this._lastStatus = await r.json();
          close();
          this._openModal();
        }
      } catch (e) {
        toast.error(`檢查失敗:${String(e)}`);
        recheckBtn.disabled = false;
        recheckBtn.textContent = "立即檢查";
      }
    });

    runBtn?.addEventListener("click", async () => {
      if (_polling) return;
      runBtn.disabled = true;
      dismissBtn.disabled = true;
      runBtn.textContent = "啟動中...";
      try {
        const r = await authFetch("/api-accounting/admin/update/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirm: true }),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${r.status}`);
        }
        const { task_id } = await r.json();
        runBtn.textContent = "更新中...";
        box.querySelector("#update-task-progress").style.display = "block";
        await this._pollTask(task_id, box);
      } catch (e) {
        toast.error(`更新失敗:${String(e.message || e)}`);
        runBtn.disabled = false;
        dismissBtn.disabled = false;
        runBtn.textContent = "立即更新";
      }
    });
  },

  async _pollTask(taskId, box) {
    _polling = true;
    const logEl = box.querySelector("#update-task-log");
    const startedAt = Date.now();

    while (_polling) {
      try {
        const r = await authFetch(`/api-accounting/admin/update/run/${taskId}`);
        if (!r.ok) {
          // 容器可能正在重啟 · 持續 retry
          await new Promise(res => setTimeout(res, POLL_INTERVAL_MS));
          continue;
        }
        const data = await r.json();
        if (logEl && data.log_tail) {
          logEl.textContent = data.log_tail;
          logEl.scrollTop = logEl.scrollHeight;
        }
        const status = data.meta?.status;
        if (status === "done") {
          toast.success("✅ 更新完成 · 即將重新載入頁面");
          _polling = false;
          setTimeout(() => window.location.reload(), 2500);
          return;
        }
        if (status === "failed" || status === "timeout" || status === "exception") {
          toast.error(`❌ 更新失敗:${data.meta?.message || status}`);
          _polling = false;
          // 顯示「重試」按鈕
          const actions = box.querySelector("#update-modal-actions");
          if (actions) {
            actions.innerHTML = `
              <button id="update-retry" type="button" style="padding:10px 16px; border:1px solid var(--border,#ddd); background:transparent; border-radius:8px; cursor:pointer">關閉</button>
            `;
            actions.querySelector("#update-retry").onclick = () => {
              box.parentElement?.remove();
              _modalOpen = false;
            };
          }
          return;
        }
      } catch (e) {
        // 容器斷線 · 等下次
      }
      // 安全保險 · 5 分鐘還沒完 · 自己 timeout
      if (Date.now() - startedAt > 5 * 60 * 1000) {
        toast.warn("⏱ 更新超過 5 分鐘 · 自行檢查 docker compose ps");
        _polling = false;
        return;
      }
      await new Promise(res => setTimeout(res, POLL_INTERVAL_MS));
    }
  },
};

// expose for ⌘K palette + manual trigger
window.updateNotifier = updateNotifier;

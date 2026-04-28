/**
 * Tenders view · g0v 政府採購網每日新標案監測
 */
import { escapeHtml, skeletonCards } from "./util.js";
import { authFetch } from "./auth.js";
import { toast, networkError, operationError } from "./toast.js";

const BASE = "/api-accounting/tender-alerts";

export const tenders = {
  filter: "all",
  _filterBound: false,
  _settingsBound: false,
  settings: null,

  async load() {
    await Promise.all([this.loadSettings(), this.refresh()]);
    this.bindFilter();  // 內部 guard · 只綁一次
    this.bindSettings();
  },

  bindFilter() {
    if (this._filterBound) return;
    this._filterBound = true;
    // Event delegation · 綁在父容器 · 避免元素重繪後 listener 丟失
    const parent = document.querySelector(".view-tenders .projects-filter");
    if (!parent) return;
    parent.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-tender-filter]");
      if (!btn) return;
      parent.querySelectorAll("[data-tender-filter]").forEach(x => x.classList.remove("active"));
      btn.classList.add("active");
      this.filter = btn.dataset.tenderFilter;
      await this.refresh();
    });
  },

  async loadSettings() {
    try {
      const r = await authFetch(`${BASE}/settings`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      this.settings = await r.json();
      this.renderSettings();
    } catch (e) {
      const root = document.getElementById("tenders-monitor-panel");
      if (root) root.innerHTML = `
        <div class="empty-state compact">
          <div class="empty-state-title">標案監測設定讀取失敗</div>
          <div class="empty-state-hint">${escapeHtml(e?.message || "請稍後重試")}</div>
        </div>`;
    }
  },

  renderSettings() {
    const root = document.getElementById("tenders-monitor-panel");
    if (!root) return;
    const s = this.settings || {};
    const last = s.last_run_summary;
    root.innerHTML = `
      <div class="tender-monitor-head">
        <div>
          <div class="tender-monitor-kicker">每日自動商機雷達</div>
          <h2>先設定「去哪裡找」,系統每天幫你掃新標案</h2>
        </div>
        <span class="status-pill ${s.enabled === false ? "warn" : "ok"}">
          ${s.enabled === false ? "已暫停" : `每日 ${String(s.daily_hour ?? 6).padStart(2, "0")}:00`}
        </span>
      </div>
      <form id="tender-monitor-form" class="tender-monitor-form">
        <label>關鍵字
          <input name="keywords" value="${escapeHtml((s.keywords || []).join(", "))}"
                 placeholder="活動, 行銷, 公關, 展覽">
        </label>
        <label>縣市
          <input name="counties" value="${escapeHtml((s.counties || []).join(", "))}"
                 placeholder="臺北市, 新北市, 桃園市">
        </label>
        <label>機關 / 部門
          <input name="units" value="${escapeHtml((s.units || []).join(", "))}"
                 placeholder="文化局, 觀光局, 環保局">
        </label>
        <label>排除字
          <input name="exclude_keywords" value="${escapeHtml((s.exclude_keywords || []).join(", "))}"
                 placeholder="工程, 土木, 採購硬體">
        </label>
        <label>每天幾點
          <input name="daily_hour" type="number" min="0" max="23" value="${Number(s.daily_hour ?? 6)}">
        </label>
        <label class="toggle-row">
          <input name="enabled" type="checkbox" ${s.enabled === false ? "" : "checked"}>
          <span>啟用每日自動抓取</span>
        </label>
        <label class="toggle-row">
          <input name="auto_import_interested" type="checkbox" ${s.auto_import_interested ? "checked" : ""}>
          <span>未來可自動匯入有興趣標案</span>
        </label>
        <div class="tender-monitor-actions">
          <button type="submit" class="btn-primary">儲存設定</button>
          <button type="button" class="btn-ghost" data-tender-run-now>立即抓一次</button>
        </div>
      </form>
      <div class="tender-monitor-summary">
        <span>範圍:${(s.counties || []).length ? escapeHtml(s.counties.join("、")) : "不限縣市"}</span>
        <span>機關:${(s.units || []).length ? escapeHtml(s.units.join("、")) : "不限機關"}</span>
        <span>上次:${s.last_run_at ? new Date(s.last_run_at).toLocaleString("zh-TW") : "尚未執行"}</span>
        ${last ? `<span>新發現 ${Number(last.new_count || 0)} 筆 / 掃描 ${Number(last.total_scanned || 0)} 筆</span>` : ""}
      </div>
    `;
  },

  bindSettings() {
    if (this._settingsBound) return;
    this._settingsBound = true;
    const root = document.getElementById("tenders-monitor-panel");
    if (!root) return;
    root.addEventListener("submit", async (e) => {
      if (e.target.id !== "tender-monitor-form") return;
      e.preventDefault();
      await this.saveSettings(e.target);
    });
    root.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-tender-run-now]");
      if (!btn) return;
      await this.runNow(btn);
    });
  },

  async saveSettings(form) {
    const fd = new FormData(form);
    const payload = {
      enabled: Boolean(fd.get("enabled")),
      keywords: splitList(fd.get("keywords")),
      counties: splitList(fd.get("counties")),
      units: splitList(fd.get("units")),
      exclude_keywords: splitList(fd.get("exclude_keywords")),
      daily_hour: Number(fd.get("daily_hour") || 6),
      auto_import_interested: Boolean(fd.get("auto_import_interested")),
    };
    try {
      const r = await authFetch(`${BASE}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("儲存標案監測設定", err);
        return;
      }
      this.settings = await r.json();
      this.renderSettings();
      toast.success("標案監測設定已更新");
    } catch (e) {
      networkError("儲存標案監測設定", e, () => this.saveSettings(form));
    }
  },

  async refresh() {
    const root = document.getElementById("tenders-list");
    if (!root) return;
    root.innerHTML = skeletonCards(3);
    const q = this.filter === "all" ? "" : `?status=${this.filter}`;
    try {
      const r = await authFetch(`${BASE}${q}`);
      // v1.3 batch6 · M-2 silent · 沒 r.ok 會把 500 error JSON 當空陣列 · 顯示「尚無標案」誤導
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const items = await r.json();
      const count = document.getElementById("tender-count");
      if (count) count.textContent = items.filter(i => i.status === "new").length;
      if (!items.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🎯</div>
            <div class="empty-state-title">尚無符合標案</div>
            <div class="empty-state-hint">每日 06:00 自動抓 · 或按上方「🔄 重新抓取」立即跑</div>
          </div>`;
        return;
      }
      // v4.6 · 分批 render(Round 6 reviewer 紅線:舊 Intel 機長列表掉幀)
      // 先 render 前 20 筆 · 剩下用 requestIdleCallback 補
      const FIRST_BATCH = 20;
      const renderItem = (t) => {
        const typeLabel = t.brief_type || "公告";
        const date = t.date ? String(t.date).slice(0, 8) : "";
        const scope = [t.county, t.department || t.unit_name].filter(Boolean).join(" · ");
        return `
          <div class="recent-item" data-tender-key="${escapeHtml(t.tender_key)}">
            <div class="recent-title">${escapeHtml(t.title)}</div>
            <span class="recent-agent">${escapeHtml(t.unit_name)} · ${typeLabel}</span>
            <div class="recent-time">${date} · ${escapeHtml(t.keyword)}${scope ? ` · ${escapeHtml(scope)}` : ""}</div>
            <div style="display:flex;gap:4px;margin-left:auto">
              <button class="btn-ghost" style="padding:2px 8px;font-size:11px"
                      data-tender-action="interested" data-tender-key="${escapeHtml(t.tender_key)}">✨</button>
              <button class="btn-ghost" style="padding:2px 8px;font-size:11px"
                      data-tender-action="skipped" data-tender-key="${escapeHtml(t.tender_key)}">🗑</button>
            </div>
          </div>
        `;
      };
      root.innerHTML = items.slice(0, FIRST_BATCH).map(renderItem).join("");
      if (items.length > FIRST_BATCH) {
        const ric = window.requestIdleCallback || ((cb) => setTimeout(cb, 16));
        ric(() => {
          const more = document.createElement("div");
          more.innerHTML = items.slice(FIRST_BATCH).map(renderItem).join("");
          while (more.firstChild) root.appendChild(more.firstChild);
        });
      }
      // event delegation 綁在 root · 後續分批 append 也能吃到
      if (!root.dataset.delegated) {
        root.dataset.delegated = "1";
        root.addEventListener("click", e => {
          const btn = e.target.closest("[data-tender-action]");
          if (!btn) return;
          e.stopPropagation();
          this.mark(btn.dataset.tenderKey, btn.dataset.tenderAction);
        });
      }
    } catch (e) {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">😓</div>
          <div class="empty-state-title">無法載入標案</div>
          <div class="empty-state-hint">${(e?.message || "政府電子採購網可能暫時連不上")}</div>
          <button class="btn-ghost" data-action="tenders.refresh" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  async mark(tenderKey, status) {
    await authFetch(`${BASE}/${encodeURIComponent(tenderKey)}?status=${status}`, { method: "PUT" });
    await this.refresh();
  },

  async runNow(button = null) {
    const btn = button || document.querySelector("[data-tender-run-now]");
    const old = btn?.textContent;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "抓取中…";
    }
    try {
      const r = await authFetch(`${BASE}/run-now`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        operationError("立即抓取標案", err);
        return;
      }
      const body = await r.json();
      toast.success(`標案抓取完成 · 新增 ${body.new_count} 筆`, {
        detail: `掃描 ${body.total_scanned} 筆 · ${body.errors?.length ? "部分關鍵字失敗" : "全部完成"}`,
      });
      await Promise.all([this.loadSettings(), this.refresh()]);
    } catch (e) {
      networkError("立即抓取標案", e, () => this.runNow(button));
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = old || "立即抓一次";
      }
    }
  },
};

function splitList(value) {
  return String(value || "")
    .split(/[,，\n]/)
    .map(v => v.trim())
    .filter(Boolean);
}

/**
 * Admin Dashboard · 成本 / 品質 / 用量總覽
 */
import { escapeHtml, copyToClipboard } from "./util.js";
import { authFetch } from "./auth.js";

const BASE = "/api-accounting";

export const admin = {
  async load() { await this.refresh(); },

  async refresh() {
    await Promise.all([
      this.loadDashboard(),
      this.loadAgentStats(),
      this.loadCost(),
      this.loadAccessUrls(),
      this.loadStorageStats(),
    ]);
  },

  /**
   * 同仁連線網址(LAN / mDNS / tunnel)+ 老闆指引
   * - 從 backend GET /admin/access-urls 拉
   * - render 進 #access-urls-content + bind delegated click(複製 + help-anchor)
   * - 失敗顯示 retry empty state · 不 throw(避免阻擋 admin dashboard 其他 block)
   * @returns {Promise<void>}
   */
  async loadAccessUrls() {
    const root = document.getElementById("access-urls-content");
    if (!root) return;
    try {
      const r = await authFetch(`${BASE}/admin/access-urls`);
      if (!r.ok) throw new Error(r.statusText);
      const d = await r.json();
      root.innerHTML = renderAccessUrls(d);
      _bindAccessUrlActions(root);
    } catch {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔌</div>
          <div class="empty-state-title">無法載入連線資訊</div>
          <div class="empty-state-hint">確認後端服務已啟動</div>
          <button class="btn-ghost" data-act="retry-access-urls" style="margin-top:12px">重試</button>
        </div>`;
      root.querySelector('[data-act="retry-access-urls"]')?.addEventListener("click", () => this.loadAccessUrls());
    }
  },

  async loadDashboard() {
    try {
      const r = await authFetch(`${BASE}/admin/dashboard`);
      if (!r.ok) throw new Error(r.statusText);
      const d = await r.json();
      setText("admin-income",          (d.accounting.month_income  / 10000).toFixed(1) + "萬");
      setText("admin-expense",         (d.accounting.month_expense / 10000).toFixed(1) + "萬");
      setText("admin-net",             (d.accounting.month_net     / 10000).toFixed(1) + "萬");
      setText("admin-projects",        d.projects.active);
      setText("admin-satisfaction",    d.feedback.satisfaction_rate + "%");
      setText("admin-feedback-total",  d.feedback.total);
      setText("admin-convos",          d.conversations.this_month);
      setText("admin-convos-total",    d.conversations.total);
    } catch {
      ["admin-income", "admin-expense", "admin-net", "admin-projects",
       "admin-satisfaction", "admin-feedback-total", "admin-convos", "admin-convos-total"]
       .forEach(id => setText(id, "⚠"));
    }
  },

  async loadAgentStats() {
    const root = document.getElementById("admin-agent-stats");
    if (!root) return;
    try {
      const r = await authFetch(`${BASE}/feedback/stats`);
      const stats = await r.json();
      if (!stats.length) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">👍</div>
            <div class="empty-state-title">尚無回饋資料</div>
            <div class="empty-state-hint">同仁在對話按 👍 👎 累積一段時間後才會有統計</div>
          </div>`;
        return;
      }
      stats.sort((a, b) => b.score - a.score);
      root.innerHTML = stats.map(s => {
        const color = s.score >= 80 ? "#5AB174" : s.score >= 60 ? "#D8851E" : "#D14B43";
        return `
          <div class="recent-item">
            <div class="recent-title">${escapeHtml(s.agent)}</div>
            <span class="recent-agent">👍 ${s.up} · 👎 ${s.down}</span>
            <div class="recent-time" style="color:${color}">${s.score}% 滿意</div>
          </div>
        `;
      }).join("");
    } catch {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔌</div>
          <div class="empty-state-title">無法連線介接服務</div>
          <div class="empty-state-hint">檢查 <code>docker compose ps</code> 會計服務是否啟動</div>
          <button class="btn-ghost" data-act="retry-agent-stats" style="margin-top:12px">重試</button>
        </div>`;
      root.querySelector('[data-act="retry-agent-stats"]')?.addEventListener("click", () => this.loadAgentStats());
    }
  },

  async loadCost() {
    const root = document.getElementById("admin-cost-stats");
    if (!root) return;
    try {
      const r = await authFetch(`${BASE}/admin/cost?days=30`);
      const d = await r.json();
      if (d.error || !d.by_model) {
        root.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <div class="empty-state-title">尚無成本資料</div>
          <div class="empty-state-hint">對話交易紀錄尚未累積 · 有對話後才有統計</div>
          </div>`;
        return;
      }
      root.innerHTML = d.by_model.map(m => `
        <div class="recent-item">
          <div class="recent-title">${escapeHtml(m._id || "unknown")}</div>
          <span class="recent-agent">${(m.input_tokens || 0).toLocaleString()} 輸入 / ${(m.output_tokens || 0).toLocaleString()} 輸出</span>
          <div class="recent-time">${m.count} 次呼叫</div>
        </div>
      `).join("");
    } catch {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔌</div>
          <div class="empty-state-title">無法載入成本</div>
          <div class="empty-state-hint">檢查會計服務是否啟動</div>
          <button class="btn-ghost" data-act="retry-cost" style="margin-top:12px">重試</button>
        </div>`;
      root.querySelector('[data-act="retry-cost"]')?.addEventListener("click", () => this.loadCost());
    }
  },

  async loadStorageStats() {
    const root = document.getElementById("admin-storage-stats");
    if (!root) return;
    try {
      const r = await authFetch(`${BASE}/admin/storage-stats`);
      if (!r.ok) throw new Error(r.statusText);
      const d = await r.json();
      root.innerHTML = renderStorageStats(d);
    } catch {
      root.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🗄️</div>
          <div class="empty-state-title">無法載入資料庫狀態</div>
          <div class="empty-state-hint">維運指標不影響一般功能,請稍後重試</div>
          <button class="btn-ghost" data-act="retry-storage" style="margin-top:12px">重試</button>
        </div>`;
      root.querySelector('[data-act="retry-storage"]')?.addEventListener("click", () => this.loadStorageStats());
    }
  },
};

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function renderStorageStats(d) {
  const items = Array.isArray(d.items) ? d.items : [];
  if (!items.length) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">🗄️</div>
        <div class="empty-state-title">尚無資料庫統計</div>
        <div class="empty-state-hint">系統開始使用後會自動累積 collection 狀態</div>
      </div>`;
  }
  const totalDocs = Number(d.totals?.documents || 0).toLocaleString();
  const totalStorage = formatBytes(d.totals?.storage_bytes || d.totals?.size_bytes || 0);
  const alertCount = Number(d.totals?.alerts || 0);
  const topItems = items.slice(0, 8);
  return `
    <div class="storage-summary">
      <div><strong>${totalDocs}</strong><span>文件</span></div>
      <div><strong>${totalStorage}</strong><span>儲存</span></div>
      <div data-alert="${alertCount ? "1" : "0"}"><strong>${alertCount}</strong><span>警示</span></div>
    </div>
    ${topItems.map(renderStorageRow).join("")}
  `;
}

function renderStorageRow(item) {
  const level = item.alert_level || "ok";
  const reason = item.alert_reason || (item.stats_available ? "狀態正常" : "僅回傳文件/索引數,storage 需 Mongo 權限");
  return `
    <div class="recent-item storage-row" data-storage-level="${escapeHtml(level)}">
      <div class="recent-title">${escapeHtml(item.collection || "unknown")}</div>
      <span class="recent-agent">${Number(item.count || 0).toLocaleString()} 筆</span>
      <span class="recent-agent">${Number(item.index_count || 0)} 索引</span>
      <div class="recent-time">${formatBytes(item.storage_bytes || item.size_bytes || 0)}</div>
      <div class="storage-reason">${escapeHtml(reason)}</div>
    </div>
  `;
}

function formatBytes(bytes) {
  const n = Number(bytes || 0);
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

/**
 * 同仁連線網址 · render 卡片清單 + 複製按鈕 + 帳號取得指引
 * @param {{
 *   current_origin: string|null,
 *   lan_urls: string[],
 *   mdns_url: string|null,
 *   tunnel_urls: string[],
 *   guidance: { account_source: string, first_login: string, remote_status: string }
 * }} d
 * @returns {string} HTML
 */
function renderAccessUrls(d) {
  const rows = [];
  if (Array.isArray(d.tunnel_urls) && d.tunnel_urls.length) {
    d.tunnel_urls.forEach(url => rows.push(urlRow({
      label: "遠端 (在家 / 出差)",
      url,
      kind: "tunnel",
      hint: "Cloudflare Tunnel · 加密 + 2FA",
    })));
  }
  if (d.mdns_url) {
    rows.push(urlRow({
      label: "辦公室 (mDNS)",
      url: d.mdns_url,
      kind: "mdns",
      hint: "同網段 macOS / iPhone 自動解析",
    }));
  }
  (d.lan_urls || []).forEach((url, i) => rows.push(urlRow({
    label: i === 0 ? "辦公室 LAN" : `辦公室 LAN (備網段 ${i})`,
    url,
    kind: "lan",
    hint: "公司 Wi-Fi / 有線同網段",
  })));
  if (!rows.length) {
    // D1 · 強引導 empty state · 給非技術 admin 明確下一步
    rows.push(`
      <div class="access-url-empty">
        <div class="access-url-empty-icon" aria-hidden="true">📡</div>
        <div class="access-url-empty-body">
          <div class="access-url-empty-title">尚未偵測到網路資訊</div>
          <ol class="access-url-empty-steps">
            <li>確認 Mac mini 已開機並連到公司 Wi-Fi / 有線網路</li>
            <li>在 Mac mini 終端機執行 <code>./scripts/start.sh</code> 重啟</li>
            <li>仍無法 → 看 <a href="#help" data-help-anchor="help-doc-troubleshooting-v1.3">🔧 故障排除</a></li>
          </ol>
        </div>
      </div>`);
  }

  const g = d.guidance || {};
  const remoteState = (d.tunnel_urls || []).length ? "ok" : "pending";

  return `
    ${d.current_origin ? `
      <div class="access-url-current">
        目前你正在用 <strong>${escapeHtml(d.current_origin)}</strong>
      </div>
    ` : ""}
    <div class="access-url-list">${rows.join("")}</div>
    <details class="access-url-guidance">
      <summary>
        <span class="access-url-guide-summary-icon">ℹ️</span>
        <span>帳號取得 · 遠端連線 · 完整教學</span>
        <span class="access-url-guide-summary-state" data-state="${remoteState}">${remoteState === "ok" ? "遠端已啟用" : "遠端待設定"}</span>
      </summary>
      <div class="access-url-guide-row">
        <span class="access-url-guide-icon">🔑</span>
        <div>
          <strong>${escapeHtml(g.account_source || "帳號 / 密碼由老闆統一設置")}</strong>
          <div class="access-url-guide-sub">${escapeHtml(g.first_login || "首次登入後請改密碼")}</div>
        </div>
      </div>
      <div class="access-url-guide-row" data-state="${remoteState}">
        <span class="access-url-guide-icon">🌐</span>
        <div>
          <strong>遠端連線</strong>
          <div class="access-url-guide-sub">${escapeHtml(g.remote_status || "")}</div>
        </div>
      </div>
      <div class="access-url-guide-row">
        <span class="access-url-guide-icon">📖</span>
        <div>
          <strong>完整教學</strong>
          <div class="access-url-guide-sub">
            <a href="#help" data-help-anchor="help-doc-remote-access">🌐 同仁連線方式(內網 + 遠端)</a>
            ·
            <a href="#help" data-help-anchor="help-doc-account-management">📇 同仁帳號管理</a>
          </div>
        </div>
      </div>
    </details>
  `;
}

/**
 * URL protocol allowlist · escapeHtml 只擋 HTML attribute 跳脫,不擋 javascript:/data:/file: scheme
 * 這層用 URL parser 強制 http/https 才放進 href · 杜絕未來來源擴充被利用做 XSS / phishing
 * @param {string} url
 * @returns {string} 安全 URL 或空字串
 */
function _safeHttpUrl(url) {
  try {
    const u = new URL(String(url));
    if (u.protocol === "http:" || u.protocol === "https:") return u.href;
  } catch { /* invalid URL */ }
  return "";
}

/**
 * @param {{ label: string, url: string, kind: string, hint: string }} args
 * @returns {string} HTML for one access url row
 */
function urlRow({ label, url, kind, hint }) {
  // 雙層防護:1) URL parser 限 http/https  2) escapeHtml 防 attribute 跳脫
  const sanitized = _safeHttpUrl(url);
  if (!sanitized) {
    // 不合法 URL · 顯示 row 但停用按鈕(避免畫面缺漏 admin 不知為何)
    return `
      <div class="access-url-row" data-kind="${kind}" data-invalid="1">
        <div class="access-url-meta">
          <span class="access-url-label">${escapeHtml(label)}</span>
          <code class="access-url-link">${escapeHtml(url)}</code>
          <span class="access-url-hint">⚠ URL 不合法 · 已禁用</span>
        </div>
      </div>
    `;
  }
  const safeUrl = escapeHtml(sanitized);
  // D2 · URL 連結加 external icon · 明示「會開新分頁」· 同時提升 affordance
  return `
    <div class="access-url-row" data-kind="${kind}">
      <div class="access-url-meta">
        <span class="access-url-label">${escapeHtml(label)}</span>
        <a class="access-url-link" href="${safeUrl}" target="_blank" rel="noopener">
          <span class="access-url-link-text">${safeUrl}</span>
          <svg class="access-url-link-ext" aria-hidden="true" focusable="false" width="11" height="11" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
        <span class="access-url-hint">${escapeHtml(hint)}</span>
      </div>
      <div class="access-url-actions">
        <button type="button" class="btn-ghost" data-copy-url="${safeUrl}" aria-label="複製 ${escapeHtml(label)} 網址">複製</button>
        <a class="btn-ghost" href="${safeUrl}" target="_blank" rel="noopener" aria-label="新分頁開啟 ${escapeHtml(label)}">開啟</a>
      </div>
    </div>
  `;
}

/** delegated click · 集中綁 access-urls block 所有 button:
 *  - [data-copy-url] 複製 URL
 *  - [data-help-anchor] 跳到 help view 對應 section */
function _bindAccessUrlActions(root) {
  if (!root || root._bound) return;
  root._bound = true;
  root.addEventListener("click", e => {
    const copyBtn = e.target.closest("[data-copy-url]");
    if (copyBtn) {
      copyToClipboard(copyBtn.dataset.copyUrl, copyBtn);
      return;
    }
    const helpLink = e.target.closest("[data-help-anchor]");
    if (helpLink) {
      e.preventDefault();
      window.app?.showView?.("help");
      const anchor = helpLink.dataset.helpAnchor;
      setTimeout(() => {
        document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 300);
    }
  });
}

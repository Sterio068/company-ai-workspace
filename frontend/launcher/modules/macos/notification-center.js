/**
 * macOS Notification Center · v1.4 Sprint C Phase 5
 * =====================================
 * 右滑出面板 · 包含原 inspector 內容(本月用量 / 系統狀態 / 提示)
 *
 * 觸發:
 *   - 點 menubar 右上 🔔 通知 icon
 *   - 鍵盤 ⌃⌘N
 *
 * 行為:
 *   - 從右側滑入(macOS Sequoia 風)
 *   - 點外面 / Esc 關
 *   - 內容:今日用量 widget · 系統狀態 widget · 自助更新通知 · 教學提示
 *
 * 結構:
 *   <aside class="notification-center">
 *     <div class="nc-header">通知中心</div>
 *     <div class="nc-widgets">
 *       <section class="nc-widget"> 本月用量 </section>
 *       <section class="nc-widget"> 系統狀態 </section>
 *       <section class="nc-widget"> 自助升級 </section>
 *       ...
 *     </div>
 *   </aside>
 */
import { authFetch } from "../auth.js";
import { slideUp } from "./motion.js";

let _ncEl = null;
let _isOpen = false;
let _cssLoaded = false;

// v1.20 perf · lazy load NC CSS · 沒打開 NC 的 user 不付 ~6KB CSS 解析成本
function _ensureCss() {
  if (_cssLoaded || document.querySelector('link[data-lazy-css="nc"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "/static/styles/notification-center.css?v=2";
  link.dataset.lazyCss = "nc";
  document.head.appendChild(link);
  _cssLoaded = true;
}

function _ensureNC() {
  _ensureCss();  // v1.20 · 第一次 open 才注入 CSS
  if (_ncEl) return _ncEl;
  _ncEl = document.createElement("aside");
  _ncEl.className = "notification-center";
  _ncEl.setAttribute("aria-label", "通知中心");
  _ncEl.setAttribute("role", "complementary");
  _ncEl.innerHTML = `
    <div class="nc-header">
      <h2 class="nc-title">通知中心</h2>
      <button class="nc-close" type="button" aria-label="關閉" title="關閉(Esc)">×</button>
    </div>
    <div class="nc-widgets" id="nc-widgets-container">
      <div class="nc-widget skeleton">載入中...</div>
    </div>
  `;
  document.body.appendChild(_ncEl);

  _ncEl.querySelector(".nc-close").addEventListener("click", () => close());
  return _ncEl;
}

// v1.50 · 30s 內重開 NC 不再重 fetch · 避免每次點 NC 都打 3 個 health endpoint
const _CACHE_TTL_MS = 30_000;
let _cachedAt = 0;
let _cached = null;
async function _renderWidgets() {
  const container = _ncEl?.querySelector("#nc-widgets-container");
  if (!container) return;

  const now = Date.now();
  let usage, health, update;
  if (_cached && now - _cachedAt < _CACHE_TTL_MS) {
    ({ usage, health, update } = _cached);
  } else {
    [usage, health, update] = await Promise.all([
      _fetchUsage(),
      _fetchHealth(),
      _fetchUpdateStatus(),
    ]);
    _cached = { usage, health, update };
    _cachedAt = now;
  }

  container.innerHTML = `
    ${_renderUsageWidget(usage)}
    ${_renderHealthWidget(health)}
    ${_renderUpdateWidget(update)}
    ${_renderTipsWidget()}
  `;

  // bind dismiss buttons
  container.querySelectorAll("[data-nc-action]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const action = btn.dataset.ncAction;
      _handleAction(action);
    });
  });
}

// ============================================================
// Widgets · 4 個
// ============================================================
async function _fetchUsage() {
  try {
    const r = await authFetch("/api-accounting/admin/cost/today");
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function _renderUsageWidget(data) {
  if (!data) {
    return `<section class="nc-widget"><div class="nc-w-title">本月用量</div><div class="nc-w-empty">無法讀取(可能非 admin)</div></section>`;
  }
  const today = data.today_usd ?? 0;
  const month = data.month_usd ?? 0;
  const budget = data.budget_usd ?? null;
  const pct = budget ? Math.min(100, (month / budget) * 100) : 0;
  const overBudget = pct > 80;

  return `
    <section class="nc-widget nc-w-usage">
      <div class="nc-w-title">本月用量</div>
      <div class="nc-w-row big">
        <span class="nc-w-amt">$${month.toFixed(2)}</span>
        ${budget ? `<span class="nc-w-max">/ $${budget.toFixed(0)}</span>` : ""}
      </div>
      ${budget ? `
      <div class="nc-w-bar">
        <div class="nc-w-bar-fill ${overBudget ? "danger" : ""}" style="width:${pct}%"></div>
      </div>
      ` : ""}
      <div class="nc-w-meta">
        <span>今日 $${today.toFixed(2)}</span>
        ${budget ? `<span class="${overBudget ? "danger" : ""}">${pct.toFixed(0)}%</span>` : ""}
      </div>
    </section>
  `;
}

async function _fetchHealth() {
  try {
    // 6 容器 health 掃描 · 簡單版
    const services = [
      { name: "nginx", url: "/healthz" },
      { name: "librechat", url: "/chat/api/config" },
      { name: "accounting", url: "/api-accounting/healthz" },
    ];
    const results = await Promise.all(services.map(async s => {
      try {
        const r = await fetch(s.url, { method: "GET" });
        return { ...s, ok: r.ok, status: r.status };
      } catch {
        return { ...s, ok: false, status: 0 };
      }
    }));
    return results;
  } catch { return []; }
}

function _renderHealthWidget(services) {
  if (!services.length) return "";
  const allOk = services.every(s => s.ok);
  return `
    <section class="nc-widget nc-w-health">
      <div class="nc-w-title">系統狀態</div>
      <div class="nc-w-row">
        <span class="nc-health-dot ${allOk ? "ok" : "warn"}"></span>
        <span class="nc-w-text">${allOk ? "所有服務正常" : "部分服務異常"}</span>
      </div>
      <div class="nc-w-services">
        ${services.map(s => `
          <div class="nc-service">
            <span class="nc-health-dot small ${s.ok ? "ok" : "warn"}"></span>
            <span>${s.name}</span>
            <span class="nc-status-code">${s.status || "✗"}</span>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

async function _fetchUpdateStatus() {
  try {
    const r = await authFetch("/api-accounting/admin/update/status");
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function _renderUpdateWidget(data) {
  if (!data) return "";
  const status = data.status?.status;
  if (status === "available") {
    const cb = data.status.commits_behind || 0;
    return `
      <section class="nc-widget nc-w-update interactive">
        <div class="nc-w-title">🚀 系統有新版</div>
        <div class="nc-w-row">
          <span>落後 ${cb} 個 commit</span>
        </div>
        <button class="nc-w-action" data-nc-action="open-update">立即更新</button>
      </section>
    `;
  } else if (status === "up_to_date") {
    return `
      <section class="nc-widget nc-w-update muted">
        <div class="nc-w-title">系統版本</div>
        <div class="nc-w-row">
          <span class="nc-w-text">已是最新版</span>
          <span class="nc-w-tag">${data.current_commit?.short || ""}</span>
        </div>
      </section>
    `;
  }
  return "";
}

function _renderTipsWidget() {
  // 簡單 tips · 隨機選一個
  const tips = [
    "💡 按 ⌘K 全域搜功能",
    "💡 對話文末按 👍/👎 · 月報會分析滿意度",
    "💡 按 ⌘1-5 快速切工作區",
    "💡 拖檔到 launcher 直接上傳",
    "💡 sidebar「使用教學」5 分鐘任務式",
    "💡 dock icon 右鍵可從 Dock 移除",
  ];
  const tip = tips[Math.floor(Math.random() * tips.length)];
  return `
    <section class="nc-widget nc-w-tip muted">
      <div class="nc-w-title">小提示</div>
      <div class="nc-w-text">${tip}</div>
    </section>
  `;
}

function _handleAction(action) {
  if (action === "open-update") {
    close();
    // 觸發既有自助更新 modal
    if (window.updateNotifier?._openModal) {
      window.updateNotifier._openModal();
    } else {
      window.app?.showView?.("admin");
    }
  }
}

// ============================================================
// Open / Close
// ============================================================
function _onDocClick(e) {
  if (_ncEl && !_ncEl.contains(e.target) && !e.target.closest(".menubar-status-item.notif")) {
    close();
  }
}
function _onDocKey(e) {
  if (e.key === "Escape" && _isOpen) close();
}

export function open() {
  _ensureNC();
  if (_isOpen) return;
  _isOpen = true;
  _ncEl.classList.add("open");
  _renderWidgets();  // re-fetch every open
  setTimeout(() => {
    document.addEventListener("click", _onDocClick);
    document.addEventListener("keydown", _onDocKey);
  }, 0);
}

export function close() {
  if (!_isOpen || !_ncEl) return;
  _isOpen = false;
  _ncEl.classList.remove("open");
  document.removeEventListener("click", _onDocClick);
  document.removeEventListener("keydown", _onDocKey);
}

export function toggle() {
  if (_isOpen) close();
  else open();
}

// 全域鍵盤 ⌃⌘N · open NC
document.addEventListener("keydown", (e) => {
  if (e.metaKey && e.ctrlKey && e.key.toLowerCase() === "n") {
    e.preventDefault();
    toggle();
  }
});

// expose for menubar bell click
if (typeof window !== "undefined") {
  window.notificationCenter = { open, close, toggle };
}

/**
 * macOS Control Center · v1.4 Sprint C Phase 5b
 * =====================================
 * 點 menubar 「模型」status item 旁邊 → 從右上滑出快速設定面板
 * (NC 在右上角往下滑 · CC 在右上角往左下滑 · macOS Sequoia 雙面板)
 *
 * 內容:
 *   - 模型切換(OpenAI / Claude · 大按鈕)
 *   - 主題(自動 / 淺 / 深)
 *   - 全螢幕 toggle
 *   - 快速動作:新對話 / 知識庫 / 重看教學
 *   - 系統:檢查更新 / 登出
 *
 * 觸發:
 *   - 點 menubar 模型 status item(原本 click 切換 · 改 open CC)
 *   - 鍵盤 ⌃⌘C
 */
import { authFetch } from "../auth.js";
import { setTheme as _sharedSetTheme, toggleFullscreen as _sharedToggleFullscreen } from "./actions.js";

let _ccEl = null;
let _isOpen = false;
let _cssLoaded = false;

// v1.20 perf · lazy load CC CSS · 沒打開 CC 的 user 不付 ~7KB CSS 解析成本
function _ensureCss() {
  if (_cssLoaded || document.querySelector('link[data-lazy-css="cc"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "/static/styles/control-center.css?v=1";
  link.dataset.lazyCss = "cc";
  document.head.appendChild(link);
  _cssLoaded = true;
}

const ENGINES = [
  { id: "openai", label: "OpenAI", desc: "GPT-4 · 創意 / 廣度", color: "#10a37f" },
  { id: "anthropic", label: "Claude", desc: "Sonnet · 深度 / 中文細", color: "#cc785c" },
];

const THEMES = [
  { id: "auto", label: "自動", icon: "◐" },
  { id: "light", label: "淺", icon: "☀" },
  { id: "dark", label: "深", icon: "☾" },
];

function _ensureCC() {
  _ensureCss();  // v1.20 · 第一次 open 才注入 CSS
  if (_ccEl) return _ccEl;
  _ccEl = document.createElement("aside");
  _ccEl.className = "control-center";
  _ccEl.setAttribute("aria-label", "控制中心");
  _ccEl.setAttribute("role", "complementary");
  _ccEl.innerHTML = `
    <div class="cc-header">
      <h2 class="cc-title">控制中心</h2>
      <button class="cc-close" type="button" aria-label="關閉" title="關閉(Esc)">×</button>
    </div>
    <div class="cc-tiles" id="cc-tiles"></div>
  `;
  document.body.appendChild(_ccEl);
  _ccEl.querySelector(".cc-close").addEventListener("click", () => close());
  return _ccEl;
}

function _render() {
  const container = _ccEl?.querySelector("#cc-tiles");
  if (!container) return;
  // v1.11 · 改讀 central store · 與 app.js / launcher 共用同 key
  const curEngine = (window.chengfuStore?.get("engine"))
    || localStorage.getItem("chengfu-ai-provider")
    || localStorage.getItem("chengfu-engine")  // legacy fallback
    || "openai";
  const curTheme = localStorage.getItem("chengfu-theme") || "auto";
  const isFs = !!document.fullscreenElement;

  container.innerHTML = `
    <!-- 模型切換 · 大塊 -->
    <section class="cc-tile cc-tile-engine">
      <div class="cc-tile-title">AI 引擎</div>
      <div class="cc-engine-grid">
        ${ENGINES.map(eng => `
          <button class="cc-engine-btn ${curEngine === eng.id ? "active" : ""}"
                  type="button" data-engine="${eng.id}">
            <div class="cc-engine-mark" style="background:${eng.color}">
              ${eng.id === "openai" ? "◯" : "C"}
            </div>
            <div class="cc-engine-label">${eng.label}</div>
            <div class="cc-engine-desc">${eng.desc}</div>
          </button>
        `).join("")}
      </div>
    </section>

    <!-- 主題 -->
    <section class="cc-tile">
      <div class="cc-tile-title">外觀</div>
      <div class="cc-segmented">
        ${THEMES.map(t => `
          <button class="cc-seg ${curTheme === t.id ? "active" : ""}"
                  type="button" data-theme="${t.id}">
            <span class="cc-seg-icon">${t.icon}</span>
            <span>${t.label}</span>
          </button>
        `).join("")}
      </div>
    </section>

    <!-- Toggle Row · 2 col -->
    <section class="cc-tile cc-tile-row">
      <button class="cc-toggle ${isFs ? "on" : ""}" type="button" data-action="fullscreen">
        <span class="cc-toggle-icon">⛶</span>
        <span class="cc-toggle-label">全螢幕</span>
      </button>
      <button class="cc-toggle" type="button" data-action="reload">
        <span class="cc-toggle-icon">↻</span>
        <span class="cc-toggle-label">重整</span>
      </button>
    </section>

    <!-- 快速動作 -->
    <section class="cc-tile">
      <div class="cc-tile-title">快速動作</div>
      <div class="cc-actions">
        <button class="cc-action" type="button" data-action="new-chat">
          <span>💬</span><span>新對話</span>
        </button>
        <button class="cc-action" type="button" data-action="knowledge">
          <span>📚</span><span>知識庫</span>
        </button>
        <button class="cc-action" type="button" data-action="tutorial">
          <span>🎓</span><span>看教學</span>
        </button>
        <button class="cc-action" type="button" data-action="check-update">
          <span>🚀</span><span>檢查更新</span>
        </button>
      </div>
    </section>

    <!-- Footer · 登出 -->
    <section class="cc-tile cc-tile-footer">
      <button class="cc-action danger" type="button" data-action="logout">
        登出
      </button>
    </section>
  `;

  // Bind
  container.querySelectorAll("[data-engine]").forEach(b => {
    b.addEventListener("click", () => _setEngine(b.dataset.engine));
  });
  container.querySelectorAll("[data-theme]").forEach(b => {
    b.addEventListener("click", () => _setTheme(b.dataset.theme));
  });
  container.querySelectorAll("[data-action]").forEach(b => {
    b.addEventListener("click", () => _handleAction(b.dataset.action));
  });
}

function _setEngine(id) {
  // v1.11 · 走 central store(取代 chengfu-engine localStorage 重複 key + 手動 dispatchEvent)
  // store 自動寫 chengfu-ai-provider + 派 engine-changed event(legacy listeners 仍能聽)
  if (window.chengfuStore) {
    window.chengfuStore.set("engine", id);
  } else {
    // fallback · launcher 還沒 boot store 時(極早呼叫)
    localStorage.setItem("chengfu-ai-provider", id);
    document.dispatchEvent(new CustomEvent("engine-changed", { detail: { id } }));
  }
  _render();
  window.toast?.info?.(`已切到 ${id === "openai" ? "OpenAI" : "Claude"}`);
}

// v1.50 · 透過共享 actions.setTheme · 派 theme-changed event 讓其他模組 sync
function _setTheme(id) {
  _sharedSetTheme(id);
  _render();
}

function _handleAction(action) {
  switch (action) {
    case "fullscreen":
      _sharedToggleFullscreen();
      setTimeout(_render, 200);
      break;
    case "reload":
      window.location.reload();
      break;
    case "new-chat":
      close();
      window.app?.openAgent?.("00");
      break;
    case "knowledge":
      close();
      window.app?.showView?.("knowledge");
      break;
    case "tutorial":
      close();
      window.tour?.start?.();
      break;
    case "check-update":
      close();
      // 觸發 update notifier
      if (window.updateNotifier?.check) {
        window.updateNotifier.check({ silent: false });
      } else {
        window.toast?.info?.("檢查中...");
      }
      break;
    case "logout":
      if (confirm("確定登出?未送出對話會丟失")) {
        window.location.href = "/chat/logout";
      }
      break;
  }
}

// Open / close
function _onDocClick(e) {
  if (_ccEl && !_ccEl.contains(e.target)
      && !e.target.closest(".menubar-status-item.engine-toggle")) {
    close();
  }
}
function _onDocKey(e) {
  if (e.key === "Escape" && _isOpen) close();
}

export function open() {
  _ensureCC();
  if (_isOpen) return;
  // NC 開著的話 · 先關
  if (window.notificationCenter?.close) window.notificationCenter.close();
  _isOpen = true;
  _ccEl.classList.add("open");
  _render();
  setTimeout(() => {
    document.addEventListener("click", _onDocClick);
    document.addEventListener("keydown", _onDocKey);
  }, 0);
}

export function close() {
  if (!_isOpen || !_ccEl) return;
  _isOpen = false;
  _ccEl.classList.remove("open");
  document.removeEventListener("click", _onDocClick);
  document.removeEventListener("keydown", _onDocKey);
}

export function toggle() {
  if (_isOpen) close();
  else open();
}

// 全域 ⌃⌘C · open CC
document.addEventListener("keydown", (e) => {
  if (e.metaKey && e.ctrlKey && e.key.toLowerCase() === "c") {
    e.preventDefault();
    toggle();
  }
});

if (typeof window !== "undefined") {
  window.controlCenter = { open, close, toggle };
}

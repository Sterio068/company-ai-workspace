/**
 * Dashboard F++ v1.6 · 主畫面 IA 完整版(含 AI 入口)
 * =====================================
 * 設計:design_handoff_main_screen_ia/README.md
 * 路線:F++ macOS Finder + iOS App 卡 混合
 *
 * v1.5(誠實版)→ v1.6(完整版)變更:
 *   ✅ AI banner 上線(信心度 + 來源對話 + cta)
 *   ✅ Smart Folder「+ 自訂條件」橘色可點 → 開 Builder modal
 *   ✅ Today widget「待回應」變「AI 小幫手建議 N」→ 開 AI Inbox 抽屜
 *   ✅ 每條建議帶:類型 chip + 來源(可點)+ 信心度條
 *   ✅ 信心 < 80% 不上 banner · 只在 Inbox · 帶 dimmed
 *   ✅ 「不再提示這類」記憶
 *
 * 結構(由上而下):
 *   1. Toolbar(承 logo · 上下頁 · 視圖切換 · inline composer · 搜尋 · ?)
 *   2. AI banner(v1.6 · 有建議才出)
 *   3. Mini-Today(時間 + 問候 + 3 widget)
 *   4. Path bar(麵包屑)
 *   5. Smart Folder segments(含「+ 自訂條件」可點 + 自訂 chips)
 *   6. Main grid
 *   7. Status bar
 *
 * 鍵盤同 v1.5。
 */
import { escapeHtml } from "../util.js";
import { authFetch } from "../auth.js";
import { brand } from "../branding.js";
import { trap as trapFocus } from "./modal-trap.js";

// v1.32 a11y · A4 修 · trap focus release handles
let _builderTrapRelease = null;
let _inboxTrapRelease = null;
// v1.40 F6 · QuickLook + Hints 也接 trap
let _quicklookTrapRelease = null;

// Mock data · 21 對話 · 與設計一致
const MOCK_ITEMS = [
  { id: 1, name: "中秋禮盒",   date: "今天",  kind: "PDF", presence: "typing",  unread: 3, ws: "投標", color: "#FF3B30" },
  { id: 2, name: "RFP v3",     date: "昨天",  kind: "DOC", presence: "idle",    unread: 0, ws: "投標", color: "#FF3B30" },
  { id: 3, name: "客戶回信",   date: "3 天前", kind: "📧",  presence: "idle",    unread: 1, ws: "公關", color: "#34C759" },
  { id: 4, name: "設計初稿",   date: "上週",  kind: "IMG", presence: "running", unread: 0, ws: "設計", color: "#AF52DE" },
  { id: 5, name: "現場照",     date: "5/12",  kind: "IMG", presence: "idle",    unread: 0, ws: "活動", color: "#FF9500" },
  { id: 6, name: "預算表",     date: "5/10",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 7, name: "公關稿",     date: "5/08",  kind: "DOC", presence: "idle",    unread: 0, ws: "公關", color: "#34C759" },
  { id: 8, name: "工地巡查",   date: "5/05",  kind: "IMG", presence: "typing",  unread: 2, ws: "活動", color: "#FF9500" },
  { id: 9, name: "財報 Q1",    date: "4/28",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 10, name: "會議紀錄",  date: "4/22",  kind: "MTG", presence: "idle",    unread: 0, ws: "公關", color: "#34C759" },
  { id: 11, name: "LOGO",      date: "4/15",  kind: "IMG", presence: "idle",    unread: 0, ws: "設計", color: "#AF52DE" },
  { id: 12, name: "下週進度",  date: "4/10",  kind: "💬",  presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 13, name: "客戶 A",    date: "4/08",  kind: "💬",  presence: "idle",    unread: 0, ws: "公關", color: "#34C759" },
  { id: 14, name: "成本表",    date: "4/03",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 15, name: "問卷",      date: "3/28",  kind: "DOC", presence: "idle",    unread: 0, ws: "公關", color: "#34C759" },
  { id: 16, name: "合約",      date: "3/22",  kind: "PDF", presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 17, name: "人事",      date: "3/18",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 18, name: "差旅",      date: "3/14",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 19, name: "報表",      date: "3/10",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 20, name: "備忘",      date: "3/05",  kind: "💬",  presence: "idle",    unread: 0, ws: "營運", color: "#007AFF" },
  { id: 21, name: "補件",      date: "3/02",  kind: "PDF", presence: "idle",    unread: 0, ws: "投標", color: "#FF3B30" },
];

const SEGMENTS = [
  { k: "all",     l: "全部 24",       active: true,  smart: false },
  { k: "today",   l: "◐ 今天回過 5",   active: false, smart: true },
  { k: "mention", l: "@我 3",          active: false, smart: true },
  { k: "review",  l: "待我審 2",       active: false, smart: true },
  { k: "stale",   l: "3 天沒動 7",     active: false, smart: true },
  { k: "ws-1",    l: "投標 6",         active: false, smart: false },
  { k: "ws-2",    l: "活動 8",         active: false, smart: false },
  { k: "ws-3",    l: "設計 4",         active: false, smart: false },
];

// v1.6 · AI 建議(初版 mock · 後端 ready 後改 fetch)
const MOCK_AI_SUGGESTIONS = [
  { id: 1, type: "deadline", text: "RFP 提到 3 個截止日 (5/15、5/22、6/01)", cta: "排進日曆", src: "中秋禮盒 · 14:32", confidence: 0.92 },
  { id: 2, type: "reply",    text: "客戶 A 上週四問的 3 個問題還沒回",         cta: "看草稿",   src: "客戶 A · 4 天前", confidence: 0.88 },
  { id: 3, type: "stale",    text: "春節提案 11 天沒動 · 要結案嗎?",          cta: "檢視",    src: "春節提案",       confidence: 0.71 },
];

// v1.6 · 「不再提示」記憶 · localStorage
const SUPPRESS_KEY = "chengfu_ai_suppress_types_v1";
function _getSuppressed() {
  try { return new Set(JSON.parse(localStorage.getItem(SUPPRESS_KEY) || "[]")); }
  catch { return new Set(); }
}
function _suppress(type) {
  const s = _getSuppressed();
  s.add(type);
  localStorage.setItem(SUPPRESS_KEY, JSON.stringify([...s]));
}

let _state = {
  view: "grid",      // grid / list / column
  selected: 0,
  segment: "all",
  showHints: true,
  quickLook: false,
  initialized: false,
  // v1.6
  builderOpen: false,
  inboxOpen: false,
  bannerDismissedIds: new Set(),
  customFolders: JSON.parse(localStorage.getItem("chengfu_custom_folders_v1") || "[]"),
  builderConditions: [
    { f: "工作區",     op: "=", v: "投標", removable: false },
    { f: "回應狀態",   op: "=", v: "待我回", removable: true },
    { f: "上次活動",   op: "<", v: "7 天", removable: true },
  ],
  builderName: "Q1 客戶 · 高優先",
  aiSuggestions: [],   // 從 fetch 進來
};

let _root = null;
let _items = MOCK_ITEMS;

// 啟動時 fetch AI 建議(後端 ready 才回真資料 · 否則 fallback mock)
async function _fetchSuggestions() {
  try {
    const r = await authFetch("/api-accounting/admin/ai-suggestions");
    if (r.ok) {
      const data = await r.json();
      _state.aiSuggestions = (data.suggestions || []).filter(s => {
        return !_getSuppressed().has(s.type);
      });
      return;
    }
  } catch { /* 後端沒準備好 · 用 mock */ }
  _state.aiSuggestions = MOCK_AI_SUGGESTIONS.filter(s => !_getSuppressed().has(s.type));
}

// ============================================================
// Render
// ============================================================
function _render() {
  if (!_root) return;
  _root.innerHTML = `
    ${_renderToolbar()}
    ${_renderAiBanner()}
    ${_renderMiniToday()}
    ${_renderPathBar()}
    ${_renderSegments()}
    <div class="fpp-main" id="fpp-main">
      ${_renderGrid()}
    </div>
    ${_renderStatusBar()}
  `;
  _bindToolbar();
  _bindGrid();
  _bindWidgets();
  _bindHints();
  _bindSegments();
  _bindAiBanner();
}

// v1.6 · AI Banner · 只顯示信心 > 80% 的最高優先建議
function _renderAiBanner() {
  const top = _state.aiSuggestions.find(s =>
    s.confidence > 0.8 && !_state.bannerDismissedIds.has(s.id)
  );
  if (!top) return "";
  const others = _state.aiSuggestions.filter(s =>
    s.id !== top.id && !_state.bannerDismissedIds.has(s.id)
  ).length;
  return `
    <div class="fpp-ai-banner" data-fpp-banner>
      <span class="fpp-ai-icon" aria-hidden="true">✨</span>
      <span class="fpp-ai-text">AI 小幫手:${escapeHtml(top.text)} · 要我${escapeHtml(top.cta)}嗎?</span>
      ${_renderConfidenceBar(top.confidence)}
      <button type="button" class="fpp-ai-source" data-fpp-source="${escapeHtml(top.src)}" title="點看來源對話">
        來源:${escapeHtml(top.src)} ↗
      </button>
      <span class="fpp-banner-spacer"></span>
      ${others > 0 ? `<button type="button" class="fpp-ai-more" data-fpp-banner-more>看其他 ${others} 條</button>` : ""}
      <button type="button" class="fpp-ai-cta" data-fpp-banner-cta="${top.id}">${escapeHtml(top.cta)}</button>
      <button type="button" class="fpp-ai-later" data-fpp-banner-later="${top.id}">之後再說</button>
      <button type="button" class="fpp-ai-close" data-fpp-banner-close aria-label="關閉">×</button>
    </div>
  `;
}

function _renderConfidenceBar(value) {
  // v1.38 a11y · F5 修 · 信心度條本身是裝飾(% 文字才是 SR 內容)
  // 加 role="img" + aria-label 讓 SR 念整體含意 · 段條 aria-hidden 略過
  const filled = value > 0.85 ? 3 : value > 0.7 ? 2 : 1;
  const segs = [0, 1, 2].map(i => {
    const cls = i < filled
      ? (filled === 3 ? "high" : filled === 2 ? "mid" : "low")
      : "empty";
    return `<span class="fpp-conf-seg ${cls}" aria-hidden="true"></span>`;
  }).join("");
  const pct = Math.round(value * 100);
  return `<span class="fpp-conf" role="img" aria-label="AI 信心度 ${pct}%">${segs}<span class="fpp-conf-pct">${pct}%</span></span>`;
}

function _renderToolbar() {
  return `
    <div class="fpp-toolbar">
      <button type="button" class="fpp-logo" data-fpp-logo title="導覽 (⌘0)">
        <span class="fpp-logo-text">${escapeHtml(brand.companyShort)}</span>
        <span class="fpp-logo-arrow">▾</span>
      </button>
      <div class="fpp-nav-arrows">
        <button type="button" class="fpp-arrow" disabled aria-label="上一頁">‹</button>
        <button type="button" class="fpp-arrow" disabled aria-label="下一頁">›</button>
      </div>
      <div class="fpp-view-switch" role="tablist">
        ${["grid", "list", "column"].map(v => `
          <button type="button" class="fpp-view-btn ${_state.view === v ? "active" : ""}"
                  data-fpp-view="${v}" role="tab" aria-selected="${_state.view === v}">
            ${v === "grid" ? "圖示" : v === "list" ? "清單" : "分欄"}
          </button>
        `).join("")}
      </div>
      <div class="fpp-composer">
        <span class="fpp-composer-dot" aria-hidden="true"></span>
        <input type="text" class="fpp-composer-input"
               placeholder="交給AI 小幫手…(輸入後 ↵ 送出)"
               aria-label="AI 小幫手對話">
        <kbd class="fpp-composer-hint">↵</kbd>
      </div>
      <button type="button" class="fpp-search" data-fpp-search title="全域搜尋 (⌘K)" aria-label="搜尋">
        <svg width="13" height="13" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8" fill="none">
          <circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <kbd>⌘F</kbd>
      </button>
      <button type="button" class="fpp-hints-toggle ${_state.showHints ? "active" : ""}"
              data-fpp-hints title="鍵盤提示 (?)">?</button>
    </div>
  `;
}

function _renderMiniToday() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const day = ["日", "一", "二", "三", "四", "五", "六"][now.getDay()];
  const dateStr = `週${day} ${now.getMonth() + 1}/${now.getDate()}`;
  const userName = window.app?.user?.name || window.app?.user?.email?.split("@")[0] || "你";
  const greeting = now.getHours() < 12 ? "早安" : now.getHours() < 18 ? "午安" : "晚安";

  return `
    <div class="fpp-today">
      <div class="fpp-today-time">
        <div class="fpp-time-big">${hh}:${mm}</div>
        <div class="fpp-time-date">${dateStr}</div>
      </div>
      <div class="fpp-today-greeting">
        <div class="fpp-greeting-text">${greeting} ${escapeHtml(userName)}</div>
        <div class="fpp-greeting-sub">本週省了 7.4 小時</div>
      </div>
      <div class="fpp-widgets">
        <div class="fpp-widget" data-fpp-widget="conversations">
          <div class="fpp-widget-row">
            <span class="fpp-widget-big">12</span>
            <span class="fpp-widget-unit">次</span>
          </div>
          <div class="fpp-widget-label">今日對話</div>
        </div>
        <div class="fpp-widget" data-fpp-widget="saved">
          <div class="fpp-widget-row">
            <span class="fpp-widget-big">7.4</span>
            <span class="fpp-widget-unit">小時</span>
          </div>
          <div class="fpp-widget-label">本週節省</div>
        </div>
        <div class="fpp-widget fpp-widget-accent" data-fpp-widget="inbox">
          <div class="fpp-widget-row">
            <span class="fpp-widget-big">${_state.aiSuggestions.length}</span>
            <span class="fpp-widget-unit">件</span>
            <span class="fpp-widget-cta">✨ 看建議</span>
          </div>
          <div class="fpp-widget-label">AI 小幫手建議</div>
        </div>
      </div>
    </div>
  `;
}

function _renderPathBar() {
  return `
    <div class="fpp-path">
      <span class="fpp-path-label">路徑</span>
      <span class="fpp-path-segment fpp-path-current">主畫面</span>
    </div>
  `;
}

function _renderSegments() {
  // SEGMENTS · 加 customFolders(在 smart 之後 · 工作區之前)
  const built = [
    ...SEGMENTS.slice(0, 5),
    ..._state.customFolders.map(c => ({ k: c.k, l: c.l, active: false, smart: true, custom: true })),
    ...SEGMENTS.slice(5),
  ];
  return `
    <div class="fpp-segments" role="tablist">
      ${built.map(s => `
        <button type="button" class="fpp-segment ${s.active ? "active" : ""} ${s.smart ? "smart" : ""}"
                data-fpp-segment="${s.k}" ${s.custom ? `data-fpp-custom="${s.k}"` : ""}
                role="tab" aria-selected="${s.active}">
          ${escapeHtml(s.l)}
          ${s.custom ? `<span class="fpp-seg-edit" data-fpp-seg-edit="${s.k}" title="編輯">⋯</span>` : ""}
        </button>
      `).join("")}
      <!-- v1.6 · 「+ 自訂條件」橘色可點 → 開 Builder -->
      <button type="button" class="fpp-segment fpp-segment-add" data-fpp-builder-open
              title="新增 Smart Folder">+ 自訂條件</button>
      <span class="fpp-segments-hint">橘色 · Smart Folder 條件查詢</span>
    </div>
  `;
}

function _renderGrid() {
  return `
    <div class="fpp-grid" id="fpp-grid">
      ${_items.map((it, i) => `
        <button type="button" class="fpp-item ${i === _state.selected ? "selected" : ""}"
                data-fpp-item="${i}" tabindex="${i === _state.selected ? 0 : -1}"
                aria-label="${escapeHtml(it.name)} · ${escapeHtml(it.date)}">
          <div class="fpp-icon" style="--ws-color:${escapeHtml(it.color)}" aria-hidden="true">
            <span class="fpp-icon-kind">${escapeHtml(it.kind)}</span>
            ${it.presence === "typing" ? `<span class="fpp-icon-presence typing" title="對方輸入中">✏</span>` : ""}
            ${it.presence === "running" ? `<span class="fpp-icon-presence running" title="AI 小幫手進行中">⟳</span>` : ""}
            ${it.unread > 0 ? `<span class="fpp-icon-badge">${escapeHtml(String(it.unread))}</span>` : ""}
          </div>
          <span class="fpp-item-name">${escapeHtml(it.name)}</span>
          <span class="fpp-item-date">${escapeHtml(it.date)}</span>
        </button>
      `).join("")}
    </div>
  `;
}

function _renderStatusBar() {
  const item = _items[_state.selected];
  return `
    <div class="fpp-status">
      <span class="fpp-status-dot" aria-hidden="true"></span>
      <span>6 容器 healthy</span>
      <span class="fpp-status-sep">│</span>
      <span>選中: <b>${escapeHtml(item?.name || "—")}</b></span>
      <span class="fpp-status-sep">│</span>
      <span>$0.45 / $20</span>
      <span class="fpp-status-sep">│</span>
      <span class="fpp-status-accent">● 2 待回應</span>
      <span class="fpp-status-spacer"></span>
      <span class="fpp-status-keys">j/k 移動 · space 預覽 · enter 開啟 · ? 提示</span>
    </div>
  `;
}

// ============================================================
// Bind
// ============================================================
function _bindToolbar() {
  _root.querySelectorAll("[data-fpp-view]").forEach(b => {
    b.addEventListener("click", () => {
      _state.view = b.dataset.fppView;
      // v1.19 perf · view (grid/list/column) 切換只動 grid · 不重 render 整頁
      _renderGridOnly();
      // toolbar 自身的 active class 也要更新
      _root.querySelectorAll("[data-fpp-view]").forEach(other => {
        other.classList.toggle("active", other.dataset.fppView === _state.view);
      });
    });
  });
  _root.querySelector("[data-fpp-logo]")?.addEventListener("click", () => {
    if (window.app?.openPalette) window.app.openPalette();
  });
  _root.querySelector("[data-fpp-search]")?.addEventListener("click", () => {
    if (window.app?.openPalette) window.app.openPalette();
  });
  // composer enter → 開新對話
  const composer = _root.querySelector(".fpp-composer-input");
  composer?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && composer.value.trim()) {
      const text = composer.value.trim();
      window.app?.openAgent?.("00");
      window.toast?.info?.(`已交給AI 小幫手:${text.slice(0, 30)}${text.length > 30 ? "…" : ""}`);
      composer.value = "";
    }
  });
}

function _bindGrid() {
  _root.querySelectorAll("[data-fpp-item]").forEach(btn => {
    const idx = parseInt(btn.dataset.fppItem, 10);
    btn.addEventListener("click", () => {
      _state.selected = idx;
      _renderGridOnly();
      _renderStatusOnly();
    });
    btn.addEventListener("dblclick", () => {
      _openItem(_items[idx]);
    });
  });
}

function _bindSegments() {
  _root.querySelectorAll("[data-fpp-segment]").forEach(b => {
    b.addEventListener("click", (e) => {
      // 內部 edit 按鈕點擊不觸發 segment 切換
      if (e.target.closest("[data-fpp-seg-edit]")) return;
      const k = b.dataset.fppSegment;
      SEGMENTS.forEach(s => s.active = (s.k === k));
      _state.segment = k;
      // v1.16 perf · segment 切換只 re-render segments + grid + status
      // 取代整頁 _render()(避免重 bind toolbar/banner/widgets/hints · perf-optimizer 黃 6)
      _renderSegmentsOnly();
    });
  });
  // v1.6 · 「+ 自訂條件」開 Builder
  _root.querySelector("[data-fpp-builder-open]")?.addEventListener("click", () => {
    _openBuilder();
  });
  // v1.6 · 編輯 custom folder
  _root.querySelectorAll("[data-fpp-seg-edit]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const k = btn.dataset.fppSegEdit;
      const folder = _state.customFolders.find(f => f.k === k);
      if (folder) {
        _state.builderName = folder.name || folder.l;
        _state.builderConditions = folder.conditions || _state.builderConditions;
      }
      _openBuilder(k);
    });
  });
}

function _bindWidgets() {
  _root.querySelector('[data-fpp-widget="inbox"]')?.addEventListener("click", () => {
    _openInbox();
  });
}

// v1.6 · AI banner 點擊事件
function _bindAiBanner() {
  const banner = _root.querySelector("[data-fpp-banner]");
  if (!banner) return;

  banner.querySelector("[data-fpp-banner-close]")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const top = _state.aiSuggestions.find(s => s.confidence > 0.8);
    if (top) _state.bannerDismissedIds.add(top.id);
    _renderBannerOnly();
  });
  banner.querySelector("[data-fpp-banner-cta]")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = parseInt(e.currentTarget.dataset.fppBannerCta, 10);
    _executeSuggestion(id);
  });
  banner.querySelector("[data-fpp-banner-later]")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = parseInt(e.currentTarget.dataset.fppBannerLater, 10);
    _state.bannerDismissedIds.add(id);
    _renderBannerOnly();
  });
  banner.querySelector("[data-fpp-banner-more]")?.addEventListener("click", (e) => {
    e.stopPropagation();
    _openInbox();
  });
  banner.querySelector("[data-fpp-source]")?.addEventListener("click", (e) => {
    e.stopPropagation();
    _showSourceJump(e.currentTarget.dataset.fppSource);
  });
}

// v1.19 perf · 真 banner-only re-render(從整頁 _render 改 partial)
// banner 元素 .fpp-ai-banner outerHTML swap · re-bind 即可 · 不動 toolbar/grid
function _renderBannerOnly() {
  if (!_root) return;
  const oldBanner = _root.querySelector(".fpp-ai-banner");
  const newHtml = _renderAiBanner();  // 可能回 "" (沒建議或全 dismissed)
  if (oldBanner) {
    if (newHtml) {
      // swap outerHTML 保位置
      oldBanner.outerHTML = newHtml;
    } else {
      oldBanner.remove();
    }
  } else if (newHtml) {
    // 沒舊 banner · 插在 toolbar 後 mini-today 前
    const toolbar = _root.querySelector(".fpp-toolbar");
    if (toolbar) toolbar.insertAdjacentHTML("afterend", newHtml);
  }
  _bindAiBanner();  // re-bind banner 內 button
}

function _executeSuggestion(id) {
  const s = _state.aiSuggestions.find(x => x.id === id);
  if (!s) return;
  // MVP · 顯示 toast + 移除該建議
  window.toast?.success?.(`已${s.cta} · ${s.text.slice(0, 30)}`);
  _state.aiSuggestions = _state.aiSuggestions.filter(x => x.id !== id);
  _state.bannerDismissedIds.add(id);
  // v1.19 · 只 banner 變了 · 不需重 render 整頁
  _renderBannerOnly();
}

function _showSourceJump(src) {
  const old = document.getElementById("fpp-source-jump");
  if (old) old.remove();
  const t = document.createElement("div");
  t.id = "fpp-source-jump";
  t.className = "fpp-source-jump";
  t.innerHTML = `↗ 跳到對話「${escapeHtml(src)}」 <span class="fpp-source-jump-sub">(scroll 到 14:32 訊息)</span>`;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("show"), 10);
  setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => t.remove(), 200);
  }, 2000);
}

function _bindHints() {
  _root.querySelector("[data-fpp-hints]")?.addEventListener("click", () => {
    _state.showHints = !_state.showHints;
    _renderHintsOverlay();
    _root.querySelector("[data-fpp-hints]")?.classList.toggle("active", _state.showHints);
  });
}

// 局部 render(避免整頁閃)
function _renderGridOnly() {
  const main = _root.querySelector("#fpp-main");
  if (main) {
    main.innerHTML = _renderGrid();
    _bindGrid();
  }
}

function _renderStatusOnly() {
  const status = _root.querySelector(".fpp-status");
  if (status) status.outerHTML = _renderStatusBar();
}

// v1.16 perf · segment-only re-render(避免整頁閃 + re-bind 全 toolbar/banner)
// 切換 Smart Folder 時用 · 只 update segments active class + grid
function _renderSegmentsOnly() {
  const segs = _root.querySelector(".fpp-segments");
  if (segs) {
    segs.outerHTML = _renderSegments();
    _bindSegments();  // 重新綁 click handlers · segments DOM 重生
  }
  _renderGridOnly();
  _renderStatusOnly();
}

// ============================================================
// Quick Look overlay
// ============================================================
function _openQuickLook() {
  if (_state.quickLook) return;
  _state.quickLook = true;
  const item = _items[_state.selected];
  const overlay = document.createElement("div");
  overlay.className = "fpp-quicklook-overlay";
  overlay.id = "fpp-quicklook";
  overlay.innerHTML = `
    <div class="fpp-quicklook">
      <div class="fpp-quicklook-head">
        <div class="fpp-quicklook-title">
          <div class="fpp-icon fpp-icon-large" style="--ws-color:${escapeHtml(item.color)}" aria-hidden="true">
            <span class="fpp-icon-kind">${escapeHtml(item.kind)}</span>
          </div>
          <div>
            <div class="fpp-quicklook-name" id="fpp-quicklook-title">${escapeHtml(item.name)}</div>
            <div class="fpp-quicklook-meta">${escapeHtml(item.ws)} · ${escapeHtml(item.date)}</div>
          </div>
        </div>
        <button type="button" class="fpp-quicklook-close" aria-label="關閉">space / esc 關閉</button>
      </div>
      <div class="fpp-quicklook-section">
        <div class="fpp-quicklook-label">最近 3 訊</div>
        <div class="fpp-msg fpp-msg-them">
          <div class="fpp-msg-bubble">客戶 A:RFP v3 收到了 · 有 3 個地方要再確認…</div>
        </div>
        <div class="fpp-msg fpp-msg-me">
          <div class="fpp-msg-bubble fpp-msg-bubble-accent">AI 小幫手:已整理回應草稿,需要您審核</div>
        </div>
        <div class="fpp-msg fpp-msg-them">
          <div class="fpp-msg-bubble">Sterio:第 2 點建議改成…</div>
        </div>
      </div>
      <div class="fpp-quicklook-section">
        <div class="fpp-quicklook-label">素材</div>
        <div class="fpp-quicklook-files">
          <div class="fpp-file"><span class="fpp-file-icon">PDF</span> RFP_v3.pdf</div>
          <div class="fpp-file"><span class="fpp-file-icon">📧</span> 客戶回信.eml</div>
        </div>
      </div>
      <div class="fpp-quicklook-actions">
        <button type="button" class="fpp-btn fpp-btn-primary" data-fpp-ql-open>開啟對話 ↵</button>
        <button type="button" class="fpp-btn" data-fpp-ql-reply>快速回覆</button>
      </div>
    </div>
  `;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) _closeQuickLook();
  });
  overlay.querySelector("[data-fpp-ql-open]")?.addEventListener("click", () => {
    _closeQuickLook();
    _openItem(item);
  });
  document.body.appendChild(overlay);
  setTimeout(() => overlay.classList.add("open"), 10);
  // v1.40 F6 · 接 modal trap focus + dialog ARIA + #app inert
  _quicklookTrapRelease = trapFocus(overlay, {
    labelledBy: "fpp-quicklook-title",
  });
}

function _closeQuickLook() {
  _state.quickLook = false;
  // v1.40 F6 · 釋放 trap · 恢復 focus
  if (_quicklookTrapRelease) {
    _quicklookTrapRelease();
    _quicklookTrapRelease = null;
  }
  const overlay = document.getElementById("fpp-quicklook");
  if (overlay) {
    overlay.classList.remove("open");
    setTimeout(() => overlay.remove(), 160);
  }
}

function _openItem(item) {
  // 暫時:跳到對應 workspace · 之後 v1.6 改開對話 window
  const wsMap = { "投標": 1, "活動": 2, "設計": 3, "公關": 4, "營運": 5 };
  const wsId = wsMap[item.ws];
  if (wsId && window.app?.openWorkspace) {
    window.app.openWorkspace(wsId);
  } else {
    window.toast?.info?.(`開啟 ${item.name}`);
  }
}

// ============================================================
// v1.6 · Smart Folder Builder modal
// ============================================================
function _openBuilder(editingKey = null) {
  const old = document.getElementById("fpp-builder");
  if (old) old.remove();
  _state.builderOpen = true;

  const overlay = document.createElement("div");
  overlay.id = "fpp-builder";
  overlay.className = "fpp-modal-overlay";
  overlay.innerHTML = `
    <div class="fpp-builder">
      <div class="fpp-builder-head">
        <h3 class="fpp-builder-title" id="fpp-builder-title">${editingKey ? "編輯" : "新增"} Smart Folder</h3>
        <button type="button" class="fpp-builder-close" aria-label="關閉">×</button>
      </div>
      <div class="fpp-builder-section">
        <label class="fpp-builder-label">名稱</label>
        <input type="text" class="fpp-builder-input" id="fpp-builder-name"
               value="${escapeHtml(_state.builderName)}" autocomplete="off">
      </div>
      <div class="fpp-builder-section">
        <label class="fpp-builder-label">條件 · 全部符合(AND)</label>
        <div id="fpp-builder-conds" class="fpp-builder-conds"></div>
        <button type="button" class="fpp-builder-add-cond" data-fpp-add-cond>+ 加條件</button>
      </div>
      <div class="fpp-builder-preview" id="fpp-builder-preview"></div>
      <div class="fpp-builder-options">
        <label class="fpp-builder-checkbox">
          <input type="checkbox" id="fpp-builder-show-seg" checked>
          <span>顯示在 segment 列</span>
        </label>
        <label class="fpp-builder-checkbox">
          <input type="checkbox" id="fpp-builder-notify">
          <span>有新項目時通知</span>
        </label>
      </div>
      <div class="fpp-builder-actions">
        <button type="button" class="fpp-btn" data-fpp-builder-cancel>取消</button>
        <button type="button" class="fpp-btn fpp-btn-primary" data-fpp-builder-save>儲存</button>
      </div>
    </div>
  `;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) _closeBuilder();
  });
  document.body.appendChild(overlay);
  setTimeout(() => overlay.classList.add("open"), 10);

  _renderBuilderConds();
  _renderBuilderPreview();

  // bind
  overlay.querySelector(".fpp-builder-close").addEventListener("click", _closeBuilder);
  overlay.querySelector("[data-fpp-builder-cancel]").addEventListener("click", _closeBuilder);
  overlay.querySelector("[data-fpp-add-cond]").addEventListener("click", () => {
    _state.builderConditions.push({ f: "未讀數", op: ">", v: "0", removable: true });
    _renderBuilderConds();
    _renderBuilderPreview();
  });
  overlay.querySelector("[data-fpp-builder-save]").addEventListener("click", async () => {
    const name = overlay.querySelector("#fpp-builder-name").value.trim() || "未命名";
    const key = editingKey || "custom-" + Date.now();
    const conditions = _state.builderConditions.map(c => ({ f: c.f, op: c.op, v: c.v }));
    const showInSeg = overlay.querySelector("#fpp-builder-show-seg").checked;
    const notify = overlay.querySelector("#fpp-builder-notify").checked;
    // 同步 backend(失敗仍存本機)
    try {
      const url = editingKey
        ? `/api-accounting/admin/smart-folders/${encodeURIComponent(editingKey)}`
        : `/api-accounting/admin/smart-folders`;
      await authFetch(url, {
        method: editingKey ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, name, conditions, show_in_segments: showInSeg, notify }),
      });
    } catch (e) { window.toast?.warn?.(`後端同步失敗:${e.message || e}`); }
    const folder = { k: key, name, l: name + " " + _builderPreviewCount(),
                     conditions, showInSegments: showInSeg, notify };
    if (editingKey) {
      _state.customFolders = _state.customFolders.map(f => f.k === editingKey ? folder : f);
    } else {
      _state.customFolders.push(folder);
    }
    localStorage.setItem("chengfu_custom_folders_v1", JSON.stringify(_state.customFolders));
    window.toast?.success?.(`Smart Folder「${name}」已${editingKey ? "更新" : "建立"}`);
    _closeBuilder();
    // v1.19 perf · 只 segment 列加新 chip · 不需重 render 整頁
    _renderSegmentsOnly();
  });
  // ESC + v1.32 a11y · A4 修 · trap focus + initial focus 到名稱欄位
  setTimeout(() => {
    document.addEventListener("keydown", _onBuilderEsc);
    _builderTrapRelease = trapFocus(overlay, {
      initialFocusSelector: "#fpp-builder-name",
      labelledBy: "fpp-builder-title",  // v1.35 F1 · SR 念「dialog · 編輯 Smart Folder」
    });
  }, 0);
}

function _onBuilderEsc(e) {
  if (e.key === "Escape" && _state.builderOpen) {
    e.preventDefault();
    _closeBuilder();
  }
}

function _closeBuilder() {
  _state.builderOpen = false;
  document.removeEventListener("keydown", _onBuilderEsc);
  // v1.32 · 釋放 trap focus · 恢復原 focus 到開 modal 前的 element
  if (_builderTrapRelease) {
    _builderTrapRelease();
    _builderTrapRelease = null;
  }
  const overlay = document.getElementById("fpp-builder");
  if (overlay) {
    overlay.classList.remove("open");
    setTimeout(() => overlay.remove(), 180);
  }
}

function _renderBuilderConds() {
  const container = document.getElementById("fpp-builder-conds");
  if (!container) return;
  const FIELDS = ["工作區", "回應狀態", "上次活動", "對話標題", "未讀數", "提及我", "工作包", "AI 小幫手活動"];
  const OPS = ["=", "≠", "包含", ">", "<"];
  // v1.43 a11y · F10 修 · 條件 row 加 group + 各 control aria-label
  // SR 念「條件 1 群組 · 欄位 combobox · 比較 combobox · 值 textbox · 移除 button」
  container.innerHTML = _state.builderConditions.map((c, i) => `
    <div class="fpp-cond-row" role="group" aria-label="條件 ${i + 1}">
      <select data-fpp-cond-f="${i}" class="fpp-cond-select" aria-label="條件 ${i + 1} 欄位">
        ${FIELDS.map(f => `<option ${f === c.f ? "selected" : ""}>${f}</option>`).join("")}
      </select>
      <select data-fpp-cond-op="${i}" class="fpp-cond-select fpp-cond-op" aria-label="條件 ${i + 1} 比較運算子">
        ${OPS.map(o => `<option ${o === c.op ? "selected" : ""}>${o}</option>`).join("")}
      </select>
      <input data-fpp-cond-v="${i}" class="fpp-cond-input" value="${escapeHtml(c.v)}" aria-label="條件 ${i + 1} 值">
      ${c.removable !== false ? `<button type="button" class="fpp-cond-rm" data-fpp-cond-rm="${i}" aria-label="移除條件 ${i + 1}">×</button>` : ""}
    </div>
  `).join("");
  // bind change
  container.querySelectorAll("[data-fpp-cond-f]").forEach(s => {
    s.addEventListener("change", e => {
      const i = +e.target.dataset.fppCondF;
      _state.builderConditions[i].f = e.target.value;
      _renderBuilderPreview();
    });
  });
  container.querySelectorAll("[data-fpp-cond-op]").forEach(s => {
    s.addEventListener("change", e => {
      const i = +e.target.dataset.fppCondOp;
      _state.builderConditions[i].op = e.target.value;
      _renderBuilderPreview();
    });
  });
  container.querySelectorAll("[data-fpp-cond-v]").forEach(s => {
    s.addEventListener("input", e => {
      const i = +e.target.dataset.fppCondV;
      _state.builderConditions[i].v = e.target.value;
      _renderBuilderPreview();
    });
  });
  container.querySelectorAll("[data-fpp-cond-rm]").forEach(s => {
    s.addEventListener("click", e => {
      const i = +e.currentTarget.dataset.fppCondRm;
      _state.builderConditions.splice(i, 1);
      _renderBuilderConds();
      _renderBuilderPreview();
    });
  });
}

// 條件 → 預覽符合對話數(MVP · 之後接後端 query engine)
function _builderPreviewCount() {
  return Math.max(1, 12 - _state.builderConditions.length * 3 +
    (_state.builderConditions.length === 1 ? 4 : 0));
}

function _renderBuilderPreview() {
  const el = document.getElementById("fpp-builder-preview");
  if (!el) return;
  const n = _builderPreviewCount();
  const previewItems = MOCK_ITEMS.slice(0, Math.min(3, n));
  el.innerHTML = `
    <div class="fpp-preview-row">
      <span class="fpp-preview-dot"></span>
      <span class="fpp-preview-text">預覽:符合條件 <strong>${n}</strong> 個對話</span>
      <span class="fpp-preview-spacer"></span>
      <span class="fpp-preview-items">${previewItems.map(i => i.name).join(" · ")}${n > 3 ? " …" : ""}</span>
    </div>
  `;
}

// ============================================================
// v1.6 · AI Inbox 右抽屜
// ============================================================
function _openInbox() {
  const old = document.getElementById("fpp-inbox");
  if (old) { _closeInbox(); return; }
  _state.inboxOpen = true;

  const overlay = document.createElement("div");
  overlay.id = "fpp-inbox";
  overlay.className = "fpp-inbox-overlay";
  overlay.innerHTML = `
    <div class="fpp-inbox">
      <div class="fpp-inbox-head">
        <h3 class="fpp-inbox-title" id="fpp-inbox-title">✨ AI 小幫手建議</h3>
        <button type="button" class="fpp-inbox-close" aria-label="關閉">×</button>
      </div>
      <div class="fpp-inbox-meta">基於對話內容 + 截止日 + 回應狀態 · 每 30 分鐘掃描一次</div>
      <div class="fpp-inbox-list" id="fpp-inbox-list"></div>
      <div class="fpp-inbox-footer">觸發規則可在 設定 › AI 小幫手行為 調整</div>
    </div>
  `;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) _closeInbox();
  });
  document.body.appendChild(overlay);
  setTimeout(() => overlay.classList.add("open"), 10);

  _renderInboxList();

  overlay.querySelector(".fpp-inbox-close").addEventListener("click", _closeInbox);
  setTimeout(() => {
    document.addEventListener("keydown", _onInboxEsc);
    // v1.32 a11y · A4 修 · trap focus(initial 自動找第一個 focusable · 通常是 close button)
    _inboxTrapRelease = trapFocus(overlay, {
      labelledBy: "fpp-inbox-title",  // v1.35 F1 · SR 念「dialog · AI 小幫手建議」
    });
  }, 0);
}

function _onInboxEsc(e) {
  if (e.key === "Escape" && _state.inboxOpen) {
    e.preventDefault();
    _closeInbox();
  }
}

function _closeInbox() {
  _state.inboxOpen = false;
  document.removeEventListener("keydown", _onInboxEsc);
  // v1.32 · 釋放 inbox trap focus · 恢復原 focus
  if (_inboxTrapRelease) {
    _inboxTrapRelease();
    _inboxTrapRelease = null;
  }
  const overlay = document.getElementById("fpp-inbox");
  if (overlay) {
    overlay.classList.remove("open");
    setTimeout(() => overlay.remove(), 200);
  }
}

function _renderInboxList() {
  const container = document.getElementById("fpp-inbox-list");
  if (!container) return;
  if (_state.aiSuggestions.length === 0) {
    container.innerHTML = `
      <div class="fpp-inbox-empty">
        <div class="fpp-inbox-empty-icon">✓</div>
        <div class="fpp-inbox-empty-text">沒有待處理的建議</div>
        <div class="fpp-inbox-empty-sub">下次掃描 · 17:12</div>
      </div>
    `;
    return;
  }
  container.innerHTML = _state.aiSuggestions.map(s => `
    <div class="fpp-inbox-item ${s.confidence < 0.75 ? "low-conf" : ""}">
      <div class="fpp-inbox-row">
        <span class="fpp-chip fpp-chip-${s.type}">${
          s.type === "deadline" ? "截止日" :
          s.type === "reply" ? "待回信" : "停滯"
        }</span>
        <button type="button" class="fpp-inbox-source" data-fpp-inbox-src="${escapeHtml(s.src)}">↗ 來源:${escapeHtml(s.src)}</button>
        <span class="fpp-inbox-spacer"></span>
        ${_renderConfidenceBar(s.confidence)}
      </div>
      <div class="fpp-inbox-text">${escapeHtml(s.text)}</div>
      <div class="fpp-inbox-actions">
        <button type="button" class="fpp-btn fpp-btn-primary fpp-btn-sm" data-fpp-inbox-cta="${s.id}">${escapeHtml(s.cta)}</button>
        <button type="button" class="fpp-btn fpp-btn-sm" data-fpp-inbox-later="${s.id}">之後再說</button>
        <span class="fpp-inbox-spacer"></span>
        <button type="button" class="fpp-inbox-suppress" data-fpp-inbox-suppress="${s.type}">不再提示這類</button>
      </div>
    </div>
  `).join("");
  // v1.26 perf · #2 修 · event delegation 取代 4 個 querySelectorAll + N×listener
  // 原本:N 個 suggestion × 4 button × addEventListener = 4N listener
  //       + 「之後再說」雙綁(2 個 forEach)實際上是 5N
  // 改成:1 個 listener on container · click 用 closest() 派發
  // 預估省 80%+ listener 註冊成本(N=10 時 50 listener → 1)
  if (!container._fppDelegated) {
    container._fppDelegated = true;
    container.addEventListener("click", async (e) => {
      const t = e.target;
      // 來源跳轉
      const src = t.closest("[data-fpp-inbox-src]");
      if (src) {
        _showSourceJump(src.dataset.fppInboxSrc);
        _closeInbox();
        return;
      }
      // 主 CTA
      const cta = t.closest("[data-fpp-inbox-cta]");
      if (cta) {
        _executeSuggestion(+cta.dataset.fppInboxCta);
        _renderInboxList();
        return;
      }
      // 「之後再說」· 雙作用:UI 移除 + backend dismiss 24h(fire-and-forget)
      const later = t.closest("[data-fpp-inbox-later]");
      if (later) {
        const id = +later.dataset.fppInboxLater;
        _state.aiSuggestions = _state.aiSuggestions.filter(x => x.id !== id);
        _renderInboxList();
        authFetch(`/api-accounting/admin/ai-suggestions/${id}/dismiss`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ hours: 24 }),
        }).catch(() => {});
        return;
      }
      // 「不再提示這類」
      const sup = t.closest("[data-fpp-inbox-suppress]");
      if (sup) {
        const type = sup.dataset.fppInboxSuppress;
        _suppress(type);
        try {
          await authFetch("/api-accounting/admin/ai-suggestions/suppress", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type }),
          });
        } catch {}
        _state.aiSuggestions = _state.aiSuggestions.filter(s => s.type !== type);
        window.toast?.info?.(`已關閉「${type === "deadline" ? "截止日" : type === "reply" ? "待回信" : "停滯"}」類提示`);
        _renderInboxList();
      }
    });
  }
}

// ============================================================
// Hints overlay
// ============================================================
function _renderHintsOverlay() {
  const old = document.getElementById("fpp-hints");
  if (old) old.remove();
  if (!_state.showHints) return;
  const h = document.createElement("div");
  h.id = "fpp-hints";
  h.className = "fpp-hints";
  // v1.40 F6 · popover ARIA(非 modal · 不 trap focus 但給 SR 結構提示)
  h.setAttribute("role", "region");
  h.setAttribute("aria-label", "鍵盤快捷鍵提示");
  h.innerHTML = `
    <div class="fpp-hints-head">
      <span class="fpp-hints-title" id="fpp-hints-title">鍵盤</span>
      <button type="button" class="fpp-hints-close" aria-label="關閉" data-fpp-hints-close>×</button>
    </div>
    <div class="fpp-hints-body">
      <div><kbd>j / k</kbd><span>上下移動</span></div>
      <div><kbd>h / l</kbd><span>左右移動</span></div>
      <div><kbd>space</kbd><span>Quick Look</span></div>
      <div><kbd>↵</kbd><span>開啟對話</span></div>
      <div><kbd>esc</kbd><span>關閉</span></div>
      <div><kbd>?</kbd><span>切換此提示</span></div>
    </div>
  `;
  h.querySelector("[data-fpp-hints-close]")?.addEventListener("click", () => {
    _state.showHints = false;
    h.remove();
    _root?.querySelector("[data-fpp-hints]")?.classList.remove("active");
  });
  document.body.appendChild(h);
}

// ============================================================
// Global keyboard
// ============================================================
function _onKey(e) {
  // 不在 dashboard view 不處理
  if (window.app?.currentView !== "dashboard") return;
  // input 中只處理 esc / 特定 key
  const t = e.target;
  const inInput = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);

  if (_state.quickLook) {
    if (e.key === "Escape" || e.key === " ") {
      e.preventDefault();
      _closeQuickLook();
    }
    return;
  }
  if (inInput) return;

  const total = _items.length;
  const cols = 7;
  let handled = true;
  switch (e.key) {
    case "j": case "ArrowDown":
      _state.selected = Math.min(total - 1, _state.selected + cols);
      break;
    case "k": case "ArrowUp":
      _state.selected = Math.max(0, _state.selected - cols);
      break;
    case "h": case "ArrowLeft":
      _state.selected = Math.max(0, _state.selected - 1);
      break;
    case "l": case "ArrowRight":
      _state.selected = Math.min(total - 1, _state.selected + 1);
      break;
    case " ":
      _openQuickLook();
      break;
    case "Enter":
      _openItem(_items[_state.selected]);
      break;
    case "?":
      _state.showHints = !_state.showHints;
      _renderHintsOverlay();
      _root?.querySelector("[data-fpp-hints]")?.classList.toggle("active", _state.showHints);
      break;
    default:
      handled = false;
  }
  if (handled) {
    e.preventDefault();
    if (e.key !== "?") {
      _renderGridOnly();
      _renderStatusOnly();
      // 滾動 selected 進入視野
      const sel = _root?.querySelector(`[data-fpp-item="${_state.selected}"]`);
      sel?.focus();
      sel?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }
}

// ============================================================
// Public API
// ============================================================
export const dashboardFpp = {
  /** 把 view-dashboard innerHTML 接管 */
  async init(viewEl) {
    if (_state.initialized && _root === viewEl) {
      // 重新訪問 · 重 fetch 看有沒新建議 · v1.19 只 banner 變 不需整頁
      await _fetchSuggestions();
      _renderBannerOnly();
      return;
    }
    _root = viewEl;
    _root.classList.add("view-dashboard-fpp");
    _state.initialized = true;
    // 先 render 占位 · 不擋首屏
    _render();
    _renderHintsOverlay();
    // v1.44 perf F-6 修 · idempotent · 先 remove 再 add 防 listener 累積
    // 即使 init 重複呼叫(viewEl 改變的測試場景)也只會有 1 個 _onKey listener
    document.removeEventListener("keydown", _onKey);
    document.addEventListener("keydown", _onKey);
    // 並行 fetch · 之後只 banner 重 render(suggestions 進來時 layout 不變)
    _fetchSuggestions().then(() => _renderBannerOnly());
  },

  destroy() {
    document.removeEventListener("keydown", _onKey);
    document.removeEventListener("keydown", _onBuilderEsc);
    document.removeEventListener("keydown", _onInboxEsc);
    ["fpp-hints","fpp-quicklook","fpp-builder","fpp-inbox","fpp-source-jump"]
      .forEach(id => document.getElementById(id)?.remove());
  },
};

if (typeof window !== "undefined") window.dashboardFpp = dashboardFpp;

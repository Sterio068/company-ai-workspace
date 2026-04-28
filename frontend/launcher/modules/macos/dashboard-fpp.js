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
import { WORKSPACES } from "../config.js";
import { trap as trapFocus } from "./modal-trap.js";

// v1.32 a11y · A4 修 · trap focus release handles
let _builderTrapRelease = null;
let _inboxTrapRelease = null;
// v1.40 F6 · QuickLook + Hints 也接 trap
let _quicklookTrapRelease = null;

// Mock data · 21 對話 · 與設計一致
const MOCK_ITEMS = [
  { id: 1, name: "中秋禮盒",   date: "今天",  kind: "PDF", presence: "typing",  unread: 3, ws: "投標", color: "#D14B43" },
  { id: 2, name: "RFP v3",     date: "昨天",  kind: "DOC", presence: "idle",    unread: 0, ws: "投標", color: "#D14B43" },
  { id: 3, name: "客戶回信",   date: "3 天前", kind: "📧",  presence: "idle",    unread: 1, ws: "公關", color: "#5AB174" },
  { id: 4, name: "設計初稿",   date: "上週",  kind: "IMG", presence: "running", unread: 0, ws: "設計", color: "#8C5CB1" },
  { id: 5, name: "現場照",     date: "5/12",  kind: "IMG", presence: "idle",    unread: 0, ws: "活動", color: "#D8851E" },
  { id: 6, name: "預算表",     date: "5/10",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 7, name: "公關稿",     date: "5/08",  kind: "DOC", presence: "idle",    unread: 0, ws: "公關", color: "#5AB174" },
  { id: 8, name: "工地巡查",   date: "5/05",  kind: "IMG", presence: "typing",  unread: 2, ws: "活動", color: "#D8851E" },
  { id: 9, name: "財報 Q1",    date: "4/28",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 10, name: "會議紀錄",  date: "4/22",  kind: "MTG", presence: "idle",    unread: 0, ws: "公關", color: "#5AB174" },
  { id: 11, name: "LOGO",      date: "4/15",  kind: "IMG", presence: "idle",    unread: 0, ws: "設計", color: "#8C5CB1" },
  { id: 12, name: "下週進度",  date: "4/10",  kind: "💬",  presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 13, name: "客戶 A",    date: "4/08",  kind: "💬",  presence: "idle",    unread: 0, ws: "公關", color: "#5AB174" },
  { id: 14, name: "成本表",    date: "4/03",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 15, name: "問卷",      date: "3/28",  kind: "DOC", presence: "idle",    unread: 0, ws: "公關", color: "#5AB174" },
  { id: 16, name: "合約",      date: "3/22",  kind: "PDF", presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 17, name: "人事",      date: "3/18",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 18, name: "差旅",      date: "3/14",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 19, name: "報表",      date: "3/10",  kind: "DOC", presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 20, name: "備忘",      date: "3/05",  kind: "💬",  presence: "idle",    unread: 0, ws: "營運", color: "#3F86C9" },
  { id: 21, name: "補件",      date: "3/02",  kind: "PDF", presence: "idle",    unread: 0, ws: "投標", color: "#D14B43" },
];

const SEGMENTS = [
  // v1.49 · 移除 active 欄位 · _state.segment 為 single source of truth
  { k: "all",     l: "全部 24",       smart: false },
  { k: "today",   l: "◐ 今天回過 5",  smart: true },
  { k: "mention", l: "@我 3",         smart: true },
  { k: "review",  l: "待我審 2",      smart: true },
  { k: "stale",   l: "3 天沒動 7",    smart: true },
  { k: "ws-1",    l: "投標 6",        smart: false },
  { k: "ws-2",    l: "活動 8",        smart: false },
  { k: "ws-3",    l: "設計 4",        smart: false },
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
  // v1.45 calm mode · 預設關 hints overlay(右下浮窗太擾 · 點 ? toggle)
  showHints: false,
  // v1.46 calm · segments 預設只顯 4 個 primary chip · 點「更多 ▾」展開
  segmentsExpanded: false,
  // v1.46 calm · grid 預設只顯 12 個(原 21)· 點「顯示全部」展開
  gridExpanded: false,
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

const QUICK_WORKFLOWS = [
  { id: "tender-full", title: "投標流程", desc: "招標須知、承接評估、建議書與送件風險。", tag: "投標" },
  { id: "client-proposal", title: "客戶提案", desc: "把需求整理成提案架構、素材清單與待確認事項。", tag: "提案" },
  { id: "closing-full", title: "結案整理", desc: "彙整成果、照片、數字與下次可改進事項。", tag: "結案" },
];

function _activeProjects() {
  try {
    const projects = window.Projects?.load?.() || [];
    return projects
      .filter(project => project && project.status !== "closed")
      .slice(0, 3);
  } catch {
    return [];
  }
}

function _formatProjectMeta(project) {
  const client = project.client ? `${project.client} · ` : "";
  const due = project.due_date || project.deadline || project.dueDate;
  const dueText = due ? `截止 ${String(due).slice(0, 10)}` : "尚未設定截止日";
  return `${client}${dueText}`;
}

function _projectId(project) {
  return project.id || project._id || "";
}

function _projectNext(project) {
  return project.next_step || project.nextStep || project.summary || "打開專案後補齊下一步、附件與交棒內容。";
}

function _renderWorkspaceCard(ws) {
  return `
    <button type="button"
            class="workspace-card fpp-workspace-card ws-${ws.id}"
            data-ws="${ws.id}"
            style="--ws-color:${escapeHtml(ws.color)}"
            aria-label="開啟${escapeHtml(ws.fullName)}">
      <span class="fpp-workspace-top">
        <span class="fpp-workspace-icon" aria-hidden="true">${escapeHtml(ws.icon)}</span>
        <span class="fpp-workspace-shortcut">${escapeHtml(ws.shortcut)}</span>
      </span>
      <strong>${escapeHtml(ws.name)}</strong>
      <span>${escapeHtml(ws.flow)}</span>
    </button>
  `;
}

function _renderProjectRows() {
  const projects = _activeProjects();
  if (!projects.length) {
    return `
      <div class="fpp-empty-panel">
        <strong>還沒有可接續的專案</strong>
        <span>建立專案後,客戶背景、附件、對話與下一步會集中保存。</span>
        <button type="button" class="btn-primary btn-sm" data-today-new-project>建立專案</button>
      </div>
    `;
  }
  return projects.map(project => {
    const id = _projectId(project);
    return `
      <button type="button" class="fpp-project-row" data-open-project="${escapeHtml(id)}">
        <span class="fpp-project-dot" aria-hidden="true"></span>
        <span class="fpp-project-copy">
          <strong>${escapeHtml(project.name || "未命名專案")}</strong>
          <small>${escapeHtml(_formatProjectMeta(project))}</small>
          <span>${escapeHtml(_projectNext(project))}</span>
        </span>
      </button>
    `;
  }).join("");
}

function _renderWorkdesk() {
  const userName = window.app?.user?.name || window.app?.user?.email?.split("@")[0] || "你";
  const now = new Date();
  const day = ["日", "一", "二", "三", "四", "五", "六"][now.getDay()];
  const dateText = `${now.getMonth() + 1}/${now.getDate()} 週${day}`;

  return `
    <section class="fpp-workdesk" aria-labelledby="fpp-home-title">
      <div class="fpp-hero">
        <div class="fpp-hero-main">
          <div class="fpp-kicker">今日工作台 · ${escapeHtml(dateText)}</div>
          <h1 id="fpp-home-title">${escapeHtml(userName)},今天要先處理哪件事?</h1>
          <p>輸入需求、貼上客戶訊息,或加入 PDF / Word / Excel / 圖片。系統會先判斷任務類型,再帶你進入正確工作區。</p>

          <form class="fpp-intake" id="today-composer-form">
            <label class="sr-only" for="today-composer-input">今天要做什麼</label>
            <textarea id="today-composer-input" rows="5"
              placeholder="例:幫我整理客戶會議紀錄,列出下一步、待補資料,並存成專案交棒內容"></textarea>
            <div class="today-file-ribbon fpp-file-ribbon" id="today-file-ribbon" aria-live="polite" hidden></div>
            <input type="file" id="today-file-input" hidden multiple
              accept=".pdf,.txt,.md,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.json,.png,.jpg,.jpeg,.webp,.gif">
            <div class="fpp-intake-actions">
              <button type="button" class="btn-ghost" data-today-pick-file>加入附件</button>
              <button type="button" class="btn-ghost" data-today-new-project>建立專案</button>
              <button type="button" class="btn-ghost" data-today-show-projects>看專案</button>
              <button type="submit" class="btn-primary">交給主管家</button>
            </div>
            <div class="fpp-drop-hint">可拖放檔案到這裡。送出前都能移除附件。</div>
          </form>
        </div>

        <aside class="fpp-route-preview" aria-label="送出後會怎麼處理">
          <div class="fpp-route-title">送出後</div>
          <div class="fpp-route-step">
            <b>1</b>
            <span><strong>判斷任務</strong><small>投標、活動、設計、公關或營運。</small></span>
          </div>
          <div class="fpp-route-step">
            <b>2</b>
            <span><strong>整理素材</strong><small>讀文字與附件,標出缺漏與風險。</small></span>
          </div>
          <div class="fpp-route-step">
            <b>3</b>
            <span><strong>產出草稿</strong><small>可接著存專案、交棒或複製給客戶。</small></span>
          </div>
        </aside>
      </div>

      <section class="fpp-section" aria-labelledby="fpp-workspace-title">
        <div class="fpp-section-head">
          <div>
            <h2 id="fpp-workspace-title">5 個工作區</h2>
            <p>已經知道工作類型時,直接進工作區。</p>
          </div>
        </div>
        <div class="workspaces fpp-workspace-strip" id="workspace-cards">
          ${WORKSPACES.map(_renderWorkspaceCard).join("")}
        </div>
      </section>

      <div class="fpp-lower-grid">
        <section class="fpp-section fpp-continuity" aria-labelledby="fpp-projects-title">
          <div class="fpp-section-head">
            <div>
              <h2 id="fpp-projects-title">最近專案</h2>
              <p>接續中的工作,不用重新交代背景。</p>
            </div>
            <button type="button" class="btn-ghost btn-sm" data-today-show-projects>全部</button>
          </div>
          <div class="fpp-project-list">
            ${_renderProjectRows()}
          </div>
        </section>

        <section class="fpp-section fpp-flow-quickstart" aria-labelledby="fpp-flow-title">
          <div class="fpp-section-head">
            <div>
              <h2 id="fpp-flow-title">常用流程</h2>
              <p>固定任務可直接開草稿,再確認是否執行。</p>
            </div>
            <button type="button" class="btn-ghost btn-sm" data-open-workflows>更多</button>
          </div>
          <div class="fpp-flow-list">
            ${QUICK_WORKFLOWS.map(flow => `
              <button type="button" class="fpp-flow-card" data-workflow-shortcut="${escapeHtml(flow.id)}">
                <span>${escapeHtml(flow.tag)}</span>
                <strong>${escapeHtml(flow.title)}</strong>
                <small>${escapeHtml(flow.desc)}</small>
              </button>
            `).join("")}
          </div>
        </section>
      </div>
    </section>
  `;
}

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
  // v1.70 · 交付版首頁收斂:
  // 移除 Finder/Smart Folder/假資料格狀清單,改成新手可理解的單一工作入口。
  // 舊函式保留在檔內,供後續若要做進階工作台時復用。
  _root.innerHTML = _renderWorkdesk();
  _bindWorkdesk();
}

function _bindWorkdesk() {
  if (!_root) return;
  const form = _root.querySelector("#today-composer-form");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    window.app?.submitTodayComposer?.(e);
  });
  form?.addEventListener("dragover", (e) => {
    e.preventDefault();
    form.classList.add("is-dragover");
  });
  form?.addEventListener("dragleave", (e) => {
    if (!form.contains(e.relatedTarget)) form.classList.remove("is-dragover");
  });
  form?.addEventListener("drop", (e) => {
    e.preventDefault();
    form.classList.remove("is-dragover");
    window.app?.addTodayFiles?.(Array.from(e.dataTransfer?.files || []));
  });
  _root.querySelector("[data-today-pick-file]")?.addEventListener("click", (e) => {
    e.preventDefault();
    window.app?.pickTodayFiles?.();
  });
  _root.querySelector("#today-file-input")?.addEventListener("change", (e) => {
    window.app?.addTodayFiles?.(Array.from(e.target.files || []));
    e.target.value = "";
  });
  _root.querySelectorAll("[data-today-new-project]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      window.app?.newProject?.();
    });
  });
  _root.querySelectorAll("[data-today-show-projects]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      window.app?.showView?.("projects");
    });
  });
  _root.querySelectorAll("[data-ws]").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.ws);
      if (Number.isFinite(id)) window.app?.openWorkspace?.(id);
    });
  });
  _root.querySelectorAll("[data-open-project]").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.openProject;
      if (id) window.app?.openProjectDrawer?.(id);
      else window.app?.showView?.("projects");
    });
  });
  _root.querySelector("[data-open-workflows]")?.addEventListener("click", () => {
    window.app?.showView?.("workflows");
    window.workflows?.load?.();
  });
  _root.querySelectorAll("[data-workflow-shortcut]").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.workflowShortcut;
      window.app?.showView?.("workflows");
      window.workflows?.load?.().then(() => window.workflows?.prepare?.(id));
    });
  });
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
  // v1.65 U2 · toolbar 從 11 元素簡化為 3 群組
  // 左:logo (1) · 中:對話框佔主軸 (1) · 右:view-switch + search + hints 收進 secondary group (3)
  return `
    <div class="fpp-toolbar">
      <button type="button" class="fpp-logo" data-fpp-logo title="導覽 (⌘0)" aria-label="導覽">
        <span class="fpp-logo-text">${escapeHtml(brand.companyShort)}</span>
        <span class="fpp-logo-arrow">▾</span>
      </button>
      <form class="fpp-composer fpp-composer-primary" id="today-composer-form">
        <span class="fpp-composer-dot" aria-hidden="true"></span>
        <label class="sr-only" for="today-composer-input">今天要做什麼</label>
        <input type="text" class="fpp-composer-input" id="today-composer-input"
               placeholder="交給 AI 小幫手…按 ↵ 送出"
               aria-label="AI 小幫手對話">
        <div class="today-file-ribbon fpp-file-ribbon" id="today-file-ribbon" hidden></div>
        <input type="file" id="today-file-input" hidden multiple
               accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv,.jpg,.jpeg,.png,.webp,.gif">
        <button type="button" class="fpp-composer-btn" data-today-pick-file aria-label="加入附件">📎</button>
        <button type="submit" class="fpp-composer-submit" aria-label="送出">↵</button>
      </form>
      <div class="fpp-toolbar-secondary">
        <div class="fpp-view-switch" role="tablist" aria-label="顯示模式">
          ${["grid", "list", "column"].map(v => `
            <button type="button" class="fpp-view-btn ${_state.view === v ? "active" : ""}"
                    data-fpp-view="${v}" role="tab" aria-selected="${_state.view === v}"
                    aria-controls="fpp-main"
                    title="${v === "grid" ? "圖示" : v === "list" ? "清單" : "分欄"}">
              ${v === "grid" ? "▦" : v === "list" ? "☰" : "⫶"}
            </button>
          `).join("")}
        </div>
        <button type="button" class="fpp-search" data-fpp-search title="全域搜尋 (⌘K)" aria-label="搜尋">
          <svg width="13" height="13" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8" fill="none">
            <circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </button>
        <button type="button" class="fpp-hints-toggle ${_state.showHints ? "active" : ""}"
                data-fpp-hints title="鍵盤提示 (?)" aria-label="鍵盤提示">?</button>
      </div>
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

  // v1.45 calm mode · Mini-Today 從 3 widget → 1 個焦點(只留有行動意義的 AI 建議)
  // 12 次對話 / 7.4 小時節省 → 純資訊性 · 不是 today 的決策依據 · 移除
  // 「本週省 X 小時」也移除(數字過於樂觀沒實證)
  // 焦點:時間 · 問候 · AI 建議數(可點 → Inbox)
  const sCnt = _state.aiSuggestions.length;
  return `
    <div class="fpp-today">
      <div class="fpp-today-time">
        <div class="fpp-time-big">${hh}:${mm}</div>
        <div class="fpp-time-date">${dateStr}</div>
      </div>
      <div class="fpp-today-greeting">
        <div class="fpp-greeting-text">${greeting} ${escapeHtml(userName)}</div>
        ${sCnt > 0 ? `<div class="fpp-greeting-sub">AI 小幫手有 ${sCnt} 件建議</div>` : ""}
      </div>
      ${sCnt > 0 ? `
        <div class="fpp-widget fpp-widget-accent fpp-widget-solo" data-fpp-widget="inbox">
          <div class="fpp-widget-row">
            <span class="fpp-widget-big">${sCnt}</span>
            <span class="fpp-widget-unit">件</span>
            <span class="fpp-widget-cta">✨ 看建議</span>
          </div>
          <div class="fpp-widget-label">AI 小幫手建議</div>
        </div>
      ` : ""}
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
  // v1.65 U3 · 進一步簡化 · 只剩 2 個關鍵 chip(全部 / 今天)+ 「更多 ▾」
  // 「待我審 / 3 天沒動」這類僅在有量時才該凸顯 · 平時收起更冷靜
  // 點「更多 ▾」展開所有 segments + custom + 「+ 自訂條件」
  const PRIMARY_KEYS = new Set(["all", "today"]);
  const customFolders = _state.customFolders.map(c => ({
    k: c.k, l: c.l, smart: true, custom: true,
  }));
  const all = [
    ...SEGMENTS.slice(0, 5),
    ...customFolders,
    ...SEGMENTS.slice(5),
  ];
  const expanded = _state.segmentsExpanded === true;
  const visible = expanded
    ? all
    : all.filter(s => PRIMARY_KEYS.has(s.k) || s.k === _state.segment);
  const hiddenCount = all.length - visible.length;

  return `
    <div class="fpp-segments" role="tablist" aria-label="智慧分類">
      ${visible.map(s => {
        const active = s.k === _state.segment;
        return `
        <button type="button" class="fpp-segment ${active ? "active" : ""} ${s.smart ? "smart" : ""}"
                data-fpp-segment="${s.k}" ${s.custom ? `data-fpp-custom="${s.k}"` : ""}
                role="tab" aria-selected="${active}">
          ${escapeHtml(s.l)}
          ${s.custom ? `<span class="fpp-seg-edit" data-fpp-seg-edit="${s.k}" title="編輯">⋯</span>` : ""}
        </button>
      `;}).join("")}
      ${!expanded && hiddenCount > 0 ? `
        <button type="button" class="fpp-segment fpp-segment-more" data-fpp-segments-more
                aria-label="顯示其他 ${hiddenCount} 個分類">
          更多 ${hiddenCount} ▾
        </button>
      ` : ""}
      ${expanded ? `
        <button type="button" class="fpp-segment fpp-segment-add" data-fpp-builder-open
                title="新增 Smart Folder">+ 自訂條件</button>
      ` : ""}
    </div>
  `;
}

function _renderGrid() {
  // v1.46 calm · 預設只顯 12 個 · 「全部 · 顯示其餘 N 個」展開
  // v1.65 U8 · 空狀態優化 · 沒事不硬塞 · 改顯 CTA(不再 14 彩塊轟炸)
  const expanded = _state.gridExpanded === true;
  const PRIMARY_LIMIT = 12;
  const visible = expanded ? _items : _items.slice(0, PRIMARY_LIMIT);
  const hidden = _items.length - visible.length;
  if (!_items.length) {
    return `
      <div class="fpp-grid-empty">
        <div class="fpp-empty-icon" aria-hidden="true">☁️</div>
        <div class="fpp-empty-title">今天沒事 · 真好</div>
        <div class="fpp-empty-hint">試試對話框問 AI 小幫手 · 或看看「專案」</div>
        <div class="fpp-empty-actions">
          <button type="button" class="fpp-empty-cta" data-fpp-empty="chat">與主管家對話</button>
          <button type="button" class="fpp-empty-cta-ghost" data-fpp-empty="projects">看專案</button>
        </div>
      </div>
    `;
  }
  return `
    <div class="fpp-grid" id="fpp-grid">
      ${visible.map((it, i) => `
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
      ${hidden > 0 ? `
        <button type="button" class="fpp-item fpp-item-more" data-fpp-grid-more
                aria-label="顯示其他 ${hidden} 個">
          <div class="fpp-icon fpp-icon-more" aria-hidden="true">+${hidden}</div>
          <span class="fpp-item-name">顯示全部</span>
          <span class="fpp-item-date">${_items.length} 件</span>
        </button>
      ` : ""}
    </div>
  `;
}

function _renderStatusBar() {
  // v1.65 U5 · status 改 floating chip · 縮到右下小角 · 不再橫貫
  // 沒選中時不顯 · 不浪費垂直空間
  const item = _items[_state.selected];
  if (!item) return `<div class="fpp-status fpp-status-empty"></div>`;
  return `
    <div class="fpp-status fpp-status-chip">
      <span class="fpp-status-dot" aria-hidden="true"></span>
      <span>${escapeHtml(item.name)}</span>
      ${item.unread ? `<span class="fpp-status-badge">${item.unread}</span>` : ""}
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
  const form = _root.querySelector("#today-composer-form");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    window.app?.submitTodayComposer?.(e);
  });
  _root.querySelector(".fpp-composer-submit")?.addEventListener("click", (e) => {
    // Dynamic toolbar renderers can bypass the legacy app-level submit listener.
    // Keep the visible send button explicit while Enter still uses the form submit path.
    e.preventDefault();
    window.app?.submitTodayComposer?.(e);
  });
  _root.querySelector("[data-today-pick-file]")?.addEventListener("click", (e) => {
    e.preventDefault();
    window.app?.pickTodayFiles?.();
  });
  _root.querySelector("#today-file-input")?.addEventListener("change", (e) => {
    window.app?.addTodayFiles?.(Array.from(e.target.files || []));
    e.target.value = "";
  });
}

function _bindGrid() {
  // v1.46 calm · 「+N 顯示全部」按鈕
  _root.querySelector("[data-fpp-grid-more]")?.addEventListener("click", () => {
    _state.gridExpanded = true;
    _renderGridOnly();
  });
  _root.querySelectorAll("[data-fpp-item]:not([data-fpp-grid-more])").forEach(btn => {
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
  // v1.65 U8 · 空狀態 CTA
  _root.querySelectorAll("[data-fpp-empty]").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.fppEmpty;
      if (action === "chat") window.chat?.open?.("00", "");
      else if (action === "projects") window.app?.showView?.("projects");
    });
  });
}

function _bindSegments() {
  _root.querySelectorAll("[data-fpp-segment]").forEach(b => {
    b.addEventListener("click", (e) => {
      // 內部 edit 按鈕點擊不觸發 segment 切換
      if (e.target.closest("[data-fpp-seg-edit]")) return;
      const k = b.dataset.fppSegment;
      // v1.49 · 不再 mutate SEGMENTS · 純粹 derive from _state.segment
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
  // v1.46 calm · 「更多 N ▾」展開所有 segments
  _root.querySelector("[data-fpp-segments-more]")?.addEventListener("click", () => {
    _state.segmentsExpanded = true;
    _renderSegmentsOnly();
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
  const FIELDS = ["工作區", "回應狀態", "上次活動", "對話標題", "未讀數", "提及我", "專案", "AI 小幫手活動"];
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
      // 重新訪問時重畫一次,讓最近專案與附件狀態保持同步。
      _render();
      await _fetchSuggestions();
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

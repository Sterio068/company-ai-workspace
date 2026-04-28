/**
 * Launcher · v4 主程式(ES module · entry)
 *
 * 架構:
 *   - modules/config.js     ← 靜態常數 (CORE_AGENTS / SKILLS / STAGES)
 *   - modules/util.js       ← 純工具 (escapeHtml / timeAgo / …)
 *   - modules/auth.js       ← LibreChat JWT
 *   - modules/projects.js   ← Projects store
 *   - modules/modal.js      ← Modal v2
 *   - modules/toast.js      ← Toast
 *   - modules/palette.js    ← ⌘K
 *   - modules/shortcuts.js  ← ? overlay
 *   - modules/health.js     ← Service health
 *   - modules/mobile.js     ← 漢堡選單
 *   - modules/chat.js       ← 路線 A 內建對話
 *   - modules/voice.js      ← 語音輸入
 *   - modules/accounting.js / admin.js / tenders.js / workflows.js / crm.js  ← Views
 *
 * 本檔 (app.js) 只負責:
 *   1. 登入 + User
 *   2. Dashboard render (5 Workspace / frequent chips / projects-preview / 最近對話)
 *   3. Projects view CRUD
 *   4. Skills view render
 *   5. View 切換 + 鍵盤快捷鍵
 *   6. 注入各 module 的 store 依賴
 */

import {
  API,
  AI_PROVIDERS,
  AI_PROVIDER_KEY,
  DEFAULT_AI_PROVIDER,
  CORE_AGENTS,
  SKILLS,
  CLAUDE_SKILLS,
  WORKSPACES,
  WORKSPACE_TO_AGENT,
  WORKSPACE_DRAFTS,
  agentRoleName,
  ATTACHMENT,
} from "./modules/config.js";
import { escapeHtml, formatDate, greetingFor, timeAgo, formatMoney, skeletonCards, localizeVisibleText, copyToClipboard } from "./modules/util.js";
import { refreshAuthWithLock, authFetch, setUserEmail } from "./modules/auth.js";
// v1.7 · 暴露 authFetch 給 ESM 外的模組(branding.js inline form / 未來 plugin)
if (typeof window !== "undefined") window.authFetch = authFetch;
import { store } from "./modules/store.js";  // v1.11 · central state(architect R1 第一階段)
import { Projects } from "./modules/projects.js";
import { modal } from "./modules/modal.js";
import { toast } from "./modules/toast.js";
import { palette } from "./modules/palette.js";
import { theme } from "./modules/theme.js";  // v1.3 A2 · 從 app.js 抽出
import { activateLauncherView, isRoutableView, routeFromHash } from "./modules/router.js";
// v1.4 macOS · PWA detection(自動 init · 套 [data-pwa] · menubar 才出)
import "./modules/macos/pwa-detect.js";
// v1.4 macOS · Dock(底部 · vibrancy · hover magnification · default seed 7 agents)
import { dock as macosDock } from "./modules/macos/dock.js";
// v1.4 macOS · Menubar(頂部 · 6 menu + 5 status item)· Sprint B Phase 3
import { menubar as macosMenubar } from "./modules/macos/menubar.js";
// v1.4 macOS · Sprint C Phase 6 · 全套鍵盤快捷(全域 listen)
import "./modules/macos/shortcuts.js";
// v1.5 · Dashboard F++ 主畫面 IA 重構(toolbar + mini-Today + segments + grid + status)
import { dashboardFpp } from "./modules/macos/dashboard-fpp.js";
// v1.7 · Multi-tenant Branding(動態品牌名 · 取代 hardcode 「公司」)
import { brand } from "./modules/branding.js";
import { shortcuts } from "./modules/shortcuts.js";
import { health } from "./modules/health.js";
import { mobile } from "./modules/mobile.js";
import { setupGlobalKeyboard } from "./modules/keyboard.js";
import { installDomActions } from "./modules/dom-actions.js";
import { chat } from "./modules/chat.js";
import { voice } from "./modules/voice.js";
import { knowledge } from "./modules/knowledge.js";  // 跟首頁 file_search 緊耦合 · 不延遲
import { help } from "./modules/help.js";  // 多 view 用到 + onboarding · 不延遲
// ROADMAP §11.2 · single source of truth · 取代 cross-module currentProject 散處
import { projectStore, KEYS as STATE_KEYS } from "./modules/state/project-store.js";

// v1.58 perf · 11 個 view 模組改 lazy load · 第一次點該 view 才下載 + parse
// 首屏估省 40-60 KB JS · LCP -150~250ms(尤其遠端 Cloudflare Tunnel)
// 注意:loader 回 Promise · 呼叫端必須 await · 已 cache 的同步回(快)
const _viewModuleLoaders = {
  accounting: () => import("./modules/accounting.js").then(m => m.accounting),
  admin:      () => import("./modules/admin.js").then(m => m.admin),
  userMgmt:   () => import("./modules/user_mgmt.js").then(m => m.userMgmt),
  design:     () => import("./modules/design.js").then(m => m.design),
  meeting:    () => import("./modules/meeting.js").then(m => m.meeting),
  media:      () => import("./modules/media.js").then(m => m.media),
  social:     () => import("./modules/social.js").then(m => m.social),
  siteSurvey: () => import("./modules/site_survey.js").then(m => m.siteSurvey),
  tenders:    () => import("./modules/tenders.js").then(m => m.tenders),
  workflows:  () => import("./modules/workflows.js").then(m => m.workflows),
  crm:        () => import("./modules/crm.js").then(m => m.crm),
  notebooklm: () => import("./modules/notebooklm.js").then(m => m.notebooklm),
};
const _viewCache = {};
async function _view(name) {
  if (_viewCache[name]) return _viewCache[name];
  const loader = _viewModuleLoaders[name];
  if (!loader) throw new Error(`unknown view module: ${name}`);
  _viewCache[name] = await loader();
  return _viewCache[name];
}
// 暴露給 console / palette / debug
if (typeof window !== "undefined") window._loadView = _view;
import { installGlobalErrorHandler } from "./modules/errors.js";
import { tpl, renderList } from "./modules/tpl.js";
import { buildPaletteItems } from "./modules/palette-items.js";
import {
  filterProjects,
  projectColor,
  projectDeadline,
  projectPromptContext,
  projectUpdatedAt,
  projectUpdatedTs,
  selectDefaultProjectId,
  sortProjects,
  workActionSuggestions,
  workHandoffSaveConfig,
  workKind,
  workReadiness,
} from "./modules/work-package.js";

// v1.50 · 從 config.js ATTACHMENT 拉共享規格 · 與 chat.js 一致
const TODAY_MAX_ATTACHMENT_COUNT = ATTACHMENT.MAX_COUNT;
const TODAY_MAX_ATTACHMENT_BYTES = ATTACHMENT.MAX_BYTES;
const TODAY_SUPPORTED_ATTACHMENT_EXT = ATTACHMENT.SUPPORTED_EXT;

// ============================================================
//  App Controller
// ============================================================
export const app = {
  user: null,
  agents: [],
  currentView: "dashboard",
  activeWorkspace: 1,
  editingProjectId: null,
  _projectModalReturnFocus: null,
  _projectModalKeyHandler: null,
  activeProjectId: null,
  projectFilter: "all",
  projectSearch: "",
  // v1.21 · aiProvider 完全搬到 store · this.aiProvider 不再保存(architect R1 god object 縮圈)
  // 讀:store.get("engine") · 寫:store.set("engine", ...)
  todayAttachments: [],

  async init() {
    installGlobalErrorHandler();

    // 認證
    try {
      const data = await refreshAuthWithLock();
      this.user = data.user || data;
      setUserEmail(this.user?.email);  // 讓 authFetch 帶 X-User-Email · 給後端 RBAC 用
    } catch (e) {
      console.warn("[AI Workspace] 認證失敗:", e);
      window.location.href = "/login";
      return;
    }

    this.setupGreeting();
    this.setupUser();
    this.applyTheme();

    // v1.7 · 載品牌 + 套到 DOM(取代 hardcode 「公司」)
    try {
      await brand.load();
      this._applyBranding();
      brand.subscribe(() => this._applyBranding());
    } catch (e) {
      console.warn("[brand] load failed", e);
    }

    // 注入 chat / crm 的 store 依賴
    // v1.21 · provider 改直接讀 store · 不再走 this.aiProvider mirror
    chat.bind({ agents: () => this.agents, user: () => this.user, provider: () => this.getAIProvider() });
    // v1.58 lazy · crm.setUser 改在 _view("crm").load() 時呼叫(見 handleHashChange)
    palette.bind(() => this._paletteItems());
    // V1.1 §E-3 · 知識庫全文搜尋加入 palette(async · debounced)
    palette.addAsyncSource((q) => knowledge.paletteSearch(q));
    // 多分頁同步:其他分頁改了專案,本分頁自動 re-render(避免髒清單)
    Projects.bindOnChange(() => {
      this.renderProjects();
      this.renderProjectsPreview();
      this.renderTodayWorkbench();
      this.renderWorkDetail();
    });

    // v1.8 perf · loadAgents 不阻擋首頁渲染 · 並進 Promise.all
    // (findAgentByNum 是 UI helper · 渲染後才用)
    await Promise.all([
      this.loadAgents(),
      this.loadConversations(),
      this.loadUsage(),
      this.loadROI(),
      Projects.refresh(),
    ]);

    this.renderFrequent();
    this.renderWorkspaceCards();
    this.renderTodayWorkbench();
    this.renderProjects();
    this.renderProjectsPreview();
    this.renderWorkDetail();
    this.renderSkills();
    this.renderAIProvider();
    this._bindAiSourcePanel();

    this.setupKeyboard();
    this.setupNavigation();
    this.setupTodayActions();
    chat.bindFileInput();
    localizeVisibleText(document.getElementById("app"));

    // Projects 上線狀態提示
    document.querySelectorAll("[data-project-status]").forEach(notice => {
      if (Projects._online) {
        notice.innerHTML = "✅ 專案資料已連接 MongoDB · 團隊共享";
        notice.style.background = "color-mix(in srgb, var(--green) 8%, transparent)";
        notice.style.color = "var(--green)";
      }
    });

    // v1.70 · Dashboard F++ 必須在 app 顯示前接管,避免舊 dashboard textarea 短暫可見
    // 造成使用者或 E2E 先輸入後又被 F++ 重繪清空。
    try {
      const dashView = document.querySelector('.view[data-view="dashboard"]');
      if (dashView) dashboardFpp.init(dashView);
    } catch (e) {
      console.warn("[fpp] dashboard init failed", e);
    }

    document.getElementById("loading").style.display = "none";
    document.getElementById("app").hidden = false;

    health.start();
    mobile.init();
    // 主備源 health · 啟動拉一次 + 每 60s refresh(失敗 silent)
    // 保留 interval id · 重複 init 時清前一個避免疊
    this.refreshAIProviderHealth();
    if (this._healthInterval) clearInterval(this._healthInterval);
    this._healthInterval = setInterval(() => this.refreshAIProviderHealth(), 60_000);
    // v1.4 macOS · Dock 啟動 · default seed 7 個 agent
    // v1.46 calm mode · 預設關 dock(底部 7 彩色 icon 視覺重)
    // 設 localStorage chengfu-dock-show=1 才出
    if (localStorage.getItem("chengfu-dock-show") === "1") {
      try {
        macosDock.init();
      } catch (e) {
        console.warn("[macos] dock init failed", e);
      }
    }
    // v1.4 macOS · Menubar(頂部)· Sprint B Phase 3
    try {
      macosMenubar.init();
    } catch (e) {
      console.warn("[macos] menubar init failed", e);
    }
    // v1.17 · 確保 body[data-active-view] 預設值為 dashboard
    // (handleHashChange 只在有 hash 時才 call showView · 開啟首頁無 hash → 從未設過)
    // 這個 attr 是 dashboard sidebar 收起 CSS 的 trigger
    if (!document.body.dataset.activeView) {
      document.body.dataset.activeView = this.currentView || "dashboard";
    }
    // v1.22 a11y · 初始 sidebar 收合狀態(showView 在 hash 路由時才 fire,首頁進來無 hash → 自己設)
    const _sb = document.querySelector(".sidebar");
    if (_sb) {
      const _collapsed = (this.currentView || "dashboard") === "dashboard";
      _sb.setAttribute("aria-expanded", _collapsed ? "false" : "true");
      _sb.setAttribute("aria-label", _collapsed
        ? "主導覽(已收合 · 滑入或聚焦展開)"
        : "主導覽");
    }

    // 首次訪問 onboarding
    if (!localStorage.getItem("chengfu-tour-done") && window.tour) {
      setTimeout(() => {
        if (!localStorage.getItem("chengfu-tour-done")) window.tour.start();
      }, 500);
    }

    // URL hash → view
    this.handleHashChange();
    window.addEventListener("hashchange", () => this.handleHashChange());

    // v1.36 a11y · F3 修 · <details> summary 同步 aria-expanded
    // VoiceOver 在 macOS Safari 不會主動播 details open 變化 · 加 ARIA 自管
    document.querySelectorAll("details > summary").forEach(summary => {
      const details = summary.parentElement;
      summary.setAttribute("aria-expanded", details.open ? "true" : "false");
      details.addEventListener("toggle", () => {
        summary.setAttribute("aria-expanded", details.open ? "true" : "false");
      });
    });
  },

  handleHashChange() {
    const rawHash = String(window.location.hash || "").replace("#", "");
    const workspaceMatch = rawHash.match(/^workspace-([1-5])$/);
    if (workspaceMatch) {
      this.openWorkspace(Number(workspaceMatch[1]), { replaceHash: false });
      return;
    }
    const hash = routeFromHash();
    if (isRoutableView(hash)) {
      this.showView(hash);
    }
  },

  // ---------- AI Provider (v1.21 · 完全 store-backed · this.aiProvider 不再保存) ----------
  normalizeAIProvider(provider) {
    return AI_PROVIDERS[provider] ? provider : DEFAULT_AI_PROVIDER;
  },

  getAIProvider() {
    // 唯一 source of truth = store
    const cur = store.get("engine");
    return this.normalizeAIProvider(cur);
  },

  // Delegated handler · ai-source panel 兩個 row 共用 · 取代 inline onclick
  // (一致 J2 retry button 改法 · 不留 inline handler)
  _bindAiSourcePanel() {
    const panel = document.querySelector(".ai-source-panel");
    if (!panel || panel._bound) return;
    panel._bound = true;
    panel.addEventListener("click", e => {
      const row = e.target.closest(".ai-source-row[data-ai-provider]");
      if (!row) return;
      this.setAIProvider(row.dataset.aiProvider);
    });
  },

  setAIProvider(provider) {
    // C1 client-side admin gate · 防 USER 從 console 切備援拉高成本
    // 真 enforcement 在 LibreChat server (modelSpecs / preset 限定) · 此處先 UI 阻擋
    if (this.user?.role !== "ADMIN") {
      toast.warn("AI 引擎切換僅管理員可用");
      return;
    }
    const next = this.normalizeAIProvider(provider);
    if (next === this.getAIProvider()) {
      this.renderAIProvider();
      return;
    }
    // store.set 自動 persist(localStorage)+ fire engine-changed event
    store.set("engine", next);
    this.renderAIProvider();
    const meta = AI_PROVIDERS[next];
    toast.success(`AI 引擎已切換為 ${meta.label} · 新對話生效`);
  },

  // 主備源面板 render
  // - row.active toggle(主力/備援哪個正在用)
  // - state 文字(使用中 / 待機)+ foot 顯示目前模型描述
  // - 非 admin: aria-disabled + tabindex=-1 防鍵盤聚焦但仍視覺呈現(WCAG 4.1.2)
  renderAIProvider() {
    const provider = this.getAIProvider();
    const meta = AI_PROVIDERS[provider] || AI_PROVIDERS[DEFAULT_AI_PROVIDER];
    document.documentElement.dataset.aiProvider = provider;

    const isAdmin = this.user?.role === "ADMIN";
    document.querySelectorAll(".ai-source-row[data-ai-provider]").forEach(row => {
      const id = row.dataset.aiProvider;
      const rowMeta = AI_PROVIDERS[id];
      if (!rowMeta) return;
      const active = id === provider;
      row.classList.toggle("active", active);
      row.setAttribute("aria-pressed", active ? "true" : "false");
      row.title = active ? `目前使用 ${rowMeta.label}` : (isAdmin ? `切換到 ${rowMeta.label}` : `${rowMeta.label}(僅管理員可切換)`);
      // 非 admin · 鍵盤跳過 + 標 disabled · CSS pointer-events:none 配合
      if (isAdmin) {
        row.removeAttribute("aria-disabled");
        row.removeAttribute("tabindex");
      } else {
        row.setAttribute("aria-disabled", "true");
        row.setAttribute("tabindex", "-1");
      }
      const stateEl = row.querySelector(`[data-ai-source-state="${id}"]`);
      if (stateEl) stateEl.textContent = active ? "使用中" : "待機";
    });

    const foot = document.getElementById("ai-source-foot");
    if (foot) foot.textContent = meta.desc;
  },

  // 拉 backend health 並更新主備源連線指示
  // - 失敗 / 沒接後端時保持「unknown」(灰)· 不阻擋畫面
  // - state 用 icon shape + 顏色雙重編碼(WCAG 1.4.1 不只靠顏色)
  async refreshAIProviderHealth() {
    const dots = document.querySelectorAll("[data-ai-source-health]");
    if (!dots.length) return;
    const ICON_MAP = { ok: "●", warn: "▲", down: "✕", unknown: "○" };
    const LABEL_MAP = { ok: "已連線", warn: "部分功能受限", down: "無法連線", unknown: "狀態未知" };
    const setDot = (dot, state, latency) => {
      dot.dataset.state = state;
      dot.textContent = ICON_MAP[state] || ICON_MAP.unknown;
      const label = LABEL_MAP[state] || LABEL_MAP.unknown;
      const lat = latency ? ` · ${latency}ms` : "";
      dot.title = `${label}${lat}`;
      dot.setAttribute("aria-label", `連線狀態:${label}`);
    };
    try {
      const r = await fetch("/api-accounting/health/ai-providers", {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      const map = j?.providers || {};
      dots.forEach(dot => {
        const info = map[dot.dataset.aiSourceHealth];
        setDot(dot, info?.state || "unknown", info?.latency_ms);
      });
    } catch {
      dots.forEach(d => setDot(d, "unknown"));
    }
  },

  // ---------- Setup ----------
  setupGreeting() {
    const now = new Date();
    const name = this.user?.name || this.user?.username || "同仁";
    const greet = document.getElementById("greeting");
    if (greet) greet.textContent = `${greetingFor(now.getHours())},${name} 👋`;
    const date = document.getElementById("date-line");
    if (date) date.textContent = formatDate(now);
  },

  /** v1.7 · 把 brand 資訊套到 DOM(data-brand-* 屬性 + document.title) */
  _applyBranding() {
    const s = brand.state;
    document.title = s.app_name;
    document.querySelectorAll("[data-brand-app-name]").forEach(el => el.textContent = s.app_name);
    document.querySelectorAll("[data-brand-tagline]").forEach(el => el.textContent = s.tagline);
    document.querySelectorAll("[data-brand-short]").forEach(el => el.textContent = brand.companyShort);
    document.querySelectorAll("[data-brand-title]").forEach(el => el.textContent = s.app_name);
    // populate admin 設定表單
    document.querySelectorAll("[data-brand-input]").forEach(el => {
      const k = el.dataset.brandInput;
      if (s[k] !== undefined && el.value !== s[k]) el.value = s[k] || "";
    });
  },

  setupUser() {
    const name = this.user?.name || this.user?.username || "使用者";
    setText("user-name", name);
    setText("user-avatar", name.charAt(0).toUpperCase());
    setText("user-role", this.user?.role === "ADMIN" ? "管理員" : "同仁");
    if (this.user?.role === "ADMIN") {
      const nav = document.getElementById("admin-nav");
      if (nav) nav.style.display = "";
      const opsNav = document.getElementById("ops-nav");
      if (opsNav) opsNav.style.display = "";
      // v1.3 · User Management UI(admin 建同仁)
      const usersNav = document.getElementById("users-nav");
      if (usersNav) usersNav.style.display = "";
      document.documentElement.dataset.role = "admin";
      document.documentElement.dataset.userEmail = this.user.email || "";
      // vNext C · 系統自動更新通知(admin only · lazy import 不擋首屏)
      import("./modules/update-notifier.js").then(({ updateNotifier }) => {
        updateNotifier.init(true);
      }).catch(() => {/* 沒裝好不擋 */});
    }
  },

  setupNavigation() {
    document.querySelectorAll(".nav-item").forEach(el => {
      if (el instanceof HTMLAnchorElement && !el.getAttribute("href") && el.dataset.view) {
        el.setAttribute("href", el.dataset.view === "dashboard" ? "#" : `#${el.dataset.view}`);
      }
      el.addEventListener("click", e => {
        e.preventDefault();
        this.navigateToView(el.dataset.view);
      });
    });
    document.querySelectorAll(".sidebar-item.ws-nav").forEach(el => {
      if (el instanceof HTMLAnchorElement && !el.getAttribute("href") && el.dataset.ws) {
        el.setAttribute("href", `#workspace-${el.dataset.ws}`);
      }
      el.addEventListener("click", e => {
        e.preventDefault();
        this.navigateToWorkspace(parseInt(el.dataset.ws, 10));
      });
    });
    document.querySelectorAll("[data-slash]").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        this.slashCmd(el.dataset.slash);
      });
    });
    document.querySelectorAll(".sidebar-item[data-agent]").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        this.openAgent(el.dataset.agent);
      });
    });
    document.querySelectorAll(".filter-chip[data-filter]").forEach(el => {
      el.addEventListener("click", () => {
        this.projectFilter = el.dataset.filter;
        document.querySelectorAll(".filter-chip[data-filter]").forEach(x => x.classList.remove("active"));
        el.classList.add("active");
        this.renderProjects();
      });
    });
  },

  navigateToView(view) {
    if (!view) return;
    const nextHash = view === "dashboard" ? "" : `#${view}`;
    if (window.location.hash === nextHash) {
      this.handleHashChange();
      return;
    }
    if (view === "dashboard") {
      history.pushState("", document.title, window.location.pathname);
      this.showView("dashboard");
      return;
    }
    window.location.hash = nextHash;
  },

  navigateToWorkspace(n) {
    if (!n) return;
    const nextHash = `#workspace-${n}`;
    if (window.location.hash === nextHash) {
      this.handleHashChange();
      return;
    }
    window.location.hash = nextHash;
  },

  setupTodayActions() {
    document.getElementById("today-composer-form")?.addEventListener("submit", e => {
      this.submitTodayComposer(e);
    });
    document.querySelectorAll("[data-today-pick-file]").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        this.pickTodayFiles();
      });
    });
    document.getElementById("today-file-input")?.addEventListener("change", e => {
      this.addTodayFiles(Array.from(e.target.files || []));
      e.target.value = "";
    });
    const form = document.getElementById("today-composer-form");
    if (form && form.dataset.dropBound !== "true") {
      form.dataset.dropBound = "true";
      form.addEventListener("dragover", e => {
        if (!e.dataTransfer?.types?.includes("Files")) return;
        e.preventDefault();
        form.classList.add("drop-active");
      });
      form.addEventListener("dragleave", e => {
        if (!form.contains(e.relatedTarget)) form.classList.remove("drop-active");
      });
      form.addEventListener("drop", e => {
        if (!e.dataTransfer?.files?.length) return;
        e.preventDefault();
        form.classList.remove("drop-active");
        this.addTodayFiles(Array.from(e.dataTransfer.files));
      });
    }
    document.querySelectorAll("[data-today-new-project]").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        this.newProject();
      });
    });
    document.querySelectorAll("[data-today-show-projects]").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        this.showView("projects");
      });
    });
  },

  pickTodayFiles() {
    document.getElementById("today-file-input")?.click();
  },

  addTodayFiles(files = []) {
    const accepted = [];
    for (const file of files) {
      const validation = this._validateTodayAttachment(file);
      if (!validation.ok) {
        toast.warn(validation.message);
        continue;
      }
      const duplicate = this.todayAttachments.some(item =>
        item.file.name === file.name &&
        item.file.size === file.size &&
        item.file.lastModified === file.lastModified
      ) || accepted.some(item =>
        item.file.name === file.name &&
        item.file.size === file.size &&
        item.file.lastModified === file.lastModified
      );
      if (duplicate) continue;
      if (this.todayAttachments.length + accepted.length >= TODAY_MAX_ATTACHMENT_COUNT) {
        toast.warn(`一次最多附 ${TODAY_MAX_ATTACHMENT_COUNT} 個檔案`);
        break;
      }
      accepted.push({
        id: crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`,
        file,
      });
    }
    if (!accepted.length) return;
    this.todayAttachments = [...this.todayAttachments, ...accepted];
    this.renderTodayAttachments();
    toast.success(`已加入 ${accepted.length} 個附件`);
  },

  removeTodayFile(id) {
    this.todayAttachments = this.todayAttachments.filter(item => item.id !== id);
    this.renderTodayAttachments();
  },

  renderTodayAttachments() {
    const root = document.getElementById("today-file-ribbon");
    if (!root) return;
    root.innerHTML = "";
    root.hidden = this.todayAttachments.length === 0;
    for (const item of this.todayAttachments) {
      const chip = document.createElement("div");
      chip.className = "today-file-chip";
      chip.innerHTML = `
        <span class="today-file-name">📎 ${escapeHtml(item.file.name)}</span>
        <span class="today-file-size">${escapeHtml(this._formatBytes(item.file.size))}</span>
        <button type="button" aria-label="移除 ${escapeHtml(item.file.name)}">✕</button>
      `;
      chip.querySelector("button")?.addEventListener("click", () => this.removeTodayFile(item.id));
      root.appendChild(chip);
    }
  },

  _validateTodayAttachment(file) {
    if (!file) return { ok: false, message: "檔案讀取失敗" };
    if (file.size > TODAY_MAX_ATTACHMENT_BYTES) {
      return { ok: false, message: `${file.name} 超過 25MB,請壓縮或分段上傳` };
    }
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    if (!TODAY_SUPPORTED_ATTACHMENT_EXT.has(ext)) {
      return { ok: false, message: `${file.name} 格式暫不支援` };
    }
    return { ok: true };
  },

  _formatBytes(bytes = 0) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  },

  searchProjects(event) {
    this.projectSearch = (event?.target?.value || "").trim().toLowerCase();
    this.renderProjects();
  },

  showView(view) {
    this.currentView = view;
    activateLauncherView(view);
    // v1.4 macOS · body[data-active-view] · 給 dock CSS 在 chat view 隱藏(Issue 6)
    document.body.dataset.activeView = view;
    // v1.22 a11y · sidebar 收合狀態 announce 給 screen reader(WCAG 4.1.2)
    const sidebar = document.querySelector(".sidebar");
    if (sidebar) {
      const collapsed = view === "dashboard";
      sidebar.setAttribute("aria-expanded", collapsed ? "false" : "true");
      sidebar.setAttribute("aria-label", collapsed
        ? "主導覽(已收合 · 滑入或聚焦展開)"
        : "主導覽");
    }
    if (view !== "workspace") {
      document.querySelectorAll(".sidebar-item.ws-nav").forEach(el => el.classList.remove("active"));
    }
    // vNext C · view 第一次進 · 自動 fade-in 教學提示 + 注入 ❓ 按鈕
    import("./modules/help-tip.js").then(({ helpTip }) => {
      helpTip.maybeShow(view);
      this._injectViewHelpBtn(view);
    }).catch(() => {/* helpTip 沒裝好不擋 */});
    // v1.5 · Dashboard F++ takeover(主畫面 IA 重構 · F++ v1.5 誠實版)
    if (view === "dashboard") {
      const dashView = document.querySelector('.view[data-view="dashboard"]');
      if (dashView) {
        try { dashboardFpp.init(dashView); }
        catch (e) { console.warn("[fpp] init failed", e); }
      }
    }
    // V1.1 §E-3 · 切到 knowledge 自動載入
    if (view === "knowledge") knowledge.loadBrowser();
    if (view === "notebooklm") _view("notebooklm").then(m => m.load());
    if (view === "accounting") _view("accounting").then(m => m.load());
    if (view === "admin") _view("admin").then(m => { m.load(); knowledge.loadAdmin(); });
    if (view === "tenders") _view("tenders").then(m => m.load());
    if (view === "workflows") _view("workflows").then(m => m.load());
    if (view === "crm") _view("crm").then(m => { m.setUser(this.user?.email); m.load(); });
    // 使用教學 · 切過去就 init(admin 才載 secrets)
    if (view === "help") {
      const isAdmin = this.user?.role === "ADMIN";
      help.init(isAdmin);
    }
    // v1.58 lazy · 4 個 view module 第一次點才下載
    const isAdmin = this.user?.role === "ADMIN";
    if (view === "meeting") _view("meeting").then(m => m.init());
    if (view === "media") _view("media").then(m => m.init(isAdmin));
    if (view === "social") _view("social").then(m => m.init());
    if (view === "site") _view("siteSurvey").then(m => m.init());
    // v1.3 · User Management(admin only)
    if (view === "users" && isAdmin) _view("userMgmt").then(m => m.init());
    // v1.24 perf · 從 3 次 setTimeout × 4 querySelector × 106 regex/node
    // 改成單次 1000ms debounce(view 切換時 view 內容已 stable)
    // 避免 ~80ms × 3 = 240ms 主線程阻塞
    if (this._localizeTimer) clearTimeout(this._localizeTimer);
    this._localizeTimer = setTimeout(() => {
      localizeVisibleText(document.querySelector(`.view[data-view="${view}"]`));
      localizeVisibleText(document.querySelector(".usage-aside"));
      localizeVisibleText(document.querySelector(".command-palette"));
      localizeVisibleText(document.querySelector(".chat-panel"));
    }, 250);
  },

  // vNext C · 在當前 active view header 注入 ❓ 按鈕
  _injectViewHelpBtn(view) {
    document.querySelectorAll(".view-help-btn").forEach(b => b.remove());
    const activeView = document.querySelector(`.view[data-view="${view}"].active`);
    if (!activeView) return;
    const header = activeView.querySelector(".view-header, .main-header");
    if (!header) return;
    if (header.querySelector(".view-help-btn")) return;
    // 若 header 已有 .header-actions 區 · ❓ 加進那裡(同行 · 不重疊)
    // 否則 absolute 定位到 top-right
    const actions = header.querySelector(".header-actions");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "view-help-btn";
    btn.textContent = "?";
    btn.title = "看本頁教學";
    btn.setAttribute("aria-label", "看本頁教學");
    btn.onclick = () => window.helpTip?.showFor(view);
    if (actions) {
      // inline 模式 · 加 class 給 CSS 切換 absolute → static
      btn.classList.add("inline");
      actions.insertBefore(btn, actions.firstChild);
    } else {
      if (getComputedStyle(header).position === "static") header.style.position = "relative";
      header.appendChild(btn);
    }
  },

  openCreateSource() { knowledge.openCreateModal(); },

  // ---------- Data loading ----------
  async loadAgents() {
    try {
      const resp = await authFetch(API.agents);
      if (!resp.ok) throw new Error(resp.status);
      const r = await resp.json();
      this.agents = Array.isArray(r) ? r : (r.agents || r.data || []);
    } catch (e) {
      console.warn("載入 Agent 失敗", e);
      this.agents = [];
    }
  },

  findAgentByNum(num) {
    const meta = CORE_AGENTS.find(a => a.num === num);
    if (!meta) return null;
    // 先試 metadata.number(若未被 zod strip),再 fallback 到名稱含 meta.name
    return this.agents.find(a =>
      (a.metadata && a.metadata.number === num) ||
      (a.name || "").includes(meta.name)
    );
  },

  async loadConversations() {
    const container = document.getElementById("recent-list");
    if (!container) return;
    container.innerHTML = skeletonCards(3);
    try {
      const resp = await authFetch(API.convos);
      if (!resp.ok) throw new Error(resp.status);
      const r = await resp.json();
      const convos = Array.isArray(r) ? r : (r.conversations || r.data || []);
      if (convos.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">💬</div>
            <div class="empty-state-title">尚無對話</div>
            <div class="empty-state-hint">從 5 個工作區選一個 · 或按 ⌘1-5 快速切</div>
          </div>`;
        return;
      }
      const dotColors = ["#D14B43", "#D8851E", "#8C5CB1", "#5AB174", "#3F86C9"];
      const nodes = convos.slice(0, 5).map((c, i) => {
        const agent = this.agents.find(a => a.id === (c.agent_id || c.agentId)) || {};
        const label = (agent.name || "").replace(/^\W+\s*[\w\W]*·\s*/, "").slice(0, 8) || "對話";
        const color = dotColors[i % dotColors.length];
        const node = tpl("tpl-recent-item", {
          title: c.title || "未命名對話",
          preset: label,
          time: timeAgo(c.updatedAt || c.createdAt),
        }, {
          attrs: { href: `/chat/c/${c.conversationId || c.id}` },
        });
        const dot = node.querySelector("[data-slot='dotColor']") || node.querySelector(".recent-dot");
        if (dot) dot.style.background = color;
        return node;
      });
      renderList(container, nodes);
    } catch (e) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">😓</div>
          <div class="empty-state-title">無法載入對話</div>
          <div class="empty-state-hint">${(e?.message || "網路或後端錯")}</div>
          <button class="btn-ghost" data-action="app.loadConversations" style="margin-top:12px">重試</button>
        </div>`;
    }
  },

  async loadUsage() {
    try {
      const resp = await authFetch(API.balance);
      if (!resp.ok) throw new Error(resp.status);
      const r = await resp.json();
      const used = r.monthlyUsage || 0;
      const limit = r.monthlyLimit || 1500000;
      const pct = Math.min(100, Math.round(used / limit * 100));
      setText("usage-used", (used / 10000).toFixed(1) + "萬");
      setText("usage-limit", (limit / 10000).toFixed(0) + "萬");
      setText("usage-remaining", Math.max(0, Math.round((limit - used) / 10000)) + "萬");
      const fill = document.getElementById("usage-fill");
      if (fill) fill.style.width = pct + "%";
      const today = new Date().getDate();
      setText("usage-avg", Math.round(used / Math.max(1, today) / 1000) + "k");
    } catch (e) {
      // v1.3 batch6 · 別吞 quota 失敗 · 顯示 "—" 而非 misleading 0
      console.warn("[usage] loadUsage failed:", e);
      setText("usage-used", "—");
      setText("usage-limit", "—");
      setText("usage-remaining", "—");
      setText("usage-avg", "—");
      const card = document.querySelector(".usage-card");
      if (card) {
        card.classList.add("empty");
        card.title = "用量載入失敗 · 點重試或檢查 accounting 服務";
      }
    }
  },

  async loadROI() {
    // 3 個 ROI 儀表 · admin 看得到數字,同仁看 fallback
    const isAdmin = this.user?.role === "ADMIN";
    // 預算進度
    const budgetEl = document.getElementById("roi-budget-card");
    const showBudgetFallback = (subtitle = "智慧助理可正常使用 · 成本服務稍後再試") => {
      setText("roi-budget-value", "成本統計暫不可用");
      setText("roi-budget-sub", subtitle);
      const fill = document.getElementById("roi-budget-fill");
      if (fill) { fill.style.width = "0%"; fill.className = "roi-fill warn"; }
    };

    // v1.36 perf F-1 · 兩個獨立 fetch 改 Promise.allSettled 並行
    // 原本 budget 跑完才發 funnel · RTT 相加 · 改並行省 1 RTT(~200-400ms)
    const _budgetReq = (budgetEl && isAdmin)
      ? authFetch("/api-accounting/admin/budget-status").catch(e => ({ _err: e }))
      : Promise.resolve(null);
    const _funnelReq = authFetch("/api-accounting/admin/tender-funnel").catch(e => ({ _err: e }));
    const [budgetResp, funnelResp] = await Promise.all([_budgetReq, _funnelReq]);

    // ---- 處理 budget ----
    if (budgetEl && isAdmin) {
      try {
        if (budgetResp?._err) throw budgetResp._err;
        if (!budgetResp?.ok) throw new Error(`budget-status ${budgetResp?.status}`);
        const d = await budgetResp.json();
        if (d.data_source_ok === false) {
          console.warn("[roi] budget data source issue:", d.data_source_issue || "unknown");
          setText("roi-budget-value", "成本統計待校正");
          setText("roi-budget-sub", "智慧助理可正常使用 · 用量格式需同步");
          const fill = document.getElementById("roi-budget-fill");
          if (fill) { fill.style.width = "0%"; fill.className = "roi-fill warn"; }
        } else {
          setText("roi-budget-value", `NT$ ${Number(d.spent_ntd).toLocaleString()}`);
          setText("roi-budget-sub", `預算 NT$ ${Number(d.budget_ntd).toLocaleString()} · ${d.pct}% · 定價 ${d.pricing_version || ""}`);
          const fill = document.getElementById("roi-budget-fill");
          if (fill) {
            fill.style.width = Math.min(100, d.pct) + "%";
            fill.className = "roi-fill " + (d.alert_level === "over" ? "over" : d.alert_level === "warn" ? "warn" : "");
          }
        }
      } catch (e) {
        console.warn("[roi] budget-status failed:", e);
        showBudgetFallback();
      }
    } else if (budgetEl) {
      setText("roi-budget-value", "—");
      setText("roi-budget-sub", "管理員才看得到");
    }

    // ---- 處理 funnel(標案漏斗 · admin 全員皆可見) ----
    try {
      if (funnelResp?._err) throw funnelResp._err;
      if (funnelResp?.ok) {
        const d = await funnelResp.json();
        const f = d.funnel || {};
        const el = document.getElementById("roi-funnel-value");
        if (el) {
          el.innerHTML = `
            <span class="f-num">${f.new_discovered || 0}</span>
            <span class="f-sep">→</span>
            <span class="f-num">${f.interested || 0}</span>
            <span class="f-sep">→</span>
            <span class="f-num">${f.proposing || 0}</span>
            <span class="f-sep">→</span>
            <span class="f-num">${f.submitted || 0}</span>
            <span class="f-sep">→</span>
            <span class="f-num f-win">${f.won || 0}</span>
          `;
        }
      }
    } catch (e) {
      console.warn("[roi] tender-funnel failed:", e);
    }
    // 本週 AI 幫你做幾件(loadUsage 已放 stat-this-week-tasks)· 抓相同數值到 ROI 卡
    const tasks = document.getElementById("stat-this-week-tasks")?.textContent;
    if (tasks && tasks !== "—") setText("roi-tasks-value", tasks);
    else {
      const counts = JSON.parse(localStorage.getItem("chengfu-agent-usage") || "{}");
      const total = Object.values(counts).reduce((s, n) => s + (n || 0), 0);
      setText("roi-tasks-value", String(total));
    }
  },

  // ---------- Render · Dashboard ----------
  renderFrequent() {
    const root = document.getElementById("frequent-chips");
    if (!root) return;
    const counts = JSON.parse(localStorage.getItem("chengfu-agent-usage") || "{}");
    const sorted = CORE_AGENTS
      .filter(a => counts[a.num])
      .sort((a, b) => (counts[b.num] || 0) - (counts[a.num] || 0))
      .slice(0, 6);
    if (sorted.length === 0) return;
    const nodes = sorted.map(a => tpl("tpl-chip", {
      emoji: a.emoji,
      name:  agentRoleName(a),
      badge: `${counts[a.num]} 次`,
    }, {
      attrs: { "data-agent-num": a.num },
      onclick: () => this.openAgent(a.num),
    }));
    renderList(root, nodes);
  },

  renderTodayWorkbench() {
    const root = document.getElementById("today-workbench");
    if (!root) return;
    const projects = Projects.load()
      .filter(p => p.status !== "closed")
      .sort((a, b) => {
        const ad = a.deadline ? new Date(a.deadline).getTime() : Number.MAX_SAFE_INTEGER;
        const bd = b.deadline ? new Date(b.deadline).getTime() : Number.MAX_SAFE_INTEGER;
        return ad - bd;
      });
    const nextProject = projects[0];
    const projectNext = nextProject?.handoff?.next_actions?.[0]
      || nextProject?.description
      || "打開交棒卡,補上下一步與素材來源";

    const cards = [
      nextProject ? {
        kind: "專案下一步",
        title: nextProject.name,
        desc: projectNext,
        context: "已帶入：專案 / 交棒卡 / 下一步",
        outcome: "可產出：任務草稿或交棒卡",
        cta: "打開交棒卡",
        color: this._projectColor(nextProject.name),
        action: () => this.openProjectDrawer(nextProject.id),
      } : {
        kind: "專案下一步",
        title: "建立第一個專案",
        desc: "把標案、活動或客戶需求先收進專案,後續智慧草稿才有脈絡。",
        context: "先建立：客戶 / 期限 / 預算 / 需求",
        outcome: "可接續：投標、活動、設計、公關",
        cta: "建立專案",
        color: "#3F86C9",
        action: () => this.newProject(),
      },
      {
        kind: "流程草稿",
        title: "投標完整閉環",
        desc: "招標摘要、承接評估、建議書大綱與報價風險一次拆好。",
        context: "已帶入：投標 SOP / 建議書格式",
        outcome: "可產出：主管家流程草稿",
        cta: "產生投標流程",
        color: "#D14B43",
        action: () => {
          this.showView("workflows");
          _view("workflows").then(m => m.load().then(() => m.prepare("tender-full", {
            projectId: nextProject?.id,
          })));
        },
      },
      {
        kind: "工作區起手式",
        title: "活動執行工作台",
        desc: "貼上活動目標、場地、預算與日期,先產場景需求單、動線和風險。",
        context: "已帶入：活動企劃流程 / 場勘交棒",
        outcome: "可產出：活動需求單與現場風險",
        cta: "開活動草稿",
        color: "#D8851E",
        action: () => this.openWorkspace(2),
      },
    ];

    root.innerHTML = "";
    cards.forEach((card) => {
      const el = document.createElement("article");
      el.className = "today-card";
      el.tabIndex = 0;
      el.setAttribute("role", "button");
      el.setAttribute("aria-label", `${card.kind}:${card.title}`);
      el.style.setProperty("--today-color", card.color);
      el.innerHTML = `
        <div class="today-kicker">${escapeHtml(card.kind)}</div>
        <div class="today-title">${escapeHtml(card.title)}</div>
        <div class="today-desc">${escapeHtml(card.desc)}</div>
        <div class="today-context">${escapeHtml(card.context)}</div>
        <div class="today-outcome">${escapeHtml(card.outcome)}</div>
        <div class="today-cta">${escapeHtml(card.cta)} →</div>
      `;
      el.addEventListener("click", card.action);
      el.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          card.action();
        }
      });
      root.appendChild(el);
    });
  },

  renderWorkspaceCards() {
    const root = document.getElementById("workspace-cards");
    if (!root) return;
    const nodes = WORKSPACES.map(ws => {
      const draft = WORKSPACE_DRAFTS[ws.id] || {};
      const card = document.createElement("button");
      card.type = "button";
      card.className = `workspace-card ws-${ws.id}`;
      card.style.setProperty("--ws-color", ws.color);
      card.setAttribute("aria-label", `進入${ws.fullName}`);
      card.innerHTML = `
        <div class="ws-head">
          <div class="ws-icon">${escapeHtml(ws.icon)}</div>
        <div class="ws-name">${escapeHtml(ws.fullName)}</div>
          <kbd class="ws-shortcut">${escapeHtml(ws.shortcut)}</kbd>
        </div>
        <div class="ws-desc">${escapeHtml(ws.desc)}</div>
        <div class="ws-flow">${escapeHtml(ws.flow)}</div>
        <div class="ws-next">先做:${escapeHtml(draft.next || "接續專案或貼資料")}</div>
        <div class="ws-deliverable">完成後:${escapeHtml(draft.deliverable || "可交付草稿")}</div>
        <div class="ws-cta">接續這類工作 →</div>
      `;
      card.addEventListener("click", () => this.openWorkspace(ws.id));
      return card;
    });
    renderList(root, nodes);
  },

  renderWorkspacePage() {
    const ws = WORKSPACES.find(item => item.id === Number(this.activeWorkspace)) || WORKSPACES[0];
    const draft = WORKSPACE_DRAFTS[ws.id] || {};
    const agent = CORE_AGENTS.find(item => item.num === ws.agent);
    const relatedProjects = Projects.load()
      .filter(p => p.status !== "closed")
      .filter(p => {
        const kind = workKind(p).label;
        return kind.includes(ws.name) || (ws.id === 5 && ["財務", "合約", "營運"].some(k => kind.includes(k)));
      })
      .slice(0, 3);

    document.getElementById("workspace-head")?.style.setProperty("--ws-color", ws.color);
    setText("workspace-eyebrow", `${ws.shortcut} · ${agentRoleName(agent)}`);
    setText("workspace-title", `${ws.icon} ${ws.fullName}`);
    setText("workspace-subtitle", ws.desc);

    const root = document.getElementById("workspace-stage");
    if (!root) return;
    root.style.setProperty("--ws-color", ws.color);
    const firstRelated = relatedProjects[0];
    const firstRelatedId = firstRelated ? escapeHtml(firstRelated.id || firstRelated._id) : "";
    root.innerHTML = `
      <article class="workspace-hero-card">
        <div>
          <div class="ws-flow">${escapeHtml(ws.flow)}</div>
          <h2>先接續專案,再請 AI 產草稿</h2>
          <p>${escapeHtml(draft.next || "選一個既有專案,或先建立新的專案；資料不足時再開草稿詢問。")}</p>
        </div>
        <div class="workspace-hero-actions">
          ${firstRelated ? `<button class="btn-primary" data-action="app.openProjectDrawer" data-action-arg="${firstRelatedId}">接續最近專案</button>` : ""}
          <button class="btn-ghost" data-action="app.newProject">建立專案</button>
          <button class="btn-ghost" data-action="app.startWorkspaceDraft" data-action-arg="${ws.id}">開新草稿</button>
        </div>
      </article>
      <div class="workspace-two-col">
        <section class="work-panel-card">
          <div class="work-section-title">這個工作區的專案</div>
          ${relatedProjects.length ? relatedProjects.map(p => `
            <button type="button" class="workspace-project-row" data-action="app.openProjectDrawer" data-action-arg="${escapeHtml(p.id || p._id)}">
              <strong>${escapeHtml(p.name || "未命名專案")}</strong>
              <span>${escapeHtml(p.client || "未指定客戶")} · ${escapeHtml(p.handoff?.next_actions?.[0] || p.description || "打開交棒卡補下一步")}</span>
            </button>
          `).join("") : `
            <div class="chip-empty">尚無相關專案 · 建立後就能保存素材、下一步與交接內容。</div>
          `}
        </section>
        <section class="work-panel-card">
          <div class="work-section-title">這裡通常會完成</div>
          <div class="workspace-output">${escapeHtml(draft.deliverable || "可交付草稿")}</div>
          <div class="ws-agents">${ws.tools.map(t => `<span class="ws-agent-tag">${escapeHtml(t)}</span>`).join("")}</div>
        </section>
      </div>
    `;
  },

  // ---------- Render · Projects ----------
  _projectUpdatedAt(p) {
    return projectUpdatedAt(p);
  },

  _projectUpdatedTs(p) {
    return projectUpdatedTs(p);
  },

  _sortedProjects(list) {
    return sortProjects(list);
  },

  _filteredProjects() {
    return filterProjects(Projects.load(), {
      filter: this.projectFilter,
      search: this.projectSearch,
    });
  },

  _selectDefaultProject(list) {
    this.activeProjectId = selectDefaultProjectId({
      activeProjectId: this.activeProjectId,
      filteredProjects: list,
      allProjects: Projects.load(),
    });
  },

  renderProjects() {
    const root = document.getElementById("projects-grid");
    if (!root) return;
    if (Projects._cache.length === 0 && !Projects._online) {
      root.innerHTML = skeletonCards(3);
    }
    const list = this._filteredProjects();
    this._selectDefaultProject(list);

    const count = document.getElementById("project-count");
    if (count) count.textContent = Projects.load().filter(p => p.status !== "closed").length;

    if (list.length === 0) {
      root.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1">
          <div class="empty-state-icon">📁</div>
          <div class="empty-state-title">${this.projectFilter === "all" ? "尚無專案" : "沒有符合條件的專案"}</div>
          <div class="empty-state-hint">
            <a href="#" class="link" data-new-project>建立新專案</a>${this.projectFilter !== "all" ? " · 或切換篩選條件" : ""}
          </div>
          <div class="work-empty-actions">
            <button class="btn-primary" data-new-project-button>手動建立</button>
            <button class="btn-ghost" data-project-planner>主管家帶我建</button>
          </div>
        </div>`;
      root.querySelector("[data-new-project]")?.addEventListener("click", e => {
        e.preventDefault();
        this.newProject();
      });
      root.querySelector("[data-new-project-button]")?.addEventListener("click", () => this.newProject());
      root.querySelector("[data-project-planner]")?.addEventListener("click", () => this.startProjectPlanner());
      this.renderWorkDetail();
      return;
    }

    const nodes = list.map(p => {
      const color = this._projectColor(p.name);
      const desc = p.description
        ? p.description.substring(0, 80) + (p.description.length > 80 ? "…" : "")
        : "";
      const collabLabel = p.next_owner
        ? `➡️ 下一棒 ${p.next_owner}`
        : (p.collaborators?.length ? `👥 ${p.collaborators.length} 位協作` : "");
      const node = tpl("tpl-project-card", {
        name:        p.name,
        client:      p.client ? `🏢 ${p.client}` : "",
        description: desc,
        deadline:    p.deadline ? `📅 ${p.deadline}` : "",
        budget:      collabLabel || (p.budget ? `💰 ${formatMoney(p.budget)}` : ""),
        updated:     `更新 ${timeAgo(this._projectUpdatedAt(p))}`,
      }, {
        classes: [
          `status-${p.status || "active"}`,
          "work-list-card",
          (this.activeProjectId === (p.id || p._id)) ? "active" : "",
        ].filter(Boolean),
        attrs: { "data-project-id": p.id || p._id, "aria-label": `選取專案:${p.name}` },
        style: { "--project-color": color },
        onclick: () => this.selectProject(p.id || p._id),
      });
      node.tabIndex = 0;
      node.setAttribute("role", "button");
      node.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this.selectProject(p.id || p._id);
        }
      });
      return node;
    });
    renderList(root, nodes);
    this.renderWorkDetail();
  },

  selectProject(id) {
    this.activeProjectId = id;
    // v1.39 perf F-2 修 · 拆 render scope · 不再透過 renderProjects 順帶 fire renderWorkDetail
    // 改為呼叫 _renderProjectViews · 統一觸發點
    this._renderProjectViews({ workDetail: true });
  },

  /**
   * v1.39 perf · 集中所有 project view re-render · 避免 4 個 render 散叫
   * @param {object} opts · 可控制是否含 workDetail / preview / today
   */
  _renderProjectViews(opts = {}) {
    const { workDetail = true, preview = true, today = true } = opts;
    this.renderProjects();
    if (workDetail) this.renderWorkDetail();
    if (today) this.renderTodayWorkbench();
    if (preview) this.renderProjectsPreview();
  },

  _projectDeadline(p) {
    return projectDeadline(p);
  },

  _workReadiness(p) {
    return workReadiness(p);
  },

  _workKind(p) {
    return workKind(p);
  },

  _workActionSuggestions(p, readiness, kind, deadline) {
    return workActionSuggestions(p, readiness, kind, deadline);
  },

  renderWorkDetail() {
    const root = document.getElementById("work-detail");
    if (!root) return;
    const p = Projects.get(this.activeProjectId);
    if (!p) {
      root.className = "work-detail-empty";
      root.innerHTML = `
        <div class="empty-state-icon">◎</div>
        <div class="empty-state-title">選一個專案,或讓主管家帶你建立</div>
        <div class="empty-state-hint">右側會顯示下一棒、素材缺口與智慧助理可執行動作。</div>
        <div class="work-empty-actions">
          <button class="btn-primary" data-action="app.newProject">建立專案</button>
          <button class="btn-ghost" data-action="app.startProjectPlanner">請主管家帶我建</button>
        </div>`;
      return;
    }

    const readiness = this._workReadiness(p);
    const deadline = this._projectDeadline(p);
    const kind = this._workKind(p);
    const suggestions = this._workActionSuggestions(p, readiness, kind, deadline);
    const leadSuggestion = suggestions[0];
    const color = this._projectColor(p.name);
    const handoff = p.handoff || {};
    const nextActions = (handoff.next_actions || []).filter(Boolean);
    const assets = (handoff.asset_refs || []).map(a => a.ref || a.label || "").filter(Boolean);
    const next = nextActions[0] || p.description || "尚未寫下一步,建議先產交棒卡。";
    const missing = readiness.missing.slice(0, 5);
    const statusLabel = (p.status || "active") === "closed" ? "已結案" : "進行中";
    const suggestionCards = suggestions.map((s, index) => `
      <button class="work-suggestion-card ${index === 0 ? "primary" : ""}" data-action="app.runWorkAction" data-action-arg="${escapeHtml(s.kind)}">
        <span class="work-suggestion-icon">${escapeHtml(s.icon)}</span>
        <span>
          <strong>${escapeHtml(s.title)}</strong>
          <small>${escapeHtml(s.desc)}</small>
        </span>
        <em>${escapeHtml(s.cta)} →</em>
      </button>
    `).join("");

    root.className = "work-detail";
    root.style.setProperty("--project-color", color);
    root.style.setProperty("--kind-color", kind.color);
    root.innerHTML = `
      <div class="work-hero">
        <div>
          <div class="work-kind" style="--kind-color:${kind.color}">${escapeHtml(kind.label)}</div>
          <h2>${escapeHtml(p.name || "未命名專案")}</h2>
          <p>${escapeHtml(p.client || "未指定客戶")} · ${escapeHtml(statusLabel)} · 更新 ${escapeHtml(timeAgo(this._projectUpdatedAt(p)) || "—")}</p>
        </div>
        <div class="readiness-ring" style="--score:${readiness.score}">
          <strong>${readiness.score}%</strong>
          <span>可交接度</span>
        </div>
      </div>

      <div class="work-stats">
        <div class="work-stat ${deadline.tone}"><span>截止</span><strong>${escapeHtml(deadline.label)}</strong></div>
        <div class="work-stat"><span>預算</span><strong>${escapeHtml(p.budget ? formatMoney(p.budget) : "未設定")}</strong></div>
        <div class="work-stat"><span>下一棒</span><strong>${escapeHtml(p.next_owner || "未指定")}</strong></div>
        <div class="work-stat"><span>協作者</span><strong>${escapeHtml((p.collaborators || []).length ? `${p.collaborators.length} 位` : "未設定")}</strong></div>
      </div>

      <div class="work-next-strip">
        <div class="work-next-mark">AI 判斷</div>
        <div class="work-next-copy">
          <span>建議下一步</span>
          <strong>${escapeHtml(leadSuggestion?.title || "先拆可執行任務")}</strong>
          <p>${escapeHtml(leadSuggestion?.desc || "讓主管家先把專案拆成今天能做的下一步。")}</p>
        </div>
        <button class="btn-primary" data-action="app.runWorkAction" data-action-arg="${escapeHtml(leadSuggestion?.kind || "next")}">${escapeHtml(leadSuggestion?.cta || "開始")}</button>
      </div>

      <div class="work-suggestion-grid" aria-label="智慧助理建議動作">
        ${suggestionCards}
      </div>

      <div class="work-focus-card">
        <div class="work-section-title">現在最該推的一步</div>
        <p>${escapeHtml(next)}</p>
        <div class="work-actions">
          <button class="btn-primary" data-action="app.runWorkAction" data-action-arg="next">請主管家拆下一步</button>
          <button class="btn-ghost" data-action="app.openProjectDrawer" data-action-arg="${escapeHtml(p.id || p._id)}">打開交棒卡</button>
          <button class="btn-ghost" data-action="app.runWorkAction" data-action-arg="handoff">產交棒草稿</button>
        </div>
      </div>

      <div class="work-split">
        <section class="work-panel-card">
          <div class="work-section-title">缺口雷達</div>
          ${missing.length ? `
            <div class="gap-list">
              ${missing.map(label => `<span>${escapeHtml(label)}</span>`).join("")}
            </div>
            <button class="work-text-action" data-action="app.runWorkAction" data-action-arg="gaps">請智慧助理補成待確認清單 →</button>
          ` : `
            <div class="gap-complete">核心欄位齊了,可以進入產出。</div>
            <button class="work-text-action" data-action="app.runWorkAction" data-action-arg="deliverable">請智慧助理產第一版成果 →</button>
          `}
        </section>
        <section class="work-panel-card">
          <div class="work-section-title">素材與脈絡</div>
          <div class="asset-list">
            ${assets.length ? assets.slice(0, 4).map(a => `<span>${escapeHtml(a)}</span>`).join("") : `<span>尚未記錄素材路徑</span>`}
          </div>
          <button class="work-text-action" data-action="app.runWorkAction" data-action-arg="assets">整理素材需求 →</button>
        </section>
      </div>

      <div class="work-playbook-card">
        <div>
          <div class="work-section-title">推薦 Playbook</div>
          <p>${escapeHtml(kind.label)} · 會帶入這個專案的客戶、期限、預算與下一步。</p>
        </div>
        <button class="playbook-pill" style="--ws-color:${kind.color}" data-action="app.runWorkAction" data-action-arg="playbook">帶入 ${escapeHtml(kind.label)} 草稿</button>
      </div>`;
  },

  _projectPromptContext(p) {
    return projectPromptContext(p);
  },

  _workHandoffSaveConfig(p, actionKind) {
    return workHandoffSaveConfig(p, actionKind);
  },

  runWorkAction(kind) {
    const p = Projects.get(this.activeProjectId);
    if (!p) {
      toast.info("先選一個專案");
      return;
    }
    const workKind = this._workKind(p);
    const context = this._projectPromptContext(p);
    const prompts = {
      next: "請把這個專案拆成今天可執行的 3 個下一步,每步標明負責角色、需要素材、完成定義。",
      handoff: "請替這個專案產一張交棒卡,包含目標、限制、素材來源、下一步、需要人工確認的問題。",
      gaps: "請檢查這個專案缺哪些資訊,整理成最多 8 個待確認問題,並依急迫性排序。",
      assets: "請整理這個專案需要的素材清單,分成已知素材、待補素材、建議檔案命名與資料夾結構。",
      deliverable: "請依目前資訊產第一版可交付成果大綱,並明確標出假設與待確認處。",
      daily: "請把這個專案整理成今天必做清單,每項控制在 45 分鐘內,並標明負責角色、輸入素材、完成定義與阻塞點。",
      playbook: `請用「${workKind.label}」流程協助推進這個專案,先產出流程步驟、風險、下一個可直接交辦的任務。`,
    };
    const prompt = [
      "請以智慧助理主管家的角色處理以下專案。",
      "不要泛泛建議;請輸出可直接交辦的內容。若資料不足,請列出待確認,不要自行編造。",
      "",
      context,
      "",
      `任務:${prompts[kind] || prompts.next}`,
    ].join("\n");
    chat.open("00", prompt, { handoffSave: this._workHandoffSaveConfig(p, kind) });
    toast.info("已帶入主管家草稿 · 檢查後再送出");
  },

  renderProjectsPreview() {
    const root = document.getElementById("projects-preview");
    if (!root) return;
    const list = Projects.load()
      .filter(p => p.status !== "closed")
      .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
      .slice(0, 3);
    if (list.length === 0) return;
    const nodes = list.map(p => {
      const color = this._projectColor(p.name);
      const next = p.handoff?.next_actions?.[0] || p.description || "打開交棒卡補下一步";
      const collabLabel = p.next_owner
        ? `➡️ ${p.next_owner}`
        : (p.collaborators?.length ? `👥 ${p.collaborators.length} 位協作` : "");
      return tpl("tpl-project-card", {
        name:     p.name,
        client:   p.client || "",
        description: next,
        deadline: p.deadline ? `📅 ${p.deadline}` : "",
        budget:   collabLabel,
        updated:  `更新 ${timeAgo(p.updatedAt)}`,
      }, {
        attrs: { "data-project-id": p.id },
        style: { "--project-color": color },
        onclick: () => this.openProjectDrawer(p.id),
      });
    });
    renderList(root, nodes);
  },

  _projectColor(name) {
    return projectColor(name);
  },

  // ---------- Render · Skills ----------
  renderSkills() {
    const root = document.getElementById("skills-grid");
    if (root) {
      renderList(root, SKILLS.map(s => tpl("tpl-skill-card", {
        num:  `#${s.num}`,
        ws:   s.ws,
        name: s.name,
        desc: s.desc,
      }, { style: { "--ws-color": s.wscolor } })));
    }
    const croot = document.getElementById("claude-skills-grid");
    if (croot) {
      renderList(croot, CLAUDE_SKILLS.map(s => tpl("tpl-skill-card", {
        num:  `官方 · ${s.num}`,
        ws:   "",
        name: s.name,
        desc: s.desc,
      }, { style: { "--ws-color": "#0F2340" } })));
    }
  },

  // ---------- Actions ----------
  async submitTodayComposer(event) {
    event?.preventDefault?.();
    const input = document.getElementById("today-composer-input");
    const value = (input?.value || "").trim();
    const pendingFiles = this.todayAttachments.map(item => item.file);
    if (!value && !pendingFiles.length) {
      toast.info("先輸入一句今天要推進的工作,或加入附件");
      input?.focus();
      return;
    }
    const fileLines = pendingFiles.length
      ? ["", "我已附上這些檔案:", ...pendingFiles.map(file => `- ${file.name}`)]
      : [];
    const prompt = [
      "請以智慧助理主管家的角色協助我把這件工作往前推。",
      "請先判斷這應該建立或接續哪個專案,再列出可直接執行的下一步。",
      "如果需要我補資料,請用 3 個以內的問題詢問,不要泛泛建議。",
      "",
      "我的需求:",
      value || "請先閱讀附件,整理重點並建議下一步。",
      ...fileLines,
    ].join("\n");
    await chat.open("00", prompt);
    if (pendingFiles.length && document.getElementById("chat-pane")?.classList.contains("open")) {
      chat.addFiles(pendingFiles);
      this.todayAttachments = [];
      this.renderTodayAttachments();
    }
    toast.info(pendingFiles.length ? "已帶入主管家與附件 · 檢查後再送出" : "已帶入主管家 · 檢查後再送出");
  },

  openAgent(num) {
    const counts = JSON.parse(localStorage.getItem("chengfu-agent-usage") || "{}");
    counts[num] = (counts[num] || 0) + 1;
    localStorage.setItem("chengfu-agent-usage", JSON.stringify(counts));
    chat.open(num);
  },

  openWorkspace(n, options = {}) {
    this.activeWorkspace = Number(n);
    const agentNum = WORKSPACE_TO_AGENT[n];
    if (!agentNum) return;
    const ws = JSON.parse(localStorage.getItem("chengfu-ws-usage") || "{}");
    ws[n] = (ws[n] || 0) + 1;
    localStorage.setItem("chengfu-ws-usage", JSON.stringify(ws));
    this.showView("workspace");
    this.renderWorkspacePage();
    document.querySelectorAll(".sidebar-item.ws-nav").forEach(el => {
      el.classList.toggle("active", String(el.dataset.ws) === String(n));
    });
    // v1.13 · 透過 store 派 ws-changed event(取代手動 dispatchEvent)
    // store 內部會 fire engine-changed event 兼容 legacy listener
    store.set("activeWorkspace", String(n));
    if (options.replaceHash !== false) history.pushState("", document.title, `#workspace-${n}`);
  },

  startWorkspaceDraft(n = this.activeWorkspace) {
    const agentNum = WORKSPACE_TO_AGENT[n];
    const draft = WORKSPACE_DRAFTS[n];
    if (draft?.prompt) {
      chat.open(agentNum, draft.prompt);
      toast.info(`${draft.name}草稿已帶入 · 貼上資料後再送出`);
      return;
    }
    this.openAgent(agentNum);
  },

  slashCmd(cmd) {
    // Round 9 A · /design → 生圖 modal(v1.58 lazy)
    if (cmd === "/design" || cmd === "/image" || cmd === "/生圖") {
      _view("design").then(m => m.openPromptModal());
      return;
    }
    // Feature #1 · /meet → 會議速記上傳(v1.58 lazy)
    if (cmd === "/meet" || cmd === "/meeting" || cmd === "/會議") {
      _view("meeting").then(m => m.openUpload());
      return;
    }
    chat.open("00", cmd + " ");
  },

  openDesignModal() { _view("design").then(m => m.openPromptModal()); },

  startProjectPlanner() {
    const prompt = [
      "我想建立一個新的專案,但現在資訊還不完整。",
      "請用主管家的角色先問我 5 個必要問題,幫我快速收斂成可以建立專案的內容。",
      "請問題要短、好回答,並最後輸出可貼進專案的欄位:專案名稱、客戶、期限、預算、描述、下一棒、協作者、交棒目標、下一步、素材需求。",
    ].join("\n");
    chat.open("00", prompt);
    toast.info("已打開主管家 · 先回答 5 個問題就能建專案");
  },

  // ---------- Projects CRUD ----------
  newProject() {
    this.editingProjectId = null;
    setText("project-modal-title", "新專案");
    document.getElementById("project-form")?.reset();
    const delBtn = document.getElementById("project-delete-btn");
    if (delBtn) delBtn.style.display = "none";
    this.openProjectModal();
  },

  editProject(id) {
    const p = Projects.get(id);
    if (!p) return;
    this.editingProjectId = id;
    setText("project-modal-title", "編輯專案");
    const form = document.getElementById("project-form");
    if (!form) return;
    form.name.value = p.name || "";
    form.client.value = p.client || "";
    form.budget.value = p.budget || "";
    form.deadline.value = p.deadline || "";
    form.description.value = p.description || "";
    if (form.collaborators) form.collaborators.value = (p.collaborators || []).join("\n");
    if (form.next_owner) form.next_owner.value = p.next_owner || "";
    form.status.value = p.status || "active";
    const delBtn = document.getElementById("project-delete-btn");
    if (delBtn) delBtn.style.display = "inline-block";
    this.openProjectModal();
  },

  async saveProject(e) {
    e.preventDefault();
    const form = document.getElementById("project-form");
    if (!form) return;
    const editingId = this.editingProjectId;
    const data = {
      name:        form.name.value.trim(),
      client:      form.client.value.trim(),
      budget:      form.budget.value ? parseInt(form.budget.value) : null,
      deadline:    form.deadline.value,
      description: form.description.value.trim(),
      collaborators: (form.collaborators?.value || "")
        .split(/[\n,;]+/)
        .map(x => x.trim().toLowerCase())
        .filter(Boolean),
      next_owner:  (form.next_owner?.value || "").trim().toLowerCase() || null,
      status:      form.status.value,
    };
    if (!data.name) return;
    // Codex R3.7 · Projects.add/update 現在 throw on server 500 · 要 catch
    try {
      if (editingId) await Projects.update(editingId, data);
      else           await Projects.add(data);
    } catch (err) {
      toast.error(err.message || "儲存失敗 · 請重試");
      return;  // 不關 modal · 保留表單讓 user 重試
    }
    if (editingId) {
      this.activeProjectId = editingId;
    } else {
      const newest = [...Projects.load()].sort((a, b) =>
        this._projectUpdatedTs(b) - this._projectUpdatedTs(a)
      )[0];
      this.activeProjectId = newest?.id || newest?._id || null;
    }
    this.closeProjectModal();
    // v1.39 perf F-2 · 4 個獨立 render call → 1 個 helper(統一去抖點)
    this._renderProjectViews();
    toast.success("專案已儲存");
  },

  async deleteProject() {
    if (!this.editingProjectId) return;
    const deletingId = this.editingProjectId;
    const ok = await modal.confirm(
      "確定刪除這個專案?<br><small style='color:var(--text-secondary)'>對話與檔案不會刪,只刪除專案資料。</small>",
      { title: "刪除專案", icon: "⚠️", primary: "刪除", danger: true }
    );
    if (!ok) return;
    // Codex R3.7 · Projects.remove throw on server 500
    try {
      await Projects.remove(this.editingProjectId);
    } catch (err) {
      toast.error(err.message || "刪除失敗 · 請重試");
      return;
    }
    this.closeProjectModal();
    if (this.activeProjectId === deletingId) this.activeProjectId = null;
    // v1.39 perf F-2 · 統一 _renderProjectViews · 取代 4 個獨立 render
    this._renderProjectViews();
    toast.success("專案已刪除");
  },

  openProjectModal() {
    const modalEl = document.getElementById("project-modal");
    this._projectModalReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    document.getElementById("project-modal-backdrop")?.classList.add("open");
    modalEl?.classList.add("open");
    modalEl?.setAttribute("aria-hidden", "false");
    if (this._projectModalKeyHandler) document.removeEventListener("keydown", this._projectModalKeyHandler);
    this._projectModalKeyHandler = e => this._handleProjectModalKey(e);
    document.addEventListener("keydown", this._projectModalKeyHandler);
    requestAnimationFrame(() => {
      const initialFocus =
        modalEl?.querySelector('[name="name"]:not([disabled])') ||
        modalEl?.querySelector('input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled])');
      initialFocus?.focus();
    });
  },

  closeProjectModal() {
    document.getElementById("project-modal-backdrop")?.classList.remove("open");
    const modalEl = document.getElementById("project-modal");
    modalEl?.classList.remove("open");
    modalEl?.setAttribute("aria-hidden", "true");
    if (this._projectModalKeyHandler) {
      document.removeEventListener("keydown", this._projectModalKeyHandler);
      this._projectModalKeyHandler = null;
    }
    this.editingProjectId = null;
    const returnFocus = this._projectModalReturnFocus;
    this._projectModalReturnFocus = null;
    requestAnimationFrame(() => returnFocus?.focus?.());
  },

  _handleProjectModalKey(e) {
    const modalEl = document.getElementById("project-modal");
    if (!modalEl?.classList.contains("open")) return;
    if (e.key === "Escape") {
      e.preventDefault();
      this.closeProjectModal();
      return;
    }
    if (e.key !== "Tab") return;
    const focusable = modalEl.querySelectorAll(
      'a[href], input:not([disabled]), button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  },

  // ---------- Project Drawer(V1.1-SPEC §C · Q5 決議 drawer)----------
  async openProjectDrawer(id) {
    const p = Projects.get(id);
    if (!p) return;
    this.drawerProjectId = id;
    // ROADMAP §11.2 · 寫進 store · 其他 module 訂閱即時感知
    // chat / crm / knowledge 之後可 projectStore.subscribe(KEYS.CURRENT_PROJECT, ...)
    projectStore.set(STATE_KEYS.CURRENT_PROJECT, p);

    // Round 9 bug fix · 若之前被知識庫模式隱藏 · 這裡復原
    const drawer = document.getElementById("project-drawer");
    const handoffEl = document.getElementById("dr-handoff");
    if (handoffEl && handoffEl.dataset.hiddenByKnowledge === "1") {
      handoffEl.style.display = "";
      delete handoffEl.dataset.hiddenByKnowledge;
    }
    if (drawer) drawer.dataset.mode = "project";

    // 填基本資訊
    const name = p.name || "未命名專案";
    const setEl = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v || "—";
    };
    setEl("drawer-project-name", name);
    setEl("dr-client", p.client || "—");
    setEl("dr-budget", p.budget ? formatMoney(p.budget) : "—");
    setEl("dr-deadline", p.deadline || "—");
    setEl("dr-owner", p.owner || "—");
    setEl("dr-next-owner", p.next_owner || "—");
    setEl("dr-collaborators", (p.collaborators || []).join("、") || "—");
    this._updateProjectReadiness(p, null);

    // status badge
    const statusEl = document.getElementById("dr-status");
    if (statusEl) {
      const s = p.status || "active";
      statusEl.innerHTML = `<span class="drawer-status ${s}">${s === "closed" ? "已結案" : "進行中"}</span>`;
    }

    // description(有才顯示)
    const descSec = document.getElementById("dr-description-section");
    const descEl = document.getElementById("dr-description");
    if (descSec && descEl) {
      if (p.description) {
        descEl.textContent = p.description;
        descSec.style.display = "";
      } else {
        descSec.style.display = "none";
      }
    }

    // 清空 handoff 欄位,再 fetch
    ["dr-goal", "dr-constraints", "dr-assets", "dr-next"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
    setEl("dr-handoff-meta", "");

    // 滑出 drawer(先顯示 · 再 fetch handoff · 避免卡感)
    document.getElementById("project-drawer-backdrop")?.classList.add("open");
    drawer?.classList.add("open");
    drawer?.setAttribute("aria-hidden", "false");

    // Round 9 C · fetch handoff 改用 authFetch · 確保 X-User-Email header
    try {
      const r = await authFetch(`/api-accounting/projects/${id}/handoff`);
      if (!r.ok) {
        this._updateProjectReadiness(p, {});
        return;
      }
      const { handoff } = await r.json();
      if (handoff && typeof handoff === "object") {
        const goal = handoff.goal || "";
        const constraints = (handoff.constraints || []).join("\n");
        const assets = (handoff.asset_refs || [])
          .map(a => a.ref || a.label || "").filter(Boolean).join("\n");
        const next = (handoff.next_actions || []).join("\n");
        const setVal = (id, v) => {
          const el = document.getElementById(id);
          if (el) el.value = v;
        };
        setVal("dr-goal", goal);
        setVal("dr-constraints", constraints);
        setVal("dr-assets", assets);
        setVal("dr-next", next);
        if (handoff.updated_by || handoff.updated_at) {
          const meta = `上次由 ${handoff.updated_by || "—"} 編輯於 ${
            handoff.updated_at ? timeAgo(handoff.updated_at) : "—"
          }`;
          setEl("dr-handoff-meta", meta);
        }
        // 有內容就展開 details
        const hasContent = goal || constraints || assets || next;
        const details = document.getElementById("dr-handoff");
        if (details && hasContent) details.open = true;
        this._updateProjectReadiness(p, handoff);
      }
    } catch (e) {
      console.warn("[drawer] handoff fetch failed", e);
      this._updateProjectReadiness(p, {});
    }
  },

  _updateProjectReadiness(project, handoff = {}) {
    const h = handoff || {};
    const assetRefs = h.asset_refs || [];
    const nextActions = h.next_actions || [];
    const checks = [
      { ok: Boolean(project?.client), label: "客戶" },
      { ok: Boolean(project?.deadline), label: "截止日" },
      { ok: Boolean(project?.description), label: "專案描述" },
      { ok: Boolean((h.goal || "").trim()), label: "目標" },
      { ok: Boolean((h.constraints || []).length), label: "限制" },
      { ok: Boolean(assetRefs.length), label: "素材來源" },
      { ok: Boolean(nextActions.length), label: "下一步" },
    ];
    const done = checks.filter(item => item.ok).length;
    const score = Math.round((done / checks.length) * 100);
    const missing = checks.filter(item => !item.ok).map(item => item.label);
    const setTextLocal = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    };
    setTextLocal("dr-readiness-score", `${score}%`);
    setTextLocal(
      "dr-readiness-copy",
      score >= 80
        ? "這個專案已足夠讓 AI 接手。"
        : "還可以補幾個欄位,AI 回答會更準。",
    );
    setTextLocal(
      "dr-readiness-missing",
      missing.length ? `建議補:${missing.join("、")}` : "欄位完整,可直接交給 AI 接續。",
    );
    const fill = document.getElementById("dr-readiness-fill");
    if (fill) {
      fill.style.width = `${score}%`;
      fill.dataset.level = score >= 80 ? "ready" : score >= 50 ? "partial" : "low";
    }
  },

  closeProjectDrawer() {
    document.getElementById("project-drawer-backdrop")?.classList.remove("open");
    const drawer = document.getElementById("project-drawer");
    drawer?.classList.remove("open");
    drawer?.setAttribute("aria-hidden", "true");
    this.drawerProjectId = null;
    // ROADMAP §11.2 · 清 store · 訂閱者收 null 即可清 UI
    projectStore.set(STATE_KEYS.CURRENT_PROJECT, null);
  },

  editProjectFromDrawer() {
    if (!this.drawerProjectId) return;
    const id = this.drawerProjectId;
    this.closeProjectDrawer();
    // 延遲 250ms 等 drawer 滑出動畫結束再開 modal · 避免重疊動畫
    setTimeout(() => this.editProject(id), 250);
  },

  async saveHandoff() {
    if (!this.drawerProjectId) return;
    const id = this.drawerProjectId;
    const handoff = this._handoffFromDrawer();
    const assetLines = handoff.assets;
    const asset_refs = assetLines.map(line => ({
      type: line.startsWith("http") ? "url" :
            line.startsWith("/Volumes/") ? "nas" : "note",
      label: line,
      ref: line,
    }));
    const payload = {
      goal: handoff.goal,
      constraints: handoff.constraints,
      asset_refs,
      next_actions: handoff.nextActions,
    };
    try {
      // Round 9 C · 改 authFetch · updated_by 要能寫入正確 email
      const r = await authFetch(`/api-accounting/projects/${id}/handoff`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(r.statusText);
      const body = await r.json();
      const meta = document.getElementById("dr-handoff-meta");
      if (meta) meta.textContent = `已儲存 · ${timeAgo(body.updated_at)}`;
      toast.success("交棒卡已儲存");
      // 廣播 · 其他分頁 re-render project 列表(刷 updated_at)
      try {
        if ("BroadcastChannel" in self) {
          const bc = new BroadcastChannel("chengfu-projects");
          bc.postMessage({ type: "handoff-saved", ts: Date.now() });
          bc.close();
        }
      } catch {}
    } catch (e) {
      toast.error("儲存失敗:" + (e.message || "網路錯誤"));
    }
  },

  _handoffFromDrawer() {
    const lines = (value) => (value || "").split("\n").map(x => x.trim()).filter(Boolean);
    return {
      projectName: document.getElementById("drawer-project-name")?.textContent?.trim() || "未命名專案",
      client: document.getElementById("dr-client")?.textContent?.trim() || "—",
      nextOwner: document.getElementById("dr-next-owner")?.textContent?.trim() || "—",
      deadline: document.getElementById("dr-deadline")?.textContent?.trim() || "—",
      goal: (document.getElementById("dr-goal")?.value || "").trim(),
      constraints: lines(document.getElementById("dr-constraints")?.value),
      assets: lines(document.getElementById("dr-assets")?.value),
      nextActions: lines(document.getElementById("dr-next")?.value),
    };
  },

  _formatHandoffForShare(format, handoff) {
    const list = (items, empty = "未填") => items.length ? items.map(item => `- ${item}`).join("\n") : empty;
    if (format === "email") {
      return [
        `主旨:${handoff.projectName} · 專案交棒`,
        "",
        "Hi,",
        "",
        `以下是「${handoff.projectName}」目前交棒重點,請接續處理:`,
        "",
        `客戶:${handoff.client}`,
        `截止:${handoff.deadline}`,
        `接手同仁:${handoff.nextOwner}`,
        "",
        `目標:${handoff.goal || "未填"}`,
        "",
        "限制 / 注意事項:",
        list(handoff.constraints),
        "",
        "素材 / 附件來源:",
        list(handoff.assets),
        "",
        "下一步:",
        list(handoff.nextActions),
        "",
        "需要我補資料的地方請直接回覆,謝謝。",
      ].join("\n");
    }
    return [
      `【專案交棒】${handoff.projectName}`,
      `客戶:${handoff.client}`,
      `截止:${handoff.deadline}`,
      `接手同仁:${handoff.nextOwner}`,
      "",
      `目標:${handoff.goal || "未填"}`,
      "",
      `限制:${handoff.constraints.length ? handoff.constraints.join(" / ") : "未填"}`,
      "",
      "素材:",
      list(handoff.assets),
      "",
      "下一步:",
      list(handoff.nextActions),
    ].join("\n");
  },

  async copyHandoff(format = "line") {
    const handoff = this._handoffFromDrawer();
    const hasContent = handoff.goal || handoff.constraints.length || handoff.assets.length || handoff.nextActions.length;
    if (!hasContent) {
      toast.info("交棒卡還是空的 · 填至少一格再複製");
      return;
    }
    const text = this._formatHandoffForShare(format, handoff);
    try {
      const copied = await copyToClipboard(text);
      if (copied) toast.success(format === "email" ? "Email 版交棒已複製" : "LINE 版交棒已複製");
      else throw new Error("clipboard unavailable");
    } catch (e) {
      console.warn("[handoff] clipboard failed", e);
      await modal.alert(`<pre style="white-space:pre-wrap">${escapeHtml(text)}</pre>`, {
        title: "複製失敗 · 可手動選取",
        icon: "📋",
        primary: "知道了",
      });
    }
  },

  insertHandoffToChat() {
    const handoff = this._handoffFromDrawer();
    const goal = handoff.goal;
    const constraints = handoff.constraints.join("\n");
    const assets = handoff.assets.join("\n");
    const next = handoff.nextActions.join("\n");

    if (!goal && !constraints && !assets && !next) {
      toast.info("交棒卡還是空的 · 填至少一格再試");
      return;
    }

    const prompt = [
      "你接到這個專案的交棒:",
      goal ? `\n目標:${goal}` : "",
      constraints ? `\n限制:\n${constraints}` : "",
      assets ? `\n附件來源:\n${assets}` : "",
      next ? `\n下一步:\n${next}` : "",
      "",
      "請先回覆:",
      "1. 你理解了什麼?",
      "2. 還缺什麼資訊?",
      "3. 你打算怎麼開始?",
    ].filter(Boolean).join("\n");

    const projectName = handoff.projectName || "目前專案";
    chat.open("00", prompt, {
      handoffSave: {
        projectId: this.drawerProjectId,
        projectName,
        target: "asset_ref",
        label: "AI 接續回答",
        cta: "回寫交棒卡",
      },
    });
    this.closeProjectDrawer();
    toast.info("已打開主管家 · AI 回答後可一鍵回寫此專案");
  },

  summarizeProjectWithAI() {
    if (!this.drawerProjectId) return;
    const handoff = this._handoffFromDrawer();
    const projectName = handoff.projectName || "目前專案";
    const prompt = [
      `請協助整理「${projectName}」成可以交接的工作包。`,
      "",
      "目前資料:",
      `客戶:${handoff.client}`,
      `截止:${handoff.deadline}`,
      `接手同仁:${handoff.nextOwner}`,
      `目標:${handoff.goal || "未填"}`,
      `限制:${handoff.constraints.length ? handoff.constraints.join(" / ") : "未填"}`,
      `素材:${handoff.assets.length ? handoff.assets.join(" / ") : "未填"}`,
      `下一步:${handoff.nextActions.length ? handoff.nextActions.join(" / ") : "未填"}`,
      "",
      "請輸出四段:",
      "1. 目標一句話",
      "2. 限制 / 風險",
      "3. 素材缺口",
      "4. 明天可以直接做的下一步",
      "",
      "若資訊不足,請明確標成「待補」。",
    ].join("\n");
    chat.open("00", prompt, {
      handoffSave: {
        projectId: this.drawerProjectId,
        projectName,
        target: "asset_ref",
        label: "AI 專案整理",
        cta: "存回此專案",
      },
    });
    this.closeProjectDrawer();
    toast.info("已交給主管家整理 · 回答後可直接存回專案");
  },

  // ---------- Theme(v1.3 A2 · 拆到 modules/theme.js · 此 thin wrapper 不破壞既有 caller) ----------
  applyTheme() { theme.apply(); },
  toggleTheme() { theme.toggle(); },

  // ---------- Palette data source ----------
  _paletteItems() {
    return buildPaletteItems({
      showView: (view) => this.showView(view),
      openAgent: (num) => this.openAgent(num),
      openWorkspace: (num) => this.openWorkspace(num),
      editProject: (id) => this.editProject(id),
      setAIProvider: (provider) => this.setAIProvider(provider),
    });
  },

  openPalette() { palette.open(); },
  closePalette() { palette.close(); },

  // ---------- Keyboard ----------
  setupKeyboard() {
    setupGlobalKeyboard({
      openPalette: () => this.openPalette(),
      showView: (view) => this.showView(view),
      openWorkspace: (num) => this.openWorkspace(num),
      openAgent: (num) => this.openAgent(num),
      openAccounting: () => { this.showView("accounting"); _view("accounting").then(m => m.load()); },
      openAdmin: () => { this.showView("admin"); _view("admin").then(m => m.load()); },
      openTenders: () => { this.showView("tenders"); _view("tenders").then(m => m.load()); },
      openWorkflows: () => { this.showView("workflows"); _view("workflows").then(m => m.load()); },
      openCrm: () => { this.showView("crm"); _view("crm").then(m => { m.setUser(this.user?.email); m.load(); }); },
      isAdmin: () => this.user?.role === "ADMIN",
      toggleShortcuts: () => shortcuts.toggle(),
      closePalette: () => this.closePalette(),
      closeProjectModal: () => this.closeProjectModal(),
      closeProjectDrawer: () => this.closeProjectDrawer(),
      closeChat: () => chat.close(),
    });
  },
};

// ============================================================
//  Globals · 保留給 HTML onclick(逐步會改為 data-* + event delegation)
// ============================================================
window.app         = app;
window.chat        = chat;
window.modal       = modal;
window.toast       = toast;
window.shortcuts   = shortcuts;
window.voice       = voice;
window.Projects    = Projects;
window.knowledge   = knowledge;
window.palette     = palette;
// v1.58 lazy · 11 個 view module 改 proxy · console / debug 用 window.workflows.load() 仍可
// 第一次存取觸發動態 import · 之後 cache 直回
const _viewModuleNames = ["accounting","admin","userMgmt","design","meeting","media","social","siteSurvey","tenders","workflows","crm","notebooklm"];
for (const n of _viewModuleNames) {
  Object.defineProperty(window, n, {
    get() {
      // 同步取已 cache 的 · 沒 cache 觸發 import 但回 Proxy(任何 method 呼叫先 await import)
      return _viewCache[n] || new Proxy({}, {
        get(_, prop) {
          return (...args) => _view(n).then(m => m[prop]?.(...args));
        },
      });
    },
    configurable: true,
  });
}

// ============================================================
//  URL 參數處理 · pending(Chrome Ext) · convo(歷史對話重開)
// ============================================================
const urlParams = new URLSearchParams(window.location.search);
const pendingInput = urlParams.get("pending");
const convoToOpen  = urlParams.get("convo");

// ROADMAP §11.6 + sec F-7 · `?pending=` 反射 XSS / prompt 投送風險
// v1.26 perf · #5 修 · 4 個 DOMContentLoaded 合併成 1 個
// 攻擊者可佈局 `<a href="http://localhost/?pending=...">` 騙員工點 · 自動送惡意 prompt
// 修法:必先 modal 確認 · 加 source domain 警告 · 內容過長截斷
async function _handlePendingInput() {
  if (!pendingInput) return;
  const decoded = pendingInput;
  const truncated = decoded.length > 200 ? decoded.slice(0, 200) + "…" : decoded;
  const referrer = document.referrer || "(直接點擊網址)";
  const ok = await modal.confirm(
    `<div style='margin-bottom:10px'>偵測到外部連結帶入內容 · 要先帶入草稿嗎?</div>
     <div style='font-size:12px;color:var(--text-secondary);margin-bottom:8px'>來源:${escapeHtml(referrer)}</div>
     <pre style='font-size:12px;background:var(--bg-subtle,rgba(0,0,0,0.05));padding:8px;border-radius:6px;max-height:200px;overflow:auto;white-space:pre-wrap'>${escapeHtml(truncated)}</pre>
     <small style='color:var(--text-tertiary)'>內容只會放進輸入框,不會自動送到模型 · 請檢查後再按送出。</small>`,
    { title: "外部連結帶入內容", icon: "⚠️", primary: "帶入草稿", cancel: "取消" }
  );
  history.replaceState({}, document.title, window.location.pathname);
  if (ok) chat.open("00", decoded);
}

// Round 9 Q2 · Handoff 插入對話 sessionStorage 自動帶入(5 分鐘 TTL)
function _handleHandoffPending() {
  if (pendingInput || convoToOpen) return;
  try {
    const pending = sessionStorage.getItem("chengfu.pendingPrompt");
    const ts = parseInt(sessionStorage.getItem("chengfu.pendingPromptTs") || "0");
    const source = sessionStorage.getItem("chengfu.pendingPromptSource");
    if (pending && (Date.now() - ts < 5 * 60 * 1000)) {
      sessionStorage.removeItem("chengfu.pendingPrompt");
      sessionStorage.removeItem("chengfu.pendingPromptTs");
      sessionStorage.removeItem("chengfu.pendingPromptSource");
      setTimeout(() => {
        chat.open("00", pending);
        if (source === "handoff") {
          toast.info?.("交棒內容已帶入草稿 · 檢查無誤後送出即可");
        }
      }, 200);
    }
  } catch (e) {
    console.warn("[handoff] sessionStorage restore failed:", e);
  }
}

async function _handleConvoToOpen() {
  if (!convoToOpen) return;
  await new Promise(r => setTimeout(r, 300));  // 等 agents 載入
  try {
    await chat.open("00");
    await chat.loadConvo(decodeURIComponent(convoToOpen));
    history.replaceState({}, document.title, window.location.pathname);
  } catch (e) {
    console.warn("載入對話失敗", e);
  }
}

// ============================================================
//  Boot · 單一 DOMContentLoaded(原 4 個 listener 合併)
//  perf #5:減少 event 註冊 + 序列化執行 · 不重複 fire
// ============================================================
document.addEventListener("DOMContentLoaded", async () => {
  installDomActions();
  app.init();
  // 注意:app.init 是 async 但裡面 await refreshAuthWithLock,
  // 這裡不 await · 讓下面 3 個 handler 並行(它們互斥)
  _handlePendingInput();   // 只 pendingInput 有值才跑
  _handleHandoffPending(); // 只 !pendingInput && !convoToOpen 跑
  _handleConvoToOpen();    // 只 convoToOpen 跑
});

// helper
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

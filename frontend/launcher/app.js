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
} from "./modules/config.js";
import { escapeHtml, formatDate, greetingFor, timeAgo, formatMoney, skeletonCards, localizeVisibleText } from "./modules/util.js";
import { refreshAuthWithLock, authFetch, setUserEmail } from "./modules/auth.js";
// v1.7 · 暴露 authFetch 給 ESM 外的模組(branding.js inline form / 未來 plugin)
if (typeof window !== "undefined") window.authFetch = authFetch;
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
// v1.7 · Multi-tenant Branding(動態品牌名 · 取代 hardcode 「承富」)
import { brand } from "./modules/branding.js";
import { shortcuts } from "./modules/shortcuts.js";
import { health } from "./modules/health.js";
import { mobile } from "./modules/mobile.js";
import { setupGlobalKeyboard } from "./modules/keyboard.js";
import { chat } from "./modules/chat.js";
import { voice } from "./modules/voice.js";
import { accounting } from "./modules/accounting.js";
import { admin } from "./modules/admin.js";
import { userMgmt } from "./modules/user_mgmt.js";
import { knowledge } from "./modules/knowledge.js";
import { design } from "./modules/design.js";
import { help } from "./modules/help.js";
import { meeting } from "./modules/meeting.js";
import { media } from "./modules/media.js";
import { social } from "./modules/social.js";
import { siteSurvey } from "./modules/site_survey.js";
// ROADMAP §11.2 · single source of truth · 取代 cross-module currentProject 散處
import { projectStore, KEYS as STATE_KEYS } from "./modules/state/project-store.js";
import { tenders } from "./modules/tenders.js";
import { workflows } from "./modules/workflows.js";
import { crm } from "./modules/crm.js";
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

const TODAY_MAX_ATTACHMENT_COUNT = 6;
const TODAY_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024;
const TODAY_SUPPORTED_ATTACHMENT_EXT = new Set([
  "pdf", "txt", "md", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "csv", "json",
  "png", "jpg", "jpeg", "webp", "gif",
]);

// ============================================================
//  App Controller
// ============================================================
export const app = {
  user: null,
  agents: [],
  currentView: "dashboard",
  activeWorkspace: 1,
  editingProjectId: null,
  activeProjectId: null,
  projectFilter: "all",
  projectSearch: "",
  aiProvider: localStorage.getItem(AI_PROVIDER_KEY) || DEFAULT_AI_PROVIDER,
  todayAttachments: [],

  async init() {
    installGlobalErrorHandler();

    // 認證
    try {
      const data = await refreshAuthWithLock();
      this.user = data.user || data;
      setUserEmail(this.user?.email);  // 讓 authFetch 帶 X-User-Email · 給後端 RBAC 用
    } catch (e) {
      console.warn("[ChengFu] 認證失敗:", e);
      window.location.href = "/login";
      return;
    }

    this.setupGreeting();
    this.setupUser();
    this.applyTheme();

    // v1.7 · 載品牌 + 套到 DOM(取代 hardcode 「承富」)
    try {
      await brand.load();
      this._applyBranding();
      brand.subscribe(() => this._applyBranding());
    } catch (e) {
      console.warn("[brand] load failed", e);
    }

    // 注入 chat / crm 的 store 依賴
    chat.bind({ agents: () => this.agents, user: () => this.user, provider: () => this.aiProvider });
    crm.setUser(this.user?.email);
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

    this.setupKeyboard();
    this.setupNavigation();
    this.setupTodayActions();
    chat.bindFileInput();
    localizeVisibleText(document.getElementById("app"));

    // Projects 上線狀態提示
    document.querySelectorAll("[data-project-status]").forEach(notice => {
      if (Projects._online) {
        notice.innerHTML = "✅ 工作包資料已連接 MongoDB · 團隊共享";
        notice.style.background = "color-mix(in srgb, var(--green) 8%, transparent)";
        notice.style.color = "var(--green)";
      }
    });

    document.getElementById("loading").style.display = "none";
    document.getElementById("app").hidden = false;

    health.start();
    mobile.init();
    // v1.4 macOS · Dock 啟動 · default seed 7 個 agent
    try {
      macosDock.init();
    } catch (e) {
      console.warn("[macos] dock init failed", e);
    }
    // v1.4 macOS · Menubar(頂部)· Sprint B Phase 3
    try {
      macosMenubar.init();
    } catch (e) {
      console.warn("[macos] menubar init failed", e);
    }
    // v1.5 · Dashboard F++ 接手 · default active view = dashboard
    try {
      const dashView = document.querySelector('.view[data-view="dashboard"]');
      if (dashView) dashboardFpp.init(dashView);
    } catch (e) {
      console.warn("[fpp] dashboard init failed", e);
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
      if (hash === "accounting") accounting.load();
      if (hash === "admin")    { admin.load(); knowledge.loadAdmin(); }
      if (hash === "tenders")    tenders.load();
      if (hash === "workflows")  workflows.load();
      if (hash === "crm")        crm.load();
      if (hash === "knowledge")  knowledge.loadBrowser();
      // showView 已經 dispatch help/meeting/media/social/site init · 此處不重複
    }
  },

  // ---------- AI Provider ----------
  normalizeAIProvider(provider) {
    return AI_PROVIDERS[provider] ? provider : DEFAULT_AI_PROVIDER;
  },

  getAIProvider() {
    this.aiProvider = this.normalizeAIProvider(this.aiProvider);
    return this.aiProvider;
  },

  setAIProvider(provider) {
    const next = this.normalizeAIProvider(provider);
    if (next === this.aiProvider) {
      this.renderAIProvider();
      return;
    }
    this.aiProvider = next;
    localStorage.setItem(AI_PROVIDER_KEY, next);
    this.renderAIProvider();
    const meta = AI_PROVIDERS[next];
    toast.success(`AI 引擎已切換為 ${meta.label} · 新對話生效`);
  },

  renderAIProvider() {
    const provider = this.getAIProvider();
    const meta = AI_PROVIDERS[provider] || AI_PROVIDERS[DEFAULT_AI_PROVIDER];
    document.documentElement.dataset.aiProvider = provider;
    document.querySelectorAll("[data-ai-provider]").forEach(btn => {
      const active = btn.dataset.aiProvider === provider;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
      btn.title = active ? `目前使用 ${meta.label}` : `切換到 ${btn.textContent.trim()}`;
    });
    const label = document.getElementById("ai-provider-label");
    if (label) label.textContent = meta.badge;
    const hint = document.getElementById("ai-provider-hint");
    if (hint) hint.textContent = meta.desc;
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
        this.showView(el.dataset.view);
      });
    });
    document.querySelectorAll(".sidebar-item.ws-nav").forEach(el => {
      if (el instanceof HTMLAnchorElement && !el.getAttribute("href") && el.dataset.ws) {
        el.setAttribute("href", `#workspace-${el.dataset.ws}`);
      }
      el.addEventListener("click", e => {
        e.preventDefault();
        this.openWorkspace(parseInt(el.dataset.ws));
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
    if (view === "admin") knowledge.loadAdmin();
    // 使用教學 · 切過去就 init(admin 才載 secrets)
    if (view === "help") {
      const isAdmin = this.user?.role === "ADMIN";
      help.init(isAdmin);
    }
    // v1.2 Day 1.5 · 4 個新功能 view init
    const isAdmin = this.user?.role === "ADMIN";
    if (view === "meeting") meeting.init();
    if (view === "media") media.init(isAdmin);
    if (view === "social") social.init();
    if (view === "site") siteSurvey.init();
    // v1.3 · User Management
    if (view === "users" && isAdmin) userMgmt.init();
    [0, 250, 1000].forEach(delay => {
      setTimeout(() => {
        localizeVisibleText(document.querySelector(`.view[data-view="${view}"]`));
        localizeVisibleText(document.querySelector(".usage-aside"));
        localizeVisibleText(document.querySelector(".command-palette"));
        localizeVisibleText(document.querySelector(".chat-panel"));
      }, delay);
    });
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
      const dotColors = ["#FF3B30", "#FF9500", "#AF52DE", "#34C759", "#007AFF"];
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
          <button class="btn-ghost" onclick="window.app?.loadConversations?.()" style="margin-top:12px">重試</button>
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
    if (budgetEl && isAdmin) {
      try {
        const r = await authFetch("/api-accounting/admin/budget-status");
        if (!r.ok) throw new Error(`budget-status ${r.status}`);
        const d = await r.json();
        // v4.6 · 若資料源有問題 · 黃牌降級顯示而不是默默回 0
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
        // v1.3 batch6 · 別吞 budget API 失敗
        console.warn("[roi] budget-status failed:", e);
        showBudgetFallback();
      }
    } else if (budgetEl) {
      setText("roi-budget-value", "—");
      setText("roi-budget-sub", "管理員才看得到");
    }
    // 標案漏斗(admin 全員皆可見 · 管理面板另有更詳細版)
    try {
      const r = await authFetch("/api-accounting/admin/tender-funnel");
      if (r.ok) {
        const d = await r.json();
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
      // v1.3 batch6 · 別吞 funnel API 失敗
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
        kind: "工作包下一步",
        title: nextProject.name,
        desc: projectNext,
        context: "已帶入：工作包 / 交棒卡 / 下一步",
        outcome: "可產出：任務草稿或交棒卡",
        cta: "打開交棒卡",
        color: this._projectColor(nextProject.name),
        action: () => this.openProjectDrawer(nextProject.id),
      } : {
        kind: "工作包下一步",
        title: "建立第一個工作包",
        desc: "把標案、活動或客戶需求先收進工作包,後續智慧草稿才有脈絡。",
        context: "先建立：客戶 / 期限 / 預算 / 需求",
        outcome: "可接續：投標、活動、設計、公關",
        cta: "建立工作包",
        color: "#007AFF",
        action: () => this.newProject(),
      },
      {
        kind: "流程草稿",
        title: "投標完整閉環",
        desc: "招標摘要、承接評估、建議書大綱與報價風險一次拆好。",
        context: "已帶入：投標 SOP / 建議書格式",
        outcome: "可產出：主管家流程草稿",
        cta: "產生投標流程",
        color: "#FF3B30",
        action: () => {
          this.showView("workflows");
          workflows.load().then(() => workflows.prepare("tender-full", {
            projectId: nextProject?.id,
          }));
        },
      },
      {
        kind: "工作區起手式",
        title: "活動執行工作台",
        desc: "貼上活動目標、場地、預算與日期,先產場景需求單、動線和風險。",
        context: "已帶入：活動企劃流程 / 場勘交棒",
        outcome: "可產出：活動需求單與現場風險",
        cta: "開活動草稿",
        color: "#FF9500",
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
        <div class="ws-next">先做:${escapeHtml(draft.next || "接續工作包或貼資料")}</div>
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
          <h2>先接續工作包,再請 AI 產草稿</h2>
          <p>${escapeHtml(draft.next || "選一個既有工作包,或先建立新的工作包；資料不足時再開草稿詢問。")}</p>
        </div>
        <div class="workspace-hero-actions">
          ${firstRelated ? `<button class="btn-primary" onclick="app.openProjectDrawer('${firstRelatedId}')">接續最近工作包</button>` : ""}
          <button class="btn-ghost" onclick="app.newProject()">建立工作包</button>
          <button class="btn-ghost" onclick="app.startWorkspaceDraft(${ws.id})">開新草稿</button>
        </div>
      </article>
      <div class="workspace-two-col">
        <section class="work-panel-card">
          <div class="work-section-title">這個工作區的工作包</div>
          ${relatedProjects.length ? relatedProjects.map(p => `
            <button type="button" class="workspace-project-row" onclick="app.openProjectDrawer('${escapeHtml(p.id || p._id)}')">
              <strong>${escapeHtml(p.name || "未命名工作包")}</strong>
              <span>${escapeHtml(p.client || "未指定客戶")} · ${escapeHtml(p.handoff?.next_actions?.[0] || p.description || "打開交棒卡補下一步")}</span>
            </button>
          `).join("") : `
            <div class="chip-empty">尚無相關工作包 · 建立後就能保存素材、下一步與交接內容。</div>
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
          <div class="empty-state-title">${this.projectFilter === "all" ? "尚無工作包" : "沒有符合條件的工作包"}</div>
          <div class="empty-state-hint">
            <a href="#" class="link" data-new-project>建立新工作包</a>${this.projectFilter !== "all" ? " · 或切換篩選條件" : ""}
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
        attrs: { "data-project-id": p.id || p._id, "aria-label": `選取工作包:${p.name}` },
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
    this.renderProjects();
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
        <div class="empty-state-title">選一個工作包,或讓主管家帶你建立</div>
        <div class="empty-state-hint">右側會顯示下一棒、素材缺口與智慧助理可執行動作。</div>
        <div class="work-empty-actions">
          <button class="btn-primary" onclick="app.newProject()">建立工作包</button>
          <button class="btn-ghost" onclick="app.startProjectPlanner()">請主管家帶我建</button>
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
      <button class="work-suggestion-card ${index === 0 ? "primary" : ""}" onclick="app.runWorkAction('${s.kind}')">
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
          <h2>${escapeHtml(p.name || "未命名工作包")}</h2>
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
          <p>${escapeHtml(leadSuggestion?.desc || "讓主管家先把工作包拆成今天能做的下一步。")}</p>
        </div>
        <button class="btn-primary" onclick="app.runWorkAction('${leadSuggestion?.kind || "next"}')">${escapeHtml(leadSuggestion?.cta || "開始")}</button>
      </div>

      <div class="work-suggestion-grid" aria-label="智慧助理建議動作">
        ${suggestionCards}
      </div>

      <div class="work-focus-card">
        <div class="work-section-title">現在最該推的一步</div>
        <p>${escapeHtml(next)}</p>
        <div class="work-actions">
          <button class="btn-primary" onclick="app.runWorkAction('next')">請主管家拆下一步</button>
          <button class="btn-ghost" onclick="app.openProjectDrawer('${escapeHtml(p.id || p._id)}')">打開交棒卡</button>
          <button class="btn-ghost" onclick="app.runWorkAction('handoff')">產交棒草稿</button>
        </div>
      </div>

      <div class="work-split">
        <section class="work-panel-card">
          <div class="work-section-title">缺口雷達</div>
          ${missing.length ? `
            <div class="gap-list">
              ${missing.map(label => `<span>${escapeHtml(label)}</span>`).join("")}
            </div>
            <button class="work-text-action" onclick="app.runWorkAction('gaps')">請智慧助理補成待確認清單 →</button>
          ` : `
            <div class="gap-complete">核心欄位齊了,可以進入產出。</div>
            <button class="work-text-action" onclick="app.runWorkAction('deliverable')">請智慧助理產第一版成果 →</button>
          `}
        </section>
        <section class="work-panel-card">
          <div class="work-section-title">素材與脈絡</div>
          <div class="asset-list">
            ${assets.length ? assets.slice(0, 4).map(a => `<span>${escapeHtml(a)}</span>`).join("") : `<span>尚未記錄素材路徑</span>`}
          </div>
          <button class="work-text-action" onclick="app.runWorkAction('assets')">整理素材需求 →</button>
        </section>
      </div>

      <div class="work-playbook-card">
        <div>
          <div class="work-section-title">推薦 Playbook</div>
          <p>${escapeHtml(kind.label)} · 會帶入這個工作包的客戶、期限、預算與下一步。</p>
        </div>
        <button class="playbook-pill" style="--ws-color:${kind.color}" onclick="app.runWorkAction('playbook')">帶入 ${escapeHtml(kind.label)} 草稿</button>
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
      toast.info("先選一個工作包");
      return;
    }
    const workKind = this._workKind(p);
    const context = this._projectPromptContext(p);
    const prompts = {
      next: "請把這個工作包拆成今天可執行的 3 個下一步,每步標明負責角色、需要素材、完成定義。",
      handoff: "請替這個工作包產一張交棒卡,包含目標、限制、素材來源、下一步、需要人工確認的問題。",
      gaps: "請檢查這個工作包缺哪些資訊,整理成最多 8 個待確認問題,並依急迫性排序。",
      assets: "請整理這個工作包需要的素材清單,分成已知素材、待補素材、建議檔案命名與資料夾結構。",
      deliverable: "請依目前資訊產第一版可交付成果大綱,並明確標出假設與待確認處。",
      daily: "請把這個工作包整理成今天必做清單,每項控制在 45 分鐘內,並標明負責角色、輸入素材、完成定義與阻塞點。",
      playbook: `請用「${workKind.label}」流程協助推進這個工作包,先產出流程步驟、風險、下一個可直接交辦的任務。`,
    };
    const prompt = [
      "請以智慧助理主管家的角色處理以下工作包。",
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
      "請先判斷這應該建立或接續哪個工作包,再列出可直接執行的下一步。",
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
    document.dispatchEvent(new CustomEvent("ws-changed", { detail: { ws: String(n), view: "workspace" } }));
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
    // Round 9 A · /design → 生圖 modal(有 polling 閉環)
    if (cmd === "/design" || cmd === "/image" || cmd === "/生圖") {
      design.openPromptModal();
      return;
    }
    // Feature #1 · /meet → 會議速記上傳
    if (cmd === "/meet" || cmd === "/meeting" || cmd === "/會議") {
      meeting.openUpload();
      return;
    }
    chat.open("00", cmd + " ");
  },

  openDesignModal() { design.openPromptModal(); },

  startProjectPlanner() {
    const prompt = [
      "我想建立一個新的工作包,但現在資訊還不完整。",
      "請用主管家的角色先問我 5 個必要問題,幫我快速收斂成可以建立工作包的內容。",
      "請問題要短、好回答,並最後輸出可貼進工作包的欄位:工作包名稱、客戶、期限、預算、描述、下一棒、協作者、交棒目標、下一步、素材需求。",
    ].join("\n");
    chat.open("00", prompt);
    toast.info("已打開主管家 · 先回答 5 個問題就能建工作包");
  },

  // ---------- Projects CRUD ----------
  newProject() {
    this.editingProjectId = null;
    setText("project-modal-title", "新工作包");
    document.getElementById("project-form")?.reset();
    const delBtn = document.getElementById("project-delete-btn");
    if (delBtn) delBtn.style.display = "none";
    this.openProjectModal();
  },

  editProject(id) {
    const p = Projects.get(id);
    if (!p) return;
    this.editingProjectId = id;
    setText("project-modal-title", "編輯工作包");
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
    this.renderProjects();
    this.renderWorkDetail();
    this.renderTodayWorkbench();
    this.renderProjectsPreview();
    toast.success("工作包已儲存");
  },

  async deleteProject() {
    if (!this.editingProjectId) return;
    const deletingId = this.editingProjectId;
    const ok = await modal.confirm(
      "確定刪除這個工作包?<br><small style='color:var(--text-secondary)'>對話與檔案不會刪,只刪除工作包資料。</small>",
      { title: "刪除工作包", icon: "⚠️", primary: "刪除", danger: true }
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
    this.renderProjects();
    this.renderWorkDetail();
    this.renderTodayWorkbench();
    this.renderProjectsPreview();
    toast.success("工作包已刪除");
  },

  openProjectModal() {
    document.getElementById("project-modal-backdrop")?.classList.add("open");
    document.getElementById("project-modal")?.classList.add("open");
  },

  closeProjectModal() {
    document.getElementById("project-modal-backdrop")?.classList.remove("open");
    document.getElementById("project-modal")?.classList.remove("open");
    this.editingProjectId = null;
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
    const name = p.name || "未命名工作包";
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
      if (!r.ok) return;
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
      }
    } catch (e) {
      console.warn("[drawer] handoff fetch failed", e);
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
      projectName: document.getElementById("drawer-project-name")?.textContent?.trim() || "未命名工作包",
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
        `主旨:${handoff.projectName} · 工作包交棒`,
        "",
        "Hi,",
        "",
        `以下是「${handoff.projectName}」目前交棒重點,請接續處理:`,
        "",
        `客戶:${handoff.client}`,
        `截止:${handoff.deadline}`,
        `下一棒:${handoff.nextOwner}`,
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
      `【工作包交棒】${handoff.projectName}`,
      `客戶:${handoff.client}`,
      `截止:${handoff.deadline}`,
      `下一棒:${handoff.nextOwner}`,
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
      await navigator.clipboard.writeText(text);
      toast.success(format === "email" ? "Email 版交棒已複製" : "LINE 版交棒已複製");
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
      "你接到這個工作包的交棒:",
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

    // Round 9 Q2 · sessionStorage 自動帶入新對話輸入框
    // 舊行為(clipboard + redirect)保留為 fallback
    try {
      sessionStorage.setItem("chengfu.pendingPrompt", prompt);
      sessionStorage.setItem("chengfu.pendingPromptSource", "handoff");
      sessionStorage.setItem("chengfu.pendingPromptTs", String(Date.now()));
    } catch (e) {
      console.warn("[handoff] sessionStorage unavailable:", e);
    }
    // clipboard 作為 Safari 隱私模式 / 跨分頁 fallback(sessionStorage 存但沒貼到)
    navigator.clipboard?.writeText(prompt).then(
      () => toast.success("交棒內容已準備 · 新對話會自動帶入"),
      () => toast.success("交棒內容已準備"),
    );
    // 延遲一點開新對話視窗 · 讓 user 看到 toast
    setTimeout(() => {
      window.location.href = "/c/new";
    }, 400);
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
      openAccounting: () => { this.showView("accounting"); accounting.load(); },
      openAdmin: () => { this.showView("admin"); admin.load(); },
      openTenders: () => { this.showView("tenders"); tenders.load(); },
      openWorkflows: () => { this.showView("workflows"); workflows.load(); },
      openCrm: () => { this.showView("crm"); crm.load(); },
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
window.accounting  = accounting;
window.admin       = admin;
window.tenders     = tenders;
window.workflows   = workflows;
window.crm         = crm;
window.Projects    = Projects;
window.siteSurvey  = siteSurvey;
window.meeting     = meeting;
window.media       = media;
window.social      = social;
window.knowledge   = knowledge;
window.userMgmt    = userMgmt;
window.palette     = palette;

// ============================================================
//  URL 參數處理 · pending(Chrome Ext) · convo(歷史對話重開)
// ============================================================
const urlParams = new URLSearchParams(window.location.search);
const pendingInput = urlParams.get("pending");
const convoToOpen  = urlParams.get("convo");

// ROADMAP §11.6 + sec F-7 · `?pending=` 反射 XSS / prompt 投送風險
// 攻擊者可佈局 `<a href="http://localhost/?pending=...">` 騙員工點 · 自動送惡意 prompt
// 修法:必先 modal 確認 · 加 source domain 警告 · 內容過長截斷
if (pendingInput) {
  window.addEventListener("DOMContentLoaded", async () => {
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
    if (ok) {
      chat.open("00", decoded);
    }
  });
}

// Round 9 Q2 · Handoff 插入對話 sessionStorage 自動帶入
// sessionStorage 5 分鐘內有效 · 避免舊資料誤帶入
if (!pendingInput && !convoToOpen) {
  window.addEventListener("DOMContentLoaded", () => {
    try {
      const pending = sessionStorage.getItem("chengfu.pendingPrompt");
      const ts = parseInt(sessionStorage.getItem("chengfu.pendingPromptTs") || "0");
      const source = sessionStorage.getItem("chengfu.pendingPromptSource");
      if (pending && (Date.now() - ts < 5 * 60 * 1000)) {
        sessionStorage.removeItem("chengfu.pendingPrompt");
        sessionStorage.removeItem("chengfu.pendingPromptTs");
        sessionStorage.removeItem("chengfu.pendingPromptSource");
        // 用主管家(00)開 · 交棒卡適用於任何助手
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
  });
}

if (convoToOpen) {
  // v4.3 · 最近對話 click → /chat/c/:id → librechat-relabel.js 302 回 /?convo=:id
  // Launcher 認領 · 打開 chat pane · 用主管家身份載入歷史
  window.addEventListener("DOMContentLoaded", async () => {
    // 等 agents 載入好再 open · 不然 _findAgentByNum 會失敗
    await new Promise(r => setTimeout(r, 300));
    try {
      await chat.open("00");  // 以主管家 agent 開 pane
      await chat.loadConvo(decodeURIComponent(convoToOpen));
      // 清 URL query 避免 reload 再執行
      history.replaceState({}, document.title, window.location.pathname);
    } catch (e) {
      console.warn("載入對話失敗", e);
    }
  });
}

// ============================================================
//  Boot
// ============================================================
document.addEventListener("DOMContentLoaded", () => app.init());

// helper
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

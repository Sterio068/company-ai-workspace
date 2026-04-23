/**
 * 承富 Launcher · v4 主程式(ES module · entry)
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

import { API, CORE_AGENTS, SKILLS, CLAUDE_SKILLS, WORKSPACE_TO_AGENT } from "./modules/config.js";
import { escapeHtml, formatDate, greetingFor, timeAgo, formatMoney, skeletonCards } from "./modules/util.js";
import { refreshAuth, authFetch, setUserEmail } from "./modules/auth.js";
import { Projects } from "./modules/projects.js";
import { modal } from "./modules/modal.js";
import { toast } from "./modules/toast.js";
import { palette } from "./modules/palette.js";
import { theme } from "./modules/theme.js";  // v1.3 A2 · 從 app.js 抽出
import { shortcuts } from "./modules/shortcuts.js";
import { health } from "./modules/health.js";
import { mobile } from "./modules/mobile.js";
import { chat } from "./modules/chat.js";
import { voice } from "./modules/voice.js";
import { accounting } from "./modules/accounting.js";
import { admin } from "./modules/admin.js";
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

// ============================================================
//  App Controller
// ============================================================
export const app = {
  user: null,
  agents: [],
  currentView: "dashboard",
  editingProjectId: null,
  projectFilter: "all",

  async init() {
    installGlobalErrorHandler();

    // 認證
    try {
      const data = await refreshAuth();
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

    // 注入 chat / crm 的 store 依賴
    chat.bind({ agents: () => this.agents, user: () => this.user });
    crm.setUser(this.user?.email);
    palette.bind(() => this._paletteItems());
    // V1.1 §E-3 · 知識庫全文搜尋加入 palette(async · debounced)
    palette.addAsyncSource((q) => knowledge.paletteSearch(q));
    // 多分頁同步:其他分頁改了專案,本分頁自動 re-render(避免髒清單)
    Projects.bindOnChange(() => {
      this.renderProjects();
      this.renderProjectsPreview();
    });

    // 並行載入
    await Promise.all([
      this.loadAgents(),
      this.loadConversations(),
      this.loadUsage(),
      this.loadROI(),
      Projects.refresh(),
    ]);

    this.renderFrequent();
    this.renderProjects();
    this.renderProjectsPreview();
    this.renderSkills();

    this.setupKeyboard();
    this.setupNavigation();
    chat.bindFileInput();

    // Projects 上線狀態提示
    document.querySelectorAll(".v10-notice").forEach(notice => {
      if (Projects._online) {
        notice.innerHTML = "✅ 專案資料已連接 MongoDB · 團隊共享";
        notice.style.background = "color-mix(in srgb, var(--green) 8%, transparent)";
        notice.style.color = "var(--green)";
      }
    });

    document.getElementById("loading").style.display = "none";
    document.getElementById("app").hidden = false;

    health.start();
    mobile.init();

    // 首次訪問 onboarding
    if (!localStorage.getItem("chengfu-tour-done") && window.tour) {
      setTimeout(() => window.tour.start(), 500);
    }

    // URL hash → view
    this.handleHashChange();
    window.addEventListener("hashchange", () => this.handleHashChange());
  },

  handleHashChange() {
    const hash = window.location.hash.replace("#", "");
    // R24 P1 · v1.2 加 4 個新 view + help 進 whitelist · 重新整理 /#social 才進得去
    const views = ["projects", "skills", "dashboard", "accounting", "admin", "tenders",
                   "workflows", "crm", "knowledge", "help",
                   "meeting", "media", "social", "site"];
    if (views.includes(hash)) {
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

  // ---------- Setup ----------
  setupGreeting() {
    const now = new Date();
    const name = this.user?.name || this.user?.username || "同仁";
    const greet = document.getElementById("greeting");
    if (greet) greet.textContent = `${greetingFor(now.getHours())},${name} 👋`;
    const date = document.getElementById("date-line");
    if (date) date.textContent = formatDate(now);
  },

  setupUser() {
    const name = this.user?.name || this.user?.username || "使用者";
    setText("user-name", name);
    setText("user-avatar", name.charAt(0).toUpperCase());
    setText("user-role", this.user?.role === "ADMIN" ? "管理員" : "同仁");
    if (this.user?.role === "ADMIN") {
      const nav = document.getElementById("admin-nav");
      if (nav) nav.style.display = "";
      document.documentElement.dataset.role = "admin";
      document.documentElement.dataset.userEmail = this.user.email || "";
    }
  },

  setupNavigation() {
    document.querySelectorAll(".nav-item").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        this.showView(el.dataset.view);
      });
    });
    document.querySelectorAll(".sidebar-item.ws-nav").forEach(el => {
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
    document.querySelectorAll(".filter-chip").forEach(el => {
      el.addEventListener("click", () => {
        this.projectFilter = el.dataset.filter;
        document.querySelectorAll(".filter-chip").forEach(x => x.classList.remove("active"));
        el.classList.add("active");
        this.renderProjects();
      });
    });
  },

  showView(view) {
    this.currentView = view;
    document.querySelectorAll(".view").forEach(el => {
      el.classList.toggle("active", el.dataset.view === view);
    });
    document.querySelectorAll(".nav-item").forEach(el => {
      el.classList.toggle("active", el.dataset.view === view);
    });
    if (view !== "dashboard") window.location.hash = view;
    else history.pushState("", document.title, window.location.pathname);
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
        container.innerHTML = '<div class="chip-empty">尚無對話 · 從工作區開始</div>';
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
    } catch {
      container.innerHTML = '<div class="chip-empty">尚無對話</div>';
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
    } catch {
      setText("usage-used", "0");
      setText("usage-limit", "150萬");
      setText("usage-remaining", "150萬");
      setText("usage-avg", "0");
      const card = document.querySelector(".usage-card");
      if (card) card.classList.add("empty");
    }
  },

  async loadROI() {
    // 3 個 ROI 儀表 · admin 看得到數字,同仁看 fallback
    const isAdmin = this.user?.role === "ADMIN";
    // 預算進度
    const budgetEl = document.getElementById("roi-budget-card");
    if (budgetEl && isAdmin) {
      try {
        const r = await authFetch("/api-accounting/admin/budget-status");
        if (r.ok) {
          const d = await r.json();
          // v4.6 · 若資料源有問題 · 黃牌降級顯示而不是默默回 0
          if (d.data_source_ok === false) {
            setText("roi-budget-value", "資料源異常");
            setText("roi-budget-sub", `⚠ ${d.data_source_issue || "LibreChat schema 變動?"} · 找工程師`);
            const fill = document.getElementById("roi-budget-fill");
            if (fill) { fill.style.width = "100%"; fill.className = "roi-fill warn"; }
          } else {
            setText("roi-budget-value", `NT$ ${Number(d.spent_ntd).toLocaleString()}`);
            setText("roi-budget-sub", `預算 NT$ ${Number(d.budget_ntd).toLocaleString()} · ${d.pct}% · 定價 ${d.pricing_version || ""}`);
            const fill = document.getElementById("roi-budget-fill");
            if (fill) {
              fill.style.width = Math.min(100, d.pct) + "%";
              fill.className = "roi-fill " + (d.alert_level === "over" ? "over" : d.alert_level === "warn" ? "warn" : "");
            }
          }
        }
      } catch {}
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
    } catch {}
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
      name:  a.name,
      badge: `${counts[a.num]} 次`,
    }, {
      attrs: { "data-agent-num": a.num },
      onclick: () => this.openAgent(a.num),
    }));
    renderList(root, nodes);
  },

  // ---------- Render · Projects ----------
  renderProjects() {
    const root = document.getElementById("projects-grid");
    if (!root) return;
    if (Projects._cache.length === 0 && !Projects._online) {
      root.innerHTML = skeletonCards(3);
    }
    let list = Projects.load();
    if (this.projectFilter !== "all") list = list.filter(p => p.status === this.projectFilter);

    const count = document.getElementById("project-count");
    if (count) count.textContent = Projects.load().filter(p => p.status !== "closed").length;

    if (list.length === 0) {
      root.innerHTML = `
        <div class="chip-empty" style="grid-column: 1 / -1">
          ${this.projectFilter === "all" ? "還沒有專案" : "沒有符合條件的專案"} ·
          <a href="#" class="link" data-new-project>建立新專案</a>
        </div>`;
      root.querySelector("[data-new-project]")?.addEventListener("click", e => {
        e.preventDefault();
        this.newProject();
      });
      return;
    }

    const nodes = list.map(p => {
      const color = this._projectColor(p.name);
      const desc = p.description
        ? p.description.substring(0, 80) + (p.description.length > 80 ? "…" : "")
        : "";
      const node = tpl("tpl-project-card", {
        name:        p.name,
        client:      p.client ? `🏢 ${p.client}` : "",
        description: desc,
        deadline:    p.deadline ? `📅 ${p.deadline}` : "",
        budget:      p.budget ? `💰 ${formatMoney(p.budget)}` : "",
        updated:     `更新 ${timeAgo(p.updatedAt)}`,
      }, {
        classes: [`status-${p.status || "active"}`],
        attrs: { "data-project-id": p.id },
        style: { "--project-color": color },
        onclick: () => this.openProjectDrawer(p.id),
      });
      return node;
    });
    renderList(root, nodes);
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
      return tpl("tpl-project-card", {
        name:     p.name,
        client:   p.client || "",
        deadline: p.deadline ? `📅 ${p.deadline}` : "",
        budget:   "",
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
    const colors = ["#FF3B30", "#FF9500", "#34C759", "#007AFF", "#AF52DE", "#FF2D55"];
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % colors.length;
    return colors[h];
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
        num:  `Claude · ${s.num}`,
        ws:   "",
        name: s.name,
        desc: s.desc,
      }, { style: { "--ws-color": "#0F2340" } })));
    }
  },

  // ---------- Actions ----------
  openAgent(num) {
    const counts = JSON.parse(localStorage.getItem("chengfu-agent-usage") || "{}");
    counts[num] = (counts[num] || 0) + 1;
    localStorage.setItem("chengfu-agent-usage", JSON.stringify(counts));
    chat.open(num);
  },

  openWorkspace(n) {
    const agentNum = WORKSPACE_TO_AGENT[n];
    if (!agentNum) return;
    const ws = JSON.parse(localStorage.getItem("chengfu-ws-usage") || "{}");
    ws[n] = (ws[n] || 0) + 1;
    localStorage.setItem("chengfu-ws-usage", JSON.stringify(ws));
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
    form.status.value = p.status || "active";
    const delBtn = document.getElementById("project-delete-btn");
    if (delBtn) delBtn.style.display = "inline-block";
    this.openProjectModal();
  },

  async saveProject(e) {
    e.preventDefault();
    const form = document.getElementById("project-form");
    if (!form) return;
    const data = {
      name:        form.name.value.trim(),
      client:      form.client.value.trim(),
      budget:      form.budget.value ? parseInt(form.budget.value) : null,
      deadline:    form.deadline.value,
      description: form.description.value.trim(),
      status:      form.status.value,
    };
    if (!data.name) return;
    // Codex R3.7 · Projects.add/update 現在 throw on server 500 · 要 catch
    try {
      if (this.editingProjectId) await Projects.update(this.editingProjectId, data);
      else                       await Projects.add(data);
    } catch (err) {
      toast.error(err.message || "儲存失敗 · 請重試");
      return;  // 不關 modal · 保留表單讓 user 重試
    }
    this.closeProjectModal();
    this.renderProjects();
    this.renderProjectsPreview();
    toast.success("專案已儲存");
  },

  async deleteProject() {
    if (!this.editingProjectId) return;
    const ok = await modal.confirm(
      "確定刪除這個專案?<br><small style='color:var(--text-secondary)'>對話與檔案不會刪,只刪除專案 metadata。</small>",
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
    this.renderProjects();
    this.renderProjectsPreview();
    toast.success("專案已刪除");
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
    const name = p.name || "未命名專案";
    const setEl = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v || "—";
    };
    setEl("drawer-project-name", name);
    setEl("dr-client", p.client || "—");
    setEl("dr-budget", p.budget ? formatMoney(p.budget) : "—");
    setEl("dr-deadline", p.deadline || "—");

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
    const lines = (s) => (s || "").split("\n").map(x => x.trim()).filter(Boolean);
    const assetLines = lines(document.getElementById("dr-assets")?.value);
    const asset_refs = assetLines.map(line => ({
      type: line.startsWith("http") ? "url" :
            line.startsWith("/Volumes/") ? "nas" : "note",
      label: line,
      ref: line,
    }));
    const payload = {
      goal: (document.getElementById("dr-goal")?.value || "").trim(),
      constraints: lines(document.getElementById("dr-constraints")?.value),
      asset_refs,
      next_actions: lines(document.getElementById("dr-next")?.value),
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

  insertHandoffToChat() {
    const goal = (document.getElementById("dr-goal")?.value || "").trim();
    const constraints = (document.getElementById("dr-constraints")?.value || "").trim();
    const assets = (document.getElementById("dr-assets")?.value || "").trim();
    const next = (document.getElementById("dr-next")?.value || "").trim();

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
    const items = [];
    [["dashboard", "🏠 首頁", "⌘0"],
     ["projects", "📁 專案", "⌘P"],
     ["skills", "📚 技能庫", "⌘L"],
     ["accounting", "💰 會計", "⌘A"],
     ["tenders", "📢 標案", "⌘T"],
     ["crm", "💼 商機", "⌘I"],
     ["workflows", "⚡ 流程", "⌘W"],
     ["knowledge", "📚 知識庫", ""],
     ["admin", "📊 Admin", "⌘M"]].forEach(([v, label, hint]) => {
      items.push({ icon: "", label, hint, action: () => this.showView(v) });
    });
    CORE_AGENTS.forEach(a => items.push({
      icon: a.emoji,
      label: `助手 · ${a.name}`,
      hint: a.model,
      action: () => this.openAgent(a.num),
    }));
    Projects.load().forEach(p => items.push({
      icon: "📁",
      label: `專案 · ${p.name}`,
      hint: p.client || "",
      action: () => this.editProject(p.id),
    }));
    SKILLS.forEach(s => items.push({
      icon: "📚",
      label: `技能 · ${s.name}`,
      hint: s.ws,
      action: () => this.showView("skills"),
    }));
    // Round 9 A · /design palette entry
    items.push({
      icon: "🎨",
      label: "生圖 · Fal.ai Recraft v3(每次 3 張挑方向)",
      hint: "/design",
      action: () => design.openPromptModal(),
    });
    return items;
  },

  openPalette() { palette.open(); },
  closePalette() { palette.close(); },

  // ---------- Keyboard ----------
  setupKeyboard() {
    document.addEventListener("keydown", e => {
      const mod = e.metaKey || e.ctrlKey;
      const inEditable = e.target.matches("input,textarea,[contenteditable]");

      if (mod && e.key === "k") { e.preventDefault(); this.openPalette(); return; }
      if (mod && e.key === "0") { e.preventDefault(); this.showView("dashboard"); return; }
      if (mod && e.key === "p") { e.preventDefault(); this.showView("projects"); return; }
      if (mod && e.key === "l") { e.preventDefault(); this.showView("skills"); return; }
      if (mod && "12345".includes(e.key) && !inEditable) { e.preventDefault(); this.openWorkspace(parseInt(e.key)); return; }
      if (mod && "6789".includes(e.key) && !inEditable) { e.preventDefault(); this.openAgent("0" + e.key); return; }
      if (mod && e.key === "a" && !inEditable) { e.preventDefault(); this.showView("accounting"); accounting.load(); return; }
      if (mod && e.key === "m" && !inEditable && this.user?.role === "ADMIN") { e.preventDefault(); this.showView("admin"); admin.load(); return; }
      if (mod && e.key === "t" && !inEditable) { e.preventDefault(); this.showView("tenders"); tenders.load(); return; }
      if (mod && e.key === "w" && !inEditable) { e.preventDefault(); this.showView("workflows"); workflows.load(); return; }
      if (mod && e.key === "i" && !inEditable) { e.preventDefault(); this.showView("crm"); crm.load(); return; }

      // Shift+/ = ?
      if (e.key === "?" && !inEditable) { e.preventDefault(); shortcuts.toggle(); return; }

      if (e.key === "Escape") {
        this.closePalette();
        this.closeProjectModal();
        // drawer 也要關 · 但 modal 開著的時候 Esc 先給 modal
        if (!document.getElementById("project-modal")?.classList.contains("open")) {
          this.closeProjectDrawer();
        }
        if (document.getElementById("chat-pane")?.classList.contains("open")
            && !document.querySelector(".modal2-box.open")
            && !document.querySelector(".palette.open")) {
          chat.close();
        }
      }
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
    const decoded = decodeURIComponent(pendingInput);
    const truncated = decoded.length > 200 ? decoded.slice(0, 200) + "…" : decoded;
    const referrer = document.referrer || "(直接點擊網址)";
    const ok = await modal.confirm(
      `<div style='margin-bottom:10px'>偵測到外部連結帶入內容 · 確認要送出嗎?</div>
       <div style='font-size:12px;color:var(--text-secondary);margin-bottom:8px'>來源:${escapeHtml(referrer)}</div>
       <pre style='font-size:12px;background:var(--bg-subtle,rgba(0,0,0,0.05));padding:8px;border-radius:6px;max-height:200px;overflow:auto;white-space:pre-wrap'>${escapeHtml(truncated)}</pre>
       <small style='color:var(--text-tertiary)'>未經確認的內容不會送到 AI · 取消可關閉。</small>`,
      { title: "外部連結帶入內容", icon: "⚠️", primary: "我確認送出", cancel: "取消" }
    );
    if (ok) {
      chat.open("00", decoded);
    } else {
      // 清掉 URL query 避免 reload 又跳
      history.replaceState({}, document.title, window.location.pathname);
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
            toast.info?.("交棒內容已自動帶入 · 檢查無誤後送出即可");
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
//  SW 清理 · dev 階段不用 PWA
// ============================================================
if ("serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    try {
      let cleaned = false;
      const regs = await navigator.serviceWorker.getRegistrations();
      for (const r of regs) { await r.unregister(); cleaned = true; }
      const keys = await caches.keys();
      for (const k of keys) { await caches.delete(k); cleaned = true; }
      if (cleaned && !sessionStorage.getItem("sw-cleaned-v4")) {
        sessionStorage.setItem("sw-cleaned-v4", "1");
        window.location.reload();
      }
    } catch {}
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

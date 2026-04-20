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
import { shortcuts } from "./modules/shortcuts.js";
import { health } from "./modules/health.js";
import { mobile } from "./modules/mobile.js";
import { chat } from "./modules/chat.js";
import { voice } from "./modules/voice.js";
import { accounting } from "./modules/accounting.js";
import { admin } from "./modules/admin.js";
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
    const views = ["projects", "skills", "dashboard", "accounting", "admin", "tenders", "workflows", "crm"];
    if (views.includes(hash)) {
      this.showView(hash);
      if (hash === "accounting") accounting.load();
      if (hash === "admin")      admin.load();
      if (hash === "tenders")    tenders.load();
      if (hash === "workflows")  workflows.load();
      if (hash === "crm")        crm.load();
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
  },

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
          setText("roi-budget-value", `NT$ ${Number(d.spent_ntd).toLocaleString()}`);
          setText("roi-budget-sub", `預算 NT$ ${Number(d.budget_ntd).toLocaleString()} · ${d.pct}%`);
          const fill = document.getElementById("roi-budget-fill");
          if (fill) {
            fill.style.width = Math.min(100, d.pct) + "%";
            fill.className = "roi-fill " + (d.alert_level === "over" ? "over" : d.alert_level === "warn" ? "warn" : "");
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
        onclick: () => this.editProject(p.id),
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
        onclick: () => this.editProject(p.id),
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
    chat.open("00", cmd + " ");
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
    if (this.editingProjectId) await Projects.update(this.editingProjectId, data);
    else                       await Projects.add(data);
    this.closeProjectModal();
    this.renderProjects();
    this.renderProjectsPreview();
  },

  async deleteProject() {
    if (!this.editingProjectId) return;
    const ok = await modal.confirm(
      "確定刪除這個專案?<br><small style='color:var(--text-secondary)'>對話與檔案不會刪,只刪除專案 metadata。</small>",
      { title: "刪除專案", icon: "⚠️", primary: "刪除", danger: true }
    );
    if (!ok) return;
    await Projects.remove(this.editingProjectId);
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

  // ---------- Theme ----------
  applyTheme() {
    const saved = localStorage.getItem("chengfu-theme") || "auto";
    document.documentElement.dataset.theme = saved;
  },

  toggleTheme() {
    const cur = document.documentElement.dataset.theme || "auto";
    const next = { auto: "light", light: "dark", dark: "auto" }[cur] || "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("chengfu-theme", next);
  },

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
window.palette     = palette;

// ============================================================
//  URL 參數處理 · pending(Chrome Ext) · convo(歷史對話重開)
// ============================================================
const urlParams = new URLSearchParams(window.location.search);
const pendingInput = urlParams.get("pending");
const convoToOpen  = urlParams.get("convo");

if (pendingInput) {
  window.addEventListener("DOMContentLoaded", () => {
    chat.open("00", decodeURIComponent(pendingInput));
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

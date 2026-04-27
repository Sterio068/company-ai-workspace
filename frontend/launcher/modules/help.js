/**
 * Help · 使用教學 + 服務金鑰管理
 * ==========================================================
 * 6 個區塊:
 *   1. 快速開始(新用戶 5 分鐘)
 *   2. 5 個工作區介紹
 *   3. 10 個智慧助手速覽
 *   4. 鍵盤快捷鍵
 *   5. 資料分級 SOP
 *   6. 服務金鑰管理與申請(管理員才顯示設定)
 */
import { authFetch } from "./auth.js";
import { escapeHtml, localizeVisibleText } from "./util.js";
import { toast } from "./toast.js";
import { modal } from "./modal.js";
// vNext B + D + G · 教學大幅優化 · 角色 / 進度 / 搜尋
import { ROLES, getRole, setRole, getRoleProgress, getProgress, resetProgress } from "./help-state.js";
import { helpTutorial } from "./help-tutorial.js";

const BASE = "/api-accounting";

// ============================================================
// vNext D · task ID → 人話 label · 給進度卡片用
// ============================================================
const TASK_LABELS = {
  // 任務式 FTUE(help-tutorial.js 的 6 步)
  "ftue-01-first-task": "完成首次任務式教學",
  "ftue-02-handoff-card": "用過交棒卡 4 格",
  "ftue-03-meeting-summary": "上傳過會議錄音",
  // 教學任務(各角色 priority_tasks 用)
  "tutorial-attach-pdf": "知道怎麼丟附件給 AI",
  "tutorial-handoff-copy-line": "複製過 LINE 格式交棒卡",
  "tutorial-tender-go-no-go": "用過招標 Go/No-Go 評估",
  "tutorial-meeting-upload": "用過會議速記上傳",
  "tutorial-design-fal": "用過 Fal.ai 生圖",
  "tutorial-press-release": "寫過新聞稿草稿",
  "tutorial-social-schedule": "排程過社群貼文",
  "tutorial-knowledge-search": "搜過知識庫",
  "tutorial-vendor-compare": "用過廠商比價表",
  "tutorial-budget-quote": "做過專案報價毛利試算",
  "tutorial-classification": "看懂資料分級 L1/L2/L3",
  "tutorial-shortcuts": "記住 ⌘1-5 / ⌘K 快捷鍵",
};

function _taskLabel(taskId) {
  return TASK_LABELS[taskId] || taskId;
}

function _highlightQuery(text, q) {
  const escaped = escapeHtml(text);
  if (!q) return escaped;
  // q 來自使用者輸入 · regex 特殊字元先 escape
  const safe = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(${safe})`, "gi");
  return escaped.replace(re, "<mark>$1</mark>");
}

// v1.3 · 使用手冊完整列表(對應 frontend/launcher/user-guide/*.md)
const USER_GUIDE_DOCS = [
  { slug: "quickstart-v1.3",      icon: "🚀", title: "v1.3 快速開始(5 分鐘)" },
  { slug: "training-v1.3",        icon: "🎓", title: "v1.3 教育訓練(15 分鐘)" },
  { slug: "error-codes",          icon: "🚨", title: "錯誤訊息對照表" },
  { slug: "troubleshooting-v1.3", icon: "🔧", title: "v1.3 故障排除" },
  { slug: "mobile-ios",           icon: "📱", title: "iPhone 完整設定指南" },
  { slug: "slash-commands",       icon: "⌨️", title: "快速命令 + 快捷鍵" },
  { slug: "handoff-card",         icon: "📋", title: "交棒 4 格卡標準流程" },
  { slug: "knowledge-search",     icon: "📚", title: "知識庫搜尋 5 範例" },
  { slug: "dashboard-metrics",    icon: "📊", title: "首頁指標解讀" },
  { slug: "audio-note-sop",       icon: "🎙", title: "場勘語音備註標準流程" },
  { slug: "social-oauth-fallback",icon: "🔌", title: "社群授權降級方案" },
  { slug: "admin-permissions",    icon: "🔐", title: "管理員權限對照表" },
  { slug: "frontend-endpoints",   icon: "🔌", title: "前端 ↔ 後端介接對照" },
];


export const help = {
  _isAdmin: false,
  _secrets: [],
  _markdownCache: {},  // slug → rendered HTML

  async init(isAdmin) {
    this._isAdmin = isAdmin;
    this.render();
    if (isAdmin) {
      await this.loadSecrets();
    }
  },

  render() {
    const root = document.getElementById("help-content");
    if (!root) return;
    root.innerHTML = `
      <!-- vNext B + D + G · 教學大幅優化 · 角色 / 進度 / 搜尋 -->
      ${this._renderRolePicker()}
      ${this._renderProgress()}
      ${this._renderSearchBox()}

      <div class="help-container">
        <aside class="help-nav">
          <a href="#help-quickstart" class="help-nav-item active" data-section="quickstart">🚀 快速開始</a>
          <a href="#help-newfeatures" class="help-nav-item" data-section="newfeatures">🆕 v1.2 新功能</a>
          <a href="#help-workspaces" class="help-nav-item" data-section="workspaces">🎯 5 個工作區</a>
          <a href="#help-agents" class="help-nav-item" data-section="agents">🤖 10 個助手</a>
          <a href="#help-shortcuts" class="help-nav-item" data-section="shortcuts">⌨️ 快捷鍵</a>
          <a href="#help-classification" class="help-nav-item" data-section="classification">🔒 資料分級</a>

          <div class="help-nav-section">📖 完整使用手冊(v1.3)</div>
          ${USER_GUIDE_DOCS.map(d => `
            <a href="#help-doc-${d.slug}" class="help-nav-item" data-doc="${d.slug}">${d.icon} ${d.title}</a>
          `).join("")}

          <div class="help-nav-section">🔐 管理</div>
          <a href="#help-secrets" class="help-nav-item" data-section="secrets">🔐 服務金鑰管理</a>
        </aside>

        <div class="help-main">
          ${this._renderQuickstart()}
          ${this._renderNewFeatures()}
          ${this._renderWorkspaces()}
          ${this._renderAgents()}
          ${this._renderShortcuts()}
          ${this._renderClassification()}
          ${USER_GUIDE_DOCS.map(d => `
            <section id="help-doc-${d.slug}" class="help-section help-doc-section" data-doc-slug="${d.slug}">
              <div class="help-doc-loading">點左側「${d.icon} ${d.title}」載入</div>
            </section>
          `).join("")}
          ${this._renderSecrets()}
        </div>
      </div>
    `;
    this._bindNav();
    this._bindRoleAndProgress();
    this._bindSearch();
  },

  // ============================================================
  // vNext B · 角色 picker · 點 → setRole + re-render
  // ============================================================
  _renderRolePicker() {
    const current = getRole();
    return `
      <section class="help-role-section" style="padding:24px;background:var(--bg-content);border-radius:var(--r-2xl);margin-bottom:16px">
        <h2 style="margin:0 0 6px;font-size:18px">👤 你是哪個角色?</h2>
        <p style="margin:0;color:var(--text-secondary);font-size:13px">選了之後 · 教學會優先顯示跟你相關的內容。</p>
        <div class="help-role-picker">
          ${Object.entries(ROLES).filter(([k]) => k !== "unknown").map(([key, meta]) => `
            <button class="help-role-card${current === key ? " active" : ""}" type="button" data-help-role="${key}">
              <div class="help-role-icon">${meta.icon}</div>
              <div class="help-role-label">${escapeHtml(meta.label)}</div>
              <div class="help-role-desc">${escapeHtml(meta.desc)}</div>
            </button>
          `).join("")}
        </div>
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <button class="btn-primary" type="button" data-help-tutorial-start style="padding:8px 16px;border-radius:var(--r-md);background:var(--accent);color:white;border:none;cursor:pointer;font-weight:500">
            🚀 重新看 5 分鐘任務式教學
          </button>
          <button class="btn-ghost" type="button" data-help-progress-reset style="padding:8px 14px;border-radius:var(--r-md);background:var(--bg-base);border:1px solid var(--border);color:var(--text-secondary);cursor:pointer">
            重設進度
          </button>
        </div>
      </section>
    `;
  },

  // ============================================================
  // vNext D · 進度 bar · 角色 task 完成度
  // ============================================================
  _renderProgress() {
    const role = getRole();
    const meta = ROLES[role] || ROLES.unknown;
    const { done, total, percent } = getRoleProgress();
    const progress = getProgress();
    if (total === 0) {
      return `
        <section class="help-progress-card">
          <div class="help-progress-row">
            <div class="help-progress-text">尚未選角色 · 選一個之後會看到「為你定制的優先學習清單」</div>
          </div>
        </section>
      `;
    }
    return `
      <section class="help-progress-card">
        <div class="help-progress-row">
          <div class="help-progress-text"><b>${meta.icon} ${escapeHtml(meta.label)}</b> · 你已掌握的核心任務</div>
          <div class="help-progress-pct">${done} / ${total} · ${percent}%</div>
        </div>
        <div class="help-progress-bar-outer">
          <div class="help-progress-bar-inner" style="width:${percent}%"></div>
        </div>
        <ul class="help-task-list" style="margin-top:12px">
          ${meta.priority_tasks.map(taskId => {
            const isDone = !!progress[taskId];
            const label = _taskLabel(taskId);
            return `
              <li class="help-task-item${isDone ? " done" : ""}">
                <span class="help-task-check">${isDone ? "✓" : "○"}</span>
                <span>${escapeHtml(label)}</span>
              </li>
            `;
          }).join("")}
        </ul>
      </section>
    `;
  },

  // ============================================================
  // vNext G · 教學搜尋 · keyword → 對應 section / doc
  // ============================================================
  _renderSearchBox() {
    return `
      <section style="margin-bottom:16px">
        <input type="search" class="help-search-box" id="help-search-input"
               placeholder="搜教學...(例:「會議」「招標」「LINE」「快捷鍵」)"
               aria-label="搜尋教學">
        <div class="help-search-results" id="help-search-results" style="display:none"></div>
      </section>
    `;
  },

  _bindRoleAndProgress() {
    document.querySelectorAll("[data-help-role]").forEach(el => {
      el.addEventListener("click", () => {
        // dataset.helpRole(camelCase) · 對應 data-help-role(kebab)
        setRole(el.dataset.helpRole || el.getAttribute("data-help-role"));
        this.render();
      });
    });
    document.querySelector("[data-help-tutorial-start]")?.addEventListener("click", () => {
      helpTutorial.reset();
      helpTutorial.start();
    });
    document.querySelector("[data-help-progress-reset]")?.addEventListener("click", () => {
      if (confirm("重設教學進度?已完成的勾選會清空 · 但實際工作包不會動。")) {
        resetProgress();
        this.render();
      }
    });
  },

  _bindSearch() {
    const input = document.getElementById("help-search-input");
    const results = document.getElementById("help-search-results");
    if (!input || !results) return;

    // 索引:section + doc + role 標題
    const HELP_INDEX = [
      { id: "help-quickstart", title: "🚀 快速開始", body: "5 分鐘新人入門 工作區 對話 交棒" },
      { id: "help-newfeatures", title: "🆕 v1.2 新功能", body: "會議速記 媒體名單 社群排程 場勘" },
      { id: "help-workspaces", title: "🎯 5 個工作區", body: "投標 活動 設計 公關 營運" },
      { id: "help-agents", title: "🤖 10 個助手", body: "主管家 投標顧問 設計師 公關 會計 會議速記" },
      { id: "help-shortcuts", title: "⌨️ 快捷鍵", body: "⌘K ⌘1 ⌘2 ⌘3 ⌘4 ⌘5 ⌘P ⌘A ⌘M" },
      { id: "help-classification", title: "🔒 資料分級", body: "L1 L2 L3 機敏 PDPA" },
      { id: "help-doc-quickstart-v1.3", title: "🚀 v1.3 快速開始", body: "5 分鐘 新人 上手" },
      { id: "help-doc-training-v1.3", title: "🎓 v1.3 教育訓練", body: "15 分鐘 詳細教案" },
      { id: "help-doc-error-codes", title: "🚨 錯誤訊息對照表", body: "30+ error code 故障 修復" },
      { id: "help-doc-troubleshooting-v1.3", title: "🔧 v1.3 故障排除", body: "21 症狀 修法" },
      { id: "help-doc-mobile-ios", title: "📱 iPhone 完整設定", body: "場勘 PWA 拍照 GPS 麥克風" },
      { id: "help-doc-slash-commands", title: "⌨️ 快速命令", body: "⌘K /know /meet /vendor 27 快捷鍵" },
      { id: "help-doc-handoff-card", title: "📋 交棒 4 格卡", body: "目標 限制 素材 下一步 LINE Email" },
      { id: "help-doc-knowledge-search", title: "📚 知識庫搜尋", body: "5 範例 全文搜 引用" },
      { id: "help-doc-dashboard-metrics", title: "📊 首頁指標解讀", body: "用量 預算 ROI 標案漏斗" },
      { id: "help-doc-audio-note-sop", title: "🎙 場勘語音備註", body: "30 秒 語音 STT 設計師" },
      { id: "help-doc-social-oauth-fallback", title: "🔌 社群授權降級", body: "Meta 審核期 mock 排程" },
      { id: "help-doc-admin-permissions", title: "🔐 管理員權限對照", body: "ADMIN USER 匿名 7 preset 28 權限" },
      { id: "help-doc-frontend-endpoints", title: "🔌 前端 ↔ 後端對照", body: "module API 串接" },
      { id: "help-secrets", title: "🔐 服務金鑰管理", body: "Anthropic OpenAI Fal.ai Keychain" },
    ];

    let timer;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const q = input.value.trim().toLowerCase();
        if (q.length < 1) {
          results.style.display = "none";
          return;
        }
        const matches = HELP_INDEX.filter(item =>
          item.title.toLowerCase().includes(q) ||
          item.body.toLowerCase().includes(q)
        ).slice(0, 8);
        if (!matches.length) {
          results.innerHTML = `<div class="help-search-result" style="color:var(--text-secondary)">沒找到「${escapeHtml(input.value)}」相關教學</div>`;
          results.style.display = "block";
          return;
        }
        results.innerHTML = matches.map(m => `
          <div class="help-search-result" data-jump="${m.id}">
            <b>${_highlightQuery(m.title, q)}</b>
            <div style="color:var(--text-secondary);font-size:12px;margin-top:2px">${_highlightQuery(m.body, q)}</div>
          </div>
        `).join("");
        results.style.display = "block";
        results.querySelectorAll("[data-jump]").forEach(el => {
          el.addEventListener("click", () => {
            const target = document.getElementById(el.dataset.jump);
            if (target) {
              target.scrollIntoView({ behavior: "smooth", block: "start" });
              results.style.display = "none";
              input.value = "";
              // 對應 nav item 也標 active
              const navItem = document.querySelector(`.help-nav-item[data-section="${el.dataset.jump.replace("help-", "")}"], .help-nav-item[data-doc="${el.dataset.jump.replace("help-doc-", "")}"]`);
              if (navItem) {
                document.querySelectorAll(".help-nav-item").forEach(x => x.classList.remove("active"));
                navItem.classList.add("active");
                if (navItem.dataset.doc) this._loadDoc(navItem.dataset.doc);
              }
            }
          });
        });
      }, 200);
    });
  },

  _bindNav() {
    document.querySelectorAll(".help-nav-item").forEach(el => {
      el.addEventListener("click", async e => {
        e.preventDefault();
        document.querySelectorAll(".help-nav-item").forEach(x => x.classList.remove("active"));
        el.classList.add("active");

        // user-guide doc · fetch + render
        const docSlug = el.dataset.doc;
        if (docSlug) {
          await this._loadDoc(docSlug);
          const target = document.getElementById(`help-doc-${docSlug}`);
          if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
        // 內嵌 section · scroll
        const section = el.dataset.section;
        const target = document.getElementById(`help-${section}`);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  },

  async _loadDoc(slug) {
    const target = document.getElementById(`help-doc-${slug}`);
    if (!target) return;
    if (this._markdownCache[slug]) {
      target.innerHTML = this._markdownCache[slug];
      localizeVisibleText(target);
      return;
    }
    target.innerHTML = `<div class="help-doc-loading">⏳ 載入中...</div>`;
    try {
      const r = await fetch(`/static/user-guide/${slug}.md`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const md = await r.text();
      const { marked } = await import("./vendor-marked.js");
      const html = marked.parse(md);
      this._markdownCache[slug] = html;
      target.innerHTML = `<div class="help-doc-rendered">${html}</div>`;
      localizeVisibleText(target);
    } catch (e) {
      target.innerHTML = `<div class="help-doc-error">❌ 載入失敗:${e.message}<br>檔案 frontend/launcher/user-guide/${slug}.md 是否存在?</div>`;
    }
  },

  // ============================================================
  // 1. 快速開始
  // ============================================================
  _renderQuickstart() {
    return `
      <section id="help-quickstart" class="help-section">
        <h2>🚀 快速開始 · 第一次用的 5 分鐘</h2>

        <div class="help-step">
          <div class="help-step-num">1</div>
          <div>
            <h3>選擇工作區(⌘1 ~ ⌘5)</h3>
            <p>智慧助理以工作「情境」組織 · 不是助手清單。從左側選或按 ⌘1-5 切到對應工作區:</p>
            <ul class="help-ws-list">
              <li><span style="color:#D14B43">🎯 ⌘1 投標</span> · 招標須知 / 服務建議書 / 競品</li>
              <li><span style="color:#D8851E">🎪 ⌘2 活動執行</span> · 場景需求單 / 廠商 / 動線</li>
              <li><span style="color:#8C5CB1">🎨 ⌘3 設計協作</span> · 主視覺 / Fal 生圖(3 張)</li>
              <li><span style="color:#5AB174">📣 ⌘4 公關溝通</span> · 新聞稿 / 社群 / 電子郵件</li>
              <li><span style="color:#3F86C9">📊 ⌘5 營運後勤</span> · 結案報告 / 報價 / 知識查</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">2</div>
          <div>
            <h3>打開對話(選助手或直接打字)</h3>
            <p>工作區卡片點進去 · 或按 <kbd>⌘K</kbd> 開指令面板模糊搜尋。對話有三個貼心:</p>
            <ul>
              <li>文末貼 👍👎 · 月報會分析滿意度</li>
              <li>送前自動檢查本月預算 · 超了擋</li>
              <li>你打的內容會先留在公司主機 · 系統只做資料分級提醒,不會阻擋送出</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">3</div>
          <div>
            <h3>交棒 4 格卡</h3>
            <p>公關下班 · 設計明天才能接手?在專案頁填「交棒 4 格卡」:</p>
            <ul>
              <li><b>目標</b>:中秋活動主視覺</li>
              <li><b>限制</b>:品牌色橘黃 / 預算 5 萬 / 3 天內</li>
              <li><b>素材</b>:內部路徑 / 網路連結 / 會議紀錄連結</li>
              <li><b>下一步</b>:設計出 3 方向 / 企劃排客戶會</li>
            </ul>
            <p>設計隔天進設計工作區 · 對話自動帶入 4 格卡內容 · 無縫接手。</p>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">4</div>
          <div>
            <h3>知識庫(NAS 全案自動索引)</h3>
            <p>左側「知識庫」進去 · 全文搜尋 · 過往標書 / 結案報告 / 標準流程都在。</p>
            <p>機敏資料分級:投標工作區看得到投標案資料源 · 公關工作區看不到(防洩)。</p>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">5</div>
          <div>
            <h3>遇到問題?</h3>
            <p>左下找內部負責窗口聯絡 → 公司內部 IT / 專案管理員</p>
            <p>或打開服務監控頁(http://localhost:3001) · 看哪個服務沒有亮綠燈。</p>
          </div>
        </div>
      </section>
    `;
  },

  // ============================================================
  // 1.5 v1.2 新功能(2026-04-23)
  // ============================================================
  _renderNewFeatures() {
    return `
      <section id="help-newfeatures" class="help-section">
        <h2>🆕 v1.2 新功能 · 4 個</h2>
        <p>2026-04-23 上線 · 全部在左側側邊欄有入口 · 月省合計 ≥ 120 小時 / 10 人</p>

        <div class="help-step">
          <div class="help-step-num">🎤</div>
          <div>
            <h3>會議速記自動化</h3>
            <p>左側「會議速記」· 上傳音檔(m4a/mp3/wav · ≤ 25MB)· 語音轉文字 + 快速模型整理 · 一鍵推到交棒卡。</p>
            <ul>
              <li>每週 10 場客戶會議 · 手打 40 分/場 → 智慧助理整理 < 20 秒</li>
              <li>結構化:標題 / 與會者 / 決議 / 待辦 / 關鍵數字 / 下次會議</li>
              <li>PDPA · 處理完音檔自動刪 · 只留逐字稿 + 結構化</li>
              <li>Slash:<code>/meet</code> 或 <code>/會議</code></li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">📇</div>
          <div>
            <h3>媒體名單</h3>
            <p>左側「媒體名單」· 記者資料庫 + 主題推薦 + 表格匯入。寫完新聞稿 → 推薦前 10 名記者。</p>
            <ul>
              <li>記者建檔(初次匯入 100 筆表格)· 管理員才可改</li>
              <li>推薦公式:主題重疊 + 接受率 + 距上次發稿時間</li>
              <li>非管理員看不到手機(PDPA)· 推薦只管理員可用</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">📅</div>
          <div>
            <h3>社群貼文排程</h3>
            <p>左側「社群排程」· 臉書 / Instagram / 領英排程發布(目前為模擬 · 正式介接等審核)。</p>
            <ul>
              <li>排定時間用本地時區 · 內部自動轉 UTC</li>
              <li>失敗 3 次重試 · 第 3 次寫稽核紀錄給管理員</li>
              <li>正式 Meta/LinkedIn 接入 · 等老闆完成開發者應用程式審核(1-2 週)</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">📸</div>
          <div>
            <h3>場勘 PWA</h3>
            <p>左側「場勘」· iPhone 開瀏覽器到工作台 · 拍 1-5 張照片 + 定位 · 視覺模型自動結構化。</p>
            <ul>
              <li>會由智慧助理描述每張照片 + 彙整成 場地類型 / 入口 / 洗手間 / 停車 / 問題</li>
              <li><b>iPhone 用戶:</b> 設定 → 相機 → 格式 → 改「最相容」(否則拍出來是 HEIC 會被擋)</li>
              <li>一鍵推到專案交棒卡(獨立場勘問題欄位,不覆寫人工內容)</li>
              <li>2 年後依保存期限自動清除(活動週期 + 復盤)</li>
            </ul>
          </div>
        </div>
      </section>
    `;
  },

  // ============================================================
  // 2. 5 個工作區
  // ============================================================
  _renderWorkspaces() {
    const workspaces = [
      {
        num: 1, color: "#D14B43", icon: "🎯", name: "投標",
        desc: "看到招標須知 → 送件前最後一哩",
        agents: ["承接評估", "招標須知解析", "服務建議書初稿", "競品視覺研究", "簡報視覺架構"],
        slash: "/bid",
      },
      {
        num: 2, color: "#D8851E", icon: "🎪", name: "活動執行",
        desc: "企劃到現場到驗收 全流程",
        agents: ["立體場景需求單", "舞台技術", "動線與交通", "現場流程", "廠商比價", "委外合約"],
        slash: "/event",
      },
      {
        num: 3, color: "#8C5CB1", icon: "🎨", name: "設計協作",
        desc: "PM ↔ 設計師無痛溝通",
        agents: ["主視覺概念", "需求單結構化", "Fal.ai 生圖(3 張)", "多渠道適配", "活動視覺系統"],
        slash: "/design",
      },
      {
        num: 4, color: "#5AB174", icon: "📣", name: "公關溝通",
        desc: "對外發聲全流程",
        agents: ["新聞稿", "社群貼文", "月度企劃", "電子郵件草稿", "會議速記"],
        slash: "/pr",
      },
      {
        num: 5, color: "#3F86C9", icon: "📊", name: "營運後勤",
        desc: "內部管理中樞",
        agents: ["結案報告", "專案報價", "里程碑追蹤", "客戶紀錄", "保密協議 / 合約", "稅務", "新人引導", "知識查詢"],
        slash: "/ops",
      },
    ];

    return `
      <section id="help-workspaces" class="help-section">
        <h2>🎯 5 個工作區 · 按 ⌘1 ~ ⌘5 切</h2>
        <p>智慧助理以「工作情境」組織 · 不是助手清單。每個工作區有自己的封面 / 流程 / 近期對話:</p>

        <div class="help-ws-grid">
          ${workspaces.map(ws => `
            <div class="help-ws-card" style="border-left:4px solid ${ws.color}">
              <div class="help-ws-head">
                <span class="help-ws-icon" style="background:${ws.color}">${ws.icon}</span>
                <div>
                  <h3>${ws.icon} ${ws.name} <kbd>⌘${ws.num}</kbd></h3>
                  <p class="help-ws-desc">${ws.desc}</p>
                </div>
              </div>
              <div class="help-ws-body">
                <b>包含助手:</b>
                <ul>
                  ${ws.agents.map(a => `<li>${a}</li>`).join("")}
                </ul>
                <b>快速命令:</b> <code>${ws.slash}</code>
              </div>
            </div>
          `).join("")}
        </div>
      </section>
    `;
  },

  // ============================================================
  // 3. 10 個助手
  // ============================================================
  _renderAgents() {
    const agents = [
      { num: "00", name: "主管家", desc: "D-010 跨工作區協調 · 自動分派工作", ws: "全" },
      { num: "01", name: "投標顧問", desc: "招標須知解析 · 服務建議書初稿", ws: "投標" },
      { num: "02", name: "活動策劃", desc: "立體場景需求單 · 動線 · 現場流程", ws: "活動" },
      { num: "03", name: "設計夥伴", desc: "主視覺概念 · Fal.ai 生圖 · 多渠道適配", ws: "設計" },
      { num: "04", name: "公關文案", desc: "新聞稿 · 社群貼文 · 電子郵件草稿", ws: "公關" },
      { num: "05", name: "結案報告", desc: "結案撰寫 · KPI 回顧 · 下次改進", ws: "營運" },
      { num: "06", name: "財務 / 報價", desc: "專案報價 · 毛利試算 · 月度報告", ws: "營運" },
      { num: "07", name: "法務 / 合約", desc: "保密協議 · 授權書 · 合約初稿", ws: "營運" },
      { num: "08", name: "客戶紀錄管家", desc: "客戶紀錄 · 標案 → 提案 → 得標漏斗", ws: "營運" },
      { num: "09", name: "知識查手", desc: "全文搜 NAS · 過往案例 · 公司手冊", ws: "全" },
    ];

    return `
      <section id="help-agents" class="help-section">
        <h2>🤖 10 個智慧助手速覽</h2>
        <p>原始提案文件的 29 個助手精簡為 10 個核心 · 涵蓋 100% 功能。主管家(#00)會自動調度其他 9 個。</p>

        <table class="help-agents-table">
          <thead><tr><th>#</th><th>助手</th><th>說明</th><th>工作區</th></tr></thead>
          <tbody>
            ${agents.map(a => `
              <tr>
                <td><code>#${a.num}</code></td>
                <td><b>${a.name}</b></td>
                <td>${a.desc}</td>
                <td>${a.ws}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </section>
    `;
  },

  // ============================================================
  // 4. 鍵盤快捷鍵
  // ============================================================
  _renderShortcuts() {
    const shortcuts = [
      { keys: "⌘K", desc: "全域指令面板(模糊搜工作區 / 助手 / 快速命令)" },
      { keys: "⌘0", desc: "回今日首頁" },
      { keys: "⌘1 ~ ⌘5", desc: "切到對應工作區" },
      { keys: "⌘N", desc: "新對話" },
      { keys: "⌘/", desc: "快速命令面板" },
      { keys: "Esc", desc: "關閉視窗 / 取消輸入" },
      { keys: "Enter", desc: "送出對話(中文輸入法時 Shift+Enter 送)" },
      { keys: "Shift+Enter", desc: "對話內換行" },
      { keys: "⌘,", desc: "設定面板(管理員)" },
      { keys: "⌘S", desc: "搜知識庫" },
    ];

    return `
      <section id="help-shortcuts" class="help-section">
        <h2>⌨️ 鍵盤快捷鍵</h2>
        <table class="help-shortcut-table">
          <thead><tr><th>按鍵</th><th>說明</th></tr></thead>
          <tbody>
            ${shortcuts.map(s => `
              <tr>
                <td><kbd>${s.keys}</kbd></td>
                <td>${s.desc}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </section>
    `;
  },

  // ============================================================
  // 5. 資料分級
  // ============================================================
  _renderClassification() {
    return `
      <section id="help-classification" class="help-section">
        <h2>🔒 資料分級 SOP</h2>
        <p>智慧助理把任何內容送往雲端模型前 · 請先判斷分級:</p>

        <div class="help-level help-level-01">
          <h3>第一級 · 公開(白色)</h3>
          <p><b>例:</b>行銷通稿 · 通案研究 · 已公告政府資訊</p>
          <p><b>處理:</b>✅ 可直接送雲端模型</p>
        </div>

        <div class="help-level help-level-02">
          <h3>第二級 · 一般(黃色)</h3>
          <p><b>例:</b>招標須知 · 服務建議書 · 預算分析 · 客戶會議紀錄(去識別化)</p>
          <p><b>處理:</b>⚠️ 去識別化後可送雲 · 客戶名 / 電話 / 地址先打碼</p>
        </div>

        <div class="help-level help-level-03">
          <h3>第三級 · 機敏(紅色)</h3>
          <p><b>例:</b>選情分析 · 客戶機敏 · 未公告標案內情 · 競爭對手情報</p>
          <p><b>處理:</b>由使用者自行判斷是否去識別化、改用本地模型或人工處理</p>
          <p><b>系統提醒:</b>含「選情」/「競情」/「內情」等關鍵字時只做分級提醒,不阻擋送出</p>
        </div>

        <p class="help-sop-note">
          不確定分級?預設視為第二級 · 先去識別化再送。<br>
          詳見 <code>docs/DATA-CLASSIFICATION-POSTER.md</code>(A3 海報已貼辦公室牆)
        </p>
      </section>
    `;
  },

  // ============================================================
  // 6. 服務金鑰管理
  // ============================================================
  _renderSecrets() {
    return `
      <section id="help-secrets" class="help-section">
        <h2>🔐 服務金鑰管理與申請</h2>
        <p>智慧助理用到的外部服務金鑰 · 管理員可在此檢視狀態:</p>

        ${this._isAdmin ? `
          <div id="secrets-panel">
            <p class="help-secrets-loading">讀取中...</p>
          </div>
        ` : `
          <div class="help-secrets-noadmin">
            <p>⚠️ 只有管理員可以管理服務金鑰。</p>
            <p>若智慧助理回答「服務未啟用」· 請內部負責窗口或 Sterio 檢查金鑰設定。</p>
          </div>
        `}

        <div class="help-secret-guide">
          <h3>📖 各服務金鑰申請指引</h3>

          <div class="help-secret-item">
            <h4>備援模型服務金鑰(必填)</h4>
            <ol>
              <li>去 <a href="https://console.anthropic.com/" target="_blank" rel="noopener">console.anthropic.com</a></li>
              <li>註冊 → 設定 → 服務金鑰 → 建立金鑰</li>
              <li><b>預存美金 $50 升第二級</b>(D-002 · 10 人尖峰需要)</li>
              <li>格式:<code>sk-ant-...</code></li>
              <li>裝機時由安裝程式收取 · 存進 macOS 鑰匙圈</li>
            </ol>
          </div>

          <div class="help-secret-item help-secret-featured">
            <h4>🎨 生圖服務商(可選兩家 · 前端可切換)</h4>
            <table class="help-provider-compare">
              <thead><tr><th>服務商</th><th>模型</th><th>價格 / 3 張</th><th>速度</th><th>特色</th></tr></thead>
              <tbody>
                <tr>
                  <td><b>Fal.ai</b><br><span>低成本模式</span></td>
                  <td>Recraft v3</td>
                  <td>約 NT$ 4</td>
                  <td>12s 平均</td>
                  <td>繁中文字佳 · 品牌視覺<br>排隊模式 · 支援等待中狀態</td>
                </tr>
                <tr>
                  <td><b>高品質生圖</b><br><span>高品質模式</span></td>
                  <td>高品質生圖模型<br>(2026-04-21)</td>
                  <td>約 NT$ 20</td>
                  <td>15-30s</td>
                  <td>整體品質最高 · 複雜場景<br>同步回傳 · 無等待中狀態</td>
                </tr>
              </tbody>
            </table>
            <p>預設使用低成本生圖服務(成本低 5 倍)· 管理員可在上方表格切到高品質生圖,需要較高品質時使用。</p>
          </div>

          <div class="help-secret-item">
            <h4>Fal.ai 服務金鑰(Recraft v3 · 可前端改)</h4>
            <ol>
              <li>去 <a href="https://fal.ai/dashboard/keys" target="_blank" rel="noopener">fal.ai/dashboard/keys</a></li>
              <li>註冊 → 控制台 → 服務金鑰 → 新增金鑰</li>
              <li>Recraft v3 約美金 $0.04 / 張 · 3 張約 NT$ 4</li>
              <li>可在此管理畫面直接設定 · 不用重啟容器</li>
            </ol>
          </div>

          <div class="help-secret-item">
            <h4>主力模型服務金鑰(高品質生圖 + 語音轉文字 · 可前端改)</h4>
            <ol>
              <li>去 <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">platform.openai.com/api-keys</a></li>
              <li>建立金鑰 · 第一級額度一般就夠</li>
              <li>高品質生圖約美金 $0.21 / 張 · 3 張約 NT$ 20</li>
              <li>語音轉文字約美金 $0.006 / 分鐘(對話服務另讀環境設定)</li>
              <li>可在此管理畫面直接設定 · 不用重啟容器</li>
            </ol>
          </div>

          <div class="help-secret-item">
            <h4>寄信服務(月報自動寄信 · 選配)</h4>
            <ol>
              <li>Gmail:去 <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener">myaccount.google.com/apppasswords</a></li>
              <li>應用程式密碼(16 字母 · 非本密碼)</li>
              <li>寫入寄信帳號與寄信密碼(由鑰匙圈注入)</li>
            </ol>
          </div>
        </div>
      </section>
    `;
  },

  // ============================================================
  // Secrets panel · 載入 + render
  // ============================================================
  async loadSecrets() {
    try {
      const r = await authFetch(`${BASE}/admin/secrets/status`);
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      this._secrets = d.secrets || [];
      this._renderSecretsPanel();
    } catch (e) {
      const panel = document.getElementById("secrets-panel");
      if (panel) {
        panel.innerHTML = `<p class="help-secrets-err">讀取失敗:${escapeHtml(String(e))}</p>`;
        localizeVisibleText(panel);
      }
    }
  },

  _renderSecretsPanel() {
    const panel = document.getElementById("secrets-panel");
    if (!panel) return;

    panel.innerHTML = `
      <div class="help-secrets-summary">
        共 ${this._secrets.length} 項 · 已設 ${this._secrets.filter(s => s.is_set).length} 項
      </div>

      <table class="help-secrets-table">
        <thead>
          <tr><th>名稱</th><th>狀態</th><th>預覽</th><th>來源</th><th>操作</th></tr>
        </thead>
        <tbody>
          ${this._secrets.map(s => {
            const label = localizeSecretText(s.label);
            const desc = localizeSecretText(s.desc);
            const source = localizeSecretText(s.source);
            const nameLabel = localizeSecretName(s.name);
            return `
            <tr class="${s.is_set ? 'secret-set' : 'secret-unset'} ${s.required ? 'secret-required' : ''}">
              <td>
                <b>${escapeHtml(label)}</b>
                ${s.required ? '<span class="badge-required">必填</span>' : '<span class="badge-optional">選配</span>'}
                <br>
                <small class="secret-desc">${escapeHtml(desc)}</small>
                <br>
                <code class="secret-name" title="${escapeHtml(s.name)}">${escapeHtml(nameLabel)}</code>
              </td>
              <td>${s.is_set ? '<span class="secret-ok">✅ 已設</span>' : '<span class="secret-miss">❌ 未設</span>'}</td>
              <td><code class="secret-preview">${escapeHtml(s.preview)}</code></td>
              <td><small>${escapeHtml(source)}</small></td>
              <td>
                ${s.console_url ? `<a href="${s.console_url}" target="_blank" rel="noopener" class="btn-apply">申請 →</a>` : '—'}
                ${s.frontend_writable ? `<button class="btn-edit" data-name="${escapeHtml(s.name)}">設定</button>` : '<small>走鑰匙圈</small>'}
              </td>
            </tr>
          `}).join("")}
        </tbody>
      </table>
    `;

    // Bind 設定按鈕
    panel.querySelectorAll(".btn-edit").forEach(btn => {
      btn.addEventListener("click", () => this._openEditModal(btn.dataset.name));
    });
    localizeVisibleText(panel);
  },

  async _openEditModal(name) {
    const secret = this._secrets.find(s => s.name === name);
    if (!secret) return;
    const label = localizeSecretText(secret.label);
    const source = localizeSecretText(secret.source);

    const r = await modal.prompt(
      [
        {
          name: "value",
          label,
          type: "text",
          placeholder: secret.name === "FAL_API_KEY" ? "fal_xxx..." : "貼上服務金鑰",
          hint: `留空清除 · 來源:${source}`,
        },
      ],
      {
        title: `設定 ${label}`,
        icon: "🔐",
        submitText: "儲存(立即生效)",
      }
    );

    if (!r) return;

    try {
      const resp = await authFetch(`${BASE}/admin/secrets/${name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: r.value || "" }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        toast.error(`儲存失敗:${detail.detail || resp.status}`);
        return;
      }
      toast.success(`${label} 已儲存`);
      await this.loadSecrets();
    } catch (e) {
      toast.error(`儲存失敗:${String(e)}`);
    }
  },
};

function localizeSecretText(value = "") {
  return String(value)
    .replace(/STT 語音轉文字/g, "語音轉文字")
    .replace(/SMTP 密碼 · Gmail 用 App Password/g, "寄信密碼 · Gmail 使用應用程式密碼")
    .replace(/認證 cookie 用 · prod 必設 · 跟 LibreChat \.env 同步/g, "登入驗證用 · 正式環境必設 · 需與對話系統環境設定同步")
    .replace(/cron → accounting admin endpoint 用 · prod 必設/g, "排程服務呼叫會計管理介接時使用 · 正式環境必設")
    .replace(/選 'fal'\(Recraft v3 · NT\$ 4 \/ 3 張\)或 'openai'\(gpt-image-2 · NT\$ 20 \/ 3 張\)/g, "可選低成本模式(Recraft v3 · NT$ 4 / 3 張)或高品質模式(約 NT$ 20 / 3 張)")
    .replace(/設計流程一次/g, "設計流程一次")
    .replace(/預設 fal/g, "預設低成本模式")
    .replace(/Anthropic API Key/g, "備援模型服務金鑰")
    .replace(/OpenAI API Key/g, "主力模型服務金鑰")
    .replace(/Fal\.ai API Key/g, "生圖服務金鑰")
    .replace(/生圖 Provider/g, "生圖服務商")
    .replace(/SMTP Username/g, "寄信帳號")
    .replace(/SMTP Password/g, "寄信密碼")
    .replace(/JWT Refresh Secret/g, "登入安全密鑰")
    .replace(/ECC Internal Token/g, "內部通行權杖")
    .replace(/Meilisearch Master Key/g, "全文搜尋主密鑰")
    .replace(/Claude 模型/g, "備援模型")
    .replace(/gpt-image-2/g, "高品質生圖模型")
    .replace(/App Password/g, "應用程式密碼")
    .replace(/SMTP/g, "寄信服務")
    .replace(/cookie/g, "登入憑證")
    .replace(/prod/g, "正式環境")
    .replace(/cron/g, "排程服務")
    .replace(/endpoint/g, "介接端點")
    .replace(/index/g, "索引")
    .replace(/Day 0/g, "上線第一天")
    .replace(/Tier 2/g, "第二級")
    .replace(/USD/g, "美金")
    .replace(/\.env/g, "環境設定")
    .replace(/API Key/g, "服務金鑰")
    .replace(/Internal Token/g, "內部通行權杖")
    .replace(/STT/g, "語音轉文字")
    .replace(/accounting admin endpoint/g, "會計管理介接")
    .replace(/accounting/g, "會計服務")
    .replace(/admin endpoint/g, "管理介接")
    .replace(/system_settings/g, "系統設定")
    .replace(/frontend/g, "前端")
    .replace(/install/g, "安裝")
    .replace(/Keychain/g, "鑰匙圈");
}

function localizeSecretName(name = "") {
  const names = {
    ANTHROPIC_API_KEY: "備援模型服務金鑰",
    OPENAI_API_KEY: "主力模型服務金鑰",
    FAL_API_KEY: "生圖服務金鑰",
    IMAGE_PROVIDER: "生圖服務商設定",
    EMAIL_USERNAME: "寄信帳號",
    EMAIL_PASSWORD: "寄信密碼",
    JWT_REFRESH_SECRET: "登入安全密鑰",
    ECC_INTERNAL_TOKEN: "內部通行權杖",
    MEILI_MASTER_KEY: "全文搜尋主密鑰",
  };
  return names[name] || localizeSecretText(name).replace(/_/g, " ");
}

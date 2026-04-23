/**
 * Help · 使用教學 + API Key 管理
 * ==========================================================
 * 6 sections:
 *   1. 快速開始(新用戶 5 分鐘)
 *   2. 5 個 Workspace 介紹
 *   3. 10 個 AI 助手速覽
 *   4. 鍵盤快捷鍵
 *   5. 資料分級 SOP
 *   6. API Key 管理 & 申請(admin 才顯示設定)
 */
import { authFetch } from "./auth.js";
import { escapeHtml } from "./util.js";
import { toast } from "./toast.js";
import { modal } from "./modal.js";

const BASE = "/api-accounting";

export const help = {
  _isAdmin: false,
  _secrets: [],

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
      <div class="help-container">
        <aside class="help-nav">
          <a href="#help-quickstart" class="help-nav-item active" data-section="quickstart">🚀 快速開始</a>
          <a href="#help-newfeatures" class="help-nav-item" data-section="newfeatures">🆕 v1.2 新功能</a>
          <a href="#help-workspaces" class="help-nav-item" data-section="workspaces">🎯 5 個工作區</a>
          <a href="#help-agents" class="help-nav-item" data-section="agents">🤖 10 個助手</a>
          <a href="#help-shortcuts" class="help-nav-item" data-section="shortcuts">⌨️ 快捷鍵</a>
          <a href="#help-classification" class="help-nav-item" data-section="classification">🔒 資料分級</a>
          <a href="#help-secrets" class="help-nav-item" data-section="secrets">🔐 API Key 管理</a>
        </aside>

        <div class="help-main">
          ${this._renderQuickstart()}
          ${this._renderNewFeatures()}
          ${this._renderWorkspaces()}
          ${this._renderAgents()}
          ${this._renderShortcuts()}
          ${this._renderClassification()}
          ${this._renderSecrets()}
        </div>
      </div>
    `;
    this._bindNav();
  },

  _bindNav() {
    document.querySelectorAll(".help-nav-item").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        const section = el.dataset.section;
        document.querySelectorAll(".help-nav-item").forEach(x => x.classList.remove("active"));
        el.classList.add("active");
        const target = document.getElementById(`help-${section}`);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
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
            <p>承富 AI 系統以工作「情境」組織 · 不是 agent 清單。從左側選或按 ⌘1-5 切到對應工作區:</p>
            <ul class="help-ws-list">
              <li><span style="color:#FF3B30">🎯 ⌘1 投標</span> · 招標須知 / 服務建議書 / 競品</li>
              <li><span style="color:#FF9500">🎪 ⌘2 活動執行</span> · 場景 brief / 廠商 / 動線</li>
              <li><span style="color:#AF52DE">🎨 ⌘3 設計協作</span> · 主視覺 / Fal 生圖(3 張)</li>
              <li><span style="color:#34C759">📣 ⌘4 公關溝通</span> · 新聞稿 / 社群 / Email</li>
              <li><span style="color:#007AFF">📊 ⌘5 營運後勤</span> · 結案報告 / 報價 / 知識查</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">2</div>
          <div>
            <h3>打開對話(選 Agent 或直接打字)</h3>
            <p>工作區卡片點進去 · 或按 <kbd>⌘K</kbd> 開指令面板模糊搜尋。對話有三個貼心:</p>
            <ul>
              <li>文末貼 👍👎 · 月報會分析滿意度</li>
              <li>送前自動檢查本月預算 · 超了擋</li>
              <li>你打的東西 100% 在公司 Mac mini · 對話送雲 API · Level 03 機敏自動擋</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">3</div>
          <div>
            <h3>交棒(Handoff 4 格卡)</h3>
            <p>公關下班 · 設計明天才能接手?在專案頁填「Handoff 4 格卡」:</p>
            <ul>
              <li><b>Goal</b> 目標:中秋活動主視覺</li>
              <li><b>Constraints</b> 限制:品牌色橘黃 / 預算 5 萬 / 3 天內</li>
              <li><b>Asset refs</b> 素材:NAS / URL / 會議紀錄連結</li>
              <li><b>Next actions</b> 待辦:設計出 3 方向 / PM 排客戶會</li>
            </ul>
            <p>設計隔天進設計 Workspace · 對話自動帶入 4 格卡內容 · 無縫接手。</p>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">4</div>
          <div>
            <h3>知識庫(NAS 全案自動索引)</h3>
            <p>左側「知識庫」進去 · Meilisearch 全文搜 · 過往標書 / 結案報告 / SOP 都在。</p>
            <p>機敏資料分級:投標 Workspace 看得到投標案 source · 公關 Workspace 看不到(防洩)。</p>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">5</div>
          <div>
            <h3>遇到問題?</h3>
            <p>左下 Champion 聯絡 → Sterio sterio068@gmail.com</p>
            <p>或 Uptime Kuma(http://localhost:3001) · 看 6 容器哪個沒亮綠。</p>
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
        <p>2026-04-23 上線 · 全部在左側 sidebar 有入口 · 月省合計 ≥ 120 小時 / 10 人</p>

        <div class="help-step">
          <div class="help-step-num">🎤</div>
          <div>
            <h3>會議速記自動化</h3>
            <p>左側「會議速記」· 上傳音檔(m4a/mp3/wav · ≤ 25MB)· Whisper STT + Haiku 整理 · 一鍵推到 Handoff。</p>
            <ul>
              <li>每週 10 場客戶會議 · 手打 40 分/場 → AI 整理 < 20 秒</li>
              <li>結構化:標題 / 與會者 / 決議 / 待辦 / 關鍵數字 / 下次會議</li>
              <li>PDPA · 處理完音檔自動刪 · 只留逐字稿 + 結構化</li>
              <li>Slash:<code>/meet</code> 或 <code>/會議</code></li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">📇</div>
          <div>
            <h3>媒體 CRM</h3>
            <p>左側「媒體 CRM」· 記者資料庫 + 主題推薦 + CSV 匯入。寫完新聞稿 → 推薦 top 10 記者。</p>
            <ul>
              <li>承富記者建檔(初次匯入 100 筆 CSV)· admin 才可改</li>
              <li>推薦公式:beats 重疊 + 接受率 + 距上次 pitched 時間</li>
              <li>非 admin 看不到 phone(PDPA)· 推薦只 admin 可用</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">📅</div>
          <div>
            <h3>社群貼文排程</h3>
            <p>左側「社群排程」· FB / IG / LinkedIn 排程發布(目前 mock · 真 API 等審核)。</p>
            <ul>
              <li>排定時間用本地時區 · 內部自動轉 UTC</li>
              <li>失敗 3 次 retry · 第 3 次寫 audit_log 給 admin</li>
              <li>真 Meta/LinkedIn 接入 · 等承富老闆走 developer app(1-2 週)</li>
            </ul>
          </div>
        </div>

        <div class="help-step">
          <div class="help-step-num">📸</div>
          <div>
            <h3>場勘 PWA</h3>
            <p>左側「場勘」· iPhone 開瀏覽器到 launcher · 拍 1-5 張照片 + GPS · Claude Vision 自動結構化。</p>
            <ul>
              <li>會 AI 描述每張 + 彙整成 場地類型 / 入口 / 洗手間 / 停車 / 問題</li>
              <li><b>iPhone 用戶:</b> 設定 → 相機 → 格式 → 改「最相容」(否則拍出來是 HEIC 會被擋)</li>
              <li>一鍵推到 project.handoff(獨立 site_issues 不覆寫人工)</li>
              <li>2 年後自動 TTL 清(活動週期 + 復盤)</li>
            </ul>
          </div>
        </div>
      </section>
    `;
  },

  // ============================================================
  // 2. 5 Workspace
  // ============================================================
  _renderWorkspaces() {
    const workspaces = [
      {
        num: 1, color: "#FF3B30", icon: "🎯", name: "投標",
        desc: "看到招標須知 → 送件前最後一哩",
        agents: ["Go/No-Go 評估", "招標須知解析", "服務建議書初稿", "競品視覺研究", "簡報視覺架構"],
        slash: "/bid",
      },
      {
        num: 2, color: "#FF9500", icon: "🎪", name: "活動執行",
        desc: "企劃到現場到驗收 全流程",
        agents: ["3D 場景 Brief", "舞台技術", "動線與交通", "現場流程", "廠商比價", "委外合約"],
        slash: "/event",
      },
      {
        num: 3, color: "#AF52DE", icon: "🎨", name: "設計協作",
        desc: "PM ↔ 設計師無痛溝通",
        agents: ["主視覺概念", "Brief 結構化", "Fal.ai 生圖(3 張)", "多渠道適配", "活動視覺系統"],
        slash: "/design",
      },
      {
        num: 4, color: "#34C759", icon: "📣", name: "公關溝通",
        desc: "對外發聲全流程",
        agents: ["新聞稿", "社群貼文", "月度企劃", "Email 草稿", "會議速記"],
        slash: "/pr",
      },
      {
        num: 5, color: "#007AFF", icon: "📊", name: "營運後勤",
        desc: "內部管理中樞",
        agents: ["結案報告", "專案報價", "里程碑追蹤", "CRM 紀錄", "NDA / 合約", "稅務", "Onboarding", "知識查"],
        slash: "/ops",
      },
    ];

    return `
      <section id="help-workspaces" class="help-section">
        <h2>🎯 5 個 Workspace · 按 ⌘1 ~ ⌘5 切</h2>
        <p>承富 AI 以「工作情境」組織 · 不是 agent 清單。每個 Workspace 有自己的封面 / 流程 / 近期對話:</p>

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
                <b>Slash 命令:</b> <code>${ws.slash}</code>
              </div>
            </div>
          `).join("")}
        </div>
      </section>
    `;
  },

  // ============================================================
  // 3. 10 Agent
  // ============================================================
  _renderAgents() {
    const agents = [
      { num: "00", name: "主管家", desc: "D-010 跨 Workspace orchestrator · 自動分派工作", ws: "全" },
      { num: "01", name: "投標顧問", desc: "招標須知解析 · 服務建議書初稿", ws: "投標" },
      { num: "02", name: "活動策劃", desc: "3D 場景 brief · 動線 · 現場流程", ws: "活動" },
      { num: "03", name: "設計夥伴", desc: "主視覺概念 · Fal.ai 生圖 · 多渠道適配", ws: "設計" },
      { num: "04", name: "公關文案", desc: "新聞稿 · 社群貼文 · Email 草稿", ws: "公關" },
      { num: "05", name: "結案報告", desc: "結案撰寫 · KPI 回顧 · 下次改進", ws: "營運" },
      { num: "06", name: "財務 / 報價", desc: "專案報價 · 毛利試算 · 月度報告", ws: "營運" },
      { num: "07", name: "法務 / 合約", desc: "NDA · 授權書 · 合約初稿", ws: "營運" },
      { num: "08", name: "CRM 管家", desc: "客戶紀錄 · 標案 → 提案 → 得標 pipeline", ws: "營運" },
      { num: "09", name: "知識查手", desc: "全文搜 NAS · 過往案例 · 公司手冊", ws: "全" },
    ];

    return `
      <section id="help-agents" class="help-section">
        <h2>🤖 10 個 AI 助手速覽</h2>
        <p>原 PDF 提案的 29 個精簡為 10 個核心 · 涵蓋 100% 功能。主管家(#00)會自動調度其他 9 個。</p>

        <table class="help-agents-table">
          <thead><tr><th>#</th><th>助手</th><th>說明</th><th>Workspace</th></tr></thead>
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
      { keys: "⌘K", desc: "全域指令面板(模糊搜 Workspace / Agent / Slash)" },
      { keys: "⌘0", desc: "回首頁 Dashboard" },
      { keys: "⌘1 ~ ⌘5", desc: "切到對應 Workspace" },
      { keys: "⌘N", desc: "新對話" },
      { keys: "⌘/", desc: "Slash 命令面板" },
      { keys: "Esc", desc: "關 modal / 取消輸入" },
      { keys: "Enter", desc: "送出對話(中文輸入法時 Shift+Enter 送)" },
      { keys: "Shift+Enter", desc: "對話內換行" },
      { keys: "⌘,", desc: "設定面板(admin)" },
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
        <p>承富 AI 送任何東西給雲端 Claude API 之前 · 請先判斷分級:</p>

        <div class="help-level help-level-01">
          <h3>Level 01 · 公開(白色)</h3>
          <p><b>例:</b>行銷通稿 · 通案研究 · 已公告政府資訊</p>
          <p><b>處理:</b>✅ 可直接送雲端 Claude API</p>
        </div>

        <div class="help-level help-level-02">
          <h3>Level 02 · 一般(黃色)</h3>
          <p><b>例:</b>招標須知 · 服務建議書 · 預算分析 · 客戶會議紀錄(去識別化)</p>
          <p><b>處理:</b>⚠️ 去識別化後可送雲 · 客戶名 / 電話 / 地址先打碼</p>
        </div>

        <div class="help-level help-level-03">
          <h3>Level 03 · 機敏(紅色)</h3>
          <p><b>例:</b>選情分析 · 客戶機敏 · 未公告標案內情 · 競爭對手情報</p>
          <p><b>處理:</b>🚫 絕不送雲 API · 人工處理或 v2.0 本地 Ollama</p>
          <p><b>系統自動擋:</b>含「選情」/「競情」/「內情」等關鍵字 · 送出前彈警告</p>
        </div>

        <p class="help-sop-note">
          不確定分級?預設視為 Level 02 · 先去識別化再送。<br>
          詳見 <code>docs/DATA-CLASSIFICATION-POSTER.md</code>(A3 海報已貼辦公室牆)
        </p>
      </section>
    `;
  },

  // ============================================================
  // 6. API Key 管理
  // ============================================================
  _renderSecrets() {
    return `
      <section id="help-secrets" class="help-section">
        <h2>🔐 API Key 管理 & 申請</h2>
        <p>承富 AI 用到的外部服務 API Key · admin 可在此檢視狀態:</p>

        ${this._isAdmin ? `
          <div id="secrets-panel">
            <p class="help-secrets-loading">讀取中...</p>
          </div>
        ` : `
          <div class="help-secrets-noadmin">
            <p>⚠️ 只有 admin 可以管理 API Key。</p>
            <p>若 AI 回答「服務未啟用」· 請 Champion 或 Sterio 檢查 secret 設定。</p>
          </div>
        `}

        <div class="help-secret-guide">
          <h3>📖 各 key 申請指引</h3>

          <div class="help-secret-item">
            <h4>Anthropic API Key(Claude 模型 · 必填)</h4>
            <ol>
              <li>去 <a href="https://console.anthropic.com/" target="_blank" rel="noopener">console.anthropic.com</a></li>
              <li>註冊 → Settings → API Keys → Create Key</li>
              <li><b>預存 USD $50 升 Tier 2</b>(D-002 · 10 人尖峰需要)</li>
              <li>格式:<code>sk-ant-...</code></li>
              <li>裝機時由 ChengFu-AI-Installer.app 收 · 存進 macOS Keychain</li>
            </ol>
          </div>

          <div class="help-secret-item help-secret-featured">
            <h4>🎨 生圖 Provider(承富可選兩家 · 切換 IMAGE_PROVIDER)</h4>
            <table class="help-provider-compare">
              <thead><tr><th>Provider</th><th>模型</th><th>價格 / 3 張</th><th>速度</th><th>特色</th></tr></thead>
              <tbody>
                <tr>
                  <td><b>Fal.ai</b><br><code>IMAGE_PROVIDER=fal</code></td>
                  <td>Recraft v3</td>
                  <td>約 NT$ 4</td>
                  <td>12s 平均</td>
                  <td>繁中文字佳 · 品牌視覺<br>Queue 模式 · 支援 pending</td>
                </tr>
                <tr>
                  <td><b>OpenAI</b><br><code>IMAGE_PROVIDER=openai</code></td>
                  <td>gpt-image-2<br>(2026-04-21)</td>
                  <td>約 NT$ 20</td>
                  <td>15-30s</td>
                  <td>整體品質最高 · 複雜場景<br>同步回 · 無 pending</td>
                </tr>
              </tbody>
            </table>
            <p>承富預設 <b>fal</b>(成本低 5 倍)· admin 可在上方 table 切到 <b>openai</b> 需要較高品質時用。</p>
          </div>

          <div class="help-secret-item">
            <h4>Fal.ai API Key(Recraft v3 · 可前端改)</h4>
            <ol>
              <li>去 <a href="https://fal.ai/dashboard/keys" target="_blank" rel="noopener">fal.ai/dashboard/keys</a></li>
              <li>註冊 → Dashboard → API Keys → Add new key</li>
              <li>Recraft v3 ~ USD $0.04 / 張 · 3 張 ~ NT$ 4</li>
              <li>可在此 admin UI 直接設 · 不用重啟容器</li>
            </ol>
          </div>

          <div class="help-secret-item">
            <h4>OpenAI API Key(gpt-image-2 + STT · 可前端改)</h4>
            <ol>
              <li>去 <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">platform.openai.com/api-keys</a></li>
              <li>Create secret key · Tier 1 一般就夠</li>
              <li>gpt-image-2(高品質)~ USD $0.21 / 張 · 3 張 ~ NT$ 20</li>
              <li>Whisper STT ~ USD $0.006 / 分鐘(LibreChat 另讀 .env)</li>
              <li>可在此 admin UI 直接設 · 不用重啟容器</li>
            </ol>
          </div>

          <div class="help-secret-item">
            <h4>SMTP(月報自動寄信 · 選配)</h4>
            <ol>
              <li>Gmail:去 <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener">myaccount.google.com/apppasswords</a></li>
              <li>App Password(16 字母 · 非本密碼)</li>
              <li>寫進 EMAIL_USERNAME + EMAIL_PASSWORD .env(Keychain 注入)</li>
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
      if (panel) panel.innerHTML = `<p class="help-secrets-err">讀取失敗:${escapeHtml(String(e))}</p>`;
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
          ${this._secrets.map(s => `
            <tr class="${s.is_set ? 'secret-set' : 'secret-unset'} ${s.required ? 'secret-required' : ''}">
              <td>
                <b>${escapeHtml(s.label)}</b>
                ${s.required ? '<span class="badge-required">必填</span>' : '<span class="badge-optional">選配</span>'}
                <br>
                <small class="secret-desc">${escapeHtml(s.desc)}</small>
                <br>
                <code class="secret-name">${escapeHtml(s.name)}</code>
              </td>
              <td>${s.is_set ? '<span class="secret-ok">✅ 已設</span>' : '<span class="secret-miss">❌ 未設</span>'}</td>
              <td><code class="secret-preview">${escapeHtml(s.preview)}</code></td>
              <td><small>${escapeHtml(s.source)}</small></td>
              <td>
                ${s.console_url ? `<a href="${s.console_url}" target="_blank" rel="noopener" class="btn-apply">申請 →</a>` : '—'}
                ${s.frontend_writable ? `<button class="btn-edit" data-name="${escapeHtml(s.name)}">設定</button>` : '<small>走 Keychain</small>'}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    // Bind 設定按鈕
    panel.querySelectorAll(".btn-edit").forEach(btn => {
      btn.addEventListener("click", () => this._openEditModal(btn.dataset.name));
    });
  },

  async _openEditModal(name) {
    const secret = this._secrets.find(s => s.name === name);
    if (!secret) return;

    const r = await modal.prompt(
      [
        {
          name: "value",
          label: `${secret.label}`,
          type: "text",
          placeholder: secret.name === "FAL_API_KEY" ? "fal_xxx..." : "貼上 API Key",
          hint: `留空清除 · 來源:${secret.source}`,
        },
      ],
      {
        title: `設定 ${secret.label}`,
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
      toast.success(`${secret.label} 已儲存`);
      await this.loadSecrets();
    } catch (e) {
      toast.error(`儲存失敗:${String(e)}`);
    }
  },
};

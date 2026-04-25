/**
 * 承富智慧助理 · 首次引導(v4.3 + vNext 整合)
 *
 * 主路徑:角色 picker → helpTutorial(任務式 6 步)
 * 對齊老闆 top 5 任務(舊 STEPS 內容已移到 help-tutorial.js)
 *
 * 此檔保留 window.tour 介面 · 給 app.js 呼叫 · 真實作在 modules/help-tutorial.js
 * Note · 此檔仍是 non-module(<script src> 載入) · 用 dynamic import 拿 module。
 */

let _modules = null;
async function _loadModules() {
  if (_modules) return _modules;
  // 字串拼接 · 防 esbuild 在 build 時 try-resolve(這是 runtime 由 nginx 提供的絕對路徑)
  const base = "/static/modules/";
  const [tutorialMod, stateMod] = await Promise.all([
    import(base + "help-tutorial.js"),
    import(base + "help-state.js"),
  ]);
  _modules = {
    helpTutorial: tutorialMod.helpTutorial,
    setRole: stateMod.setRole,
    getRole: stateMod.getRole,
    ROLES: stateMod.ROLES,
  };
  return _modules;
}

/**
 * 第一次登入 · 沒選過角色 → 先角色 picker · 再開 tutorial
 * 已選過角色 → 直接開 tutorial
 */
async function _showRolePickerThenTutorial() {
  const { helpTutorial, setRole, getRole, ROLES } = await _loadModules();
  // 已選 OK · 直接開 tutorial
  if (getRole() !== "unknown") {
    helpTutorial.start();
    return;
  }

  // 沒選 · 用簡單 modal 問
  const overlay = document.createElement("div");
  overlay.className = "tutorial-backdrop open";
  overlay.style.zIndex = "650";

  const box = document.createElement("div");
  box.className = "tutorial-bubble open";
  box.style.zIndex = "651";
  box.innerHTML = `
    <div class="tutorial-icon">👋</div>
    <h2 class="tutorial-title">歡迎來到承富 AI</h2>
    <p class="tutorial-body" style="text-align:center;color:var(--text-secondary)">
      先告訴我你的角色 · 我會給你最相關的教學
    </p>
    <div class="help-role-picker" id="onboarding-role-picker">
      ${Object.entries(ROLES).filter(([k]) => k !== "unknown").map(([key, meta]) => `
        <button class="help-role-card" type="button" data-role="${key}">
          <div class="help-role-icon">${meta.icon}</div>
          <div class="help-role-label">${meta.label}</div>
          <div class="help-role-desc">${meta.desc}</div>
        </button>
      `).join("")}
    </div>
    <div class="tutorial-actions">
      <button class="btn-ghost" id="onboarding-skip-role">先不選 · 直接開始</button>
    </div>
  `;
  document.body.appendChild(overlay);
  document.body.appendChild(box);

  function close() {
    overlay.remove();
    box.remove();
  }

  box.querySelectorAll(".help-role-card").forEach(card => {
    card.addEventListener("click", () => {
      setRole(card.dataset.role);
      close();
      helpTutorial.start();
    });
  });
  box.querySelector("#onboarding-skip-role").addEventListener("click", () => {
    close();
    helpTutorial.start();
  });
}

const tour = {
  /** 啟動 · 配合舊 app.js 介面 */
  start() {
    _showRolePickerThenTutorial().catch(e => console.warn("[onboarding] start failed", e));
  },

  /** 跳過 */
  async skip() {
    const { helpTutorial } = await _loadModules();
    helpTutorial.skip();
    localStorage.setItem("chengfu-tour-done", new Date().toISOString());
  },
};

window.tour = tour;

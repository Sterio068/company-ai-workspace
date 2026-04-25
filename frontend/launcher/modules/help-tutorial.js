/**
 * Help Tutorial · 任務式 FTUE(First-Time User Experience)
 * ==========================================================
 * 對應 vNext A + E
 *
 * 取代舊的 4 步 click-through tour · 改成「跟著做完一個真任務」:
 *   Step 1 · 看歡迎(15s)
 *   Step 2 · 在今日 composer 輸入範例 prompt + 送出(60s)
 *   Step 3 · AI 回應後 · 點「存成工作包」(30s)
 *   Step 4 · 開工作包 · 填 handoff 4 格(60s)
 *   Step 5 · 點「複製 LINE」格式分發(15s)
 *
 * 完成 → confetti + markTaskDone("ftue-01-first-task")
 * 隨時可 skip · 但會 warn「之後找不到」
 */
import { markTaskDone, getRole, ROLES } from "./help-state.js";
import { escapeHtml } from "./util.js";

const TUTORIAL_DONE_KEY = "chengfu-tutorial-done";

const STEPS = [
  {
    id: "welcome",
    icon: "👋",
    title: "歡迎來到承富 AI",
    body: () => {
      const role = getRole();
      const meta = ROLES[role] || ROLES.unknown;
      return `
        我會帶你走完一個真實的任務,這樣你 5 分鐘後就知道:
        <ul>
          <li>怎麼把工作丟給 AI</li>
          <li>怎麼把結果存成工作包</li>
          <li>怎麼交棒給同事</li>
        </ul>
        <p style="margin-top:12px">你選的角色:<b>${meta.icon} ${escapeHtml(meta.label)}</b></p>
        <p style="color:var(--text-secondary);font-size:13px">不對?點下方「重選角色」</p>
      `;
    },
    cta: "開始 · 5 分鐘搞定",
    skipText: "我自己摸索就好",
    next: "compose",
    onEnter: () => {
      // 跳到首頁(若不在)
      if (window.app?.currentView !== "dashboard") {
        window.app?.showView?.("dashboard");
      }
    },
  },
  {
    id: "compose",
    icon: "✍️",
    title: "Step 1 · 把工作丟進來",
    body: () => `
      <p>看到首頁中央的大輸入框了嗎?把這段範例 paste 進去,然後按「<b>交給主管家</b>」:</p>
      <pre style="background:var(--bg-base);padding:12px;border-radius:6px;font-size:13px;line-height:1.5;overflow:auto;border:1px solid var(--border)">幫我整理「下週要交的中秋節活動企劃案」的接續工作清單,
我手上有客戶的 brief PDF、上次會議錄音、預算 5 萬。
列出 5 件事 + 誰要做 + 期限。</pre>
      <p style="margin-top:12px;color:var(--text-secondary);font-size:13px">💡 不用真的打 · 你看就好。等等的步驟會教你貼上 + 送出。</p>
    `,
    cta: "我輸入了 · 下一步",
    next: "save",
    onEnter: () => {
      // 把範例 prompt 預填到 composer · 但不送出
      const input = document.getElementById("today-composer-input");
      if (input && !input.value) {
        input.value = "幫我整理「下週要交的中秋節活動企劃案」的接續工作清單,我手上有客戶的 brief PDF、上次會議錄音、預算 5 萬。列出 5 件事 + 誰要做 + 期限。";
        input.dispatchEvent(new Event("input"));
      }
      // highlight 輸入框
      _highlight("#today-composer-form");
    },
  },
  {
    id: "save",
    icon: "📦",
    title: "Step 2 · 把 AI 回應存成工作包",
    body: () => `
      <p>AI 回完後,你會看到 chat pane 右上角有「<b>存成工作包</b>」按鈕。</p>
      <p>點下去 · 系統會把這串對話 + AI 整理的清單 · 包裝成一個「工作包」。</p>
      <p style="background:color-mix(in srgb, var(--blue) 8%, transparent);padding:10px;border-radius:6px;font-size:13px;border-left:3px solid var(--blue)">
        <b>為什麼要包裝?</b><br>
        ChatGPT 的對話只是聊天紀錄。承富的「工作包」會把客戶、預算、期限、對話、附件、下一步、誰負責、交棒卡 · 全部結構化保存。下次接續不用從頭講。
      </p>
    `,
    cta: "懂了 · 下一步",
    next: "handoff",
    onEnter: () => _highlight('[data-view="projects"]'),
  },
  {
    id: "handoff",
    icon: "🤝",
    title: "Step 3 · 填交棒卡 4 格",
    body: () => `
      <p>每個工作包都有「交棒卡」· 4 個欄位:</p>
      <ol style="font-size:14px;line-height:1.8">
        <li><b>目標</b> · 一句話寫這個工作要達成什麼</li>
        <li><b>限制</b> · 預算、期限、品牌規則、客戶偏好</li>
        <li><b>素材來源</b> · 哪些檔案、哪些對話可參考</li>
        <li><b>下一步</b> · 誰要做什麼、什麼時候</li>
      </ol>
      <p style="background:color-mix(in srgb, var(--green) 8%, transparent);padding:10px;border-radius:6px;font-size:13px;border-left:3px solid var(--green)">
        <b>Pro tip</b>:AI 通常會自動預填好 80%,你只要檢查 + 補空白格,30 秒搞定。
      </p>
    `,
    cta: "好 · 下一步",
    next: "share",
  },
  {
    id: "share",
    icon: "📤",
    title: "Step 4 · 分發給下一位同事",
    body: () => `
      <p>填完交棒卡 · 點下方「<b>📋 複製為 LINE</b>」或「<b>📧 複製為 Email</b>」。</p>
      <p>系統會把 4 格內容轉成適合 LINE / Email 的格式 · 直接 paste 給設計師 / PM 就好。</p>
      <pre style="background:var(--bg-base);padding:12px;border-radius:6px;font-size:13px;line-height:1.6;border:1px solid var(--border)">📌 中秋節活動企劃 · 給設計師接手

🎯 目標
3 個主視覺方向 · 含色調建議

📋 限制
• 品牌橘黃 · 預算 5 萬 · 3 天交第一版

📂 素材
• 客戶 brief PDF
• 競品參考(連結)

✅ 下一步
• 阿銘 · 出 3 個方向 · 5/2 前
• 小玉 · 約客戶提案會議 · 5/3</pre>
    `,
    cta: "讚 · 完成教學",
    next: "done",
  },
  {
    id: "done",
    icon: "🎉",
    title: "完成!你已經會 80% 的核心流程",
    body: () => `
      <p style="font-size:15px">你剛才走的這條路 · 就是承富 AI 跟 ChatGPT 最大差別:</p>
      <ul style="font-size:14px;line-height:1.8">
        <li>✅ 工作會被結構化保存(不只是對話)</li>
        <li>✅ AI 會幫你預填交棒卡(不只是回答)</li>
        <li>✅ 一鍵複製 LINE / Email(不用再手寫)</li>
      </ul>
      <p style="background:color-mix(in srgb, var(--accent) 8%, transparent);padding:12px;border-radius:6px;margin-top:16px">
        <b>下一步可以試:</b><br>
        ${_nextStepsForRole()}
      </p>
    `,
    cta: "開始用 🚀",
    skipText: null,  // 不能 skip · 已 done
    next: null,
    onEnter: () => {
      markTaskDone("ftue-01-first-task");
      localStorage.setItem(TUTORIAL_DONE_KEY, new Date().toISOString());
      _confetti();
    },
  },
];

function _nextStepsForRole() {
  const role = getRole();
  const tips = {
    boss: "按 ⌘M 進管理面板 · 看本月成本與標案漏斗",
    pm: "按 ⌘1 進投標工作區 · 貼一段招標須知試看",
    design: "按 ⌘3 進設計協作 · 主管家會幫你想 3 個 KV 方向",
    pr: "按 ⌘4 進公關溝通 · 寫第一篇新聞稿",
    account: "按 ⌘A 進會計 · 開第一張統編發票",
    unknown: "去「📖 使用教學」選你的角色 · 看為你定制的優先學習清單",
  };
  return escapeHtml(tips[role] || tips.unknown);
}

function _highlight(selector) {
  document.querySelectorAll(".tutorial-highlight").forEach(el => el.classList.remove("tutorial-highlight"));
  const el = document.querySelector(selector);
  if (el) {
    el.classList.add("tutorial-highlight");
    setTimeout(() => el.classList.remove("tutorial-highlight"), 4000);
  }
}

function _confetti() {
  // 簡單 css confetti · 不引外部 lib
  const overlay = document.createElement("div");
  overlay.className = "tutorial-confetti";
  for (let i = 0; i < 30; i++) {
    const piece = document.createElement("span");
    piece.style.left = (Math.random() * 100) + "%";
    piece.style.animationDelay = (Math.random() * 0.5) + "s";
    piece.style.background = ["#FF3B30", "#FF9500", "#34C759", "#007AFF", "#AF52DE"][i % 5];
    overlay.appendChild(piece);
  }
  document.body.appendChild(overlay);
  setTimeout(() => overlay.remove(), 3000);
}

let _currentStep = "welcome";
let _backdrop = null;
let _bubble = null;

function _build() {
  if (_backdrop) return;
  _backdrop = document.createElement("div");
  _backdrop.className = "tutorial-backdrop";
  _backdrop.onclick = () => helpTutorial.skip();
  document.body.appendChild(_backdrop);

  _bubble = document.createElement("div");
  _bubble.className = "tutorial-bubble";
  _bubble.setAttribute("role", "dialog");
  _bubble.setAttribute("aria-modal", "true");
  _bubble.setAttribute("aria-labelledby", "tutorial-title");
  document.body.appendChild(_bubble);
}

function _render() {
  _build();
  const step = STEPS.find(s => s.id === _currentStep);
  if (!step) return;
  const idx = STEPS.findIndex(s => s.id === _currentStep);
  const total = STEPS.length;

  _bubble.innerHTML = `
    <div class="tutorial-progress">
      <span class="tutorial-step-num">${idx + 1} / ${total}</span>
      <div class="tutorial-progress-bar">
        <div class="tutorial-progress-fill" style="width:${((idx + 1) / total) * 100}%"></div>
      </div>
    </div>
    <div class="tutorial-icon">${step.icon}</div>
    <h2 class="tutorial-title" id="tutorial-title">${escapeHtml(step.title)}</h2>
    <div class="tutorial-body">${step.body()}</div>
    <div class="tutorial-actions">
      ${step.skipText ? `<button class="btn-ghost" data-tutorial-skip>${escapeHtml(step.skipText)}</button>` : ""}
      ${idx > 0 && step.next ? `<button class="btn-ghost" data-tutorial-back>← 上一步</button>` : ""}
      <button class="btn-primary" data-tutorial-next>${escapeHtml(step.cta)}</button>
    </div>
    ${step.id === "welcome" ? `<button class="tutorial-role-reset" type="button" data-tutorial-role-reset>重選角色</button>` : ""}
  `;

  _backdrop.classList.add("open");
  _bubble.classList.add("open");

  if (step.onEnter) {
    try { step.onEnter(); } catch (e) { console.warn("[tutorial] onEnter", e); }
  }

  _bubble.querySelector("[data-tutorial-skip]")?.addEventListener("click", () => helpTutorial.skip());
  _bubble.querySelector("[data-tutorial-back]")?.addEventListener("click", () => helpTutorial.back());
  _bubble.querySelector("[data-tutorial-next]")?.addEventListener("click", () => helpTutorial.next());
  _bubble.querySelector("[data-tutorial-role-reset]")?.addEventListener("click", () => {
    localStorage.removeItem("chengfu-help-role");
    location.reload();
  });
}

export const helpTutorial = {
  /** 啟動 · 從 welcome 開始 */
  start() {
    _currentStep = "welcome";
    _render();
  },

  /** 下一步 */
  next() {
    const step = STEPS.find(s => s.id === _currentStep);
    if (!step) return;
    if (!step.next) {
      // done · 收尾
      this.close();
      return;
    }
    _currentStep = step.next;
    _render();
  },

  /** 上一步 */
  back() {
    const idx = STEPS.findIndex(s => s.id === _currentStep);
    if (idx > 0) {
      _currentStep = STEPS[idx - 1].id;
      _render();
    }
  },

  /** 跳過 · 之後可從 ⌘? 重新開 */
  skip() {
    if (_currentStep !== "done") {
      const ok = confirm("跳過教學?之後可從「⌘? → 重新看教學」叫回來。");
      if (!ok) return;
    }
    this.close();
  },

  /** 關閉 */
  close() {
    if (_backdrop) _backdrop.classList.remove("open");
    if (_bubble) _bubble.classList.remove("open");
    document.querySelectorAll(".tutorial-highlight").forEach(el => el.classList.remove("tutorial-highlight"));
  },

  /** 是否已完成 */
  isDone() {
    return !!localStorage.getItem(TUTORIAL_DONE_KEY);
  },

  /** 重設 · 讓 user 再走一次 */
  reset() {
    localStorage.removeItem(TUTORIAL_DONE_KEY);
  },
};

window.helpTutorial = helpTutorial;

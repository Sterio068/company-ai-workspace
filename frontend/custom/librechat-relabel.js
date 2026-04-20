/**
 * 承富 AI · LibreChat 術語中文化與「回首頁」按鈕
 *
 * 透過 nginx sub_filter 注入到每個 LibreChat 頁面,
 * 在 DOMContentLoaded 後掃描 DOM 並替換文字節點。
 *
 * 注意:LibreChat 為 React 應用,DOM 會不斷重繪,
 *      所以用 MutationObserver 持續監控。
 */

(function () {
  "use strict";

  // ============================================================
  // 路線 A · 所有 /c/* 或 /chat/* URL 都強制彈回承富 Launcher
  // 含:初次載入 + React SPA 導航(監聽 history 變化)
  // ============================================================
  function redirectIfChatPath() {
    const path = window.location.pathname;
    if (path === "/c/new" || path.startsWith("/c/") || path === "/chat" || path.startsWith("/chat/")) {
      const convoMatch = path.match(/^\/c\/([^\/]+)$/);
      const target = convoMatch && convoMatch[1] !== "new"
        ? `/?convo=${convoMatch[1]}`
        : "/";
      console.info("[ChengFu] 重導到承富 Launcher:", target);
      window.location.replace(target);
      return true;
    }
    return false;
  }

  // 初次載入立刻檢查
  if (redirectIfChatPath()) return;

  // React SPA 導航:monkey-patch pushState / replaceState + popstate
  const origPush = history.pushState;
  const origReplace = history.replaceState;
  history.pushState = function () {
    origPush.apply(this, arguments);
    redirectIfChatPath();
  };
  history.replaceState = function () {
    origReplace.apply(this, arguments);
    redirectIfChatPath();
  };
  window.addEventListener("popstate", redirectIfChatPath);

  // 登入頁登入成功後,LibreChat 的 navigate('/c/new')
  // 我們透過 URL 監聽每 300ms 檢查(最保險)
  let lastPath = window.location.pathname;
  setInterval(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      redirectIfChatPath();
    }
  }, 300);

  // ============================== 術語對照表 ==============================
  const TERMS = {
    // 英文 → 繁中(對 AI 小白友善)
    "Endpoint": "AI 引擎",
    "endpoint": "AI 引擎",
    "Preset": "助手模板",
    "presets": "助手模板",
    "Prompts": "快速指令",
    "Prompt": "指令",
    "Temperature": "創意程度",
    "Max Tokens": "最大輸出字數",
    "Max output tokens": "最大輸出字數",
    "Top P": "取樣範圍",
    "Agents": "助手",
    "Agent": "助手",
    "New Chat": "新對話",
    "New Agent": "新增助手",
    "Send a message": "把你想問的打進來…",
    "Regenerate": "重新產生",
    "Stop generating": "停止",
    "Files": "檔案",
    "Upload File": "上傳檔案",
    "Upload files": "上傳檔案",
    "Settings": "設定",
    "Profile": "個人資料",
    "Logout": "登出",
    "Sign out": "登出",
    "Dark": "深色",
    "Light": "淺色",
    "System": "跟隨系統",
  };

  // ============================== 文字節點替換 ==============================
  function replaceText(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const txt = node.nodeValue;
      if (!txt || !txt.trim()) return;
      let newTxt = txt;
      for (const [en, tw] of Object.entries(TERMS)) {
        // 完整單字才取代(避免「prompts」取代到其他字裡)
        const re = new RegExp(`\\b${en}\\b`, "g");
        newTxt = newTxt.replace(re, tw);
      }
      if (newTxt !== txt) node.nodeValue = newTxt;
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      // 不掃描 textarea / input(避免把使用者輸入換掉)
      if (["TEXTAREA", "INPUT", "SCRIPT", "STYLE"].includes(node.tagName)) return;
      // placeholder 也要替換
      if (node.placeholder && TERMS[node.placeholder]) {
        node.placeholder = TERMS[node.placeholder];
      }
      // aria-label
      if (node.ariaLabel && TERMS[node.ariaLabel]) {
        node.ariaLabel = TERMS[node.ariaLabel];
      }
      for (const child of node.childNodes) replaceText(child);
    }
  }

  // ============================== 「回承富首頁」按鈕 ==============================
  function addHomeButton() {
    if (document.querySelector(".chengfu-home-btn")) return;
    const btn = document.createElement("button");
    btn.className = "chengfu-home-btn";
    btn.innerHTML = "← 承富首頁";
    btn.title = "回到 5 Workspace 首頁";
    btn.onclick = () => { window.location.href = "/"; };
    document.body.appendChild(btn);
  }

  // ============================== Admin 偵測 ==============================
  // LibreChat v0.8.4 用 /api/user 取得當前使用者
  async function detectRole() {
    try {
      const r = await fetch("/api/user", { credentials: "include" });
      if (!r.ok) return;
      const user = await r.json();
      if (user.role === "ADMIN") {
        document.documentElement.dataset.role = "admin";
      }
    } catch (e) { /* silent */ }
  }

  // ============================== MutationObserver ==============================
  function startObserver() {
    const obs = new MutationObserver(mutations => {
      for (const m of mutations) {
        for (const n of m.addedNodes) {
          replaceText(n);
        }
      }
      // 每次 DOM 變動都掃一次 feedback 按鈕
      scanForFeedback();
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  // ============================== 👍👎 回饋按鈕 ==============================
  // 在每個 AI 訊息下方注入 👍👎 按鈕,點擊存 localStorage
  // v1.1 會改為 POST 到後端 MongoDB
  const FEEDBACK_KEY = "chengfu-feedback-v1";
  const FEEDBACK_API = "/api-accounting/feedback";

  function loadFeedback() {
    // localStorage cache(快速查已按過什麼)
    try { return JSON.parse(localStorage.getItem(FEEDBACK_KEY) || "{}"); }
    catch (e) { return {}; }
  }

  async function saveFeedback(messageId, verdict, note) {
    // 1. 本地快取(UI 即時回應)
    const store = loadFeedback();
    store[messageId] = { verdict, note: note || "", at: new Date().toISOString() };
    localStorage.setItem(FEEDBACK_KEY, JSON.stringify(store));

    // 2. POST 到 MongoDB(團隊共享 + 品質分析)
    try {
      // 嘗試從頁面或 localStorage 抓 Agent 名稱 / 使用者 email
      const agentName = document.querySelector("[data-testid='agent-name'], [class*='agent-title']")?.textContent
                        || document.title.replace("LibreChat", "").trim() || "unknown";
      const userEmail = document.documentElement.dataset.userEmail || "";

      await fetch(FEEDBACK_API, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          message_id: messageId,
          conversation_id: window.location.pathname.split("/c/")[1] || null,
          agent_name: agentName,
          verdict: verdict,
          note: note || "",
          user_email: userEmail,
        }),
      });
    } catch (e) {
      console.warn("Feedback API 未就緒,只存 localStorage");
    }
  }

  function injectFeedback(msgEl) {
    if (msgEl.dataset.chengfuFb === "1") return;
    if (!msgEl.dataset.messageId && !msgEl.getAttribute("data-message-id")) return;

    const messageId = msgEl.dataset.messageId || msgEl.getAttribute("data-message-id");

    // 只對 AI 訊息注入(不對使用者訊息)
    const role = msgEl.dataset.role || msgEl.getAttribute("data-role") || "";
    if (role === "user") return;

    const bar = document.createElement("div");
    bar.className = "chengfu-fb-bar";
    bar.innerHTML = `
      <button class="chengfu-fb-btn" data-verdict="up" title="這個回答有幫到">👍</button>
      <button class="chengfu-fb-btn" data-verdict="down" title="回答不好 / 錯誤">👎</button>
    `;

    const existing = loadFeedback()[messageId];
    if (existing) {
      bar.querySelector(`[data-verdict="${existing.verdict}"]`)?.classList.add("active");
    }

    bar.querySelectorAll(".chengfu-fb-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        const verdict = btn.dataset.verdict;
        let note = "";
        if (verdict === "down") {
          note = prompt("幫我們改進 · 哪裡不好?(可空白)", "") || "";
        }
        saveFeedback(messageId, verdict, note);
        bar.querySelectorAll(".chengfu-fb-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });

    msgEl.appendChild(bar);
    msgEl.dataset.chengfuFb = "1";
  }

  function scanForFeedback() {
    // LibreChat 的訊息 element 可能用不同 class/attr,嘗試多種 selector
    const selectors = [
      "[data-message-id]",
      "[data-testid='message-text']",
      "[role='listitem']",
    ];
    for (const sel of selectors) {
      document.querySelectorAll(sel).forEach(injectFeedback);
    }
  }

  function injectFeedbackStyles() {
    if (document.getElementById("chengfu-fb-style")) return;
    const s = document.createElement("style");
    s.id = "chengfu-fb-style";
    s.textContent = `
      .chengfu-fb-bar {
        display: inline-flex;
        gap: 4px;
        margin-top: 8px;
        padding: 4px 6px;
        background: rgba(0,0,0,0.04);
        border-radius: 6px;
      }
      .chengfu-fb-btn {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 14px;
        padding: 2px 6px;
        border-radius: 4px;
        opacity: 0.5;
        transition: all 0.15s;
      }
      .chengfu-fb-btn:hover { opacity: 1; background: rgba(0,0,0,0.08); }
      .chengfu-fb-btn.active { opacity: 1; background: rgba(15, 35, 64, 0.12); }
    `;
    document.head.appendChild(s);
  }

  // ============================== 使用者送出的 pending 輸入 ==============================
  // Launcher 送到 localStorage 的 chengfu-pending-input,
  // 在 LibreChat 載入完成後自動填入輸入框
  function injectPendingInput() {
    const pending = localStorage.getItem("chengfu-pending-input");
    if (!pending) return;

    const tryFill = () => {
      const textarea = document.querySelector("textarea[placeholder*='訊息'], textarea[placeholder*='Message'], textarea[data-testid='text-input']");
      if (textarea) {
        textarea.value = pending;
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
        localStorage.removeItem("chengfu-pending-input");
        textarea.focus();
        return true;
      }
      return false;
    };

    if (!tryFill()) {
      // 重試 5 次(React 元件可能晚載)
      let retries = 0;
      const iv = setInterval(() => {
        if (tryFill() || ++retries >= 10) clearInterval(iv);
      }, 300);
    }
  }

  // ============================== Bootstrap ==============================
  function init() {
    replaceText(document.body);
    addHomeButton();
    detectRole();
    injectFeedbackStyles();
    scanForFeedback();
    injectPendingInput();
    startObserver();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

/**
 * LibreChat 術語中文化與「回首頁」按鈕(v1.8 multi-tenant)
 *
 * 透過 nginx sub_filter 注入到每個 LibreChat 頁面,
 * 在 DOMContentLoaded 後掃描 DOM 並替換文字節點。
 *
 * v1.8 改:首頁按鈕 label 從 hardcode 「承富」改為動態讀
 *         /api-accounting/admin/branding 的 company_short
 *
 * 注意:LibreChat 為 React 應用,DOM 會不斷重繪,
 *      所以用 MutationObserver 持續監控。
 */

(function () {
  "use strict";

  // ============================================================
  // 路線 A · 所有 /c/* 或 /chat/* URL 都強制彈回 Launcher
  // 含:初次載入 + React SPA 導航(監聽 history 變化)
  // ============================================================
  // v4.6 · 同時抓 pathname 與 hash · 防 LibreChat 升版改成 hash router
  function _matchChatPath(pathOrHash) {
    if (!pathOrHash) return null;
    // pathname 形式 · /c/new · /c/<id> · /chat · /chat/...
    const m = pathOrHash.match(/^\/?c\/([^\/?#]+)$/);
    if (m) return m[1] === "new" ? "/" : `/?convo=${m[1]}`;
    if (pathOrHash === "/chat" || pathOrHash.startsWith("/chat/") ||
        pathOrHash === "chat"  || pathOrHash.startsWith("chat/")) return "/";
    return null;
  }

  function redirectIfChatPath() {
    const path = window.location.pathname;
    // hash 也檢查 · 移掉開頭 # 後判斷
    const hashRaw = (window.location.hash || "").replace(/^#/, "");
    const target = _matchChatPath(path) || _matchChatPath(hashRaw);
    if (target) {
      console.info("[launcher-relabel] redirect to launcher:", target, "from", path, hashRaw);
      window.location.replace(target);
      return true;
    }
    return false;
  }

  // 初次載入立刻檢查
  if (redirectIfChatPath()) return;

  // React SPA 導航:monkey-patch pushState / replaceState + popstate + hashchange
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
  // v4.6 · LibreChat 若改 hash router(#/c/new)· hashchange 接到
  window.addEventListener("hashchange", redirectIfChatPath);

  // 登入頁登入成功後,LibreChat 的 navigate('/c/new')
  // 我們透過 URL 監聽每 300ms 檢查(最保險 · 同時看 path + hash)
  let lastPath = window.location.pathname;
  let lastHash = window.location.hash;
  setInterval(() => {
    if (window.location.pathname !== lastPath || window.location.hash !== lastHash) {
      lastPath = window.location.pathname;
      lastHash = window.location.hash;
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
    "Search": "搜尋",
    "Conversations": "對話紀錄",
    "Conversation": "對話",
    "Create": "建立",
    "Save": "儲存",
    "Cancel": "取消",
    "Delete": "刪除",
    "Edit": "編輯",
    "Continue": "繼續",
    "Submit": "送出",
    "Regenerate": "重新產生",
    "Stop generating": "停止",
    "Files": "檔案",
    "Upload File": "上傳檔案",
    "Email address": "電子郵件",
    "Upload files": "上傳檔案",
    "Email": "電子郵件",
    "Password": "密碼",
    "Forgot password?": "忘記密碼?",
    "Sign in": "登入",
    "Log in": "登入",
    "Login": "登入",
    "Register": "註冊",
    "Welcome back": "歡迎回來",
    "Continue with Google": "使用 Google 繼續",
    "Privacy policy": "隱私權政策",
    "Terms of service": "服務條款",
    "Settings": "設定",
    "Profile": "個人資料",
    "Logout": "登出",
    "Sign out": "登出",
    "Dark": "深色",
    "Light": "淺色",
    "System": "跟隨系統",
    "Toggle theme": "切換深淺色",
  };

  function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // ============================== 文字節點替換 ==============================
  function replaceText(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const txt = node.nodeValue;
      if (!txt || !txt.trim()) return;
      let newTxt = txt;
      for (const [en, tw] of Object.entries(TERMS)) {
        // 完整單字才取代(避免「prompts」取代到其他字裡)
        const pattern = /^[A-Za-z0-9 ]+$/.test(en) ? `\\b${escapeRegExp(en)}\\b` : escapeRegExp(en);
        const re = new RegExp(pattern, "g");
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

  // ============================== 「回首頁」按鈕(v1.8 multi-tenant) ==============================
  // 從 /api-accounting/admin/branding 拉品牌名 · 動態組合
  let _brandCache = null;
  async function getBrand() {
    if (_brandCache) return _brandCache;
    try {
      const r = await fetch("/api-accounting/admin/branding", { credentials: "include" });
      if (r.ok) _brandCache = await r.json();
    } catch (e) { /* silent · 用 default */ }
    if (!_brandCache) _brandCache = { app_name: "智慧助理", company_short: "" };
    return _brandCache;
  }

  async function addHomeButton() {
    if (window.location.pathname === "/login") return;
    if (document.querySelector(".chengfu-home-btn")) return;
    const brand = await getBrand();
    const homeLabel = brand.company_short ? `${brand.company_short} 首頁` : "首頁";
    const btn = document.createElement("button");
    btn.className = "chengfu-home-btn";
    btn.innerHTML = `← ${homeLabel}`;
    btn.title = `回到 ${brand.app_name} 首頁`;
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
      console.warn("回饋介接未就緒,只存本機暫存");
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

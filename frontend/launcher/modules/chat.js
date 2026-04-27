/**
 * Chat Pane · Launcher 內建對話介面(路線 A · 不跳 LibreChat 頁)
 * 呼叫 /api/agents/chat · SSE 串流
 */
import { escapeHtml } from "./util.js";
import { modal } from "./modal.js";
import { toast } from "./toast.js";
import { authFetch, SessionExpiredError } from "./auth.js";
import { AI_PROVIDERS, AI_PROVIDER_KEY, DEFAULT_AI_PROVIDER, CORE_AGENTS, agentRoleName, ATTACHMENT, STORAGE_KEY } from "./config.js";
import { Projects } from "./projects.js";
import { sanitizeRenderedHtml as _sanitizeRenderedHtml } from "./chat-sanitize.js";
import { validateAttachment as _validateAttachmentFn, composeUserMessageSummary as _composeSummaryFn, isSameFile as _isSameFile } from "./chat-attachments.js";

// v1.50 · 從 config.js 拉共享常數 · 與 app.js today 附件規格一致
const { MAX_COUNT: MAX_ATTACHMENT_COUNT, MAX_BYTES: MAX_ATTACHMENT_BYTES, SUPPORTED_EXT: SUPPORTED_ATTACHMENT_EXT } = ATTACHMENT;

export const chat = {
  currentAgentNum: null,
  currentAgentId:  null,
  currentProvider: null,
  currentConvoId:  null,
  currentProjectContext: null,
  isStreaming:     false,
  attachments:     [],
  pendingHandoffSave: null,
  _agentsStore:    null,   // app 注入,用來查 agent.id
  _userStore:      null,   // app 注入,用來帶 email 給 feedback
  _providerStore:  null,   // app 注入,用來決定 OpenAI / Claude 版本

  // v1.50 · DOM 元件 cache · 避免每次 send/render 都 getElementById
  // 元件在 init 後就不會 detach,可以放心 cache · 第一次查到後常駐
  _elsCache: {},
  _$(id) {
    let el = this._elsCache[id];
    if (el && el.isConnected) return el;
    el = document.getElementById(id);
    if (el) this._elsCache[id] = el;
    return el;
  },

  bind({ agents, user, provider }) {
    this._agentsStore = agents;
    this._userStore = user;
    this._providerStore = provider;
    this._bindSuggestions();
    this._initPaneResize();
    this._initFullscreen();
    this._initTextareaResize();
  },

  // v1.48 · 偵測 user 手動拖 textarea 右下角 · 標記 data-user-sized=1
  // 避免 onKey auto-grow 覆蓋 user 設定的高度
  _initTextareaResize() {
    const ta = this._$("chat-input");
    if (!ta || typeof ResizeObserver === "undefined") return;
    let baseHeight = ta.offsetHeight;
    const ro = new ResizeObserver(() => {
      // 若高度跟初始基準有意義差(>4px),視為 user 手動 drag
      if (Math.abs(ta.offsetHeight - baseHeight) > 4) {
        ta.dataset.userSized = "1";
      }
    });
    ro.observe(ta);
    // 雙擊縮回 auto-grow 模式
    ta.addEventListener("dblclick", (e) => {
      // 只在右下角區域才生效(避免文字選取雙擊)
      const r = ta.getBoundingClientRect();
      if (e.clientX > r.right - 20 && e.clientY > r.bottom - 20) {
        ta.dataset.userSized = "0";
        ta.style.height = "";
        baseHeight = ta.offsetHeight;
      }
    });
  },

  // v1.48 · 左緣拖曳調寬 · localStorage 記住寬度
  _initPaneResize() {
    const PANE_W_KEY = STORAGE_KEY.CHAT_PANE_W;
    const MIN_W = 360;
    const MAX_W = Math.min(1400, window.innerWidth);
    const saved = parseInt(localStorage.getItem(PANE_W_KEY) || "", 10);
    if (saved && saved >= MIN_W) {
      document.documentElement.style.setProperty(
        "--chat-pane-w",
        Math.min(saved, window.innerWidth) + "px",
      );
    }
    const handle = this._$("chat-pane-resizer");
    const pane = this._$("chat-pane");
    if (!handle || !pane) return;
    let dragging = false;
    handle.addEventListener("mousedown", (e) => {
      e.preventDefault();
      dragging = true;
      pane.classList.add("resizing");
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const w = Math.max(MIN_W, Math.min(window.innerWidth, window.innerWidth - e.clientX));
      document.documentElement.style.setProperty("--chat-pane-w", w + "px");
    });
    window.addEventListener("mouseup", () => {
      if (!dragging) return;
      dragging = false;
      pane.classList.remove("resizing");
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      const cur = getComputedStyle(document.documentElement).getPropertyValue("--chat-pane-w").trim();
      const px = parseInt(cur, 10);
      if (px && px >= MIN_W) localStorage.setItem(PANE_W_KEY, String(px));
    });
  },

  // v1.48 · 全螢幕模式 · ⌘⇧F 切換 · localStorage 記住
  _initFullscreen() {
    const FS_KEY = STORAGE_KEY.CHAT_FULLSCREEN;
    if (localStorage.getItem(FS_KEY) === "1") {
      this._applyFullscreen(true);
    }
    window.addEventListener("keydown", (e) => {
      // ⌘⇧F (Mac) / Ctrl⇧F (其他) 切全螢幕 · 僅在 chat 開啟時
      const inChat = this._$("chat-pane")?.classList.contains("open");
      if (!inChat) return;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.shiftKey && (e.key === "F" || e.key === "f")) {
        e.preventDefault();
        this.toggleFullscreen();
      }
    });
  },

  toggleFullscreen() {
    const pane = this._$("chat-pane");
    if (!pane) return;
    const next = !pane.classList.contains("fullscreen");
    this._applyFullscreen(next);
    localStorage.setItem(STORAGE_KEY.CHAT_FULLSCREEN, next ? "1" : "0");
  },

  _applyFullscreen(on) {
    const pane = this._$("chat-pane");
    const btn = this._$("chat-fullscreen-btn");
    if (!pane) return;
    pane.classList.toggle("fullscreen", on);
    document.body.classList.toggle("chat-fullscreen", on);
    if (btn) {
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "⤓" : "⛶";
      btn.title = on ? "退出全螢幕 (⌘⇧F)" : "全螢幕 (⌘⇧F)";
    }
  },

  // v1.3 P1#15 · 空對話建議 prompt · AI 小白起步友善
  _bindSuggestions() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".chat-suggestion");
      if (!btn) return;
      const prompt = btn.dataset.prompt;
      if (!prompt) return;
      const input = this._$("chat-input");
      if (!input) return;
      input.value = prompt;
      input.dispatchEvent(new Event("input"));  // 觸發 L1/L2/L3 classifier
      // 自動送?先填入讓用戶看 · 按 Enter 再送
      input.focus();
    });
  },

  getSelectedProvider() {
    const selected = this._providerStore?.() || localStorage.getItem(AI_PROVIDER_KEY) || DEFAULT_AI_PROVIDER;
    return AI_PROVIDERS[selected] ? selected : DEFAULT_AI_PROVIDER;
  },

  _normalizeProvider(value = "") {
    const text = String(value || "").toLowerCase();
    if (text.includes("openai") || text.includes("open ai") || text.includes("gpt")) return "openai";
    if (text.includes("anthropic") || text.includes("claude")) return "anthropic";
    return "";
  },

  _agentProvider(agent) {
    const metadata = agent.metadata || {};
    const raw = [
      agent.provider,
      agent.endpoint,
      metadata.provider,
      metadata.endpoint,
      agent.model,
      agent.name,
      agent.description,
    ].filter(Boolean).join(" ");
    return this._normalizeProvider(raw);
  },

  _agentModel(agent) {
    return agent.model || agent.modelName || agent.model_name || agent.metadata?.model || "";
  },

  _agentMatchesNumber(agent, meta, num) {
    const name = agent.name || "";
    const description = agent.description || "";
    const metadata = agent.metadata || {};
    return (
      metadata.number === num ||
      metadata.num === num ||
      description.includes(`#${num}`) ||
      description.includes(`number=${num}`) ||
      name.includes(meta.name)
    );
  },

  _findAgentByNum(num) {
    const list = this._agentsStore?.() || [];
    const meta = CORE_AGENTS.find(a => a.num === num);
    if (!meta) return null;
    const candidates = list.filter(agent => this._agentMatchesNumber(agent, meta, num));
    if (!candidates.length) return null;
    const selected = this.getSelectedProvider();
    return candidates.find(agent => this._agentProvider(agent) === selected) || candidates[0];
  },

  async _waitForAgentByNum(agentNum, timeoutMs = 3000) {
    const startedAt = Date.now();
    let agent = this._findAgentByNum(agentNum);
    while (!agent && Date.now() - startedAt < timeoutMs) {
      await new Promise(resolve => setTimeout(resolve, 100));
      agent = this._findAgentByNum(agentNum);
    }
    return agent;
  },

  _showAgentMissing(agentNum) {
    const meta = CORE_AGENTS.find(a => a.num === agentNum) || {};
    const nice = meta.name ? `${meta.emoji || "🤖"} ${agentRoleName(meta)}` : "主管家";
    modal.alert(`系統還沒準備好「${escapeHtml(nice)}」這位助手,請聯絡管理員協助。`, {
      title: "助手尚未就緒",
      icon: "🤖",
      primary: "知道了",
    });
  },

  _selectAgent(agentNum, agent) {
    const meta = CORE_AGENTS.find(a => a.num === agentNum) || {};
    this.currentAgentNum = agentNum;
    this.currentAgentId = agent.id || agent._id;
    const selectedProvider = this.getSelectedProvider();
    const actualProvider = this._agentProvider(agent) || selectedProvider;
    const providerMeta = AI_PROVIDERS[actualProvider] || AI_PROVIDERS[selectedProvider] || AI_PROVIDERS[DEFAULT_AI_PROVIDER];
    const agentModel = this._agentModel(agent);
    setText("chat-agent-emoji", meta.emoji || "🤖");
    setText("chat-agent-name", agentRoleName(meta) || agent.name || "助手");
    setText("chat-agent-sub", `${providerMeta.label} · ${agentModel || meta.model || "標準模型"} · ${meta.desc || ""}`);
    this.currentProvider = actualProvider;
    return Boolean(this.currentAgentId);
  },

  _setProjectContext(context) {
    this.currentProjectContext = context?.projectId ? context : null;
    const badge = this._$("chat-project-link");
    if (!badge) return;
    if (!this.currentProjectContext) {
      badge.hidden = true;
      badge.textContent = "";
      return;
    }
    badge.hidden = false;
    const name = this.currentProjectContext.projectName || "目前工作包";
    const label = this.currentProjectContext.label || "AI 回覆可回寫";
    badge.textContent = `已綁定工作包:${name} · ${label}`;
  },

  async _ensureCurrentAgent(agentNum = "00") {
    const selectedProvider = this.getSelectedProvider();
    if (this.currentAgentId && this.currentProvider === selectedProvider) return true;
    const agent = await this._waitForAgentByNum(agentNum);
    if (!agent) {
      this._showAgentMissing(agentNum);
      return false;
    }
    return this._selectAgent(agentNum, agent);
  },

  async open(agentNum, initialInput, options = {}) {
    const agent = await this._waitForAgentByNum(agentNum);
    if (!agent) {
      const meta = CORE_AGENTS.find(a => a.num === agentNum);
      const nice = meta ? `${meta.emoji} ${agentRoleName(meta)}` : `#${agentNum}`;
      // 一般同仁友善版
      const isAdmin = document.documentElement.dataset.role === "admin";
      const adminHint = isAdmin
        ? `<div style="margin-top:12px;padding:10px;background:var(--bg-base);border-radius:6px;font-size:12px;color:var(--text-secondary);font-family:var(--font-mono)">
             管理員補充:執行 <code>python3 scripts/create-agents.py --tier core --provider both</code> 建立雙引擎助手
           </div>`
        : "";
      modal.alert(
        `系統還沒準備好「${escapeHtml(nice)}」這位助手,請聯絡管理員協助。${adminHint}`,
        { title: "助手尚未就緒", icon: "🤖", primary: "知道了" }
      );
      return;
    }
    this._selectAgent(agentNum, agent);
    this.currentConvoId  = null;
    this.attachments     = [];
    this.pendingHandoffSave = options.handoffSave || null;
    this._setProjectContext(options.handoffSave);

    const meta = CORE_AGENTS.find(a => a.num === agentNum) || {};
    const selectedProvider = this.getSelectedProvider();
    const actualProvider = this._agentProvider(agent) || selectedProvider;
    const providerMeta = AI_PROVIDERS[actualProvider] || AI_PROVIDERS[selectedProvider] || AI_PROVIDERS[DEFAULT_AI_PROVIDER];
    if (actualProvider !== selectedProvider) {
      const wanted = AI_PROVIDERS[selectedProvider]?.label || selectedProvider;
      const actual = providerMeta?.label || actualProvider;
      toast.warn(`找不到 ${wanted} 版「${agentRoleName(meta) || agent.name}」,已先使用 ${actual} 版`);
    }

    const msgs = this._$("chat-messages");
    if (msgs) {
      msgs.innerHTML = `
        <div class="chat-welcome">
          <div class="chat-welcome-emoji">${meta.emoji || "🤖"}</div>
          <div class="chat-welcome-title">${escapeHtml(agentRoleName(meta) || "助手")}</div>
          <div class="chat-welcome-sub">${escapeHtml(`${providerMeta.label} · ${meta.desc || "隨時為你服務"}`)}</div>
        </div>
      `;
    }
    this._$("chat-pane")?.classList.add("open");
    document.body.classList.add("chat-open");
    this._$("chat-input")?.focus();

    if (initialInput) {
      const input = this._$("chat-input");
      if (input) {
        input.value = initialInput;
        input.dispatchEvent(new Event("input"));
        if (options.autoSend === true) {
          setTimeout(() => this.send(), 100);
        }
      }
    }
  },

  close() {
    this._$("chat-pane")?.classList.remove("open");
    document.body.classList.remove("chat-open");
  },

  newConversation() {
    this.currentConvoId = null;
    this.attachments = [];
    this.pendingHandoffSave = null;
    this._setProjectContext(null);
    const attEl = this._$("chat-attachments");
    if (attEl) attEl.innerHTML = "";
    const msgs = this._$("chat-messages");
    if (msgs) msgs.innerHTML =
      '<div class="chat-welcome"><div class="chat-welcome-title">新對話</div><div class="chat-welcome-sub">上下文清空 · 開始新話題</div></div>';
    toast.info("新對話");
  },

  onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      this.send();
    }
    setTimeout(() => {
      const ta = e.target;
      // v1.48 · 若 user 已手動拖過(data-user-sized=1),不要 auto-grow 蓋掉
      if (ta.dataset.userSized === "1") return;
      ta.style.height = "auto";
      const cap = this._$("chat-pane")?.classList.contains("fullscreen") ? 600 : 200;
      ta.style.height = Math.min(cap, ta.scrollHeight) + "px";
    }, 0);
  },

  // 輸入時 debounce 去問 backend L3 classifier · 更新等級提示 badge
  _classifyTimer: null,
  onInput(e) {
    const text = (e?.target?.value || "").trim();
    const badge = this._$("chat-level-hint");
    if (!badge) return;
    if (text.length < 20) {
      badge.className = "hint-level l1";
      badge.textContent = "第一級 公開";
      badge.title = "短文字尚未判定 · 預設公開";
      return;
    }
    clearTimeout(this._classifyTimer);
    this._classifyTimer = setTimeout(async () => {
      try {
        const r = await fetch("/api-accounting/safety/classify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (!r.ok) return;
        const d = await r.json();
        const level = d.level || "01";
        if (level === "03") {
          badge.className = "hint-level l3";
          badge.textContent = "第三級提醒";
          badge.title = "偵測到可能較敏感的內容 · 系統只提醒,不阻擋送出。";
        } else if (level === "02") {
          badge.className = "hint-level l2";
          badge.textContent = "第二級一般";
          badge.title = "一般內部資料 · 需要時可自行去識別化。";
        } else {
          badge.className = "hint-level l1";
          badge.textContent = "第一級 公開";
          badge.title = "公開資訊 · 可安全上雲";
        }
      } catch { /* backend 離線 · 不改 */ }
    }, 450);
  },

  pickFile() {
    this._$("chat-file-input")?.click();
  },

  async send(e, _piiRedacted = false) {
    if (e) e.preventDefault();
    if (this.isStreaming) return;
    const input = this._$("chat-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text && this.attachments.length === 0) return;
    if (!(await this._ensureCurrentAgent("00"))) return;

    // v4.6 · request-time quota check(Round 6 紅線 + Codex Round 10.5 收緊)
    // 策略:
    //   · qr.ok + allowed=false → 擋(原本就有)
    //   · qr.ok + allowed=true → 放行 · 顯示 warning
    //   · qr.ok=false(HTTP 非 2xx) → 按 hard_stop 預期 fail-closed · 擋
    //   · 網路錯 / quota service 完全掛 → hard_stop 擋 · soft_warn 放(後端決定)
    // 注意:真正的 quota enforcement 應在後端 /api/agents/chat gateway · 這裡只是第一道
    try {
      const qr = await authFetch("/api-accounting/quota/check");
      if (qr.ok) {
        const q = await qr.json();
        if (q.allowed === false) {
          toast.error(`❌ ${q.reason || "本月用量已達上限 · 請找內部負責窗口放行"}`);
          return;
        }
        if (q.warning) {
          toast.warn(q.warning);
        }
      } else {
        // HTTP 500/503 · 後端明確告訴我們擋 · 就擋
        // (後端 hard_stop 模式會回 allowed=false + 200 · 走上面路徑;
        //  這裡只剩 endpoint 本身掛掉的情況)
        toast.error("⚠ 預算服務暫時無回應 · 為安全先暫停送出 · 請找內部負責窗口或稍後重試");
        return;
      }
    } catch (e) {
      // 網路錯(fetch 直接 throw)· 保守擋 · 老闆 Q1 選 C
      toast.error("⚠ 預算服務連不上 · 為安全暫停送出 · 請找內部負責窗口");
      return;
    }

    this.isStreaming = true;
    this._toolCallSeen = new Set();  // v1.59 #4 · 每次新 send reset · 不跨訊息 leak chip
    const sendBtn = this._$("chat-send-btn");
    if (sendBtn) sendBtn.disabled = true;

    let assistantBody = null;
    try {
      const uploadedAttachments = await this._uploadPendingAttachments();
      const userSummary = this._composeUserMessageSummary(text, uploadedAttachments);
      document.querySelector("#chat-messages .chat-welcome")?.remove();
      this.appendMessage("user", userSummary);
      input.value = "";
      input.style.height = "auto";

      assistantBody = this.appendMessage("assistant", "", true);
      await this._stream(text || "請先閱讀我附上的檔案,整理重點並詢問我下一步要做什麼。", assistantBody, uploadedAttachments);
    } catch (err) {
      // Session 過期:banner 已由 authFetch 顯示 · 訊息框靜默移除佔位,避免紅字誤導
      if (err instanceof SessionExpiredError) {
        assistantBody?.closest(".chat-msg")?.remove();
      } else if (!assistantBody) {
        toast.error(err.message || "附件上傳失敗 · 請稍後重試");
      } else {
        assistantBody.innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(err.message || "送出失敗")}</span>`;
      }
    } finally {
      this.isStreaming = false;
      if (sendBtn) sendBtn.disabled = false;
      this._finishStream(assistantBody);  // v1.57 a11y · 切 aria-live + SR announce
      const msgEl = assistantBody?.closest(".chat-msg");
      if (msgEl && !msgEl.querySelector(".chat-msg-actions")) {
        this._attachFeedback(msgEl);
      }
    }
  },

  async _stream(text, assistantBodyEl, uploadedAttachments = []) {
    const requestStartedAt = Date.now();
    const body = {
      agent_id: this.currentAgentId,
      conversationId: this.currentConvoId || "new",
      parentMessageId: "00000000-0000-0000-0000-000000000000",
      text,
      endpoint: "agents",
      isContinued: false,
      isTemporary: false,
      messageId: crypto.randomUUID?.() || String(Date.now()),
    };
    if (uploadedAttachments.length) {
      body.files = uploadedAttachments.map(file => ({
        file_id: file.file_id,
        filename: file.filename,
        type: file.type,
        bytes: file.bytes,
      }));
    }
    const resp = await authFetch("/api/agents/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${errText.slice(0, 200)}`);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let accumulated = "";
    const processPayload = (data) => {
      if (!data || typeof data !== "object") return;
      // v1.59 #4 · 偵測 tool call 並 inline 顯示「⚙ 主管家正在呼叫 PCC...」
      // LibreChat / OpenAI Agent SSE 在 tool 呼叫時送 tool_call / function_call event
      this._maybeShowToolCall(data, assistantBodyEl);
      const extracted = this._messageText(data);
      if (!extracted) return;
      if (data.delta || data.choices?.[0]?.delta) accumulated += extracted;
      else accumulated = extracted;
      if (accumulated) this.renderMarkdown(assistantBodyEl, accumulated);
    };
    const processEvent = (evt) => {
      const trimmed = (evt || "").trim();
      if (!trimmed) return;
      const dataLines = trimmed
        .split("\n")
        .filter(l => l.startsWith("data: "))
        .map(l => l.substring(6));
      const payloads = dataLines.length ? dataLines : [trimmed];
      for (const line of payloads) {
        if (line === "[DONE]") continue;
        try {
          const data = JSON.parse(line);
          const conversationId =
            data.conversationId ||
            data.conversation?.conversationId ||
            data.message?.conversationId ||
            data.responseMessage?.conversationId ||
            data.finalMessage?.conversationId;
          if (conversationId) {
            this.currentConvoId = conversationId;
          }
          processPayload(data);
        } catch { /* skip non-json */ }
      }
    };
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";  // 保護:若 chunk 剛好以 \n\n 結尾,pop() 會是 undefined
      for (const evt of events) processEvent(evt);
    }
    processEvent(buffer);
    if (!accumulated && this.currentConvoId) {
      accumulated = await this._hydrateLatestAssistant(assistantBodyEl, {
        parentMessageId: body.messageId,
        createdAfter: requestStartedAt - 1000,
        verifyExists: true,
      });
    }
    if (!accumulated) {
      accumulated = await this._hydrateRecentAssistant(assistantBodyEl, {
        parentMessageId: body.messageId,
        createdAfter: requestStartedAt - 1000,
        promptText: text,
      });
    }
    if (!accumulated) {
      throw new Error("AI 已回應,但回傳格式沒有可顯示文字 · 請稍後重試");
    }
  },

  _extractContentText(content) {
    if (!content) return "";
    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
      return content
        .map(part => {
          if (!part) return "";
          if (typeof part === "string") return part;
          if (part.type === "text" && typeof part.text === "string") return part.text;
          if (typeof part.text === "string" && part.type !== "tool_call") return part.text;
          return this._extractContentText(part.content);
        })
        .filter(Boolean)
        .join("\n\n");
    }
    if (typeof content === "object") {
      if (typeof content.text === "string") return content.text;
      return this._extractContentText(content.content);
    }
    return "";
  },

  _messageText(message) {
    if (!message || typeof message !== "object") return "";
    if (typeof message.text === "string" && message.text.trim()) return message.text;
    if (typeof message.delta?.content === "string") return message.delta.content;
    if (typeof message.choices?.[0]?.delta?.content === "string") return message.choices[0].delta.content;
    if (typeof message.message?.text === "string" && message.message.text.trim()) return message.message.text;
    return (
      this._extractContentText(message.content) ||
      this._extractContentText(message.message?.content) ||
      this._extractContentText(message.responseMessage?.content) ||
      this._extractContentText(message.finalMessage?.content)
    );
  },

  async _conversationExists(conversationId) {
    if (!conversationId) return false;
    try {
      const r = await authFetch(`/api/convos?pageSize=20&_=${Date.now()}`);
      if (!r.ok) return true; // 清單 API 暫時失敗時,保守維持原本回填路徑。
      const payload = await r.json();
      const convos = Array.isArray(payload) ? payload : (payload.conversations || payload.data || []);
      return convos.some(c => (c.conversationId || c._id || c.id) === conversationId);
    } catch {
      return true;
    }
  },

  async _hydrateLatestAssistant(assistantBodyEl, options = {}) {
    const {
      parentMessageId,
      createdAfter,
      conversationId = this.currentConvoId,
      verifyExists = false,
    } = options;
    const attempts = parentMessageId ? 8 : 1;
    if (!conversationId) return "";
    if (verifyExists && !(await this._conversationExists(conversationId))) return "";
    try {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        const r = await authFetch(`/api/messages/${conversationId}?_=${Date.now()}`);
        if (!r.ok) return "";
        const msgs = await r.json();
        if (!Array.isArray(msgs)) return "";
        const assistants = msgs
          .filter(m => !m.isCreatedByUser)
          .sort((a, b) => new Date(a.createdAt || 0) - new Date(b.createdAt || 0));
        const byParent = parentMessageId
          ? assistants.find(m => m.parentMessageId === parentMessageId)
          : null;
        const byTime = createdAfter
          ? assistants.filter(m => new Date(m.createdAt || 0).getTime() >= createdAfter).at(-1)
          : null;
        const target = byParent || byTime || (!parentMessageId ? assistants.at(-1) : null);
        const freshEnough = !createdAfter || new Date(target?.createdAt || 0).getTime() >= createdAfter;
        const text = freshEnough ? this._messageText(target) : "";
        if (text) {
          this.currentConvoId = conversationId;
          await this.renderMarkdown(assistantBodyEl, text);
          return text;
        }
        await new Promise(resolve => setTimeout(resolve, 250));
      }
      return "";
    } catch (e) {
      console.warn("[chat] hydrate latest assistant failed", e);
      return "";
    }
  },

  async _hydrateRecentAssistant(assistantBodyEl, options = {}) {
    const { parentMessageId, createdAfter, promptText } = options;
    try {
      for (let attempt = 0; attempt < 10; attempt += 1) {
        const r = await authFetch(`/api/convos?pageSize=8&_=${Date.now()}`);
        if (!r.ok) return "";
        const payload = await r.json();
        const convos = Array.isArray(payload) ? payload : (payload.conversations || payload.data || []);
        const recent = convos
          .map(c => ({
            ...c,
            id: c.conversationId || c._id || c.id,
            ts: new Date(c.updatedAt || c.createdAt || 0).getTime(),
          }))
          .filter(c => c.id)
          .sort((a, b) => b.ts - a.ts)
          .slice(0, 5);

        for (const convo of recent) {
          const text = await this._hydrateLatestAssistant(assistantBodyEl, {
            conversationId: convo.id,
            parentMessageId,
            createdAfter,
          });
          if (text) return text;

          // LibreChat 某些回傳不保留 parentMessageId 給前端,改用本次 prompt 對齊最近回覆。
          const mr = await authFetch(`/api/messages/${convo.id}?_=${Date.now()}`);
          if (!mr.ok) continue;
          const msgs = await mr.json();
          if (!Array.isArray(msgs)) continue;
          const userMsg = msgs.find(m =>
            m.isCreatedByUser &&
            (!promptText || m.text === promptText) &&
            (!createdAfter || new Date(m.createdAt || 0).getTime() >= createdAfter)
          );
          if (!userMsg) continue;
          const assistant = msgs
            .filter(m =>
              !m.isCreatedByUser &&
              (!createdAfter || new Date(m.createdAt || 0).getTime() >= createdAfter)
            )
            .at(-1);
          const fallbackText = this._messageText(assistant);
          if (fallbackText) {
            this.currentConvoId = convo.id;
            await this.renderMarkdown(assistantBodyEl, fallbackText);
            return fallbackText;
          }
        }

        await new Promise(resolve => setTimeout(resolve, 250));
      }
      return "";
    } catch (e) {
      console.warn("[chat] hydrate recent assistant failed", e);
      return "";
    }
  },

  appendMessage(role, content, streaming = false) {
    const container = this._$("chat-messages");
    if (!container) return document.createElement("div");
    const el = document.createElement("div");
    el.className = `chat-msg ${role}`;
    const emoji = role === "user"
      ? "👤"
      : (CORE_AGENTS.find(a => a.num === this.currentAgentNum)?.emoji || "🤖");
    // v1.57 a11y · streaming 期間 body 設 aria-live=off · 防 SR 每 token 重念整段
    // 完成時(_finishStream)切回 polite + announce「回覆完成 · 共 N 字」
    const ariaLive = streaming ? "off" : "polite";
    el.innerHTML = `
      <div class="chat-msg-avatar" aria-hidden="true">${emoji}</div>
      <div class="chat-msg-body ${streaming ? "chat-msg-streaming" : ""}" aria-live="${ariaLive}"></div>
    `;
    const body = el.querySelector(".chat-msg-body");
    if (role === "user") body.textContent = content;
    else this.renderMarkdown(body, content);
    container.appendChild(el);
    this._scrollMessages();
    if (role === "assistant" && !streaming) this._attachFeedback(el);
    return body;
  },

  // v1.57 a11y · streaming 結束後切 aria-live + 在 SR-only region announce 一次
  _finishStream(bodyEl) {
    if (!bodyEl) return;
    bodyEl.classList.remove("chat-msg-streaming");
    bodyEl.setAttribute("aria-live", "polite");
    // 在隱藏 region 喊「回覆完成」一次 · 不重念整段
    let live = document.getElementById("chat-sr-announcer");
    if (!live) {
      live = document.createElement("div");
      live.id = "chat-sr-announcer";
      live.setAttribute("role", "status");
      live.setAttribute("aria-live", "polite");
      live.setAttribute("aria-atomic", "true");
      live.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap";
      document.body.appendChild(live);
    }
    const len = (bodyEl.textContent || "").length;
    live.textContent = `助理已回覆 · 共 ${len} 字`;
  },

  // v1.59 #4 · tool call 可見性 · SSE 偵測到 tool_call/function_call 時 inline 顯示
  // 例:「⚙ 主管家正在呼叫 PCC 查標案... 」· 同事看得到 AI 在做事 · 不再黑盒
  _toolCallSeen: new Set(),  // 同 call id 不重複加 chip
  _maybeShowToolCall(data, bodyEl) {
    if (!bodyEl) return;
    // LibreChat / OpenAI 多種事件型態 · 收斂在這
    const candidates = [
      data?.tool_call,
      data?.function_call,
      data?.delta?.tool_calls?.[0],
      data?.choices?.[0]?.delta?.tool_calls?.[0],
      data?.message?.tool_call,
    ].filter(Boolean);
    for (const tc of candidates) {
      const fn = tc.function?.name || tc.name || tc.tool_name;
      if (!fn) continue;
      const callId = tc.id || tc.call_id || `${fn}-${Date.now()}`;
      if (this._toolCallSeen.has(callId)) continue;
      this._toolCallSeen.add(callId);
      const chip = document.createElement("div");
      chip.className = "chat-tool-call-chip";
      chip.setAttribute("role", "status");
      chip.style.cssText = "display:inline-flex;align-items:center;gap:6px;padding:6px 10px;margin:6px 0;border-radius:999px;background:color-mix(in srgb, var(--accent) 12%, transparent);border:1px solid color-mix(in srgb, var(--accent) 28%, transparent);font-size:13px;color:var(--text-primary)";
      chip.innerHTML = `<span aria-hidden="true">⚙</span><span>正在呼叫 <strong>${this._friendlyToolName(fn)}</strong>...</span>`;
      bodyEl.appendChild(chip);
      this._scrollMessages();
    }
  },

  _friendlyToolName(fn) {
    const map = {
      searchByTitle: "PCC 標案查詢",
      listByUnit: "PCC 機關列表",
      listByDate: "PCC 近期標案",
      getTenderDetail: "PCC 標案詳情",
      generateImage: "OpenAI 生圖",
      editImage: "OpenAI 改圖",
      extractTenderSummary: "招標 9 欄抽取",
      extractTable: "表格抽取",
      extractScoringCriteria: "評分標準抽取",
      listAccounts: "會計科目查詢",
      createTransaction: "記一筆交易",
      listTransactions: "交易列表",
      delegateToAgent: "轉交專家",
    };
    return map[fn] || fn;
  },

  // v1.50 · RAF 節流 scroll · 串流時每 frame 只 scroll 一次 · 取代 token-rate forced layout
  _scrollScheduled: false,
  _scrollMessages() {
    if (this._scrollScheduled) return;
    this._scrollScheduled = true;
    requestAnimationFrame(() => {
      this._scrollScheduled = false;
      const msgs = this._$("chat-messages");
      if (msgs) msgs.scrollTop = msgs.scrollHeight;
    });
  },

  // v4.6 · 改用 marked.js(vendor 進 modules/vendor-marked.js · 無 build step)
  // 原 regex parser 對巢狀 list / code block / 中英混排 / PDF 條列 都會有 corner case
  // marked 是 GFM 標準實作 · ~28 KB · 比手刻 regex 多但每年省一堆 bug
  async renderMarkdown(el, text) {
    if (!this._marked) {
      // v1.50 · 第一次 import 時放 placeholder · 避免空白閃爍
      if (el && !el.textContent) el.textContent = "…";
      try {
        const m = await import("./vendor-marked.js");
        this._marked = m.marked;
        // Codex R4.3 · 關閉 raw HTML + 全 escape(防 AI 回傳惡意 <img onerror=...>)
        // marked 7+ 預設會保留 raw HTML · 必須明示 renderer.html=() => '' 擋
        this._marked.use({
          renderer: {
            // 來源 text 內的 <tag> 整段丟 · 不進 DOM
            html() { return ""; },
          },
        });
        this._marked.setOptions({ gfm: true, breaks: true });
      } catch (e) {
        console.warn("marked.js 載入失敗 · 降級到 regex parser", e);
        return this._renderMarkdownLegacy(el, text);
      }
    }
    try {
      const html = this._marked.parse(text || "");
      // Codex R4.3 · 二道防線 · DOMParser 掃過清 event handler 與 script
      el.innerHTML = _sanitizeRenderedHtml(html);
    } catch (e) {
      console.warn("markdown parse error", e);
      el.textContent = text;
    }
    this._scrollMessages();
  },

  _renderMarkdownLegacy(el, text) {
    let html = escapeHtml(text);
    html = html
      .replace(/```([^`]*?)```/gs, (_, code) => `<pre><code>${code.trim()}</code></pre>`)
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/__(.+?)__/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/^## (.+)$/gm, "<h2>$1</h2>")
      .replace(/^# (.+)$/gm, "<h1>$1</h1>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
      .replace(/\n\n+/g, "</p><p>")
      .replace(/\n/g, "<br>");
    el.innerHTML = `<p>${html}</p>`;
    this._scrollMessages();
  },

  _attachFeedback(msgEl) {
    const body = msgEl.querySelector(".chat-msg-body");
    const actions = document.createElement("div");
    actions.className = "chat-msg-actions";
    const directSave = this.pendingHandoffSave;
    if (directSave?.projectId) actions.classList.add("has-direct-save");
    const directSaveButton = directSave?.projectId
      ? `<button class="chat-msg-save primary" data-handoff-direct title="直接回寫到目前工作包">${escapeHtml(directSave.cta || "回寫到工作包")}</button>`
      : "";
    actions.innerHTML = `
      ${directSaveButton}
      <button class="chat-msg-fb" data-verdict="up" title="好回答">👍</button>
      <button class="chat-msg-fb" data-verdict="down" title="需要改進">👎</button>
      <button class="chat-msg-save" data-handoff-target="asset_ref" title="存到工作包交棒卡">存交棒</button>
      <button class="chat-msg-save" data-handoff-target="next_action" title="列成工作包下一步">列下一步</button>
    `;
    actions.querySelector("[data-handoff-direct]")?.addEventListener("click", () => {
      const text = this._messagePlainText(body);
      this.saveAnswerToHandoffDirect(text, directSave);
    });
    actions.querySelectorAll(".chat-msg-fb").forEach(btn => {
      btn.addEventListener("click", async () => {
        actions.querySelectorAll(".chat-msg-fb").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const verdict = btn.dataset.verdict;
        let note = "";
        if (verdict === "down") {
          const r = await modal.prompt(
            [{ name: "note", label: "哪裡不好?(可空白)", type: "textarea", rows: 2 }],
            { title: "幫我們改進", icon: "👎" }
          );
          if (r) note = r.note;
        }
        // R8#5 · 改 authFetch · 帶 cookie + X-User-Email · prod 嚴格 mode 才能成功
        await authFetch("/api-accounting/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message_id: crypto.randomUUID?.() || String(Date.now()),
            conversation_id: this.currentConvoId,
            agent_name: CORE_AGENTS.find(a => a.num === this.currentAgentNum)?.name,
            verdict,
            note,
            // R7#4 · server 只認 trusted_email · 這欄位送了也會被覆蓋
            user_email: this._userStore?.()?.email,
          }),
        });
        toast.success(verdict === "up" ? "感謝👍" : "感謝回饋 · 月底會列入優化分析");
      });
    });
    actions.querySelectorAll("[data-handoff-target]").forEach(btn => {
      btn.addEventListener("click", () => {
        const text = this._messagePlainText(body);
        this.saveAnswerToHandoff(text, btn.dataset.handoffTarget);
      });
    });
    body.appendChild(actions);
  },

  _messagePlainText(body) {
    const clone = body.cloneNode(true);
    clone.querySelectorAll(".chat-msg-actions").forEach(el => el.remove());
    return (clone.innerText || clone.textContent || "").trim();
  },

  _handoffTargetLabel(target) {
    if (target === "next_action") return "工作包下一步";
    if (target === "constraint") return "工作包限制";
    if (target === "goal") return "工作包目標";
    return "工作包交棒卡";
  },

  async saveAnswerToHandoffDirect(answerText, config = {}) {
    const text = (answerText || "").trim();
    if (!text) {
      toast.info("這則回答還沒有內容可回寫");
      return;
    }
    const projectId = config?.projectId;
    if (!projectId) {
      await this.saveAnswerToHandoff(text, config?.target || "asset_ref");
      return;
    }
    const target = config.target || "asset_ref";
    let r;
    try {
      r = await authFetch(`/api-accounting/projects/${projectId}/handoff/append`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target,
          text,
          label: config.label || "智慧助理回答摘要",
          source_conversation_id: this.currentConvoId,
        }),
      });
    } catch (e) {
      console.warn("[chat] direct handoff save failed", e);
      toast.error("回寫工作包失敗 · 請稍後再試");
      return;
    }
    if (!r.ok) {
      toast.error("回寫工作包失敗 · 請確認工作包權限");
      return;
    }
    await Projects.refresh();
    Projects._onChange?.();
    toast.success(`已回寫到${this._handoffTargetLabel(target)}`);
  },

  async saveAnswerToHandoff(answerText, defaultTarget = "asset_ref") {
    const text = (answerText || "").trim();
    if (!text) {
      toast.info("這則回答還沒有內容可保存");
      return;
    }
    let projects = Projects.load().filter(p => p.status !== "closed");
    if (!projects.length) {
      try {
        projects = (await Projects.refresh()).filter(p => p.status !== "closed");
      } catch {}
    }
    if (!projects.length) {
      toast.info("先建立一個工作包,回答才能存回交棒卡");
      return;
    }

    const modalId = "handoff_save_" + Math.random().toString(36).slice(2, 8);
    const options = projects.map(p => `
      <option value="${escapeHtml(p.id || p._id)}">${escapeHtml(p.name || "未命名工作包")}</option>
    `).join("");
    const bodyHTML = `
      <div class="handoff-save-form" id="${modalId}">
        <label>
          <span>存到哪個工作包</span>
          <select name="project_id">${options}</select>
        </label>
        <label>
          <span>存成什麼</span>
          <select name="target">
            <option value="asset_ref" ${defaultTarget === "asset_ref" ? "selected" : ""}>交棒素材 / 智慧助理回答摘要</option>
            <option value="next_action" ${defaultTarget === "next_action" ? "selected" : ""}>下一步待辦</option>
            <option value="constraint" ${defaultTarget === "constraint" ? "selected" : ""}>限制 / 注意事項</option>
            <option value="goal" ${defaultTarget === "goal" ? "selected" : ""}>補進目標</option>
          </select>
        </label>
        <label>
          <span>內容可先修一下再存</span>
          <textarea name="text" rows="7">${escapeHtml(text.slice(0, 4000))}</textarea>
        </label>
      </div>
    `;

    await modal.show({
      title: "存到工作包交棒卡",
      icon: "🤝",
      primary: "存入交棒卡",
      cancel: "取消",
      bodyHTML,
      onSubmit: async () => {
        const root = document.getElementById(modalId);
        const projectId = root?.querySelector('[name="project_id"]')?.value;
        const target = root?.querySelector('[name="target"]')?.value || defaultTarget;
        const value = (root?.querySelector('[name="text"]')?.value || "").trim();
        if (!projectId || !value) {
          toast.error("請選工作包並保留要存的內容");
          return false;
        }
        let r;
        try {
          r = await authFetch(`/api-accounting/projects/${projectId}/handoff/append`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              target,
              text: value,
              label: "智慧助理回答摘要",
              source_conversation_id: this.currentConvoId,
            }),
          });
        } catch (e) {
          console.warn("[chat] save handoff failed", e);
          toast.error("存入交棒卡失敗 · 請稍後再試");
          return false;
        }
        if (!r.ok) {
          toast.error("存入交棒卡失敗 · 請確認工作包權限");
          return false;
        }
        await Projects.refresh();
        Projects._onChange?.();
        toast.success(target === "next_action" ? "已列入工作包下一步" : "已存到工作包交棒卡");
        return true;
      },
    });
  },

  // v1.50 · 重構 · 不再 root.innerHTML 兩次 + setTimeout(50) 重綁
  // 改用 document-level event delegation · 自動 cleanup
  async history() {
    try {
      const r = await authFetch("/api/convos?pageSize=20");
      const data = await r.json();
      const convos = data.conversations || data.data || data;
      if (!Array.isArray(convos) || convos.length === 0) { toast.info("尚無歷史對話"); return; }
      const items = convos.slice(0, 10).map(c => {
        const id = c.conversationId || c._id;
        const title = c.title || "未命名";
        return `<li class="chat-history-item" data-convo-id="${escapeHtml(id)}"
                  style="padding:10px 12px;border-bottom:1px solid var(--border);cursor:pointer;border-radius:6px;transition:background 0.1s"
                  onmouseover="this.style.background='var(--bg-base)'"
                  onmouseout="this.style.background='transparent'">${escapeHtml(title)}</li>`;
      }).join("");
      const bodyHTML = `<ul class="chat-history-list" style="list-style:none;padding:0;margin:0;max-height:60vh;overflow-y:auto">${items}</ul>`;

      // 1) document-level delegation · 點 li 觸發 loadConvo + 模擬點關閉鈕
      let chosen = null;
      const onClick = (e) => {
        const li = e.target.closest(".chat-history-item");
        if (!li) return;
        chosen = li.dataset.convoId;
        // 找關閉 button(modal.show 的 cancel)觸發
        const closeBtn = document.querySelector(".modal2-box .btn-ghost");
        if (closeBtn) closeBtn.click();
      };
      document.addEventListener("click", onClick);

      await modal.show({
        title: "歷史對話 · 點一筆開啟",
        icon: "🕒",
        bodyHTML,
        cancel: "關閉",
        primary: "完成",
      });
      document.removeEventListener("click", onClick);
      if (chosen) await this.loadConvo(chosen);
    } catch {
      toast.error("無法載入歷史對話");
    }
  },

  async loadConvo(convoId) {
    if (!convoId) return;
    this.currentConvoId = convoId;
    try {
      const r = await authFetch(`/api/messages/${convoId}?_=${Date.now()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const msgs = await r.json();
      const container = this._$("chat-messages");
      if (!container) return;

      // 確保 chat pane 是開的(從 URL 直接進來時 · pane 可能沒開)
      this._$("chat-pane")?.classList.add("open");
      document.body.classList.add("chat-open");

      container.innerHTML = "";  // 清 welcome + 舊訊息
      if (!Array.isArray(msgs) || msgs.length === 0) {
        container.innerHTML = `
          <div class="chat-welcome">
            <div class="chat-welcome-emoji">💭</div>
            <div class="chat-welcome-title">對話無訊息</div>
            <div class="chat-welcome-sub">這串對話還沒內容 · 輸入問題開始吧</div>
          </div>`;
        return;
      }
      // 依時間序 append
      msgs.sort((a, b) => new Date(a.createdAt || 0) - new Date(b.createdAt || 0));
      for (const m of msgs) {
        this.appendMessage(m.isCreatedByUser ? "user" : "assistant", this._messageText(m));
      }
      toast.success(`已載入對話 · ${msgs.length} 則訊息`);
    } catch (e) {
      console.warn("載入對話失敗", e);
      toast.error("載入對話失敗 · 可能對話已被刪除");
    }
  },

  bindFileInput() {
    const fi = this._$("chat-file-input");
    if (!fi) return;
    fi.addEventListener("change", async (e) => {
      this.addFiles(Array.from(e.target.files || []));
      fi.value = "";
    });

    const form = this._$("chat-form");
    if (!form || form.dataset.fileDropBound === "true") return;
    form.dataset.fileDropBound = "true";
    form.addEventListener("dragover", (e) => {
      if (!e.dataTransfer?.types?.includes("Files")) return;
      e.preventDefault();
      form.classList.add("drag-over");
    });
    form.addEventListener("dragleave", (e) => {
      if (!form.contains(e.relatedTarget)) form.classList.remove("drag-over");
    });
    form.addEventListener("drop", (e) => {
      if (!e.dataTransfer?.files?.length) return;
      e.preventDefault();
      form.classList.remove("drag-over");
      this.addFiles(Array.from(e.dataTransfer.files));
    });
  },

  addFiles(files = []) {
    const accepted = [];
    for (const file of files) {
      const validation = _validateAttachmentFn(file);
      if (!validation.ok) {
        toast.warn(validation.message);
        continue;
      }
      const duplicate = this.attachments.some(item => _isSameFile(item.file, file));
      if (duplicate) continue;
      if (this.attachments.length + accepted.length >= MAX_ATTACHMENT_COUNT) {
        toast.warn(`一次最多附 ${MAX_ATTACHMENT_COUNT} 個檔案`);
        break;
      }
      accepted.push({
        id: crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`,
        file,
        status: "ready",
        uploaded: null,
      });
    }
    if (!accepted.length) return;
    this.attachments = [...this.attachments, ...accepted];
    this.renderAttachments();
    toast.success(`已加入 ${accepted.length} 個附件 · 送出時會一併讀取`);
  },

  // v1.50 · _validateAttachment 移至 chat-attachments.js · 純函數

  renderAttachments() {
    const attEl = this._$("chat-attachments");
    if (!attEl) return;
    attEl.innerHTML = "";
    for (const item of this.attachments) {
      const chip = document.createElement("div");
      chip.className = `chat-attachment-chip ${item.status}`;
      const status = item.status === "uploading" ? "上傳中" : item.status === "error" ? "失敗" : "待送出";
      chip.innerHTML = `
        <span class="chat-attachment-name">📎 ${escapeHtml(item.file.name)}</span>
        <span class="chat-attachment-status">${status}</span>
        <button type="button" aria-label="移除 ${escapeHtml(item.file.name)}">✕</button>
      `;
      chip.querySelector("button")?.addEventListener("click", () => {
        this.attachments = this.attachments.filter(att => att.id !== item.id);
        this.renderAttachments();
      });
      attEl.appendChild(chip);
    }
  },

  async _uploadPendingAttachments() {
    if (!this.attachments.length) return [];
    const uploaded = [];
    for (const item of this.attachments) {
      if (item.uploaded) {
        uploaded.push(item.uploaded);
        continue;
      }
      item.status = "uploading";
      this.renderAttachments();
      try {
        item.uploaded = await this._uploadAttachment(item.file);
        item.status = "uploaded";
        uploaded.push(item.uploaded);
      } catch (err) {
        item.status = "error";
        this.renderAttachments();
        throw new Error(`${item.file.name} 上傳失敗:${err.message || "請稍後重試"}`);
      }
    }
    this.attachments = [];
    this.renderAttachments();
    return uploaded;
  },

  async _uploadAttachment(file) {
    const fileId = crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`;
    const form = new FormData();
    form.append("endpoint", "agents");
    form.append("endpointType", "agents");
    form.append("message_file", "true");
    form.append("file_id", fileId);
    form.append("file", file, encodeURIComponent(file.name));
    const resp = await authFetch("/api/files", { method: "POST", body: form });
    if (!resp.ok) {
      const errText = await resp.text().catch(() => "");
      throw new Error(`HTTP ${resp.status} ${errText.slice(0, 120)}`);
    }
    const data = await resp.json();
    return {
      ...data,
      file_id: data.file_id || data.id || data._id || fileId,
      filename: data.filename || file.name,
      type: data.type || file.type || "application/octet-stream",
      bytes: data.bytes || file.size,
    };
  },

  // v1.50 · _composeUserMessageSummary 移至 chat-attachments.js
  _composeUserMessageSummary: _composeSummaryFn,
};

// v1.50 · sanitizeRenderedHtml 抽至 chat-sanitize.js(純函數 · 易測)

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

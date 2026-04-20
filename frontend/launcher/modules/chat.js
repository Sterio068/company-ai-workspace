/**
 * Chat Pane · Launcher 內建對話介面(路線 A · 不跳 LibreChat 頁)
 * 呼叫 /api/ask/agents · SSE 串流
 */
import { escapeHtml } from "./util.js";
import { modal } from "./modal.js";
import { toast } from "./toast.js";
import { authFetch, SessionExpiredError } from "./auth.js";
import { CORE_AGENTS } from "./config.js";

export const chat = {
  currentAgentNum: null,
  currentAgentId:  null,
  currentConvoId:  null,
  isStreaming:     false,
  attachments:     [],
  _agentsStore:    null,   // app 注入,用來查 agent.id
  _userStore:      null,   // app 注入,用來帶 email 給 feedback

  bind({ agents, user }) {
    this._agentsStore = agents;
    this._userStore = user;
  },

  _findAgentByNum(num) {
    const list = this._agentsStore?.() || [];
    const meta = CORE_AGENTS.find(a => a.num === num);
    if (!meta) return null;
    return list.find(a =>
      (a.metadata && a.metadata.number === num) ||
      (a.name || "").includes(meta.name)
    );
  },

  async open(agentNum, initialInput) {
    const agent = this._findAgentByNum(agentNum);
    if (!agent) {
      const meta = CORE_AGENTS.find(a => a.num === agentNum);
      const nice = meta ? `${meta.emoji} ${meta.name}` : `#${agentNum}`;
      // 一般同仁友善版
      const isAdmin = document.documentElement.dataset.role === "admin";
      const adminHint = isAdmin
        ? `<div style="margin-top:12px;padding:10px;background:var(--bg-base);border-radius:6px;font-size:12px;color:var(--text-secondary);font-family:var(--font-mono)">
             管理員補充:執行 <code>python3 scripts/create-agents.py --tier core</code> 建立助手
           </div>`
        : "";
      modal.alert(
        `系統還沒準備好「${escapeHtml(nice)}」這位助手,請聯絡管理員協助。${adminHint}`,
        { title: "助手尚未就緒", icon: "🤖", primary: "知道了" }
      );
      return;
    }
    this.currentAgentNum = agentNum;
    this.currentAgentId  = agent.id || agent._id;
    this.currentConvoId  = null;
    this.attachments     = [];

    const meta = CORE_AGENTS.find(a => a.num === agentNum) || {};
    setText("chat-agent-emoji", meta.emoji || "🤖");
    setText("chat-agent-name",  meta.name  || agent.name || "Agent");
    setText("chat-agent-sub",   `${meta.model || "Sonnet"} · ${meta.desc || ""}`);

    const msgs = document.getElementById("chat-messages");
    if (msgs) {
      msgs.innerHTML = `
        <div class="chat-welcome">
          <div class="chat-welcome-emoji">${meta.emoji || "🤖"}</div>
          <div class="chat-welcome-title">${escapeHtml(meta.name || "Agent")}</div>
          <div class="chat-welcome-sub">${escapeHtml(meta.desc || "隨時為你服務")}</div>
        </div>
      `;
    }
    document.getElementById("chat-pane")?.classList.add("open");
    document.body.classList.add("chat-open");
    document.getElementById("chat-input")?.focus();

    if (initialInput) {
      const input = document.getElementById("chat-input");
      if (input) {
        input.value = initialInput;
        setTimeout(() => this.send(), 100);
      }
    }
  },

  close() {
    document.getElementById("chat-pane")?.classList.remove("open");
    document.body.classList.remove("chat-open");
  },

  newConversation() {
    this.currentConvoId = null;
    this.attachments = [];
    const attEl = document.getElementById("chat-attachments");
    if (attEl) attEl.innerHTML = "";
    const msgs = document.getElementById("chat-messages");
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
      ta.style.height = "auto";
      ta.style.height = Math.min(200, ta.scrollHeight) + "px";
    }, 0);
  },

  // 輸入時 debounce 去問 backend L3 classifier · 更新等級提示 badge
  _classifyTimer: null,
  onInput(e) {
    const text = (e?.target?.value || "").trim();
    const badge = document.getElementById("chat-level-hint");
    if (!badge) return;
    if (text.length < 20) {
      badge.className = "hint-level l1";
      badge.textContent = "L1 公開";
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
          badge.textContent = "⚠ L3 機敏";
          badge.title = "偵測到機敏內容 · 送出前會再次確認。建議不要上雲。";
        } else if (level === "02") {
          badge.className = "hint-level l2";
          badge.textContent = "L2 一般";
          badge.title = "一般機密 · 建議去識別化後再送";
        } else {
          badge.className = "hint-level l1";
          badge.textContent = "L1 公開";
          badge.title = "公開資訊 · 可安全上雲";
        }
      } catch { /* backend 離線 · 不改 */ }
    }, 450);
  },

  pickFile() {
    // v1.0 先關閉 · 避免假成功
    toast.info("v1.1 開放檔案上傳 · 現在請把檔案內容複製貼上");
  },

  async send(e) {
    if (e) e.preventDefault();
    if (this.isStreaming) return;
    const input = document.getElementById("chat-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    document.querySelector("#chat-messages .chat-welcome")?.remove();
    this.appendMessage("user", text);
    input.value = "";
    input.style.height = "auto";

    const assistantBody = this.appendMessage("assistant", "", true);
    this.isStreaming = true;
    const sendBtn = document.getElementById("chat-send-btn");
    if (sendBtn) sendBtn.disabled = true;

    try {
      await this._stream(text, assistantBody);
    } catch (err) {
      // Session 過期:banner 已由 authFetch 顯示 · 訊息框靜默移除佔位,避免紅字誤導
      if (err instanceof SessionExpiredError) {
        assistantBody.closest(".chat-msg")?.remove();
      } else {
        assistantBody.innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(err.message || "送出失敗")}</span>`;
      }
    } finally {
      this.isStreaming = false;
      if (sendBtn) sendBtn.disabled = false;
      assistantBody.classList.remove("chat-msg-streaming");
    }
  },

  async _stream(text, assistantBodyEl) {
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
    const resp = await authFetch("/api/ask/agents", {
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
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";  // 保護:若 chunk 剛好以 \n\n 結尾,pop() 會是 undefined
      for (const evt of events) {
        const dataLines = evt.split("\n").filter(l => l.startsWith("data: ")).map(l => l.substring(6));
        for (const line of dataLines) {
          if (line === "[DONE]") continue;
          try {
            const data = JSON.parse(line);
            if (data.text !== undefined) accumulated = data.text;
            else if (data.message?.text) accumulated = data.message.text;
            else if (data.delta?.content) accumulated += data.delta.content;
            if (data.conversationId || data.conversation?.conversationId) {
              this.currentConvoId = data.conversationId || data.conversation.conversationId;
            }
            if (accumulated) this.renderMarkdown(assistantBodyEl, accumulated);
          } catch { /* skip non-json */ }
        }
      }
    }
  },

  appendMessage(role, content, streaming = false) {
    const container = document.getElementById("chat-messages");
    if (!container) return document.createElement("div");
    const el = document.createElement("div");
    el.className = `chat-msg ${role}`;
    const emoji = role === "user"
      ? "👤"
      : (CORE_AGENTS.find(a => a.num === this.currentAgentNum)?.emoji || "🤖");
    el.innerHTML = `
      <div class="chat-msg-avatar">${emoji}</div>
      <div class="chat-msg-body ${streaming ? "chat-msg-streaming" : ""}"></div>
    `;
    const body = el.querySelector(".chat-msg-body");
    if (role === "user") body.textContent = content;
    else this.renderMarkdown(body, content);
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
    if (role === "assistant" && !streaming) this._attachFeedback(el);
    return body;
  },

  renderMarkdown(el, text) {
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
    // `#chat-messages` 是 id 不是 class · 原 `.chat-messages` 選不到 · 修正
    const msgs = document.getElementById("chat-messages");
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
  },

  _attachFeedback(msgEl) {
    const body = msgEl.querySelector(".chat-msg-body");
    const actions = document.createElement("div");
    actions.className = "chat-msg-actions";
    actions.innerHTML = `
      <button class="chat-msg-fb" data-verdict="up" title="好回答">👍</button>
      <button class="chat-msg-fb" data-verdict="down" title="需要改進">👎</button>
    `;
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
        await fetch("/api-accounting/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message_id: crypto.randomUUID?.() || String(Date.now()),
            conversation_id: this.currentConvoId,
            agent_name: CORE_AGENTS.find(a => a.num === this.currentAgentNum)?.name,
            verdict,
            note,
            user_email: this._userStore?.()?.email,
          }),
        });
        toast.success(verdict === "up" ? "感謝👍" : "感謝回饋 · 月底會列入優化分析");
      });
    });
    body.appendChild(actions);
  },

  async history() {
    try {
      const r = await fetch("/api/convos?pageSize=20", { credentials: "include" });
      const data = await r.json();
      const convos = data.conversations || data.data || data;
      if (!Array.isArray(convos) || convos.length === 0) { toast.info("尚無歷史對話"); return; }
      const list = convos.slice(0, 10).map(c =>
        `<li style="padding:6px 0;border-bottom:1px solid var(--border);cursor:pointer"
             data-convo-id="${escapeHtml(c.conversationId || c._id)}">${escapeHtml(c.title || "未命名")}</li>`
      ).join("");
      await modal.alert(`<ul style="list-style:none;padding:0" id="chat-history-list">${list}</ul>`,
        { title: "歷史對話", icon: "🕒" });
      // after modal closed, the delegated listener is lost, but user clicked inside modal triggered close
      // simpler:在 modal 開著時直接綁(修為用事件委派)
    } catch {
      toast.error("無法載入歷史對話");
    }
  },

  async loadConvo(convoId) {
    this.currentConvoId = convoId;
    try {
      const r = await fetch(`/api/messages/${convoId}`, { credentials: "include" });
      const msgs = await r.json();
      const container = document.getElementById("chat-messages");
      if (!container) return;
      container.innerHTML = "";
      for (const m of (msgs || [])) {
        this.appendMessage(m.isCreatedByUser ? "user" : "assistant", m.text || "");
      }
    } catch {
      toast.error("載入對話失敗");
    }
  },

  bindFileInput() {
    const fi = document.getElementById("chat-file-input");
    if (!fi) return;
    fi.addEventListener("change", async (e) => {
      const attEl = document.getElementById("chat-attachments");
      if (!attEl) return;
      for (const f of e.target.files) {
        this.attachments.push(f);
        const chip = document.createElement("div");
        chip.className = "chat-attachment-chip";
        chip.innerHTML = `📎 ${escapeHtml(f.name)} <button type="button" aria-label="移除">✕</button>`;
        chip.querySelector("button").addEventListener("click", () => chip.remove());
        attEl.appendChild(chip);
      }
      toast.success(`已選 ${e.target.files.length} 個檔案 · 送訊息時會一併送出`);
      fi.value = "";
    });
  },
};

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

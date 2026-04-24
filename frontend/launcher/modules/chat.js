/**
 * Chat Pane · Launcher 內建對話介面(路線 A · 不跳 LibreChat 頁)
 * 呼叫 /api/agents/chat · SSE 串流
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
    this._bindSuggestions();
  },

  // v1.3 P1#15 · 空對話建議 prompt · AI 小白起步友善
  _bindSuggestions() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".chat-suggestion");
      if (!btn) return;
      const prompt = btn.dataset.prompt;
      if (!prompt) return;
      const input = document.getElementById("chat-input");
      if (!input) return;
      input.value = prompt;
      input.dispatchEvent(new Event("input"));  // 觸發 L1/L2/L3 classifier
      // 自動送?先填入讓用戶看 · 按 Enter 再送
      input.focus();
    });
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

  async send(e, _piiRedacted = false) {
    if (e) e.preventDefault();
    if (this.isStreaming) return;
    const input = document.getElementById("chat-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    // v1.3 batch5 · L3 機敏 · 送雲前再次確認(分類 badge 已 pulse · 但要實心擋)
    const levelBadge = document.getElementById("chat-level-hint");
    if (levelBadge?.classList.contains("l3")) {
      const ok = await modal.confirm(
        `⚠️ 偵測到「L3 機敏」內容<br><br>
         此內容可能含選情 / 客戶機敏 / 未公告標案內情。<br>
         <strong>送出後會傳到雲端 Claude API。</strong><br><br>
         是否繼續?`,
        { title: "機敏內容確認", icon: "🔒", primary: "我知道,送出", cancel: "回去修改", danger: true }
      );
      if (!ok) return;

      // v1.3 A3 · CRITICAL C-3 · server-side L3 audit + (可選)硬擋
      // 即使 user 同意 · 仍打 backend 留可追責 audit log
      try {
        const lr = await authFetch("/api-accounting/safety/l3-preflight", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (lr.status === 403) {
          const err = await lr.json().catch(() => ({}));
          toast.error("L3 機敏禁止送雲", {
            detail: err.detail?.message || "公司政策禁止 · 請改人工或本地處理",
          });
          return;
        }
        // 200 · 已 audit · 繼續送
      } catch (e) {
        // server preflight 掛 · 保守擋(類似 quota fail-closed)
        toast.error("L3 audit 服務無回應 · 為合規暫停送出", {
          detail: "請找 Champion 或稍後重試",
        });
        return;
      }
    }

    // v1.2 Feature #3 · PII 偵測 · 送前掃一次身分證/電話/email/信用卡
    // v1.3 batch6 · CRITICAL · _piiRedacted flag 防遞迴炸彈
    // 原本 redacted 後 return this.send(e) · 若後端對 ★★★★ 仍回 PII 就無限循環
    if (!_piiRedacted) try {
      const piiR = await authFetch("/api-accounting/safety/pii-detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (piiR.ok) {
        const pii = await piiR.json();
        if (pii.total > 0) {
          const kinds = pii.hits.map(h => h.label).filter((v, i, a) => a.indexOf(v) === i);
          // v1.3 batch5 · 用 modal.confirm 取代 window.confirm · 更友善
          const ok = await modal.confirm(
            `偵測到 <strong>${pii.total} 個 PII</strong>:${escapeHtml(kinds.join("、"))}<br><br>
             按「用打碼版送」會把身分證 / 電話等敏感資料先打 ★ 再送雲端。<br>
             <small style="color:var(--text-secondary)">建議:打碼版能達成大多數任務 · 不需原始資料時優先選</small>`,
            { title: "PII 偵測", icon: "🛡️", primary: "用打碼版送", cancel: "回去修改" }
          );
          if (!ok) return;
          // 寫 audit + 用 redacted text 送
          try {
            await authFetch("/api-accounting/safety/pii-audit", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ text }),
            });
          } catch {}
          input.value = pii.redacted;
          // 重新讀取打碼後的 text 繼續送 · 帶 _piiRedacted=true 防無限遞迴
          return this.send(e, true);
        }
      }
    } catch (e) {
      // PII 偵測壞 · 不擋(best-effort)
    }

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
          toast.error(`❌ ${q.reason || "本月用量已達上限 · 請找 Champion 放行"}`);
          return;
        }
        if (q.warning) {
          toast.warn(q.warning);
        }
      } else {
        // HTTP 500/503 · 後端明確告訴我們擋 · 就擋
        // (後端 hard_stop 模式會回 allowed=false + 200 · 走上面路徑;
        //  這裡只剩 endpoint 本身掛掉的情況)
        toast.error("⚠ 預算服務暫時無回應 · 為安全先暫停送出 · 請找 Champion 或稍後重試");
        return;
      }
    } catch (e) {
      // 網路錯(fetch 直接 throw)· 保守擋 · 老闆 Q1 選 C
      toast.error("⚠ 預算服務連不上 · 為安全暫停送出 · 請找 Champion");
      return;
    }

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

  // v4.6 · 改用 marked.js(vendor 進 modules/vendor-marked.js · 無 build step)
  // 原 regex parser 對巢狀 list / code block / 中英混排 / PDF 條列 都會有 corner case
  // marked 是 GFM 標準實作 · ~28 KB · 比手刻 regex 多但每年省一堆 bug
  async renderMarkdown(el, text) {
    if (!this._marked) {
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
    const msgs = document.getElementById("chat-messages");
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
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
    body.appendChild(actions);
  },

  async history() {
    try {
      const r = await authFetch("/api/convos?pageSize=20");
      const data = await r.json();
      const convos = data.conversations || data.data || data;
      if (!Array.isArray(convos) || convos.length === 0) { toast.info("尚無歷史對話"); return; }
      // 打開 modal 後 · 用 event delegation 在 modal body 點 li 時 · close modal 並 loadConvo
      const list = convos.slice(0, 10).map(c =>
        `<li style="padding:8px 10px;border-bottom:1px solid var(--border);cursor:pointer;border-radius:6px"
             data-convo-id="${escapeHtml(c.conversationId || c._id)}"
             onmouseover="this.style.background='var(--bg-base)'"
             onmouseout="this.style.background='transparent'">${escapeHtml(c.title || "未命名")}</li>`
      ).join("");
      // Use DOM content listener instead of alert
      const root = document.createElement("div");
      root.innerHTML = `<ul style="list-style:none;padding:0;margin:0" id="chat-history-list">${list}</ul>`;
      root.addEventListener("click", async (e) => {
        const li = e.target.closest("[data-convo-id]");
        if (!li) return;
        const cid = li.dataset.convoId;
        // 關閉 modal
        document.querySelectorAll(".modal2-backdrop.open, .modal2-box.open").forEach(el => el.classList.remove("open"));
        setTimeout(() => {
          document.querySelectorAll(".modal2-backdrop, .modal2-box").forEach(el => el.remove());
        }, 200);
        await this.loadConvo(cid);
      });
      modal.alert(root.innerHTML, { title: "歷史對話 · 點一筆開啟", icon: "🕒", primary: "關閉" });
      // alert 的 body 被 re-innerHTML · 重新綁
      setTimeout(() => {
        document.querySelectorAll(".modal2-body [data-convo-id]").forEach(li => {
          li.addEventListener("click", async () => {
            const cid = li.dataset.convoId;
            document.querySelectorAll(".modal2-backdrop.open, .modal2-box.open").forEach(el => el.classList.remove("open"));
            setTimeout(() => document.querySelectorAll(".modal2-backdrop, .modal2-box").forEach(el => el.remove()), 200);
            await this.loadConvo(cid);
          });
        });
      }, 50);
    } catch {
      toast.error("無法載入歷史對話");
    }
  },

  async loadConvo(convoId) {
    if (!convoId) return;
    this.currentConvoId = convoId;
    try {
      const r = await authFetch(`/api/messages/${convoId}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const msgs = await r.json();
      const container = document.getElementById("chat-messages");
      if (!container) return;

      // 確保 chat pane 是開的(從 URL 直接進來時 · pane 可能沒開)
      document.getElementById("chat-pane")?.classList.add("open");
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
        this.appendMessage(m.isCreatedByUser ? "user" : "assistant", m.text || "");
      }
      toast.success(`已載入對話 · ${msgs.length} 則訊息`);
    } catch (e) {
      console.warn("載入對話失敗", e);
      toast.error("載入對話失敗 · 可能對話已被刪除");
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

// Codex R4.3 · 第二道 XSS 防線 · 用 DOMParser 白名單過濾
// 即使 marked renderer.html 已擋 block-level raw HTML · inline event handler 仍可能從其他路徑進來
// 白名單 tag + 禁 on* 屬性 + 禁 script/iframe/object/embed
const _ALLOWED_TAGS = new Set([
  "p", "br", "hr", "strong", "em", "code", "pre", "blockquote",
  "ul", "ol", "li", "a", "img",
  "h1", "h2", "h3", "h4", "h5", "h6",
  "table", "thead", "tbody", "tr", "th", "td",
  "span", "div",
  "del", "ins", "sub", "sup",
]);
const _ALLOWED_ATTRS = new Set(["href", "src", "alt", "title", "colspan", "rowspan", "class"]);

function _sanitizeRenderedHtml(html) {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<body>${html}</body>`, "text/html");
    _cleanNode(doc.body);
    return doc.body.innerHTML;
  } catch {
    // DOMParser 壞的話 · fallback 回 text(safer)
    return html.replace(/<[^>]*>/g, "");
  }
}

function _cleanNode(node) {
  // 先複製 childNodes 再遍歷(避免變動時迭代錯)
  const children = Array.from(node.childNodes);
  for (const child of children) {
    if (child.nodeType === 3) continue;  // text node · keep
    if (child.nodeType !== 1) { child.remove(); continue; }  // 只留 Element 與 Text

    const tag = child.tagName.toLowerCase();
    if (!_ALLOWED_TAGS.has(tag)) {
      // 不在白名單 · 但保留內文
      const frag = document.createDocumentFragment();
      while (child.firstChild) frag.appendChild(child.firstChild);
      child.replaceWith(frag);
      continue;
    }
    // 清 attributes · 只留白名單
    for (const attr of Array.from(child.attributes)) {
      const name = attr.name.toLowerCase();
      if (name.startsWith("on")) {
        child.removeAttribute(attr.name);  // onclick / onerror / onload
        continue;
      }
      if (!_ALLOWED_ATTRS.has(name)) {
        child.removeAttribute(attr.name);
        continue;
      }
      // href/src 禁 javascript: / data: (除了 image)
      if ((name === "href" || name === "src")) {
        const val = attr.value.trim().toLowerCase();
        if (val.startsWith("javascript:") || val.startsWith("vbscript:")) {
          child.removeAttribute(attr.name);
          continue;
        }
        if (name === "src" && val.startsWith("data:") && !val.startsWith("data:image/")) {
          child.removeAttribute(attr.name);
          continue;
        }
      }
    }
    // 遞歸
    _cleanNode(child);
  }
}


function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

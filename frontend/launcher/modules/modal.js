/**
 * Modal v2 · 取代 window.alert / confirm / prompt 的 async 版本
 *
 * 用法:
 *   await modal.alert("訊息")
 *   if (await modal.confirm("確定?")) { ... }
 *   const r = await modal.prompt([{name:"title", label:"標題", required:true}])
 */
import { escapeHtml } from "./util.js";

function ensureRoot() {
  let c = document.getElementById("modal-stack-root");
  if (!c) { c = document.createElement("div"); c.id = "modal-stack-root"; document.body.appendChild(c); }
  return c;
}

function show({ title, body, icon, buttons, autofocus }) {
  const root = ensureRoot();
  // v1.3 batch3 · 記住觸發 modal 的元素 · 關閉時 focus restore
  const previouslyFocused = document.activeElement;

  const backdrop = document.createElement("div");
  backdrop.className = "modal2-backdrop";
  const box = document.createElement("div");
  box.className = "modal2-box";
  // v1.3 batch3 · WCAG 2.1 dialog role + aria-modal + labelled by title
  const titleId = "modal2-title-" + Math.random().toString(36).slice(2, 8);
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-labelledby", titleId);
  box.tabIndex = -1;
  box.innerHTML = `
    <div class="modal2-head">
      <span class="modal2-icon" aria-hidden="true">${icon || ""}</span>
      <h3 class="modal2-title" id="${titleId}">${escapeHtml(title)}</h3>
    </div>
    <div class="modal2-body">${body}</div>
    <div class="modal2-actions"></div>
  `;
  const actions = box.querySelector(".modal2-actions");
  buttons.forEach(btn => {
    const b = document.createElement("button");
    b.className = `btn-${btn.variant || "primary"}`;
    b.textContent = btn.text;
    b.onclick = async () => {
      try {
        const ok = btn.handler ? await btn.handler() : true;
        if (ok !== false) close();
      } catch (err) {
        console.error("[modal] action failed", err);
      }
    };
    actions.appendChild(b);
  });

  root.appendChild(backdrop);
  root.appendChild(box);
  requestAnimationFrame(() => {
    backdrop.classList.add("open");
    box.classList.add("open");
    if (autofocus) document.getElementById(autofocus)?.focus();
    else box.focus();  // 預設 focus modal 本身 · 讓 Tab 從這裡開始
  });

  const close = () => {
    backdrop.classList.remove("open");
    box.classList.remove("open");
    setTimeout(() => { backdrop.remove(); box.remove(); }, 200);
    document.removeEventListener("keydown", onKey);
    // v1.3 batch3 · 還原 focus · 鍵盤使用者體驗
    if (previouslyFocused && typeof previouslyFocused.focus === "function") {
      try { previouslyFocused.focus(); } catch {}
    }
  };

  // v1.3 batch3 · ESC 關 + Tab focus trap
  const onKey = (e) => {
    if (e.key === "Escape") { close(); return; }
    if (e.key !== "Tab") return;
    const focusables = box.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };
  document.addEventListener("keydown", onKey);
  backdrop.onclick = close;
}

export const modal = {
  /**
   * 直接顯示 · 給需要自訂 HTML body 的 view 用(E-3 知識庫)
   * @param opts.title / bodyHTML / primary / icon
   * @param opts.onSubmit · async fn 回 true 則關閉 modal
   */
  show(opts) {
    const { title, bodyHTML, primary = "確定", cancel = "關閉", icon = "", onSubmit } = opts;
    return new Promise((resolve) => {
      show({
        title, body: bodyHTML, icon,
        buttons: [
          { text: cancel, variant: "ghost", handler: () => { resolve(false); return true; } },
          { text: primary, variant: "primary", handler: async () => {
            if (!onSubmit) { resolve(true); return true; }
            const ok = await onSubmit();
            if (ok) resolve(true);
            return ok !== false;
          }},
        ],
      });
    });
  },

  /**
   * 表單 modal · 用於 create/edit 場景
   * opts.bodyHTML 裡放 <form id="..."> 自己處理 reportValidity + values
   * opts.onSubmit 回 true 關 modal · 回 false 不關(驗證失敗)
   */
  openForm(opts) {
    return this.show(opts);
  },

  alert(body, { title = "提示", primary = "知道了", icon = "ℹ️" } = {}) {
    return new Promise(resolve => show({
      title, body, icon,
      buttons: [{ text: primary, variant: "primary", handler: () => resolve(true) }],
    }));
  },

  confirm(body, { title = "請確認", primary = "確定", cancel = "取消", icon = "❓", danger = false } = {}) {
    return new Promise(resolve => show({
      title, body, icon,
      buttons: [
        { text: cancel,  variant: "ghost",                            handler: () => resolve(false) },
        { text: primary, variant: danger ? "danger" : "primary",     handler: () => resolve(true)  },
      ],
    }));
  },

  prompt(fields, { title = "輸入", primary = "確定", submitText = "", cancel = "取消", icon = "✏️" } = {}) {
    return new Promise(resolve => {
      const fid = "f_" + Math.random().toString(36).slice(2);
      // v1.3 batch3 · aria-required + label for + 驗證錯誤訊息(不只紅框)
      const html = fields.map((f, i) => {
        const inputId = `${fid}_${i}`;
        const errId = `${inputId}_err`;
        const fieldValue = String(f.value ?? f.default ?? "");
        // v1.3 batch6 · WCAG 1.4.1 · 必填非只靠紅色 · 加 badge 文字 + 圖示
        const labelText = `${escapeHtml(f.label)}${f.required ? ' <span class="modal2-req-badge" aria-hidden="true">必填</span>' : ""}`;
        const ariaReq = f.required ? "aria-required=\"true\"" : "";
        const ariaErr = `aria-describedby="${errId}"`;
        const inputCommon = `id="${inputId}" placeholder="${escapeHtml(f.placeholder || "")}" ${ariaReq} ${ariaErr}`;
        const baseStyle = "width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:14px";
        let inputEl;
        if (f.type === "textarea") {
          inputEl = `<textarea ${inputCommon} rows="${f.rows || 3}" style="${baseStyle};font-family:inherit">${escapeHtml(fieldValue)}</textarea>`;
        } else if (f.type === "select") {
          const options = (f.options || []).map(opt => {
            const value = typeof opt === "object" ? String(opt.value ?? opt.label ?? "") : String(opt);
            const label = typeof opt === "object" ? String(opt.label ?? opt.value ?? "") : String(opt);
            return `<option value="${escapeHtml(value)}" ${value === fieldValue ? "selected" : ""}>${escapeHtml(label)}</option>`;
          }).join("");
          inputEl = `<select ${inputCommon} style="${baseStyle}">${options}</select>`;
        } else {
          const numericAttrs = [
            f.min != null ? `min="${escapeHtml(String(f.min))}"` : "",
            f.max != null ? `max="${escapeHtml(String(f.max))}"` : "",
            f.step != null ? `step="${escapeHtml(String(f.step))}"` : "",
          ].filter(Boolean).join(" ");
          inputEl = `<input ${inputCommon} type="${escapeHtml(f.type || "text")}" value="${escapeHtml(fieldValue)}" ${numericAttrs} style="${baseStyle}">`;
        }
        return `
          <div style="margin-bottom:12px">
            <label for="${inputId}" style="display:block;font-size:12px;color:var(--text-secondary);margin-bottom:4px">
              ${labelText}
            </label>
            ${inputEl}
            <div id="${errId}" class="modal2-field-error" role="alert" style="display:none;font-size:12px;color:var(--red);margin-top:4px"></div>
          </div>`;
      }).join("");

      show({
        title, icon, body: html, autofocus: `${fid}_0`,
        buttons: [
          { text: cancel,  variant: "ghost",   handler: () => resolve(null) },
          { text: submitText || primary, variant: "primary", handler: () => {
            const result = {}; let valid = true; let firstErr = null;
            fields.forEach((f, i) => {
              const el = document.getElementById(`${fid}_${i}`);
              const errEl = document.getElementById(`${fid}_${i}_err`);
              const val = el.value.trim();
              if (f.required && !val) {
                valid = false;
                el.style.borderColor = "var(--red)";
                el.setAttribute("aria-invalid", "true");
                if (errEl) {
                  // v1.3 batch6 · 加 ⚠ 圖示 · SR 會唸「警告」
                  errEl.textContent = `⚠ 「${f.label}」必填`;
                  errEl.style.display = "block";
                }
                if (!firstErr) firstErr = el;
              } else {
                el.style.borderColor = "";
                el.removeAttribute("aria-invalid");
                if (errEl) errEl.style.display = "none";
              }
              result[f.name] = val;
            });
            if (valid) resolve(result);
            else if (firstErr) firstErr.focus();
            return valid;
          }},
        ],
      });
    });
  },
};

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
  const backdrop = document.createElement("div");
  backdrop.className = "modal2-backdrop";
  const box = document.createElement("div");
  box.className = "modal2-box";
  box.innerHTML = `
    <div class="modal2-head">
      <span class="modal2-icon">${icon || ""}</span>
      <h3 class="modal2-title">${escapeHtml(title)}</h3>
    </div>
    <div class="modal2-body">${body}</div>
    <div class="modal2-actions"></div>
  `;
  const actions = box.querySelector(".modal2-actions");
  buttons.forEach(btn => {
    const b = document.createElement("button");
    b.className = `btn-${btn.variant || "primary"}`;
    b.textContent = btn.text;
    b.onclick = () => {
      const ok = btn.handler ? btn.handler() : true;
      if (ok !== false) close();
    };
    actions.appendChild(b);
  });

  root.appendChild(backdrop);
  root.appendChild(box);
  requestAnimationFrame(() => {
    backdrop.classList.add("open");
    box.classList.add("open");
    if (autofocus) document.getElementById(autofocus)?.focus();
  });

  const close = () => {
    backdrop.classList.remove("open");
    box.classList.remove("open");
    setTimeout(() => { backdrop.remove(); box.remove(); }, 200);
    document.removeEventListener("keydown", onEsc);
  };
  const onEsc = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onEsc);
  backdrop.onclick = close;
}

export const modal = {
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

  prompt(fields, { title = "輸入", primary = "確定", cancel = "取消", icon = "✏️" } = {}) {
    return new Promise(resolve => {
      const fid = "f_" + Math.random().toString(36).slice(2);
      const html = fields.map((f, i) => `
        <label style="display:block;margin-bottom:12px">
          <span style="display:block;font-size:12px;color:var(--text-secondary);margin-bottom:4px">
            ${escapeHtml(f.label)}${f.required ? ' <em style="color:var(--red)">*</em>' : ""}
          </span>
          ${f.type === "textarea"
            ? `<textarea id="${fid}_${i}" rows="${f.rows || 3}" placeholder="${escapeHtml(f.placeholder || "")}" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;font-family:inherit;font-size:14px">${escapeHtml(f.default || "")}</textarea>`
            : `<input id="${fid}_${i}" type="${f.type || "text"}" placeholder="${escapeHtml(f.placeholder || "")}" value="${escapeHtml(f.default || "")}" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:14px">`}
        </label>
      `).join("");

      show({
        title, icon, body: html, autofocus: `${fid}_0`,
        buttons: [
          { text: cancel,  variant: "ghost",   handler: () => resolve(null) },
          { text: primary, variant: "primary", handler: () => {
            const result = {}; let valid = true;
            fields.forEach((f, i) => {
              const el = document.getElementById(`${fid}_${i}`);
              const val = el.value.trim();
              if (f.required && !val) { valid = false; el.style.borderColor = "var(--red)"; }
              result[f.name] = val;
            });
            if (valid) resolve(result);
            return valid;
          }},
        ],
      });
    });
  },
};

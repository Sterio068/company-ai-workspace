/**
 * <template> 渲染 helper
 *
 * 慣例:HTML 中 <template id="tpl-project-card"> 放卡片 skeleton,
 *      用 [data-slot="name"] 標記可填槽位。fill() 會把 fields 對應塞進去,
 *      並把根節點的 [data-attr-id] 等屬性依傳入值設好。
 *
 * 用法:
 *   const node = tpl("tpl-project-card", {
 *     name: p.name,
 *     client: p.client,
 *     deadline: p.deadline,
 *   }, {
 *     attrs: { "data-project-id": p.id },
 *     style: { "--project-color": color },
 *   });
 *   container.appendChild(node);
 */

export function tpl(id, slots = {}, opts = {}) {
  const template = document.getElementById(id);
  if (!template || template.tagName !== "TEMPLATE") {
    throw new Error(`Template not found: #${id}`);
  }
  const node = template.content.firstElementChild.cloneNode(true);

  // 填 data-slot
  for (const [key, val] of Object.entries(slots)) {
    const target = node.querySelector(`[data-slot="${key}"]`);
    if (!target) continue;
    if (val === null || val === undefined || val === "") {
      target.remove();
    } else if (target.tagName === "IMG") {
      target.src = val;
    } else {
      target.textContent = String(val);
    }
  }

  // 設 attrs(僅限 data-* / class / style / title / href 等安全屬性)
  const allow = /^(data-|aria-|class$|style$|title$|href$|alt$|id$)/;
  if (opts.attrs) {
    for (const [k, v] of Object.entries(opts.attrs)) {
      if (!allow.test(k)) continue;
      node.setAttribute(k, v);
    }
  }
  if (opts.style) {
    for (const [k, v] of Object.entries(opts.style)) {
      node.style.setProperty(k, v);
    }
  }
  if (opts.classes) {
    for (const c of opts.classes) node.classList.add(c);
  }
  if (opts.onclick) {
    node.addEventListener("click", opts.onclick);
  }
  return node;
}

/** 清空 container + append 多個 node */
export function renderList(container, nodes) {
  if (!container) return;
  container.replaceChildren(...nodes);
}

/**
 * 對話內容 XSS 防線 · v1.50 從 chat.js 抽出
 *
 * 第二道防線:即使 marked renderer.html 已擋 block-level raw HTML,
 * inline event handler 仍可能從其他路徑進來,因此用 DOMParser 白名單再過一次。
 *
 * 純 functional · 無 this · 無模組狀態 · 易測
 */

const ALLOWED_TAGS = new Set([
  "p", "br", "hr", "strong", "em", "code", "pre", "blockquote",
  "ul", "ol", "li", "a", "img",
  "h1", "h2", "h3", "h4", "h5", "h6",
  "table", "thead", "tbody", "tr", "th", "td",
  "span", "div",
  "del", "ins", "sub", "sup",
]);
const ALLOWED_ATTRS = new Set(["href", "src", "alt", "title", "colspan", "rowspan", "class"]);

export function sanitizeRenderedHtml(html) {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<body>${html}</body>`, "text/html");
    _cleanNode(doc.body);
    return doc.body.innerHTML;
  } catch {
    return html.replace(/<[^>]*>/g, "");
  }
}

function _cleanNode(node) {
  const children = Array.from(node.childNodes);
  for (const child of children) {
    if (child.nodeType === 3) continue;
    if (child.nodeType !== 1) { child.remove(); continue; }

    const tag = child.tagName.toLowerCase();
    if (!ALLOWED_TAGS.has(tag)) {
      const frag = document.createDocumentFragment();
      while (child.firstChild) frag.appendChild(child.firstChild);
      child.replaceWith(frag);
      continue;
    }
    for (const attr of Array.from(child.attributes)) {
      const name = attr.name.toLowerCase();
      if (name.startsWith("on")) {
        child.removeAttribute(attr.name);
        continue;
      }
      if (!ALLOWED_ATTRS.has(name)) {
        child.removeAttribute(attr.name);
        continue;
      }
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
    _cleanNode(child);
  }
}

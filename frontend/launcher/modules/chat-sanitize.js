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
const SAFE_HREF_PROTOCOLS = new Set(["http:", "https:", "mailto:", "tel:"]);
const SAFE_SRC_PROTOCOLS = new Set(["http:", "https:", "blob:"]);

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
        if (!_isSafeUrl(attr.value, name)) {
          child.removeAttribute(attr.name);
          continue;
        }
      }
    }
    _cleanNode(child);
  }
}

function _isSafeUrl(value, attrName) {
  const raw = String(value || "").trim();
  if (!raw) return false;
  const lower = raw.toLowerCase();
  if (lower.startsWith("#") || lower.startsWith("/") || lower.startsWith("./") || lower.startsWith("../")) {
    return true;
  }
  if (attrName === "src" && lower.startsWith("data:image/")) return true;
  if (lower.startsWith("javascript:") || lower.startsWith("vbscript:") || lower.startsWith("file:")) {
    return false;
  }
  try {
    const url = new URL(raw, window.location.origin);
    const allowed = attrName === "src" ? SAFE_SRC_PROTOCOLS : SAFE_HREF_PROTOCOLS;
    return allowed.has(url.protocol);
  } catch {
    return false;
  }
}

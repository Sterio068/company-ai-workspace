/**
 * Toast 通知系統 · 取代 alert() 的輕量 feedback
 */
import { escapeHtml } from "./util.js";

let container = null;

function ensureContainer() {
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  return container;
}

export function show(msg, type = "info", duration = 4000) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<div class="toast-body">${escapeHtml(msg)}</div><button class="toast-close">✕</button>`;
  el.querySelector(".toast-close").onclick = () => el.remove();
  ensureContainer().appendChild(el);
  if (duration > 0) setTimeout(() => el.remove(), duration);
}

export const toast = {
  success: (m) => show(m, "success"),
  warn:    (m) => show(m, "warn"),
  error:   (m) => show(m, "error"),
  info:    (m) => show(m, "info"),
};

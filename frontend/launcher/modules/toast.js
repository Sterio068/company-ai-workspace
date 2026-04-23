/**
 * Toast 通知系統 · 取代 alert() 的輕量 feedback
 *
 * v1.3 P1#8 · 標準化錯誤訊息格式
 * 用法:
 *   toast.error("讀取失敗")                       — 簡短
 *   toast.error("上傳失敗", { detail: "檔案太大" })  — 含細節
 *   toast.error("網路錯誤", { action: { label: "重試", onClick: () => loadData() } })
 *   toast.success("已儲存")
 */
import { escapeHtml } from "./util.js";

let container = null;

function ensureContainer() {
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    // v1.3 P1#8 · a11y · 讀屏器會唸出 toast 內容 · error/warn 用 assertive
    container.setAttribute("role", "status");
    container.setAttribute("aria-live", "polite");
    container.setAttribute("aria-atomic", "true");
    document.body.appendChild(container);
  }
  return container;
}

/**
 * 顯示 toast
 * @param {string} msg - 主要訊息
 * @param {string} type - "info" | "success" | "warn" | "error"
 * @param {object} opts - { duration, detail, action: {label, onClick} }
 */
export function show(msg, type = "info", opts = {}) {
  // 向下相容:duration 可直接傳數字
  if (typeof opts === "number") opts = { duration: opts };
  const duration = opts.duration ?? (type === "error" ? 6000 : 4000);
  const detail = opts.detail || "";
  const action = opts.action;

  const el = document.createElement("div");
  el.className = `toast ${type}`;
  // v1.3 P1#8 · error/warn 用 assertive(立刻唸)· success/info 用 polite(等說完再唸)
  el.setAttribute("role", type === "error" || type === "warn" ? "alert" : "status");

  const detailHtml = detail ? `<div class="toast-detail">${escapeHtml(detail)}</div>` : "";
  const actionHtml = action ? `<button class="toast-action">${escapeHtml(action.label)}</button>` : "";

  el.innerHTML = `
    <div class="toast-body">
      <div class="toast-msg">${escapeHtml(msg)}</div>
      ${detailHtml}
    </div>
    ${actionHtml}
    <button class="toast-close" aria-label="關閉通知">✕</button>
  `;

  el.querySelector(".toast-close").onclick = () => el.remove();
  if (action) {
    el.querySelector(".toast-action").onclick = () => {
      try { action.onClick(); } catch (e) { console.error(e); }
      el.remove();
    };
  }

  ensureContainer().appendChild(el);
  if (duration > 0) setTimeout(() => el.remove(), duration);
  return el;
}

export const toast = {
  success: (m, opts) => show(m, "success", opts),
  warn:    (m, opts) => show(m, "warn", opts),
  error:   (m, opts) => show(m, "error", opts),
  info:    (m, opts) => show(m, "info", opts),
};

/**
 * v1.3 P1#8 · 標準化錯誤訊息工具
 * 統一格式 · 避免「網路錯:[object]」「儲存失敗:undefined」這類醜訊息
 */

/** 從 fetch error / response 萃取易讀訊息 */
export function describeError(e, fallback = "未知錯誤") {
  if (!e) return fallback;
  if (typeof e === "string") return e;
  if (e instanceof Error) return e.message || fallback;
  if (typeof e === "object") {
    return e.detail || e.message || e.error || JSON.stringify(e).slice(0, 100);
  }
  return String(e);
}

/** 網路錯 toast · 統一文案 */
export function networkError(action, e, retryFn) {
  const detail = describeError(e, "網路或服務暫時無回應");
  const opts = { detail };
  if (retryFn) opts.action = { label: "重試", onClick: retryFn };
  toast.error(`${action} · 網路錯`, opts);
}

/** 操作失敗 toast · 統一文案(伺服器有回應但失敗) */
export function operationError(action, e, retryFn) {
  const detail = describeError(e);
  const opts = { detail };
  if (retryFn) opts.action = { label: "重試", onClick: retryFn };
  toast.error(`${action}失敗`, opts);
}

/** 權限不足 toast */
export function permissionError(action) {
  toast.error(`${action} · 需 admin 權限`, { detail: "聯絡 Champion 開通" });
}

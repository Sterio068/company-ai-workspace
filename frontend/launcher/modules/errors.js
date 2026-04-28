/**
 * Error Boundary · 包裝 view loader,fetch 失敗不讓整個 UI 壞
 * 用法:withErrorBoundary(async () => { ... }, { fallback: selector, message: "..." })
 */
import { toast } from "./toast.js";
import { escapeHtml } from "./util.js";

export async function withErrorBoundary(fn, { fallback, message = "載入失敗 · 稍後重試" } = {}) {
  try {
    return await fn();
  } catch (e) {
    console.error("[ErrorBoundary]", e);
    toast.error(message);
    if (fallback) {
      const el = document.querySelector(fallback);
      if (el) {
        el.innerHTML = `
          <div class="error-state">
            <div class="error-icon">😓</div>
            <div class="error-msg">${escapeHtml(message)}</div>
            <div class="error-detail">${escapeHtml(e.message || "")}</div>
            <button data-action="window.reload" class="btn-ghost" style="margin-top:12px">重新整理</button>
          </div>
        `;
      }
    }
    return null;
  }
}

/**
 * 全域未捕捉錯誤 handler · 避免整頁崩潰
 * v4.4:前台只顯示可恢復話術 · 細節寫 console + 用 request id 串 backend log
 */
function _makeRid() {
  return "rid-" + Math.random().toString(36).slice(2, 10);
}

// v1.66 Q3 · 把 frontend errors 也送 backend · 集中看 admin dashboard
// 不依賴外部 Sentry SaaS · 自有 mongo error_log collection
async function _reportError(rid, kind, payload) {
  try {
    await fetch("/api-accounting/admin/error-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        rid,
        kind,
        ts: new Date().toISOString(),
        ua: navigator.userAgent.slice(0, 200),
        url: location.pathname + location.hash,
        ...payload,
      }),
      keepalive: true,  // 即使 page unload 也送
    });
  } catch { /* report 失敗別讓使用者看到 · console 已有 */ }
}

export function installGlobalErrorHandler() {
  window.addEventListener("error", (e) => {
    const rid = _makeRid();
    console.error(`[Global Error ${rid}]`, e.error || e.message, e.filename, e.lineno);
    _reportError(rid, "uncaught", {
      message: String(e.message || e.error?.message || "?").slice(0, 500),
      file: e.filename, line: e.lineno, col: e.colno,
      stack: (e.error?.stack || "").slice(0, 1500),
    });
    toast.error(`系統暫時有點問題 · 請按 ⌘⇧R 重新整理 · 問題編號 ${rid}`);
  });
  window.addEventListener("unhandledrejection", (e) => {
    const rid = _makeRid();
    console.error(`[Unhandled Promise ${rid}]`, e.reason);
    if (e.reason?.name === "SessionExpiredError") return;
    _reportError(rid, "unhandled-promise", {
      message: String(e.reason?.message || e.reason || "?").slice(0, 500),
      stack: (e.reason?.stack || "").slice(0, 1500),
    });
    toast.error(`網路或服務短暫異常 · 再試一次 · 問題編號 ${rid}`);
  });
}

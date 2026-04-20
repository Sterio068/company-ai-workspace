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
            <button onclick="location.reload()" class="btn-ghost" style="margin-top:12px">重新整理</button>
          </div>
        `;
      }
    }
    return null;
  }
}

/**
 * 全域未捕捉錯誤 handler · 避免整頁崩潰
 */
export function installGlobalErrorHandler() {
  window.addEventListener("error", (e) => {
    console.error("[Global Error]", e.error);
    toast.error(`⚠️ 未預期錯誤:${e.message}`);
  });
  window.addEventListener("unhandledrejection", (e) => {
    console.error("[Unhandled Promise]", e.reason);
    toast.error(`⚠️ Promise 錯誤:${e.reason?.message || e.reason}`);
  });
}

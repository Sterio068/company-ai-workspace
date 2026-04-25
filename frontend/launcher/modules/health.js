/**
 * Service Health Indicator · Sidebar 底部 · 每 30s 自動檢查
 * v4.2 起:後端完全離線時拉出 banner · 恢復時自動收
 */
import { _showBanner, _hideBanner } from "./auth.js";

let _offlineBannerShown = false;

async function check() {
  const r = { librechat: false, accounting: false };
  const timeout = (ms) => AbortSignal.timeout ? AbortSignal.timeout(ms) : undefined;
  try { r.librechat  = (await fetch("/api/config",             { signal: timeout(3000) })).ok; } catch {}
  try { r.accounting = (await fetch("/api-accounting/healthz", { signal: timeout(3000) })).ok; } catch {}
  return r;
}

async function update() {
  const r = await check();
  const el = document.getElementById("health-indicator");
  const all  = r.librechat && r.accounting;
  const some = r.librechat || r.accounting;

  if (el) {
    el.className = "health-indicator " + (all ? "ok" : some ? "warn" : "err");
    el.title = `對話服務:${r.librechat ? "✓" : "✗"} | 會計介接:${r.accounting ? "✓" : "✗"}`;
    const text = el.querySelector(".health-text");
    if (text) text.textContent = all ? "系統正常" : some ? "部分降級" : "後端離線";
  }

  // 後端完全離線 → 拉 banner · 有回應了就收
  if (!some && !_offlineBannerShown) {
    _offlineBannerShown = true;
    _showBanner({
      message: "⚠ 後端服務離線 · 智慧對話暫時無法使用。請等待系統恢復,或通知管理員。",
      actionLabel: "重試",
      onClick: () => update(),
      variant: "error",
    });
  } else if (some && _offlineBannerShown) {
    _offlineBannerShown = false;
    _hideBanner();
  }
}

export const health = {
  update,
  start() {
    update();
    setInterval(update, 30000);
  },
};

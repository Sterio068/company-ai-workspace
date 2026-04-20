/**
 * Service Health Indicator · Sidebar 底部 · 每 30s 自動檢查
 */

async function check() {
  const r = { librechat: false, accounting: false };
  const timeout = (ms) => AbortSignal.timeout ? AbortSignal.timeout(ms) : undefined;
  try { r.librechat  = (await fetch("/api/config",               { signal: timeout(3000) })).ok; } catch {}
  try { r.accounting = (await fetch("/api-accounting/healthz",   { signal: timeout(3000) })).ok; } catch {}
  return r;
}

async function update() {
  const r = await check();
  const el = document.getElementById("health-indicator");
  if (!el) return;
  const all = r.librechat && r.accounting;
  const some = r.librechat || r.accounting;
  el.className = "health-indicator " + (all ? "ok" : some ? "warn" : "err");
  el.title = `LibreChat: ${r.librechat ? "✓" : "✗"} | Accounting: ${r.accounting ? "✓" : "✗"}`;
  const text = el.querySelector(".health-text");
  if (text) text.textContent = all ? "系統正常" : some ? "部分降級" : "後端離線";
}

export const health = {
  update,
  start() {
    update();
    setInterval(update, 30000);
  },
};

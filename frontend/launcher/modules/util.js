/**
 * 承富 Launcher · 共用 utility
 * ES module · 無狀態 · 全 pure functions
 */

export async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, { credentials: "include", ...opts });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export function formatDate(d) {
  const wk = ["日", "一", "二", "三", "四", "五", "六"];
  return `${d.getFullYear()} 年 ${d.getMonth()+1} 月 ${d.getDate()} 日 · 週${wk[d.getDay()]}`;
}

export function greetingFor(hour) {
  if (hour < 6)  return "凌晨好";
  if (hour < 12) return "早安";
  if (hour < 14) return "午安";
  if (hour < 18) return "下午好";
  return "晚上好";
}

export function timeAgo(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diffMs / 60000);
  if (m < 1)  return "剛剛";
  if (m < 60) return `${m} 分前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 時前`;
  const d = Math.floor(h / 24);
  return `${d} 天前`;
}

export function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function formatMoney(n) {
  if (!n || isNaN(n)) return "—";
  return "NT$ " + Number(n).toLocaleString("en-US");
}

export function skeletonCards(count = 3) {
  return Array(count).fill(0).map(() => `
    <div class="skeleton-card">
      <div class="skeleton skeleton-line md"></div>
      <div class="skeleton skeleton-line sm"></div>
      <div class="skeleton skeleton-line"></div>
    </div>
  `).join("");
}

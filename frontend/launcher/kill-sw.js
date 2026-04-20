// 承富 Launcher · SW 自我銷毀腳本
// ============================================================
// 這個 SW 被註冊後 · 立刻把自己 unregister · 並清所有 cache
// 用途:清除 LibreChat v0.8.4 留下的 Workbox SW 殘影
// ============================================================

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", async (event) => {
  event.waitUntil((async () => {
    // 清所有 cache
    const keys = await caches.keys();
    await Promise.all(keys.map(k => caches.delete(k)));
    // 取所有 clients
    const clients = await self.clients.matchAll({ type: "window" });
    // unregister 自己
    await self.registration.unregister();
    // 通知所有 window reload(乾淨重載)
    clients.forEach(c => c.navigate(c.url));
  })());
});

self.addEventListener("fetch", (event) => {
  // 不攔截任何 request · 全部直出
  return;
});

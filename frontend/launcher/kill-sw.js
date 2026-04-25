// 承富 Launcher · SW 自我銷毀腳本
// ============================================================
// 這個 SW 被註冊後 · 立刻把自己 unregister
// 不清同 origin cache,避免傷到 LibreChat 或未來 PWA。
// ============================================================

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", async (event) => {
  event.waitUntil((async () => {
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

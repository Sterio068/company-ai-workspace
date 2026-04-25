// ============================================================
// 承富 AI · Self-Destruct Service Worker(dev 階段不用 PWA)
// ============================================================
// 任何已註冊過舊版承富 SW 的瀏覽器,會在下次 update check 拿到這個 SW
// → skipWaiting → activate 時 unregister 自己 + navigate
// 不清同 origin cache,避免傷到 LibreChat 或未來 PWA。

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    await self.registration.unregister();
    const cs = await self.clients.matchAll({ type: "window" });
    cs.forEach((c) => c.navigate(c.url));
  })());
});

// Fetch · 完全不攔截 · 直接 pass-through network
self.addEventListener("fetch", () => {
  return;
});

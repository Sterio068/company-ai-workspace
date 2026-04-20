// ============================================================
// 承富 AI · Self-Destruct Service Worker(dev 階段不用 PWA)
// ============================================================
// 任何已註冊過舊版承富 SW 的瀏覽器,會在下次 update check 拿到這個 SW
// → install 時清 cache / skipWaiting → activate 時 unregister 自己 + navigate
// 之後 app.js 也會再次主動 unregister(雙保險)。

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    await self.registration.unregister();
    const cs = await self.clients.matchAll({ type: "window" });
    cs.forEach((c) => c.navigate(c.url));
  })());
});

// Fetch · 完全不攔截 · 直接 pass-through network
self.addEventListener("fetch", () => {
  return;
});

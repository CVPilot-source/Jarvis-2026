/* Service Worker: Mitarbeiter-Seite auch ohne Internet öffnen können */
const CACHE = "objekt-scanner-v1";
const STATIC = ["/static/style.css", "/static/worker.js", "/static/icon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const isWorkerPage = /^\/o\/[^/]+$/.test(url.pathname) || url.pathname.startsWith("/manifest/");
  const isStatic = url.pathname.startsWith("/static/");
  if (!isWorkerPage && !isStatic) return; // Admin-Bereich nie cachen

  // Netzwerk zuerst, bei Offline aus dem Cache
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});

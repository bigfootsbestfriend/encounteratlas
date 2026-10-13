// Encounter Atlas service worker: pages network-first (offline falls back to the last copy),
// static files and map data cache-first. Map tiles are left to the browser cache.
const V = 'ea-v31';
const BASE = new URL(self.registration.scope).pathname.replace(/\/$/, '');
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(V).then((c) => c.addAll([BASE + '/', BASE + '/map/', BASE + '/static/site.css', BASE + '/static/map.js'])).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  const isPage = e.request.mode === 'navigate';
  if (isPage) {
    e.respondWith(fetch(e.request).then((r) => { const copy = r.clone(); caches.open(V).then((c) => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request).then((r) => r || caches.match(BASE + '/'))));
    return;
  }
  if (u.pathname.includes('/static/') || u.pathname.includes('/data/')) {
    e.respondWith(caches.match(e.request).then((hit) => {
      const net = fetch(e.request).then((r) => { const copy = r.clone(); caches.open(V).then((c) => c.put(e.request, copy)); return r; });
      return hit || net;
    }));
  }
});

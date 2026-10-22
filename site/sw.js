// Encounter Atlas service worker: pages network-first (offline falls back to the last copy),
// static files and map data cache-first. Map tiles are left to the browser cache.
const V = 'ea-v83';
const BASE = new URL(self.registration.scope).pathname.replace(/\/$/, '');
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(V).then((c) => c.addAll([BASE + '/', BASE + '/map/', BASE + '/near-me/', BASE + '/static/site.css', BASE + '/static/map.js',
    BASE + '/static/nearme.js', BASE + '/static/nearme.css', BASE + '/data/near/index.json'])).then(() => self.skipWaiting()));
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
      // Offline: the last copy of this page (ignoring ?source=app and the like), else the app home, else the home page.
      .catch(() => caches.match(e.request, { ignoreSearch: true })
        .then((r) => r || caches.match(BASE + (u.pathname.startsWith(BASE + '/near-me/') ? '/near-me/' : '/')))));
    return;
  }
  if (u.pathname.includes('/static/') || u.pathname.includes('/data/')) {
    e.respondWith(caches.match(e.request).then((hit) => {
      const net = fetch(e.request).then((r) => { const copy = r.clone(); caches.open(V).then((c) => c.put(e.request, copy)); return r; });
      return hit || net;
    }));
  }
});

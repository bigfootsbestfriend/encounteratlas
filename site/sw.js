// Encounter Atlas service worker: pages network-first with navigation preload; on a slow connection (no answer in
// 2.5 s) the last saved copy shows instead, and offline falls back to it too,
// static files and map data cache-first. Map tiles are left to the browser cache.
// Also: sighting-alert notifications (push), and waking the report form when a report queued with no signal can go.
const V = 'ea-v129';
const BASE = new URL(self.registration.scope).pathname.replace(/\/$/, '');
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(V).then((c) => c.addAll([BASE + '/', BASE + '/map/', BASE + '/near-me/', BASE + '/report/', BASE + '/static/site.css', BASE + '/static/map.js',
    BASE + '/static/nearme.js', BASE + '/static/nearme.css', BASE + '/data/near/index.json',
    BASE + '/road-trip/', BASE + '/cards/', BASE + '/static/roadtrip.js', BASE + '/static/placefind.js', BASE + '/static/cards.js', BASE + '/static/roadtrip.css', BASE + '/data/roadtrip.json',
    BASE + '/tools/skywatch/', BASE + '/static/skywatch.js', BASE + '/static/skywatch.css', BASE + '/journal/', BASE + '/static/journal.js', BASE + '/static/journal.css',
    BASE + '/stories/campfire/', BASE + '/static/campfire.js', BASE + '/static/campfire.css', BASE + '/data/campfire.json',
    BASE + '/mystery-of-the-day/', BASE + '/static/motd.js', BASE + '/static/motd.css', BASE + '/static/conditions.js', BASE + '/static/conditions.css', BASE + '/data/showers.json', BASE + '/static/legend.css', BASE + '/data/historic.geojson', BASE + '/static/cards.css', BASE + '/static/cards/back.webp', BASE + '/static/podplayer.js', BASE + '/static/podplayer.css', BASE + '/data/cards.json',
    BASE + '/static/report.js', BASE + '/static/report.css', BASE + '/static/app-bridge.js', BASE + '/static/vote.js', BASE + '/static/skycore.js',
    BASE + '/static/fonts/publicsans-ijwRs572Xtc6ZYQws9YVwnNGfJ4.woff2', BASE + '/static/fonts/zillaslab-dFa5ZfeM_74wlPZtksIFYoEf6HOpWw.woff2'])).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k))))
    .then(() => self.registration.navigationPreload && self.registration.navigationPreload.enable())
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;   // podcast audio is always another site's, so it's never touched
  if (e.request.destination === 'audio' || e.request.headers.has('range')) return;
  const isPage = e.request.mode === 'navigate';
  if (isPage) {
    const saved = () => caches.match(e.request, { ignoreSearch: true });
    // Offline: the last copy of this page (ignoring ?source=app and the like), else the app home, else the home page.
    const fallback = () => saved().then((r) => r || caches.match(BASE + (u.pathname.startsWith(BASE + '/near-me/') ? '/near-me/' : '/')));
    const net = Promise.resolve(e.preloadResponse).then((pre) => pre || fetch(e.request)).then((r) => {
      if (r && r.ok) { const copy = r.clone(); caches.open(V).then((c) => c.put(e.request, copy)); }
      return r;
    });
    e.waitUntil(net.catch(() => {}));
    // Slow connection: after 2.5 s show the saved copy if there is one (the fresh copy still lands in the cache)
    const slow = new Promise((res) => setTimeout(() => saved().then((r) => r && res(r)), 2500));
    e.respondWith(Promise.race([net, slow]).catch(fallback));
    return;
  }
  if (u.pathname.includes('/static/') || u.pathname.includes('/data/')) {
    e.respondWith(caches.match(e.request).then((hit) => {
      const net = fetch(e.request).then((r) => { const copy = r.clone(); caches.open(V).then((c) => c.put(e.request, copy)); return r; });
      return hit || net;
    }));
  }
});

// Sighting alerts: the Worker sends {title, body, url} for a report near the reader's saved area.
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data.json(); } catch (x) { d = { title: 'Encounter Atlas', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'New report near you', {
    body: d.body || '', icon: BASE + '/static/app-192.png', badge: BASE + '/static/app-192.png',
    tag: d.id ? 'report-' + d.id : undefined, data: { url: d.url || BASE + '/near-me/' },
  }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || BASE + '/near-me/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
    const same = cs.find((c) => c.url === url);
    return same ? same.focus() : self.clients.openWindow(url);
  }));
});

// Background Sync: a report written with no signal is waiting in the form's storage. The spam check needs a page,
// so an open page is asked to send it; with none open, a notification (if allowed) brings the form back.
self.addEventListener('sync', (e) => {
  if (e.tag !== 'ea-send-reports') return;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
    if (cs.length) { cs.forEach((c) => c.postMessage({ type: 'send-queued' })); return; }
    if (self.Notification && Notification.permission === 'granted') {
      return self.registration.showNotification('Back online', { body: 'Tap to send the report you wrote with no signal.',
        icon: BASE + '/static/app-192.png', tag: 'queued-report', data: { url: BASE + '/report/?source=queued' } });
    }
  }));
});

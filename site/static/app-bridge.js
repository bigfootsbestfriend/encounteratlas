// The Android / iPhone app (Capacitor, ~/Work/encounteratlas-cap) is this website in a WebView. This file is the only
// app-specific code the site has. In a normal browser and in the old TWA it stops on the first line, so pages behave
// exactly as before. Inside the app it:
//   - closes an open menu, goes back a page, or leaves the app (at the app home, /near-me/) on the Back button
//   - sends the site's share buttons (navigator.share) to the phone's share sheet
//   - mirrors the podcast player's Media Session to the phone, so audio keeps playing with the screen locked and the
//     lock screen gets play / pause / skip buttons (native MediaPlaybackService)
//   - exposes window.EAApp for nearme.js sighting alerts: { native, platform, push, ready, pushToken(), pushOff() }
//     push is false until the app is built with Firebase (google-services.json); nearme.js then says alerts are coming.
// "Use my location" needs nothing here: the app asks for the location permission itself.
(function () {
  const C = window.Capacitor;
  if (!C || typeof C.isNativePlatform !== 'function' || !C.isNativePlatform()) return;
  const P = C.Plugins || {};
  const quiet = (p) => (p && p.catch ? p.catch(() => {}) : p);
  document.documentElement.classList.add('in-app');

  const EA = window.EAApp = { native: true, platform: C.getPlatform ? C.getPlatform() : 'android', push: false, version: '' };

  // iPhone: the app draws the page under the status bar (contentInset 'never'), so let the page reach the edges and pad
  // for the safe areas itself (site.css .in-ios). Safari does this on its own; the WebView doesn't.
  if (EA.platform === 'ios') {
    document.documentElement.classList.add('in-ios');
    const vp = document.querySelector('meta[name="viewport"]');
    if (vp && !/viewport-fit/.test(vp.content)) vp.content += ', viewport-fit=cover';
  }
  EA.ready = (P.EaApp ? P.EaApp.info().catch(() => ({})) : Promise.resolve({})).then((i) => {
    EA.push = !!(i && i.push) && !!P.PushNotifications;
    EA.version = (i && i.version) || '';
    return EA;
  });

  // The splash screen hides itself after 2.5 s; on a quick connection the page is ready sooner.
  if (P.SplashScreen) quiet(P.SplashScreen.hide({ fadeOutDuration: 200 }));

  // ---------- Back button ----------
  if (P.App) {
    P.App.addListener('backButton', (e) => {
      const open = document.querySelector('details.mm[open], details.nav-dd[open]');
      if (open) { open.open = false; return; }
      const home = location.pathname === '/near-me/' || location.pathname === '/near-me/index.html';
      if (home || !e || !e.canGoBack) quiet(P.App.exitApp());
      else history.back();
    });
  }

  // ---------- Share sheet ----------
  if (P.Share) {
    const share = (d) => {
      d = d || {};
      return P.Share.share({ title: d.title || document.title, text: d.text || undefined, url: d.url || undefined, dialogTitle: 'Share' })
        .then(() => undefined)
        .catch((err) => { throw new DOMException(String((err && err.message) || 'Share canceled'), 'AbortError'); });
    };
    try {
      Object.defineProperty(navigator, 'share', { value: share, configurable: true, writable: true });
      Object.defineProperty(navigator, 'canShare', { value: (d) => !!d && !(d.files && d.files.length), configurable: true, writable: true });
    } catch (e) { /* leave the page's own fallback (copy link) */ }
  }

  // ---------- Podcast player: background audio + lock-screen controls ----------
  // Android's WebView has no Media Session API at all, so the app supplies one (navigator.mediaSession and
  // MediaMetadata) that hands everything to the phone. podplayer.js uses it exactly as it does in Chrome.
  if (P.EaApp) {
    let ms = navigator.mediaSession;
    if (!ms) {
      ms = {};
      try { Object.defineProperty(navigator, 'mediaSession', { value: ms, configurable: true }); } catch (e) { /* stays without */ }
    }
    if (!window.MediaMetadata) {
      window.MediaMetadata = class MediaMetadata {
        constructor(i) { i = i || {}; this.title = i.title || ''; this.artist = i.artist || ''; this.album = i.album || ''; this.artwork = i.artwork || []; }
      };
    }
    const handlers = {};
    let meta = null, state = 'none', pos = { position: 0, duration: 0, playbackRate: 1 }, sent = null, sentAt = 0;
    const origSet = typeof ms.setActionHandler === 'function' ? ms.setActionHandler.bind(ms) : null;
    const send = (force) => {
      const now = Date.now();
      if (!force && sent) {
        // Only when the lock screen would drift (a seek, a rate change) or every 15 s; Android moves the bar itself.
        const expect = sent.position + (sent.state === 'playing' ? ((now - sentAt) / 1000) * sent.rate : 0);
        if (Math.abs(expect - pos.position) < 3 && now - sentAt < 15000) return;
      }
      const art = meta && meta.artwork && meta.artwork.length ? meta.artwork[meta.artwork.length - 1].src : '';
      sent = { state: meta || state === 'playing' ? state : 'none', title: (meta && meta.title) || '', artist: (meta && meta.artist) || '', art,
        position: pos.position || 0, duration: pos.duration || 0, rate: pos.playbackRate || 1 };
      sentAt = now;
      quiet(P.EaApp.media(sent));
    };
    try {
      ms.setActionHandler = (action, fn) => { handlers[action] = fn; if (origSet) { try { origSet(action, fn); } catch (e) { /* unsupported action */ } } };
      Object.defineProperty(ms, 'metadata', { configurable: true, get: () => meta, set: (m) => { meta = m; send(true); } });
      Object.defineProperty(ms, 'playbackState', { configurable: true, get: () => state, set: (s) => { if (s !== state) { state = s; send(true); } } });
      ms.setPositionState = (p) => { pos = Object.assign({ position: 0, duration: 0, playbackRate: 1 }, p || {}); send(false); };
      P.EaApp.addListener('mediaAction', (e) => {
        const a = e && e.action;
        const fn = handlers[a] || (a === 'stop' ? handlers.pause : null);
        if (fn) fn({ action: a, seekTime: e.seekTime });
      });
      // Leaving the page stops its audio, so the lock-screen controls go too.
      addEventListener('pagehide', () => { if (sent && sent.state !== 'none') quiet(P.EaApp.media({ state: 'none' })); });
    } catch (e) { /* the page's audio still plays; just no lock-screen controls */ }
  }

  // ---------- Sighting alerts (native push through Firebase Cloud Messaging) ----------
  const PN = P.PushNotifications;
  // Asks for the notification permission if needed, registers with FCM and resolves the device token.
  EA.pushToken = () => new Promise((resolve, reject) => {
    if (!PN || !EA.push) { reject(new Error('Alerts are coming to the app soon.')); return; }
    const subs = [];
    const done = (fn, v) => { subs.forEach((s) => quiet(s && s.remove && s.remove())); fn(v); };
    (async () => {
      let perm = await PN.checkPermissions();
      if (perm.receive !== 'granted') perm = await PN.requestPermissions();
      if (perm.receive !== 'granted') throw new Error('Notifications are off for this app. Turn them on in your phone settings, then try again.');
      subs.push(await PN.addListener('registration', (t) => done(resolve, t.value)));
      subs.push(await PN.addListener('registrationError', () => done(reject, new Error('This phone could not set up alerts. Try again later.'))));
      await PN.register();
    })().catch((err) => done(reject, err));
  });
  EA.pushOff = () => (PN && EA.push ? PN.unregister().catch(() => {}) : Promise.resolve());
})();

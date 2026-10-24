// Campfire mode (/stories/campfire/). Nothing happens until "Start campfire mode" is tapped, apart from enabling the
// button and, when a service worker controls the page, warming its cache with data/campfire.json on idle so the
// mode works later with no signal. The night view is built here, red on black only (see campfire.css).
(function () {
  'use strict';
  var start = document.querySelector('[data-cf-start]');
  var cfgEl = document.getElementById('cf-config');
  if (!start || !cfgEl) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var SIZES = [1.1, 1.25, 1.4, 1.6, 1.85, 2.15, 2.5];
  var KEY = 'ea-campfire';
  var prefs = {};
  try { prefs = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { prefs = {}; }
  var size = typeof prefs.size === 'number' ? Math.max(0, Math.min(SIZES.length - 1, prefs.size)) : (window.innerWidth >= 760 ? 4 : 3);
  var canSpeak = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;

  var stories = null, order = [], pos = 0, root = null, els = {}, lock = null, speaking = false, lastFocus = null,
      themeMeta = null, oldTheme = '', inerted = [], pushed = false, open = false;

  start.disabled = false;
  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    var warm = function () { fetch(cfg.data).catch(function () {}); };
    if ('requestIdleCallback' in window) requestIdleCallback(warm, { timeout: 8000 }); else setTimeout(warm, 4000);
  }

  function save() { try { localStorage.setItem(KEY, JSON.stringify({ size: size })); } catch (e) {} }

  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }

  function shuffle(n) {
    var a = [];
    for (var i = 0; i < n; i++) a.push(i);
    for (var j = n - 1; j > 0; j--) {
      var r = Math.floor(Math.random() * (j + 1)), t = a[j]; a[j] = a[r]; a[r] = t;
    }
    return a;
  }

  function build() {
    root = el('div', { class: 'cf-night', id: 'cf-night', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Campfire mode', hidden: '' });
    var bar = el('div', { class: 'cf-bar' });
    els.pos = el('span', { class: 'cf-pos', 'aria-hidden': 'true' });
    els.exit = el('button', { type: 'button', class: 'cf-btn', 'data-cf': 'exit' }, 'Exit');
    els.smaller = el('button', { type: 'button', class: 'cf-btn', 'data-cf': 'smaller', 'aria-label': 'Smaller text' }, 'A-');
    els.bigger = el('button', { type: 'button', class: 'cf-btn', 'data-cf': 'bigger', 'aria-label': 'Bigger text' }, 'A+');
    bar.appendChild(els.exit);
    bar.appendChild(el('span', { class: 'cf-gap' }));
    if (canSpeak) {
      els.speak = el('button', { type: 'button', class: 'cf-btn', 'data-cf': 'speak', 'aria-pressed': 'false' }, 'Read it to me');
      bar.appendChild(els.speak);
    }
    bar.appendChild(els.smaller); bar.appendChild(els.bigger);
    els.scroll = el('div', { class: 'cf-scroll' });
    var nav = el('div', { class: 'cf-nav' });
    els.prev = el('button', { type: 'button', class: 'cf-btn', 'data-cf': 'prev' }, 'Back');
    els.next = el('button', { type: 'button', class: 'cf-btn', 'data-cf': 'next' }, 'Next story');
    var status = el('p', { class: 'cf-status' });
    els.awake = el('span', { class: 'cf-awake' });
    status.appendChild(els.pos); status.appendChild(els.awake);
    nav.appendChild(els.prev); nav.appendChild(els.next); nav.appendChild(status);
    els.live = el('p', { class: 'visually-hidden', 'aria-live': 'polite' });
    root.appendChild(bar); root.appendChild(els.scroll); root.appendChild(nav); root.appendChild(els.live);
    document.body.appendChild(root);

    root.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-cf]');
      if (!b) return;
      var a = b.getAttribute('data-cf');
      if (a === 'next') go(1);
      else if (a === 'prev') go(-1);
      else if (a === 'smaller') setSize(size - 1);
      else if (a === 'bigger') setSize(size + 1);
      else if (a === 'speak') toggleSpeak();
      else if (a === 'exit') leave();
    });
    var sx = 0, sy = 0, st = 0;
    els.scroll.addEventListener('touchstart', function (ev) {
      if (ev.touches.length !== 1) { st = 0; return; }
      sx = ev.touches[0].clientX; sy = ev.touches[0].clientY; st = Date.now();
    }, { passive: true });
    els.scroll.addEventListener('touchend', function (ev) {
      if (!st) return;
      var t = ev.changedTouches[0], dx = t.clientX - sx, dy = t.clientY - sy;
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5 && Date.now() - st < 800) go(dx < 0 ? 1 : -1);
      st = 0;
    }, { passive: true });
  }

  function setSize(i) {
    size = Math.max(0, Math.min(SIZES.length - 1, i));
    root.style.setProperty('--cf-fs', SIZES[size] + 'rem');
    els.smaller.disabled = size === 0;
    els.bigger.disabled = size === SIZES.length - 1;
    save();
  }

  function message(text) {
    els.scroll.textContent = '';
    els.scroll.appendChild(el('p', { class: 'cf-story cf-msg' }, text));
  }

  function show(announce) {
    var s = stories[order[pos]];
    var art = el('article', { class: 'cf-story', tabindex: '-1', 'aria-labelledby': 'cf-title' });
    art.appendChild(el('p', { class: 'cf-meta' }, s.c + ' · ' + s.p + ' · ' + s.w));
    art.appendChild(el('h2', { id: 'cf-title' }, s.t));
    s.b.forEach(function (p) { art.appendChild(el('p', null, p)); });
    art.appendChild(el('p', { class: 'cf-credit' }, s.cr));
    els.scroll.textContent = '';
    els.scroll.appendChild(art);
    els.scroll.scrollTop = 0;
    els.pos.textContent = 'Story ' + (pos + 1) + ' of ' + order.length;
    els.prev.disabled = pos === 0;
    els.next.textContent = pos === order.length - 1 ? 'Start over' : 'Next story';
    if (announce) els.live.textContent = 'Story ' + (pos + 1) + ' of ' + order.length + ': ' + s.t;
    if (speaking) speak(s);
  }

  function go(d) {
    if (!stories || !stories.length) return;
    if (d > 0 && pos === order.length - 1) { order = shuffle(stories.length); pos = 0; }
    else pos = Math.max(0, Math.min(order.length - 1, pos + d));
    show(true);
  }

  // ---- read it to me: one utterance per paragraph (long ones stall in some browsers) ----
  function speak(s) {
    window.speechSynthesis.cancel();
    [s.t + '.'].concat(s.b).forEach(function (txt) {
      var ut = new SpeechSynthesisUtterance(txt);
      ut.rate = 0.95; ut.lang = 'en';
      window.speechSynthesis.speak(ut);
    });
  }
  function stopSpeaking() {
    if (canSpeak) window.speechSynthesis.cancel();
    speaking = false;
    if (els.speak) els.speak.setAttribute('aria-pressed', 'false');
  }
  function toggleSpeak() {
    if (speaking) { stopSpeaking(); return; }
    speaking = true;
    els.speak.setAttribute('aria-pressed', 'true');
    if (stories && stories.length) speak(stories[order[pos]]);
  }

  // ---- screen wake lock (re-taken when the page comes back into view) ----
  function wake() {
    if (!('wakeLock' in navigator) || !open) return;
    navigator.wakeLock.request('screen').then(function (l) {
      lock = l;
      els.awake.textContent = 'Screen stays on';
      l.addEventListener('release', function () { lock = null; if (open) els.awake.textContent = ''; });
    }).catch(function () { els.awake.textContent = ''; });
  }
  document.addEventListener('visibilitychange', function () {
    if (open && document.visibilityState === 'visible' && !lock) wake();
  });

  function onKey(ev) {
    if (!open || ev.altKey || ev.ctrlKey || ev.metaKey) return;
    var k = ev.key;
    if (k === 'ArrowRight') { ev.preventDefault(); go(1); }
    else if (k === 'ArrowLeft') { ev.preventDefault(); go(-1); }
    else if (k === 'Escape') { ev.preventDefault(); leave(); }
    else if (k === '+' || k === '=') { ev.preventDefault(); setSize(size + 1); }
    else if (k === '-' || k === '_') { ev.preventDefault(); setSize(size - 1); }
    else if (k === 'Tab') {  // keep focus inside the dialog
      var f = root.querySelectorAll('button:not([disabled])');
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (ev.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) { ev.preventDefault(); last.focus(); }
      else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
    }
  }

  function setTheme(c) {
    themeMeta = themeMeta || document.querySelector('meta[name="theme-color"]');
    if (!themeMeta) return;
    if (c) { oldTheme = themeMeta.getAttribute('content'); themeMeta.setAttribute('content', c); }
    else if (oldTheme) themeMeta.setAttribute('content', oldTheme);
  }

  function enter() {
    if (open) return;
    if (!root) build();
    open = true;
    lastFocus = document.activeElement;
    setSize(size);
    document.documentElement.classList.add('cf-open');
    inerted = Array.prototype.filter.call(document.body.children, function (n) { return n !== root && !n.inert; });
    inerted.forEach(function (n) { n.inert = true; });
    root.hidden = false;
    setTheme('#000000');
    try { history.pushState({ cf: 1 }, '', '#campfire'); pushed = true; } catch (e) { pushed = false; }
    if (document.documentElement.requestFullscreen && !document.fullscreenElement) {
      document.documentElement.requestFullscreen({ navigationUI: 'hide' }).catch(function () {});
    }
    wake();
    els.exit.focus();
    if (stories) { order = shuffle(stories.length); pos = 0; show(true); return; }
    message('Getting the stories..');
    fetch(cfg.data).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      stories = (d && d.stories) || [];
      if (!stories.length) throw new Error('empty');
      order = shuffle(stories.length); pos = 0;
      if (open) show(true);
    }).catch(function () {
      message("Couldn't load the stories. Open this page once while you've got signal and try again.");
    });
  }

  function close() {
    if (!open) return;
    open = false;
    stopSpeaking();
    if (lock) { lock.release().catch(function () {}); lock = null; }
    if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(function () {});
    root.hidden = true;
    inerted.forEach(function (n) { n.inert = false; });
    inerted = [];
    document.documentElement.classList.remove('cf-open');
    setTheme('');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  // Exit goes through history so the phone's back button and the Exit button do the same thing.
  function leave() {
    if (pushed && history.state && history.state.cf) history.back(); else close();
  }
  window.addEventListener('popstate', function () { pushed = false; close(); });

  document.addEventListener('keydown', onKey);
  start.addEventListener('click', enter);
})();

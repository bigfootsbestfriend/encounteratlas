// Podcast player: a docked bar with big driving-safe buttons, a queue, lock-screen controls (Media Session API) and
// resume. Works on any page that loads it. Audio streams straight from each show's own enclosure URL (never copied or
// cached by us), and nothing is fetched until someone presses play.
//
// Markup it understands (server-rendered or built later, clicks are delegated):
//   <button data-pp='{"t","s","d","m","a","art","u","sa"}'>  plays that episode, then the rest of its [data-pp-list]
//   <button data-pp-all> inside a [data-pp-list]               plays the whole list in order
// Road trip planner: roadtrip.js fires "ea:route" after it renders the stops; we add a "Listen along" list after them.
(function () {
  if (window.eaPod) return;
  const KEY = 'ea-pod-v1';
  const BACK = 15, FWD = 30, RATES = [1, 1.25, 1.5, 1.75, 2, 0.8];
  const PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.1v13.8a1 1 0 0 0 1.5.86l11-6.9a1 1 0 0 0 0-1.72l-11-6.9A1 1 0 0 0 8 5.1z"/></svg>';
  const PAUSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="4.5" width="4.2" height="15" rx="1.2" fill="currentColor"/><rect x="13.8" y="4.5" width="4.2" height="15" rx="1.2" fill="currentColor"/></svg>';
  const ICON = {
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5V2L7 6l5 4V7a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z" fill="currentColor"/></svg>',
    fwd: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5V2l5 4-5 4V7a6 6 0 1 0 6 6h2a8 8 0 1 1-8-8z" fill="currentColor"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 5.6v12.8a1 1 0 0 0 1.5.86L16 13.1V18a1 1 0 0 0 2 0V6a1 1 0 0 0-2 0v4.9L6.5 4.74A1 1 0 0 0 5 5.6z"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>',
    share: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  };
  const S = { q: [], i: 0, rate: 1, seekTo: 0, dragging: false, lastSave: 0, errorTimer: null };
  let audio = null, bar = null;
  const $ = (sel, root) => (root || document).querySelector(sel);
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const track = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: 'podcast-player', ...p }); } catch (e) { /* no analytics */ } };
  const clock = (s) => {
    if (!isFinite(s) || s < 0) return '0:00';
    s = Math.floor(s);
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = String(s % 60).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${x}` : `${m}:${x}`;
  };
  const cur = () => S.q[S.i];
  const bigArt = (u) => (u || '').replace(/\/\d+x\d+bb\./, '/512x512bb.');

  // ---------- saved state ----------
  function save(force) {
    const now = Date.now();
    if (!force && now - S.lastSave < 5000) return;
    S.lastSave = now;
    try {
      if (!S.q.length) { localStorage.removeItem(KEY); return; }
      localStorage.setItem(KEY, JSON.stringify({ q: S.q.slice(0, 60), i: S.i, pos: audio ? Math.floor(audio.currentTime || S.seekTo || 0) : S.seekTo, rate: S.rate, at: now }));
    } catch (e) { /* storage blocked */ }
  }
  function load() {
    try { const d = JSON.parse(localStorage.getItem(KEY) || 'null'); return d && Array.isArray(d.q) && d.q.length ? d : null; } catch (e) { return null; }
  }

  // ---------- the bar ----------
  function btn(cls, label, html) {
    const b = el('button', 'pp-b ' + cls); b.type = 'button'; b.setAttribute('aria-label', label); b.title = label; b.innerHTML = html; return b;
  }
  function ensureBar() {
    if (bar) return bar;
    bar = el('section', 'pp-bar');
    bar.setAttribute('aria-label', 'Podcast player');
    bar.innerHTML = `<div class="pp-in">
  <div class="pp-top">
    <img class="pp-art" alt="" width="56" height="56" hidden>
    <div class="pp-meta"><p class="pp-title"></p><p class="pp-show"><a class="pp-showlink" rel="noopener" target="_blank"></a><span class="pp-pos"></span></p></div>
  </div>
  <div class="pp-prog"><span class="pp-t0">0:00</span><input class="pp-range" type="range" min="0" max="1000" step="1" value="0" aria-label="Position in episode"><span class="pp-t1">0:00</span></div>
  <div class="pp-ctl"></div>
  <p class="pp-status" aria-live="polite"></p>
  <div class="pp-resume" hidden><button type="button" class="btn pp-resume-go"></button></div>
</div>`;
    const ctl = $('.pp-ctl', bar);
    const back = btn('pp-back', `Back ${BACK} seconds`, ICON.back + `<span class="pp-n">${BACK}</span>`);
    const play = btn('pp-main', 'Play', PLAY);
    const fwd = btn('pp-fwd', `Skip ${FWD} seconds`, ICON.fwd + `<span class="pp-n">${FWD}</span>`);
    const next = btn('pp-next', 'Next episode', ICON.next);
    const rate = btn('pp-rate', 'Playback speed', '1x');
    const close = btn('pp-close', 'Close the player', ICON.close);
    const share = btn('pp-share', 'Save or share this episode', ICON.share);
    share.addEventListener('click', () => cur() && shareSheet(cur()));
    ctl.append(back, play, fwd, next, rate);
    $('.pp-top', bar).append(share, close);
    back.addEventListener('click', () => seekBy(-BACK));
    fwd.addEventListener('click', () => seekBy(FWD));
    play.addEventListener('click', toggle);
    next.addEventListener('click', () => go(S.i + 1, true));
    rate.addEventListener('click', () => setRate(RATES[(RATES.indexOf(S.rate) + 1) % RATES.length]));
    close.addEventListener('click', closeBar);
    const range = $('.pp-range', bar);
    range.addEventListener('input', () => {
      S.dragging = true;
      const d = audio && audio.duration;
      if (isFinite(d)) $('.pp-t0', bar).textContent = clock((range.value / 1000) * d);
    });
    range.addEventListener('change', () => {
      S.dragging = false;
      const d = audio && audio.duration;
      if (isFinite(d)) seekTo((range.value / 1000) * d);
    });
    $('.pp-resume-go', bar).addEventListener('click', () => { showResume(false); go(S.i, true, S.seekTo); });
    document.body.append(bar);
    document.body.classList.add('pp-on');
    return bar;
  }
  function closeBar() {
    if (audio) { audio.pause(); audio.removeAttribute('src'); audio.load(); }
    S.q = []; S.i = 0; save(true);
    if (bar) { bar.remove(); bar = null; }
    document.body.classList.remove('pp-on');
    marks();
    if ('mediaSession' in navigator) { navigator.mediaSession.metadata = null; navigator.mediaSession.playbackState = 'none'; }
  }
  function say(t) { if (bar) $('.pp-status', bar).textContent = t || ''; }
  function showResume(on) {
    if (!bar) return;
    $('.pp-resume', bar).hidden = !on;
    $('.pp-ctl', bar).hidden = on;
    $('.pp-prog', bar).hidden = on;
  }
  function paint() {
    const e = cur();
    if (!bar || !e) return;
    const img = $('.pp-art', bar);
    if (e.art) { img.src = e.art; img.hidden = false; } else img.hidden = true;
    $('.pp-title', bar).textContent = e.t;
    const sl = $('.pp-showlink', bar);
    // show's Apple page: given, or the episode URL without the episode part (/podcast/<slug>/id123?i=456 -> /podcast/id123)
    sl.textContent = e.s; sl.href = e.sa || (e.u || '').replace(/\/podcast\/[^/]+\/(id\d+).*$/, '/podcast/$1') || '#'; sl.title = `${e.s} on Apple Podcasts`;
    $('.pp-pos', bar).textContent = S.q.length > 1 ? ` · ${S.i + 1} of ${S.q.length}` : '';
    $('.pp-next', bar).disabled = S.i >= S.q.length - 1;
    $('.pp-rate', bar).textContent = (S.rate % 1 ? S.rate : S.rate.toFixed(0)) + 'x';
    playing();
    times();
  }
  function playing() {
    const on = !!(audio && !audio.paused);
    if (bar) { const b = $('.pp-main', bar); b.innerHTML = on ? PAUSE : PLAY; b.setAttribute('aria-label', on ? 'Pause' : 'Play'); b.title = on ? 'Pause' : 'Play'; }
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = on ? 'playing' : (S.q.length ? 'paused' : 'none');
    marks();
  }
  function times() {
    if (!bar || !audio) return;
    const t = audio.currentTime || 0, d = audio.duration;
    if (!S.dragging) {
      $('.pp-t0', bar).textContent = clock(t);
      $('.pp-range', bar).value = isFinite(d) && d > 0 ? Math.round((t / d) * 1000) : 0;
    }
    const m = cur() && cur().m;
    $('.pp-t1', bar).textContent = isFinite(d) && d > 0 ? clock(d) : m ? clock(m * 60) : '';
    $('.pp-range', bar).disabled = !(isFinite(d) && d > 0);
  }
  // Episode buttons on the page show which one is playing
  function marks() {
    const e = cur(), on = !!(audio && !audio.paused);
    document.querySelectorAll('[data-pp]').forEach((b) => {
      let a = null; try { a = JSON.parse(b.dataset.pp).a; } catch (x) { /* bad data */ }
      const me = !!(e && a === e.a && bar);
      b.classList.toggle('pp-cur', me);
      b.setAttribute('aria-pressed', String(me && on));
      const svg = b.querySelector('svg');
      if (svg) svg.outerHTML = me && on ? PAUSE : PLAY;
      const lab = b.querySelector('span');
      if (lab && lab.textContent) lab.textContent = me && on ? 'Pause' : 'Play';
    });
    // "Today's listen" dial: turn it to the station that's playing (sideways only, the page itself doesn't move)
    document.querySelectorAll('.pf-dial').forEach((d) => {
      const li = d.querySelector('.pp-cur') && d.querySelector('.pp-cur').closest('li');
      if (!li || d.dataset.at === li.dataset.i) return;
      d.dataset.at = li.dataset.i = li.dataset.i || String([...d.children].indexOf(li));
      const calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
      d.scrollTo({ left: Math.max(0, li.offsetLeft - d.offsetLeft - 16), behavior: calm ? 'auto' : 'smooth' });
    });
  }

  // ---------- audio ----------
  function ensureAudio() {
    if (audio) return audio;
    audio = new Audio();
    audio.preload = 'none';
    audio.addEventListener('play', () => { playing(); say(''); });
    audio.addEventListener('pause', () => { playing(); save(true); });
    audio.addEventListener('waiting', () => say('Loading...'));
    audio.addEventListener('playing', () => say(''));
    audio.addEventListener('timeupdate', () => { times(); save(false); position(); });
    audio.addEventListener('durationchange', times);
    audio.addEventListener('loadedmetadata', () => {
      if (S.seekTo > 0 && (!isFinite(audio.duration) || S.seekTo < audio.duration - 5)) audio.currentTime = S.seekTo;
      S.seekTo = 0;
      audio.playbackRate = S.rate;
      times(); position();
    });
    audio.addEventListener('ended', () => { if (S.i < S.q.length - 1) go(S.i + 1, true); else { say("That's the end of the list."); S.seekTo = 0; save(true); } });
    audio.addEventListener('error', () => {
      if (!audio.getAttribute('src')) return;
      const e = cur();
      track('podcast_error', { show: e ? e.s : '' });
      const more = S.i < S.q.length - 1;
      say(`This episode won't load from ${e ? e.s : 'the show'}'s host right now.${more ? ' Skipping to the next one.' : ''}`);
      clearTimeout(S.errorTimer);
      if (more) S.errorTimer = setTimeout(() => go(S.i + 1, true), 2500);
    });
    if ('mediaSession' in navigator) {
      const ms = navigator.mediaSession, set = (a, f) => { try { ms.setActionHandler(a, f); } catch (e) { /* not supported */ } };
      set('play', () => resume());
      set('pause', () => audio.pause());
      set('stop', () => audio.pause());
      set('seekbackward', (d) => seekBy(-((d && d.seekOffset) || BACK)));
      set('seekforward', (d) => seekBy((d && d.seekOffset) || FWD));
      set('seekto', (d) => { if (d && isFinite(d.seekTime)) { if (d.fastSeek && audio.fastSeek) audio.fastSeek(d.seekTime); else seekTo(d.seekTime); } });
      set('nexttrack', () => go(S.i + 1, true));
      set('previoustrack', () => { if (audio.currentTime > 5 || S.i === 0) seekTo(0); else go(S.i - 1, true); });
    }
    return audio;
  }
  function meta() {
    const e = cur();
    if (!('mediaSession' in navigator) || !e || !window.MediaMetadata) return;
    const art = e.art ? [{ src: e.art, sizes: '160x160', type: 'image/jpeg' }, { src: bigArt(e.art), sizes: '512x512', type: 'image/jpeg' }] : [];
    navigator.mediaSession.metadata = new MediaMetadata({ title: e.t, artist: e.s, album: 'Encounter Atlas: listen along', artwork: art });
  }
  function position() {
    if (!('mediaSession' in navigator) || !navigator.mediaSession.setPositionState || !audio) return;
    const d = audio.duration;
    if (!isFinite(d) || d <= 0) return;
    try { navigator.mediaSession.setPositionState({ duration: d, playbackRate: audio.playbackRate || 1, position: Math.min(audio.currentTime || 0, d) }); } catch (e) { /* bad state */ }
  }
  function go(i, autoplay, at) {
    if (i < 0 || i >= S.q.length) return;
    clearTimeout(S.errorTimer);
    S.i = i;
    const e = cur();
    ensureBar(); showResume(false); ensureAudio();
    S.seekTo = at || 0;
    audio.src = e.a; // only now does the browser touch the show's server
    audio.defaultPlaybackRate = S.rate;
    paint(); meta(); save(true);
    if (autoplay) {
      const p = audio.play();
      if (p && p.catch) p.catch((err) => { if (err && err.name === 'NotAllowedError') say('Press play to start.'); /* load errors are handled by the error event */ playing(); });
      track('podcast_play', { show: e.s });
    }
  }
  function resume() {
    if (!audio || !audio.getAttribute('src')) { go(S.i, true, S.seekTo); return; }
    const p = audio.play();
    if (p && p.catch) p.catch(() => playing());
  }
  function toggle() { if (audio && !audio.paused) audio.pause(); else resume(); }
  function seekTo(t) {
    if (!audio || !audio.getAttribute('src')) { S.seekTo = Math.max(0, t); return; }
    const d = audio.duration;
    audio.currentTime = Math.max(0, isFinite(d) ? Math.min(t, d - 1) : t);
    times(); position(); save(true);
  }
  function seekBy(dt) { if (audio) seekTo((audio.currentTime || 0) + dt); }
  function setRate(r) {
    S.rate = r;
    if (audio) { audio.playbackRate = r; audio.defaultPlaybackRate = r; }
    paint(); position(); save(true);
  }
  function play(queue, i) {
    if (!queue.length) return;
    S.q = queue.filter((e) => e && /^https:\/\//.test(e.a));
    go(Math.max(0, Math.min(i || 0, S.q.length - 1)), true);
  }

  // ---------- save or share an episode (email it to yourself, send it to a friend, copy the link) ----------
  const ORIGIN = 'https://encounteratlas.com';
  function shareLink(e) {
    const base = (document.querySelector('link[rel="canonical"]') || {}).href || location.href;
    if (e.c) return new URL(`/podcasts/creature/${e.c}/`, ORIGIN).href;
    return base.split('#')[0].split('?')[0];
  }
  let sheet = null;
  function shareSheet(e) {
    const link = shareLink(e);
    const line = `${e.t} (${e.s}${e.m ? `, ${e.m} min` : ''})`;
    const body = `${line}\n\nListen on Encounter Atlas: ${link}${e.u ? `\nOr in Apple Podcasts: ${e.u}` : ''}`;
    if (!sheet) {
      sheet = el('dialog', 'pp-sheet');
      sheet.setAttribute('aria-labelledby', 'pp-sheet-h');
      sheet.innerHTML = `<form method="dialog" class="pp-sheet-in"><h2 id="pp-sheet-h">Save or share</h2><p class="pp-sheet-t"></p>
<div class="pp-sh-save"><label for="pp-sh-email">Email it to myself</label>
<div class="pp-sh-row"><input id="pp-sh-email" type="email" autocomplete="email" placeholder="you@example.com" enterkeyhint="send"><button type="button" class="btn pp-sh-mail">Send</button></div>
<input class="pp-sh-hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
<small>We'll email you the link, and sign you up for our free weekly email (strange news, a creature of the week, new reports). Unsubscribe anytime.</small></div>
<button type="button" class="btn pp-sh-share">Send to a friend</button>
<button type="button" class="btn pp-sh-copy">Copy link</button>
<p class="pp-sheet-msg" aria-live="polite"></p><button class="pp-sheet-x" value="close">Close</button></form>`;
      document.body.append(sheet);
      sheet.addEventListener('click', (ev) => { if (ev.target === sheet) sheet.close(); });
    }
    $('.pp-sheet-t', sheet).textContent = line;
    $('.pp-sheet-msg', sheet).textContent = '';
    const mail = $('.pp-sh-mail', sheet), input = $('#pp-sh-email', sheet), msg = $('.pp-sheet-msg', sheet);
    const api = (document.querySelector('meta[name="ea-nl"]') || {}).content;
    try { const saved = localStorage.getItem('ea-nl-email'); if (saved && !input.value) input.value = saved; } catch (x) { /* storage blocked */ }
    const mailto = () => { location.href = `mailto:?subject=${encodeURIComponent('Listen later: ' + e.t)}&body=${encodeURIComponent(body)}`; };
    const send = async () => {
      const email = input.value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) { msg.textContent = 'Type your email address first.'; input.focus(); return; }
      if (!api) { mailto(); return; }
      mail.disabled = true; msg.textContent = 'Sending...';
      try {
        const r = await fetch(api + '/save-episode', { method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ site: 'encounteratlas', email, a: e.a, website: $('.pp-sh-hp', sheet).value }) });
        const d = await r.json().catch(() => ({}));
        if (d.state === 'sent') {
          msg.textContent = 'Sent! Check your inbox. You\'re on the weekly email too.';
          track('podcast_share', { how: 'email', show: e.s });
          try { localStorage.setItem('ea-nl-email', email); localStorage.setItem('nl-subbed', '1'); } catch (x) { /* storage blocked */ }
        } else if (d.state === 'slow') msg.textContent = "That's a lot of saves at once. Try again in a little while.";
        else if (d.state === 'invalid') msg.textContent = "That email address doesn't look right.";
        else { msg.textContent = "Couldn't send it, so we opened your email app instead."; mailto(); }
      } catch (x) { msg.textContent = "Couldn't send it, so we opened your email app instead."; mailto(); }
      mail.disabled = false;
    };
    mail.onclick = send;
    input.onkeydown = (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); send(); } };
    const sh = $('.pp-sh-share', sheet);
    sh.onclick = async () => {
      track('podcast_share', { how: 'share', show: e.s });
      if (navigator.share) {
        try { await navigator.share({ title: e.t, text: `${line}. Thought you'd like this one:`, url: link }); sheet.close(); } catch (x) { /* cancelled */ }
      } else {
        location.href = `mailto:?subject=${encodeURIComponent('You need to hear this: ' + e.t)}&body=${encodeURIComponent(body)}`;
      }
    };
    $('.pp-sh-copy', sheet).onclick = async () => {
      track('podcast_share', { how: 'copy', show: e.s });
      try { await navigator.clipboard.writeText(`${line}\n${link}`); $('.pp-sheet-msg', sheet).textContent = 'Link copied.'; }
      catch (x) { $('.pp-sheet-msg', sheet).textContent = link; }
    };
    if (sheet.showModal) sheet.showModal(); else sheet.setAttribute('open', '');
  }
  document.addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-pp-share]');
    if (!b) return;
    ev.preventDefault();
    const src = b.closest('li, .spin-card, [data-pp-item]');
    const p = src && src.querySelector('[data-pp]');
    try { if (p) shareSheet(JSON.parse(p.dataset.pp)); } catch (x) { /* bad data */ }
  });

  // ---------- clicks on episode buttons ----------
  const parse = (b) => { try { return JSON.parse(b.dataset.pp); } catch (e) { return null; } };
  document.addEventListener('click', (ev) => {
    const one = ev.target.closest('[data-pp]'), all = ev.target.closest('[data-pp-all]');
    if (!one && !all) return;
    ev.preventDefault();
    const list = (one || all).closest('[data-pp-list]');
    const btns = list ? [...list.querySelectorAll('[data-pp]')] : [one];
    const q = btns.map(parse).filter(Boolean);
    if (all) { play(q, 0); track('podcast_play_all', { n: q.length }); return; }
    const e = parse(one);
    if (!e) return;
    if (cur() && cur().a === e.a && bar) { toggle(); return; } // same episode: play/pause
    play(q, Math.max(0, q.findIndex((x) => x.a === e.a)));
  });

  // ---------- road trip planner: "Listen along" after the stops ----------
  let playP = null, namesP = null;
  const PER = 3;
  document.addEventListener('ea:route', async (ev) => {
    const { after, stops } = ev.detail || {};
    if (!after) return;
    const order = [], first = {};
    for (const s of stops || []) if ((s.k === 'place' || s.k === 'case') && s.c && !(s.c in first)) { first[s.c] = s.t; order.push(s.c); }
    if (!order.length) return;
    const cfg = document.getElementById('rt-config');
    const cfgD = cfg ? JSON.parse(cfg.textContent) : {};
    const base = (cfgD.data || '/data/roadtrip.json').replace(/roadtrip\.json$/, '');
    playP = playP || fetch(base + 'podcast-play.json').then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
    namesP = namesP || (cfgD.data ? fetch(cfgD.data).then((r) => r.json()).then((d) => d.cards || {}).catch(() => ({})) : Promise.resolve({}));
    const [pl, cards] = await Promise.all([playP, namesP]);
    if (!after.isConnected) return; // re-rendered meanwhile
    const slugs = order.filter((c) => pl[c] && pl[c].length);
    if (!slugs.length) return;
    const sec = el('section', 'pp-along'); sec.setAttribute('data-pp-list', ''); sec.setAttribute('aria-labelledby', 'pp-along-h');
    const h = el('h2', '', 'Listen along'); h.id = 'pp-along-h';
    const n = slugs.reduce((a, c) => a + Math.min(PER, pl[c].length), 0);
    const all = el('button', 'btn pp-all'); all.type = 'button'; all.setAttribute('data-pp-all', ''); all.innerHTML = PLAY + ` Play all ${n} in route order`;
    const pAll = el('p'); pAll.append(all);
    sec.append(h, el('p', '', "Podcast episodes about the creatures you'll pass, in the order you'll pass them. Start it before you pull out and it keeps going with your screen off, with big buttons so you never have to type anything. Episodes stream straight from each show, so the people who make them get the listen."), pAll);
    const ol = el('ol', 'pp-stops');
    for (const c of slugs) {
      const li = el('li', 'pp-stop'), h3 = el('h3'), a = el('a', '', (cards[c] && cards[c].n) || c);
      a.href = (cfgD.cards || '/cards/').replace(/\/cards\/$/, '') + '/podcasts/creature/' + c + '/'; h3.append(a);
      li.append(h3, el('p', 'pp-near', 'First spot on the road: ' + first[c]));
      const eps = el('ol', 'pp-eps');
      for (const e of pl[c].slice(0, PER)) {
        const it = el('li', 'pp-ep');
        const b = el('button', 'pp-btn pp-round'); b.type = 'button'; b.dataset.pp = JSON.stringify(e); b.setAttribute('aria-label', 'Play ' + e.t); b.innerHTML = PLAY;
        const t = el('span', 'pp-ep-t'), sm = el('small'), sa = el('a', '', e.s);
        sa.href = e.u; sa.rel = 'noopener'; sa.target = '_blank';
        const bits = [e.d ? new Date(e.d + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '', e.m ? e.m + ' min' : ''].filter(Boolean);
        sm.append(sa, bits.length ? ' · ' + bits.join(' · ') : '');
        t.append(el('b', '', e.t), sm);
        it.append(b, t); eps.append(it);
      }
      li.append(eps); ol.append(li);
    }
    sec.append(ol);
    after.after(sec);
    marks();
  });

  // ---------- resume offer (never autoplays) ----------
  window.addEventListener('pagehide', () => save(true));
  const saved = load();
  if (saved) {
    S.q = saved.q; S.i = Math.min(saved.i || 0, saved.q.length - 1); S.rate = RATES.includes(saved.rate) ? saved.rate : 1; S.seekTo = saved.pos || 0;
    const start = () => {
      ensureBar(); paint(); showResume(true);
      $('.pp-resume-go', bar).innerHTML = PLAY + ` Resume${S.seekTo > 5 ? ' at ' + clock(S.seekTo) : ''}`;
    };
    if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  }

  // ---------- "Today's listen" (home page, app home) ----------
  // After dark it's "Tonight's listen", by the visitor's own clock.
  const when = () => {
    const h = new Date().getHours();
    if (h >= 18 || h < 5) document.querySelectorAll('[data-pf-when]').forEach((x) => { x.textContent = "Tonight's listen"; });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', when); else when();
  // A tiny buzz on play in the app (Android WebView), so the big button feels like a button
  document.addEventListener('click', (ev) => {
    if (!document.documentElement.classList.contains('in-app') || !ev.target.closest('[data-pp],[data-pp-all]')) return;
    try { if (navigator.vibrate) navigator.vibrate(8); } catch (e) { /* not allowed */ }
  });

  window.eaPod = { play, toggle, close: closeBar };
})();

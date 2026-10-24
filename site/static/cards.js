// Collector cards: the collection lives in localStorage ('ea-cards': {slug: {t: ISO date, at: spot name}}), no account.
// window.eaCards: collected(), checkIn() (asks for location once, collects every card with a spot within checkin_km),
// mark(), message(), load(), button(), reveal(got).
// On /cards/ it also flips the trading cards, runs the light on the card you're pointing at (or tilting, on phones),
// filters the grid, counts the collection and shows the nearest spot when we already know roughly where you are.
(function () {
  const KEY = 'ea-cards', LOC = 'ea-cards-loc';
  // Face-down artwork for the reveal: fetched before the card flies in so it never shows up blank
  const REV = ((document.currentScript && document.currentScript.src) || '/static/cards.js').replace(/cards\.js(\?.*)?$/, 'cards/reverse.webp');
  const revArt = () => { const im = new Image(); im.src = REV; return im.decode().catch(() => {}); };
  const cfgEl = document.getElementById('cc-config') || document.getElementById('rt-config');
  const cfg = cfgEl ? JSON.parse(cfgEl.textContent) : {};
  const dataUrl = cfg.data || '/data/roadtrip.json';
  const cardsUrl = cfg.cards || dataUrl.replace(/roadtrip\.json$/, 'cards.json');
  let dataP = null, infoP = null;
  const load = () => dataP || (dataP = fetch(dataUrl).then((r) => r.json()));
  const loadInfo = () => infoP || (infoP = fetch(cardsUrl).then((r) => { if (!r.ok) throw new Error('cards ' + r.status); return r.json(); }));
  const ls = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || 'null') || d; } catch (e) { return d; } };
  const collected = () => ls(KEY, {});
  const save = (c) => { try { localStorage.setItem(KEY, JSON.stringify(c)); } catch (e) { /* storage full or blocked */ } };
  const reduced = () => window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fmtDate = (iso) => { try { return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); } catch (e) { return ''; } };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  function hav(a1, o1, a2, o2) {
    const r = Math.PI / 180, h = Math.sin(((a2 - a1) * r) / 2) ** 2 + Math.cos(a1 * r) * Math.cos(a2 * r) * Math.sin(((o2 - o1) * r) / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
  }
  // Where we last knew the visitor was: our own check-in, else the near-me page's saved spot. Rounded, stays on the device.
  function lastLoc() {
    const a = ls(LOC, null);
    if (a && isFinite(a.lat)) return [a.lat, a.lon];
    const n = ls('ea-near', null);
    if (n && isFinite(n.lat) && isFinite(n.lng)) return [n.lat, n.lng];
    return null;
  }
  function where() {
    return new Promise((res, rej) => {
      if (!navigator.geolocation) { rej(new Error('nogeo')); return; }
      navigator.geolocation.getCurrentPosition((p) => res([p.coords.latitude, p.coords.longitude]), rej, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
    });
  }
  // Returns {got: [{slug, name, at}], nearest: {name, at, km} | null}
  async function checkIn() {
    const [lat, lon] = await where();
    try { localStorage.setItem(LOC, JSON.stringify({ lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100 })); } catch (e) { /* blocked */ }
    const d = await load(), mine = collected(), got = [];
    let nearest = null;
    for (const [slug, c] of Object.entries(d.cards)) {
      for (const [a, o, label] of c.spots) {
        const km = hav(lat, lon, a, o);
        if (km <= d.checkin_km) {
          if (!mine[slug]) { mine[slug] = { t: new Date().toISOString(), at: label }; got.push({ slug, name: c.n, at: label }); }
          break;
        }
        if (!mine[slug] && (!nearest || km < nearest.km)) nearest = { name: c.n, at: label, km };
      }
    }
    save(mine);
    try { if (window.gtag) window.gtag('event', 'card_checkin', { page_type: location.pathname.split('/')[1] || 'home', cards: got.length }); } catch (e) { /* no analytics */ }
    return { got, nearest };
  }

  function mark(root) {
    const mine = collected();
    (root || document).querySelectorAll('[data-card]').forEach((li) => {
      const m = mine[li.dataset.card], has = !!m;
      li.classList.toggle('cc-have', has);
      li.classList.toggle('tc-have', has);
      const g = li.querySelector('.cc-got');
      if (g) { g.hidden = !has; if (has) g.textContent = 'Collected' + (m.at ? ' at ' + m.at : ''); }
      const tg = li.querySelector('.tc-got');
      if (tg) {
        if (!tg.dataset.def) tg.dataset.def = tg.textContent;
        tg.textContent = has ? fmtDate(m.t) : tg.dataset.def;
        tg.title = has ? 'Collected ' + fmtDate(m.t) + (m.at ? ' at ' + m.at : '') : '';
      }
    });
    document.querySelectorAll('.cc-huntbox').forEach((box) => {
      const all = box.querySelectorAll('[data-card]');
      const n = [...all].filter((li) => mine[li.dataset.card]).length;
      const p = box.querySelector('.cc-prog');
      if (p) p.textContent = `${n} of ${all.length} collected`;
    });
    const grid = document.getElementById('tc-all');
    document.querySelectorAll('[data-tally]').forEach((b) => {
      b.textContent = grid ? grid.querySelectorAll(`.tc-have[data-r="${b.dataset.tally}"]`).length : 0;
    });
    const tot = document.getElementById('cc-total');
    if (tot) {
      const all = new Set([...document.querySelectorAll('[data-card]')].map((x) => x.dataset.card)), n = Object.keys(mine).filter((s) => all.has(s)).length;
      tot.hidden = !n;
      tot.textContent = `You've collected ${n} of ${all.size} cards.`;
    }
    if (grid) filter();
  }
  function message(res) {
    if (res.got.length) return `Got ${res.got.length === 1 ? 'a card' : res.got.length + ' cards'}: ${res.got.map((g) => g.name + ' (' + g.at + ')').join(', ')}.`;
    if (res.nearest) {
      const km = Math.round(res.nearest.km);
      const mi = Math.round(res.nearest.km / 1.609344);
      return `No new cards right here. The closest one you don't have is ${res.nearest.name}, at ${res.nearest.at}, about ${km.toLocaleString()} km (${mi.toLocaleString()} mi) away.`;
    }
    return 'No new cards here, and you already have every card. Seriously impressive.';
  }
  async function button(btn, statusEl) {
    btn.addEventListener('click', async () => {
      statusEl.textContent = 'Checking where you are...';
      btn.disabled = true;
      let res = null;
      try { res = await checkIn(); statusEl.textContent = message(res); mark(); nearest(); } catch (e) {
        statusEl.textContent = e && e.code === 1 ? 'Location is blocked for this site. Allow it in your browser or app settings to collect cards.'
          : "Couldn't get your location. Try again outside or with location turned on.";
      }
      btn.disabled = false;
      if (res && res.got.length) reveal(res.got, btn);
    });
  }

  // ---------- reveal: a new card flies in face down and turns over ----------
  const RANK = { Common: ['common', '●'], Uncommon: ['uncommon', '◆'], Unique: ['unique', '★'] };
  function frontHTML(slug, d, info, when) {
    const [rk, mk] = RANK[d.r] || RANK.Common;
    const no = `#${String(d.no).padStart(3, '0')} / ${info.total}`;
    const n = d.spots.length;
    return `<div class="tc-face tc-front"><div class="tc-name"><h3><span class="tc-nm">${esc(d.n)}</span></h3><span class="tc-mark" aria-hidden="true">${mk}</span></div>
<div class="tc-win">${d.art ? `<img src="${esc(d.art)}" alt="" width="240" height="240">` : ''}<span class="tc-holo" aria-hidden="true"></span></div>
<div class="tc-strip"><span class="tc-kind">${esc(d.k)}</span><span class="tc-no">${no}</span></div>
<p class="tc-sum">${esc(d.s)}</p><p class="tc-foot"><span class="tc-r">${esc(d.r)}</span><span class="tc-got">${when ? fmtDate(when) : `${n} place${n === 1 ? "" : "s"}`}</span></p>
<span class="tc-fx" aria-hidden="true"></span></div>`;
  }
  let revealing = false;
  async function reveal(got, returnFocus) {
    if (revealing || !got || !got.length) return;
    let info;
    try { [info] = await Promise.all([loadInfo(), revArt()]); } catch (e) { return; }
    revealing = true;
    const prevFocus = returnFocus || document.activeElement;
    const hunt = new Set(info.hunt || []);
    const ov = document.createElement('div');
    ov.className = 'tc-rv';
    ov.setAttribute('role', 'dialog');
    ov.setAttribute('aria-modal', 'true');
    ov.setAttribute('aria-labelledby', 'tc-rv-t');
    document.body.appendChild(ov);
    const prevOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    let i = 0, timers = [];
    const close = () => {
      timers.forEach(clearTimeout);
      ov.remove();
      document.documentElement.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKey, true);
      revealing = false;
      if (prevFocus && prevFocus.focus) prevFocus.focus();
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      else if (e.key === 'Tab') { // keep focus inside the dialog
        const f = [...ov.querySelectorAll('a[href], button')];
        if (!f.length) return;
        const a = f[0], z = f[f.length - 1];
        if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
      }
    };
    document.addEventListener('keydown', onKey, true);
    const show = () => {
      timers.forEach(clearTimeout); timers = [];
      const g = got[i], d = info.cards[g.slug];
      if (!d) { if (++i < got.length) show(); else close(); return; }
      const rk = (RANK[d.r] || RANK.Common)[0], still = reduced();
      const more = i < got.length - 1;
      ov.className = 'tc-rv';
      ov.innerHTML = `<div class="tc-rv-stage"><span class="tc-burst" aria-hidden="true"></span>
<div class="tc tc-rvcard tc-have tc-${rk} cat-${esc(d.c)}${hunt.has(g.slug) ? ' tc-hunt' : ''}${still ? '' : ' is-flip'}"><div class="tc-card"><div class="tc-tilt"><div class="tc-in">
${frontHTML(g.slug, d, info, (collected()[g.slug] || {}).t || new Date().toISOString())}<div class="tc-face tc-rev" aria-hidden="true"></div>
</div></div></div></div></div>
<p class="tc-rv-t" id="tc-rv-t">${got.length > 1 ? `New card ${i + 1} of ${got.length}` : 'New card!'}</p>
<p class="tc-rv-s">${esc(d.n)}, ${esc(d.r)}${g.at ? `. Collected at ${esc(g.at)}` : ''}.</p>
<p class="tc-rv-b">${more ? '<button type="button" class="btn" data-rv="next">Next card</button>' : ''}<a class="btn btn-ghost" href="${esc(d.u)}">Read the file</a><button type="button" class="btn${more ? ' btn-ghost' : ''}" data-rv="close">${more ? 'Skip' : 'Nice'}</button></p>`;
      const card = ov.querySelector('.tc-rvcard');
      const done = () => { ov.classList.add('is-shown'); (ov.querySelector('[data-rv="next"]') || ov.querySelector('[data-rv="close"]')).focus(); };
      if (still) { done(); return; }
      timers.push(setTimeout(() => card.classList.remove('is-flip'), 950));
      timers.push(setTimeout(() => { if (rk === 'unique') { ov.classList.add('is-burst'); card.classList.add('is-live'); } done(); }, 1750));
      ov.querySelector('[data-rv="close"]').focus({ preventScroll: true });
    };
    ov.addEventListener('click', (e) => {
      const b = e.target.closest('[data-rv]');
      if (b) { if (b.dataset.rv === 'next') { i++; show(); } else close(); }
      else if (e.target === ov) close();
    });
    show();
  }

  window.eaCards = { collected, checkIn, mark, message, load, button, reveal };

  // ---------- /cards/ page: flip, light, filters, nearest spot ----------
  const grid = document.getElementById('tc-all');
  let filter = () => {};
  if (grid) {
    const wraps = [...document.querySelectorAll('.tc-grid')];
    const btns = [...document.querySelectorAll('.tc-filters [data-f]')];
    const shown = document.getElementById('tc-shown'), empty = document.getElementById('tc-empty');
    let mode = 'all';
    filter = () => {
      let n = 0;
      grid.querySelectorAll('.tc').forEach((li) => {
        const ok = mode === 'all' || (mode === 'have' && li.classList.contains('tc-have')) || (mode === 'unique' && li.dataset.r === 'unique') || (mode === 'hunt' && li.classList.contains('tc-hunt'));
        li.hidden = !ok;
        if (ok) n++;
      });
      if (empty) empty.hidden = !(mode === 'have' && !n);
      if (shown) shown.textContent = mode === 'all' ? '' : `Showing ${n} card${n === 1 ? '' : 's'}.`;
    };
    btns.forEach((b) => b.addEventListener('click', () => {
      mode = b.dataset.f;
      btns.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      filter();
    }));

    // flip
    wraps.forEach((w) => w.addEventListener('click', (e) => {
      const b = e.target.closest('.tc-flip');
      if (!b) return;
      const li = b.closest('.tc'), on = !li.classList.contains('is-flip');
      li.classList.toggle('is-flip', on);
      b.setAttribute('aria-pressed', String(on));
    }));

    // light under the pointer (mouse and pen): only the card you're over gets updated, once per frame
    let act = null, rect = null, pend = null, raf = 0;
    const setVars = (li, px, py) => {
      li.style.setProperty('--px', px.toFixed(3));
      li.style.setProperty('--py', py.toFixed(3));
      li.style.setProperty('--ry', ((px - 0.5) * 16).toFixed(2) + 'deg');
      li.style.setProperty('--rx', ((0.5 - py) * 16).toFixed(2) + 'deg');
    };
    const clearVars = (li) => { ['--px', '--py', '--rx', '--ry'].forEach((p) => li.style.removeProperty(p)); li.classList.remove('is-act', 'is-live'); };
    const frame = () => {
      raf = 0;
      if (!act || !pend) return;
      setVars(act, Math.min(1, Math.max(0, (pend[0] - rect.left) / rect.width)), Math.min(1, Math.max(0, (pend[1] - rect.top) / rect.height)));
    };
    wraps.forEach((w) => {
      w.addEventListener('pointerover', (e) => {
        if (e.pointerType === 'touch' || reduced()) return;
        const b = e.target.closest('.tc-flip');
        if (!b) return;
        const li = b.closest('.tc');
        if (act === li) return;
        if (act) clearVars(act);
        act = li; rect = b.getBoundingClientRect();
        li.classList.add('is-act');
      });
      w.addEventListener('pointermove', (e) => {
        if (!act || e.pointerType === 'touch') return;
        pend = [e.clientX, e.clientY];
        if (!raf) raf = requestAnimationFrame(frame);
      }, { passive: true });
      w.addEventListener('pointerout', (e) => {
        if (!act) return;
        const to = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('.tc');
        if (to === act) return;
        clearVars(act); act = null; pend = null;
      });
    });
    window.addEventListener('scroll', () => { if (act) rect = act.querySelector('.tc-flip').getBoundingClientRect(); }, { passive: true });

    // Phones: the Unique card nearest the middle of the screen is the live one (shine band), and once you've
    // tapped (Android) or allowed motion (iOS) it follows the phone's tilt. Cards off screen never animate.
    const coarse = window.matchMedia && matchMedia('(hover: none)').matches;
    if (coarse && !reduced() && 'IntersectionObserver' in window) {
      const vis = new Set();
      let live = null, tilt = null, traf = 0;
      const pick = () => {
        let best = null, bd = Infinity;
        const mid = innerHeight / 2;
        vis.forEach((li) => {
          if (li.hidden || li.classList.contains('is-flip')) return;
          const r = li.getBoundingClientRect(), d = Math.abs(r.top + r.height / 2 - mid);
          if (d < bd) { bd = d; best = li; }
        });
        if (best !== live) {
          if (live) clearVars(live);
          live = best;
          if (live) live.classList.add('is-live');
        }
      };
      const io = new IntersectionObserver((ents) => {
        ents.forEach((en) => (en.isIntersecting ? vis.add(en.target) : vis.delete(en.target)));
        pick();
      }, { threshold: [0, 0.6] });
      document.querySelectorAll('.tc-grid .tc-unique').forEach((li) => io.observe(li));
      let st = 0;
      window.addEventListener('scroll', () => { if (!st) st = requestAnimationFrame(() => { st = 0; pick(); }); }, { passive: true });
      const onTilt = (e) => {
        if (e.beta == null) return;
        tilt = [e.beta, e.gamma];
        if (!traf) traf = requestAnimationFrame(() => {
          traf = 0;
          if (!live || !tilt) return;
          const px = Math.min(1, Math.max(0, (tilt[1] + 25) / 50)), py = Math.min(1, Math.max(0, (tilt[0] - 15) / 50));
          live.classList.add('is-act');
          setVars(live, px, py);
        });
      };
      let tiltOn = false;
      const tbtn = document.querySelector('.tc-tiltbtn');
      const startTilt = () => { if (tiltOn) return; tiltOn = true; addEventListener('deviceorientation', onTilt, { passive: true }); if (tbtn) tbtn.setAttribute('aria-pressed', 'true'); };
      const stopTilt = () => { tiltOn = false; removeEventListener('deviceorientation', onTilt); if (live) { clearVars(live); live.classList.add('is-live'); } if (tbtn) tbtn.setAttribute('aria-pressed', 'false'); };
      const DOE = window.DeviceOrientationEvent;
      if (DOE && typeof DOE.requestPermission === 'function') {
        // iOS asks first, and only from a tap, so it gets its own button
        if (tbtn) {
          tbtn.hidden = false;
          tbtn.addEventListener('click', async () => {
            if (tiltOn) { stopTilt(); return; }
            try { if ((await DOE.requestPermission()) === 'granted') startTilt(); } catch (e) { tbtn.hidden = true; }
          });
        }
      } else if (DOE) {
        wraps.forEach((w) => w.addEventListener('pointerdown', startTilt, { once: true, passive: true }));
        if (tbtn) { tbtn.hidden = false; tbtn.addEventListener('click', () => (tiltOn ? stopTilt() : startTilt())); }
      }
    }

    // nearest spot on each card's back, if we already know roughly where the visitor is (no new location prompt)
    const ric = window.requestIdleCallback || ((f) => setTimeout(f, 600));
    if (lastLoc()) ric(() => nearest());
  }
  function nearest() {
    const at = lastLoc();
    if (!at || !document.querySelector('.tc-near')) return;
    loadInfo().then((info) => {
      const imperial = /^en-US\b/.test(navigator.language || '');
      document.querySelectorAll('.tc[data-card]').forEach((li) => {
        const d = info.cards[li.dataset.card], p = li.querySelector('.tc-near');
        if (!d || !p || !d.spots.length) return;
        let best = null;
        for (const s of d.spots) { const km = hav(at[0], at[1], s[0], s[1]); if (!best || km < best[1]) best = [s[2], km]; }
        const km = Math.round(best[1]), mi = Math.round(best[1] / 1.609344);
        const dist = imperial ? `${mi.toLocaleString()} mi (${km.toLocaleString()} km)` : `${km.toLocaleString()} km (${mi.toLocaleString()} mi)`;
        p.textContent = best[1] <= info.checkin_km ? `Closest: ${best[0]}, right around you` : `Closest: ${best[0]}, about ${dist} away`;
        p.hidden = false;
        li.querySelectorAll('.tc-spots li').forEach((x) => x.classList.toggle('tc-dup', x.textContent === best[0]));
      });
    }).catch(() => { /* offline: the listed spots are still there */ });
  }

  mark();
  const here = document.getElementById('cc-here');
  if (here) button(here, document.getElementById('cc-status'));
})();

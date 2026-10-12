// Encounter Atlas client core + "Real or hoax?" voting + the /reports/ pages.
// EA (window.EA): API calls, email sign-in session, Turnstile, creature badges, a small map helper.
// Views on /reports/: list (default), ?id=<report>, ?me=1 (your reports), ?signin=<link token>.
// Everything user-supplied is put on the page with textContent, never innerHTML.
(function () {
  const cfgEl = document.getElementById('ea-config');
  if (!cfgEl) return;
  const cfg = JSON.parse(cfgEl.textContent);
  const meta = JSON.parse((document.getElementById('ea-creatures') || {}).textContent || '{"creatures":{},"cats":{}}');
  const API = cfg.api, BASE = cfg.base || '';

  const store = {
    get(k, s = localStorage) { try { return s.getItem(k); } catch (e) { return null; } },
    set(k, v, s = localStorage) { try { s.setItem(k, v); } catch (e) { /* private mode */ } },
    del(k, s = localStorage) { try { s.removeItem(k); } catch (e) { /* private mode */ } },
  };

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : String(kid));
    return el;
  }

  const session = () => store.get('ea-session');
  const user = () => { try { return JSON.parse(store.get('ea-user') || 'null'); } catch (e) { return null; } };
  function signOut() { store.del('ea-session'); store.del('ea-user'); store.del('ea-pass', sessionStorage); }

  async function api(path, { method = 'GET', body, form, auth = true } = {}) {
    const headers = {};
    if (auth && session()) headers.authorization = 'Bearer ' + session();
    let payload;
    if (form) payload = form;
    else if (body !== undefined) { payload = JSON.stringify(body); headers['content-type'] = 'application/json'; }
    let res;
    try {
      res = await fetch(API + path, { method, headers, body: payload });
    } catch (e) {
      return { status: 0, data: { state: 'offline' } };
    }
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && session()) signOut();
    return { status: res.status, data };
  }

  // Turnstile: renders a widget into `slot` (once) and resolves with a token. Tokens are single use,
  // so callers call reset(slot) after spending one.
  const widgets = new WeakMap();
  function turnstileReady() {
    return new Promise((resolve, reject) => {
      let n = 0;
      (function wait() {
        if (window.turnstile) return resolve(window.turnstile);
        if (++n > 100) return reject(new Error('turnstile'));
        setTimeout(wait, 100);
      })();
    });
  }
  async function human(slot) {
    const ts = await turnstileReady();
    const w = widgets.get(slot);
    if (w) {
      const t = ts.getResponse(w.id);
      if (t) return t;
      return new Promise((resolve) => { w.waiters.push(resolve); });
    }
    return new Promise((resolve) => {
      const rec = { waiters: [resolve] };
      widgets.set(slot, rec);
      rec.id = ts.render(slot, {
        sitekey: cfg.sitekey, size: 'flexible', theme: 'light',
        callback: (token) => { const ws = rec.waiters.splice(0); ws.forEach((f) => f(token)); },
      });
    });
  }
  function resetHuman(slot) {
    const w = widgets.get(slot);
    if (w && window.turnstile) window.turnstile.reset(w.id);
  }

  function creature(slug, other) {
    const c = meta.creatures[slug];
    if (c) return { name: c.n, cat: c.c, icon: c.i, slug };
    return { name: other ? other : 'Something else', cat: 'other', icon: null, slug: 'other' };
  }
  function badge(slug, size = 'sm', other) {
    const c = creature(slug, other);
    const b = h('span', { class: `badge badge-${size} cat-${c.cat}` });
    if (c.icon) b.append(h('span', { class: 'mico', 'aria-hidden': 'true', style: `--i:url("${BASE}/static/icons/${c.icon}.svg")` }));
    else b.append(h('span', { class: 'q', 'aria-hidden': 'true', text: '?' }));
    return b;
  }
  function title(r) {
    const c = creature(r.creature, r.other_what);
    const what = r.creature === 'other' ? r.other_what || 'Something strange' : c.name;
    if (!r.place) return `${what} encounter`;
    // "Near Index, WA" / "Outside Asheville" already say where: don't write "near Near Index".
    if (/^(near|outside|by|at|in|around|off|on|above|over)\s/i.test(r.place)) return `${what} ${r.place[0].toLowerCase()}${r.place.slice(1)}`;
    return `${what} near ${r.place}`;
  }
  function fmtDate(d, t, approx) {
    if (!d) return '';
    const [y, m, day] = d.split('-').map(Number);
    let s = new Date(Date.UTC(y, m - 1, day)).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
    if (approx) s = 'Around ' + s;
    if (t) {
      const [hh, mm] = t.split(':').map(Number);
      s += ', ' + new Date(Date.UTC(2000, 0, 1, hh, mm)).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', timeZone: 'UTC' });
    }
    return s;
  }
  const page = (q = '') => `${BASE}/reports/${q}`;

  // ---------- map (same dark, forest-tinted look as the main map) ----------
  const CAT_COLORS = { hominid: '#D9A05B', canid: '#D0633F', winged: '#B98ACB', aquatic: '#4FB3A9', entity: '#9CC46B', ufo: '#8E8CF0', other: '#E0C36A' };
  function makeMap(el, opts = {}) {
    if (!window.maplibregl) return null;
    const map = new maplibregl.Map({
      container: el, style: 'https://tiles.openfreemap.org/styles/dark', center: opts.center || [-98, 41],
      zoom: opts.zoom || (window.innerWidth < 720 ? 2.4 : 3), minZoom: 1.5, maxZoom: opts.maxZoom || 15,
      attributionControl: { compact: true }, cooperativeGestures: !!opts.cooperative,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.on('load', () => {
      // Start with the attribution collapsed to its (i) button so it doesn't cover small maps.
      el.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
      for (const layer of map.getStyle().layers) {
        try {
          if (layer.type === 'background') map.setPaintProperty(layer.id, 'background-color', '#0F1F19');
          else if (/water/.test(layer.id) && layer.type === 'fill') map.setPaintProperty(layer.id, 'fill-color', '#0A1714');
          else if (/landcover|park|wood|forest|grass/.test(layer.id) && layer.type === 'fill') map.setPaintProperty(layer.id, 'fill-color', '#16302A');
          else if (layer.type === 'symbol' && /place|label/.test(layer.id)) {
            map.setPaintProperty(layer.id, 'text-color', '#A9B98F');
            map.setPaintProperty(layer.id, 'text-halo-color', '#0F1F19');
          }
        } catch (e) { /* layer without that paint property */ }
      }
    });
    return map;
  }
  // A polygon circle (km) for "it was somewhere in here".
  function circle(lon, lat, km, n = 48) {
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * 2 * Math.PI;
      pts.push([lon + (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.cos(a), lat + (km / 110.57) * Math.sin(a)]);
    }
    return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [pts] }, properties: {} };
  }
  function areaLayer(map, id, lon, lat, km) {
    const data = { type: 'FeatureCollection', features: [circle(lon, lat, km)] };
    if (map.getSource(id)) { map.getSource(id).setData(data); return; }
    map.addSource(id, { type: 'geojson', data });
    map.addLayer({ id: id + '-f', type: 'fill', source: id, paint: { 'fill-color': '#F2B33D', 'fill-opacity': 0.18 } });
    map.addLayer({ id: id + '-l', type: 'line', source: id, paint: { 'line-color': '#F2B33D', 'line-width': 2, 'line-dasharray': [2, 2] } });
  }

  // ---------- sign-in ----------
  function signinBox(opts = {}) {
    const slot = h('div', { class: 'ts-slot' });
    const msg = h('p', { class: 'form-msg', role: 'status', 'aria-live': 'polite' });
    const input = h('input', { type: 'email', required: true, autocomplete: 'email', inputmode: 'email', placeholder: 'you@example.com', id: 'si-' + Math.random().toString(36).slice(2, 8) });
    const btn = h('button', { class: 'btn', type: 'submit', text: 'Email me a sign-in link' });
    const form = h('form', { class: 'signin', novalidate: true },
      h('p', { class: 'signin-h', text: opts.title || 'Sign in to vote' }),
      h('p', { class: 'hint', text: 'No password. We email you a link that signs you in on this device.' }),
      h('label', { class: 'visually-hidden', for: input.id, text: 'Email' }), h('div', { class: 'signin-row' }, input, btn), slot, msg);
    human(slot).catch(() => { msg.textContent = 'The spam check did not load. Check your connection and reload the page.'; });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!input.value.includes('@')) { msg.textContent = 'Enter your email address.'; return; }
      btn.disabled = true;
      msg.textContent = 'Sending...';
      let token;
      try { token = await human(slot); } catch (err) { msg.textContent = 'The spam check did not load. Reload and try again.'; btn.disabled = false; return; }
      store.set('ea-return', opts.returnTo || location.href);
      const r = await api('/api/auth/start', { method: 'POST', body: { email: input.value.trim(), turnstile: token, r: opts.r || '' }, auth: false });
      resetHuman(slot);
      btn.disabled = false;
      if (r.status === 200) {
        msg.textContent = `Check ${input.value.trim()} for your sign-in link. It works once, for 30 minutes.`;
        if (r.data.dev_link) msg.append(' ', h('a', { href: r.data.dev_link, text: '(dev: open link)' }));
        form.classList.add('sent');
      } else {
        msg.textContent = { email: 'That email address doesn\'t look right.', slow: 'Too many sign-in emails. Try again in an hour.', turnstile: 'The spam check failed. Try again.', offline: 'No connection. Try again when you have signal.' }[r.data.state] || 'Something went wrong. Try again.';
      }
    });
    return form;
  }

  async function handleSignin(t) {
    const root = document.getElementById('ea-reports');
    if (root) root.querySelector('.band-mist .wrap').replaceChildren(h('p', { class: 'loading', text: 'Signing you in...' }));
    const r = await api('/api/auth/verify', { method: 'POST', body: { t }, auth: false });
    if (r.status === 200) {
      store.set('ea-session', r.data.session);
      store.set('ea-user', JSON.stringify(r.data.user));
      const back = store.get('ea-return');
      store.del('ea-return');
      const sameSite = back && back.startsWith(location.origin) && !back.includes('signin=');
      location.replace(r.data.r ? page('?id=' + r.data.r) : sameSite ? back : page('?me=1'));
      return;
    }
    const why = { used: 'That sign-in link was already used.', expired: 'That sign-in link has expired.' }[r.data.state] || 'That sign-in link didn\'t work.';
    const wrap = root.querySelector('.band-mist .wrap');
    wrap.replaceChildren(h('p', { class: 'lede-dark', text: why + ' Get a new one:' }), signinBox({ title: 'Sign in', returnTo: page('?me=1') }));
  }

  // ---------- voting ----------
  const LABELS = { real: 'Real', hoax: 'Hoax', mis: 'Misidentified' };
  const REASONS = { bear: 'Bear', plane: 'Plane', satellite: 'Satellite', starlink: 'Starlink', balloon: 'Balloon', drone: 'Drone', costume: 'Costume', 'cgi-ai': 'CGI or AI', pareidolia: 'Pareidolia', other: 'Something else' };
  const tallies = new Map();
  const widgetsByItem = new Map();

  async function loadTallies(items) {
    if (!items.length) return;
    const r = await api('/api/votes?items=' + encodeURIComponent(items.join(',')));
    for (const t of (r.data.items || [])) tallies.set(t.item, t);
  }

  function results(t) {
    const box = h('div', { class: 'vote-results' });
    for (const k of ['real', 'hoax', 'mis']) {
      const pct = t.results[k];
      box.append(h('div', { class: `vr vr-${k}` }, h('span', { class: 'vr-l', text: LABELS[k] }),
        h('span', { class: 'vr-bar' }, h('span', { style: `width:${pct}%` })), h('span', { class: 'vr-n', text: Math.round(pct) + '%' })));
    }
    const rs = Object.entries(t.results.reasons || {}).sort((a, b) => b[1] - a[1]);
    if (rs.length) box.append(h('p', { class: 'vr-why', text: 'Misidentified as: ' + rs.map(([k, v]) => `${REASONS[k] || k} ${Math.round(v)}%`).join(', ') }));
    box.append(h('p', { class: 'vr-note', text: `${t.n} votes. Newer accounts count for less. Community opinion, not a verdict.` }));
    return box;
  }

  function voteWidget(item, opts = {}) {
    const el = h('div', { class: 'vote' + (opts.compact ? ' vote-compact' : ''), 'data-item': item });
    widgetsByItem.set(item, el);
    renderVote(el, item, opts);
    return el;
  }

  function renderVote(el, item, opts) {
    const t = tallies.get(item) || { n: 0, threshold: 10, mine: null, frozen: false };
    el.replaceChildren();
    el.append(h('p', { class: 'vote-h' }, h('strong', { text: opts.label || 'Real or hoax?' }),
      h('span', { class: 'vote-sub', text: ' Community opinion, not a verdict.' })));
    if (t.frozen) {
      el.append(h('p', { class: 'vote-msg', text: 'Voting is paused while a moderator looks at unusual activity on this one.' }));
      return;
    }
    if (t.mine) {
      const mine = LABELS[t.mine.choice] + (t.mine.reason ? ` (${REASONS[t.mine.reason] || t.mine.reason})` : '');
      el.append(h('p', { class: 'vote-mine', text: `You voted: ${mine}.` }));
      if (t.results) el.append(results(t));
      else el.append(h('p', { class: 'vote-msg', text: `Results show once ${t.threshold} people have voted (${t.n} so far). Check back later.` }));
      if (opts.ai) el.append(aiButton(item));
      return;
    }
    const choices = h('div', { class: 'vote-btns', role: 'group', 'aria-label': 'Your vote' });
    const reasons = h('div', { class: 'vote-reasons', hidden: true },
      h('p', { class: 'hint', text: 'What do you think it was?' }),
      h('div', { class: 'chips' }, Object.entries(REASONS).map(([k, v]) =>
        h('button', { type: 'button', class: 'chip', 'data-reason': k, 'aria-pressed': 'false', text: v }))));
    const slot = h('div', { class: 'ts-slot' });
    const msg = h('p', { class: 'vote-msg', role: 'status', 'aria-live': 'polite' });
    let choice = null, reason = null;
    for (const k of ['real', 'hoax', 'mis']) {
      choices.append(h('button', { type: 'button', class: `vbtn vbtn-${k}`, 'data-choice': k, 'aria-pressed': 'false', text: LABELS[k] }));
    }
    const send = h('button', { type: 'button', class: 'btn', hidden: true, text: 'Send my vote' });
    el.append(choices, reasons, send, slot, msg);
    el.append(h('p', { class: 'vote-n', text: t.n ? `${t.n} ${t.n === 1 ? 'vote' : 'votes'} so far. Vote to see results once there are ${t.threshold}.` : `No votes yet. Results show after ${t.threshold} votes.` }));
    if (opts.ai) el.append(aiButton(item));

    choices.addEventListener('click', (e) => {
      const b = e.target.closest('[data-choice]');
      if (!b) return;
      if (!session()) { askSignin(el, msg); return; }
      choice = b.dataset.choice;
      choices.querySelectorAll('[data-choice]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      reasons.hidden = choice !== 'mis';
      send.hidden = false;
      send.textContent = choice === 'mis' && !reason ? 'Pick a reason, then send' : `Send my vote: ${LABELS[choice]}`;
    });
    reasons.addEventListener('click', (e) => {
      const b = e.target.closest('[data-reason]');
      if (!b) return;
      reason = b.dataset.reason;
      reasons.querySelectorAll('[data-reason]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      send.textContent = `Send my vote: Misidentified (${REASONS[reason]})`;
    });
    send.addEventListener('click', async () => {
      if (!choice) return;
      if (choice === 'mis' && !reason) { msg.textContent = 'Pick what you think it was.'; return; }
      send.disabled = true;
      const body = { item, choice, reason: choice === 'mis' ? reason : '' };
      const pass = store.get('ea-pass', sessionStorage);
      if (pass) body.pass = pass;
      else {
        msg.textContent = 'Quick spam check...';
        try { body.turnstile = await human(slot); } catch (e) { msg.textContent = 'The spam check did not load. Reload and try again.'; send.disabled = false; return; }
      }
      msg.textContent = 'Sending...';
      let r = await api('/api/votes', { method: 'POST', body });
      if (r.status === 403 && r.data.state === 'turnstile' && body.pass) {
        store.del('ea-pass', sessionStorage); // pass expired: do the check once more
        delete body.pass;
        msg.textContent = 'Quick spam check...';
        body.turnstile = await human(slot);
        r = await api('/api/votes', { method: 'POST', body });
      }
      if (body.turnstile) resetHuman(slot);
      send.disabled = false;
      if (r.data.pass) store.set('ea-pass', r.data.pass, sessionStorage);
      if (r.status === 200) {
        tallies.set(item, r.data);
        renderVote(el, item, opts);
        if (r.data.state === 'held') el.append(h('p', { class: 'vote-msg', text: 'Thanks. A lot of votes came from your network at once, so yours will count after a moderator checks it.' }));
        return;
      }
      if (r.status === 401) { askSignin(el, msg); return; }
      msg.textContent = {
        duplicate: 'You already voted on this one.', frozen: 'Voting is paused on this one while a moderator checks it.',
        slow: 'You\'re voting very fast. Take a break and come back in a while.', turnstile: 'The spam check failed. Try again.',
        offline: 'No connection. Try again when you have signal.',
      }[r.data.state] || 'Something went wrong. Try again.';
      if (r.data.state === 'duplicate' || r.data.state === 'frozen') { await loadTallies([item]); renderVote(el, item, opts); }
    });
  }

  function askSignin(el, msg) {
    if (el.querySelector('.signin')) return;
    msg.textContent = '';
    el.append(signinBox({ title: 'Sign in to vote. One vote per person keeps it fair.', returnTo: location.href }));
  }

  function aiButton(item) {
    const b = h('button', { type: 'button', class: 'linkish ai-flag', text: 'Looks AI-generated? Tell a moderator' });
    b.addEventListener('click', async () => {
      if (!session()) { b.replaceWith(signinBox({ title: 'Sign in to flag this', returnTo: location.href })); return; }
      b.disabled = true;
      const r = await api('/api/flag', { method: 'POST', body: { item, kind: 'ai' } });
      b.textContent = r.status === 200 ? 'Thanks. A moderator will take a look.' : r.data.state === 'slow' ? 'You\'ve flagged a lot today. Try tomorrow.' : 'That didn\'t work. Try again later.';
    });
    return b;
  }

  // ---------- /reports/ views ----------
  const root = document.getElementById('ea-reports');
  window.EA = { cfg, API, BASE, h, api, store, session, user, signOut, human, resetHuman, creature, badge, title, fmtDate, makeMap, areaLayer, circle, signinBox, voteWidget, loadTallies, CAT_COLORS, page };
  if (!root) return;

  const qs = new URLSearchParams(location.search);
  const acct = root.querySelector('[data-acct]');
  if (acct && !session()) acct.textContent = 'Sign in';
  const mist = () => root.querySelector('.band-mist .wrap');
  const dark = () => root.querySelector('.band-dark .wrap');

  function headerBand(crumbs, h1, lede) {
    const d = dark();
    d.replaceChildren(h('p', { class: 'crumb' }, ...crumbs), h1, lede || '');
  }

  async function listView() {
    const head = dark();
    const mapEl = h('div', { class: 'reports-map', id: 'reports-map', 'aria-label': 'Map of approved reports' });
    head.append(mapEl);
    const map = makeMap(mapEl, { cooperative: true });
    if (map) {
      map.on('load', () => {
        map.addSource('reports', { type: 'geojson', data: API + '/api/reports.geojson', cluster: true, clusterRadius: 36, clusterMaxZoom: 10 });
        const colorExpr = ['match', ['get', 'c']];
        for (const [slug, c] of Object.entries(meta.creatures)) colorExpr.push(slug, CAT_COLORS[c.c] || '#E0C36A');
        colorExpr.push('#E0C36A');
        map.addLayer({ id: 'rc', type: 'circle', source: 'reports', filter: ['has', 'point_count'], paint: {
          'circle-color': '#F2B33D', 'circle-radius': ['interpolate', ['linear'], ['get', 'point_count'], 2, 12, 50, 20],
          'circle-stroke-color': '#13261F', 'circle-stroke-width': 2 } });
        map.addLayer({ id: 'rn', type: 'symbol', source: 'reports', filter: ['has', 'point_count'],
          layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12, 'text-font': ['Noto Sans Bold'] }, paint: { 'text-color': '#13261F' } });
        map.addLayer({ id: 'rp', type: 'circle', source: 'reports', filter: ['!', ['has', 'point_count']], paint: {
          'circle-color': colorExpr, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 6, 10, 10],
          'circle-stroke-color': '#13261F', 'circle-stroke-width': 2, 'circle-opacity': 0.95 } });
        map.on('click', 'rc', async (e) => {
          const f = e.features[0];
          const z = await map.getSource('reports').getClusterExpansionZoom(f.properties.cluster_id);
          map.easeTo({ center: f.geometry.coordinates, zoom: z });
        });
        map.on('click', 'rp', (e) => {
          const p = e.features[0].properties;
          const div = h('div', { class: 'pop' }, h('p', { class: 'pop-h', text: p.n || 'Encounter' }),
            h('p', { style: 'margin:0 0 .4rem', text: [p.t, p.d].filter(Boolean).join(', ') }),
            h('a', { href: page('?id=' + p.id), text: 'Read the report' }),
            h('p', { class: 'approx', style: 'margin:.4rem 0 0', text: 'Shown within about 5 km.' }));
          new maplibregl.Popup({ maxWidth: '280px' }).setLngLat(e.features[0].geometry.coordinates).setDOMContent(div).addTo(map);
        });
        for (const id of ['rc', 'rp']) {
          map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
          map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
        }
      });
    }

    const sel = h('select', { id: 'rf-creature', 'aria-label': 'Filter by creature' }, h('option', { value: '', text: 'Everything' }));
    for (const [k, label] of Object.entries(meta.cats)) {
      const og = h('optgroup', { label });
      for (const [slug, c] of Object.entries(meta.creatures).filter(([, c]) => c.c === k).sort((a, b) => a[1].n.localeCompare(b[1].n))) {
        og.append(h('option', { value: slug, text: c.n }));
      }
      if (og.children.length) sel.append(og);
    }
    sel.append(h('option', { value: 'other', text: 'Something else' }));
    const grid = h('div', { class: 'rep-cards' });
    const more = h('button', { type: 'button', class: 'btn btn-quiet', hidden: true, text: 'Show older reports' });
    const status = h('p', { class: 'loading', text: 'Loading reports...' });
    mist().replaceChildren(h('div', { class: 'list-bar' }, h('h2', { text: 'Latest reports' }), h('label', { class: 'filter' }, 'Show ', sel)), status, grid, h('p', {}, more));
    let next = null;
    async function load(reset) {
      if (reset) { grid.replaceChildren(); next = null; }
      status.hidden = false;
      status.textContent = 'Loading reports...';
      const q = new URLSearchParams({ limit: '24' });
      if (sel.value) q.set('creature', sel.value);
      if (next) q.set('before', next);
      const r = await api('/api/reports?' + q, { auth: false });
      if (r.status !== 200) { status.textContent = r.data.state === 'offline' ? 'No connection. Reports will load when you have signal.' : 'Reports didn\'t load. Try again in a minute.'; return; }
      status.hidden = r.data.reports.length > 0 || grid.children.length > 0;
      if (!status.hidden) {
        status.replaceChildren('No reports here yet. ', h('a', { href: `${BASE}/report/`, text: 'Be the first to report one' }), '.');
      }
      for (const x of r.data.reports) grid.append(card(x));
      next = r.data.next;
      more.hidden = !next;
    }
    sel.addEventListener('change', () => load(true));
    more.addEventListener('click', () => load(false));
    load(true);
  }

  function card(x) {
    const c = creature(x.creature, x.other_what);
    const pic = x.photo ? h('img', { src: API + x.photo, alt: '', loading: 'lazy', class: 'rc-img' }) : h('div', { class: `rc-img rc-noimg cat-${c.cat}` }, badge(x.creature, 'md', x.other_what));
    const bits = [x.n_photos ? `${x.n_photos} photo${x.n_photos > 1 ? 's' : ''}` : '', x.n_videos ? `${x.n_videos} video${x.n_videos > 1 ? 's' : ''}` : '', x.witnesses > 1 ? `${x.witnesses} witnesses` : ''].filter(Boolean);
    return h('a', { class: 'rcard', href: page('?id=' + x.id) }, pic,
      h('span', { class: 'rc-body' },
        h('span', { class: 'rc-kind' }, h('span', { class: `dot cat-${c.cat}` }), c.name),
        h('span', { class: 'rc-title', text: x.place || 'Place not named' }),
        h('span', { class: 'rc-date', text: fmtDate(x.seen_date, '', x.date_approx) }),
        h('span', { class: 'rc-snip', text: x.snippet }),
        bits.length ? h('span', { class: 'rc-meta', text: bits.join(' · ') }) : ''));
  }

  async function detailView(id) {
    mist().replaceChildren(h('p', { class: 'loading', text: 'Loading report...' }));
    const r = await api('/api/reports/' + encodeURIComponent(id));
    if (r.status !== 200) {
      headerBand([h('a', { href: page(), text: 'Encounters' })], h('h1', { text: 'Report not found' }));
      mist().replaceChildren(h('p', { class: 'lede-dark', text: r.data.state === 'offline' ? 'No connection right now.' : 'This report isn\'t public. It may still be waiting for a moderator, or it was removed.' }),
        h('p', {}, h('a', { class: 'btn', href: page(), text: 'See recent reports' })));
      return;
    }
    const R = r.data.report;
    const c = creature(R.creature, R.other_what);
    document.title = `${title(R)} | Encounter Atlas`;
    const d = dark();
    d.classList.add('rep-detail-head');
    d.replaceChildren(
      h('div', { class: 'creature-head-in' }, badge(R.creature, 'lg', R.other_what),
        h('div', {}, h('p', { class: 'crumb' }, h('a', { href: page(), text: 'Encounters' }), ' / ', c.name),
          h('h1', { text: title(R) }),
          h('p', { class: 'lede', text: fmtDate(R.seen_date, R.seen_time, R.date_approx) }))));

    const art = h('article', { class: 'prose rep-story' });
    if (R.owner) {
      const st = { pending: 'Waiting for a moderator. Only you can see it.', approved: 'Live on the site.', rejected: 'Not approved' + (R.mod_note ? `: ${R.mod_note}` : '.') }[R.status] || R.status;
      art.append(h('div', { class: 'owner-bar' }, h('span', { class: `pill pill-${R.status}`, text: R.status }), h('span', { text: ' Your report. ' + st + ' ' }),
        h('a', { href: `${BASE}/report/?edit=${R.id}`, text: 'Edit' })));
    }
    for (const p of R.story.split(/\n+/)) art.append(h('p', { text: p }));
    if (R.sounds) art.append(h('h2', { text: 'Sounds' }), h('p', { text: R.sounds }));
    if (R.smells) art.append(h('h2', { text: 'Smells' }), h('p', { text: R.smells }));

    const items = [R.item];
    if (R.photos.length) {
      art.append(h('h2', { text: R.photos.length > 1 ? 'Photos' : 'Photo' }));
      const gal = h('div', { class: 'gallery' });
      R.photos.forEach((p, i) => {
        items.push(p.item);
        gal.append(h('figure', { class: 'ph' },
          p.url ? h('a', { href: API + p.url, target: '_blank', rel: 'noopener' }, h('img', { src: API + p.url, alt: `Photo ${i + 1} from the witness`, loading: 'lazy', width: p.w, height: p.h })) : h('div', { class: 'ph-wait', text: 'Photo shows after approval' }),
          R.owner && R.status !== 'approved' ? '' : voteWidget(p.item, { label: 'This photo: real or hoax?', compact: true, ai: true })));
      });
      art.append(gal);
    }
    if (R.videos.length) {
      art.append(h('h2', { text: R.videos.length > 1 ? 'Videos' : 'Video' }));
      for (const v of R.videos) {
        items.push(v.item);
        art.append(h('div', { class: 'vid' }, videoEmbed(v), R.owner && R.status !== 'approved' ? '' : voteWidget(v.item, { label: 'This video: real or hoax?', compact: true, ai: true })));
      }
    }
    if (!R.owner || R.status === 'approved') {
      art.append(h('h2', { id: 'vote', text: 'Real or hoax?' }), voteWidget(R.item, { label: 'Your verdict on this encounter', ai: false }));
    }

    const facts = h('dl');
    const add = (k, v) => { if (v) facts.append(h('div', {}, h('dt', { text: k }), h('dd', {}, v))); };
    add('What', R.creature === 'other' ? R.other_what : h('a', { href: `${BASE}/creatures/${R.creature}/`, text: c.name }));
    add('When', fmtDate(R.seen_date, R.seen_time, R.date_approx));
    add('Where', (R.place ? R.place + '. ' : '') + 'Shown within about 5 km.');
    add('How long', R.duration);
    add('Witnesses', String(R.witnesses));
    add('Reported by', R.name || 'Anonymous');
    const mapEl = h('div', { class: 'mini-map', 'aria-label': 'Approximate area' });
    const aside = h('aside', { class: 'facts' }, mapEl, facts,
      h('p', { class: 'more' }, h('a', { href: `${BASE}/report/`, text: 'Seen something too? Report it' })));
    mist().replaceChildren(h('div', { class: 'creature-body' }, art, aside));
    const map = makeMap(mapEl, { center: [R.lon, R.lat], zoom: 9.5, maxZoom: 11, cooperative: true });
    if (map) map.on('load', () => areaLayer(map, 'area', R.lon, R.lat, 3));
    await loadTallies(items);
    for (const [it, el] of widgetsByItem) {
      const opts = { label: el.querySelector('.vote-h strong')?.textContent, compact: el.classList.contains('vote-compact'), ai: it[0] !== 'r' };
      renderVote(el, it, opts);
    }
    if (location.hash === '#vote') document.getElementById('vote')?.scrollIntoView();
  }

  function videoEmbed(v) {
    if (v.provider === 'youtube') {
      const btn = h('button', { type: 'button', class: 'yt', 'aria-label': 'Play video' },
        h('img', { src: `https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`, alt: '', loading: 'lazy' }), h('span', { class: 'yt-play', 'aria-hidden': 'true' }));
      btn.addEventListener('click', () => {
        btn.replaceWith(h('iframe', { class: 'yt-frame', src: `https://www.youtube-nocookie.com/embed/${v.id}?autoplay=1`, title: 'Video from the witness',
          allow: 'autoplay; encrypted-media; picture-in-picture', allowfullscreen: true, referrerpolicy: 'strict-origin-when-cross-origin' }));
      });
      return h('div', { class: 'vid-box' }, btn, h('a', { class: 'vid-link', href: v.url, rel: 'noopener nofollow ugc', target: '_blank', text: 'Watch on YouTube' }));
    }
    const name = v.provider === 'tiktok' ? 'TikTok' : 'Vimeo';
    return h('a', { class: 'vid-card', href: v.url, rel: 'noopener nofollow ugc', target: '_blank' }, h('span', { class: 'yt-play', 'aria-hidden': 'true' }), `Watch the video on ${name}`);
  }

  async function meView() {
    headerBand([h('a', { href: page(), text: 'Encounters' }), ' / Your reports'], h('h1', { text: 'Your reports' }));
    if (!session()) {
      mist().replaceChildren(h('p', { class: 'lede-dark', text: 'Sign in to see and edit your reports, and to vote.' }), signinBox({ title: 'Sign in', returnTo: page('?me=1') }));
      return;
    }
    mist().replaceChildren(h('p', { class: 'loading', text: 'Loading...' }));
    const r = await api('/api/me');
    if (r.status !== 200) { location.reload(); return; }
    const u = r.data.user;
    const nameIn = h('input', { value: u.name || '', maxlength: '40', id: 'acct-name', autocomplete: 'nickname' });
    const saved = h('span', { class: 'hint' });
    const list = h('ul', { class: 'my-reports' });
    for (const x of r.data.reports) {
      const c = creature(x.creature, x.other_what);
      list.append(h('li', {}, badge(x.creature, 'sm', x.other_what),
        h('span', { class: 'mr-t' }, h('a', { href: page('?id=' + x.id), text: title(x) }),
          h('span', { class: 'muted', text: ' ' + fmtDate(x.seen_date) })),
        h('span', { class: `pill pill-${x.status}`, text: x.status }),
        x.status !== 'withdrawn' ? h('a', { href: `${BASE}/report/?edit=${x.id}`, text: 'Edit' }) : ''));
    }
    const out = h('button', { type: 'button', class: 'btn btn-quiet', text: 'Sign out' });
    out.addEventListener('click', () => { signOut(); location.href = page(); });
    const save = h('button', { type: 'button', class: 'btn btn-quiet', text: 'Save' });
    save.addEventListener('click', async () => {
      const s = await api('/api/me', { method: 'PATCH', body: { name: nameIn.value } });
      saved.textContent = s.status === 200 ? ' Saved.' : ' Not saved, try again.';
    });
    mist().replaceChildren(
      h('p', { class: 'lede-dark', text: `Signed in as ${u.email}.` }),
      h('div', { class: 'field acct-name' }, h('label', { for: 'acct-name', text: 'Name shown on reports where you choose to show it' }), h('div', { class: 'signin-row' }, nameIn, save), saved),
      h('h2', { text: 'Reports you sent' }),
      r.data.reports.length ? list : h('p', {}, 'None yet. ', h('a', { href: `${BASE}/report/`, text: 'Report an encounter' }), '.'),
      h('p', { class: 'hint', text: u.weight < 1 ? 'New accounts\' votes count a little less for the first week, or until a report of yours is approved. It keeps throwaway accounts from swinging results.' : '' }),
      h('p', {}, out));
  }

  if (qs.get('signin')) handleSignin(qs.get('signin'));
  else if (qs.get('id')) detailView(qs.get('id'));
  else if (qs.get('me')) meView();
  else listView();
})();

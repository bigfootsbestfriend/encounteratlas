// Road trip mode. Planner (/road-trip/) and sample trip pages (/road-trip/<slug>/). Nothing runs until a control is
// used, except the trip-page map, which loads when it scrolls near the screen.
// Route: FOSSGIS OSRM (routing.openstreetmap.de, OpenStreetMap data) with coordinates rounded to 0.01; if that fails,
// a straight line, labelled as such. Stops come from /data/roadtrip.json, archive counts from the /data/near/ tiles,
// reader reports from the Worker's public feed.
(function () {
  const cfgEl = document.getElementById('rt-config');
  if (!cfgEl) return;
  const CFG = JSON.parse(cfgEl.textContent);
  const $ = (id) => document.getElementById(id);
  const KM_PER_MI = 1.609344;
  const KIND = { place: ['Place to visit', '#9CC46B'], case: ['Famous case', '#D9A05B'], mystery: ['Mystery', '#E07A4F'],
    encounter: ['Close encounter', '#8E8CF0'], newspaper: ['Old newspaper story', '#C9B27A'], report: ['Reader report', '#F2B33D'] };
  const ARCH = { bluebook: ['Air Force UFO file', 'Air Force UFO files'], faa: ['FAA pilot report', 'FAA pilot reports'], pursue: ['Pentagon UFO file', 'Pentagon UFO files'],
    canada: ['Canadian UFO Survey town', 'Canadian UFO Survey towns'], greece: ['Greek close encounter', 'Greek close encounters'] };
  const S = { km: 40, unit: 'km', trip: null };
  const status = $('rt-status');
  const say = (t) => { if (status) status.textContent = t; };
  const round2 = (x) => Math.round(x * 100) / 100;
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const fold = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const fmt = (km) => (S.unit === 'mi' ? `${Math.round(km / KM_PER_MI).toLocaleString()} mi` : `${Math.round(km).toLocaleString()} km`);
  const track = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: 'road-trip', ...p }); } catch (e) { /* no analytics */ } };
  function hav(a1, o1, a2, o2) {
    const r = Math.PI / 180, h = Math.sin(((a2 - a1) * r) / 2) ** 2 + Math.cos(a1 * r) * Math.cos(a2 * r) * Math.sin(((o2 - o1) * r) / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
  }
  let dataP = null;
  const data = () => dataP || (dataP = fetch(CFG.data).then((r) => r.json()));

  // ---------- geometry ----------
  function densify(route, step = 4) {
    const out = []; let acc = 0;
    for (let i = 0; i < route.length - 1; i++) {
      const [o1, a1] = route[i], [o2, a2] = route[i + 1], d = hav(a1, o1, a2, o2), n = Math.max(1, Math.floor(d / step));
      for (let j = 0; j < n; j++) out.push([a1 + ((a2 - a1) * j) / n, o1 + ((o2 - o1) * j) / n, acc + (d * j) / n]);
      acc += d;
    }
    const last = route[route.length - 1];
    out.push([last[1], last[0], acc]);
    return out;
  }
  // Samples bucketed into half-degree cells so each stop only checks the bit of road near it
  function indexer(samples) {
    const grid = new Map(), key = (a, o) => `${Math.floor(a * 2)}_${Math.floor(o * 2)}`;
    samples.forEach((s, i) => { const k = key(s[0], s[1]); if (!grid.has(k)) grid.set(k, []); grid.get(k).push(i); });
    return (lat, lon, max) => {
      let best = null;
      const span = Math.ceil(max / 50) + 1, ka = Math.floor(lat * 2), ko = Math.floor(lon * 2);
      for (let da = -span; da <= span; da++) for (let dn = -span; dn <= span; dn++) {
        for (const i of grid.get(`${ka + da}_${ko + dn}`) || []) {
          const d = hav(lat, lon, samples[i][0], samples[i][1]);
          if (d <= max && (!best || d < best.off)) best = { off: d, km: samples[i][2] };
        }
      }
      return best;
    };
  }
  function straight(pts) {
    // Fallback when the routing server can't be reached: a straight line between the points
    return pts.map(([a, o]) => [o, a]);
  }
  async function route(pts) {
    const coords = pts.map(([a, o]) => `${round2(o)},${round2(a)}`).join(';');
    try {
      const r = await fetch(`https://routing.openstreetmap.de/routed-car/route/v1/driving/${coords}?overview=full&geometries=geojson`);
      const d = await r.json();
      if (d.code !== 'Ok') throw new Error(d.code);
      return { line: d.routes[0].geometry.coordinates, km: d.routes[0].distance / 1000, h: d.routes[0].duration / 3600, road: true };
    } catch (e) {
      const line = straight(pts);
      const km = densify(line).pop()[2];
      return { line, km, h: null, road: false };
    }
  }

  // ---------- what's along the road ----------
  let tileIndex = null; const tileCache = new Map();
  const loadIndex = () => tileIndex || (tileIndex = fetch(CFG.tiles + 'index.json').then((r) => r.json()).then((d) => new Set(Object.keys(d.tiles))).catch(() => null));
  const tile = (k) => { if (!tileCache.has(k)) tileCache.set(k, fetch(CFG.tiles + k + '.json').then((r) => (r.ok ? r.json() : { features: [] })).catch(() => ({ features: [] }))); return tileCache.get(k); };
  async function archiveCounts(samples, near, max) {
    const keys = new Set();
    for (const [a, o] of samples) for (const da of [-1, 0, 1]) for (const dn of [-1, 0, 1]) {
      const la = Math.floor((a + da * (max / 111)) / 5) * 5, lo = Math.floor((o + dn * (max / 80)) / 5) * 5;
      if (la >= -90 && la <= 85) keys.add(`${la}_${lo}`);
    }
    const have = await loadIndex();
    const tiles = await Promise.all([...keys].filter((k) => !have || have.has(k)).map(tile));
    const n = {};
    for (const t of tiles) for (const f of t.features) {
      const src = f.properties.src;
      if (!ARCH[src] || f.properties.a === 1) continue;
      const [lon, lat] = f.geometry.coordinates;
      if (near(lat, lon, max)) n[src] = (n[src] || 0) + 1;
    }
    return n;
  }
  let feed = null;
  async function readerReports(near, max) {
    feed = feed || fetch(CFG.api + '/api/reports.geojson').then((r) => (r.ok ? r.json() : { features: [] })).catch(() => ({ features: [] }));
    const out = [];
    for (const f of (await feed).features) {
      const p = f.properties;
      if (CFG.living.includes(p.c)) continue; // region-level only, never a spot on a road trip
      const [lon, lat] = f.geometry.coordinates, b = near(lat, lon, max);
      if (b) out.push({ k: 'report', lat, lon, t: p.n || 'Something strange', sub: `${p.t || ''}${p.d ? ', ' + p.d : ''}`, u: '/reports/' + p.id + '/', c: p.c, ...b });
    }
    return out;
  }
  async function along(line) {
    const d = await data(), samples = densify(line), near = indexer(samples), max = S.km;
    const stops = [];
    for (const s of d.stops) {
      const b = near(s[1], s[2], max);
      if (b) stops.push({ k: s[0], lat: s[1], lon: s[2], t: s[3], sub: s[4], u: s[5], c: s[6], ...b });
    }
    const [reps, arch] = await Promise.all([readerReports(near, max), archiveCounts(samples, near, max)]);
    stops.push(...reps);
    const seen = new Set();
    const uniq = stops.sort((x, y) => x.km - y.km).filter((s) => { const k = s.t + '|' + s.u; if (seen.has(k)) return false; seen.add(k); return true; });
    const cards = [...new Set(uniq.map((s) => s.c).filter((c) => c && d.cards[c]))];
    return { stops: uniq, arch, cards, total: samples[samples.length - 1][2] };
  }

  // ---------- map ----------
  let map = null, mapP = null;
  function tint() {
    for (const layer of map.getStyle().layers) {
      try {
        if (layer.type === 'background') map.setPaintProperty(layer.id, 'background-color', '#0F1F19');
        else if (/water/.test(layer.id) && layer.type === 'fill') map.setPaintProperty(layer.id, 'fill-color', '#0A1714');
        else if (/landcover|park|wood|forest|grass/.test(layer.id) && layer.type === 'fill') map.setPaintProperty(layer.id, 'fill-color', '#16302A');
        else if (layer.type === 'symbol' && /place|label/.test(layer.id)) { map.setPaintProperty(layer.id, 'text-color', '#A9B98F'); map.setPaintProperty(layer.id, 'text-halo-color', '#0F1F19'); }
      } catch (e) { /* layer without that property */ }
    }
  }
  function loadLib() {
    if (window.maplibregl) return Promise.resolve();
    return new Promise((res, rej) => { const s = document.createElement('script'); s.src = 'https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js'; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
  }
  function ensureMap() {
    if (mapP) return mapP;
    mapP = loadLib().then(() => new Promise((resolve) => {
      map = new maplibregl.Map({ container: 'rt-map', style: 'https://tiles.openfreemap.org/styles/dark', center: [0, 30], zoom: 2,
        cooperativeGestures: true, attributionControl: { compact: true } });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
      map.on('load', () => {
        tint();
        map.addSource('route', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addSource('stops', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({ id: 'route-casing', type: 'line', source: 'route', paint: { 'line-color': '#13261F', 'line-width': 7 } });
        map.addLayer({ id: 'route', type: 'line', source: 'route', paint: { 'line-color': '#F2B33D', 'line-width': 3.5 } });
        map.addLayer({ id: 'stops', type: 'circle', source: 'stops', paint: { 'circle-color': ['get', 'col'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 5, 10, 9],
          'circle-stroke-color': '#13261F', 'circle-stroke-width': 2 } });
        map.on('mouseenter', 'stops', () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', 'stops', () => { map.getCanvas().style.cursor = ''; });
        map.on('click', 'stops', (e) => {
          const p = e.features[0].properties, div = el('div', 'pop');
          div.append(el('div', 'pop-kind', KIND[p.k][0]), el('p', 'pop-h', p.t), el('p', 'pop-meta', p.sub));
          const a = el('a', '', 'Read more'); a.href = p.u; div.append(a);
          new maplibregl.Popup({ maxWidth: '280px' }).setLngLat(e.features[0].geometry.coordinates).setDOMContent(div).addTo(map);
        });
        resolve(map);
      });
    }));
    return mapP;
  }
  async function draw(line, stops) {
    await ensureMap();
    map.getSource('route').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: line }, properties: {} });
    map.getSource('stops').setData({ type: 'FeatureCollection', features: stops.map((s) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: { k: s.k, t: s.t, sub: s.sub, u: s.u, col: KIND[s.k][1] } })) });
    const b = new maplibregl.LngLatBounds();
    line.forEach((c) => b.extend(c));
    map.fitBounds(b, { padding: 40, duration: 0 });
  }

  // ---------- trip pages: just the map, when it comes near the screen ----------
  if (CFG.trip && !$('rt-form')) {
    const box = $('rt-map');
    const go = async () => {
      const d = await data(), t = d.trips[CFG.trip];
      const res = await along(t.route);
      draw(t.route, res.stops.filter((s) => s.k !== 'report'));
    };
    if ('IntersectionObserver' in window) new IntersectionObserver((es, o) => { if (es.some((e) => e.isIntersecting)) { o.disconnect(); go(); } }, { rootMargin: '400px 0px' }).observe(box);
    else go();
    return;
  }

  // ---------- planner ----------
  const form = $('rt-form');
  if (!form) return;
  let cities = null;
  const loadCities = () => cities || (cities = fetch(CFG.cities).then((r) => r.json()).catch(() => []));
  const here = { from: null };
  for (const id of ['rt-from', 'rt-to']) {
    const inp = $(id);
    inp.addEventListener('focus', loadCities, { once: true });
    inp.addEventListener('input', async () => {
      if (id === 'rt-from') here.from = null;
      const q = fold(inp.value.trim());
      if (q.length < 2) return;
      const list = await loadCities(), hits = [];
      for (const c of list) { if (fold(c[0]).startsWith(q)) { hits.push(c); if (hits.length >= 12) break; } }
      const show = (vals) => $('rt-cities').replaceChildren(...vals.map((v) => { const o = document.createElement('option'); o.value = v; return o; }));
      const mine = hits.map((c) => c[0] + ', ' + c[1]);
      show(mine);
      // smaller towns (Jasper, Alberta) come from the place search a moment after typing stops
      clearTimeout(here.t);
      here.t = setTimeout(async () => {
        if (!window.EAPlace || fold(inp.value.trim()) !== q) return;
        const more = await window.EAPlace.suggest(inp.value);
        if (fold(inp.value.trim()) !== q) return;
        const have = new Set(mine.map((m) => fold(m.split(',')[0]) + '|' + fold(m.split(',')[1] || '')));
        show([...mine, ...more.filter((m) => !have.has(fold(m.split(',')[0]) + '|' + fold(m.split(',')[1] || '')))].slice(0, 16));
      }, 350);
    });
  }
  form.querySelectorAll('.rt-chips [data-km]').forEach((b) => b.addEventListener('click', () => {
    form.querySelectorAll('.rt-chips [data-km]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    S.km = S.unit === 'mi' ? +b.dataset.mi * KM_PER_MI : +b.dataset.km;
  }));
  const unitBtn = form.querySelector('.rt-unit');
  const setUnit = (u) => {
    S.unit = u; unitBtn.setAttribute('aria-pressed', String(u === 'mi'));
    form.querySelectorAll('.rt-chips [data-km]').forEach((b) => {
      b.textContent = u === 'mi' ? `${b.dataset.mi} mi` : `${b.dataset.km} km`;
      if (b.getAttribute('aria-pressed') === 'true') S.km = u === 'mi' ? +b.dataset.mi * KM_PER_MI : +b.dataset.km;
    });
    if (S.last) render(S.last);
  };
  unitBtn.addEventListener('click', () => setUnit(S.unit === 'km' ? 'mi' : 'km'));
  if (/^en-US$/i.test(navigator.language || '')) setUnit('mi');
  $('rt-here').addEventListener('click', () => {
    const msg = $('rt-here-msg'), inp = $('rt-from'), tell = (t) => { if (msg) msg.textContent = t; };
    if (!navigator.geolocation) { tell("This browser can't share your location. Type your town instead."); inp.focus(); return; }
    tell('Finding you...'); inp.value = ''; inp.placeholder = 'Finding you...';
    navigator.geolocation.getCurrentPosition(async (p) => {
      const lat = round2(p.coords.latitude), lon = round2(p.coords.longitude);
            let label = 'Your location';
      try {
        // our list runs biggest first, so the first town within 25 km is the city you'd name (Edmonton, not a neighbourhood)
        const list = await loadCities(), k = Math.cos(lat * Math.PI / 180);
        const km = (c) => 111 * Math.hypot(c[2] - lat, (c[3] - lon) * k);
        const best = list.find((c) => km(c) < 25);
        if (best) label = best[0] + ', ' + best[1];
      } catch (e) { /* list didn't load, keep the generic label */ }
      here.from = [lat, lon, label];
      inp.value = label; inp.placeholder = 'Town or city'; tell('Got it. Now pick where you\'re headed.');
      $('rt-to').focus();
    }, (err) => {
      inp.placeholder = 'Town or city';
      tell(err && err.code === 1
        ? 'Location is blocked for this site. Allow it from the icon in the address bar (or your phone settings), or just type your town.'
        : "Couldn't get your location just now. Type your town instead.");
      inp.focus();
    }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 });
  });

  async function plan(pts, label, cached) {
    say('Working out the route...');
    $('rt-out').hidden = false;
    const r = cached ? { line: cached, km: densify(cached).pop()[2], h: null, road: true } : await route(pts);
    say('Finding everything along the road...');
    const res = await along(r.line);
    S.last = { pts, label, r, res };
    render(S.last);
    draw(r.line, res.stops);
    say('');
    track('roadtrip_plan', { km: Math.round(r.km), stops: res.stops.length });
    const q = new URLSearchParams({ from: pts[0].slice(0, 2).join(','), to: pts[pts.length - 1].slice(0, 2).join(','), fn: pts[0][2] || '', tn: pts[pts.length - 1][2] || '', km: S.km });
    if (!S.trip) history.replaceState(null, '', '?' + q);
  }
  function render({ pts, label, r, res }) {
    const out = $('rt-results'); out.replaceChildren();
    out.append(el('h2', 'rt-title', label));
    const stats = el('ul', 'rt-stats');
    const stat = (b, s) => { const li = el('li'); li.append(el('b', '', b), el('span', '', s)); stats.append(li); };
    stat(fmt(r.km), r.road ? 'by road' : 'straight line');
    if (r.h) stat(`${r.h.toFixed(1)} h`, 'of driving');
    stat(String(res.stops.length), 'stops');
    stat(String(res.cards.length), 'cards to collect');
    out.append(stats);
    if (!r.road) out.append(el('p', 'rt-note', "We couldn't reach the routing server, so this is a straight line between the two places. The stops are still real, but the road will be longer."));
    const arch = Object.entries(res.arch).filter(([, n]) => n);
    if (arch.length) out.append(el('p', 'rt-arch', 'Also along this road: ' + arch.map(([k, n]) => `${n.toLocaleString()} ${ARCH[k][n === 1 ? 0 : 1]}`).join(', ') + '.'));
    const acts = el('p', 'rt-actions');
    const saveBtn = el('button', 'btn btn-sm', 'Save this trip'); saveBtn.type = 'button';
    saveBtn.addEventListener('click', () => { saveTrip(label, pts); saveBtn.textContent = 'Saved on this device'; });
    const dir = el('a', 'btn btn-sm btn-ghost', 'Directions');
    dir.href = 'https://www.google.com/maps/dir/' + pts.map((p) => `${round2(p[0])},${round2(p[1])}`).join('/'); dir.target = '_blank'; dir.rel = 'noopener';
    const share = el('button', 'btn btn-sm btn-ghost', 'Share'); share.type = 'button';
    share.addEventListener('click', async () => {
      try { if (navigator.share) await navigator.share({ title: label, url: location.href }); else { await navigator.clipboard.writeText(location.href); share.textContent = 'Link copied'; } } catch (e) { /* cancelled */ }
    });
    acts.append(saveBtn, dir, share); out.append(acts);
    if (!res.stops.length) out.append(el('p', 'rt-note', `Nothing within ${fmt(S.km)} of this road yet. Try a wider distance, or if you see something on the way, report it.`));
    const ol = el('ol', 'rt-stops');
    for (const s of res.stops) {
      const li = el('li', 'rt-stop k-' + s.k);
      li.append(el('span', 'rt-km', fmt(s.km)));
      const dot = el('span', 'rt-dot'); dot.style.setProperty('--k', KIND[s.k][1]); dot.setAttribute('aria-hidden', 'true'); li.append(dot);
      const txt = el('span', 'rt-txt'), a = el('a', '', s.t); a.href = s.u;
      txt.append(a, el('small', '', `${KIND[s.k][0]} · ${s.sub}${s.off >= 5 ? ' · ' + fmt(s.off) + ' off the route' : ''}`));
      li.append(txt); ol.append(li);
    }
    out.append(ol);
    document.dispatchEvent(new CustomEvent('ea:route', { detail: { after: ol, stops: res.stops } })); // podplayer.js "Listen along"
    if (res.cards.length) {
      out.append(el('h2', '', 'Cards on this route'));
      const p = el('p', '', `Stand within ${fmt(25)} of one of these spots and tap "I'm here" to collect the card.`); out.append(p);
      const btn = el('button', 'btn', "I'm here"); btn.type = 'button';
      const st = el('p', 'rt-status'); st.setAttribute('aria-live', 'polite');
      out.append(btn, st);
      if (window.eaCards) window.eaCards.button(btn, st);
      data().then((d) => {
        const ul = el('ul', 'cc-grid');
        for (const slug of res.cards) {
          const c = d.cards[slug], li = el('li', 'cc cat-' + c.c); li.dataset.card = slug;
          const a = el('a'); a.href = '/creatures/' + slug + '/';
          const art = el('span', 'cc-art');
          if (c.art) { const img = el('img'); img.src = c.art; img.alt = ''; img.width = 96; img.height = 96; art.append(img); }
          const meta = el('span', 'cc-meta'); meta.append(el('span', 'cc-r cc-r-' + c.r.toLowerCase(), c.r));
          const got = el('span', 'cc-got', 'Collected'); got.hidden = true;
          a.append(art, el('span', 'cc-name', c.n), meta, got); li.append(a); ul.append(li);
        }
        out.append(ul);
        if (window.eaCards) window.eaCards.mark(out);
      });
    }
  }
  const TKEY = 'ea-trips';
  const trips = () => { try { return JSON.parse(localStorage.getItem(TKEY) || '[]'); } catch (e) { return []; } };
  function saveTrip(label, pts) {
    const t = trips().filter((x) => x.label !== label);
    t.unshift({ label, pts, km: S.km, at: new Date().toISOString().slice(0, 10) });
    try { localStorage.setItem(TKEY, JSON.stringify(t.slice(0, 20))); } catch (e) { /* storage blocked */ }
    savedList();
  }
  // Stops added with "Add to road trip" on place and state pages (tripadd.js): one saved trip marked mine: true
  const mineTrip = () => trips().find((x) => x && x.mine) || null;
  function order(pts) {
    // nearest stop next, starting from the first one added, so the route doesn't zigzag
    const left = pts.slice(1), out = [pts[0]];
    while (left.length) {
      const last = out[out.length - 1];
      let bi = 0;
      left.forEach((p, i) => { if (hav(last[0], last[1], p[0], p[1]) < hav(last[0], last[1], left[bi][0], left[bi][1])) bi = i; });
      out.push(left.splice(bi, 1)[0]);
    }
    return out;
  }
  function planMine() {
    const t = mineTrip();
    if (!t || t.pts.length < 2) return false;
    S.trip = null; S.km = t.km || 40;
    plan(order(t.pts), `Your road trip: ${t.pts.length} stops`);
    track('roadtrip_plan_mine', { stops: t.pts.length });
    return true;
  }
  function mineBox() {
    const t = mineTrip(); let box = $('rt-mine');
    if (!t || !t.pts.length) { if (box) box.remove(); return; }
    if (!box) { box = el('div', 'rt-saved rt-mine'); box.id = 'rt-mine'; form.after(box); }
    box.replaceChildren(el('h2', '', `Your stops (${t.pts.length})`));
    const ol = el('ol');
    t.pts.forEach((p, i) => {
      const li = el('li'), a = el('a', '', p[2]); a.href = p[3] || '#';
      const rm = el('button', 'rt-savedbtn rt-rm', 'Remove'); rm.type = 'button';
      rm.setAttribute('aria-label', 'Remove ' + p[2]);
      rm.addEventListener('click', () => {
        const all = trips(), m = all.find((x) => x && x.mine);
        if (m) m.pts.splice(i, 1);
        try { localStorage.setItem(TKEY, JSON.stringify(all.filter((x) => !x.mine || x.pts.length))); } catch (e) { /* storage blocked */ }
        mineBox();
      });
      li.append(a, document.createTextNode(' '), rm); ol.append(li);
    });
    box.append(ol);
    if (t.pts.length >= 2) {
      const go = el('button', 'btn btn-sm', `Plan a route through all ${t.pts.length}`); go.type = 'button';
      go.addEventListener('click', planMine); box.append(go);
    } else box.append(el('p', 'small', 'Add one more place from any place or state page and we\'ll plan a route through them.'));
  }
  function savedList() {
    mineBox();
    const t = trips().filter((x) => !x.mine); let box = $('rt-saved');
    if (!t.length) { if (box) box.remove(); return; }
    if (!box) { box = el('div', 'rt-saved'); box.id = 'rt-saved'; ($('rt-mine') || form).after(box); }
    box.replaceChildren(el('h2', '', 'Your saved trips'));
    const ul = el('ul');
    for (const x of t) {
      const li = el('li'), b = el('button', 'rt-savedbtn', x.label); b.type = 'button';
      b.addEventListener('click', () => { S.km = x.km || 40; plan(x.pts, x.label); });
      li.append(b, el('small', '', ' saved ' + x.at)); ul.append(li);
    }
    box.append(ul);
  }
  savedList();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    S.trip = null;
    // placefind.js settles both ends together, so "Edmonton" to "Jasper" is Jasper, Alberta (not Indiana)
    const [from, to] = window.EAPlace ? await window.EAPlace.trip(here.from || $('rt-from').value, $('rt-to').value, await loadCities()) : [null, null];
    if (!from) { say(`We couldn't find "${$('rt-from').value}". Try a bigger town nearby.`); return; }
    if (!to) { say(`We couldn't find "${$('rt-to').value}". Try a bigger town nearby.`); return; }
    plan([from, to], `${from[2]} to ${to[2]}`);
  });

  // Shared links (?from=lat,lon&to=lat,lon&fn=&tn=&km=) and "Open in the planner" (?trip=slug)
  const q = new URLSearchParams(location.search);
  if (q.get('mine')) {
    if (!planMine() && $('rt-mine')) $('rt-mine').scrollIntoView({ block: 'center' });
  } else if (q.get('trip')) {
    data().then((d) => {
      const t = d.trips[q.get('trip')];
      if (!t) return;
      S.trip = q.get('trip');
      $('rt-from').value = t.waypoints[0][0]; $('rt-to').value = t.waypoints[t.waypoints.length - 1][0];
      const pts = t.waypoints.map((w) => [w[1], w[2], w[0]]);
      plan(pts, t.title, t.route);
    });
  } else if (q.get('from') && q.get('to')) {
    const p = (s, n) => { const [a, o] = s.split(',').map(Number); return isFinite(a) && isFinite(o) ? [a, o, n || `${a}, ${o}`] : null; };
    const a = p(q.get('from'), q.get('fn')), b = p(q.get('to'), q.get('tn'));
    if (q.get('km')) S.km = Math.min(80, Math.max(5, +q.get('km') || 40));
    if (a && b) { $('rt-from').value = a[2]; $('rt-to').value = b[2]; here.from = a; plan([a, b], `${a[2]} to ${b[2]}`); }
  }
})();

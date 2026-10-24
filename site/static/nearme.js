// /near-me/: the site page and the app's home screen. Nothing runs until a control is used (SEO-safe: the page is
// complete HTML without this file). Then: reader reports from the Worker's /v1/reports/nearby, archive files from
// the 5-degree tiles in /data/near/, a MapLibre map in the same style as the full map, and a list under it.
// "Then and now" filters the map and list by era (old newspapers to today) with a count per era; old newspaper stories
// come from /data/historic.geojson, fetched with the first search. "Flap in progress" asks the Worker's /v1/clusters,
// only when the build found it live (CFG.clusters), and stays silent if anything goes wrong.
(function () {
  const cfgEl = document.getElementById('nm-config');
  if (!cfgEl) return;
  const CFG = JSON.parse(cfgEl.textContent);
  const $ = (id) => document.getElementById(id);
  const R_KM = 6371.0088, KM_PER_MI = 1.609344;
  const CAT = { hominid: '#D9A05B', canid: '#D0633F', winged: '#B98ACB', aquatic: '#4FB3A9', entity: '#9CC46B', fae: '#E58FB0', ufo: '#8E8CF0', other: '#E0C36A' };
  const REP = { ufo: '#8E8CF0', creature: '#D9A05B', other: '#E0C36A' };
  const ARCH = {
    bluebook: { color: '#F2B33D', label: 'Air Force UFO file (Project Blue Book)' },
    bluebook_approx: { color: '#F2B33D', label: 'Air Force UFO files, area only' },
    faa: { color: '#7FD3FF', label: 'FAA pilot report' },
    pursue: { color: '#E07A5F', label: 'Pentagon UFO file' },
    canada: { color: '#C08BE8', label: 'Canadian UFO Survey' },
    greece: { color: '#4FC3A1', label: 'Greek close encounter (GRUFON)' },
    historic: { color: '#E9D8A6', label: 'Old newspaper story' },
  };
  const PILL = { bluebook: ['Air Force file', 'Air Force files'], faa: ['FAA pilot report', 'FAA pilot reports'], pursue: ['Pentagon file', 'Pentagon files'],
    canada: ['Canadian UFO Survey town', 'Canadian UFO Survey towns'], greece: ['Greek close encounter', 'Greek close encounters'], historic: ['old newspaper story', 'old newspaper stories'], bluebook_approx: ['area-only Air Force group', 'area-only Air Force groups'] };
  const S = { lat: null, lng: null, label: '', km: 50, mi: 30, unit: 'km', cat: '', days: 30, era: 0 };
  const ERAS = CFG.eras || [{ id: 'all', name: 'Every era', span: '' }];
  let last = null; // the latest search results, so the era slider can re-filter without fetching again
  const status = $('nm-status'), results = $('nm-results');
  let map = null, mapReady = null, seq = 0;

  // ---------- helpers ----------
  const round2 = (x) => Math.round(x * 100) / 100;
  function hav(a1, o1, a2, o2) {
    const r = Math.PI / 180, dl = (a2 - a1) * r, dn = (o2 - o1) * r;
    const h = Math.sin(dl / 2) ** 2 + Math.cos(a1 * r) * Math.cos(a2 * r) * Math.sin(dn / 2) ** 2;
    return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  const wrapLon = (x) => ((((x + 180) % 360) + 360) % 360) - 180;
  // Keep a point's longitude on the same side of the antimeridian as the search centre, so the map draws it nearby.
  const near = (lon) => (lon - S.lng > 180 ? lon - 360 : lon - S.lng < -180 ? lon + 360 : lon);
  const dist = (km) => { const v = S.unit === 'mi' ? km / KM_PER_MI : km; return v < 1 ? `under 1 ${S.unit}` : `${Math.round(v)} ${S.unit}`; };
  function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function a(href, text, cls) { const n = el('a', cls, text); n.href = href; return n; }
  const say = (t) => { status.textContent = t; };
  const niceDate = (d) => { try { return new Date(d + 'T12:00:00Z').toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }); } catch (e) { return d; } };
  const track = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: 'near-me', ...p }); } catch (e) { /* no analytics */ } };

  function press(group, btn) {
    group.querySelectorAll('[aria-pressed]').forEach((b) => b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'));
  }

  // ---------- controls ----------
  $('nm-radius').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    press($('nm-radius'), b);
    S.km = S.unit === 'mi' ? Math.round(Number(b.dataset.mi) * KM_PER_MI) : Number(b.dataset.km);
    S.mi = Number(b.dataset.mi);
    track('nearme_filter', { filter: 'radius', value: S.unit === 'mi' ? S.mi + ' mi' : S.km + ' km' });
    search();
  });
  $('nm-unit').addEventListener('click', (e) => {
    const b = e.currentTarget;
    S.unit = S.unit === 'km' ? 'mi' : 'km';
    b.setAttribute('aria-pressed', S.unit === 'mi' ? 'true' : 'false');
    b.textContent = S.unit === 'mi' ? 'Show km' : 'Show miles';
    document.querySelectorAll('#nm-radius .u-km').forEach((x) => { x.hidden = S.unit === 'mi'; });
    document.querySelectorAll('#nm-radius .u-mi').forEach((x) => { x.hidden = S.unit === 'km'; });
    const on = document.querySelector('#nm-radius [aria-pressed="true"]');
    S.km = S.unit === 'mi' ? Math.round(Number(on.dataset.mi) * KM_PER_MI) : Number(on.dataset.km);
    track('nearme_filter', { filter: 'units', value: S.unit });
    search();
  });
  $('nm-cat').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    press($('nm-cat'), b); S.cat = b.dataset.cat; track('nearme_filter', { filter: 'category', value: S.cat || 'all' }); search();
  });
  $('nm-days').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    press($('nm-days'), b); S.days = Number(b.dataset.days); track('nearme_filter', { filter: 'days', value: String(S.days) }); search();
  });

  $('nm-locate').addEventListener('click', () => {
    if (!navigator.geolocation) { say('Your browser can\'t share a location. Pick a place instead.'); return; }
    say('Finding you...');
    navigator.geolocation.getCurrentPosition((p) => {
      // Rounded to ~1 km before it goes anywhere.
      S.lat = round2(p.coords.latitude); S.lng = round2(p.coords.longitude); S.label = 'you';
      $('nm-place').value = '';
      track('near_search', { how: 'location' });
      track('nearme_locate', {});
      search();
    }, (err) => {
      say(err && err.code === 1 ? 'Location is blocked. Allow it in your browser settings, or pick a place instead.' : 'Couldn\'t find your location. Pick a place instead.');
    }, { timeout: 12000, maximumAge: 600000 });
  });

  let cities = null;
  const fold = (t) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const loadCities = () => cities || (cities = fetch(CFG.cities).then((r) => r.json()).catch(() => []));
  const place = $('nm-place');
  place.addEventListener('focus', loadCities, { once: true });
  place.addEventListener('input', async () => {
    const q = fold(place.value.trim());
    if (q.length < 2) return;
    const list = await loadCities(), hits = [];
    for (const c of list) { if (fold(c[0]).startsWith(q)) { hits.push(c); if (hits.length >= 12) break; } }
    const dl = $('nm-cities');
    dl.replaceChildren(...hits.map((c) => { const o = document.createElement('option'); o.value = c[0] + ', ' + c[1]; return o; }));
  });
  $('nm-pick').addEventListener('submit', async () => {
    const v = fold(place.value.trim());
    if (!v) { say('Type a town or city.'); place.focus(); return; }
    const list = await loadCities();
    const [name, reg] = v.split(',').map((s) => s.trim());
    const c = list.find((x) => fold(x[0]) === name && (!reg || fold(x[1]).startsWith(reg)))
      || list.find((x) => fold(x[0]).startsWith(name));
    if (!c) { seq++; say(`We couldn't find "${place.value.trim()}". Try a bigger town nearby.`); return; }
    S.lat = round2(c[2]); S.lng = round2(c[3]); S.label = c[0] + ', ' + c[1];
    place.value = S.label;
    place.blur();
    track('near_search', { how: 'place' });
    search();
  });
  place.addEventListener('change', () => { if (cities && place.value.includes(',')) $('nm-pick').requestSubmit(); });

  // ---------- data ----------
  async function reports() {
    const q = new URLSearchParams({ lat: S.lat, lng: S.lng, radius_km: Math.min(250, Math.max(5, S.km)), days: S.days, limit: 100 });
    if (S.cat) q.set('category', S.cat);
    if (!noEndpoint) {
      const r = await fetch(CFG.api + '/v1/reports/nearby?' + q).catch(() => null);
      if (r && r.status === 429) throw new Error('slow');
      if (r && r.ok) return (await r.json()).reports || [];
      // A Worker without /v1/reports/nearby answers 404 with no CORS header, which the browser reports as a failed
      // fetch: use the feed for the rest of this visit.
      if (!r || r.status === 404) noEndpoint = true;
    }
    try { return await fromFeed(); } catch (e) { feed = null; throw new Error('api'); }
  }
  let noEndpoint = false;
  // Fallback: the public reports feed the full map uses (approved only, public ~5 km cell, ~100 km for living
  // traditions, first ~160 characters of the story, no links). Same filters and output as the endpoint.
  let feed = null;
  async function fromFeed() {
    feed = feed || fetch(CFG.api + '/api/reports.geojson').then((r) => (r.ok ? r.json() : { features: [] }));
    const since = new Date(Date.now() - S.days * 86400e3).toISOString().slice(0, 10);
    const out = [];
    for (const f of (await feed).features) {
      const p = f.properties, cat = p.c === 'other' ? 'other' : CFG.ufo.includes(p.c) ? 'ufo' : 'creature';
      if ((p.d || '') < since || (S.cat && S.cat !== cat)) continue;
      const lat = round2(f.geometry.coordinates[1]), lng = round2(f.geometry.coordinates[0]);
      const km = hav(S.lat, S.lng, lat, lng);
      if (km > S.km) continue;
      out.push({ id: p.id, category: cat, creature: p.c, creature_name: p.n, seen_date: p.d, place: p.t, lat, lng,
        precision_km: CFG.living.includes(p.c) ? 100 : 5, distance_km: Math.round(km), summary: p.s });
    }
    return out.sort((x, y) => (y.seen_date || '').localeCompare(x.seen_date || ''));
  }
  const tileCache = new Map();
  let tileIndex = null; // which 5-degree squares have any archive files, so empty ones are never requested
  const loadIndex = () => tileIndex || (tileIndex = fetch(CFG.tiles + 'index.json').then((r) => r.json()).then((d) => new Set(Object.keys(d.tiles))).catch(() => null));
  function tile(key) {
    if (!tileCache.has(key)) {
      tileCache.set(key, fetch(CFG.tiles + key + '.json').then((r) => (r.ok ? r.json() : { features: [] })).catch(() => ({ features: [] })));
    }
    return tileCache.get(key);
  }
  // Category of an archive file: every official layer is UFO files; old newspaper stories carry their own.
  function catOf(p) {
    if (p.src !== 'historic') return 'ufo';
    if (p.c) return CFG.ufo.includes(p.c) ? 'ufo' : 'creature';
    return /^airship/.test(p.k) ? 'ufo' : p.k === 'phantom-light' ? 'other' : 'creature';
  }
  let hist = null;
  const loadHist = () => hist || (hist = fetch(CFG.historic).then((r) => (r.ok ? r.json() : { features: [] }))
    .then((d) => d.features.map((f) => ({ ...f, properties: { ...f.properties, src: 'historic' } }))).catch(() => { hist = null; return []; }));
  async function archives() {
    const dlat = (S.km / R_KM) * (180 / Math.PI);
    const cos = Math.cos((S.lat * Math.PI) / 180);
    const dlon = cos < 0.05 ? 180 : Math.min(180, dlat / cos);
    const keys = new Set();
    for (let la = Math.floor((S.lat - dlat) / 5) * 5; la <= S.lat + dlat; la += 5) {
      if (la < -90 || la > 85) continue;
      for (let lo = Math.floor((S.lng - dlon) / 5) * 5; lo <= S.lng + dlon; lo += 5) keys.add(`${la}_${Math.floor(wrapLon(lo) / 5) * 5}`);
    }
    const have = await loadIndex();
    const tiles = await Promise.all([...keys].filter((k) => !have || have.has(k)).map(tile));
    tiles.push({ features: CFG.historic ? await loadHist() : [] });
    const out = [];
    for (const t of tiles) {
      for (const f of t.features) {
        if (S.cat && catOf(f.properties) !== S.cat) continue;
        const [lon, lat] = f.geometry.coordinates;
        const km = hav(S.lat, S.lng, lat, lon);
        // Area-only rings are kept when the circle reaches into the area at all (their centre can be far away).
        if (km <= S.km || (f.properties.src === 'bluebook_approx' && km <= S.km + 300)) out.push({ f, km });
      }
    }
    return out.sort((x, y) => x.km - y.km);
  }

  // ---------- map ----------
  function tint() {
    for (const layer of map.getStyle().layers) {
      const id = layer.id;
      try {
        if (layer.type === 'background') map.setPaintProperty(id, 'background-color', '#0F1F19');
        else if (/water/.test(id) && layer.type === 'fill') map.setPaintProperty(id, 'fill-color', '#0A1714');
        else if (/landcover|park|wood|forest|grass/.test(id) && layer.type === 'fill') map.setPaintProperty(id, 'fill-color', '#16302A');
        else if (/boundary/.test(id) && layer.type === 'line') map.setPaintProperty(id, 'line-color', '#3E5E50');
        else if (layer.type === 'symbol' && /place|label/.test(id)) {
          map.setPaintProperty(id, 'text-color', '#A9B98F');
          map.setPaintProperty(id, 'text-halo-color', '#0F1F19');
        }
      } catch (e) { /* layer without that property */ }
    }
  }
  const EMPTY = { type: 'FeatureCollection', features: [] };
  function ensureMap() {
    if (mapReady) return mapReady;
    $('nm-mapwrap').hidden = false;
    mapReady = new Promise((resolve) => {
      const start = () => {
        if (!window.maplibregl) { setTimeout(start, 100); return; }
        map = new maplibregl.Map({ container: 'nm-map', style: 'https://tiles.openfreemap.org/styles/dark', center: [S.lng, S.lat], zoom: 8,
          cooperativeGestures: true, minZoom: 2, maxZoom: 15, attributionControl: { compact: true } });
        map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
        map.on('load', () => {
          tint();
          for (const id of ['circle', 'archive', 'reports', 'centre', 'flap']) map.addSource(id, { type: 'geojson', data: EMPTY });
          map.addLayer({ id: 'flap-fill', type: 'fill', source: 'flap', paint: { 'fill-color': '#E4572E', 'fill-opacity': 0.1 } });
          map.addLayer({ id: 'flap-line', type: 'line', source: 'flap', paint: { 'line-color': '#FF7A50', 'line-width': 2.5 } });
          map.addLayer({ id: 'circle-fill', type: 'fill', source: 'circle', paint: { 'fill-color': '#F2B33D', 'fill-opacity': 0.05 } });
          map.addLayer({ id: 'circle-line', type: 'line', source: 'circle', paint: { 'line-color': '#F2B33D', 'line-opacity': 0.6, 'line-width': 1.5, 'line-dasharray': [2, 2] } });
          // Area-only Blue Book files: big faded hollow rings, never pins.
          map.addLayer({ id: 'arch-ring', type: 'circle', source: 'archive', filter: ['==', ['get', 'src'], 'bluebook_approx'], paint: {
            'circle-color': '#F2B33D', 'circle-opacity': 0.06, 'circle-stroke-color': '#F2B33D', 'circle-stroke-opacity': 0.5, 'circle-stroke-width': 1.5,
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 18, 8, 48] } });
          map.addLayer({ id: 'arch-pt', type: 'circle', source: 'archive', filter: ['!=', ['get', 'src'], 'bluebook_approx'], paint: {
            'circle-color': ['match', ['get', 'src'], 'faa', ARCH.faa.color, 'pursue', ARCH.pursue.color, 'canada', ARCH.canada.color, 'greece', ARCH.greece.color,
              'historic', ARCH.historic.color, ARCH.bluebook.color],
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['case', ['==', ['get', 'a'], 1], 9, 4], 12, ['case', ['==', ['get', 'a'], 1], 22, 8]],
            'circle-opacity': ['case', ['==', ['get', 'a'], 1], 0.12, 0.85],
            'circle-stroke-color': ['case', ['==', ['get', 'a'], 1], ['match', ['get', 'src'], 'historic', ARCH.historic.color, '#F2B33D'], '#13261F'], 'circle-stroke-width': 1.5 } });
          map.addLayer({ id: 'rep', type: 'circle', source: 'reports', paint: {
            'circle-color': ['get', 'c'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 7, 12, 12],
            'circle-stroke-color': '#F6F0E2', 'circle-stroke-width': 2.5 } });
          map.addLayer({ id: 'centre', type: 'circle', source: 'centre', paint: { 'circle-color': '#F6F0E2', 'circle-radius': 5, 'circle-stroke-color': '#13261F', 'circle-stroke-width': 2 } });
          for (const id of ['arch-ring', 'arch-pt', 'rep']) {
            map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
            map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
          }
          map.on('click', 'rep', (e) => popup(e.features[0].geometry.coordinates, reportNodes(JSON.parse(e.features[0].properties.j))));
          map.on('click', 'arch-pt', (e) => popup(e.features[0].geometry.coordinates, archiveNodes(e.features[0].properties)));
          map.on('click', 'arch-ring', (e) => popup(e.features[0].geometry.coordinates, archiveNodes(e.features[0].properties)));
          resolve(map);
        });
      };
      start();
    });
    return mapReady;
  }
  function popup(lngLat, nodes) {
    const div = el('div', 'pop'); div.append(...nodes);
    new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(lngLat).setDOMContent(div).addTo(map);
  }
  function circle(lat, lng, km) {
    const pts = [], d = km / R_KM, r = Math.PI / 180, la = lat * r, lo = lng * r;
    for (let i = 0; i <= 72; i++) {
      const b = (i / 72) * 2 * Math.PI;
      const la2 = Math.asin(Math.sin(la) * Math.cos(d) + Math.cos(la) * Math.sin(d) * Math.cos(b));
      const lo2 = lo + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(la), Math.cos(d) - Math.sin(la) * Math.sin(la2));
      pts.push([lo2 / r, la2 / r]); // not wrapped: MapLibre draws across the antimeridian
    }
    return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [pts] }, properties: {} };
  }

  // ---------- popups and list ----------
  function reportNodes(r) {
    const n = [el('div', 'pop-kind', `Reader report, ${niceDate(r.seen_date)}${r.date_approx ? ' (about)' : ''}`), el('p', 'pop-h', r.creature_name || 'Something strange')];
    if (r.place) n.push(el('p', 'pop-meta', r.place + ' · ' + dist(r.distance_km) + ' away'));
    n.push(el('p', '', r.summary));
    if (r.precision_km >= 100) n.push(el('p', 'approx', 'Shown to the nearest region only, out of respect for a living tradition.'));
    n.push(a(CFG.reports + encodeURIComponent(r.id) + '/', 'Read the report'));
    return n;
  }
  function archiveNodes(p) {
    const k = ARCH[p.src] || ARCH.bluebook;
    const n = [el('div', 'pop-kind', k.label + (p.w ? ', ' + p.w : ''))];
    if (p.src === 'bluebook_approx') {
      n.push(el('p', 'pop-h', `${p.n} file${p.n == 1 ? '' : 's'} somewhere in ${p.t}`));
      n.push(el('p', 'approx', `Location approximate: these files name only ${p.t}, not a town, so they are not pinned to a spot.`));
      if (p.u) n.push(a(CFG.base + p.u, 'See the files'));
      return n;
    }
    if (p.src === 'canada') {
      n.push(el('p', 'pop-h', p.t + (p.r && p.a != 1 ? ', ' + p.r : '')));
      n.push(el('p', 'pop-meta', `${p.n} report${p.n == 1 ? '' : 's'} since 1989 · ${p.nu} unexplained`));
      if (p.u) n.push(a(CFG.base + p.u, 'Read the reports'));
      return n;
    }
    if (p.src === 'historic') {
      n[0].textContent = 'Old newspaper story, ' + p.d;
      n.push(el('p', 'pop-h', p.t), el('p', 'pop-meta', p.p));
      if (p.a == 1) n.push(el('p', 'approx', 'Location approximate: the papers only named the area.'));
      n.push(a(histUrl(p), 'Read the story'));
      return n;
    }
    if (p.src === 'greece') {
      n.push(el('p', 'pop-h', p.t + ', ' + p.r), el('p', 'pop-meta', p.k + ' · ' + p.h));
      if (p.d) n.push(el('p', '', String(p.d)));
      n.push(a(p.u, 'Read the case'));
      return n;
    }
    n.push(el('p', 'pop-h', p.src === 'pursue' && p.r ? p.r : p.t || 'Report'));
    if (p.r && p.src !== 'pursue' && p.r !== p.t) n.push(el('p', 'pop-meta', p.r));
    if (p.d) n.push(el('p', '', String(p.d).slice(0, 220)));
    if (p.a == 1) n.push(el('p', 'approx', 'Location approximate: the file names only the state, country or sea, so this ring marks the area, not the spot.'));
    if (p.src === 'bluebook' && p.id) n.push(a('https://catalog.archives.gov/id/' + p.id, 'Read the Air Force file'));
    else if (p.u) n.push(a(p.u, 'Open the official file'));
    return n;
  }

  const histUrl = (p) => (CFG.htopics[p.k] || CFG.base + '/history/') + '#h-' + encodeURIComponent(p.id);

  // ---------- then and now (eras) ----------
  const era = () => ERAS[S.era] || ERAS[0];
  const yearOf = (p) => { const y = parseInt(p.y || p.w, 10); return Number.isFinite(y) ? y : null; };
  function inEra(p, e) {
    if (e.id === 'all') return true;
    if ((e.src || []).includes(p.src)) return true;
    if (p.src === 'greece' && e.years) { const y = yearOf(p); return y != null && y >= e.years[0] && y <= e.years[1]; }
    return false;
  }
  const repsIn = (e) => e.id === 'all' || (e.src || []).includes('reports');
  function eraCounts(reps, arch) {
    return ERAS.map((e) => (repsIn(e) ? reps.length : 0) + arch.filter((x) => inEra(x.f.properties, e)).length);
  }
  function showEra(i, from) {
    S.era = Math.max(0, Math.min(ERAS.length - 1, i));
    const e = era(), txt = e.span ? `${e.name}, ${e.span}` : e.name;
    const range = $('nm-era-range');
    if (range) { if (from !== 'range') range.value = String(S.era); range.setAttribute('aria-valuetext', txt); }
    if ($('nm-era-out')) $('nm-era-out').textContent = txt;
    document.querySelectorAll('#nm-eras .nm-era').forEach((b) => b.setAttribute('aria-pressed', Number(b.dataset.i) === S.era ? 'true' : 'false'));
  }
  function setEra(i, from) {
    showEra(i, from);
    track('nearme_filter', { filter: 'era', value: era().id });
    if (S.lat == null) { say('Use your location or pick a place first, then slide through the eras.'); return; }
    remember();
    if (last) { render(last.reps, last.arch); draw(last.reps, last.arch); }
  }
  if ($('nm-era-range')) {
    $('nm-era-range').addEventListener('input', (e) => setEra(Number(e.target.value), 'range'));
    $('nm-eras').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) setEra(Number(b.dataset.i), 'button'); });
  }

  // The report form opens on this area (?at=), so a reader near the map can file what they saw in two taps.
  const reportHere = () => CFG.report + '?' + new URLSearchParams({ at: `${S.lat},${S.lng}`, ...(S.label && S.label !== 'you' ? { place: S.label } : {}) });
  function render(reps, arch) {
    last = { reps, arch };
    const e = era(), withReps = repsIn(e);
    const counts = eraCounts(reps, arch);
    document.querySelectorAll('#nm-eras .nm-era').forEach((b) => {
      const n = counts[Number(b.dataset.i)] || 0;
      b.querySelector('.nm-era-n').textContent = n.toLocaleString();
      b.classList.toggle('nm-era-zero', !n);
    });
    $('nm-era-st').textContent = `${e.name}: ${counts[S.era].toLocaleString()} within ${dist(S.km)}`;
    arch = arch.filter((x) => inEra(x.f.properties, e));
    results.replaceChildren();
    const bar = el('p', 'nm-actions');
    bar.append(a(reportHere(), 'Report a sighting from here', 'btn nm-report'));
    if (remembered()) {
      const forget = el('button', 'nm-forget', 'Forget this place');
      forget.type = 'button';
      forget.addEventListener('click', () => { try { localStorage.removeItem(KEY); } catch (e) { /* storage blocked */ } forget.remove(); });
      bar.append(forget);
    }
    results.append(bar);
    const where = S.label === 'you' ? 'you' : S.label;
    const h = el('h2', 'nm-res-h', reps.length ? `${reps.length} reader report${reps.length === 1 ? '' : 's'} within ${dist(S.km)} of ${where}` : '');
    if (!withReps) {
      if (!arch.length) {
        const box = el('div', 'nm-empty');
        box.append(el('p', 'nm-empty-h', `Nothing from this era (${e.name}, ${e.span}) within ${dist(S.km)}.`),
          el('p', 'nm-nudge', 'Try a bigger circle or slide to another era.'));
        results.append(box);
      }
    } else if (reps.length) {
      results.append(h);
      const ul = el('ul', 'nm-cards nm-cards-live');
      for (const r of reps) {
        const li = el('li', 'nm-card'), link = a(CFG.reports + encodeURIComponent(r.id) + '/', null);
        const dot = el('span', 'nm-dot'); dot.style.background = REP[r.category] || REP.other;
        const body = el('span', 'nm-card-body');
        body.append(el('b', '', r.creature_name || 'Something strange'),
          el('span', 'nm-meta', [r.place, niceDate(r.seen_date), dist(r.distance_km) + ' away'].filter(Boolean).join(' · ')),
          el('span', 'nm-snip', r.summary));
        link.append(dot, body); li.append(link); ul.append(li);
      }
      results.append(ul);
    } else {
      const box = el('div', 'nm-empty');
      box.append(el('p', 'nm-empty-h', arch.length ? 'No reader reports here yet. Here\'s what the archives show.' : 'No reader reports here yet.'));
      const nudge = el('p', 'nm-nudge');
      nudge.append('Seen something around here? ', a(reportHere(), 'Report it'), ' and it could be the first pin on this map.');
      box.append(nudge);
      results.append(box);
    }
    if (arch.length) {
      const counts = {};
      const head = e.id === 'all' ? `From the archives, within ${dist(S.km)} (every year)` : `${e.name} (${e.span}), within ${dist(S.km)}`;
      for (const { f } of arch) counts[f.properties.src] = (counts[f.properties.src] || 0) + 1;
      results.append(el(withReps ? 'h3' : 'h2', withReps ? 'nm-res-h3' : 'nm-res-h', head));
      const p = el('p', 'nm-arch-counts');
      for (const k of ['historic', 'bluebook', 'faa', 'pursue', 'canada', 'greece', 'bluebook_approx']) {
        if (!counts[k]) continue;
        const c = el('span', 'nm-pill'); c.style.setProperty('--c', ARCH[k].color);
        c.textContent = `${counts[k].toLocaleString()} ${PILL[k][counts[k] === 1 ? 0 : 1]}`;
        p.append(c);
      }
      results.append(p);
      const ul = el('ul', 'nm-arch');
      const list = arch.filter((x) => x.f.properties.src !== 'bluebook_approx');
      for (const { f, km } of list.slice(0, 12)) {
        const pr = f.properties, li = el('li');
        const title = pr.src === 'canada' ? `${pr.t}: ${pr.n} report${pr.n == 1 ? '' : 's'} since 1989` : (pr.src === 'pursue' && pr.r ? pr.r : pr.t);
        const b = el('b', '', pr.src === 'historic' ? null : title);
        if (pr.src === 'historic') b.append(a(histUrl(pr), title));
        li.append(b, el('span', 'nm-meta', [(ARCH[pr.src] || ARCH.bluebook).label, pr.src === 'historic' ? pr.d + ', ' + pr.p : pr.w, dist(km) + ' away'].filter(Boolean).join(' · ')));
        li.style.setProperty('--c', (ARCH[pr.src] || ARCH.bluebook).color);
        ul.append(li);
      }
      results.append(ul);
      if (list.length > 12) results.append(el('p', 'nm-more', `The nearest 12 of ${list.length.toLocaleString()}. Tap the dots on the map for the rest.`));
    }
  }

  // ---------- search ----------
  // Last place and filters, on this device only, so the app reopens where the reader left off.
  const KEY = 'ea-near';
  function remember() {
    try { localStorage.setItem(KEY, JSON.stringify({ lat: S.lat, lng: S.lng, label: S.label, km: S.km, mi: S.mi, unit: S.unit, cat: S.cat, days: S.days, era: ERAS[S.era] ? ERAS[S.era].id : 'all' })); } catch (e) { /* private mode */ }
  }
  function remembered() { try { return !!localStorage.getItem(KEY); } catch (e) { return false; } }
  async function search() {
    if (S.lat == null) { say('Use your location or pick a place to see what\'s been reported nearby.'); return; }
    remember();
    alertUi();
    const my = ++seq;
    say(`Looking within ${dist(S.km)} of ${S.label === 'you' ? 'you' : S.label}...`);
    const mp = ensureMap();
    let reps = [], arch = [], failed = '';
    try {
      [reps, arch] = await Promise.all([reports().catch((e) => { failed = e.message; return []; }), archives()]);
    } catch (e) { failed = 'api'; }
    if (my !== seq) return; // a newer search started
    say(failed === 'slow' ? 'Lots of searches just now. Wait a minute and try again.'
      : failed ? 'Reader reports couldn\'t load just now (are you offline?). Showing the archives.' : '');
    render(reps, arch);
    flap(my);
    await mp;
    if (my !== seq) return;
    map.getSource('circle').setData(circle(S.lat, S.lng, S.km));
    map.getSource('centre').setData({ type: 'Feature', geometry: { type: 'Point', coordinates: [S.lng, S.lat] }, properties: {} });
    draw(reps, arch);
    const d = (S.km / R_KM) * (180 / Math.PI), cos = Math.max(0.1, Math.cos((S.lat * Math.PI) / 180));
    map.fitBounds([[S.lng - d / cos, Math.max(-85, S.lat - d)], [S.lng + d / cos, Math.min(85, S.lat + d)]], { padding: 24, duration: 600 });
  }
  // Points on the map for the chosen era.
  function draw(reps, arch) {
    if (!map || !map.getSource('reports')) return;
    const e = era();
    map.getSource('reports').setData({ type: 'FeatureCollection', features: (repsIn(e) ? reps : []).map((r) => ({ type: 'Feature',
      geometry: { type: 'Point', coordinates: [near(r.lng), r.lat] }, properties: { c: REP[r.category] || REP.other, j: JSON.stringify(r) } })) });
    map.getSource('archive').setData({ type: 'FeatureCollection', features: arch.filter((x) => inEra(x.f.properties, e)).map(({ f }) => ({ ...f,
      geometry: { type: 'Point', coordinates: [near(f.geometry.coordinates[0]), f.geometry.coordinates[1]] } })) });
  }

  // ---------- flap in progress (/v1/clusters) ----------
  // Only asked when the build saw the endpoint answer. A 404, a network error or bad JSON just leaves the slot empty.
  let noClusters = !CFG.clusters;
  async function flap(my) {
    const slot = $('nm-flap');
    slot.replaceChildren();
    if (map && map.getSource('flap')) map.getSource('flap').setData(EMPTY);
    if (noClusters) return;
    let d = null;
    try {
      const q = new URLSearchParams({ lat: S.lat, lng: S.lng, radius_km: Math.min(500, Math.max(50, S.km)) });
      const r = await fetch(CFG.api + '/v1/clusters?' + q);
      if (r.status === 404) { noClusters = true; return; }
      if (!r.ok) return;
      d = await r.json();
    } catch (e) { return; }
    if (my !== seq || !d || !Array.isArray(d.clusters) || !d.clusters.length) return;
    const c = d.clusters[0], days = (d.rule && d.rule.window_days) || 3;
    if (!(c.count > 0) || !Number.isFinite(c.lat) || !Number.isFinite(c.lng)) return;
    const box = el('div', 'nm-flap');
    const where = c.place ? `near ${c.place}` : 'in this region';
    const kinds = [['creature', 'creature', 'creatures'], ['ufo', 'UFO', 'UFOs'], ['other', 'something else', 'something else']]
      .filter(([k]) => c.categories && c.categories[k]).map(([k, one, many]) => `${c.categories[k]} ${c.categories[k] === 1 ? one : many}`);
    const names = (c.creatures || []).map((x) => (x.count > 1 ? `${x.name} (${x.count})` : x.name));
    const when = c.first_seen === c.last_seen ? `Seen ${niceDate(c.last_seen)}` : `Seen ${niceDate(c.first_seen)} to ${niceDate(c.last_seen)}`;
    const away = c.distance_km < 5 ? 'right around here' : `about ${dist(c.distance_km)} from ${S.label === 'you' ? 'you' : S.label}`;
    box.append(el('p', 'nm-flap-k', 'Flap in progress'),
      el('h2', 'nm-flap-h', `${c.count} reports ${where} in the last ${days} days`),
      el('p', 'nm-flap-m', [when, kinds.join(', '), away].filter(Boolean).join(' · ')));
    if (names.length) box.append(el('p', 'nm-flap-m', names.join(', ')));
    const acts = el('p', 'nm-flap-acts');
    const see = el('button', 'btn nm-flap-see', 'Show them');
    see.type = 'button';
    see.addEventListener('click', () => {
      track('nearme_flap', { action: 'show' });
      const db = document.querySelector('#nm-days [data-days="7"]');
      if (db) { press($('nm-days'), db); S.days = 7; }
      const ti = ERAS.findIndex((x) => x.id === 'today');
      showEra(ti < 0 ? 0 : ti, 'flap');
      search().then(() => { if (map) map.flyTo({ center: [near(c.lng), c.lat], zoom: 8.5 }); $('nm-results').scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    });
    acts.append(see, a(reportHere(), 'Seen something too? Report it', 'btn btn-ghost nm-flap-rep'));
    box.append(acts);
    if (c.precision_km >= 100) box.append(el('p', 'nm-flap-note', 'Some of these are shown to the nearest region only.'));
    slot.append(box);
    track('nearme_flap', { action: 'shown', count: c.count });
    await mapReady;
    if (my === seq && map.getSource('flap')) map.getSource('flap').setData(circle(c.lat, near(c.lng), c.precision_km >= 100 ? 100 : 25));
  }

  // ---------- sighting alerts (Web Push for the saved area) ----------
  // The subscription id and its manage token live only on this device. Alerts follow the saved place, never the
  // phone's position. Turnstile runs once, when alerts are first turned on.
  const AKEY = 'ea-alert';
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const standaloneNow = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const alertSaved = () => { try { return JSON.parse(localStorage.getItem(AKEY) || 'null'); } catch (e) { return null; } };
  const alertSt = (t) => { $('nm-alert-st').textContent = t; };
  const u8 = (b) => Uint8Array.from(atob((b + '==='.slice((b.length + 3) % 4)).replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
  const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const radiusKm = () => Math.min(250, Math.max(5, S.km));
  function alertUi() {
    if (!CFG.vapid || S.lat == null) return;
    $('nm-alert').hidden = false;
    const a = alertSaved();
    const here = a && Math.abs(a.lat - S.lat) < 0.005 && Math.abs(a.lng - S.lng) < 0.005 && a.radius_km === radiusKm() && a.categories === (S.cat || '');
    $('nm-alert-btn').textContent = !a ? 'Alert me about new reports here' : here ? 'Turn off alerts' : 'Move my alerts here';
    $('nm-alert-btn').dataset.mode = !a ? 'on' : here ? 'off' : 'move';
    if (a) alertSt(`Alerts are on for ${a.label || 'your saved place'} (${a.units === 'mi' ? Math.round(a.radius_km / KM_PER_MI) + ' mi' : a.radius_km + ' km'}).`);
    else alertSt('');
  }
  let tsLoad = null;
  const turnstileToken = () => {
    tsLoad = tsLoad || new Promise((res, rej) => {
      if (window.turnstile) return res();
      const sc = document.createElement('script');
      sc.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'; sc.async = true; sc.onload = res; sc.onerror = rej;
      document.head.append(sc);
    });
    return tsLoad.then(() => new Promise((res) => {
      const slot = $('nm-alert-ts');
      slot.replaceChildren();
      window.turnstile.render(slot, { sitekey: CFG.sitekey, size: 'compact', theme: 'light', callback: (t) => res(t) });
    }));
  };
  const post = (path, body) => fetch(CFG.api + path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    .then(async (r) => ({ status: r.status, data: await r.json().catch(() => ({})) })).catch(() => ({ status: 0, data: { state: 'offline' } }));
  $('nm-alert-btn').addEventListener('click', async (e) => {
    const b = e.currentTarget, mode = b.dataset.mode;
    if (ios && !standaloneNow()) { alertSt('On iPhone, add this page to your Home Screen first (Share, then Add to Home Screen), then open it from there and tap this again.'); return; }
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) { alertSt('This browser can\'t show notifications. Try Chrome, Edge, Firefox or Safari on a newer phone.'); return; }
    b.disabled = true;
    try {
      const a = alertSaved();
      const area = { lat: S.lat, lng: S.lng, radius_km: radiusKm(), categories: S.cat || '', units: S.unit };
      const label = S.label === 'you' ? 'your location' : S.label;
      if (mode === 'off' && a) {
        alertSt('Turning alerts off...');
        await post('/v1/push/unsubscribe', { id: a.id, manage_token: a.manage_token });
        const reg = await navigator.serviceWorker.ready, sub = await reg.pushManager.getSubscription();
        if (sub) await sub.unsubscribe();
        localStorage.removeItem(AKEY);
        track('alert_unsubscribe', {});
        alertUi(); alertSt('Alerts are off. Nothing more will be sent.');
        return;
      }
      if (mode === 'move' && a) {
        alertSt('Moving your alerts...');
        const r = await post('/v1/push/update', { id: a.id, manage_token: a.manage_token, ...area });
        if (r.status === 200) {
          localStorage.setItem(AKEY, JSON.stringify({ ...a, ...area, label }));
          track('alert_subscribe', { how: 'move', radius_km: area.radius_km, category: area.categories || 'all' });
          alertUi(); return;
        }
        if (r.status !== 404) throw new Error(r.status === 0 ? 'No connection. Try again with signal.' : 'That didn\'t work. Try again in a minute.');
        localStorage.removeItem(AKEY); // the subscription is gone on our side: sign up again below
      }
      alertSt('Asking for permission to send notifications...');
      if (await Notification.requestPermission() !== 'granted') throw new Error('Notifications are blocked for this site. Allow them in your browser or phone settings, then try again.');
      const reg = await navigator.serviceWorker.ready;
      const sub = (await reg.pushManager.getSubscription()) || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u8(CFG.vapid) });
      alertSt('Quick spam check...');
      const token = await turnstileToken();
      const r = await post('/v1/push/subscribe', { endpoint: sub.endpoint, p256dh: b64(sub.getKey('p256dh')), auth: b64(sub.getKey('auth')), ...area, turnstile: token });
      $('nm-alert-ts').replaceChildren();
      if (r.status !== 201) throw new Error(r.status === 0 ? 'No connection. Try again with signal.' : r.data.state === 'slow' ? 'Too many tries. Wait an hour.' : 'That didn\'t work. Try again in a minute.');
      localStorage.setItem(AKEY, JSON.stringify({ id: r.data.id, manage_token: r.data.manage_token, ...area, label }));
      track('alert_subscribe', { how: 'new', radius_km: area.radius_km, category: area.categories || 'all' });
      alertUi();
    } catch (err) {
      alertSt(err.message || 'That didn\'t work. Try again.');
    } finally { b.disabled = false; }
  });

  // A report written with no signal on the report form waits on this device: offer to send it from here too.
  function queuedBanner() {
    let n = 0;
    try { n = JSON.parse(localStorage.getItem('ea-report-queue') || '[]').length; } catch (e) { n = 0; }
    let bar = $('nm-queued');
    if (!n) { if (bar) bar.remove(); return; }
    if (!bar) {
      bar = document.createElement('p'); bar.id = 'nm-queued'; bar.className = 'nm-queued';
      $('nm-status').before(bar);
    }
    bar.innerHTML = '';
    const a = document.createElement('a'); a.href = CFG.report + '?source=queued'; a.className = 'btn'; a.textContent = 'Send it now';
    bar.append(`You have ${n} report${n === 1 ? '' : 's'} waiting to send. `, a);
  }
  queuedBanner();
  window.addEventListener('online', queuedBanner);
  if (navigator.serviceWorker) navigator.serviceWorker.addEventListener('message', (e) => { if (e.data && e.data.type === 'send-queued') queuedBanner(); });

  // Install: only offered when the browser says the site is installable (Chrome/Edge fire beforeinstallprompt), never
  // as a pop-up. iPhone Safari has no such event, so it gets a one-line Add to Home Screen tip. Hidden inside the app.
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  let installEvt = null;
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); installEvt = e; if (!standalone) $('nm-install').hidden = false; });
  window.addEventListener('appinstalled', () => { $('nm-install').hidden = true; track('app_installed', {}); track('app_install', { how: 'prompt' }); });
  $('nm-install-btn').addEventListener('click', async () => {
    if (!installEvt) return;
    installEvt.prompt();
    const choice = await installEvt.userChoice.catch(() => null);
    track('app_install_prompt', { outcome: choice ? choice.outcome : 'unknown' });
    installEvt = null; $('nm-install').hidden = true;
  });
  if (!standalone && /iPhone|iPad|iPod/.test(navigator.userAgent) && !/CriOS|FxiOS|EdgiOS/.test(navigator.userAgent)) $('nm-ios').hidden = false;

  // Returning visitor (and the installed app): reopen the last place with the same filters. Search engines have no
  // saved place, so they always get the plain page.
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { saved = null; }
  if (saved && Number.isFinite(saved.lat) && Number.isFinite(saved.lng)) {
    Object.assign(S, { lat: saved.lat, lng: saved.lng, label: saved.label === 'you' ? 'your last location' : saved.label || 'your last place', cat: saved.cat || '', days: saved.days || 30,
      unit: saved.unit === 'mi' ? 'mi' : 'km' });
    if (S.unit === 'mi') {
      $('nm-unit').setAttribute('aria-pressed', 'true'); $('nm-unit').textContent = 'Show km';
      document.querySelectorAll('#nm-radius .u-km').forEach((x) => { x.hidden = true; });
      document.querySelectorAll('#nm-radius .u-mi').forEach((x) => { x.hidden = false; });
    }
    const rb = document.querySelector(S.unit === 'mi' ? `#nm-radius [data-mi="${saved.mi}"]` : `#nm-radius [data-km="${saved.km}"]`);
    if (rb) { press($('nm-radius'), rb); S.km = S.unit === 'mi' ? Math.round(Number(rb.dataset.mi) * KM_PER_MI) : Number(rb.dataset.km); S.mi = Number(rb.dataset.mi); }
    const cb = document.querySelector(`#nm-cat [data-cat="${CSS.escape(S.cat)}"]`), db = document.querySelector(`#nm-days [data-days="${S.days}"]`);
    if (cb) press($('nm-cat'), cb);
    if (db) press($('nm-days'), db);
    if (S.label !== 'you') place.value = S.label;
    const ei = ERAS.findIndex((x) => x.id === saved.era);
    if (ei > 0) showEra(ei, 'saved');
    search();
  }
})();

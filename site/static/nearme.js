// /near-me/: the site page and the app's home screen. Nothing runs until a control is used (SEO-safe: the page is
// complete HTML without this file). Then: reader reports from the Worker's /v1/reports/nearby, archive files from
// the 5-degree tiles in /data/near/, a MapLibre map in the same style as the full map, and a list under it.
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
  };
  const PILL = { bluebook: ['Air Force file', 'Air Force files'], faa: ['FAA pilot report', 'FAA pilot reports'], pursue: ['Pentagon file', 'Pentagon files'],
    canada: ['Canadian UFO Survey town', 'Canadian UFO Survey towns'], bluebook_approx: ['area-only Air Force group', 'area-only Air Force groups'] };
  const S = { lat: null, lng: null, label: '', km: 50, mi: 30, unit: 'km', cat: '', days: 30 };
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
    search();
  });
  $('nm-cat').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    press($('nm-cat'), b); S.cat = b.dataset.cat; search();
  });
  $('nm-days').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    press($('nm-days'), b); S.days = Number(b.dataset.days); search();
  });

  $('nm-locate').addEventListener('click', () => {
    if (!navigator.geolocation) { say('Your browser can\'t share a location. Pick a place instead.'); return; }
    say('Finding you...');
    navigator.geolocation.getCurrentPosition((p) => {
      // Rounded to ~1 km before it goes anywhere.
      S.lat = round2(p.coords.latitude); S.lng = round2(p.coords.longitude); S.label = 'you';
      $('nm-place').value = '';
      track('near_search', { how: 'location' });
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
    const r = await fetch(CFG.api + '/v1/reports/nearby?' + q);
    if (r.status === 429) throw new Error('slow');
    if (!r.ok) throw new Error('api');
    return (await r.json()).reports || [];
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
  async function archives() {
    if (S.cat && S.cat !== 'ufo') return []; // the archives are all UFO files
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
    const out = [];
    for (const t of tiles) {
      for (const f of t.features) {
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
          for (const id of ['circle', 'archive', 'reports', 'centre']) map.addSource(id, { type: 'geojson', data: EMPTY });
          map.addLayer({ id: 'circle-fill', type: 'fill', source: 'circle', paint: { 'fill-color': '#F2B33D', 'fill-opacity': 0.05 } });
          map.addLayer({ id: 'circle-line', type: 'line', source: 'circle', paint: { 'line-color': '#F2B33D', 'line-opacity': 0.6, 'line-width': 1.5, 'line-dasharray': [2, 2] } });
          // Area-only Blue Book files: big faded hollow rings, never pins.
          map.addLayer({ id: 'arch-ring', type: 'circle', source: 'archive', filter: ['==', ['get', 'src'], 'bluebook_approx'], paint: {
            'circle-color': '#F2B33D', 'circle-opacity': 0.06, 'circle-stroke-color': '#F2B33D', 'circle-stroke-opacity': 0.5, 'circle-stroke-width': 1.5,
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 18, 8, 48] } });
          map.addLayer({ id: 'arch-pt', type: 'circle', source: 'archive', filter: ['!=', ['get', 'src'], 'bluebook_approx'], paint: {
            'circle-color': ['match', ['get', 'src'], 'faa', ARCH.faa.color, 'pursue', ARCH.pursue.color, 'canada', ARCH.canada.color, ARCH.bluebook.color],
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['case', ['==', ['get', 'a'], 1], 9, 4], 12, ['case', ['==', ['get', 'a'], 1], 22, 8]],
            'circle-opacity': ['case', ['==', ['get', 'a'], 1], 0.12, 0.85],
            'circle-stroke-color': ['case', ['==', ['get', 'a'], 1], '#F2B33D', '#13261F'], 'circle-stroke-width': 1.5 } });
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
    n.push(a(CFG.reports + encodeURIComponent(r.id), 'Read the report'));
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
    n.push(el('p', 'pop-h', p.src === 'pursue' && p.r ? p.r : p.t || 'Report'));
    if (p.r && p.src !== 'pursue' && p.r !== p.t) n.push(el('p', 'pop-meta', p.r));
    if (p.d) n.push(el('p', '', String(p.d).slice(0, 220)));
    if (p.a == 1) n.push(el('p', 'approx', 'Location approximate: the file names only the state, country or sea, so this ring marks the area, not the spot.'));
    if (p.src === 'bluebook' && p.id) n.push(a('https://catalog.archives.gov/id/' + p.id, 'Read the Air Force file'));
    else if (p.u) n.push(a(p.u, 'Open the official file'));
    return n;
  }

  function render(reps, arch) {
    results.replaceChildren();
    const where = S.label === 'you' ? 'you' : S.label;
    const h = el('h2', 'nm-res-h', reps.length ? `${reps.length} reader report${reps.length === 1 ? '' : 's'} within ${dist(S.km)} of ${where}` : '');
    if (reps.length) {
      results.append(h);
      const ul = el('ul', 'nm-cards nm-cards-live');
      for (const r of reps) {
        const li = el('li', 'nm-card'), link = a(CFG.reports + encodeURIComponent(r.id), null);
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
      nudge.append('Seen something around here? ', a(CFG.report, 'Report it'), ' and it could be the first pin on this map.');
      box.append(nudge);
      results.append(box);
    }
    if (arch.length) {
      const counts = {};
      for (const { f } of arch) counts[f.properties.src] = (counts[f.properties.src] || 0) + 1;
      results.append(el('h3', 'nm-res-h3', `From the archives, within ${dist(S.km)} (every year)`));
      const p = el('p', 'nm-arch-counts');
      for (const k of ['bluebook', 'faa', 'pursue', 'canada', 'bluebook_approx']) {
        if (!counts[k]) continue;
        const c = el('span', 'nm-pill'); c.style.setProperty('--c', ARCH[k].color);
        c.textContent = `${counts[k].toLocaleString()} ${PILL[k][counts[k] === 1 ? 0 : 1]}`;
        p.append(c);
      }
      results.append(p);
      const ul = el('ul', 'nm-arch');
      for (const { f, km } of arch.filter((x) => x.f.properties.src !== 'bluebook_approx').slice(0, 12)) {
        const pr = f.properties, li = el('li');
        const title = pr.src === 'canada' ? `${pr.t}: ${pr.n} report${pr.n == 1 ? '' : 's'} since 1989` : (pr.src === 'pursue' && pr.r ? pr.r : pr.t);
        li.append(el('b', '', title), el('span', 'nm-meta', [(ARCH[pr.src] || ARCH.bluebook).label, pr.w, dist(km) + ' away'].filter(Boolean).join(' · ')));
        li.style.setProperty('--c', (ARCH[pr.src] || ARCH.bluebook).color);
        ul.append(li);
      }
      results.append(ul);
    }
  }

  // ---------- search ----------
  async function search() {
    if (S.lat == null) { say('Use your location or pick a place to see what\'s been reported nearby.'); return; }
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
    await mp;
    if (my !== seq) return;
    map.getSource('circle').setData(circle(S.lat, S.lng, S.km));
    map.getSource('centre').setData({ type: 'Feature', geometry: { type: 'Point', coordinates: [S.lng, S.lat] }, properties: {} });
    map.getSource('reports').setData({ type: 'FeatureCollection', features: reps.map((r) => ({ type: 'Feature',
      geometry: { type: 'Point', coordinates: [near(r.lng), r.lat] }, properties: { c: REP[r.category] || REP.other, j: JSON.stringify(r) } })) });
    map.getSource('archive').setData({ type: 'FeatureCollection', features: arch.map(({ f }) => ({ ...f,
      geometry: { type: 'Point', coordinates: [near(f.geometry.coordinates[0]), f.geometry.coordinates[1]] } })) });
    const d = (S.km / R_KM) * (180 / Math.PI), cos = Math.max(0.1, Math.cos((S.lat * Math.PI) / 180));
    map.fitBounds([[S.lng - d / cos, Math.max(-85, S.lat - d)], [S.lng + d / cos, Math.min(85, S.lat + d)]], { padding: 24, duration: 600 });
  }
})();

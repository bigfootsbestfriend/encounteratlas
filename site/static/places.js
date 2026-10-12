// Places section: map with icon markers by type, type chips + search over the card list,
// and "this month" on the events calendar (in case the static build is a few days old).
(function () {
  const TYPES = {
    museum: { color: '#F2B33D', icon: 'museum', label: 'Museums' },
    festival: { color: '#EE7A5F', icon: 'festival', label: 'Festivals and events' },
    attraction: { color: '#4FB3A9', icon: 'roadside', label: 'Roadside attractions' },
    expedition: { color: '#9CC46B', icon: 'expedition', label: 'Expeditions and tours' },
  };

  // ---------- events: highlight the current month ----------
  const now = new Date();
  const ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
  const months = document.querySelectorAll('.pl-month[data-ym], .pl-mnav[data-ym]');
  if (months.length && document.querySelector('.pl-month[data-ym="' + ym + '"]')) {
    months.forEach((m) => m.classList.toggle('is-now', m.dataset.ym === ym));
  }

  // ---------- list filtering ----------
  const cards = [...document.querySelectorAll('.pl-list .pl-card')];
  const chips = [...document.querySelectorAll('.pl-chip')];
  const q = document.getElementById('pl-q');
  const empty = document.querySelector('.pl-list .empty');
  const state = { type: '', term: '' };
  let onFilter = () => {};
  function apply() {
    let shown = 0;
    for (const c of cards) {
      const ok = (!state.type || c.dataset.type === state.type) && (!state.term || c.dataset.names.includes(state.term));
      c.hidden = !ok;
      if (ok) shown++;
    }
    document.querySelectorAll('.pl-list .pl-group').forEach((g) => { g.hidden = !g.querySelector('.pl-card:not([hidden])'); });
    document.querySelectorAll('.pl-list .pl-country').forEach((g) => { g.hidden = !g.querySelector('.pl-card:not([hidden])'); });
    if (empty) empty.hidden = shown > 0;
    onFilter();
  }
  chips.forEach((chip) => chip.addEventListener('click', () => {
    state.type = chip.dataset.filter;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
    apply();
  }));
  if (q) {
    q.addEventListener('input', () => { state.term = q.value.trim().toLowerCase(); apply(); });
    const pre = new URLSearchParams(location.search).get('q');
    if (pre) { q.value = pre; state.term = pre.toLowerCase(); }
  }
  const preType = new URLSearchParams(location.search).get('type');
  if (preType && TYPES[preType]) {
    state.type = preType;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.filter === preType)));
  }
  if (cards.length) apply();

  // ---------- map ----------
  const el = document.getElementById('pl-map');
  if (!el || !window.maplibregl) return;
  const BASE = el.dataset.base || '';
  const map = new maplibregl.Map({
    container: el,
    style: 'https://tiles.openfreemap.org/styles/dark',
    center: [-96, 42],
    zoom: window.innerWidth < 720 ? 2.3 : 3.1,
    minZoom: 1.2,
    maxZoom: 15,
    attributionControl: { compact: true },
    cooperativeGestures: !!el.dataset.focus || window.innerWidth < 720,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');

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

  async function badge(key, size) {
    const t = TYPES[key];
    let svg = await fetch(BASE + '/static/icons/' + t.icon + '.svg').then((r) => r.text()).catch(() => '');
    svg = svg.replace(/currentColor/g, t.color).replace(/var\(--eye,[^)]*\)/g, '#F2B33D').replace(/var\(--eye-red,[^)]*\)/g, '#FF5A44')
      .replace(/var\(--bg,[^)]*\)/g, '#13261F').replace('<svg ', '<svg width="64" height="64" ');
    const img = new Image();
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    await img.decode().catch(() => {});
    const px = size * 2, c = document.createElement('canvas');
    c.width = c.height = px;
    const g = c.getContext('2d');
    g.beginPath(); g.arc(px / 2, px / 2, px / 2 - 3, 0, Math.PI * 2);
    g.fillStyle = '#13261F'; g.fill(); g.lineWidth = 5; g.strokeStyle = t.color; g.stroke();
    const pad = px * 0.19;
    try { g.drawImage(img, pad, pad, px - 2 * pad, px - 2 * pad); } catch (e) { /* icon failed */ }
    map.addImage('pl-' + key, g.getImageData(0, 0, px, px), { pixelRatio: 2 });
  }

  function node(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function popup(f) {
    const p = f.properties;
    const div = node('div', 'pop');
    const kind = node('div', 'pop-kind', p.type);
    const h = node('p', 'pop-h', p.name);
    const meta = node('p', null, [p.city, p.region].filter(Boolean).join(', '));
    meta.style.margin = '0 0 .4rem';
    const a = node('a', null, 'Details, dates and directions');
    a.href = BASE + '/places/' + p.slug + '/';
    div.append(kind, h, meta, a);
    if (p.a == 1) { const ap = node('p', 'approx', 'Pin is approximate (nearest town or area).'); ap.style.margin = '.4rem 0 0'; div.append(ap); }
    new maplibregl.Popup({ maxWidth: '290px', offset: 16 }).setLngLat(f.geometry.coordinates).setDOMContent(div).addTo(map);
  }

  map.on('load', async () => {
    tint();
    const data = await fetch(el.dataset.geojson).then((r) => r.json()).catch(() => null);
    if (!data) return;
    await Promise.all(Object.keys(TYPES).map((k) => badge(k, 34)));
    const all = data.features;
    const only = el.dataset.type;
    const base = only ? all.filter((f) => f.properties.k === only) : all;
    map.addSource('pl', { type: 'geojson', data: { type: 'FeatureCollection', features: base }, cluster: true, clusterRadius: 34, clusterMaxZoom: 7 });
    map.addLayer({ id: 'pl-clusters', type: 'circle', source: 'pl', filter: ['has', 'point_count'], paint: {
      'circle-color': '#F2B33D', 'circle-opacity': 0.92,
      'circle-radius': ['interpolate', ['linear'], ['get', 'point_count'], 2, 15, 12, 21, 40, 28],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 3 } });
    map.addLayer({ id: 'pl-count', type: 'symbol', source: 'pl', filter: ['has', 'point_count'], layout: {
      'text-field': ['get', 'point_count_abbreviated'], 'text-size': 13, 'text-font': ['Noto Sans Bold'], 'text-allow-overlap': true },
      paint: { 'text-color': '#13261F' } });
    map.addLayer({ id: 'pl-pins', type: 'symbol', source: 'pl', filter: ['!', ['has', 'point_count']], layout: {
      'icon-image': ['concat', 'pl-', ['get', 'k']], 'icon-size': ['interpolate', ['linear'], ['zoom'], 2, 0.75, 8, 1.05],
      'icon-allow-overlap': true } });

    const legend = node('div', 'pl-legend');
    for (const [k, t] of Object.entries(TYPES)) {
      if (only && k !== only) continue;
      if (!base.some((f) => f.properties.k === k)) continue;
      const s = node('span'); const i = node('i'); i.style.setProperty('--tc', t.color); s.append(i, document.createTextNode(t.label)); legend.append(s);
    }
    el.appendChild(legend);

    map.on('click', 'pl-clusters', async (e) => {
      const f = e.features[0];
      const zoom = await map.getSource('pl').getClusterExpansionZoom(f.properties.cluster_id);
      map.easeTo({ center: f.geometry.coordinates, zoom });
    });
    map.on('click', 'pl-pins', (e) => popup(e.features[0]));
    for (const id of ['pl-clusters', 'pl-pins']) {
      map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
    }

    // Region pages: fit to that region. Detail pages: centre on the place and open its popup.
    const fit = (feats, maxZoom) => {
      if (!feats.length) return;
      const b = new maplibregl.LngLatBounds();
      feats.forEach((f) => b.extend(f.geometry.coordinates));
      const wide = el.clientWidth > 600;
      map.fitBounds(b, { padding: wide ? { top: 60, bottom: 50, left: 70, right: 230 } : 40, maxZoom, duration: 0 });
    };
    if (el.dataset.region) fit(all.filter((f) => f.properties.rg === el.dataset.region), 8);
    else if (el.dataset.focus) {
      const f = all.find((x) => x.properties.slug === el.dataset.focus);
      if (f) {
        map.jumpTo({ center: f.geometry.coordinates, zoom: f.properties.a == 1 ? 7 : 8.5 });
        // Draw this place above its neighbours with a glowing ring, so it never hides under another pin.
        map.addSource('pl-focus', { type: 'geojson', data: { type: 'FeatureCollection', features: [f] } });
        map.addLayer({ id: 'pl-focus-glow', type: 'circle', source: 'pl-focus', paint: {
          'circle-radius': 30, 'circle-color': TYPES[f.properties.k].color, 'circle-opacity': 0.28, 'circle-blur': 0.6 } });
        map.addLayer({ id: 'pl-focus-pin', type: 'symbol', source: 'pl-focus', layout: {
          'icon-image': 'pl-' + f.properties.k, 'icon-size': 1.35, 'icon-allow-overlap': true } });
        map.on('click', 'pl-focus-pin', (e) => popup(e.features[0]));
      }
    } else if (only) fit(base, 6);

    onFilter = () => {
      const feats = base.filter((f) => {
        const p = f.properties;
        if (state.type && p.k !== state.type) return false;
        if (state.term) {
          const hay = [p.name, p.city, p.region, p.type, p.c].join(' ').toLowerCase();
          if (!hay.includes(state.term)) return false;
        }
        return true;
      });
      map.getSource('pl').setData({ type: 'FeatureCollection', features: feats });
    };
    if (state.type || state.term) onFilter();
  });
})();

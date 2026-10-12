// Encounter map: MapLibre + OpenFreeMap dark tiles.
// Layers: famous creature cases (icon pins), military encounters, Air Force UFO files (clusters),
// places and reports when their data exists. Each layer has a toggle chip.
(function () {
  const el = document.getElementById('map');
  if (!el || !window.maplibregl) return;
  const BASE = el.dataset.base || '';
  const CAT = { hominid: '#D9A05B', canid: '#D0633F', winged: '#B98ACB', aquatic: '#4FB3A9', entity: '#9CC46B', fae: '#E58FB0', ufo: '#8E8CF0', other: '#E0C36A' };
  const SAUCER = '<svg class="ico" viewBox="0 0 64 64" fill="currentColor" aria-hidden="true"><ellipse cx="32" cy="31" rx="27" ry="7.5"/><path d="M19 28Q32 7 45 28Z"/></svg>';
  const params = new URLSearchParams(location.search);

  const HOME_VIEW = { center: window.innerWidth < 720 ? [-98, 44] : [-98, 41], zoom: window.innerWidth < 720 ? 2.6 : 3.4 };
  const fullPage = location.pathname.endsWith('/map/');
  const map = new maplibregl.Map({
    container: el,
    style: 'https://tiles.openfreemap.org/styles/dark',
    ...HOME_VIEW,
    // Embedded maps let the page scroll; zoom with Ctrl/Cmd + wheel or two fingers. The full-screen map zooms freely.
    cooperativeGestures: !fullPage,
    minZoom: 1.2,
    maxZoom: 15,
    attributionControl: { compact: true },
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

  // Draw an icon SVG inside a dark round badge, as a map image.
  const svgCache = {};
  async function iconSvg(name) {
    if (!svgCache[name]) svgCache[name] = fetch(BASE + (name.startsWith('art/') ? '/static/' : '/static/icons/') + name + '.svg').then((r) => r.text()).catch(() => '');
    return svgCache[name];
  }
  async function addBadge(id, name, color, size = 44) {
    if (map.hasImage(id)) return;
    let svg = await iconSvg(name);
    svg = svg.replace(/currentColor/g, color).replace(/var\(--eye,[^)]*\)/g, '#F2B33D').replace(/var\(--eye-red,[^)]*\)/g, '#FF5A44')
      .replace(/var\(--bg,[^)]*\)/g, '#13261F').replace('<svg ', '<svg width="64" height="64" ');
    const img = new Image();
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    await img.decode().catch(() => {});
    const px = size * 2, c = document.createElement('canvas');
    c.width = c.height = px;
    const g = c.getContext('2d');
    g.beginPath(); g.arc(px / 2, px / 2, px / 2 - 3, 0, Math.PI * 2);
    // Park-poster silhouettes: dark creature on a disc of its category colour; old icons: coloured icon on dark disc
    const art = name.startsWith('art/');
    g.fillStyle = art ? color : '#13261F'; g.fill(); g.lineWidth = 4; g.strokeStyle = art ? '#13261F' : color; g.stroke();
    const pad = px * 0.17;
    try { g.drawImage(img, pad, pad, px - 2 * pad, px - 2 * pad); } catch (e) { /* icon failed to load */ }
    map.addImage(id, g.getImageData(0, 0, px, px), { pixelRatio: 2 });
  }

  function popup(lngLat, nodes) {
    const div = document.createElement('div');
    div.className = 'pop';
    div.append(...nodes);
    new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(lngLat).setDOMContent(div).addTo(map);
  }
  function node(tag, cls, text, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html) n.innerHTML = html; else if (text != null) n.textContent = text;
    return n;
  }
  function link(href, text) { const a = node('a', '', text); a.href = href; if (a.host !== location.host) { a.target = '_blank'; a.rel = 'noopener'; } return a; }
  function pointer(id) {
    map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
  }

  const LAYERS = []; // {key, label, color, ids}

  async function addBlueBook() {
    map.addSource('bluebook', { type: 'geojson', data: BASE + '/data/bluebook.geojson', cluster: true, clusterRadius: 38, clusterMaxZoom: 9 });
    map.addLayer({ id: 'bb-glow', type: 'circle', source: 'bluebook', paint: {
      'circle-color': '#F2B33D',
      'circle-radius': ['case', ['has', 'point_count'], ['interpolate', ['linear'], ['get', 'point_count'], 2, 16, 50, 26, 500, 42], 9],
      'circle-blur': 1, 'circle-opacity': 0.3 } });
    map.addLayer({ id: 'bb-clusters', type: 'circle', source: 'bluebook', filter: ['has', 'point_count'], paint: {
      'circle-color': ['interpolate', ['linear'], ['get', 'point_count'], 2, '#C98A22', 100, '#F2B33D', 600, '#FFD27A'],
      'circle-radius': ['interpolate', ['linear'], ['get', 'point_count'], 2, 9, 50, 14, 500, 22],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 2 } });
    map.addLayer({ id: 'bb-count', type: 'symbol', source: 'bluebook', filter: ['has', 'point_count'], layout: {
      'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12, 'text-font': ['Noto Sans Bold'], 'text-allow-overlap': true, 'text-ignore-placement': true },
      paint: { 'text-color': '#13261F' } });
    map.addLayer({ id: 'bb-point', type: 'circle', source: 'bluebook', filter: ['!', ['has', 'point_count']], paint: {
      'circle-color': ['case', ['==', ['get', 'a'], 1], '#B98A3A', '#F2B33D'],
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3, 10, 6],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5 } });
    map.on('click', 'bb-clusters', async (e) => {
      const f = e.features[0];
      const zoom = await map.getSource('bluebook').getClusterExpansionZoom(f.properties.cluster_id);
      map.easeTo({ center: f.geometry.coordinates, zoom });
    });
    map.on('click', 'bb-point', (e) => {
      const p = e.features[0].properties;
      const nodes = [node('div', 'pop-kind', null, SAUCER + '<span>Air Force UFO file (Project Blue Book)</span>'),
        node('p', 'pop-h', p.t || 'Unknown place'),
        node('p', 'pop-meta', [p.r && p.r !== p.t ? p.r : '', p.w].filter(Boolean).join(', ')),
        link('https://catalog.archives.gov/id/' + p.id, 'Read the Air Force file')];
      if (p.a == 1) nodes.push(node('p', 'approx', 'Approximate: placed in the state or country, not the exact spot.'));
      popup(e.features[0].geometry.coordinates, nodes);
    });
    pointer('bb-clusters'); pointer('bb-point');
    LAYERS.push({ key: 'ufo-files', label: 'Air Force UFO files', color: '#F2B33D', ids: ['bb-glow', 'bb-clusters', 'bb-count', 'bb-point'] });
  }

  async function addFamous() {
    const data = await fetch(BASE + '/data/famous.geojson').then((r) => r.json()).catch(() => null);
    if (!data || !data.features.length) return;
    const icons = new Set(data.features.map((f) => f.properties.i + '|' + f.properties.c));
    await Promise.all([...icons].map((k) => { const [i, c] = k.split('|'); return addBadge('crit-' + i + '-' + c, i, CAT[c] || '#C9D3A4'); }));
    for (const f of data.features) f.properties.img = 'crit-' + f.properties.i + '-' + f.properties.c;
    map.addSource('famous', { type: 'geojson', data });
    map.addLayer({ id: 'famous', type: 'symbol', source: 'famous', layout: {
      'icon-image': ['get', 'img'], 'icon-size': ['interpolate', ['linear'], ['zoom'], 2, 0.62, 8, 1],
      'icon-allow-overlap': true, 'symbol-sort-key': ['get', 'y'] } });
    map.on('click', 'famous', (e) => {
      const p = e.features[0].properties;
      popup(e.features[0].geometry.coordinates, [
        node('div', 'pop-kind', null, '<span class="dot" style="background:' + (CAT[p.c] || '#ccc') + '"></span><span>' + p.n + '</span>'),
        node('p', 'pop-h', p.t), node('p', 'pop-meta', p.p + ', ' + p.y),
        ...(p.u ? [link(p.u, 'Read the full story')] : []),
        link(BASE + '/creatures/' + p.s + '/', 'About the ' + p.n)]);
    });
    pointer('famous');
    LAYERS.push({ key: 'creatures', label: 'Famous creature cases', color: '#D9A05B', ids: ['famous'] });
  }

  async function addMilitary() {
    const data = await fetch(BASE + '/data/military.geojson').then((r) => r.json()).catch(() => null);
    if (!data || !data.features.length) return;
    await addBadge('mil', 'art/pic-mil-chase', '#7FD3FF');
    map.addSource('military', { type: 'geojson', data });
    map.addLayer({ id: 'military', type: 'symbol', source: 'military', layout: {
      'icon-image': 'mil', 'icon-size': ['interpolate', ['linear'], ['zoom'], 2, 0.62, 8, 1], 'icon-allow-overlap': true } });
    map.on('click', 'military', (e) => {
      const p = e.features[0].properties;
      popup(e.features[0].geometry.coordinates, [node('div', 'pop-kind', null, '<span>Military encounter, ' + p.y + '</span>'),
        node('p', 'pop-h', p.t), node('p', 'pop-meta', p.p + '. ' + p.b), link(BASE + '/military/', 'Read the case')]);
    });
    pointer('military');
    LAYERS.push({ key: 'military', label: 'Military encounters', color: '#7FD3FF', ids: ['military'] });
  }

  async function addPlaces() {
    const data = await fetch(BASE + '/data/places.geojson').then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (!data || !data.features || !data.features.length) return;
    map.addSource('places', { type: 'geojson', data });
    map.addLayer({ id: 'places', type: 'circle', source: 'places', paint: {
      // Festivals and gatherings get their own colour (and their own "Events and gatherings" chip)
      'circle-color': ['case', ['==', ['get', 'k'], 'festival'], '#F0806A', '#9CC46B'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 5, 10, 9],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 2 } });
    map.on('click', 'places', (e) => {
      const p = e.features[0].properties;
      const nodes = [node('div', 'pop-kind', null, '<span>' + (p.type || 'Place to visit') + '</span>'), node('p', 'pop-h', p.name || p.t || '')];
      if (p.city || p.region) nodes.push(node('p', 'pop-meta', [p.city, p.region].filter(Boolean).join(', ')));
      if (p.slug) nodes.push(link(BASE + '/places/' + p.slug + '/', p.k === 'festival' ? 'Dates and details' : 'Visit details'));
      if (p.k === 'festival') nodes.push(link(BASE + '/events/', 'All upcoming events'));
      popup(e.features[0].geometry.coordinates, nodes);
    });
    pointer('places');
    LAYERS.push({ key: 'places', label: 'Places to visit', color: '#9CC46B', ids: ['places'] });
    LAYERS.push({ key: 'events', label: 'Events and gatherings', color: '#F0806A', ids: [] });
  }

  // Newer official cases: FAA pilot reports (NARA RG 615) and the Pentagon's PURSUE files
  async function addOfficial(file, id, color, label) {
    const data = await fetch(BASE + '/data/' + file).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (!data || !data.features || !data.features.length) return;
    map.addSource(id, { type: 'geojson', data });
    map.addLayer({ id, type: 'circle', source: id, paint: {
      'circle-color': color, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3.5, 10, 7],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5, 'circle-opacity': ['case', ['==', ['get', 'a'], 1], 0.55, 0.95] } });
    map.on('click', id, (e) => {
      const p = e.features[0].properties;
      const nodes = [node('div', 'pop-kind', null, '<span>' + label + (p.w ? ', ' + p.w : '') + '</span>'), node('p', 'pop-h', p.t || 'Report')];
      if (p.r) nodes.push(node('p', 'pop-meta', p.r + (p.a == 1 ? ' (approximate spot)' : '')));
      if (p.u) nodes.push(link(p.u, 'Open the official file'));
      popup(e.features[0].geometry.coordinates, nodes);
    });
    pointer(id);
  }

  async function addReports() {
    const api = el.dataset.api;
    if (!api) return;
    const data = await fetch(api + '/api/reports.geojson').then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (!data || !data.features || !data.features.length) return;
    map.addSource('reports', { type: 'geojson', data });
    map.addLayer({ id: 'reports', type: 'circle', source: 'reports', paint: {
      'circle-color': '#F3F1E4', 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 4.5, 10, 8],
      'circle-stroke-color': '#F2B33D', 'circle-stroke-width': 2.5 } });
    map.on('click', 'reports', (e) => {
      const p = e.features[0].properties;
      popup(e.features[0].geometry.coordinates, [node('div', 'pop-kind', null, '<span>Reader report' + (p.d ? ', ' + p.d : '') + '</span>'),
        node('p', 'pop-h', (p.n || 'Something') + (p.t ? ' near ' + p.t : '')), link(BASE + '/reports/?id=' + encodeURIComponent(p.id), 'Read the report')]);
    });
    pointer('reports');
  }

  // Filters: encounter type chips + creature chips (and ?type= / ?cat= / ?creature= in the URL).
  const state = { type: params.get('type') || 'all', cat: params.get('cat') || '', creature: params.get('creature') || '' };
  let famousData = null;
  function setVis(ids, on) { for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); }
  const chipBox = document.querySelector('.cchips'), find = document.querySelector('.cfind-in'), none = document.querySelector('.cfind-none');
  // Which creature chips to show: matches for the search box, else the open category's creatures.
  function showChips(openCat) {
    if (!chipBox) return;
    const q = find ? find.value.trim().toLowerCase() : '';
    let n = 0;
    chipBox.querySelectorAll('.cchip').forEach((c) => {
      const on = q ? c.dataset.names.includes(q) : (!!openCat && c.dataset.cat === openCat);
      c.hidden = !on; if (on) n++;
    });
    chipBox.hidden = n === 0;
    if (none) none.hidden = !(q && n === 0);
  }
  function apply(fit) {
    const { type, cat, creature } = state;
    const narrowed = !!(cat || creature);
    const showUfoFiles = (type === 'all' || type === 'ufo') && (!narrowed || cat === 'ufo');
    setVis(['bb-glow', 'bb-clusters', 'bb-count', 'bb-point', 'faa', 'pursue'], showUfoFiles);
    setVis(['military'], (type === 'all' || type === 'military') && !narrowed);
    setVis(['places'], type === 'all' || type === 'places' || type === 'events');
    if (map.getLayer('places')) {
      const slugs = cat ? [...document.querySelectorAll('.cchip')].filter((b) => b.dataset.cat === cat).map((b) => b.dataset.creature) : null;
      const f = ['all'];
      if (creature) f.push(['==', ['get', 'c'], creature]); else if (slugs) f.push(['in', ['get', 'c'], ['literal', slugs]]);
      if (type === 'events') f.push(['==', ['get', 'k'], 'festival']);
      if (type === 'places') f.push(['!=', ['get', 'k'], 'festival']);
      map.setFilter('places', f.length > 1 ? f : null);
    }
    const showFamous = type === 'all' || type === 'cryptid' || (type === 'ufo');
    setVis(['famous'], showFamous);
    setVis(['reports'], type === 'all' || type === 'cryptid' || type === 'ufo');
    if (map.getLayer('reports')) {
      const slugs = cat ? [...document.querySelectorAll('.cchip')].filter((b) => b.dataset.cat === cat).map((b) => b.dataset.creature) : null;
      map.setFilter('reports', creature ? ['==', ['get', 'c'], creature] : slugs ? ['in', ['get', 'c'], ['literal', slugs]] : null);
    }
    if (map.getLayer('famous')) {
      const f = ['all'];
      if (type === 'cryptid') f.push(['!=', ['get', 'c'], 'ufo']);
      if (type === 'ufo') f.push(['==', ['get', 'c'], 'ufo']);
      if (cat) f.push(['==', ['get', 'c'], cat]);
      if (creature) f.push(['==', ['get', 's'], creature]);
      map.setFilter('famous', f.length > 1 ? f : null);
    }
    document.querySelectorAll('.tchip').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.type === type && !narrowed)));
    reset.hidden = !narrowed && type === 'all';
    document.querySelectorAll('.cchip').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.creature === creature)));
    const openCat = cat || (creature && (document.querySelector(`.cchip[data-creature="${creature}"]`) || { dataset: {} }).dataset.cat) || '';
    document.querySelectorAll('.catchip').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.cat === openCat)));
    showChips(openCat);
    const q = new URLSearchParams();
    if (type !== 'all') q.set('type', type);
    if (cat) q.set('cat', cat);
    if (creature) q.set('creature', creature);
    if (location.pathname.endsWith('/map/')) history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : ''));
    if (fit && famousData && narrowed) {
      const pts = famousData.features.filter((x) => (!creature || x.properties.s === creature) && (!cat || x.properties.c === cat));
      if (pts.length === 1) map.flyTo({ center: pts[0].geometry.coordinates, zoom: 6 });
      else if (pts.length) {
        const b = new maplibregl.LngLatBounds();
        pts.forEach((x) => b.extend(x.geometry.coordinates));
        // Worldwide groups (Bigfoot to Yowie) stay on the default view rather than zooming out to mid-Atlantic.
        if (b.getEast() - b.getWest() < 150) map.fitBounds(b, { padding: 70, maxZoom: 7 });
      }
    }
  }
  // A clear way back after picking a creature: a button on the map that shows everything at the starting view.
  const reset = document.createElement('button');
  reset.type = 'button'; reset.className = 'map-reset'; reset.textContent = 'Show everything'; reset.hidden = true;
  el.parentElement.append(reset);
  function showAll() { state.type = 'all'; state.cat = ''; state.creature = ''; apply(false); map.flyTo({ ...HOME_VIEW, duration: 800 }); }
  reset.addEventListener('click', showAll);
  document.querySelectorAll('.tchip').forEach((b) => b.addEventListener('click', () => {
    if (b.dataset.type === 'all') return showAll();
    state.type = b.dataset.type; state.cat = ''; state.creature = ''; apply(false);
  }));
  document.querySelectorAll('.cchip').forEach((b) => b.addEventListener('click', () => {
    if (state.creature === b.dataset.creature) { state.creature = ''; state.cat = b.dataset.cat; apply(false); return; }
    state.creature = b.dataset.creature; state.cat = ''; state.type = 'all'; apply(true);
  }));
  // Category chips open that group's creatures (and filter the map to it); clicking again closes it.
  document.querySelectorAll('.catchip').forEach((b) => b.addEventListener('click', () => {
    const open = b.getAttribute('aria-pressed') === 'true';
    if (find) find.value = '';
    state.creature = ''; state.type = 'all'; state.cat = open ? '' : b.dataset.cat; apply(!open);
  }));
  if (find) find.addEventListener('input', () => showChips(state.cat || ''));

  window.eaMap = map; // handy for debugging and screenshot tests
  map.on('load', async () => {
    tint();
    await addBlueBook();
    await addOfficial('ufo_faa.geojson', 'faa', '#7FD3FF', 'FAA pilot report');
    await addOfficial('ufo_pursue.geojson', 'pursue', '#E07A5F', 'Pentagon UFO file');
    await addPlaces();
    await addMilitary();
    await addFamous();
    await addReports();
    famousData = map.getSource('famous') ? await fetch(BASE + '/data/famous.geojson').then((r) => r.json()) : null;
    apply(!!(state.cat || state.creature));
  });

  let me;
  document.querySelectorAll('[data-locate]').forEach((btn) => btn.addEventListener('click', () => {
    if (!navigator.geolocation) { btn.textContent = 'Location not available'; return; }
    const label = btn.textContent;
    btn.textContent = 'Finding you...';
    navigator.geolocation.getCurrentPosition((pos) => {
      const ll = [pos.coords.longitude, pos.coords.latitude];
      if (!me) {
        const dot = document.createElement('div');
        dot.className = 'me-dot';
        me = new maplibregl.Marker({ element: dot });
      }
      me.setLngLat(ll).addTo(map);
      map.flyTo({ center: ll, zoom: 8 });
      btn.textContent = label;
      document.dispatchEvent(new CustomEvent('ea:located', { detail: ll }));
    }, () => { btn.textContent = 'Location blocked: allow it in your browser'; }, { enableHighAccuracy: true, timeout: 10000 });
  }));
})();

// Historic encounters: topic chips + decade strip filter the clippings (all cases are in the HTML);
// map of cases coloured by topic.
(function () {
  const TOPICS = {
    'airship': ['#8E8CF0', 'Mystery airships, 1896-97', 'airships-1896-1897'],
    'airship-1909': ['#7FB2F0', 'Phantom airships, 1909', 'phantom-airships-1909'],
    'wild-man': ['#D9A05B', 'Wild men', 'wild-men'],
    'sea-serpent': ['#4FB3A9', 'Sea serpents and lake monsters', 'sea-serpents'],
    'jersey-devil': ['#B98ACB', 'Jersey Devil, 1909', 'jersey-devil-1909'],
    'giant-bird': ['#E0A060', 'Giant birds', 'giant-birds'],
    'phantom-light': ['#F2B33D', 'Phantom lights', 'phantom-lights'],
    'creature': ['#9CC46B', 'Other strange creatures', 'strange-creatures'],
  };
  const state = { k: '', dec: '' };
  const cards = [...document.querySelectorAll('.hc-list .hc')];
  const chips = [...document.querySelectorAll('.hc-chip')];
  const decs = [...document.querySelectorAll('button.hd')];
  const status = document.querySelector('.hc-status');
  const empty = document.querySelector('.hc-list .empty');
  let onFilter = () => {};

  function apply() {
    let shown = 0;
    for (const c of cards) {
      const ok = (!state.k || c.dataset.k === state.k) && (!state.dec || c.dataset.dec === state.dec);
      c.hidden = !ok;
      if (ok) shown++;
    }
    document.querySelectorAll('.hc-dec').forEach((g) => { g.hidden = !g.querySelector('.hc:not([hidden])'); });
    if (empty) empty.hidden = shown > 0;
    if (status) {
      const bits = [];
      if (state.k) bits.push(TOPICS[state.k][1].toLowerCase());
      if (state.dec) bits.push('the ' + state.dec + 's');
      status.textContent = bits.length ? `Showing ${shown} case${shown === 1 ? '' : 's'}: ${bits.join(', ')}.` : '';
    }
    onFilter();
  }
  chips.forEach((chip) => chip.addEventListener('click', () => {
    state.k = chip.dataset.k;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
    apply();
  }));
  decs.forEach((b) => b.addEventListener('click', () => {
    state.dec = state.dec === b.dataset.dec ? '' : b.dataset.dec;
    decs.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.dec === state.dec)));
    apply();
  }));

  // ---------- map ----------
  const el = document.getElementById('hc-map');
  if (!el || !window.maplibregl) return;
  const BASE = el.dataset.base || '';
  const map = new maplibregl.Map({
    container: el, style: 'https://tiles.openfreemap.org/styles/dark', center: [-92, 39],
    zoom: window.innerWidth < 720 ? 2.4 : 3.3, minZoom: 1.5, maxZoom: 13,
    attributionControl: { compact: true }, cooperativeGestures: window.innerWidth < 720,
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
  function node(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  const colour = ['match', ['get', 'k']];
  for (const [k, t] of Object.entries(TOPICS)) colour.push(k, t[0]);
  colour.push('#C9D3A4');

  map.on('load', async () => {
    tint();
    const data = await fetch(el.dataset.geojson).then((r) => r.json()).catch(() => null);
    if (!data) return;
    let feats = data.features;
    if (el.dataset.k) feats = feats.filter((f) => f.properties.k === el.dataset.k);
    if (el.dataset.ids) { const ids = new Set(el.dataset.ids.split(',')); feats = feats.filter((f) => ids.has(f.properties.id)); }
    const all = feats;
    map.addSource('hc', { type: 'geojson', data: { type: 'FeatureCollection', features: all } });
    map.addLayer({ id: 'hc-glow', type: 'circle', source: 'hc', paint: {
      'circle-color': colour, 'circle-opacity': 0.22, 'circle-blur': 0.6,
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 9, 9, 18] } });
    map.addLayer({ id: 'hc-pins', type: 'circle', source: 'hc', paint: {
      'circle-color': colour, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 4.5, 9, 8],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5,
      'circle-opacity': ['case', ['==', ['get', 'a'], 1], 0.75, 1] } });

    const legend = node('div', 'hc-legend');
    for (const [k, t] of Object.entries(TOPICS)) {
      if (!all.some((f) => f.properties.k === k)) continue;
      const s = node('span'); const i = node('i'); i.style.setProperty('--tc', t[0]); s.append(i, document.createTextNode(t[1])); legend.append(s);
    }
    if (legend.children.length > 1) el.appendChild(legend);

    if (all.length) {
      const b = new maplibregl.LngLatBounds();
      all.forEach((f) => b.extend(f.geometry.coordinates));
      map.fitBounds(b, { padding: 50, maxZoom: 7, duration: 0 });
    }

    map.on('click', 'hc-pins', (e) => {
      const f = e.features[0], p = f.properties, t = TOPICS[p.k] || ['#ccc', '', ''];
      const div = node('div', 'pop hc-pop');
      const kind = node('div', 'pop-kind'); const i = node('i'); i.style.setProperty('--tc', t[0]);
      kind.append(i, document.createTextNode(t[1] + ' · ' + p.d));
      const h = node('p', 'pop-h', p.t);
      const meta = node('p', 'pop-meta', p.p);
      const a = node('a', null, 'Read the case');
      a.href = (document.getElementById('h-' + p.id) ? '' : BASE + '/history/' + t[2] + '/') + '#h-' + p.id;
      div.append(kind, h, meta, a);
      if (p.a == 1) div.append(node('p', 'approx', 'Pin is approximate (nearest town or the state).'));
      new maplibregl.Popup({ maxWidth: '290px', offset: 10 }).setLngLat(f.geometry.coordinates).setDOMContent(div).addTo(map);
    });
    map.on('mouseenter', 'hc-pins', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'hc-pins', () => { map.getCanvas().style.cursor = ''; });

    onFilter = () => {
      const fs = all.filter((f) => (!state.k || f.properties.k === state.k) &&
        (!state.dec || String(Math.floor(f.properties.y / 10) * 10) === state.dec));
      map.getSource('hc').setData({ type: 'FeatureCollection', features: fs });
    };
  });
})();

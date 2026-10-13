// Official UFO releases archive: list filters (search, chips, selects, "show more") and small MapLibre maps.
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // ---------- filters ----------
  const list = $('[data-filter-list]');
  if (list) {
    const items = $$(':scope > li, :scope li.ua-rel', list);
    const q = $('#ua-q');
    const country = $('#ua-c');
    const agency = $('#ua-a');
    const count = $('.ua-count');
    const empty = $('.empty');
    const more = $('[data-more]');
    const limit = +list.dataset.limit || 0;
    let shown = limit;
    const state = { type: '', kind: '', tranche: '' };
    const params = new URLSearchParams(location.search);

    function apply() {
      const term = q ? q.value.trim().toLowerCase() : '';
      const words = term.split(/\s+/).filter(Boolean);
      const c = country ? country.value : '';
      const a = agency ? agency.value : '';
      const filtering = !!(words.length || c || a || state.type || state.kind || state.tranche);
      let n = 0;
      for (const li of items) {
        const d = li.dataset;
        const ok = words.every((w) => (d.hay || '').includes(w)) && (!c || d.country === c) && (!a || d.agency === a)
          && (!state.type || d.type === state.type) && (!state.kind || d.kind === state.kind) && (!state.tranche || d.tranche === state.tranche);
        n += ok ? 1 : 0;
        li.hidden = !ok || (!filtering && limit && n > shown);
      }
      for (const sec of $$('.ua-year', list)) sec.hidden = !$('li:not([hidden])', sec);
      if (count) count.textContent = filtering ? `${n} of ${items.length} shown` : '';
      if (empty) empty.hidden = n > 0;
      if (more) more.parentNode.hidden = filtering || !limit || shown >= items.length;
    }
    function chipGroup(attr, key) {
      const chips = $$(`[data-${attr}]`).filter((b) => b.tagName === 'BUTTON');
      chips.forEach((b) => b.addEventListener('click', () => {
        state[key] = state[key] === b.dataset[attr] ? '' : b.dataset[attr];
        chips.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset[attr] === state[key])));
        apply();
      }));
      const pre = params.get(key);
      if (pre) { state[key] = pre; chips.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset[attr] === pre))); }
    }
    chipGroup('type', 'type'); chipGroup('kind', 'kind'); chipGroup('tranche', 'tranche');
    if (q) { q.addEventListener('input', apply); if (params.get('q')) q.value = params.get('q'); }
    if (country) { country.addEventListener('change', apply); if (params.get('country')) country.value = params.get('country'); }
    if (agency) agency.addEventListener('change', apply);
    if (more) more.addEventListener('click', () => { shown += limit * 2; apply(); });
    apply();
  }

  // ---------- maps ----------
  const COLORS = { faa: '#7FD3FF', document: '#F2B33D', video: '#FF7A66', image: '#B98ACB', audio: '#4FB3A9' };
  const LABELS = { faa: 'FAA pilot reports', document: 'Documents', video: 'Videos', image: 'Images', audio: 'Audio' };
  function tint(map) {
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
  function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }

  function initMap(box) {
    if (!window.maplibregl) return;
    const b = (box.dataset.bounds || '').split(',').map(Number);
    const map = new maplibregl.Map({
      container: box, style: 'https://tiles.openfreemap.org/styles/dark', minZoom: 0, maxZoom: 13,
      bounds: b.length === 4 && b.every((x) => !isNaN(x)) ? [[b[0], b[1]], [b[2], b[3]]] : [[-130, 20], [-60, 52]],
      attributionControl: { compact: true }, cooperativeGestures: true,
    });
    // The basemap's town dots ask for a sprite icon (circle-11) the style doesn't ship: give it a blank one, no console noise.
    map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.on('load', async () => {
      tint(map);
      const kinds = new Set();
      const urls = box.dataset.geojson.split(',');
      for (let i = 0; i < urls.length; i++) {
        const data = await fetch(urls[i]).then((r) => r.json()).catch(() => null);
        if (!data) continue;
        data.features.forEach((f) => kinds.add(f.properties.k));
        const src = 'ua' + i;
        map.addSource(src, { type: 'geojson', data });
        const color = ['match', ['get', 'k'], ...Object.entries(COLORS).flat(), '#F2B33D'];
        map.addLayer({ id: src + '-glow', type: 'circle', source: src, paint: {
          'circle-color': color, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 7, 10, 14], 'circle-blur': 1, 'circle-opacity': 0.35 } });
        map.addLayer({ id: src + '-pt', type: 'circle', source: src, paint: {
          'circle-color': color, 'circle-opacity': ['case', ['==', ['get', 'a'], 1], 0.6, 1],
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 3, 10, 7],
          'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5 } });
        map.on('mouseenter', src + '-pt', () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', src + '-pt', () => { map.getCanvas().style.cursor = ''; });
        map.on('click', src + '-pt', (e) => {
          const p = e.features[0].properties;
          const div = el('div', 'pop');
          div.append(el('div', 'pop-kind', p.s || ''), el('p', 'pop-h', p.t || ''));
          const meta = [p.r && p.r !== p.t ? p.r : '', p.w, p.f].filter(Boolean).join(' · ');
          if (meta) div.append(el('p', 'pop-meta', meta));
          if (p.d) div.append(el('p', 'pop-d', p.d));
          const a = el('a', '', p.k === 'faa' ? 'Read the FAA report' : 'Open the file'); a.href = p.u; a.rel = 'noopener'; a.target = '_blank';
          div.append(a);
          if (p.a == 1) div.append(el('p', 'approx', 'Approximate: placed in the middle of the state, country, sea or region named.'));
          new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(e.features[0].geometry.coordinates).setDOMContent(div).addTo(map);
        });
      }
      const leg = el('div', 'ua-mlegend');
      for (const k of kinds) {
        const s = el('span'); const i = el('i'); i.style.background = COLORS[k] || '#F2B33D';
        s.append(i, document.createTextNode(' ' + (LABELS[k] || k))); leg.append(s);
      }
      if (kinds.size) box.append(leg);
    });
  }
  const maps = $$('.ua-map');
  if (maps.length) {
    const start = () => maps.forEach((m) => {
      if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) { io.disconnect(); initMap(m); } }, { rootMargin: '200px' });
        io.observe(m);
      } else initMap(m);
    });
    if (window.maplibregl) start(); else window.addEventListener('load', start);
  }
})();

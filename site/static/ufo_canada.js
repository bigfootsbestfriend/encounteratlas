// Canada sightings maps (site/sections/ufo_canada.py): clustered dots coloured by the survey's verdict.
(function () {
  const COL = ['match', ['get', 'e'], 'u', '#FF7A66', 'p', '#F2B33D', 'e', '#4FB3A9', 'bb', '#F2B33D', '#B9B39A'];
  const EV = { u: 'Unexplained', p: 'Possibly explained', e: 'Explained', i: 'Not enough information' };
  const MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const fmt = (d) => { const p = (d || '').split('-'); return p.length === 3 ? `${MONTHS[+p[1]]} ${+p[2]}, ${p[0]}` : p.length === 2 ? `${MONTHS[+p[1]]} ${p[0]}` : p[0]; };
  function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
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

  function init(box) {
    if (box._map) return;
    const b = box.dataset.bounds.split(',').map(Number);
    const map = new maplibregl.Map({
      container: box, style: 'https://tiles.openfreemap.org/styles/dark', bounds: [[b[0], b[1]], [b[2], b[3]]],
      maxZoom: 13, attributionControl: { compact: true }, cooperativeGestures: true,
    });
    // The basemap's town dots ask for a sprite icon (circle-11) the style doesn't ship: give it a blank one, no console noise.
    map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    box._map = map;
    map.on('load', () => {
      tint(map);
      const cluster = box.dataset.cluster === '1';
      const towns = box.dataset.towns === '1'; // light file: one dot per town with counts n (reports) and nu (unexplained)
      map.addSource('cu', { type: 'geojson', data: box.dataset.geojson, cluster, clusterRadius: 40, clusterMaxZoom: 10,
        ...(towns ? { clusterProperties: { n: ['+', ['get', 'n']], nu: ['+', ['get', 'nu']] } } : {}) });
      if (cluster) {
        map.addLayer({ id: 'cu-cl', type: 'circle', source: 'cu', filter: ['has', 'point_count'], paint: {
          'circle-color': '#8E8CF0', 'circle-opacity': 0.85, 'circle-stroke-color': '#C9C7FF', 'circle-stroke-width': 1.5,
          'circle-radius': ['step', ['get', towns ? 'n' : 'point_count'], 13, 20, 17, 100, 22, 500, 28, 2000, 34] } });
        map.addLayer({ id: 'cu-cn', type: 'symbol', source: 'cu', filter: ['has', 'point_count'],
          layout: { 'text-field': towns ? ['case', ['>=', ['get', 'n'], 1000], ['concat', ['to-string', ['/', ['round', ['/', ['get', 'n'], 100]], 10]], 'k'], ['to-string', ['get', 'n']]] : ['get', 'point_count_abbreviated'], 'text-size': 12, 'text-font': ['Noto Sans Bold'], 'text-allow-overlap': true }, paint: { 'text-color': '#0F1F19' } });
        map.on('click', 'cu-cl', async (e) => {
          const f = e.features[0];
          const z = await map.getSource('cu').getClusterExpansionZoom(f.properties.cluster_id);
          map.easeTo({ center: f.geometry.coordinates, zoom: z });
        });
        map.on('mouseenter', 'cu-cl', () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', 'cu-cl', () => { map.getCanvas().style.cursor = ''; });
      }
      // Town dots: size by reports, redder the larger the share nobody explained.
      const townCol = ['interpolate', ['linear'], ['/', ['get', 'nu'], ['max', ['get', 'n'], 1]], 0, '#F2B33D', 0.25, '#FF7A66'];
      map.addLayer({ id: 'cu-pt', type: 'circle', source: 'cu', filter: ['!', ['has', 'point_count']], paint: {
        ...(towns ? { 'circle-radius': ['interpolate', ['linear'], ['get', 'n'], 1, 4, 20, 7, 200, 12, 1000, 18] } : {}),
        'circle-color': towns ? townCol : COL, 'circle-opacity': ['case', ['==', ['get', 'a'], 1], 0.45, 0.95],
        ...(towns ? {} : { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3.5, 10, 7] }), 'circle-stroke-color': '#13261F', 'circle-stroke-width': 1 } });
      map.on('mouseenter', 'cu-pt', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'cu-pt', () => { map.getCanvas().style.cursor = ''; });
      map.on('click', 'cu-pt', (e) => {
        // Several reports often share one town point: list them all (up to 6).
        const fs = e.features;
        const p0 = fs[0].properties;
        if (towns) {
          const div = el('div', 'pop cu-pop');
          div.append(el('div', 'pop-kind', 'UFO reports'), el('p', 'pop-h', p0.t + (p0.a == 1 ? '' : ', ' + p0.r)),
            el('p', 'pop-meta', `${p0.n} report${p0.n == 1 ? '' : 's'} since 1989 · ${p0.nu} unexplained`));
          if (p0.a == 1) div.append(el('p', 'approx', 'Reports whose town was not found, placed in the middle of the province.'));
          const a = el('a', '', /\/ufo\/canada\/[^/]+\/[^/]+\//.test(p0.u) ? `Read the ${p0.t} reports` : `Reports from ${p0.r}`); a.href = p0.u; div.append(a);
          new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(fs[0].geometry.coordinates).setDOMContent(div).addTo(map);
          return;
        }
        const div = el('div', 'pop cu-pop');
        div.append(el('div', 'pop-kind', fs.length > 1 ? `${fs.length} ${p0.lk ? 'files' : 'reports'} here` : (p0.lk ? 'Air Force case file' : 'UFO report')), el('p', 'pop-h', p0.t + (p0.r ? ', ' + p0.r : '')));
        for (const f of fs.slice(0, fs.length > 1 ? 6 : 1)) {
          const p = f.properties;
          if (!p0.lk) div.append(el('p', 'pop-meta', [fmt(p.w), p.k, p.h, EV[p.e]].filter(Boolean).join(' · ')));
          if (p.d && fs.length === 1) div.append(el('p', 'pop-d', p.d));
        }
        if (p0.a == 1) div.append(el('p', 'approx', 'Approximate: the town was not found, so this marks the province.'));
        if (p0.lk) { // Blue Book: one link per file listed
          for (const f of fs.slice(0, 6)) { const a = el('a', '', `${fmt(f.properties.w) || 'Undated'}: ${p0.lk}`); a.href = f.properties.u; a.target = '_blank'; a.rel = 'noopener'; div.append(el('p', 'pop-meta'), a); }
        } else if (p0.u) { const a = el('a', '', `All reports from ${p0.t}`); a.href = p0.u; div.append(a); }
        new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(fs[0].geometry.coordinates).setDOMContent(div).addTo(map);
      });
    });
  }

  function start() {
    if (!window.maplibregl) return;
    document.querySelectorAll('.cu-map').forEach((m) => {
      if (!('IntersectionObserver' in window)) return init(m);
      const io = new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) { io.disconnect(); init(m); } }, { rootMargin: '200px' });
      io.observe(m);
    });
  }
  if (window.maplibregl) start(); else window.addEventListener('load', start);

  document.querySelectorAll('[data-locate-cu]').forEach((btn) => btn.addEventListener('click', () => {
    const box = document.querySelector('.cu-map');
    if (!navigator.geolocation || !box) { btn.textContent = 'Location not available'; return; }
    btn.textContent = 'Finding you...';
    navigator.geolocation.getCurrentPosition((pos) => {
      const go = () => box._map.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 8.5 });
      if (box._map) go(); else { init(box); setTimeout(go, 800); }
      box.scrollIntoView({ behavior: 'smooth', block: 'center' });
      btn.textContent = 'Show reports near me';
    }, () => { btn.textContent = 'Location blocked: allow it in your browser'; }, { timeout: 10000 });
  }));
})();

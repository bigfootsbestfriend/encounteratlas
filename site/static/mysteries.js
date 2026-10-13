// Mysteries: type chips filter the cards (every card is in the HTML), and a map of pins coloured by type.
// On a mystery page the map has data-focus and centres on that place.
(function () {
  const cards = [...document.querySelectorAll('.my-card')];
  const chips = [...document.querySelectorAll('.ce-chip')];
  const status = document.querySelector('.ce-status');
  let filter = '';
  let setMap = () => {};
  chips.forEach((chip) => chip.addEventListener('click', () => {
    filter = chip.dataset.f;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
    let shown = 0;
    cards.forEach((c) => { const ok = !filter || c.dataset.t === filter; c.hidden = !ok; if (ok) shown++; });
    document.querySelectorAll('.my-group').forEach((g) => { g.hidden = !g.querySelector('.my-card:not([hidden])'); });
    if (status) status.textContent = filter ? `Showing ${shown} ${shown === 1 ? 'mystery' : 'mysteries'}.` : '';
    setMap();
  }));

  const el = document.getElementById('my-map');
  if (!el) return;
  function init() {
    if (!window.maplibregl) return setTimeout(init, 150);
    const focus = el.dataset.focus;
    const map = new maplibregl.Map({ container: el, style: 'https://tiles.openfreemap.org/styles/dark', center: [-30, 40], zoom: 1.2,
      attributionControl: { compact: true }, cooperativeGestures: !!focus });
    // The basemap's town dots ask for a sprite icon (circle-11) the style doesn't ship: give it a blank one, no console noise.
    map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.on('load', async () => {
      const data = await fetch(el.dataset.geojson).then((r) => r.json()).catch(() => null);
      if (!data) return;
      map.addSource('my', { type: 'geojson', data });
      map.addLayer({ id: 'my-glow', type: 'circle', source: 'my', paint: { 'circle-color': ['get', 'c'], 'circle-opacity': 0.25, 'circle-blur': 0.6,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 10, 9, 20] } });
      map.addLayer({ id: 'my-pins', type: 'circle', source: 'my', paint: { 'circle-color': ['get', 'c'],
        'circle-radius': ['case', ['==', ['get', 's'], focus || ''], 9, 6], 'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5 } });
      const f = focus && data.features.find((x) => x.properties.s === focus);
      if (f) map.jumpTo({ center: f.geometry.coordinates, zoom: 4 });
      else if (data.features.length) {
        const b = new maplibregl.LngLatBounds();
        data.features.forEach((x) => b.extend(x.geometry.coordinates));
        map.fitBounds(b, { padding: 40, maxZoom: 5, duration: 0 });
      }
      setMap = () => {
        const flt = filter ? ['==', ['get', 't'], filter] : null;
        map.setFilter('my-pins', flt); map.setFilter('my-glow', flt);
      };
      map.on('mouseenter', 'my-pins', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'my-pins', () => { map.getCanvas().style.cursor = ''; });
      map.on('click', 'my-pins', (ev) => {
        const p = ev.features[0].properties;
        const div = document.createElement('div'); div.className = 'pop';
        const a = document.createElement('a'); a.href = p.u; a.textContent = p.n;
        const s = document.createElement('p'); s.textContent = `${p.d} · ${p.p} · ${p.st}`;
        div.append(a, s);
        new maplibregl.Popup({ maxWidth: '280px', offset: 10 }).setLngLat(ev.features[0].geometry.coordinates).setDOMContent(div).addTo(map);
      });
    });
  }
  init();
})();

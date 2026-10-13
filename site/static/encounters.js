// Close encounters: status chips filter the case cards (all cases are in the HTML), and a map of case pins.
// On a case page the map has data-focus and centres on that case.
(function () {
  const COL = { unexplained: '#8E8CF0', disputed: '#F2B33D', explained: '#9CC46B', hoax: '#D0633F' };
  const cards = [...document.querySelectorAll('.ce-card')];
  const chips = [...document.querySelectorAll('.ce-chip')];
  const status = document.querySelector('.ce-status');
  let filter = '';
  let setMap = () => {};
  chips.forEach((chip) => chip.addEventListener('click', () => {
    filter = chip.dataset.f;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
    let shown = 0;
    cards.forEach((c) => {
      const ok = !filter || (filter === 'beings' ? c.dataset.b === '1' : c.dataset.s === filter);
      c.hidden = !ok; if (ok) shown++;
    });
    document.querySelectorAll('.ce-dec').forEach((g) => { g.hidden = !g.querySelector('.ce-card:not([hidden])'); });
    if (status) status.textContent = filter ? `Showing ${shown} case${shown === 1 ? '' : 's'}.` : '';
    setMap();
  }));

  const el = document.getElementById('ce-map');
  if (!el) return;
  function init() {
    if (!window.maplibregl) return setTimeout(init, 150);
    const focus = el.dataset.focus;
    const map = new maplibregl.Map({ container: el, style: 'https://tiles.openfreemap.org/styles/dark', center: [-40, 30], zoom: 1.2,
      attributionControl: { compact: true }, cooperativeGestures: !!focus });
    // The basemap's town dots ask for a sprite icon (circle-11) the style doesn't ship: give it a blank one, no console noise.
    map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.on('load', async () => {
      const data = await fetch(el.dataset.geojson).then((r) => r.json()).catch(() => null);
      if (!data) return;
      map.addSource('ce', { type: 'geojson', data });
      const colour = ['match', ['get', 'st'], ...Object.entries(COL).flat(), '#C9D3A4'];
      map.addLayer({ id: 'ce-glow', type: 'circle', source: 'ce', paint: { 'circle-color': colour, 'circle-opacity': 0.25, 'circle-blur': 0.6,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 10, 9, 20] } });
      map.addLayer({ id: 'ce-pins', type: 'circle', source: 'ce', paint: { 'circle-color': colour,
        'circle-radius': ['case', ['==', ['get', 's'], focus || ''], 9, 6], 'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5 } });
      const f = focus && data.features.find((x) => x.properties.s === focus);
      if (f) map.jumpTo({ center: f.geometry.coordinates, zoom: 5 });
      else if (data.features.length) {
        const b = new maplibregl.LngLatBounds();
        data.features.forEach((x) => b.extend(x.geometry.coordinates));
        map.fitBounds(b, { padding: 40, maxZoom: 5, duration: 0 });
      }
      setMap = () => {
        map.setFilter('ce-pins', !filter ? null : filter === 'beings' ? ['in', ['get', 's'], ['literal', cards.filter((c) => c.dataset.b === '1').map((c) => c.querySelector('a').pathname.split('/').filter(Boolean).pop())]] : ['==', ['get', 'st'], filter]);
        map.setFilter('ce-glow', map.getFilter('ce-pins'));
      };
      map.on('mouseenter', 'ce-pins', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'ce-pins', () => { map.getCanvas().style.cursor = ''; });
      map.on('click', 'ce-pins', (ev) => {
        const p = ev.features[0].properties;
        const div = document.createElement('div'); div.className = 'pop';
        const a = document.createElement('a'); a.href = p.u; a.textContent = p.n;
        const s = document.createElement('p'); s.textContent = `${p.d} · ${p.p}`;
        div.append(a, s);
        new maplibregl.Popup({ maxWidth: '280px', offset: 10 }).setLngLat(ev.features[0].geometry.coordinates).setDOMContent(div).addTo(map);
      });
    });
  }
  init();
})();

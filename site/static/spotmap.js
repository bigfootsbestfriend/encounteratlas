// Mini map on state and province pages. The page ships a dot picture of the area's spots (drawn at build time);
// "Show map" swaps in a real MapLibre map (about 200 KB, loaded only on that tap) with the same spots.
(function () {
  const box = document.querySelector('.spot-map');
  if (!box) return;
  const btn = box.querySelector('.spot-map-go'), frame = box.querySelector('.spot-map-box');
  const data = JSON.parse(box.querySelector('.spot-data').textContent);
  const CDN = 'https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/';
  const track = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: 'region', ...p }); } catch (e) { /* no analytics */ } };
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  let started = false;

  function lib() {
    if (window.maplibregl) return Promise.resolve();
    if (!document.querySelector('link[href*="maplibre-gl.min.css"]')) {
      const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = CDN + 'maplibre-gl.min.css'; document.head.append(l);
    }
    return new Promise((ok, bad) => { const s = document.createElement('script'); s.src = CDN + 'maplibre-gl.min.js'; s.onload = ok; s.onerror = bad; document.head.append(s); });
  }
  function tint(map) {
    for (const layer of map.getStyle().layers) {
      const id = layer.id;
      try {
        if (layer.type === 'background') map.setPaintProperty(id, 'background-color', '#0F1F19');
        else if (/water/.test(id) && layer.type === 'fill') map.setPaintProperty(id, 'fill-color', '#0A1714');
        else if (/landcover|park|wood|forest|grass/.test(id) && layer.type === 'fill') map.setPaintProperty(id, 'fill-color', '#16302A');
        else if (/boundary/.test(id) && layer.type === 'line') map.setPaintProperty(id, 'line-color', '#3E5E50');
        else if (layer.type === 'symbol' && /place|label/.test(id)) { map.setPaintProperty(id, 'text-color', '#A9B98F'); map.setPaintProperty(id, 'text-halo-color', '#0F1F19'); }
      } catch (e) { /* layer without that property */ }
    }
  }
  async function show() {
    if (started) return;
    started = true;
    btn.disabled = true; btn.textContent = 'Loading map...';
    try { await lib(); } catch (e) { btn.textContent = "Map didn't load"; started = false; btn.disabled = false; return; }
    const div = el('div', 'spot-map-live'); div.setAttribute('aria-label', 'Map of the spots on this page');
    frame.replaceChildren(div);
    btn.hidden = true;
    const map = new maplibregl.Map({ container: div, style: 'https://tiles.openfreemap.org/styles/dark', center: data.features[0].geometry.coordinates,
      zoom: 5, cooperativeGestures: true, maxZoom: 14, attributionControl: { compact: true } });
    map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    const b = new maplibregl.LngLatBounds();
    data.features.forEach((f) => b.extend(f.geometry.coordinates));
    map.fitBounds(b, { padding: 40, maxZoom: 8, duration: 0 });
    map.on('load', () => {
      tint(map);
      map.addSource('spots', { type: 'geojson', data });
      map.addLayer({ id: 'spots', type: 'circle', source: 'spots', paint: {
        'circle-color': ['get', 'col'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 6, 10, 10],
        'circle-stroke-color': '#13261F', 'circle-stroke-width': 2 } });
      map.on('mouseenter', 'spots', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'spots', () => { map.getCanvas().style.cursor = ''; });
      map.on('click', 'spots', (e) => {
        const f = e.features[0], p = f.properties, pop = el('div', 'pop');
        const a = el('a', 'pop-h', p.n); a.href = p.u;
        pop.append(el('div', 'pop-kind', p.kl), a);
        new maplibregl.Popup({ maxWidth: '260px', offset: 10 }).setLngLat(f.geometry.coordinates).setDOMContent(pop).addTo(map);
      });
    });
    track('spot_map_open', { spots: data.features.length });
  }
  btn.hidden = false;
  btn.addEventListener('click', show);
  frame.addEventListener('click', show, { once: true });
})();

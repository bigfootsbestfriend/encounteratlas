// Encounter map: MapLibre + OpenFreeMap dark tiles, clustered Blue Book points.
(function () {
  const el = document.getElementById('map');
  if (!el || !window.maplibregl) return;
  const SAUCER = '<svg class="ico" viewBox="0 0 64 64" fill="currentColor" aria-hidden="true"><ellipse cx="32" cy="31" rx="27" ry="7.5"/><path d="M19 28Q32 7 45 28Z"/></svg>';

  const map = new maplibregl.Map({
    container: el,
    style: 'https://tiles.openfreemap.org/styles/dark',
    center: [-98, 41],
    zoom: window.innerWidth < 720 ? 2.6 : 3.4,
    minZoom: 1.5,
    maxZoom: 14,
    attributionControl: { compact: true },
    cooperativeGestures: false,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');

  // Tint the base map toward the site's night-forest green.
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

  map.on('load', () => {
    tint();
    map.addSource('bluebook', { type: 'geojson', data: el.dataset.geojson, cluster: true, clusterRadius: 38, clusterMaxZoom: 9 });
    map.addLayer({ id: 'bb-glow', type: 'circle', source: 'bluebook', paint: {
      'circle-color': '#F2B33D',
      'circle-radius': ['case', ['has', 'point_count'], ['interpolate', ['linear'], ['get', 'point_count'], 2, 16, 50, 26, 500, 42], 9],
      'circle-blur': 1, 'circle-opacity': 0.35 } });
    map.addLayer({ id: 'bb-clusters', type: 'circle', source: 'bluebook', filter: ['has', 'point_count'], paint: {
      'circle-color': ['interpolate', ['linear'], ['get', 'point_count'], 2, '#C98A22', 100, '#F2B33D', 600, '#FFD27A'],
      'circle-radius': ['interpolate', ['linear'], ['get', 'point_count'], 2, 9, 50, 14, 500, 22],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 2 } });
    map.addLayer({ id: 'bb-count', type: 'symbol', source: 'bluebook', filter: ['has', 'point_count'], layout: {
      'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12, 'text-font': ['Noto Sans Bold'] },
      paint: { 'text-color': '#13261F' } });
    map.addLayer({ id: 'bb-point', type: 'circle', source: 'bluebook', filter: ['!', ['has', 'point_count']], paint: {
      'circle-color': ['case', ['==', ['get', 'a'], 1], '#B98A3A', '#F2B33D'],
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3, 10, 6],
      'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5 } });

    const legend = document.createElement('div');
    legend.className = 'map-legend';
    legend.innerHTML = SAUCER + '<span>Air Force UFO files, 1947 to 1969</span>';
    el.appendChild(legend);

    map.on('click', 'bb-clusters', async (e) => {
      const f = e.features[0];
      const zoom = await map.getSource('bluebook').getClusterExpansionZoom(f.properties.cluster_id);
      map.easeTo({ center: f.geometry.coordinates, zoom });
    });
    map.on('click', 'bb-point', (e) => {
      const p = e.features[0].properties;
      const div = document.createElement('div');
      div.className = 'pop';
      const kind = document.createElement('div');
      kind.className = 'pop-kind';
      kind.innerHTML = SAUCER + '<span>Project Blue Book case</span>';
      const h = document.createElement('p'); h.className = 'pop-h'; h.textContent = p.t || 'Unknown place';
      const meta = document.createElement('p'); meta.style.margin = '0 0 .4rem';
      meta.textContent = [p.r && p.r !== p.t ? p.r : '', p.w].filter(Boolean).join(', ');
      const a = document.createElement('a');
      a.href = 'https://catalog.archives.gov/id/' + p.id; a.rel = 'noopener'; a.textContent = 'Read the Air Force file';
      div.append(kind, h, meta, a);
      if (p.a == 1) {
        const ap = document.createElement('p'); ap.className = 'approx'; ap.style.margin = '.4rem 0 0';
        ap.textContent = 'Approximate: placed in the state or country, not the exact spot.';
        div.append(ap);
      }
      new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(e.features[0].geometry.coordinates).setDOMContent(div).addTo(map);
    });
    for (const id of ['bb-clusters', 'bb-point']) {
      map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
    }
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
        dot.style.cssText = 'width:16px;height:16px;border-radius:50%;background:#7FD3FF;border:3px solid #fff;box-shadow:0 0 0 6px rgba(127,211,255,.3)';
        me = new maplibregl.Marker({ element: dot });
      }
      me.setLngLat(ll).addTo(map);
      map.flyTo({ center: ll, zoom: 8 });
      btn.textContent = label;
    }, () => { btn.textContent = 'Location blocked: allow it in your browser'; }, { enableHighAccuracy: true, timeout: 10000 });
  }));
})();

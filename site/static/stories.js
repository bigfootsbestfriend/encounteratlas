// /stories/ filters. Every card is in the HTML; this only hides and reorders them.
(() => {
  const grid = document.querySelector('.ws-hub');
  if (!grid) return;
  const cards = [...grid.children];
  const cChips = [...document.querySelectorAll('.ws-chips .chip')];
  const sChips = [...document.querySelectorAll('.ws-set .chip')];
  const wSel = document.querySelector('[data-w]');
  const oSel = document.querySelector('[data-o]');
  const count = document.querySelector('[data-count]');
  const qs = new URLSearchParams(location.search);
  const st = { c: qs.get('c') || '', s: qs.get('s') || '', w: qs.get('w') || '', o: qs.get('o') || 'new' };
  if (!cChips.some((b) => b.dataset.c === st.c)) st.c = '';
  if (!sChips.some((b) => b.dataset.s === st.s)) st.s = '';
  if (wSel && ![...wSel.options].some((o) => o.value === st.w)) st.w = '';
  const sorts = {
    new: (a, b) => b.dataset.y - a.dataset.y, old: (a, b) => a.dataset.y - b.dataset.y,
    long: (a, b) => b.dataset.m - a.dataset.m, short: (a, b) => a.dataset.m - b.dataset.m,
  };
  function apply(push) {
    cChips.forEach((b) => b.classList.toggle('on', b.dataset.c === st.c));
    sChips.forEach((b) => b.classList.toggle('on', b.dataset.s === st.s));
    if (wSel) wSel.value = st.w;
    if (oSel) oSel.value = st.o;
    let n = 0;
    for (const d of cards) {
      const show = (!st.c || d.dataset.c === st.c) && (!st.s || d.dataset.s === st.s) && (!st.w || (st.w.endsWith('|') ? d.dataset.w.startsWith(st.w) : d.dataset.w === st.w));
      d.hidden = !show;
      n += show;
    }
    if (oSel) [...cards].sort(sorts[st.o] || sorts.new).forEach((d) => grid.append(d));
    const filtered = st.c || st.s || st.w;
    if (count) {
      count.hidden = !filtered;
      count.textContent = n ? `${n} ${n === 1 ? 'story' : 'stories'}` : 'No stories match. Try fewer filters.';
    }
    if (push) {
      const q = new URLSearchParams();
      for (const k of ['c', 's', 'w']) if (st[k]) q.set(k, st[k]);
      if (st.o !== 'new') q.set('o', st.o);
      history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : ''));
    }
  }
  cChips.forEach((b) => b.addEventListener('click', () => { st.c = b.dataset.c; apply(true); }));
  sChips.forEach((b) => b.addEventListener('click', () => { st.s = b.dataset.s; apply(true); }));
  if (wSel) wSel.addEventListener('change', () => { st.w = wSel.value; apply(true); });
  if (oSel) oSel.addEventListener('change', () => { st.o = oSel.value; apply(true); });
  if (st.c || st.s || st.w || st.o !== 'new') apply(false);
})();

// Story pages: Real / Hoax / Misidentified vote (vote.js sets window.EA).
(() => {
  const box = document.querySelector('[data-vote-item]');
  if (!box) return;
  const start = async () => {
    const { loadTallies, voteWidget } = window.EA;
    const item = box.dataset.voteItem;
    try { await loadTallies([item]); } catch (e) { /* show the widget anyway */ }
    box.replaceChildren(voteWidget(item, { label: 'Real, hoax or misidentified?' }));
  };
  if (window.EA) start();
  else window.addEventListener('load', () => window.EA && start());
})();

// Story pages: a small "where it happened" map, loaded only when it scrolls into view. Always a soft circle, never a pin.
(() => {
  const box = document.querySelector('[data-ws-map]');
  if (!box) return;
  const [lat, lon, z] = box.dataset.wsMap.split(',').map(Number);
  const KM = { 9: 6, 8: 14, 7: 32, 6: 90, 5: 220, 4: 550 };
  const km = KM[z] || 90;
  const sec = box.closest('.ws-where');
  const cat = ([...sec.classList].find((k) => k.startsWith('cat-')) || 'cat-other').slice(4);
  const colour = getComputedStyle(document.documentElement).getPropertyValue('--c-' + cat).trim() || '#E0C36A';
  const ring = () => {
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * 2 * Math.PI;
      pts.push([lon + (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.cos(a), lat + (km / 110.57) * Math.sin(a)]);
    }
    return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [pts] } };
  };
  const load = (src, css) => new Promise((ok, bad) => {
    if (css) { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = src; l.onload = ok; l.onerror = bad; document.head.append(l); return; }
    const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = bad; document.head.append(s);
  });
  const draw = async () => {
    const V = 'https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/';
    try {
      if (!window.maplibregl) await Promise.all([load(V + 'maplibre-gl.min.css', true), load(V + 'maplibre-gl.min.js')]);
    } catch (e) { sec.classList.add('ws-where-nomap'); return; }
    // Pull back so the circle sits in context: about 4 circle-widths across the box.
    const zoom = Math.max(1.5, Math.log2((box.clientWidth * 78271 * Math.cos((lat * Math.PI) / 180)) / (km * 1000 * 8)));
    const map = new maplibregl.Map({ container: box, style: 'https://tiles.openfreemap.org/styles/dark', center: [lon, lat], zoom,
      interactive: false, attributionControl: { compact: true } });
    map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
    map.on('load', () => {
      map.addSource('area', { type: 'geojson', data: ring() });
      map.addLayer({ id: 'area-fill', type: 'fill', source: 'area', paint: { 'fill-color': colour, 'fill-opacity': 0.28 } });
      map.addLayer({ id: 'area-line', type: 'line', source: 'area', paint: { 'line-color': colour, 'line-width': 2, 'line-dasharray': [2, 2] } });
    });
  };
  if (!('IntersectionObserver' in window)) { draw(); return; }
  const io = new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) { io.disconnect(); draw(); } }, { rootMargin: '300px' });
  io.observe(box);
})();

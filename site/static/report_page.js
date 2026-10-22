// Static reader-report pages (/reports/<pid>/, built by site/sections/reports.py). The story and facts are in the HTML;
// this only adds the live parts: Real/Hoax votes, the rough-area map, and an Edit bar when the reader wrote it.
(() => {
  const root = document.querySelector('[data-report]');
  if (!root) return;
  const start = async () => {
    const EA = window.EA;
    if (!EA) return;
    const pid = root.dataset.report;
    const boxes = [...document.querySelectorAll('[data-vote-item]')];
    try { await EA.loadTallies(boxes.map((b) => b.dataset.voteItem)); } catch (e) { /* show the widgets anyway */ }
    for (const b of boxes) {
      const item = b.dataset.voteItem;
      b.replaceWith(EA.voteWidget(item, { label: b.dataset.voteLabel, compact: b.hasAttribute('data-vote-compact'), ai: item[0] !== 'r' }));
    }
    if (location.hash === '#vote') document.getElementById('vote')?.scrollIntoView();

    // Map: a soft circle, never a pin (the point is already the public ~5 km cell, or ~100 km for living traditions).
    const mapEl = root.querySelector('[data-rep-map]');
    const [lat, lon, km, zoom] = (mapEl?.dataset.repMap || '').split(',').map(Number);
    if (mapEl && Number.isFinite(lat) && Number.isFinite(lon)) {
      const draw = () => {
        const map = EA.makeMap(mapEl, { center: [lon, lat], zoom, maxZoom: km > 10 ? 7 : 11, cooperative: true });
        if (map) map.on('load', () => EA.areaLayer(map, 'area', lon, lat, km));
      };
      if (window.maplibregl) draw();
      else window.addEventListener('load', () => window.maplibregl && draw());
    }

    // The reader who sent it (signed in on this device) gets the same Edit bar as /reports/?id=.
    if (EA.session()) {
      const r = await EA.api('/api/reports/' + encodeURIComponent(pid));
      const R = r.status === 200 && r.data.report;
      if (R && R.owner) {
        const slot = root.querySelector('[data-owner-slot]');
        slot.replaceWith(EA.h('div', { class: 'owner-bar' }, EA.h('span', { class: `pill pill-${R.status}`, text: R.status }),
          EA.h('span', { text: ' Your report. Edits go back to a moderator before they show here. ' }),
          EA.h('a', { href: `${EA.BASE}/report/?edit=${R.id}`, text: 'Edit' })));
      }
    }
  };
  if (window.EA) start();
  else window.addEventListener('load', start);
})();

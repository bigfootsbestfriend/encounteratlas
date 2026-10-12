// Home page: search box, "this month in the Air Force files", and a "near you" list after locate.
(() => {
  const BASE = (document.getElementById('map') || {}).dataset?.base || '';
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const caseLink = (p) => `https://catalog.archives.gov/id/${p.id}`;

  // Search
  const box = document.querySelector('.search');
  if (box) {
    const input = box.querySelector('input');
    const list = box.querySelector('.search-results');
    let index = null;
    let active = -1;
    const load = () => index || (index = fetch(box.dataset.index).then((r) => r.json()));
    const norm = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    async function run() {
      const q = norm(input.value.trim());
      if (q.length < 2) { list.hidden = true; return; }
      const items = await load();
      const scored = [];
      for (const it of items) {
        const t = norm(it.t), a = norm(it.a || '');
        let s = t.startsWith(q) ? 0 : t.includes(q) ? 1 : a.split(' ').some((w) => w.startsWith(q)) ? 2 : a.includes(q) ? 3 : -1;
        if (s >= 0) scored.push([s, t.length, it]);
      }
      scored.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
      active = -1;
      list.innerHTML = scored.length
        ? scored.slice(0, 8).map(([, , it]) => `<li><a href="${esc(it.u)}" class="cat-${esc(it.c)}"><span class="mask-ico" style="--m:url('${BASE}/static/${it.i.startsWith('art/') ? '' : 'icons/'}${esc(it.i)}.svg')"></span><span><b>${esc(it.t)}</b><small>${esc(it.k)}</small></span></a></li>`).join('')
        : `<li class="none">Nothing matches "${esc(input.value.trim())}". Try another name, a state or a country.</li>`;
      list.hidden = false;
    }
    input.addEventListener('focus', load, { once: true });
    input.addEventListener('input', run);
    input.addEventListener('keydown', (e) => {
      const links = [...list.querySelectorAll('a')];
      if (!links.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        active = (active + (e.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
        links.forEach((l, i) => l.classList.toggle('on', i === active));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        location.href = links[Math.max(active, 0)].href;
      } else if (e.key === 'Escape') {
        list.hidden = true;
      }
    });
    document.addEventListener('click', (e) => { if (!box.contains(e.target)) list.hidden = true; });
  }

  // Blue Book points, shared by the two lists below
  let bb = null;
  const loadBB = () => bb || (bb = fetch(BASE + '/data/bluebook.geojson').then((r) => r.json()).then((d) => d.features));

  // This month in the Air Force files
  const monthBox = document.querySelector('.this-month');
  if (monthBox) {
    const m = new Date().getMonth();
    monthBox.querySelector('.month-name').textContent = LONG[m];
    loadBB().then((feats) => {
      const hits = feats.filter((f) => f.properties.w.startsWith(MONTHS[m] + ' ') && f.properties.a === 0);
      // A different handful each day, spread across the years
      const day = Math.floor(Date.now() / 864e5);
      const pick = hits.map((f, i) => [((f.properties.id + day) * 2654435761) % 4294967296, f]).sort((x, y) => x[0] - y[0]).slice(0, 8).map((x) => x[1]);
      pick.sort((x, y) => x.properties.y - y.properties.y);
      monthBox.querySelector('.month-list').innerHTML = pick.map((f) => {
        const p = f.properties;
        const where = p.t === p.r || !p.r ? p.t : `${p.t}, ${p.r}`;
        return `<li><span class="yr">${esc(p.w)}</span><span><a href="${caseLink(p)}" rel="noopener">${esc(where)}</a></span></li>`;
      }).join('') + `<li><span class="yr"></span><span>${hits.length.toLocaleString()} reports in all from ${LONG[m]}s</span></li>`;
    }).catch(() => { monthBox.hidden = true; });
  }

  // Near you, after "Use my location"
  const near = document.querySelector('.near');
  if (near) {
    const km = (a, b) => {
      const r = Math.PI / 180, dLat = (b[1] - a[1]) * r, dLon = (b[0] - a[0]) * r;
      const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLon / 2) ** 2;
      return 12742 * Math.asin(Math.sqrt(h));
    };
    document.addEventListener('ea:located', async (e) => {
      const ll = e.detail;
      const [feats, famous] = await Promise.all([loadBB(), fetch(BASE + '/data/famous.geojson').then((r) => r.json()).then((d) => d.features).catch(() => [])]);
      const rows = [];
      for (const f of famous) rows.push([km(ll, f.geometry.coordinates), `<a href="${BASE}/creatures/${esc(f.properties.s)}/">${esc(f.properties.n)}: ${esc(f.properties.t)}</a>`, f.properties.y || '']);
      for (const f of feats) if (f.properties.a === 0) rows.push([km(ll, f.geometry.coordinates), `<a href="${caseLink(f.properties)}" rel="noopener">UFO report: ${esc(f.properties.t)}</a>`, f.properties.w]);
      rows.sort((x, y) => x[0] - y[0]);
      const mi = (k) => (k * 0.621371 < 1 ? 'under a mile' : `${Math.round(k * 0.621371)} mi`);
      near.querySelector('.near-list').innerHTML = rows.slice(0, 8).map(([k, link, when]) =>
        `<li><span class="yr">${mi(k)}</span><span>${link}${when ? ` <small>${esc(when)}</small>` : ''}</span></li>`).join('');
      near.hidden = false;
      near.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }
})();

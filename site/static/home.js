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
    const dist = (a, b, cap) => { // Levenshtein distance, giving up once every cell in a row passes cap
      if (Math.abs(a.length - b.length) > cap) return cap + 1;
      let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
      for (let i = 1; i <= a.length; i++) {
        const cur = [i];
        let low = i;
        for (let j = 1; j <= b.length; j++) { cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); low = Math.min(low, cur[j]); }
        if (low > cap) return cap + 1;
        prev = cur;
      }
      return prev[b.length];
    };
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
      let fuzzy = false;
      if (!scored.length && q.length >= 4) { // typo fallback: nearest names within a small edit distance ("ogopogoo", "chupacabre")
        const qw = q.split(/\s+/).length, max = q.length <= 5 ? 1 : q.length <= 9 ? 2 : 3;
        for (const it of items) {
          const ws = (norm(it.t) + ' ' + norm(it.a || '')).split(/[^a-z0-9']+/).filter(Boolean);
          let best = max + 1;
          for (let i = 0; i + qw <= ws.length && best; i++) {
            best = Math.min(best, dist(q, ws.slice(i, i + qw).join(' '), best));
            if (qw === 1 && i + 2 <= ws.length) best = Math.min(best, dist(q, ws[i] + ws[i + 1], best)); // "lochness" -> "loch ness"
          }
          if (best <= max) scored.push([best, norm(it.t).length, it]);
        }
        fuzzy = scored.length > 0;
      }
      scored.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
      active = -1;
      list.innerHTML = (fuzzy ? `<li class="none">No exact match for "${esc(input.value.trim())}". Did you mean:</li>` : '') + (scored.length
        ? scored.slice(0, +box.dataset.limit || 8).map(([, , it]) => `<li><a href="${esc(it.u)}" class="cat-${esc(it.c)}"><span class="mask-ico" style="--m:url('${BASE}/static/${it.i.startsWith('art/') ? '' : 'icons/'}${esc(it.i)}.svg')"></span><span><b>${esc(it.t)}</b><small>${esc(it.k)}</small></span></a></li>`).join('')
        : `<li class="none">Nothing matches "${esc(input.value.trim())}". Try another name, a state or a country.</li>`);
      list.hidden = false;
    }
    input.addEventListener('focus', load, { once: true });
    const pre = new URLSearchParams(location.search).get('q');
    if (pre) { input.value = pre; run(); }
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

  // Blue Book points for "Near you" (the full map file, only fetched after "Use my location")
  let bb = null;
  const loadBB = () => bb || (bb = fetch(BASE + '/data/bluebook.geojson').then((r) => r.json()).then((d) => d.features));

  // This month in the Air Force files: a small per-month list, fetched when the box comes near the screen
  const monthBox = document.querySelector('.this-month');
  if (monthBox) {
    const m = new Date().getMonth();
    monthBox.querySelector('.month-name').textContent = LONG[m];
    const fill = () => fetch(`${BASE}/data/bluebook-month/${String(m + 1).padStart(2, '0')}.json`).then((r) => r.json()).then((rows) => {
      const hits = rows.map(([id, t, r, w, y]) => ({ id, t, r, w, y }));
      // A different handful each day, spread across the years
      const day = Math.floor(Date.now() / 864e5);
      const pick = hits.map((p) => [((p.id + day) * 2654435761) % 4294967296, p]).sort((x, y) => x[0] - y[0]).slice(0, 8).map((x) => x[1]);
      pick.sort((x, y) => x.y - y.y);
      monthBox.querySelector('.month-list').innerHTML = pick.map((p) => {
        const where = p.t === p.r || !p.r ? p.t : `${p.t}, ${p.r}`;
        return `<li><span class="yr">${esc(p.w)}</span><span><a href="${caseLink(p)}" rel="noopener" target="_blank">${esc(where)}</a></span></li>`;
      }).join('') + `<li><span class="yr"></span><span><a href="${BASE}/ufo/blue-book/">All ${hits.length.toLocaleString()} ${LONG[m]} reports in the Air Force files</a></span></li>`;
    }).catch(() => { monthBox.hidden = true; });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver((es, o) => { if (es.some((e) => e.isIntersecting)) { o.disconnect(); fill(); } }, { rootMargin: '600px 0px' }).observe(monthBox);
    } else fill();
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
      const [feats, famous, canada] = await Promise.all([loadBB(), fetch(BASE + '/data/famous.geojson').then((r) => r.json()).then((d) => d.features).catch(() => []),
        fetch(BASE + '/data/ufo_canada.geojson').then((r) => r.json()).then((d) => d.features).catch(() => [])]);
      const rows = [];
      // Canadian UFO Survey towns: one row per town, so a city with 300 reports doesn't fill the list
      for (const f of canada) if (f.properties.a === 0) rows.push([km(ll, f.geometry.coordinates), `<a href="${esc(f.properties.u)}">UFO reports in ${esc(f.properties.t)}: ${f.properties.n}</a>`, 'since 1989', 'ca']);
      for (const f of famous) rows.push([km(ll, f.geometry.coordinates), `<a href="${BASE}/creatures/${esc(f.properties.s)}/">${esc(f.properties.n)}: ${esc(f.properties.t)}</a>`, f.properties.y || '']);
      for (const f of feats) if (f.properties.a === 0) rows.push([km(ll, f.geometry.coordinates), `<a href="${caseLink(f.properties)}" rel="noopener" target="_blank">UFO report: ${esc(f.properties.t)}</a>`, f.properties.w]);
      rows.sort((x, y) => x[0] - y[0]);
      // Miles for US visitors, kilometres for everyone else (Canada included)
      const usa = /-US$/i.test(navigator.language || '') && !/^America\/(Toronto|Montreal|Vancouver|Edmonton|Calgary|Winnipeg|Regina|Swift_Current|Halifax|Moncton|Glace_Bay|Goose_Bay|St_Johns|Whitehorse|Dawson|Dawson_Creek|Fort_Nelson|Creston|Yellowknife|Inuvik|Iqaluit|Rankin_Inlet|Cambridge_Bay|Resolute|Pangnirtung|Atikokan|Thunder_Bay|Nipigon|Rainy_River|Blanc-Sablon)$/.test(Intl.DateTimeFormat().resolvedOptions().timeZone || '');
      const mi = (k) => (usa ? (k * 0.621371 < 1 ? 'under a mile' : `${Math.round(k * 0.621371)} mi`) : (k < 1 ? 'under 1 km' : `${Math.round(k)} km`));
      // At most 3 Canadian-town rows, so famous cases and Air Force files still show
      let nca = 0;
      const top = rows.filter((r) => r[3] !== 'ca' || ++nca <= 3).slice(0, 8);
      near.querySelector('.near-list').innerHTML = top.map(([k, link, when]) =>
        `<li><span class="yr">${mi(k)}</span><span>${link}${when ? ` <small>${esc(when)}</small>` : ''}</span></li>`).join('');
      near.hidden = false;
      near.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }
})();

// Home page: "Latest reader reports" box. Shows the three newest approved reports with the creature poster;
// the pill counts how many went up in the last 7 days. Hidden when there are none.
(() => {
  const sec = document.querySelector('.new-reports');
  if (!sec || !sec.dataset.api) return;
  const BASE = sec.dataset.base || '';
  const SKY = { hominid: ['#E3A649', '#B5532F'], canid: ['#3B4C6B', '#1B2A3A'], winged: ['#3B4C6B', '#1B2A3A'], aquatic: ['#E8B04A', '#C8693A'],
    entity: ['#3B4C6B', '#1B2A3A'], ufo: ['#2E3E5C', '#141E2E'], fae: ['#C97B9A', '#4A2E4F'], other: ['#3B4C6B', '#1B2A3A'] };
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const place = (p) => { p = String(p || '').trim(); return p && p === p.toLowerCase() ? p.replace(/(^|[\s-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase()) : p; };
  const ago = (t) => { const d = Math.floor((Date.now() / 1000 - t) / 86400); return d < 1 ? 'today' : d === 1 ? 'yesterday' : d < 30 ? `${d} days ago` : ''; };
  let n = 0;
  function poster(art, cat) {
    const [a, b] = SKY[cat] || SKY.other, id = 'nrsky' + (++n), wet = cat === 'aquatic';
    const ground = wet ? '<rect y="160" width="200" height="40" fill="#2B4A55"/>'
      : '<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="#1E3A2F"/>';
    return `<svg viewBox="0 0 200 200" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>` +
      `<clipPath id="c${id}"><rect x="6" y="6" width="188" height="188" rx="10"/></clipPath></defs><g clip-path="url(#c${id})"><rect width="200" height="200" fill="url(#${id})"/>` +
      `<circle cx="150" cy="52" r="24" fill="#F3E3B8" opacity=".9"/><path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="#5E4A3A" opacity=".5"/>${ground}` +
      `<image href="${BASE}/static/${art}.svg" x="22" y="${wet ? 34 : 26}" width="160" height="160"/></g><rect x="6" y="6" width="188" height="188" rx="10" fill="none" stroke="#F3E3B8" stroke-width="4"/></svg>`;
  }
  Promise.all([
    fetch(sec.dataset.api + '/api/reports?limit=3').then((r) => (r.ok ? r.json() : null)),
    fetch(sec.dataset.index).then((r) => r.json()).catch(() => []),
  ]).then(([d, idx]) => {
    if (!d || !d.reports || !d.reports.length) return;
    const art = {};
    for (const x of idx) { const m = /\/creatures\/([^/]+)\/$/.exec(x.u || ''); if (m) art[m[1]] = { i: x.i, c: x.c, t: x.t }; }
    const week = Date.now() / 1000 - 7 * 86400;
    const fresh = d.reports.filter((x) => x.approved_at > week).length;
    if (fresh) sec.querySelector('[data-nr-count]').textContent = `${fresh}${d.next && fresh === d.reports.length ? '+' : ''} new this week`;
    sec.querySelector('.nr-list').innerHTML = d.reports.map((x) => {
      const a = art[x.creature] || { i: 'art/unknown-shape', c: 'other', t: 'Something else' };
      const icon = String(a.i).startsWith('art/') ? a.i : 'art/unknown-shape';
      const what = x.creature === 'other' ? (x.other_what || 'Something strange') : a.t;
      const where = place(x.place);
      const isNew = x.approved_at > week;
      return `<a class="nr-card" href="${BASE}/reports/${encodeURIComponent(x.id)}/">
        <span class="nr-art">${poster(icon, a.c)}${isNew ? '<span class="nr-new">New</span>' : ''}</span>
        <span class="nr-body"><span class="nr-what">${esc(what.length > 60 ? what.slice(0, 58) + '…' : what)}</span>
        <span class="nr-where">${esc(where || 'Place not named')}${ago(x.approved_at) ? ' · added ' + ago(x.approved_at) : ''}</span>
        <span class="nr-snip">${esc(x.snippet)}</span><span class="nr-go">Read the report</span></span></a>`;
    }).join('');
    sec.hidden = false;
  }).catch(() => {});
})();

// "What happened on this day" link in the hero points straight at today's page.
(() => {
  const a = document.querySelector('[data-otd-today]'); if (!a) return;
  const t = new Date(), m = t.toLocaleDateString('en-US', { month: 'long' });
  a.href = a.getAttribute('href') + m.toLowerCase() + '-' + t.getDate() + '/';
  a.textContent = 'What happened on ' + m + ' ' + t.getDate();
})();

// Podcast directory: search, topic filter and sort. Works on the server-rendered cards (default order = recommended).
(function () {
  const grid = document.querySelector('.pod-grid');
  if (!grid) return;
  const q = document.getElementById('pq');
  const sort = document.getElementById('psort');
  const chips = [...document.querySelectorAll('.chips.light .chip')];
  const cards = [...grid.querySelectorAll('.pod')];
  const count = document.getElementById('pcount');
  const empty = document.querySelector('.empty');
  let topic = '';
  const sorters = {
    score: (a, b) => b.dataset.score - a.dataset.score,
    latest: (a, b) => b.dataset.latest.localeCompare(a.dataset.latest),
    eps: (a, b) => b.dataset.eps - a.dataset.eps,
    active: (a, b) => (b.dataset.active - a.dataset.active) || (b.dataset.score - a.dataset.score),
    az: (a, b) => a.querySelector('.pod-name').textContent.localeCompare(b.querySelector('.pod-name').textContent),
  };
  function apply() {
    const terms = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const c of cards) {
      const ok = (!topic || c.dataset.topics.split(' ').includes(topic)) && terms.every((t) => c.dataset.names.includes(t));
      c.hidden = !ok;
      if (ok) shown++;
    }
    count.textContent = shown;
    empty.hidden = shown > 0;
    const params = new URLSearchParams();
    if (topic) params.set('topic', topic);
    if (q.value.trim()) params.set('q', q.value.trim());
    if (sort.value !== 'score') params.set('sort', sort.value);
    history.replaceState(null, '', (params.toString() ? '?' + params : location.pathname) + location.hash);
  }
  function reorder() {
    const sorted = [...cards].sort(sorters[sort.value] || sorters.score);
    grid.append(...sorted);
  }
  q.addEventListener('input', apply);
  sort.addEventListener('change', () => { reorder(); apply(); });
  chips.forEach((chip) => chip.addEventListener('click', () => {
    topic = topic === chip.dataset.filter ? '' : chip.dataset.filter;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.filter === topic)));
    apply();
  }));
  const pre = new URLSearchParams(location.search);
  if (pre.get('q')) q.value = pre.get('q');
  if (pre.get('sort') && sorters[pre.get('sort')]) { sort.value = pre.get('sort'); reorder(); }
  if (pre.get('topic')) {
    topic = pre.get('topic');
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.filter === topic)));
  }
  if ([...pre.keys()].length) apply();
})();

// Spin the dial: a random playable episode, filtered by length. Loads /data/podcast-play.json on the first spin only.
(function () {
  const box = document.querySelector('[data-spin]');
  if (!box) return;
  const cfg = JSON.parse(box.dataset.spin);
  const out = box.querySelector('.spin-out');
  const go = box.querySelector('.spin-go');
  const lens = [...box.querySelectorAll('[data-len]')];
  const hasArt = new Set(cfg.art);
  let len = 'any', pool = null, last = '';
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fits = (m) => len === 'any' || (m > 0 && (len === 'short' ? m < 30 : len === 'mid' ? m >= 30 && m <= 60 : m > 60));
  lens.forEach((b) => b.addEventListener('click', () => {
    len = b.dataset.len;
    lens.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  }));
  async function load() {
    if (pool) return pool;
    const d = await fetch(cfg.data).then((r) => r.json());
    pool = [];
    for (const [slug, eps] of Object.entries(d)) if (cfg.names[slug]) eps.forEach((e) => pool.push([slug, e]));
    return pool;
  }
  async function spin() {
    go.classList.add('spinning');
    setTimeout(() => go.classList.remove('spinning'), 750);
    let all;
    try { all = await load(); } catch (e) { out.innerHTML = '<p class="spin-hint">Couldn\'t load episodes. Try again in a moment.</p>'; return; }
    const ok = all.filter(([, e]) => fits(e.m) && e.a !== last);
    if (!ok.length) { out.innerHTML = '<p class="spin-hint">Nothing that length right now. Try another length.</p>'; return; }
    const [slug, e] = ok[Math.floor(Math.random() * ok.length)];
    last = e.a;
    const art = hasArt.has(slug) ? `<img src="${cfg.thumb}${slug}.webp" alt="" width="360" height="257">` : '<span class="pn-noart"></span>';
    const pp = esc(JSON.stringify(e));
    setTimeout(() => {
      out.classList.add('has-ep');
      out.innerHTML = `<div class="spin-card"><div class="pn-art">${art}${e.m ? `<span class="pn-min">${e.m} min</span>` : ''}` +
        `<button type="button" class="pn-share" data-pp-share aria-label="Save or share this episode"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>Save</button>` +
        `<button type="button" class="pp-btn pp-round pn-play" data-pp="${pp}" aria-label="Play ${esc(e.t)}"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.1v13.8a1 1 0 0 0 1.5.86l11-6.9a1 1 0 0 0 0-1.72l-11-6.9A1 1 0 0 0 8 5.1z"/></svg><span></span></button></div>` +
        `<div class="pn-body"><a class="pn-crit" href="${cfg.crit}${slug}/">${esc(cfg.names[slug])}</a><b class="pn-t">${esc(e.t)}</b>` +
        `<small>${esc(e.s)}</small><button type="button" class="spin-again">Not feeling it? Spin again</button></div></div>`;
      out.querySelector('.spin-again').addEventListener('click', spin);
    }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 450);
    if (window.gtag) try { window.gtag('event', 'podcast_spin', { page_type: 'podcasts', length: len }); } catch (x) { /* no analytics */ }
  }
  go.addEventListener('click', spin);
})();

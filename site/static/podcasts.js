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

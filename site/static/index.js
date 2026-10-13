// Creature index: search by any name or alias, filter by type.
(function () {
  const q = document.getElementById('q');
  const cards = [...document.querySelectorAll('.crit')];
  const groups = [...document.querySelectorAll('.cat-group')];
  const chips = [...document.querySelectorAll('.chip')];
  const empty = document.querySelector('.empty');
  let cat = '';
  const whSel = document.getElementById('where');
  let wh = '';
  function apply() {
    const term = q.value.trim().toLowerCase();
    let shown = 0;
    for (const c of cards) {
      const ok = (!term || c.dataset.names.includes(term)) && (!cat || c.dataset.cat === cat) && (!wh || (c.dataset.w || '').split(' ').includes(wh));
      c.hidden = !ok;
      if (ok) shown++;
    }
    for (const g of groups) g.hidden = !g.querySelector('.crit:not([hidden])');
    empty.hidden = shown > 0;
  }
  q.addEventListener('input', apply);
  if (whSel) whSel.addEventListener('change', () => { wh = whSel.value; apply(); });
  chips.forEach((chip) => chip.addEventListener('click', () => {
    cat = cat === chip.dataset.filter ? '' : chip.dataset.filter;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.filter === cat)));
    apply();
  }));
  // Sort within each category group; the HTML ships in "most sightings" order so it works without JS.
  const sel = document.getElementById('sort');
  const num = (c, k) => +c.dataset[k] || 0;
  const name = (c) => c.querySelector('.crit-name').textContent;
  const SORTS = {
    most: (a, b) => num(b, 'n') - num(a, 'n') || name(a).localeCompare(name(b)),
    fewest: (a, b) => num(a, 'n') - num(b, 'n') || name(a).localeCompare(name(b)),
    recent: (a, b) => num(b, 'last') - num(a, 'last') || num(b, 'n') - num(a, 'n'),
    oldest: (a, b) => num(a, 'first') - num(b, 'first') || name(a).localeCompare(name(b)),
    loc: (a, b) => (a.dataset.loc || '').localeCompare(b.dataset.loc || '') || name(a).localeCompare(name(b)),
    size: (a, b) => num(b, 'size') - num(a, 'size') || name(a).localeCompare(name(b)),
    az: (a, b) => name(a).localeCompare(name(b)),
  };
  function sortAll() {
    const f = SORTS[sel.value] || SORTS.most;
    document.querySelectorAll('.cat-group .crit-grid').forEach((g) => [...g.children].sort(f).forEach((c) => g.appendChild(c)));
    try { localStorage.setItem('ea-sort', sel.value); } catch (e) { /* storage blocked */ }
  }
  if (sel) {
    sel.addEventListener('change', sortAll);
    let saved = null; try { saved = localStorage.getItem('ea-sort'); } catch (e) { /* storage blocked */ }
    if (saved && SORTS[saved] && saved !== 'most') { sel.value = saved; sortAll(); }
  }
  const params = new URLSearchParams(location.search);
  const pre = params.get('q'), preW = params.get('where');
  if (preW && whSel && whSel.querySelector(`option[value="${CSS.escape(preW)}"]`)) { whSel.value = wh = preW; }
  if (pre) q.value = pre;
  if (pre || wh) apply();
})();

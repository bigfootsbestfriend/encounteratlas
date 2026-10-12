// Creature index: search by any name or alias, filter by type.
(function () {
  const q = document.getElementById('q');
  const cards = [...document.querySelectorAll('.crit')];
  const groups = [...document.querySelectorAll('.cat-group')];
  const chips = [...document.querySelectorAll('.chip')];
  const empty = document.querySelector('.empty');
  let cat = '';
  function apply() {
    const term = q.value.trim().toLowerCase();
    let shown = 0;
    for (const c of cards) {
      const ok = (!term || c.dataset.names.includes(term)) && (!cat || c.dataset.cat === cat);
      c.hidden = !ok;
      if (ok) shown++;
    }
    for (const g of groups) g.hidden = !g.querySelector('.crit:not([hidden])');
    empty.hidden = shown > 0;
  }
  q.addEventListener('input', apply);
  chips.forEach((chip) => chip.addEventListener('click', () => {
    cat = cat === chip.dataset.filter ? '' : chip.dataset.filter;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.filter === cat)));
    apply();
  }));
  const pre = new URLSearchParams(location.search).get('q');
  if (pre) { q.value = pre; apply(); }
})();

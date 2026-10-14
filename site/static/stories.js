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

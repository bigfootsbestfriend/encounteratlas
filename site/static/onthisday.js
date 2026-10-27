// On this day: month and day dials, Today and a "Random strange day" dice. The prev/next arrows are plain links,
// so the page works with JS off; this only shows the dials and buttons and makes them go.
(function () {
  const box = document.querySelector('.otd-spin');
  if (!box) return;
  const MON = ['', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];
  const LEN = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const BASE = box.dataset.base;
  const days = JSON.parse((document.getElementById('otd-days') || {}).textContent || '{}');
  const mSel = document.getElementById('otd-m'), dSel = document.getElementById('otd-d');
  const go = box.querySelector('.otd-go'), hint = box.querySelector('.otd-hint');
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const track = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: 'on-this-day', ...p }); } catch (e) { /* no analytics */ } };
  const key = (m, d) => String(m).padStart(2, '0') + '-' + String(d).padStart(2, '0');
  const label = (m, d) => MON[m][0].toUpperCase() + MON[m].slice(1) + ' ' + d;
  const url = (m, d) => BASE + MON[m] + '-' + d + '/';

  function fillDays(m, keep) {
    const want = Math.min(keep || 1, LEN[m]);
    const opts = [];
    for (let d = 1; d <= LEN[m]; d++) {
      const o = document.createElement('option');
      o.value = d; o.textContent = days[key(m, d)] ? d + ' •' : String(d);
      opts.push(o);
    }
    dSel.replaceChildren(...opts);
    dSel.value = want;
  }
  function show() {
    const m = +mSel.value, d = +dSel.value, n = days[key(m, d)] || 0;
    go.textContent = 'Go to ' + label(m, d);
    hint.textContent = n ? n + ' strange stor' + (n === 1 ? 'y' : 'ies') + ' on ' + label(m, d) + '. Dots mark days with stories.'
      : 'Nothing famous on ' + label(m, d) + ' yet. Dots mark days with stories.';
  }
  function set(m, d) { mSel.value = m; fillDays(m, d); show(); }

  const here = box.dataset.here;
  const now = new Date();
  if (here) set(+here.slice(0, 2), +here.slice(3));
  else set(now.getMonth() + 1, now.getDate());

  mSel.addEventListener('change', () => { fillDays(+mSel.value, +dSel.value); show(); });
  dSel.addEventListener('change', show);
  box.querySelectorAll('.otd-step').forEach((b) => b.addEventListener('click', () => {
    let m = +mSel.value, d = +dSel.value;
    const by = +b.dataset.by;
    if (b.dataset.k === 'm') m = ((m - 1 + by + 12) % 12) + 1;
    else {
      d += by;
      if (d < 1) { m = m === 1 ? 12 : m - 1; d = LEN[m]; } else if (d > LEN[m]) { m = m === 12 ? 1 : m + 1; d = 1; }
    }
    set(m, d);
    const sel = b.dataset.k === 'm' ? mSel : dSel;
    if (!calm) { sel.classList.remove('otd-bump'); void sel.offsetWidth; sel.classList.add('otd-bump'); }
  }));
  go.addEventListener('click', () => {
    track('otd_spin', { how: 'dials', day: key(+mSel.value, +dSel.value) });
    location.href = url(+mSel.value, +dSel.value);
  });
  box.querySelectorAll('.otd-arrow').forEach((a) => a.addEventListener('click', () => track('otd_spin', { how: a.classList.contains('otd-prev') ? 'prev' : 'next' })));

  const today = box.querySelector('.otd-today');
  if (today) {
    today.textContent = 'Today: ' + label(now.getMonth() + 1, now.getDate());
    today.addEventListener('click', () => { track('otd_spin', { how: 'today' }); location.href = url(now.getMonth() + 1, now.getDate()); });
  }

  // Random: spin both dials for a moment, land on a day that has stories, then go there
  const dice = box.querySelector('.otd-random');
  const pool = Object.keys(days).filter((k) => k !== here);
  dice.addEventListener('click', () => {
    if (!pool.length || dice.disabled) return;
    const k = pool[Math.floor(Math.random() * pool.length)], m = +k.slice(0, 2), d = +k.slice(3);
    track('otd_random', { day: k, stories: days[k] });
    dice.disabled = true; box.classList.add('otd-rolling');
    const land = () => {
      set(m, d);
      hint.textContent = 'Landed on ' + label(m, d) + ': ' + days[k] + ' strange stor' + (days[k] === 1 ? 'y' : 'ies') + '. Taking you there...';
      setTimeout(() => { location.href = url(m, d); }, calm ? 0 : 500);
    };
    if (calm) return land();
    let n = 0;
    const t = setInterval(() => {
      const rm = 1 + Math.floor(Math.random() * 12);
      set(rm, 1 + Math.floor(Math.random() * LEN[rm]));
      if (++n >= 12) { clearInterval(t); box.classList.remove('otd-rolling'); land(); }
    }, 60);
  });

  window.addEventListener('pageshow', (e) => { if (e.persisted) { dice.disabled = false; box.classList.remove('otd-rolling'); } });
  box.querySelector('.otd-dials').hidden = false;
  box.querySelector('.otd-quick').hidden = false;
})();

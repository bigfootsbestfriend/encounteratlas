// Creature pages: show this creature's latest approved reader reports, if it has any.
(() => {
  const sec = document.querySelector('[data-rr]');
  if (!sec || !sec.dataset.api) return;
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const when = (d) => {
    const [y, m, day] = (d || '').split('-').map(Number);
    if (!y) return '';
    return m ? `${MONTHS[m - 1]} ${day ? day + ', ' : ''}${y}` : String(y);
  };
  fetch(`${sec.dataset.api}/api/reports?limit=6&creature=${encodeURIComponent(sec.dataset.rr)}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d || !d.reports || !d.reports.length) return;
      const list = sec.querySelector('.rr-list');
      const all = sec.querySelector('p:last-child a').getAttribute('href');
      const reportsPage = all.split('?')[0];
      for (const x of d.reports) {
        const a = document.createElement('a');
        a.className = 'ws-card';
        a.href = `${reportsPage}${encodeURIComponent(x.id)}/`;
        const b = document.createElement('b');
        b.textContent = x.place || 'Somewhere';
        const m = document.createElement('span');
        m.className = 'ws-meta';
        m.textContent = (x.date_approx ? 'Around ' : '') + when(x.seen_date) + (x.witnesses > 1 ? ` · ${x.witnesses} witnesses` : '');
        const t = document.createElement('span');
        t.className = 'ws-dek';
        t.textContent = x.snippet;
        const g = document.createElement('span');
        g.className = 'ws-go';
        g.textContent = 'Read the report';
        a.append(b, m, t, g);
        list.append(a);
      }
      list.classList.add('ws-grid');
      sec.hidden = false;
      const link = document.querySelector('[data-rr-link]');
      if (link) { link.hidden = false; link.textContent = `${d.reports.length}${d.next ? '+' : ''} reader report${d.reports.length === 1 && !d.next ? '' : 's'}`; }
      const jump = document.querySelector('.jump');
      if (jump && !jump.querySelector('a[href="#reader"]')) {
        const j = document.createElement('a');
        j.href = '#reader';
        j.textContent = 'Reader reports';
        jump.insertBefore(j, jump.children[1] || null);
      }
    })
    .catch(() => {});
})();

// Interactive pass (2026-10-26). Everything below only enhances HTML that's already on the page.
const eaTrack = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: 'creature', ...p }); } catch (e) { /* no analytics */ } };

// Painted card: tap the card or the button to flip it to quick stats.
(() => {
  const card = document.querySelector('[data-ccard]');
  if (!card) return;
  const btn = card.querySelector('.ccard-flip');
  const front = card.querySelector('.ccard-front');
  const back = card.querySelector('.ccard-back');
  card.classList.add('flip-on');
  btn.hidden = false;
  back.inert = true;
  let flips = 0;
  const flip = (to) => {
    const on = typeof to === 'boolean' ? to : !card.classList.contains('flipped');
    card.classList.toggle('flipped', on);
    btn.setAttribute('aria-pressed', String(on));
    back.inert = !on;
    if (on && ++flips === 1) eaTrack('card_flip', { creature: location.pathname.split('/')[2] || '' });
  };
  btn.addEventListener('click', () => flip());
  front.addEventListener('click', () => flip(true));
  back.addEventListener('click', (e) => { if (!e.target.closest('a')) flip(false); });
})();

// "How big is it?": redraw the wall with the reader's own height (same layout as tools.py render_wall).
(() => {
  const sec = document.querySelector('[data-sz]');
  if (!sec) return;
  const D = JSON.parse(sec.dataset.sz);
  const box = sec.querySelector('.sz-svg');
  const defs = (box.querySelector('defs') || { outerHTML: '' }).outerHTML;
  const meTxt = sec.querySelector('[data-sz-me]');
  const meWho = sec.querySelector('[data-sz-who]');
  const you = sec.querySelector('.sz-you');
  const inputs = Object.fromEntries([...sec.querySelectorAll('[data-f]')].map((i) => [i.dataset.f, i]));
  const unitBtns = [...sec.querySelectorAll('.sz-units button')];
  const panes = [...sec.querySelectorAll('.sz-in')];
  const VW = 420, L = 46, R = 46, T = 30, B = 12;
  const g = (v) => String(+v.toFixed(1));
  let unit = 'ft';

  const fmt = (ft) => {
    const cm = Math.round(ft * 30.48);
    if (unit === 'cm') return `${cm} cm`;
    let f = Math.floor(ft), i = Math.round((ft - f) * 12);
    if (i === 12) { f += 1; i = 0; }
    return `${f} ft${i ? ` ${i} in` : ''} (${(cm / 100).toFixed(2)} m)`;
  };

  function draw(meFt) {
    const human = { ...D.items.human, d: meFt, lo: meFt, hi: meFt };
    const keys = ['human', D.s];
    const items = { human, [D.s]: D.items[D.s] };
    const n = keys.length, colW = (VW - L - R) / n;
    const fig = keys.map((k) => { const it = items[k]; const [, , bw, bh] = it.b; const s = it.d / (it.f === 'h' ? bh : bw); return { k, it, s, w: bw * s, h: bh * s }; });
    const maxH = Math.max(...fig.map((f) => f.h));
    const top = maxH * 1.15;
    const px = Math.min((320 - T - B) / top, ...fig.map((f) => (colW * 0.86) / f.w));
    const VH = Math.max(220, Math.round(T + B + top * px));
    const topFt = (VH - T - B) / px;
    const step = [1, 2, 5, 10, 20, 50, 100, 200].find((s) => topFt / s <= 9 && s * px >= 18) || 500;
    const mstep = [0.5, 1, 2, 5, 10, 20, 50].find((s) => topFt / 3.28084 / s <= 7 && s * 3.28084 * px >= 18) || 100;
    const gy = VH - B;
    const o = [`<svg class="wall" viewBox="0 0 ${VW} ${VH}" role="img" aria-labelledby="sz-cap" preserveAspectRatio="xMidYMax meet">${defs}`,
      `<rect class="wall-bg" x="${L}" y="${T - 10}" width="${VW - L - R}" height="${gy - T + 10}"/>`];
    for (let i = 0; i * step <= topFt; i++) {
      const y = gy - i * step * px;
      if (i % 2) o.push(`<rect class="wall-band" x="${L}" y="${g(Math.max(T - 10, y - step * px))}" width="${VW - L - R}" height="${g(Math.min(step * px, y - T + 10))}"/>`);
      o.push(`<line class="ft-line" x1="${L}" x2="${VW - R}" y1="${g(y)}" y2="${g(y)}"/><text class="ft-lbl" x="${L - 6}" y="${g(y + 4)}" text-anchor="end">${i * step} ft</text>`);
    }
    for (let j = 1; j * mstep * 3.28084 <= topFt; j++) {
      const y = gy - j * mstep * 3.28084 * px;
      o.push(`<line class="m-line" x1="${VW - R - 14}" x2="${VW - R}" y1="${g(y)}" y2="${g(y)}"/><text class="m-lbl" x="${VW - R + 6}" y="${g(y + 4)}">${j * mstep} m</text>`);
    }
    fig.forEach((f, idx) => {
      const { it } = f; const [bx, by, bw, bh] = it.b; const kk = f.s * px;
      const cx = L + colW * (idx + 0.5);
      const tint = f.k === 'human' ? 'me' : 'c';
      o.push(`<g class="fig cat-${it.cat}" transform="translate(${g(cx - (bx + bw / 2) * kk)} ${g(gy - (by + bh) * kk)}) scale(${kk.toFixed(4)})">`
        + `<image href="${it.src}" width="${it.vb[0]}" height="${it.vb[1]}" filter="url(#sz-t-${tint})"/></g>`);
      const w = f.w * px, h = f.h * px;
      const range = it.lo !== it.hi ? `${it.lo} to ${it.hi} ft` : `${it.lo} ft`;
      if (it.f === 'h') {
        const m = it.dim === 'shoulder' ? 1.2 : 1;
        const lx = cx + w / 2 + 8, ylo = gy - it.lo * m * px, yhi = gy - it.hi * m * px;
        const lbl = f.k === 'human' ? 'You' : range;
        o.push(`<rect class="dim-range" x="${g(lx - 3)}" y="${g(yhi)}" width="6" height="${g(Math.max(2, ylo - yhi))}"/>`,
          `<line class="dim" x1="${g(lx)}" x2="${g(lx)}" y1="${gy}" y2="${g(gy - h)}"/><line class="dim" x1="${g(lx - 5)}" x2="${g(lx + 5)}" y1="${g(gy - h)}" y2="${g(gy - h)}"/>`,
          `<text class="dim-lbl" x="${g(cx)}" y="${g(gy - h - 8)}" text-anchor="middle">${lbl}</text>`);
      } else {
        const y = gy - h - 8;
        o.push(`<line class="dim" x1="${g(cx - w / 2)}" x2="${g(cx + w / 2)}" y1="${g(y)}" y2="${g(y)}"/>`,
          `<line class="dim" x1="${g(cx - w / 2)}" x2="${g(cx - w / 2)}" y1="${g(y - 5)}" y2="${g(y + 5)}"/><line class="dim" x1="${g(cx + w / 2)}" x2="${g(cx + w / 2)}" y1="${g(y - 5)}" y2="${g(y + 5)}"/>`,
          `<text class="dim-lbl" x="${g(cx)}" y="${g(y - 8)}" text-anchor="middle">${range}</text>`);
      }
    });
    o.push(`<line class="ground" x1="${L - 4}" x2="${VW - R + 4}" y1="${gy}" y2="${gy}"/></svg>`);
    box.innerHTML = o.join('');
    meWho.textContent = 'You';
    meTxt.textContent = fmt(meFt);
  }

  // Height in feet from whichever inputs are showing; null if it's not a sane adult or child height.
  const readFt = () => {
    let ft;
    if (unit === 'cm') ft = parseFloat(inputs.cm.value) / 30.48;
    else ft = (parseFloat(inputs.ft.value) || 0) + (parseFloat(inputs.in.value) || 0) / 12;
    return ft >= 3 && ft <= 8.1 ? ft : null;
  };
  const fill = (ft) => {
    const cm = Math.round(ft * 30.48);
    let f = Math.floor(ft), i = Math.round((ft - f) * 12);
    if (i === 12) { f += 1; i = 0; }
    inputs.ft.value = f; inputs.in.value = i; inputs.cm.value = cm;
  };
  const setUnit = (u) => {
    unit = u;
    unitBtns.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.u === u)));
    panes.forEach((p) => { p.hidden = p.dataset.u !== u; });
  };

  let tracked = false;
  const update = () => {
    const ft = readFt();
    if (ft == null) return;
    draw(ft);
    try { localStorage.setItem('ea_height', JSON.stringify({ ft, unit })); } catch (e) { /* private mode */ }
    if (!tracked) { tracked = true; eaTrack('size_height_set', { creature: D.s, unit }); }
  };
  Object.values(inputs).forEach((i) => i.addEventListener('input', update));
  unitBtns.forEach((b) => b.addEventListener('click', () => {
    const ft = readFt();
    setUnit(b.dataset.u);
    if (ft != null) { fill(ft); draw(ft); }
  }));

  you.hidden = false;
  try {
    const saved = JSON.parse(localStorage.getItem('ea_height') || 'null');
    if (saved && saved.ft >= 3 && saved.ft <= 8.1) {
      setUnit(saved.unit === 'cm' ? 'cm' : 'ft');
      fill(saved.ft);
      draw(saved.ft);
    }
  } catch (e) { /* no storage */ }
})();

// Famous cases by decade: light up the matching cases while a bar is hovered or focused.
(() => {
  const bars = [...document.querySelectorAll('.dec-bars a[data-dec]')];
  if (!bars.length) return;
  const items = [...document.querySelectorAll('.timeline li[id^="case-"]')];
  const decOf = (li) => { const y = parseInt((li.querySelector('.yr') || {}).textContent, 10); return Number.isNaN(y) ? null : Math.floor(y / 10) * 10; };
  const hit = (dec, on) => items.forEach((li) => li.classList.toggle('dec-hit', on && decOf(li) === dec));
  bars.forEach((a) => {
    const dec = +a.dataset.dec;
    a.addEventListener('mouseenter', () => { a.classList.add('on'); hit(dec, true); });
    a.addEventListener('mouseleave', () => { a.classList.remove('on'); hit(dec, false); });
    a.addEventListener('focus', () => hit(dec, true));
    a.addEventListener('blur', () => hit(dec, false));
    a.addEventListener('click', () => {
      const t = document.getElementById(a.getAttribute('href').slice(1));
      if (t) { t.classList.remove('dec-flash'); void t.offsetWidth; t.classList.add('dec-flash'); }
      eaTrack('decade_jump', { decade: dec });
    });
  });
})();

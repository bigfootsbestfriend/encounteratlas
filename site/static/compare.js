// Size comparison: picks up to 3 creatures, redraws the measuring wall (same layout as tools.py
// render_wall), keeps ?c=slug,slug in the URL, and sorts the static size table.
(() => {
  const D = JSON.parse(document.getElementById('cmp-data').textContent);
  // Silhouettes load on demand from their SVG files (same clean-up as tools.py does for the first drawing).
  const ICONS = {};
  const loadIcon = (i) => ICONS[i] ? Promise.resolve() : fetch(D.base + '/static/' + (i.startsWith('art/') ? '' : 'icons/') + i + '.svg')
    .then((r) => r.text()).then((t) => { ICONS[i] = t.replace(/^\s*<svg[^>]*>|<\/svg>\s*$/g, '').replace(/fill="#[0-9A-Fa-f]{3,6}"/g, 'fill="currentColor"'); });
  let gen = 0;
  async function render() {
    const my = ++gen;
    await Promise.all(['human', ...picks].map((k) => loadIcon(D.items[k].i))).catch(() => {});
    if (my === gen) draw();
  }
  const box = document.querySelector('.cmp-svg');
  const legend = document.getElementById('cmp-legend');
  const cap = document.getElementById('cmp-cap');
  const chips = [...document.querySelectorAll('.pchip')];
  const L = 46, R = 46, T = 30, B = 12;
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const g = (v) => String(+v.toFixed(1));
  document.querySelectorAll('.js-only').forEach((el) => { el.hidden = false; });

  let picks = (new URLSearchParams(location.search).get('c') || '').split(',').filter((s) => D.items[s] && s !== 'human').slice(0, 3);
  if (!new URLSearchParams(location.search).has('c')) picks = D.def.slice();

  function draw() {
    const keys = ['human', ...picks];
    const VW = Math.max(300, Math.round(box.clientWidth || 1000));
    let VH = Math.round(Math.min(560, Math.max(340, VW * 0.62)));
    const n = keys.length, colW = (VW - L - R) / n;
    const fig = keys.map((k) => { const it = D.items[k]; const [, , bw, bh] = it.b; const s = it.d / (it.f === 'h' ? bh : bw); return { k, it, s, w: bw * s, h: bh * s }; });
    const maxH = Math.max(...fig.map((f) => f.h));
    const px = Math.min((VH - T - B) / (maxH * 1.15), ...fig.map((f) => (colW * 0.86) / f.w));
    VH = Math.max(220, Math.round(T + B + maxH * 1.15 * px));
    const topFt = (VH - T - B) / px;
    const step = [1, 2, 5, 10, 20, 50, 100, 200].find((s) => topFt / s <= 9 && s * px >= 18) || 500;
    const mstep = [0.5, 1, 2, 5, 10, 20, 50].find((s) => topFt / 3.28084 / s <= 7 && s * 3.28084 * px >= 18) || 100;
    const gy = VH - B;
    const o = [`<svg class="wall" viewBox="0 0 ${VW} ${VH}" role="img" aria-labelledby="cmp-cap">`,
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
      o.push(`<g class="fig cat-${it.cat}" transform="translate(${g(cx - (bx + bw / 2) * kk)} ${g(gy - (by + bh) * kk)}) scale(${kk.toFixed(4)})" fill="currentColor" stroke-linecap="round" stroke-linejoin="round">${ICONS[it.i] || ''}</g>`);
      const w = f.w * px, h = f.h * px;
      const range = it.lo !== it.hi ? `${it.lo}–${it.hi} ft` : `${it.lo} ft`;
      if (it.f === 'h') {
        const m = it.dim === 'shoulder' ? 1.2 : 1;
        const lx = cx + w / 2 + 8, ylo = gy - it.lo * m * px, yhi = gy - it.hi * m * px;
        o.push(`<rect class="dim-range" x="${g(lx - 3)}" y="${g(yhi)}" width="6" height="${g(Math.max(2, ylo - yhi))}"/>`,
          `<line class="dim" x1="${g(lx)}" x2="${g(lx)}" y1="${gy}" y2="${g(gy - h)}"/><line class="dim" x1="${g(lx - 5)}" x2="${g(lx + 5)}" y1="${g(gy - h)}" y2="${g(gy - h)}"/>`,
          `<text class="dim-lbl" x="${g(cx)}" y="${g(gy - h - 8)}" text-anchor="middle">${f.k === 'human' ? `${it.d} ft` : range}</text>`);
      } else {
        const y = gy - h - 8;
        o.push(`<line class="dim" x1="${g(cx - w / 2)}" x2="${g(cx + w / 2)}" y1="${g(y)}" y2="${g(y)}"/>`,
          `<line class="dim" x1="${g(cx - w / 2)}" x2="${g(cx - w / 2)}" y1="${g(y - 5)}" y2="${g(y + 5)}"/><line class="dim" x1="${g(cx + w / 2)}" x2="${g(cx + w / 2)}" y1="${g(y - 5)}" y2="${g(y + 5)}"/>`,
          `<text class="dim-lbl" x="${g(cx)}" y="${g(y - 8)}" text-anchor="middle">${range}</text>`);
      }
    });
    o.push(`<line class="ground" x1="${L - 4}" x2="${VW - R + 4}" y1="${gy}" y2="${gy}"/></svg>`);
    box.innerHTML = o.join('');
    legend.style.padding = `0 ${R}px 0 ${L}px`;
    legend.style.gridTemplateColumns = `repeat(${n}, 1fr)`;
    legend.innerHTML = keys.map((k) => {
      const it = D.items[k];
      const name = k === 'human' ? 'Average person' : `<a href="${D.base}/creatures/${k}/">${esc(it.n)}</a>`;
      return `<div class="lg cat-${it.cat}"><span class="lg-n">${name}</span><span class="lg-s">${esc(it.t)}</span></div>`;
    }).join('');
    cap.textContent = `Comparing a 6 ft person with ${picks.length ? picks.map((k) => `${D.items[k].n} (${D.items[k].t})`).join(', ') : 'nothing yet. Pick a creature below'}.`;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(picks.includes(c.dataset.s))));
    document.getElementById('cmp-clear').disabled = !picks.length;
  }

  function sync() {
    const u = new URL(location.href);
    u.searchParams.set('c', picks.join(','));
    history.replaceState(null, '', u.pathname + '?c=' + picks.join(',') + u.hash);
    render();
  }

  document.querySelector('.pchips').addEventListener('click', (e) => {
    const c = e.target.closest('.pchip');
    if (!c) return;
    const s = c.dataset.s;
    if (picks.includes(s)) picks = picks.filter((x) => x !== s);
    else { picks.push(s); if (picks.length > 3) picks.shift(); }
    sync();
  });
  document.getElementById('cmp-clear').addEventListener('click', () => { picks = []; sync(); });
  document.getElementById('cmp-share').addEventListener('click', async (e) => {
    const b = e.currentTarget, url = location.href;
    try {
      if (navigator.share) { await navigator.share({ title: 'Cryptid size comparison', url }); return; }
      await navigator.clipboard.writeText(url); b.textContent = 'Link copied';
    } catch (err) { if (!err || err.name !== 'AbortError') b.textContent = 'Copy the address bar link'; }
    setTimeout(() => { b.textContent = 'Share this comparison'; }, 2500);
  });
  const q = document.getElementById('cmp-q');
  q.addEventListener('input', () => {
    const v = q.value.trim().toLowerCase();
    chips.forEach((c) => { c.hidden = v && !c.dataset.names.includes(v); });
  });
  let rt;
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(render, 150); });
  render();

  // sortable table
  const tbl = document.getElementById('size-tbl');
  tbl.querySelector('thead').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    const th = b.parentElement, k = +b.dataset.k, num = !!b.dataset.num;
    const dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
    tbl.querySelectorAll('thead th').forEach((x) => { if (x.hasAttribute('aria-sort')) x.setAttribute('aria-sort', 'none'); });
    th.setAttribute('aria-sort', dir);
    const body = tbl.tBodies[0];
    const rows = [...body.rows];
    const val = (r) => { const v = r.cells[k].dataset.v; return num ? +v : v; };
    rows.sort((a, b2) => { const x = val(a), y = val(b2); const c = num ? x - y : String(x).localeCompare(String(y)); return dir === 'ascending' ? c : -c; });
    body.append(...rows);
  });
})();

// Mystery of the day (/mystery-of-the-day/, site/sections/motd.py).
// The HTML already shows the build day's case. At load this script:
//  1. says when the next case goes up in the visitor's own time,
//  2. if the visitor's UTC day isn't the build day (the site rebuilds about daily), fetches /data/motd.json and
//     swaps in the right today / yesterday / last-14-days (same pick rule as motd.py and the Worker's motd.js),
//  3. loads the vote counts once (vote.js, window.EA): the vote widget for today's case, yesterday's results and
//     a small result chip per archive day. If the Worker doesn't know the case yet, it says voting opens soon.
(function () {
  const root = document.getElementById('motd');
  if (!root) return;
  const DAY = Math.floor(Date.now() / 86400000);
  const BUILT = Number(root.dataset.day);
  const BASE = root.dataset.base || '';
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const KINDS = { my: 'Mystery', ce: 'Close encounter', uf: 'UFO case' };
  const STATUS = { unexplained: 'Unexplained', disputed: 'Disputed', solved: 'Mostly solved', legend: 'Legend', explained: 'Explained', hoax: 'Hoax' };
  const LABELS = { real: 'Real', hoax: 'Hoax', mis: 'Misidentified' };
  const SKY = { hominid: ['#E3A649', '#B5532F'], canid: ['#3B4C6B', '#1B2A3A'], winged: ['#3B4C6B', '#1B2A3A'], aquatic: ['#E8B04A', '#C8693A'],
    entity: ['#3B4C6B', '#1B2A3A'], ufo: ['#2E3E5C', '#141E2E'], fae: ['#C97B9A', '#4A2E4F'], other: ['#E3A649', '#B5532F'] };

  // When the next case goes up, in the visitor's clock.
  const sw = document.getElementById('motd-switch');
  if (sw) {
    const at = new Date((DAY + 1) * 86400000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    sw.textContent = `A new case goes up at midnight UTC every day. That's ${at} where you are.`;
  }

  function pick(eras, day) {
    let era = null;
    for (const e of eras) if (e.from <= day) era = e;
    if (!era || !era.order.length) return null;
    return era.order[(day - era.from) % era.order.length];
  }

  function el(tag, cls, text) {
    const x = document.createElement(tag);
    if (cls) x.className = cls;
    if (text != null) x.textContent = text;
    return x;
  }

  function art(a, cls, idp) {
    const span = el('span', cls);
    if (a && a.img && /^\/static\/[\w./-]+$/.test(a.img)) {
      span.classList.add('motd-photo');
      const img = el('img');
      img.src = BASE + a.img; img.alt = ''; img.width = 320; img.height = 320;
      span.append(img);
      return span;
    }
    span.setAttribute('aria-hidden', 'true');
    if (a && a.svg) {  // built by motd.py scene(), from our own /data/motd.json
      span.innerHTML = a.svg.split('{ID}').join('motd-' + idp).split('{BASE}').join(BASE);
      return span;
    }
    if (a && a.art && /^art\/[a-z0-9-]+$/.test(a.art)) {
      const [c1, c2] = SKY[a.cat] || SKY.other;
      const wet = a.cat === 'aquatic', id = 'motd-' + idp;
      const ground = wet ? '<rect y="160" width="200" height="40" fill="#2B4A55"/>'
        : '<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="#1E3A2F"/>';
      span.innerHTML = `<svg viewBox="0 0 200 200"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient>` +
        `<clipPath id="c${id}"><rect x="6" y="6" width="188" height="188" rx="10"/></clipPath></defs><g clip-path="url(#c${id})"><rect width="200" height="200" fill="url(#${id})"/>` +
        `<circle cx="150" cy="52" r="24" fill="#F3E3B8" opacity=".9"/><path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="#5E4A3A" opacity=".5"/>${ground}` +
        `<image href="${BASE}/static/${a.art}.svg" x="22" y="${wet ? 34 : 26}" width="160" height="160"/></g><rect x="6" y="6" width="188" height="188" rx="10" fill="none" stroke="#F3E3B8" stroke-width="4"/></svg>`;
      return span;
    }
    span.classList.add('motd-blank');
    span.textContent = '?';
    return span;
  }

  const kindPill = (c) => el('span', `motd-kind k-${c.k}`, KINDS[c.k] || '');
  const statusPill = (c) => el('span', `motd-st st-${c.st}`, STATUS[c.st] || c.st);

  // Fill one card (today or yesterday) with case c.
  function fill(box, slug, c, idp) {
    if (!box) return;
    box.dataset.slug = slug;
    const old = box.querySelector('.motd-art');
    if (old) old.replaceWith(art(c.a, old.className.replace(/\s*motd-(photo|blank)/g, ''), idp));
    box.querySelectorAll('[data-f]').forEach((x) => {
      const f = x.dataset.f;
      if (f === 'u') x.href = BASE + c.u;
      else if (c[f] != null) x.textContent = c[f];
    });
    const k = box.querySelector('.motd-kind');
    if (k) k.replaceWith(kindPill(c));
    const s = box.querySelector('.motd-st');
    if (s) s.replaceWith(statusPill(c));
  }

  function swap(data) {
    const cases = data.cases || {}, eras = data.eras || [];
    const ts = pick(eras, DAY), t = cases[ts];
    if (!t) return false;
    const today = document.getElementById('motd-today');
    fill(today, ts, t, 't');
    const vote = today && today.querySelector('[data-motd-vote]');
    if (vote) vote.dataset.motdVote = 'm:' + ts;
    const ys = pick(eras, DAY - 1), y = cases[ys];
    const yest = document.getElementById('motd-yest');
    if (yest && y) {
      fill(yest, ys, y, 'y');
      const r = yest.querySelector('[data-motd-results]');
      if (r) r.dataset.motdResults = 'm:' + ys;
    } else if (yest) yest.hidden = true;
    const list = document.getElementById('motd-list');
    if (list) {
      const rows = [];
      for (let i = 1; i <= 14; i++) {
        const s = pick(eras, DAY - i), c = cases[s];
        if (!c) continue;
        const d = new Date((DAY - i) * 86400000);
        const li = el('li');
        li.dataset.slug = s;
        const a = el('a', null, c.n);
        a.href = BASE + c.u;
        const meta = el('span', 'motd-arc-meta');
        const chip = el('span', 'motd-arc-vote');
        chip.dataset.motdArc = 'm:' + s;
        meta.append(kindPill(c), statusPill(c), chip);
        li.append(el('span', 'motd-day', `${MON[d.getUTCMonth()]} ${d.getUTCDate()}`), a, meta);
        rows.push(li);
      }
      list.replaceChildren(...rows);
    }
    const date = document.getElementById('motd-date');
    if (date) date.textContent = new Date(DAY * 86400000).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' }) + ' (UTC)';
    return true;
  }

  function topChoice(t) {
    const [k, v] = Object.entries(t.results).filter(([x]) => LABELS[x]).sort((a, b) => b[1] - a[1])[0];
    return `${Math.round(v)}% ${LABELS[k].toLowerCase()}`;
  }

  async function votes() {
    const EA = window.EA;
    const vbox = root.querySelector('[data-motd-vote]');
    const rbox = root.querySelector('[data-motd-results]');
    if (!EA || !vbox) return;
    const todayItem = vbox.dataset.motdVote;
    const arc = [...root.querySelectorAll('[data-motd-arc]')];
    const items = [...new Set([todayItem, rbox && rbox.dataset.motdResults, ...arc.map((x) => x.dataset.motdArc)].filter(Boolean))].slice(0, 20);
    const got = await EA.loadTallies(items);
    const find = (it) => (got || []).find((x) => x.item === it);
    const note = (text) => el('p', 'motd-wait', text);
    const head = () => { const p = el('p', 'vote-h'); p.append(el('strong', null, 'What do you think it was?')); return p; };

    if (got === null) vbox.replaceChildren(head(), note("Couldn't reach the voting server just now. Reload in a bit and try again."));
    else if (!find(todayItem)) vbox.replaceChildren(head(), note('Voting on this case opens soon. Check back later today.'));
    else vbox.replaceChildren(EA.voteWidget(todayItem, { label: 'What do you think it was?' }));

    if (rbox) {
      const t = find(rbox.dataset.motdResults);
      if (got === null) rbox.replaceChildren(note("Couldn't load the votes right now."));
      else if (t && t.results) rbox.replaceChildren(EA.results(t));
      else rbox.replaceChildren(note(`Not enough votes yet${t ? ` (${t.n} of the ${t.threshold} we need before showing results)` : ''}.`));
    }
    for (const chip of arc) {
      const t = find(chip.dataset.motdArc);
      chip.textContent = t && t.results ? topChoice(t) : t && t.n ? `${t.n} ${t.n === 1 ? 'vote' : 'votes'}` : '';
    }
  }

  async function init() {
    if (DAY !== BUILT && root.dataset.json) {
      try {
        const data = await fetch(root.dataset.json).then((r) => (r.ok ? r.json() : null));
        if (data) swap(data);
      } catch (e) { /* offline: keep the built case */ }
    }
    await votes();
  }
  init();
})();

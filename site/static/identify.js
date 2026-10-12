// "What did I see?" stepper. The page already holds every question, answer and mix-up as HTML;
// this script only shows one question at a time, scores answers against the table built into
// #idq-data, and writes the answers into the URL hash (#a=woods.taller...) so results can be shared.
(() => {
  const root = document.getElementById('idq');
  const D = JSON.parse(document.getElementById('idq-data').textContent);
  const steps = [...root.querySelectorAll('.idq-step')];
  const bar = root.querySelector('.idq-bar');
  const prog = root.querySelector('.idq-prog');
  const out = document.getElementById('idq-result');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const answers = new Array(D.q.length).fill(null);
  let cur = 0;

  root.classList.add('js');
  root.querySelectorAll('.js-only').forEach((el) => { el.hidden = false; });
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function show(i, focus = true) {
    cur = i;
    out.replaceChildren();
    root.classList.remove('done');
    steps.forEach((s, k) => {
      s.hidden = k !== i;
      s.classList.toggle('enter', k === i && !reduce);
      s.querySelectorAll('.ans').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.a === answers[k])));
    });
    bar.querySelector('.idq-back').disabled = i === 0;
    prog.setAttribute('aria-valuenow', i);
    prog.firstElementChild.style.width = `${(i / D.q.length) * 100}%`;
    if (focus) steps[i].querySelector('.idq-h').focus({ preventScroll: true });
    if (focus) root.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
  }

  function next() {
    if (cur < D.q.length - 1) show(cur + 1);
    else finish(true);
  }

  root.addEventListener('click', (e) => {
    const a = e.target.closest('.ans');
    if (a) { answers[cur] = a.dataset.a; a.setAttribute('aria-pressed', 'true'); setTimeout(next, reduce ? 0 : 120); return; }
    if (e.target.closest('.idq-skip')) { answers[cur] = null; next(); return; }
    if (e.target.closest('.idq-back')) { if (root.classList.contains('done')) show(D.q.length - 1); else if (cur > 0) show(cur - 1); }
  });

  function score() {
    const tot = {};
    answers.forEach((a) => { if (!a) return; for (const [s, v] of Object.entries(D.M[a] || {})) tot[s] = (tot[s] || 0) + v; });
    const crit = Object.keys(tot).sort((x, y) => tot[y] - tot[x] || D.c[x][0].localeCompare(D.c[y][0])).slice(0, 3);
    const ev = {};
    answers.forEach((a, i) => { if (!a) return; for (const [id, fits] of Object.entries(D.e)) if (fits.includes(a)) ev[id] = (ev[id] || 0) + D.q[i].w; });
    const every = Object.keys(ev).sort((x, y) => ev[y] - ev[x]).slice(0, 3);
    return { crit, every, best: crit.length ? tot[crit[0]] : 0 };
  }

  function card(slug, lead) {
    const [name, aka, sum, cat, icon] = D.c[slug];
    return `<a class="crit res-crit${lead ? ' lead' : ''}" href="${D.base}/creatures/${slug}/">
      <span class="badge badge-md cat-${cat}"><span class="mask-ico" style="--m:url(${D.base}/static/${icon}.svg)"></span></span>
      <span class="crit-txt">${lead ? '<span class="res-tag">Closest match</span>' : ''}<span class="crit-name">${esc(name)}</span>
      ${aka ? `<span class="aka">aka ${esc(aka)}</span>` : ''}<span class="crit-sum">${esc(sum)}</span></span></a>`;
  }

  function finish(focus) {
    const { crit, every } = score();
    const picked = answers.map((a, i) => a && D.q[i].a.find((x) => x[0] === a)[1]).filter(Boolean);
    root.classList.add('done');
    steps.forEach((s) => { s.hidden = true; });
    prog.setAttribute('aria-valuenow', D.q.length);
    prog.firstElementChild.style.width = '100%';
    history.replaceState(null, '', `#a=${answers.map((a) => a || 'x').join('.')}`);
    const top = crit[0];
    const ufo = top && D.c[top][3] === 'ufo';
    const animal = top && ['hominid', 'canid', 'winged', 'aquatic', 'other'].includes(D.c[top][3]);
    const mix = every.map((id) => {
      const el = document.getElementById(`mix-${id}`);
      return el ? `<article class="mix">${el.innerHTML}</article>` : '';
    }).join('');
    const where = [
      '<li>Anyone in danger, or a crime: call 911 (or your local emergency number) first.</li>',
      animal ? '<li>A large or injured animal near homes or roads: your state or provincial wildlife agency.</li>' : '',
      ufo ? '<li>Something near military sites or aircraft: the US Department of Defense <a href="https://www.aaro.mil/" rel="noopener">All-domain Anomaly Resolution Office (AARO)</a>.</li>' : '',
      ufo || answers.includes('lights') ? '<li>A fast, bright streak or fireball: the <a href="https://www.amsmeteors.org/" rel="noopener">American Meteor Society</a> collects fireball reports.</li>' : '',
    ].join('');
    out.innerHTML = crit.length ? `
      <h2 class="res-h" tabindex="-1">Reports that sound like yours</h2>
      <p class="res-you">You said: ${picked.map((p) => `<span class="you-chip">${esc(p)}</span>`).join(' ')}</p>
      <div class="res-crits">${crit.map((s, i) => card(s, i === 0)).join('')}</div>
      ${mix ? `<h3 class="res-sub">Rule these out first</h3><p class="res-note">Most sightings with answers like yours turn out to be one of these.</p><div class="mix-grid res-mix">${mix}</div>` : ''}
      <div class="res-actions">
        <a class="btn btn-big" href="${D.base}/report/?creature=${encodeURIComponent(top)}">Report what you saw</a>
        <button type="button" class="btn btn-ghost-d" data-act="share">Share my result</button>
        <button type="button" class="btn btn-ghost-d" data-act="again">Start again</button>
        <span class="share-msg" role="status"></span>
      </div>
      <div class="res-else"><h3 class="res-sub">Where else to report</h3><ul>${where}<li>Here: <a href="${D.base}/report/">add it to the Encounter Atlas map</a>.</li></ul></div>`
      : `<h2 class="res-h" tabindex="-1">Not enough to go on</h2><p>You skipped every question. <button type="button" class="btn" data-act="again">Start again</button></p>`;
    if (focus) out.querySelector('.res-h').focus();
  }

  out.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-act]');
    if (!b) return;
    if (b.dataset.act === 'again') {
      answers.fill(null);
      history.replaceState(null, '', location.pathname + location.search);
      show(0);
      return;
    }
    const url = location.href;
    const msg = out.querySelector('.share-msg');
    try {
      if (navigator.share) { await navigator.share({ title: 'What did I see?', text: 'My sighting, matched on Encounter Atlas', url }); return; }
      await navigator.clipboard.writeText(url);
      msg.textContent = 'Link copied';
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      msg.textContent = 'Copy this link from the address bar';
    }
  });

  bar.hidden = false;
  const m = /^#a=([a-z0-9_.-]+)$/.exec(location.hash);
  if (m) {
    const parts = m[1].split('.');
    D.q.forEach((q, i) => { const a = parts[i]; answers[i] = q.a.some((x) => x[0] === a) ? a : null; });
    finish(false);
  } else show(0, false);
})();

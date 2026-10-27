// Mysteries: type chips filter the cards (every card is in the HTML), and a map of pins coloured by type.
// On a mystery page the map has data-focus and centres on that place.
(function () {
  const cards = [...document.querySelectorAll('.my-card')];
  const chips = [...document.querySelectorAll('.ce-chip')];
  const status = document.querySelector('.ce-status');
  let filter = '';
  let setMap = () => {};
  chips.forEach((chip) => chip.addEventListener('click', () => {
    filter = chip.dataset.f;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
    let shown = 0;
    cards.forEach((c) => { const ok = !filter || c.dataset.t === filter; c.hidden = !ok; if (ok) shown++; });
    document.querySelectorAll('.my-group').forEach((g) => { g.hidden = !g.querySelector('.my-card:not([hidden])'); });
    if (status) status.textContent = filter ? `Showing ${shown} ${shown === 1 ? 'mystery' : 'mysteries'}.` : '';
    setMap();
  }));

  const el = document.getElementById('my-map');
  if (!el) return;
  function init() {
    if (!window.maplibregl) return setTimeout(init, 150);
    const focus = el.dataset.focus;
    const map = new maplibregl.Map({ container: el, style: 'https://tiles.openfreemap.org/styles/dark', center: [-30, 40], zoom: 1.2,
      attributionControl: { compact: true }, cooperativeGestures: !!focus });
    // The basemap's town dots ask for a sprite icon (circle-11) the style doesn't ship: give it a blank one, no console noise.
    map.on('styleimagemissing', (e) => { if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.on('load', async () => {
      const data = await fetch(el.dataset.geojson).then((r) => r.json()).catch(() => null);
      if (!data) return;
      map.addSource('my', { type: 'geojson', data });
      map.addLayer({ id: 'my-glow', type: 'circle', source: 'my', paint: { 'circle-color': ['get', 'c'], 'circle-opacity': 0.25, 'circle-blur': 0.6,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 10, 9, 20] } });
      map.addLayer({ id: 'my-pins', type: 'circle', source: 'my', paint: { 'circle-color': ['get', 'c'],
        'circle-radius': ['case', ['==', ['get', 's'], focus || ''], 9, 6], 'circle-stroke-color': '#13261F', 'circle-stroke-width': 1.5 } });
      const f = focus && data.features.find((x) => x.properties.s === focus);
      if (f) map.jumpTo({ center: f.geometry.coordinates, zoom: 4 });
      else if (data.features.length) {
        const b = new maplibregl.LngLatBounds();
        data.features.forEach((x) => b.extend(x.geometry.coordinates));
        map.fitBounds(b, { padding: 40, maxZoom: 5, duration: 0 });
      }
      setMap = () => {
        const flt = filter ? ['==', ['get', 't'], filter] : null;
        map.setFilter('my-pins', flt); map.setFilter('my-glow', flt);
      };
      map.on('mouseenter', 'my-pins', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'my-pins', () => { map.getCanvas().style.cursor = ''; });
      map.on('click', 'my-pins', (ev) => {
        const p = ev.features[0].properties;
        const div = document.createElement('div'); div.className = 'pop';
        const a = document.createElement('a'); a.href = p.u; a.textContent = p.n;
        const s = document.createElement('p'); s.textContent = `${p.d} · ${p.p} · ${p.st}`;
        div.append(a, s);
        new maplibregl.Popup({ maxWidth: '280px', offset: 10 }).setLngLat(ev.features[0].geometry.coordinates).setDOMContent(div).addTo(map);
      });
    });
  }
  init();
})();

// Mystery pages: "Your verdict" on each rated theory (saved in this browser only) and a tap-through timeline.
// The full theory list and timeline stay in the HTML; this only adds buttons, a stepper and a highlight.
(function () {
  const slug = (document.getElementById('my-map') || {}).dataset?.focus;
  if (!slug) return;
  const ga = (name, p) => { if (window.gtag) try { window.gtag('event', name, { page_type: 'mysteries', mystery: slug, ...p }); } catch (x) { /* no analytics */ } };
  const mk = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text != null) el.textContent = text; return el; };

  // ---- Your verdict ----
  const ths = [...document.querySelectorAll('.my-th[data-v]')];
  if (ths.length) {
    const KEY = 'ea-my-verdict-' + slug;
    const PICKS = [['likely', 'Most likely'], ['possible', 'Possible'], ['no', 'No way']];
    const RANK = { likely: 0, possible: 1, no: 2 };
    const OURS = { leading: 'likely', possible: 'possible', unlikely: 'no', 'no-evidence': 'no', disproved: 'no' };
    const OURLABEL = { leading: 'best fit', possible: 'possible', unlikely: 'unlikely', 'no-evidence': 'no evidence', disproved: 'ruled out' };
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (x) { saved = {}; }
    const save = () => { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (x) { /* private mode */ } };

    function line(mine, v) {
      const ours = OURS[v], lab = OURLABEL[v];
      if (mine === ours) return { ok: true, t: ['Same call as us. Great minds.', 'We agree. Nice one.', 'Spot on, that matches our rating.'][Math.abs(slug.length + RANK[mine]) % 3] };
      const gap = Math.abs(RANK[mine] - RANK[ours]);
      if (mine === 'likely' && gap === 2) return { ok: false, t: `Bold pick. We rate it ${lab}, but you're allowed to be stubborn.` };
      if (mine === 'no' && gap === 2) return { ok: false, t: `Tough crowd. We actually rate this one ${lab}.` };
      return { ok: false, t: `Close. We'd call it ${lab}.` };
    }

    const list = ths[0].parentElement;
    const intro = mk('p', 'my-vd-intro', 'Your verdict: tap your call on each theory, then see how you line up with us. Saved on this device only.');
    list.before(intro);
    const card = mk('div', 'my-vd-card');
    card.setAttribute('aria-live', 'polite');
    card.hidden = true;
    const big = mk('p', 'my-vd-big');
    const sub = mk('p', 'my-vd-sub');
    const row = mk('div', 'my-vd-acts');
    const share = mk('button', 'btn my-vd-share', 'Share my verdict');
    share.type = 'button';
    const reset = mk('button', 'btn btn-ghost my-vd-reset', 'Start over');
    reset.type = 'button';
    row.append(share, reset);
    card.append(big, sub, row);
    list.after(card);

    function summary() {
      const picked = ths.filter((li) => saved[ths.indexOf(li)]);
      if (!picked.length) { card.hidden = true; return null; }
      const agree = picked.filter((li) => saved[ths.indexOf(li)] === OURS[li.dataset.v]).length;
      card.hidden = false;
      big.textContent = `You and Encounter Atlas agree on ${agree} of ${picked.length}`;
      const left = ths.length - picked.length;
      sub.textContent = left ? `${left} more ${left === 1 ? 'theory' : 'theories'} to rate.`
        : agree === ths.length ? 'A perfect match. You could write these up yourself.'
        : agree === 0 ? 'Not one match. Somebody has to keep us honest.'
        : 'All rated. Some agreement, some healthy doubt.';
      return { agree, n: picked.length };
    }

    ths.forEach((li, i) => {
      const name = (li.querySelector('b') || {}).textContent || '';
      const box = mk('div', 'my-vd');
      const btns = mk('div', 'my-vd-btns');
      btns.setAttribute('role', 'group');
      btns.setAttribute('aria-label', 'Your verdict on: ' + name);
      const res = mk('p', 'my-vd-res');
      res.setAttribute('aria-live', 'polite');
      const paint = () => {
        const mine = saved[i];
        btns.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.p === mine)));
        if (!mine) { res.hidden = true; li.classList.remove('vd-agree', 'vd-differ'); return; }
        const l = line(mine, li.dataset.v);
        res.hidden = false;
        res.textContent = l.t;
        li.classList.toggle('vd-agree', l.ok);
        li.classList.toggle('vd-differ', !l.ok);
      };
      PICKS.forEach(([k, lab]) => {
        const b = mk('button', 'my-vd-b vd-' + k, lab);
        b.type = 'button';
        b.dataset.p = k;
        b.addEventListener('click', () => {
          saved[i] = saved[i] === k ? undefined : k;
          if (!saved[i]) delete saved[i];
          save(); paint(); summary();
          if (saved[i]) ga('mystery_verdict', { pick: k, ours: li.dataset.v, agree: k === OURS[li.dataset.v] ? 'yes' : 'no' });
        });
        btns.append(b);
      });
      box.append(btns, res);
      li.append(box);
      paint();
    });
    summary();

    share.addEventListener('click', async () => {
      const s = summary();
      if (!s) return;
      const title = (document.querySelector('h1') || {}).textContent || 'this mystery';
      const text = `I rated the theories on ${title} and agree with Encounter Atlas on ${s.agree} of ${s.n}. What's your verdict?`;
      const url = location.origin + location.pathname;
      ga('mystery_verdict_share', { agree: s.agree, rated: s.n });
      if (navigator.share) { try { await navigator.share({ title, text, url }); return; } catch (x) { if (x && x.name === 'AbortError') return; } }
      try { await navigator.clipboard.writeText(text + ' ' + url); share.textContent = 'Copied, paste it anywhere'; }
      catch (x) { share.textContent = 'Copy failed, sorry'; }
      setTimeout(() => { share.textContent = 'Share my verdict'; }, 2500);
    });
    reset.addEventListener('click', () => {
      saved = {}; save();
      ths.forEach((li) => { li.querySelectorAll('.my-vd-b').forEach((b) => b.setAttribute('aria-pressed', 'false')); li.querySelector('.my-vd-res').hidden = true; li.classList.remove('vd-agree', 'vd-differ'); });
      summary();
    });
  }

  // ---- Tap-through timeline ----
  const tl = document.querySelector('.my-tl');
  const items = tl ? [...tl.children] : [];
  if (items.length > 1) {
    let at = 0;
    const box = mk('div', 'my-step');
    const panel = mk('div', 'my-step-card');
    panel.setAttribute('aria-live', 'polite');
    const count = mk('p', 'my-step-n');
    const when = mk('p', 'my-step-when');
    const what = mk('p', 'my-step-what');
    panel.append(count, when, what);
    const ctl = mk('div', 'my-step-ctl');
    const prev = mk('button', 'my-step-b', 'Prev');
    const next = mk('button', 'my-step-b', 'Next');
    prev.type = next.type = 'button';
    prev.setAttribute('aria-label', 'Previous event');
    next.setAttribute('aria-label', 'Next event');
    const range = mk('input', 'my-step-range');
    range.type = 'range'; range.min = '1'; range.max = String(items.length); range.step = '1'; range.value = '1';
    range.setAttribute('aria-label', 'Move through the timeline');
    ctl.append(prev, range, next);
    box.append(panel, ctl);
    tl.before(box);
    tl.classList.add('my-tl-on');
    const show = (n, user) => {
      at = Math.max(0, Math.min(items.length - 1, n));
      items.forEach((li, i) => { li.classList.toggle('is-on', i === at); li.classList.toggle('is-past', i < at); });
      count.textContent = `Event ${at + 1} of ${items.length}`;
      when.textContent = (items[at].querySelector('b') || {}).textContent || '';
      what.textContent = (items[at].querySelector('span') || {}).textContent || '';
      range.value = String(at + 1);
      range.style.setProperty('--p', items.length > 1 ? (at / (items.length - 1)) * 100 + '%' : '0%');
      prev.disabled = at === 0;
      next.disabled = at === items.length - 1;
      if (user) ga('mystery_timeline_step', { step: at + 1 });
    };
    prev.addEventListener('click', () => show(at - 1, true));
    next.addEventListener('click', () => show(at + 1, true));
    range.addEventListener('input', () => show(Number(range.value) - 1, true));
    items.forEach((li, i) => { li.addEventListener('click', () => show(i, true)); });
    show(0);
  }
})();

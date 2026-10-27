// "Random encounter" dice: a floating button that rolls and sends you to a random creature, UFO case, witness story,
// place or mystery. /data/random.json ({kind: [[path, title], ...]}, built by build.py write_random) loads on first tap.
// Kinds are picked evenly first, so the 13 mysteries turn up as often as the 245 creatures.
// The same file runs the reading progress bar on long articles (<script data-bar>): CSS scroll-driven where the
// browser has it, a scroll listener where it doesn't, and only on pages taller than 2.5 screens.
(() => {
  const me = document.currentScript;
  if (!me) return;
  const root = document.documentElement;
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- reading bar ----------
  if (me.hasAttribute('data-bar')) {
    const bar = document.querySelector('.read-bar');
    const css = window.CSS && CSS.supports && CSS.supports('animation-timeline: scroll()');
    let on = false;
    const paint = () => {
      if (!on || css || !bar) return;
      const h = root.scrollHeight - innerHeight;
      bar.style.setProperty('--read', h > 0 ? Math.min(1, scrollY / h).toFixed(4) : 0);
    };
    const check = () => {
      on = root.scrollHeight > innerHeight * 2.5;
      root.classList.toggle('ea-long', on);
      paint();
    };
    check();
    addEventListener('load', check);
    addEventListener('resize', check, { passive: true });
    if (!css) addEventListener('scroll', () => requestAnimationFrame(paint), { passive: true });
  }

  // ---------- dice ----------
  const pool = me.dataset.pool;
  if (!pool) return;
  // pip spots on a 48 box: face n shows these
  const SPOTS = { tl: [15, 15], tr: [33, 15], ml: [15, 24], c: [24, 24], mr: [33, 24], bl: [15, 33], br: [33, 33] };
  const FACES = { 1: ['c'], 2: ['tl', 'br'], 3: ['tl', 'c', 'br'], 4: ['tl', 'tr', 'bl', 'br'], 5: ['tl', 'tr', 'c', 'bl', 'br'], 6: ['tl', 'tr', 'ml', 'mr', 'bl', 'br'] };
  const NS = 'http://www.w3.org/2000/svg';
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'ea-dice';
  b.title = 'Random encounter: a creature, UFO case, story, place or mystery';
  b.setAttribute('aria-label', 'Random encounter: take me somewhere strange');
  b.dataset.area = 'random-dice';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 48 48');
  svg.setAttribute('aria-hidden', 'true');
  const face = document.createElementNS(NS, 'rect');
  Object.entries({ x: 4, y: 4, width: 40, height: 40, rx: 9, class: 'd-face' }).forEach(([k, v]) => face.setAttribute(k, v));
  svg.append(face);
  const pips = {};
  for (const [k, [x, y]] of Object.entries(SPOTS)) {
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', 4); c.setAttribute('class', 'd-pip');
    svg.append(c); pips[k] = c;
  }
  const show = (n) => { for (const k in pips) pips[k].toggleAttribute('hidden', !FACES[n].includes(k)); };
  show(5);
  const label = document.createElement('span');
  label.className = 'ea-dice-l';
  label.textContent = 'Random encounter';
  b.append(svg, label);
  document.body.append(b);

  // Sit just above the podcast player bar (podplayer.js adds it and body.pp-on): its height changes with the screen
  // width and the resume/controls state, so measure it rather than guess.
  let watched = null;
  const ro = 'ResizeObserver' in window && new ResizeObserver(([e]) => root.style.setProperty('--ea-dock', Math.ceil(e.target.getBoundingClientRect().height) + 'px'));
  const dock = () => {
    const bar = document.querySelector('.pp-bar');
    if (bar === watched || !ro) return;
    if (watched) ro.unobserve(watched);
    watched = bar;
    if (bar) ro.observe(bar); else root.style.removeProperty('--ea-dock');
  };
  dock();
  new MutationObserver(dock).observe(document.body, { childList: true });

  let data = null, busy = false;
  const load = () => data || (data = fetch(pool).then((r) => (r.ok ? r.json() : Promise.reject(r.status))).catch((e) => { data = null; throw e; }));
  const here = location.pathname;
  const pick = (d) => {
    const kinds = Object.keys(d).filter((k) => d[k].some((x) => x[0] !== here));
    const kind = kinds[Math.floor(Math.random() * kinds.length)];
    const list = d[kind].filter((x) => x[0] !== here);
    return [kind, list[Math.floor(Math.random() * list.length)]];
  };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  b.addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    const roll = Math.ceil(Math.random() * 6);
    let tick = null;
    if (!still) {
      b.classList.remove('rolling'); void b.offsetWidth; b.classList.add('rolling');
      tick = setInterval(() => show(1 + Math.floor(Math.random() * 6)), 90);
    }
    try {
      const [d] = await Promise.all([load(), wait(still ? 0 : 700)]);
      const [kind, hit] = pick(d);
      clearInterval(tick); show(roll);
      label.textContent = hit[1].length > 34 ? hit[1].slice(0, 33) + '...' : hit[1];
      try { if (window.eaTrack) window.eaTrack('random_encounter', { kind, dest: hit[0] }); } catch (e) { /* no analytics */ }
      await wait(still ? 0 : 250);
      location.href = hit[0];
    } catch (e) {
      clearInterval(tick); show(roll);
      label.textContent = 'No signal. Try again?';
      b.title = "Couldn't load the list. Check your connection and try again.";
    }
    b.classList.remove('rolling');
    busy = false;
  });
  // Coming back with the Back button: reset the label and the busy state
  addEventListener('pageshow', (e) => { if (e.persisted) { busy = false; label.textContent = 'Random encounter'; b.classList.remove('rolling'); } });
})();

// Collector cards: the collection lives in localStorage ('ea-cards': {slug: {t: ISO date, at: spot name}}), no account.
// window.eaCards: collected(), checkIn() (asks for location once, collects every card with a spot within checkin_km).
// On /cards/ it also marks collected cards, counts them and shows hunt progress.
(function () {
  const KEY = 'ea-cards';
  let dataP = null;
  const cfgEl = document.getElementById('cc-config') || document.getElementById('rt-config');
  const dataUrl = cfgEl ? JSON.parse(cfgEl.textContent).data : '/data/roadtrip.json';
  const load = () => dataP || (dataP = fetch(dataUrl).then((r) => r.json()));
  const collected = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } };
  const save = (c) => { try { localStorage.setItem(KEY, JSON.stringify(c)); } catch (e) { /* storage full or blocked */ } };
  function hav(a1, o1, a2, o2) {
    const r = Math.PI / 180, h = Math.sin(((a2 - a1) * r) / 2) ** 2 + Math.cos(a1 * r) * Math.cos(a2 * r) * Math.sin(((o2 - o1) * r) / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
  }
  function where() {
    return new Promise((res, rej) => {
      if (!navigator.geolocation) { rej(new Error('nogeo')); return; }
      navigator.geolocation.getCurrentPosition((p) => res([p.coords.latitude, p.coords.longitude]), rej, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
    });
  }
  // Returns {got: [{slug, name, at}], near: {name, km} | null}
  async function checkIn() {
    const [lat, lon] = await where();
    const d = await load(), mine = collected(), got = [];
    let nearest = null;
    for (const [slug, c] of Object.entries(d.cards)) {
      for (const [a, o, label] of c.spots) {
        const km = hav(lat, lon, a, o);
        if (km <= d.checkin_km) {
          if (!mine[slug]) { mine[slug] = { t: new Date().toISOString(), at: label }; got.push({ slug, name: c.n, at: label }); }
          break;
        }
        if (!mine[slug] && (!nearest || km < nearest.km)) nearest = { name: c.n, at: label, km };
      }
    }
    save(mine);
    try { if (window.gtag) window.gtag('event', 'card_checkin', { page_type: location.pathname.split('/')[1] || 'home', cards: got.length }); } catch (e) { /* no analytics */ }
    return { got, nearest };
  }
  function mark(root) {
    const mine = collected();
    (root || document).querySelectorAll('[data-card]').forEach((li) => {
      const has = !!mine[li.dataset.card];
      li.classList.toggle('cc-have', has);
      const g = li.querySelector('.cc-got');
      if (g) { g.hidden = !has; if (has) g.textContent = 'Collected' + (mine[li.dataset.card].at ? ' at ' + mine[li.dataset.card].at : ''); }
    });
    document.querySelectorAll('.cc-huntbox').forEach((box) => {
      const all = box.querySelectorAll('[data-card]');
      const n = [...all].filter((li) => mine[li.dataset.card]).length;
      const p = box.querySelector('.cc-prog');
      if (p) p.textContent = `${n} of ${all.length} collected`;
    });
    const tot = document.getElementById('cc-total');
    if (tot) {
      const all = new Set([...document.querySelectorAll('[data-card]')].map((x) => x.dataset.card)).size, n = Object.keys(mine).length;
      tot.hidden = !n;
      tot.textContent = `You've collected ${n} of ${all} cards.`;
    }
  }
  function message(res) {
    if (res.got.length) return `Got ${res.got.length === 1 ? 'a card' : res.got.length + ' cards'}: ${res.got.map((g) => g.name + ' (' + g.at + ')').join(', ')}.`;
    if (res.nearest) {
      const km = Math.round(res.nearest.km);
      const mi = Math.round(res.nearest.km / 1.609344);
      return `No new cards right here. The closest one you don't have is ${res.nearest.name}, at ${res.nearest.at}, about ${km.toLocaleString()} km (${mi.toLocaleString()} mi) away.`;
    }
    return 'No new cards here, and you already have every card. Seriously impressive.';
  }
  async function button(btn, statusEl) {
    btn.addEventListener('click', async () => {
      statusEl.textContent = 'Checking where you are...';
      btn.disabled = true;
      try { statusEl.textContent = message(await checkIn()); mark(); } catch (e) {
        statusEl.textContent = e && e.code === 1 ? 'Location is blocked for this site. Allow it in your browser or app settings to collect cards.'
          : "Couldn't get your location. Try again outside or with location turned on.";
      }
      btn.disabled = false;
    });
  }
  window.eaCards = { collected, checkIn, mark, message, load, button };
  mark();
  const here = document.getElementById('cc-here');
  if (here) button(here, document.getElementById('cc-status'));
})();

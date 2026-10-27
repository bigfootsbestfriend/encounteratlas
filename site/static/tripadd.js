// "Add to road trip" buttons on place and state pages. Stops go into the road trip planner's own saved-trips list
// (localStorage "ea-trips", the format roadtrip.js reads: {label, pts: [[lat, lon, name]], km, at}) as one trip
// marked mine: true, so they show up under "Your saved trips" on /road-trip/ and plan as a route through every stop.
(function () {
  const btns = document.querySelectorAll('[data-trip-add]');
  if (!btns.length) return;
  const KEY = 'ea-trips', LABEL = 'My road trip';
  const BASE = btns[0].dataset.base || '';
  const track = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: location.pathname.split('/')[1] || 'home', ...p }); } catch (e) { /* no analytics */ } };
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } };
  const mine = (all) => all.find((t) => t && t.mine) || null;
  const has = (t, u) => !!(t && t.pts.some((p) => p[3] === u));

  function save(all) { try { localStorage.setItem(KEY, JSON.stringify(all.slice(0, 20))); return true; } catch (e) { return false; } }
  function toggle(stop) {
    const all = load();
    let t = mine(all);
    if (!t) { t = { label: LABEL, mine: true, pts: [], km: 40, at: '' }; all.unshift(t); }
    const was = has(t, stop[3]);
    t.pts = was ? t.pts.filter((p) => p[3] !== stop[3]) : [...t.pts, stop];
    t.at = new Date().toISOString().slice(0, 10);
    const rest = all.filter((x) => x !== t);
    if (!save(t.pts.length ? [t, ...rest] : rest)) return null;
    return { added: !was, n: t.pts.length };
  }

  let toast = null, timer = 0;
  function say(text, n) {
    if (!toast) {
      toast = document.createElement('div'); toast.className = 'trip-toast'; toast.setAttribute('role', 'status');
      document.body.append(toast);
    }
    const msg = document.createElement('span'); msg.textContent = text;
    toast.replaceChildren(msg);
    if (n) {
      const a = document.createElement('a'); a.href = BASE + '/road-trip/?mine=1';
      a.textContent = n + (n === 1 ? ' stop' : ' stops') + ' in your trip';
      a.addEventListener('click', () => track('roadtrip_open_mine', { stops: n }));
      toast.append(a);
    }
    toast.classList.add('is-on');
    clearTimeout(timer); timer = setTimeout(() => toast.classList.remove('is-on'), 6000);
  }
  function paint(b, on) {
    b.setAttribute('aria-pressed', String(on));
    b.querySelector('.trip-add-t').textContent = on ? 'In your trip' : 'Add to road trip';
  }

  const now = mine(load());
  btns.forEach((b) => {
    let stop;
    try { stop = JSON.parse(b.dataset.tripAdd); } catch (e) { return; }
    paint(b, has(now, stop[3]));
    b.hidden = false;
    b.addEventListener('click', () => {
      const r = toggle(stop);
      if (!r) { say("Your browser blocked saving. Private mode can do that.", 0); return; }
      document.querySelectorAll('[data-trip-add]').forEach((x) => { try { if (JSON.parse(x.dataset.tripAdd)[3] === stop[3]) paint(x, r.added); } catch (e) { /* skip */ } });
      say(r.added ? 'Added ' + stop[2] + '.' : 'Took ' + stop[2] + ' out.', r.n);
      track(r.added ? 'roadtrip_add' : 'roadtrip_remove', { stops: r.n });
    });
  });
})();

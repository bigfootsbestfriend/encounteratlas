// Tonight's skywatch forecast (site/sections/skywatch.py). At load it only switches the Moon phase times to the
// visitor's clock and marks meteor showers that are on now. Everything else waits for "Use my location" or
// "Pick a place": then Open-Meteo hourly clouds, astronomy-engine (Sun, Moon, twilight) and satellite.js with a
// Celestrak orbit (Space Station passes), the last two lazy-loaded from the same CDN and versions as skycore.js.
(() => {
  const cfgEl = document.getElementById('sw-config');
  if (!cfgEl) return;
  const CFG = JSON.parse(cfgEl.textContent);
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const round2 = (x) => Math.round(x * 100) / 100;
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  const H = 36e5, DAY = 864e5;
  const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
  const compass = (az) => COMPASS[Math.round(((az % 360) + 360) % 360 / 45) % 8];

  // ---- small setup at load: local times for the Moon phases, "On now" for showers --------------------------------
  try {
    document.querySelectorAll('.sw-phases time[data-t]').forEach((t) => {
      t.textContent = new Date(+t.dataset.t * 1000).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    });
    const d = new Date(), today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    document.querySelectorAll('.sw-table tr[data-start]').forEach((tr) => {
      if (tr.dataset.start <= today && today <= tr.dataset.end) { tr.classList.add('on'); tr.querySelector('.sw-now').hidden = false; }
    });
  } catch (e) { /* the build-time text stays */ }

  // ---- place picking (same town list and matching as /near-me/) ----------------------------------------------
  const status = $('sw-status'), out = $('sw-out'), place = $('sw-place');
  const say = (m) => { status.textContent = m; };
  let cities = null;
  const loadCities = () => cities || (cities = fetch(CFG.cities).then((r) => r.json()).catch(() => []));
  place.addEventListener('focus', loadCities, { once: true });
  place.addEventListener('input', async () => {
    const q = place.value.trim().toLowerCase();
    if (q.length < 2) return;
    const list = await loadCities(), hits = [];
    for (const c of list) { if (c[0].toLowerCase().startsWith(q)) { hits.push(c); if (hits.length >= 12) break; } }
    $('sw-cities').innerHTML = hits.map((c) => `<option value="${esc(c[0] + ', ' + c[1])}"></option>`).join('');
  });
  place.addEventListener('change', () => { if (cities && place.value.includes(',')) $('sw-pick').requestSubmit(); });
  $('sw-pick').addEventListener('submit', async () => {
    const v = place.value.trim().toLowerCase();
    if (!v) { say('Type a town or city first.'); place.focus(); return; }
    const list = await loadCities();
    const [name, reg] = v.split(',').map((s) => s.trim());
    const c = list.find((x) => x[0].toLowerCase() === name && (!reg || x[1].toLowerCase().startsWith(reg))) || list.find((x) => x[0].toLowerCase().startsWith(name));
    if (!c) { say(`We couldn't find "${place.value.trim()}". Try a bigger town nearby.`); return; }
    place.blur();
    run({ lat: round2(c[2]), lon: round2(c[3]), label: c[0] + ', ' + c[1] });
  });
  $('sw-locate').addEventListener('click', () => {
    if (!navigator.geolocation) { say('Your browser can\'t share a location. Pick a place instead.'); return; }
    say('Finding you...');
    navigator.geolocation.getCurrentPosition((p) => run({ lat: round2(p.coords.latitude), lon: round2(p.coords.longitude), label: 'your location', here: true }),
      () => say('Location is blocked. Pick a place instead.'), { timeout: 12000, maximumAge: 6e5 });
  });

  // ---- lazy libraries and data -------------------------------------------------------------------------------
  const libs = {};
  const script = (src) => libs[src] || (libs[src] = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = src; s.async = true; s.onload = res; s.onerror = () => { delete libs[src]; rej(new Error('load')); };
    document.head.append(s);
  }));
  const astro = () => (window.Astronomy ? Promise.resolve() : script(CFG.astro));
  const withTimeout = (p, ms) => Promise.race([p, new Promise((res) => setTimeout(() => res(null), ms))]);

  async function clouds(p) {
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${p.lat}&longitude=${p.lon}&hourly=cloud_cover&timezone=auto&timeformat=unixtime&past_days=1&forecast_days=3`;
    try {
      const j = await fetch(u).then((r) => (r.ok ? r.json() : null));
      if (!j || !j.hourly) return null;
      const byHour = new Map();
      j.hourly.time.forEach((t, i) => { if (j.hourly.cloud_cover[i] != null) byHour.set(t * 1000, j.hourly.cloud_cover[i]); });
      return { tz: j.timezone, byHour };
    } catch (e) { return null; }
  }

  async function tle() {
    try {
      const c = JSON.parse(localStorage.getItem('ea-iss-tle') || 'null');
      if (c && Date.now() - c.t < 12 * H) return c.l;
    } catch (e) { /* no storage */ }
    const t = await fetch('https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE').then((r) => (r.ok ? r.text() : ''));
    const l = t.trim().split('\n').map((s) => s.trim()).filter((s) => /^[12] /.test(s));
    if (l.length !== 2) throw new Error('tle');
    try { localStorage.setItem('ea-iss-tle', JSON.stringify({ t: Date.now(), l })); } catch (e) { /* fine */ }
    return l;
  }

  // Visible Space Station passes between a and b: the station above 10 degrees and still in sunlight, the observer in the dark.
  async function issPasses(p, a, b) {
    await script(CFG.sat);
    const [l1, l2] = await tle();
    const A = window.Astronomy, S = window.satellite, rec = S.twoline2satrec(l1, l2);
    const obs = new A.Observer(p.lat, p.lon, 0);
    const gd = { latitude: S.degreesToRadians(p.lat), longitude: S.degreesToRadians(p.lon), height: 0.1 };
    const passes = [];
    let cur = null;
    for (let t = a; t <= b; t += 20000) {
      const d = new Date(t), pv = S.propagate(rec, d);
      let vis = false, el = 0, az = 0;
      if (pv && pv.position) {
        const look = S.ecfToLookAngles(gd, S.eciToEcf(pv.position, S.gstime(d)));
        el = look.elevation * 180 / Math.PI; az = look.azimuth * 180 / Math.PI;
        if (el > 10 && sunAlt(A, obs, d) < -6) {
          const sv = A.GeoVector('Sun', A.MakeTime(d), true), n = Math.hypot(sv.x, sv.y, sv.z);
          const r = pv.position, dot = (r.x * sv.x + r.y * sv.y + r.z * sv.z) / n;
          const perp = Math.sqrt(Math.max(0, r.x * r.x + r.y * r.y + r.z * r.z - dot * dot));
          vis = dot > 0 || perp > 6371; // outside Earth's shadow (a cylinder is close enough)
        }
      }
      if (vis) {
        if (!cur) cur = { start: t, fromAz: az, max: el, maxAt: t };
        if (el > cur.max) { cur.max = el; cur.maxAt = t; }
        cur.end = t; cur.toAz = az;
      } else if (cur) { passes.push(cur); cur = null; }
    }
    if (cur) passes.push(cur);
    return passes.filter((x) => x.end - x.start >= 40000);
  }

  // ---- sky maths ----------------------------------------------------------------------------------------------
  const horizon = (A, obs, body, d) => { const t = A.MakeTime(d), eq = A.Equator(body, t, obs, true, true); return A.Horizon(t, obs, eq.ra, eq.dec, 'normal'); };
  const sunAlt = (A, obs, d) => horizon(A, obs, 'Sun', d).altitude;
  const tdate = (x) => (x ? x.date : null);

  // Which night is "tonight": the one we're in now, else the next one.
  function night(A, obs, now) {
    const alt = sunAlt(A, obs, now);
    let set = alt < -0.833 ? tdate(A.SearchRiseSet('Sun', obs, -1, A.MakeTime(now), -1.2)) : tdate(A.SearchRiseSet('Sun', obs, -1, A.MakeTime(now), 1.5));
    if (!set) {
      if (alt > -0.833) return { midnightSun: true };
      set = now; // polar night: it's dark now and stays dark
    }
    const rise = tdate(A.SearchRiseSet('Sun', obs, +1, A.MakeTime(set), 1.5)) || new Date(set.getTime() + 18 * H);
    let dusk = tdate(A.SearchAltitude('Sun', obs, -1, A.MakeTime(set), 1, -18));
    let dawn = dusk ? tdate(A.SearchAltitude('Sun', obs, +1, A.MakeTime(dusk), 1, -18)) : null;
    if (!dusk || dusk > rise || !dawn || dawn > rise) { dusk = null; dawn = null; }
    return { set, rise, dusk, dawn };
  }

  function moonEvents(A, obs, a, b) {
    const rise = tdate(A.SearchRiseSet('Moon', obs, +1, A.MakeTime(new Date(a - 2 * H)), (b - a) / DAY + 0.2));
    const set = tdate(A.SearchRiseSet('Moon', obs, -1, A.MakeTime(new Date(a - 2 * H)), (b - a) / DAY + 0.2));
    const mid = new Date((a + b) / 2), ill = A.Illumination('Moon', A.MakeTime(mid)).phase_fraction;
    return { rise, set, ill, waxing: A.MoonPhase(A.MakeTime(mid)) < 180 };
  }

  // Meteor showers on during this night (local date of the evening), with how close to the peak and how high the radiant gets.
  function showersTonight(A, obs, ymd, slots) {
    const [y, m, d] = ymd.split('-').map(Number), night = Date.UTC(y, m - 1, d);
    const md = (a) => a[0] * 100 + a[1];
    const outl = [];
    for (const s of CFG.showers) {
      for (const yy of [y - 1, y, y + 1]) {
        const peak = Date.UTC(yy, s.p[0] - 1, s.p[1]);
        const start = Date.UTC(yy - (md(s.s) > md(s.p) ? 1 : 0), s.s[0] - 1, s.s[1]);
        const end = Date.UTC(yy + (md(s.e) < md(s.p) ? 1 : 0), s.e[0] - 1, s.e[1]);
        if (night < start || night > end) continue;
        let best = -90, bestAt = null;
        for (const sl of slots) {
          if (sl.dark < 0.5) continue;
          const h = A.Horizon(A.MakeTime(sl.mid), obs, s.ra, s.dec, 'normal');
          if (h.altitude > best) { best = h.altitude; bestAt = sl.mid; }
        }
        const days = Math.round((night - peak) / DAY);
        let bonus = 0;
        if (best >= 10) bonus = Math.abs(days) <= 1 ? (s.z >= 50 ? 1 : 0.5) : Math.abs(days) <= 3 ? (s.z >= 50 ? 0.5 : 0.25) : 0;
        outl.push({ ...s, days, best, bestAt, bonus, peakDate: new Date(peak + 12 * H) });
      }
    }
    return outl.sort((a, b) => b.bonus - a.bonus || b.z - a.z);
  }

  // ---- drawing helpers ------------------------------------------------------------------------------------------
  function moonSvg(k, waxing, size, south) {
    const r = 10, rx = Math.abs(1 - 2 * k) * r;
    let lit = '';
    if (k > 0.98) lit = `<circle r="${r}" class="lit"/>`;
    else if (k >= 0.02) lit = `<path class="lit" d="M0 -${r}A${r} ${r} 0 0 1 0 ${r}A${rx.toFixed(2)} ${r} 0 0 ${k < 0.5 ? 0 : 1} 0 -${r}Z"${waxing !== !!south ? '' : ' transform="scale(-1 1)"'}/>`;
    return `<svg class="sw-moon" viewBox="-11 -11 22 22" width="${size}" height="${size}" aria-hidden="true"><circle r="${r}" class="dark"/>${lit}</svg>`;
  }
  const verdict = (s) => (s >= 8 ? 'Get out there' : s >= 6 ? 'Worth a look' : s >= 4 ? 'Hit and miss' : s >= 2 ? 'Not great' : 'Stay in tonight');
  const one = (x) => (Math.round(x * 10) / 10).toFixed(1).replace(/\.0$/, '');

  // ---- the forecast -------------------------------------------------------------------------------------------
  let busy = false;
  async function run(p) {
    if (busy) return;
    busy = true;
    window.eaTrack && eaTrack('skywatch_check', {});
    say(`Checking the sky over ${p.here ? "you" : p.label}...`);
    try {
      const [, wx] = await Promise.all([astro().catch(() => null), withTimeout(clouds(p), 12000)]);
      const A = window.Astronomy;
      if (!A) { say('The sky library didn\'t load. Check your connection and try again.'); return; }
      const tz = (wx && wx.tz) || Intl.DateTimeFormat().resolvedOptions().timeZone;
      const tf = (d, o) => d.toLocaleString(undefined, { timeZone: tz, ...o });
      const tm = (d) => (d ? tf(d, { hour: 'numeric', minute: '2-digit' }) : 'none');
      const obs = new A.Observer(p.lat, p.lon, 0), now = new Date();
      const n = night(A, obs, now);
      if (n.midnightSun) {
        out.innerHTML = `<div class="sw-card"><h2 class="sw-h">The Sun doesn't set ${p.here ? 'where you are' : 'in ' + esc(p.label)} tonight</h2><p>It's midnight sun season there, so there's no night to score. Enjoy the daylight.</p></div>`;
        out.hidden = false; say(''); return;
      }
      // Hour slots from the later of sunset and now, to sunrise
      const first = Math.floor(Math.max(n.set.getTime(), now.getTime()) / H) * H, last = n.rise.getTime();
      const slots = [];
      for (let t = first; t + H / 2 < last && slots.length < 24; t += H) {
        const mid = new Date(Math.min(t + H / 2, last - 60000)), sa = sunAlt(A, obs, mid), mh = horizon(A, obs, 'Moon', mid);
        const ill = A.Illumination('Moon', A.MakeTime(mid)).phase_fraction;
        const cloud = wx ? wx.byHour.get(t) : undefined;
        const clear = cloud == null ? 1 : 1 - cloud / 100;
        const dark = clamp((-6 - sa) / 12, 0, 1);
        const moonB = mh.altitude > 0 ? ill * clamp((mh.altitude + 2) / 25, 0, 1) : 0;
        slots.push({ t, mid, cloud, clear, dark, moonB, moonUp: mh.altitude > 0, cPts: 5 * clear, mPts: 3 * (1 - moonB) * clear, dPts: 2 * dark * clear });
      }
      if (!slots.length) { say('It\'s nearly sunrise there. Check back this evening.'); return; }
      // Best three hours
      const W = Math.min(3, slots.length);
      let bi = 0, bs = -1;
      for (let i = 0; i + W <= slots.length; i++) {
        const s = slots.slice(i, i + W).reduce((a, x) => a + x.cPts + x.mPts + x.dPts, 0);
        if (s > bs) { bs = s; bi = i; }
      }
      const win = slots.slice(bi, bi + W), avg = (k) => win.reduce((a, x) => a + x[k], 0) / W;
      const cPts = avg('cPts'), mPts = avg('mPts'), dPts = avg('dPts'), clr = avg('clear');
      const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(n.set);
      const showers = showersTonight(A, obs, ymd, slots);
      const moon = moonEvents(A, obs, n.set.getTime(), n.rise.getTime());

      say('Working out the Space Station passes...');
      let passes = null;
      try { passes = await withTimeout(issPasses(p, slots[0].t, last), 15000); } catch (e) { passes = null; }
      const goodPass = (passes || []).some((x) => x.max >= 20);
      const showerB = showers.length ? showers[0].bonus : 0;
      const bonus = (showerB + (goodPass ? 0.5 : 0)) * clr;
      const total = Math.min(10, cPts + mPts + dPts + bonus);

      // ---- render
      const cloudTxt = !wx ? 'We couldn\'t get the cloud forecast, so this assumes a clear sky.'
        : `About ${Math.round(100 - clr * 100)}% cloud in your best hours.`;
      const moonTxt = win.some((x) => x.moonUp) ? `The Moon is ${Math.round(moon.ill * 100)}% lit and up during your best hours.`
        : `The Moon is ${Math.round(moon.ill * 100)}% lit but below the horizon during your best hours.`;
      const darkTxt = n.dusk ? `Properly dark from ${tm(n.dusk)} to ${tm(n.dawn)}.` : 'The sky never gets fully dark here tonight (the Sun doesn\'t sink 18 degrees below the horizon).';
      const bonusBits = [];
      if (showerB) bonusBits.push(`${showers[0].n} ${Math.abs(showers[0].days) <= 1 ? 'at their peak' : 'near their peak'}`);
      if (goodPass) bonusBits.push('a Space Station pass');
      const row = (name, pts, max, txt) => `<li><span class="sw-bk-h"><b>${name}</b><span>${one(pts)} / ${max}</span></span>`
        + `<span class="sw-bar" aria-hidden="true"><i style="width:${clamp(pts / max * 100, 0, 100)}%"></i></span><span class="sw-bk-t">${esc(txt)}</span></li>`;
      const deg = clamp(total / 10, 0, 1) * 360;
      const winEnd = new Date(win[W - 1].t + H > last ? last : win[W - 1].t + H);
      const tzName = tz.replace(/_/g, ' ');

      const hours = slots.map((x, i) => {
        const inWin = i >= bi && i < bi + W, c = x.cloud == null ? null : Math.round(x.cloud);
        return `<li class="${inWin ? 'win' : ''}" style="--dk:${x.dark.toFixed(2)}"><span class="sw-hr">${esc(tf(new Date(x.t), { hour: 'numeric' }))}</span>`
          + `<span class="sw-cl" aria-hidden="true"><i style="height:${c == null ? 0 : c}%"></i></span>`
          + `<span class="sw-cp">${c == null ? '?' : c + '%'}<span class="visually-hidden"> cloud</span></span>`
          + `<span class="sw-hm">${x.moonUp ? moonSvg(moon.ill, moon.waxing, 16, p.lat < 0) + '<span class="visually-hidden">Moon up</span>' : ''}</span></li>`;
      }).join('');

      let showerHtml = '';
      if (showers.length) {
        showerHtml = showers.map((s) => {
          const when = s.days === 0 ? 'Tonight is the peak night.' : s.days < 0 ? `The peak is ${-s.days} night${s.days === -1 ? '' : 's'} away (${tf(s.peakDate, { month: 'short', day: 'numeric', timeZone: 'UTC' })}).`
            : `The peak was ${s.days} night${s.days === 1 ? '' : 's'} ago, so expect fewer.`;
          const rad = s.best < 10 ? 'From here the radiant barely gets above the horizon, so you\'ll see very few.'
            : `The radiant is highest around ${tm(s.bestAt)}, and that's when you'll see the most.`;
          return `<li><b>${esc(s.n)}</b> (up to ${s.z} an hour at best). ${when} ${rad}</li>`;
        }).join('');
        showerHtml = `<div class="sw-box"><h3>Meteor showers on tonight</h3><ul>${showerHtml}</ul></div>`;
      } else {
        showerHtml = '<div class="sw-box"><h3>Meteor showers</h3><p>No major shower is on tonight. You\'ll still catch a few random meteors an hour on a dark night.</p></div>';
      }
      let issHtml;
      if (passes === null) issHtml = '<p>We couldn\'t get the Space Station\'s orbit right now, so passes are left out of the score.</p>';
      else if (!passes.length) issHtml = '<p>No visible passes tonight. The station is up there, it\'s just not lit up while it\'s dark where you are.</p>';
      else {
        issHtml = '<ul>' + passes.map((x) => `<li><b>${tm(new Date(x.start))}</b>, about ${Math.max(1, Math.round((x.end - x.start) / 60000))} min. `
          + `Comes up in the ${compass(x.fromAz)}, gets ${Math.round(x.max)}° up${x.max > 70 ? ' (nearly overhead)' : ''} and ${x.toAz != null ? 'fades out in the ' + compass(x.toAz) : ''}.</li>`).join('') + '</ul>'
          + '<p class="small">It looks like a bright, steady star sliding across the sky with no blinking lights. Passes below 20° are easy to miss behind trees.</p>';
      }

      out.innerHTML = `<div class="sw-card">
  <p class="sw-for">Tonight ${p.here ? "where you are" : "in <b>" + esc(p.label) + "</b>"}, ${esc(tf(n.set, { weekday: 'long', month: 'long', day: 'numeric' }))}. Times in ${esc(tzName)}.</p>
  <div class="sw-top">
    <div class="sw-dial" style="--deg:${deg}deg" role="img" aria-label="Score ${one(total)} out of 10"><span><b>${one(total)}</b><small>out of 10</small></span></div>
    <div class="sw-verdict"><h2 class="sw-h">${verdict(total)}</h2>
      <p class="sw-best">${clr < 0.15 ? "It looks clouded over all night." : `Best time to be out: <b>${tm(new Date(Math.max(win[0].t, n.set.getTime(), now.getTime())))} to ${tm(winEnd)}</b>`}</p></div>
  </div>
  <ul class="sw-bk">${row('Clouds', cPts, 5, cloudTxt)}${row('Moon', mPts, 3, moonTxt)}${row('Darkness', dPts, 2, darkTxt)}
    <li><span class="sw-bk-h"><b>Bonus</b><span>+${one(bonus)}</span></span><span class="sw-bk-t">${bonusBits.length ? esc('For ' + bonusBits.join(' and ') + '.') + (clr < 0.15 ? ' The clouds cancel it out.' : clr < 0.9 ? ' Cut back a bit for the clouds.' : '') : 'No meteor shower peak or bright Space Station pass tonight.'}</span></li></ul>
  <h3>Hour by hour</h3>
  <ol class="sw-hours" tabindex="0" aria-label="Cloud cover each hour tonight; your best hours are highlighted">${hours}</ol>
  <p class="sw-key small"><span class="k-win">Best hours</span> <span class="k-dark">Darker shading means a darker sky</span> ${wx ? '' : '<span>Cloud forecast not available</span>'}</p>
  <dl class="sw-times">
    <div><dt>Sunset</dt><dd>${tm(n.set)}</dd></div>
    <div><dt>Fully dark</dt><dd>${n.dusk ? tm(n.dusk) : 'not tonight'}</dd></div>
    <div><dt>Dark until</dt><dd>${n.dawn ? tm(n.dawn) : 'n/a'}</dd></div>
    <div><dt>Sunrise</dt><dd>${tm(n.rise)}</dd></div>
    <div><dt>Moonrise</dt><dd>${tm(moon.rise)}</dd></div>
    <div><dt>Moonset</dt><dd>${tm(moon.set)}</dd></div>
    <div class="sw-tm"><dt>Moon</dt><dd>${moonSvg(moon.ill, moon.waxing, 22, p.lat < 0)} ${Math.round(moon.ill * 100)}% lit, ${moon.waxing ? 'growing' : 'shrinking'}</dd></div>
  </dl>
  ${showerHtml}
  <div class="sw-box"><h3>Space Station passes</h3>${issHtml}</div>
  <p class="sw-next"><a class="btn" href="${esc(CFG.planet)}">Saw something? Check it here first</a></p>
  <p class="small muted">Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo.com</a>. Clouds are a forecast and can change, so check again before you head out.</p>
</div>`;
      out.hidden = false;
      say('');
      const hs = out.querySelector('.sw-hours'), w0 = hs && hs.querySelector('li.win');
      if (w0) hs.scrollLeft = Math.max(0, w0.offsetLeft - hs.offsetLeft - 60);
      out.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      say('Something went wrong working out the sky. Try again in a minute.');
    } finally { busy = false; }
  }
})();

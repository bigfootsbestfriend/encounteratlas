// "Was it a planet?" (site/sections/skycheck.py): what bright things were in the sky at a time and place.
// Sun, Moon, planets and bright stars with astronomy-engine; the ISS with satellite.js and a Celestrak orbit (recent dates only).
(() => {
  const form = document.querySelector('.sk-form');
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  const out = document.querySelector('.sk-out');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
  const compass = (az) => COMPASS[Math.round(((az % 360) + 360) % 360 / 45) % 8];
  const height = (alt) => (alt < 15 ? 'low on the horizon' : alt < 40 ? 'part way up' : alt < 70 ? 'high up' : 'nearly overhead');
  // Brightest stars: [name, RA hours, Dec degrees, magnitude] (J2000)
  const STARS = [['Sirius', 6.752, -16.716, -1.46], ['Canopus', 6.399, -52.696, -0.74], ['Arcturus', 14.261, 19.182, -0.05], ['Vega', 18.616, 38.784, 0.03],
    ['Capella', 5.278, 45.998, 0.08], ['Rigel', 5.242, -8.202, 0.13], ['Procyon', 7.655, 5.225, 0.34], ['Betelgeuse', 5.919, 7.407, 0.5],
    ['Altair', 19.846, 8.868, 0.77], ['Aldebaran', 4.599, 16.509, 0.85], ['Spica', 13.42, -11.161, 0.97], ['Antares', 16.49, -26.432, 1.09],
    ['Pollux', 7.755, 28.026, 1.14], ['Fomalhaut', 22.961, -29.622, 1.16], ['Deneb', 20.69, 45.28, 1.25], ['Regulus', 10.14, 11.967, 1.35]];
  const PLANETS = ['Venus', 'Jupiter', 'Mars', 'Saturn', 'Mercury'];
  const WHY = {
    Venus: 'Venus is the classic UFO: dazzling, steady and white, and it seems to follow your car.',
    Jupiter: 'Jupiter is bright, steady and cream-coloured. It barely moves over a few minutes.',
    Mars: 'Mars looks like a steady orange-red star.',
    Saturn: 'Saturn looks like a steady, yellowish star.',
    Mercury: 'Mercury is only ever low in the twilight, near where the Sun set or will rise.',
    Moon: 'A low, orange or cloud-covered Moon can look very strange.',
    star: 'Low bright stars twinkle hard and seem to flash colours, especially Sirius.',
    starHigh: 'A bright star: a small white point that holds its place among the other stars.',
    ISS: 'The Space Station looks like a bright, steady light crossing the sky in a few minutes, with no blinking.',
  };

  // ---- inputs -------------------------------------------------------------------------------
  const when = $('sk-when'), place = $('sk-place');
  const pad = (n) => String(n).padStart(2, '0');
  const now = new Date();
  when.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
  try { $('sk-tz').textContent = Intl.DateTimeFormat().resolvedOptions().timeZone.replace(/_/g, ' '); } catch (e) { /* keep the default text */ }
  let cities = null, loc = null;
  const loadCities = () => cities || (cities = fetch(form.dataset.cities).then((r) => r.json()).catch(() => []));
  place.addEventListener('focus', loadCities, { once: true });
  place.addEventListener('input', async () => {
    loc = null;
    const q = place.value.trim().toLowerCase();
    if (q.length < 2) return;
    const list = await loadCities();
    const hits = [];
    for (const c of list) { if (c[0].toLowerCase().startsWith(q)) { hits.push(c); if (hits.length >= 12) break; } }
    $('sk-cities').innerHTML = hits.map((c) => `<option value="${esc(c[0] + ', ' + c[1])}"></option>`).join('');
  });
  async function resolvePlace() {
    if (loc) return loc;
    const v = place.value.trim().toLowerCase();
    if (!v) return null;
    const list = await loadCities();
    const [name, reg] = v.split(',').map((s) => s.trim());
    const c = list.find((x) => x[0].toLowerCase() === name && (!reg || x[1].toLowerCase().startsWith(reg))) || list.find((x) => x[0].toLowerCase().startsWith(name));
    return c ? { lat: c[2], lon: c[3], label: c[0] + ', ' + c[1] } : null;
  }
  $('sk-me').addEventListener('click', (e) => {
    const b = e.currentTarget;
    if (!navigator.geolocation) { b.textContent = 'Location not available'; return; }
    b.textContent = 'Finding you...';
    navigator.geolocation.getCurrentPosition((p) => {
      loc = { lat: p.coords.latitude, lon: p.coords.longitude, label: 'your location' };
      place.value = 'My location'; b.textContent = 'Using your location';
    }, () => { b.textContent = 'Location blocked'; }, { timeout: 10000 });
  });
  let dir = null, hgt = null;
  function toggle(sel, set) {
    document.querySelectorAll(sel).forEach((b) => b.addEventListener('click', () => {
      const on = b.getAttribute('aria-pressed') !== 'true';
      document.querySelectorAll(sel).forEach((x) => x.setAttribute('aria-pressed', 'false'));
      b.setAttribute('aria-pressed', String(on));
      set(on ? b.dataset : null);
    }));
  }
  toggle('.sk-dir', (d) => { dir = d ? +d.az : null; });
  toggle('.sk-h', (d) => { hgt = d ? d.h : null; });

  // ---- ISS ------------------------------------------------------------------------------------
  async function iss(date, lat, lon) {
    if (!window.satellite || Math.abs(date - Date.now()) > 14 * 864e5) return null; // old orbits are too far off for past dates
    try {
      const t = await fetch('https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE').then((r) => r.text());
      const [, l1, l2] = t.trim().split('\n').map((s) => s.trim());
      const rec = satellite.twoline2satrec(l1, l2);
      const gd = { latitude: satellite.degreesToRadians(lat), longitude: satellite.degreesToRadians(lon), height: 0.1 };
      let best = null;
      for (let m = -20; m <= 20; m++) {
        const d = new Date(date.getTime() + m * 60000);
        const pv = satellite.propagate(rec, d);
        if (!pv.position) continue;
        const look = satellite.ecfToLookAngles(gd, satellite.eciToEcf(pv.position, satellite.gstime(d)));
        const el = look.elevation * 180 / Math.PI;
        if (el > 10 && (!best || el > best.alt)) best = { alt: el, az: look.azimuth * 180 / Math.PI, min: m };
      }
      return best;
    } catch (e) { return null; }
  }

  // ---- compute ----------------------------------------------------------------------------------
  $('sk-go').addEventListener('click', async () => {
    window.eaTrack && eaTrack('planet_check', {});
    const A = window.Astronomy;
    const p = await resolvePlace();
    if (!A) { alertBox('The sky library did not load. Check your connection and try again.'); return; }
    if (!p) { alertBox('Pick a town from the list, or use your location.'); place.focus(); return; }
    const date = new Date(when.value);
    if (isNaN(date)) { alertBox('Enter the date and time.'); return; }
    const obs = new A.Observer(p.lat, p.lon, 0);
    const t = A.MakeTime(date);
    const hor = (ra, dec) => A.Horizon(t, obs, ra, dec, 'normal');
    const sunEq = A.Equator('Sun', t, obs, true, true);
    const sun = hor(sunEq.ra, sunEq.dec);
    const items = [];
    const moonEq = A.Equator('Moon', t, obs, true, true), moon = hor(moonEq.ra, moonEq.dec);
    const phase = A.MoonPhase(t), illum = Math.round(A.Illumination('Moon', t).phase_fraction * 100);
    items.push({ n: 'The Moon', k: 'Moon', alt: moon.altitude, az: moon.azimuth, mag: -10, note: `${illum}% lit${phase < 180 ? ', waxing' : ', waning'}` });
    for (const b of PLANETS) {
      const eq = A.Equator(b, t, obs, true, true), h = hor(eq.ra, eq.dec);
      items.push({ n: b, k: b, alt: h.altitude, az: h.azimuth, mag: A.Illumination(b, t).mag });
    }
    for (const [n, ra, dec, mag] of STARS) {
      const h = hor(ra, dec);
      items.push({ n, k: 'star', alt: h.altitude, az: h.azimuth, mag, note: 'star' });
    }
    const st = await iss(date, p.lat, p.lon);
    if (st) items.push({ n: 'International Space Station', k: 'ISS', alt: st.alt, az: st.az, mag: -3,
      note: st.min === 0 ? 'passing at that minute' : `highest ${Math.abs(st.min)} min ${st.min < 0 ? 'before' : 'after'} your time` });
    const dark = sun.altitude < -6;
    const up = items.filter((x) => x.alt > 0 && (x.mag < 1.5 || x.k === 'Moon') && (dark || x.mag < -3.5 || x.k === 'Moon'));
    // How well each object matches what the person said
    const angle = (a, b) => Math.abs(((a - b + 540) % 360) - 180);
    const band = { low: [0, 25], mid: [20, 60], high: [50, 90] };
    for (const x of up) {
      x.dirOk = dir == null || angle(x.az, dir) <= 50;
      x.hOk = !hgt || (x.alt >= band[hgt][0] && x.alt <= band[hgt][1]);
      x.score = (x.dirOk ? 2 : 0) + (x.hOk ? 1 : 0) - x.mag / 4;
    }
    up.sort((a, b) => b.score - a.score);
    const match = up.filter((x) => x.dirOk && x.hOk && (dir != null || hgt));
    // Summary
    const sky = sun.altitude > 0 ? 'The Sun was up' : sun.altitude > -6 ? 'It was twilight' : sun.altitude > -18 ? 'It was getting dark' : 'It was full night';
    let sum = `${sky} in ${esc(p.label)}. `;
    if (match.length) sum += `<strong>${match.length === 1 ? esc(match[0].n) + ' was' : match.slice(0, 2).map((x) => esc(x.n)).join(' and ') + ' were'} right where you were looking.</strong> ${WHY[match[0].k] || (match[0].alt < 20 ? WHY.star : WHY.starHigh)}`;
    else if (dir != null || hgt) sum += 'Nothing bright was where you were looking. If what you saw was bright and steady, a plane, drone or satellite is more likely than a planet. If you still can\'t explain it, report it.';
    else sum += `${up.length} bright thing${up.length === 1 ? ' was' : 's were'} up. Pick a direction above to narrow it down.`;
    if (Math.abs(date - Date.now()) > 14 * 864e5) sum += ' (The Space Station can only be checked for the last two weeks.)';
    $('sk-sum').innerHTML = sum;
    $('sk-list').innerHTML = up.slice(0, 10).map((x) => `<li class="${x.dirOk && x.hOk && (dir != null || hgt) ? 'hit' : ''}"><b>${esc(x.n)}</b>
      <span>${compass(x.az)}, ${height(x.alt)} (${Math.round(x.alt)}° up)${x.note && x.note !== 'star' ? ' · ' + esc(x.note) : ''}</span>
      <small>${esc(x.k === 'star' ? (x.alt < 20 ? WHY.star : WHY.starHigh) : WHY[x.k] || '')}</small></li>`).join('') || '<li>Nothing bright was above the horizon.</li>';
    dome(up, sun);
    out.hidden = false;
    out.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  function alertBox(msg) { const n = $('sk-sum'); out.hidden = false; n.textContent = msg; $('sk-list').innerHTML = ''; $('sk-dome').innerHTML = ''; }

  // Polar sky map: centre = overhead, edge = horizon, north at the top, east on the left (as seen looking up)
  function dome(up, sun) {
    const r = 100, xy = (alt, az) => { const d = r * (90 - alt) / 90, a = az * Math.PI / 180; return [-d * Math.sin(a), -d * Math.cos(a)]; };
    const night = sun.altitude < -6;
    let s = `<circle r="${r}" class="sk-sky${night ? ' night' : ''}"/><circle r="${r * 2 / 3}" class="sk-ring"/><circle r="${r / 3}" class="sk-ring"/>`;
    for (const [lab, az] of [['N', 0], ['E', 90], ['S', 180], ['W', 270]]) { const [x, y] = xy(-12, az); s += `<text x="${x}" y="${y + 4}" class="sk-card">${lab}</text>`; }
    if (dir != null) {
      const [x1, y1] = xy(0, dir - 45), [x2, y2] = xy(0, dir + 45);
      s += `<path d="M0 0L${x1} ${y1}A${r} ${r} 0 0 0 ${x2} ${y2}Z" class="sk-wedge"/>`;
    }
    for (const x of up.slice(0, 12)) {
      const [px, py] = xy(x.alt, x.az);
      const size = x.k === 'Moon' ? 7 : Math.max(2.2, 5 - x.mag);
      s += `<circle cx="${px}" cy="${py}" r="${size}" class="sk-obj sk-${x.k === 'star' ? 'star' : x.k === 'Moon' ? 'moon' : x.k === 'ISS' ? 'iss' : 'planet'}${x.dirOk && x.hOk ? ' hit' : ''}"/>`
        + `<text x="${px}" y="${py - size - 3}" class="sk-lbl">${esc(x.n.replace('The ', '').replace('International Space Station', 'ISS'))}</text>`;
    }
    $('sk-dome').innerHTML = s;
  }
})();

// "Conditions that night" on reader report pages: the Moon, the Sun, bright planets, meteor showers and the weather at
// the time and place of a sighting. The panel is plain HTML in the page (site/sections/reports.py, or vote.js for the
// /reports/?id= view); nothing here runs until it scrolls into view. Then astronomy-engine is lazy-loaded (same CDN
// and version as skycore.js), the weather comes from Open-Meteo (archive API, or the forecast API's past_days for the
// last week, which the archive doesn't have yet) and the shower table from /data/showers.json (skywatch.py's list).
//   <section class="cond" data-cond="lat,lon,YYYY-MM-DD,HH:MM or empty,1 if region-only"> ... </section>
//   eaCond.watch(el) for panels added after load.
(() => {
  if (window.eaCond) return;
  const ASTRO = 'https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/astronomy.browser.min.js';
  const H = 36e5, DAY = 864e5;
  const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
  const compass = (az) => COMPASS[Math.round(((az % 360) + 360) % 360 / 45) % 8];
  const height = (alt) => (alt < 15 ? 'low in the sky' : alt < 40 ? 'part way up' : alt < 70 ? 'high up' : 'nearly overhead');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const round2 = (x) => Math.round(x * 100) / 100;
  const me = document.currentScript && document.currentScript.src;
  const base = (() => { try { return new URL('..', me).pathname.replace(/\/static\/?$/, '').replace(/\/$/, ''); } catch (e) { return ''; } })();

  // ---- loading -------------------------------------------------------------------------------------------------------
  let astroP = null;
  const astro = () => (window.Astronomy ? Promise.resolve() : astroP || (astroP = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = ASTRO; s.async = true; s.onload = res; s.onerror = () => { astroP = null; rej(new Error('astro')); };
    document.head.append(s);
  })));
  const timeout = (p, ms) => Promise.race([p, new Promise((res) => setTimeout(() => res(null), ms))]);
  let showersP = null;
  const showers = () => showersP || (showersP = fetch(base + '/data/showers.json').then((r) => (r.ok ? r.json() : [])).catch(() => []));

  // ---- time zones ----------------------------------------------------------------------------------------------------
  const tzOk = (tz) => { try { new Intl.DateTimeFormat('en', { timeZone: tz }); return true; } catch (e) { return false; } };
  // Rough zone from the longitude, for when the weather call (which names the real zone) fails.
  const lonTz = (lon) => { const o = Math.round(lon / 15); return o === 0 ? 'UTC' : `Etc/GMT${o > 0 ? '-' : '+'}${Math.abs(o)}`; };
  function offsetMin(tz, ms) {
    const p = new Intl.DateTimeFormat('en-US', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric' }).formatToParts(new Date(ms));
    const g = (k) => +p.find((x) => x.type === k).value;
    return (Date.UTC(g('year'), g('month') - 1, g('day'), g('hour') % 24, g('minute'), g('second')) - Math.floor(ms / 1000) * 1000) / 60000;
  }
  function localToUtc(ymd, hm, tz) {
    const [y, m, d] = ymd.split('-').map(Number), [hh, mm] = hm.split(':').map(Number);
    const guess = Date.UTC(y, m - 1, d, hh, mm);
    const t = guess - offsetMin(tz, guess) * 60000;
    return guess - offsetMin(tz, t) * 60000;
  }

  // ---- weather (Open-Meteo, no key) ----------------------------------------------------------------------------------
  const VARS = 'temperature_2m,cloud_cover,wind_speed_10m,precipitation';
  async function getJson(u) {
    try { const r = await fetch(u); return r.ok ? await r.json() : null; } catch (e) { return null; }
  }
  function hoursOf(j) {
    if (!j || !j.hourly || !j.hourly.time) return null;
    const m = new Map(), hr = j.hourly;
    hr.time.forEach((t, i) => {
      if (hr.cloud_cover[i] == null && hr.temperature_2m[i] == null) return;
      m.set(t * 1000, { cloud: hr.cloud_cover[i], temp: hr.temperature_2m[i], wind: hr.wind_speed_10m[i], rain: hr.precipitation[i] });
    });
    return m.size ? { tz: j.timezone, hours: m } : null;
  }
  async function weather(lat, lon, ymd) {
    const [y, m, d] = ymd.split('-').map(Number), day = Date.UTC(y, m - 1, d);
    const ago = (Date.now() - day) / DAY;
    if (y < 1940 || ago < -1) return null;
    const next = new Date(day + DAY).toISOString().slice(0, 10);
    const q = `latitude=${round2(lat)}&longitude=${round2(lon)}&hourly=${VARS}&timezone=auto&timeformat=unixtime`;
    let w = null;
    if (ago > 6) w = hoursOf(await getJson(`https://archive-api.open-meteo.com/v1/archive?${q}&start_date=${ymd}&end_date=${next}`));
    // The archive runs about 5 days behind, so recent nights come from the forecast API's past days instead.
    if (!w && ago < 90) w = hoursOf(await getJson(`https://api.open-meteo.com/v1/forecast?${q}&past_days=${Math.min(92, Math.ceil(ago) + 2)}&forecast_days=2`));
    return w;
  }
  const cloudWord = (c) => (c < 15 ? 'Clear' : c < 40 ? 'Mostly clear' : c < 70 ? 'Partly cloudy' : c < 90 ? 'Mostly cloudy' : 'Overcast');
  const temp = (c) => `${Math.round(c)}°C (${Math.round(c * 9 / 5 + 32)}°F)`;
  const wind = (k) => `${Math.round(k)} km/h (${Math.round(k / 1.609)} mph)`;

  // ---- sky -----------------------------------------------------------------------------------------------------------
  const tdate = (x) => (x ? x.date.getTime() : null);
  const hor = (A, obs, body, ms) => { const t = A.MakeTime(new Date(ms)), eq = A.Equator(body, t, obs, true, true); return A.Horizon(t, obs, eq.ra, eq.dec, 'normal'); };
  const sunAlt = (A, obs, ms) => hor(A, obs, 'Sun', ms).altitude;
  function phaseName(a) {
    if (a < 12 || a >= 348) return 'New Moon';
    if (a < 78) return 'Waxing crescent';
    if (a < 102) return 'First quarter';
    if (a < 168) return 'Waxing gibbous';
    if (a < 192) return 'Full Moon';
    if (a < 258) return 'Waning gibbous';
    if (a < 282) return 'Last quarter';
    return 'Waning crescent';
  }
  function moonSvg(k, waxing, south) {
    const r = 10, rx = Math.abs(1 - 2 * k) * r;
    let lit = '';
    if (k > 0.98) lit = `<circle r="${r}" class="lit"/>`;
    else if (k >= 0.02) lit = `<path class="lit" d="M0 -${r}A${r} ${r} 0 0 1 0 ${r}A${rx.toFixed(2)} ${r} 0 0 ${k < 0.5 ? 0 : 1} 0 -${r}Z"${waxing !== !!south ? '' : ' transform="scale(-1 1)"'}/>`;
    return `<svg class="cond-moon" viewBox="-11 -11 22 22" width="34" height="34" aria-hidden="true"><circle r="${r}" class="dark"/>${lit}</svg>`;
  }
  // The night around a moment: the sunset before it (or, by day, the next one) and the sunrise after that, plus full dark.
  function nightOf(A, obs, ms, isDay) {
    const t = A.MakeTime(new Date(ms));
    const set = isDay ? tdate(A.SearchRiseSet('Sun', obs, -1, t, 1.2)) : tdate(A.SearchRiseSet('Sun', obs, -1, t, -1.2));
    if (!set) return null;
    const rise = tdate(A.SearchRiseSet('Sun', obs, +1, A.MakeTime(new Date(set)), 1.5));
    if (!rise) return { set };
    let dusk = tdate(A.SearchAltitude('Sun', obs, -1, A.MakeTime(new Date(set)), 1, -18));
    let dawn = dusk ? tdate(A.SearchAltitude('Sun', obs, +1, A.MakeTime(new Date(dusk)), 1, -18)) : null;
    if (!dusk || dusk > rise || !dawn || dawn > rise) { dusk = null; dawn = null; }
    return { set, rise, dusk, dawn };
  }
  const PLANETS = ['Venus', 'Jupiter', 'Mars', 'Saturn'];
  // Same rule as skycore.js: Venus shows in twilight, the others need a darker sky and must be bright enough to catch the eye.
  function planetUp(A, obs, b, ms, sa) {
    const h = hor(A, obs, b, ms), mag = A.Illumination(b, A.MakeTime(new Date(ms))).mag;
    return h.altitude > 3 && (b === 'Venus' ? sa < -3 : sa < -6 && mag < 0.6) ? { alt: h.altitude, az: h.azimuth, mag } : null;
  }
  const bright = (mag) => (mag < -3 ? 'very bright' : mag < -1 ? 'bright' : 'easy to spot');
  function showersOn(list, ymd) {
    const [y, m, d] = ymd.split('-').map(Number), night = Date.UTC(y, m - 1, d);
    const md = (a) => a[0] * 100 + a[1], out = [];
    for (const s of list || []) {
      for (const yy of [y - 1, y, y + 1]) {
        const peak = Date.UTC(yy, s.p[0] - 1, s.p[1]);
        const start = Date.UTC(yy - (md(s.s) > md(s.p) ? 1 : 0), s.s[0] - 1, s.s[1]);
        const end = Date.UTC(yy + (md(s.e) < md(s.p) ? 1 : 0), s.e[0] - 1, s.e[1]);
        if (night >= start && night <= end) out.push({ ...s, days: Math.round((night - peak) / DAY), peak });
      }
    }
    return out.sort((a, b) => b.z - a.z);
  }

  // ---- the panel -----------------------------------------------------------------------------------------------------
  async function fill(el) {
    const [lat, lon, ymd, hm, region] = (el.dataset.cond || '').split(',');
    const la = +lat, lo = +lon;
    if (!Number.isFinite(la) || !Number.isFinite(lo) || !/^\d{4}-\d\d-\d\d$/.test(ymd)) return;
    const known = /^\d\d:\d\d$/.test(hm || '');
    const status = el.querySelector('.cond-status') || el.appendChild(Object.assign(document.createElement('p'), { className: 'cond-status' }));
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.textContent = 'Working out the sky and weather...';
    window.eaTrack && window.eaTrack('conditions_view', {});
    const [, wx, sh] = await Promise.all([astro().catch(() => null), timeout(weather(la, lo, ymd), 15000), timeout(showers(), 8000)]);
    const A = window.Astronomy;
    if (!A) { status.textContent = 'The sky details didn\'t load. Check your connection and reload the page.'; return; }
    try {
      const tz = wx && wx.tz && tzOk(wx.tz) ? wx.tz : lonTz(lo);
      const tf = (ms, o) => new Date(ms).toLocaleString(undefined, { timeZone: tz, ...o });
      const tm = (ms) => (ms ? tf(ms, { hour: 'numeric', minute: '2-digit' }) : 'none');
      const obs = new A.Observer(la, lo, 0);
      const at = known ? localToUtc(ymd, hm, tz) : localToUtc(ymd, '12:00', tz);
      const saAt = sunAlt(A, obs, at);
      const isDay = known && saAt > -0.833;
      const n = nightOf(A, obs, at, isDay || !known);
      const ok = n && n.rise;
      const mid = known ? at : ok ? (n.set + n.rise) / 2 : at + 12 * H;
      const rows = [];
      const row = (k, html, cls = '') => rows.push(`<div class="cond-row ${cls}"><dt>${k}</dt><dd>${html}</dd></div>`);

      // Sun and darkness
      let sun;
      if (known) {
        if (saAt > -0.833) sun = `Daylight. The Sun was ${Math.round(saAt)}° up${n ? ` and set at ${tm(n.set)}` : ''}.`;
        else if (saAt > -12) {
          const am = sunAlt(A, obs, at + 10 * 60000) > saAt;
          if (saAt > -6) sun = am ? `Twilight. The sky was getting light and the Sun came up at ${tm(n && n.rise)}.` : `Twilight. The Sun had just set (${tm(n && n.set)}) and there was still some light in the sky.`;
          else sun = am ? 'Getting light. The Sun was still well down but the sky was starting to brighten.' : 'Getting dark. The Sun was well down but the sky wasn\'t black yet.';
        } else if (saAt > -18) sun = 'Nearly full dark, with a faint glow in the sky.';
        else sun = n && n.dusk ? `Full dark. The Sun set at ${tm(n.set)} and it was fully dark by ${tm(n.dusk)}.` : 'Full dark. The Sun was well below the horizon.';
      } else if (!n) {
        sun = sunAlt(A, obs, at) > 0 ? 'The Sun didn\'t set that day (midnight sun season there).' : 'The Sun didn\'t rise that day (polar night there).';
      } else {
        sun = `The Sun set at ${tm(n.set)}${n.dusk ? ` and it was fully dark from ${tm(n.dusk)} to ${tm(n.dawn)}` : ', and the sky never got fully dark'}.`;
      }
      row('Sun', esc(sun));

      // Moon
      const mt = A.MakeTime(new Date(mid));
      const ill = A.Illumination('Moon', mt).phase_fraction, ang = A.MoonPhase(mt), waxing = ang < 180;
      let moon = `${phaseName(ang)}, ${Math.round(ill * 100)}% lit. `;
      if (known) {
        const mh = hor(A, obs, 'Moon', at);
        if (mh.altitude > 0 && mh.altitude < 3) moon += `It was right on the horizon in the ${compass(mh.azimuth)}, ${hor(A, obs, 'Moon', at + 6e5).altitude > mh.altitude ? 'just coming up' : 'about to set'}.`;
        else if (mh.altitude > 0) moon +=`It was up in the ${compass(mh.azimuth)}, ${height(mh.altitude)} (about ${Math.round(mh.altitude)}°).`;
        else {
          const r = tdate(A.SearchRiseSet('Moon', obs, +1, A.MakeTime(new Date(at)), 1));
          moon += `It was below the horizon${r ? ` and rose at ${tm(r)}` : ''}.`;
        }
      } else if (ok) {
        const a = n.dusk || n.set, b = n.dawn || n.rise, ups = [];
        for (let t = a; t <= b; t += 15 * 60000) ups.push(hor(A, obs, 'Moon', t).altitude > 0);
        const r = tdate(A.SearchRiseSet('Moon', obs, +1, A.MakeTime(new Date(n.set - 2 * H)), 1.2));
        const s = tdate(A.SearchRiseSet('Moon', obs, -1, A.MakeTime(new Date(n.set - 2 * H)), 1.2));
        if (ups.every(Boolean)) moon += 'It was up all night.';
        else if (!ups.some(Boolean)) moon += 'It wasn\'t up during the dark hours.';
        else if (ups[0]) moon += `It was up in the evening and set at ${tm(s)}.`;
        else moon += `It rose at ${tm(r)}.`;
      }
      row('Moon', moonSvg(ill, waxing, la < 0) + `<span>${esc(moon)}</span>`, 'cond-mrow');

      // Planets
      const seen = [];
      if (known) {
        if (!isDay) for (const b of PLANETS) { const p = planetUp(A, obs, b, at, saAt); if (p) seen.push({ b, ...p }); }
      } else if (ok) {
        const first = {};
        for (let t = n.set; t <= n.rise; t += 30 * 60000) {
          const sa = sunAlt(A, obs, t);
          for (const b of PLANETS) if (!first[b]) { const p = planetUp(A, obs, b, t, sa); if (p) first[b] = { b, t, ...p }; }
        }
        seen.push(...Object.values(first));
      }
      seen.sort((a, b) => a.mag - b.mag);
      let pl;
      if (isDay) pl = 'It was daylight, so the planets weren\'t easy to see.';
      else if (!seen.length) pl = known ? 'None of the bright planets were up.' : 'None of the bright planets were up during the dark hours.';
      else pl = seen.map((p) => {
        if (known) return `${p.b} was ${bright(p.mag)} in the ${compass(p.az)}, ${height(p.alt)}.`;
        const evening = p.t - (n.dusk || n.set) < 2 * H;
        return evening ? `${p.b} was ${bright(p.mag)} in the ${compass(p.az)} that evening.` : `${p.b} came up later, ${bright(p.mag)} in the ${compass(p.az)} from about ${tm(p.t)}.`;
      }).join(' ');
      row('Planets', esc(pl));

      // Meteor showers
      const on = showersOn(sh, ymd);
      const fmtPeak = (ms) => new Date(ms).toLocaleDateString(undefined, { month: 'long', day: 'numeric', timeZone: 'UTC' });
      const met = on.length ? on.map((s) => {
        const when = Math.abs(s.days) <= 1 ? 'at their peak' : s.days < 0 ? `building to their peak on ${fmtPeak(s.peak)}` : `past their ${fmtPeak(s.peak)} peak`;
        return `The ${s.n} were on, ${when} (up to about ${s.z} an hour from a dark spot).`;
      }).join(' ') : 'No major meteor shower was on. A few stray meteors an hour is normal on any dark night.';
      row('Meteors', esc(met));

      // Weather
      let w = '';
      if (wx) {
        if (known) {
          let best = null, bd = Infinity;
          for (const [t, v] of wx.hours) { const d = Math.abs(t - at); if (d < bd) { bd = d; best = v; } }
          if (best && bd <= 2 * H) {
            const bits = [];
            if (best.cloud != null) bits.push(`${cloudWord(best.cloud)} (${Math.round(best.cloud)}% cloud)`);
            if (best.temp != null) bits.push(temp(best.temp));
            if (best.wind != null) bits.push(`wind ${wind(best.wind)}`);
            if (best.rain != null) bits.push(best.rain > 0 ? `${best.rain} mm of rain or snow that hour` : 'no rain or snow');
            w = bits.join(', ') + '.';
          }
        } else {
          const a = ok ? n.set : localToUtc(ymd, '18:00', tz), b = ok ? n.rise : a + 12 * H;
          const hs = [...wx.hours].filter(([t]) => t >= a - H && t <= b).map(([, v]) => v);
          const nums = (k) => hs.map((v) => v[k]).filter((x) => x != null);
          const c = nums('cloud'), t = nums('temp'), wi = nums('wind'), r = nums('rain');
          if (hs.length) {
            const bits = [];
            if (c.length) { const avg = c.reduce((s, x) => s + x, 0) / c.length; bits.push(`${cloudWord(avg)} overnight (about ${Math.round(avg)}% cloud)`); }
            if (t.length) bits.push(`between ${temp(Math.min(...t))} and ${temp(Math.max(...t))}`);
            if (wi.length) bits.push(`wind up to ${wind(Math.max(...wi))}`);
            if (r.length) { const tot = Math.round(r.reduce((s, x) => s + x, 0) * 10) / 10; bits.push(tot > 0 ? `${tot} mm of rain or snow through the night` : 'no rain or snow'); }
            w = bits.join(', ') + '.';
          }
        }
      }
      row('Weather', esc(w || 'We couldn\'t get the weather for that date and place.'));

      // Times
      if (ok) {
        const mr = tdate(A.SearchRiseSet('Moon', obs, +1, A.MakeTime(new Date(n.set - 2 * H)), 1.2));
        const ms = tdate(A.SearchRiseSet('Moon', obs, -1, A.MakeTime(new Date(n.set - 2 * H)), 1.2));
        rows.push(`<div class="cond-row cond-times"><dt>Times</dt><dd><dl>`
          + [['Sunset', tm(n.set)], ['Fully dark', n.dusk ? tm(n.dusk) : 'not that night'], ['Dark until', n.dawn ? tm(n.dawn) : 'n/a'],
            ['Sunrise', tm(n.rise)], ['Moonrise', hor(A, obs, 'Moon', n.set).altitude > 0 ? 'up at sunset' : mr > n.rise ? 'not that night' : tm(mr)], ['Moonset', ms > n.rise ? 'not that night' : tm(ms)]].map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('')
          + '</dl></dd></div>');
      }

      const [yy, mo, dd] = ymd.split('-').map(Number);
      const dateTxt = new Date(Date.UTC(yy, mo - 1, dd, 12)).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
      const tzName = tz.startsWith('Etc/') ? 'rough local time' : tz.replace(/_/g, ' ');
      const forTxt = known ? `${dateTxt}, ${tm(at)}. Times in ${tzName}.` : `${dateTxt}. The time isn't known, so this covers the whole night. Times in ${tzName}.`;
      const notes = [];
      if (region === '1') notes.push('This report is only mapped to the region, so these conditions are approximate.');
      notes.push('This is what the sky and weather were doing there. It doesn\'t tell you what anyone saw.');
      if (wx) notes.push('Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo.com</a>.');
      if (known && isDay) { const h2 = el.querySelector('h2'); if (h2) h2.textContent = 'Conditions that day'; }
      const out = document.createElement('div');
      out.className = 'cond-out';
      out.innerHTML = `<p class="cond-for">${esc(forTxt)}</p><dl class="cond-list">${rows.join('')}</dl><p class="cond-notes">${notes.map((x) => x.includes('<a ') ? x : esc(x)).join(' ')}</p>`;
      el.querySelectorAll('.cond-wait').forEach((x) => x.remove());
      el.append(out);
      status.textContent = '';
    } catch (e) {
      status.textContent = 'Something went wrong working out the sky for this one.';
    }
  }

  const done = new WeakSet();
  const go = (el) => { if (!done.has(el)) { done.add(el); fill(el); } };
  const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
    for (const e of es) if (e.isIntersecting) { io.unobserve(e.target); go(e.target); }
  }, { rootMargin: '200px 0px' }) : null;
  const watch = (el) => { if (io) io.observe(el); else go(el); };
  window.eaCond = { watch };
  document.querySelectorAll('[data-cond]').forEach(watch);
})();

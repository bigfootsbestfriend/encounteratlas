// "Was it a planet?" for the report form: which bright things were up at a time and place, with no direction
// given (the standalone checker, skycheck.js, also matches the direction and height people pick). Loads
// astronomy-engine and satellite.js only when a UFO report is about to be sent.
//   eaSky.lined(date, lat, lon) -> [{ name, why, where }] brightest first ([] if nothing, or the libraries won't load)
(() => {
  const LIBS = ['https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/astronomy.browser.min.js',
    'https://cdn.jsdelivr.net/npm/satellite.js@6.0.2/dist/satellite.min.js'];
  const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
  const compass = (az) => COMPASS[Math.round(((az % 360) + 360) % 360 / 45) % 8];
  const height = (alt) => (alt < 15 ? 'low on the horizon' : alt < 40 ? 'part way up' : alt < 70 ? 'high up' : 'nearly overhead');
  const WHY = {
    Venus: 'Venus is the classic UFO: dazzling, steady and white, and it seems to follow your car.',
    Jupiter: 'Jupiter is bright, steady and cream-coloured. It barely moves over a few minutes.',
    Mars: 'Mars looks like a steady orange-red star.',
    Saturn: 'Saturn looks like a steady, yellowish star.',
    Moon: 'A low, orange or cloud-covered Moon can look very strange.',
    ISS: 'The Space Station looks like a bright, steady light crossing the sky in a few minutes, with no blinking.',
  };
  let loading = null;
  const script = (src) => new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = src; s.async = true; s.onload = res; s.onerror = rej;
    document.head.append(s);
  });
  const load = () => loading || (loading = Promise.all(LIBS.map((u, i) => (i === 0 ? window.Astronomy : window.satellite) ? null : script(u).catch(() => null))));

  async function iss(date, lat, lon) {
    if (!window.satellite || Math.abs(date - Date.now()) > 14 * 864e5) return null; // old orbits are too far off
    try {
      const t = await fetch('https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE').then((r) => r.text());
      const [, l1, l2] = t.trim().split('\n').map((s) => s.trim());
      const rec = satellite.twoline2satrec(l1, l2);
      const gd = { latitude: satellite.degreesToRadians(lat), longitude: satellite.degreesToRadians(lon), height: 0.1 };
      let best = null;
      for (let m = -20; m <= 20; m++) {
        const d = new Date(date.getTime() + m * 60000), pv = satellite.propagate(rec, d);
        if (!pv.position) continue;
        const look = satellite.ecfToLookAngles(gd, satellite.eciToEcf(pv.position, satellite.gstime(d)));
        const el = look.elevation * 180 / Math.PI;
        if (el > 10 && (!best || el > best.alt)) best = { alt: el, az: look.azimuth * 180 / Math.PI, min: m };
      }
      return best;
    } catch (e) { return null; }
  }

  async function lined(date, lat, lon) {
    await load();
    const A = window.Astronomy;
    if (!A || isNaN(date)) return [];
    const obs = new A.Observer(lat, lon, 0), t = A.MakeTime(date);
    const hor = (b) => { const eq = A.Equator(b, t, obs, true, true); return A.Horizon(t, obs, eq.ra, eq.dec, 'normal'); };
    const sunAlt = hor('Sun').altitude;
    const out = [];
    const moon = hor('Moon');
    if (moon.altitude > 0) out.push({ name: 'The Moon', why: WHY.Moon, alt: moon.altitude, az: moon.azimuth, mag: -10 });
    for (const b of ['Venus', 'Jupiter', 'Mars', 'Saturn']) {
      const h = hor(b), mag = A.Illumination(b, t).mag;
      // Venus shows in twilight; the others need a darker sky and must be bright enough to catch the eye.
      if (h.altitude > 3 && (b === 'Venus' ? sunAlt < 0 : sunAlt < -6 && mag < 0.6)) out.push({ name: b, why: WHY[b], alt: h.altitude, az: h.azimuth, mag });
    }
    if (sunAlt < -4) {
      const st = await iss(date, lat, lon);
      if (st) out.push({ name: 'The International Space Station', why: WHY.ISS, alt: st.alt, az: st.az, mag: -3 });
    }
    return out.sort((a, b) => a.mag - b.mag).map((x) => ({ name: x.name, why: x.why, where: `${compass(x.az)}, ${height(x.alt)}` }));
  }
  window.eaSky = { lined, load };
})();

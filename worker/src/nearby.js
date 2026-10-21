// GET /v1/reports/nearby: approved reports around a point, for the field app's "near me" map.
// Only ever reads the public point (pub_lat/pub_lon, a ~5 km grid cell, ~100 km for living traditions),
// rounds it to 0.01 deg and filters on that rounded point, so moving the search circle can't reveal
// anything finer than what the site already shows. Never returns the exact point, videos or photo links.
import { CREATURES, UFO } from './creatures.js';
import { fail, json, hash, clientIp, rateLimited, b64, unb64, enc } from './util.js';
import { LIVING_TRADITIONS, fuzz } from './index.js';

const R_KM = 6371.0088;
const CATEGORIES = ['ufo', 'creature', 'other'];
const BATCH = 200;
const MAX_SCAN = 2000; // rows read per request at most; the cursor carries on from there

const round2 = (x) => Math.round(x * 100) / 100;

export function haversineKm(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const dlat = (lat2 - lat1) * rad, dlon = (lon2 - lon1) * rad;
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dlon / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

// Bounding box around (lat, lon). Longitude comes back as one or two ranges: two when the box
// crosses the antimeridian, one full range near a pole.
export function bbox(lat, lon, km) {
  const dlat = (km / R_KM) * (180 / Math.PI) + 0.02; // + rounding slack
  const latMin = Math.max(-90, lat - dlat), latMax = Math.min(90, lat + dlat);
  if (latMax >= 90 || latMin <= -90) return { latMin, latMax, lons: [[-180, 180]] };
  const dlon = Math.asin(Math.min(1, Math.sin(km / R_KM) / Math.cos((lat * Math.PI) / 180))) * (180 / Math.PI) + 0.02;
  if (dlon >= 180) return { latMin, latMax, lons: [[-180, 180]] };
  const lo = lon - dlon, hi = lon + dlon;
  if (lo < -180) return { latMin, latMax, lons: [[lo + 360, 180], [-180, hi]] };
  if (hi > 180) return { latMin, latMax, lons: [[lo, 180], [-180, hi - 360]] };
  return { latMin, latMax, lons: [[lo, hi]] };
}

// The point we publish for a row: its public cell centre (re-snapped to the region grid for living
// traditions, in case an old row predates that rule), rounded to 0.01 deg.
export function publicPoint(r) {
  const region = LIVING_TRADITIONS.has(r.creature);
  const [la, lo] = region ? fuzz(r.pub_lat, r.pub_lon, true) : [r.pub_lat, r.pub_lon];
  return { lat: round2(la), lon: round2(lo), precision_km: region ? 100 : 5 };
}

export function summary(t, max = 280) {
  t = String(t || '').replace(/\s+/g, ' ').trim();
  if (t.length <= max) return t;
  return t.slice(0, max - 1).replace(/\s+\S*$/, '') + '…';
}

export const category = (slug) => (slug === 'other' ? 'other' : UFO.includes(slug) ? 'ufo' : 'creature');

function num(url, name, dflt, min, max, fields, integer = false) {
  const raw = url.searchParams.get(name);
  if (raw === null || raw === '') {
    if (dflt === undefined) { fields[name] = 'required'; return NaN; }
    return dflt;
  }
  const v = Number(raw);
  if (!Number.isFinite(v) || v < min || v > max || (integer && !Number.isInteger(v))) fields[name] = `${min} to ${max}`;
  return v;
}

export function parseParams(url) {
  const f = {};
  const q = {
    lat: num(url, 'lat', undefined, -90, 90, f),
    lng: num(url, 'lng', undefined, -180, 180, f),
    radius_km: num(url, 'radius_km', 50, 5, 250, f),
    days: num(url, 'days', 30, 1, 365, f, true),
    limit: num(url, 'limit', 50, 1, 100, f, true),
    category: url.searchParams.get('category') || '',
    cursor: null,
  };
  if (q.category && !CATEGORIES.includes(q.category)) f.category = CATEGORIES.join(' | ');
  const c = url.searchParams.get('cursor');
  if (c) {
    try {
      const [d, pid] = new TextDecoder().decode(unb64(c)).split('|');
      if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || !/^[a-z0-9]{10}$/.test(pid)) throw 0;
      q.cursor = { d, pid };
    } catch { f.cursor = 'invalid'; }
  }
  if (Object.keys(f).length) fail(400, 'invalid', { fields: f });
  return q;
}

const encodeCursor = (r) => b64(enc.encode(`${r.seen_date}|${r.pid}`));

export async function nearby(req, env, url, ctx) {
  const q = parseParams(url);
  const iph = await hash(env, clientIp(req, env));
  if (await rateLimited(env, [[`nearby|ip|${iph}`, 60, 60]])) {
    fail(429, 'slow', { retry_after: 60 });
  }

  // Cache on the validated, normalised query so ?lat=1.0 and ?lat=1 share an entry.
  const key = new URL('https://cache.encounteratlas.internal/v1/reports/nearby');
  for (const k of ['lat', 'lng', 'radius_km', 'days', 'limit', 'category']) key.searchParams.set(k, String(q[k]));
  if (q.cursor) key.searchParams.set('cursor', url.searchParams.get('cursor'));
  const cache = typeof caches !== 'undefined' ? caches.default : null;
  const hit = cache && (await cache.match(key.toString()));
  if (hit) {
    const res = new Response(hit.body, hit);
    res.headers.set('x-cache', 'hit');
    return res;
  }

  const since = new Date(Date.now() - q.days * 86400e3).toISOString().slice(0, 10);
  const box = bbox(q.lat, q.lng, q.radius_km);
  const where = ["status = 'approved'", 'seen_date >= ?1', 'pub_lat BETWEEN ?2 AND ?3'];
  const args = [since, box.latMin, box.latMax];
  const lonParts = box.lons.map(([a, b]) => {
    args.push(a, b);
    return `pub_lon BETWEEN ?${args.length - 1} AND ?${args.length}`;
  });
  where.push(`(${lonParts.join(' OR ')})`);
  if (q.category === 'other') where.push("creature = 'other'");
  else if (q.category) {
    args.push(JSON.stringify(UFO));
    const inUfo = `creature IN (SELECT value FROM json_each(?${args.length}))`;
    where.push(q.category === 'ufo' ? inUfo : `creature <> 'other' AND NOT ${inUfo}`);
  }

  const out = [];
  let after = q.cursor, scanned = 0, last = null, exhausted = false;
  while (out.length <= q.limit && scanned < MAX_SCAN) {
    const w = [...where], a = [...args];
    if (after) {
      a.push(after.d, after.pid);
      w.push(`(seen_date < ?${a.length - 1} OR (seen_date = ?${a.length - 1} AND pid < ?${a.length}))`);
    }
    const rows = (await env.DB.prepare(
      `SELECT pid, creature, other_what, seen_date, date_approx, place, pub_lat, pub_lon, story, witnesses
       FROM reports WHERE ${w.join(' AND ')} ORDER BY seen_date DESC, pid DESC LIMIT ${BATCH}`,
    ).bind(...a).all()).results;
    scanned += rows.length;
    for (const r of rows) {
      last = r;
      const pt = publicPoint(r);
      const km = haversineKm(q.lat, q.lng, pt.lat, pt.lon);
      if (km > q.radius_km) continue;
      out.push({ r, pt, km });
      if (out.length > q.limit) break;
    }
    if (rows.length < BATCH) { exhausted = out.length <= q.limit; break; }
    after = { d: last.seen_date, pid: last.pid };
  }

  const more = out.length > q.limit;
  const page = out.slice(0, q.limit);
  // Next page starts after the last row returned; if we stopped on the scan cap, after the last row read.
  const next = more ? encodeCursor(page[page.length - 1].r) : !exhausted && last ? encodeCursor(last) : null;
  const site = String(env.SITE || 'https://encounteratlas.com').replace(/\/$/, '');
  const reports = page.map(({ r, pt, km }) => ({
    id: r.pid,
    url: `${site}/reports/?id=${r.pid}`,
    category: category(r.creature),
    creature: r.creature,
    creature_name: r.creature === 'other' ? r.other_what : CREATURES[r.creature] || '',
    seen_date: r.seen_date,
    date_approx: !!r.date_approx,
    place: r.place,
    lat: pt.lat,
    lng: pt.lon,
    precision_km: pt.precision_km,
    distance_km: Math.round(km),
    summary: summary(r.story),
    witnesses: r.witnesses,
  }));
  const res = json({
    query: { lat: q.lat, lng: q.lng, radius_km: q.radius_km, days: q.days, category: q.category || null, limit: q.limit },
    count: reports.length, reports, next_cursor: next,
  }, 200, { 'cache-control': 'public, max-age=60', 'x-cache': 'miss' });
  if (cache) ctx.waitUntil(cache.put(key.toString(), res.clone()));
  return res;
}

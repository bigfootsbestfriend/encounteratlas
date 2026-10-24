// Witness clusters ("a flap in progress"): several approved reader reports close together in a short time.
// Rule: CLUSTER_MIN (3) or more approved reports whose public points sit within CLUSTER_KM (50 km) of the cluster's
// seed report, all seen in the last WINDOW_DAYS (3 days, i.e. 72 hours; seen_date is the witness's local date, so
// the window is counted in whole UTC dates).
//
//   GET /v1/clusters?lat&lng&radius_km   active clusters whose centre is within radius_km (5 to 500, default 150)
//
// Same privacy rules as /v1/reports/nearby: only the public point is read (the ~5 km cell, ~100 km for living
// traditions), the centre is rounded to 0.1 deg (0.9 deg region grid when a living tradition is in the cluster),
// no story text, no links, no ids. Living-tradition creatures are never named, only counted as "creature".
// Same 60 s cache and 60-a-minute-per-IP limit style as nearby.js.
import { CREATURES } from './creatures.js';
import { fail, json, hash, clientIp, rateLimited } from './util.js';
import { LIVING_TRADITIONS, fuzz } from './index.js';
import { haversineKm, bbox, publicPoint, category } from './nearby.js';
import { publicPlace } from './place.js';

export const CLUSTER_MIN = 3;
export const CLUSTER_KM = 50;
export const WINDOW_DAYS = 3;

const round1 = (x) => Math.round(x * 10) / 10;
export const sinceDate = (days = WINDOW_DAYS, t = Date.now()) => new Date(t - days * 86400e3).toISOString().slice(0, 10);

// Short place for a headline: "Near Wakefield, Quebec" -> "Wakefield, Quebec"; never an address, max 48 characters.
export function shortPlace(place) {
  let p = publicPlace(place).replace(/^\s*(near|outside|around|by)\s+/i, '').trim();
  if (!p || p === 'Approximate area') return '';
  if (p.length > 48) p = p.slice(0, 48).replace(/[,\s]+\S*$/, '');
  return p;
}

// Greedy clustering on public points. rows need creature, pub_lat, pub_lon, seen_date, place.
// The report with the most neighbours within CLUSTER_KM seeds a cluster, takes those neighbours, and so on
// while a seed still has CLUSTER_MIN or more. Small inputs (a few days of reports in one area), so O(n^2) is fine.
export function findClusters(rows, opts) {
  return findClustersWithMembers(rows, opts).map((c) => c.cluster)
    .sort((a, b) => b.count - a.count || b.last_seen.localeCompare(a.last_seen));
}

function describe(members) {
  const region = members.some(({ r }) => LIVING_TRADITIONS.has(r.creature));
  let lat = 0, x = 0, y = 0;
  for (const { pt } of members) {
    lat += pt.lat;
    x += Math.cos((pt.lon * Math.PI) / 180);
    y += Math.sin((pt.lon * Math.PI) / 180);
  }
  lat /= members.length;
  const lon = (Math.atan2(y, x) * 180) / Math.PI; // circular mean, safe across the antimeridian
  const [clat, clon] = region ? fuzz(lat, lon, true) : [lat, lon];
  const dates = members.map(({ r }) => r.seen_date).sort();
  const categories = { ufo: 0, creature: 0, other: 0 };
  const names = new Map();
  for (const { r } of members) {
    categories[category(r.creature)]++;
    if (LIVING_TRADITIONS.has(r.creature) || r.creature === 'other') continue;
    const n = CREATURES[r.creature];
    if (n) names.set(n, (names.get(n) || 0) + 1);
  }
  // A place label from a member that isn't a living tradition (theirs could narrow the region down).
  const places = new Map();
  if (!region) {
    for (const { r } of members) {
      const p = shortPlace(r.place);
      if (p) places.set(p, (places.get(p) || 0) + 1);
    }
  }
  const top = (m) => [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return {
    lat: round1(clat), lng: round1(clon),
    precision_km: region ? 100 : 10,
    count: members.length,
    first_seen: dates[0], last_seen: dates[dates.length - 1],
    categories,
    creatures: top(names).slice(0, 5).map(([name, n]) => ({ name, count: n })),
    place: region ? '' : (top(places)[0] || [''])[0],
  };
}

// Approved reports seen in the window within `km` of a point (public points only).
export async function recentNear(env, lat, lng, km, since = sinceDate()) {
  const box = bbox(lat, lng, km);
  const where = ["status = 'approved'", 'seen_date >= ?1', 'pub_lat BETWEEN ?2 AND ?3'];
  const args = [since, box.latMin, box.latMax];
  const lonParts = box.lons.map(([a, b]) => {
    args.push(a, b);
    return `pub_lon BETWEEN ?${args.length - 1} AND ?${args.length}`;
  });
  where.push(`(${lonParts.join(' OR ')})`);
  const rows = (await env.DB.prepare(
    `SELECT pid, creature, seen_date, place, pub_lat, pub_lon FROM reports WHERE ${where.join(' AND ')}
     ORDER BY seen_date DESC, pid DESC LIMIT 2000`,
  ).bind(...args).all()).results;
  return rows.filter((r) => { const pt = publicPoint(r); return haversineKm(lat, lng, pt.lat, pt.lon) <= km; });
}

// The cluster an approved report belongs to right now (for the push alert), or null.
export async function clusterFor(env, r) {
  if (!r || r.seen_date < sinceDate()) return null;
  const pt = publicPoint(r);
  // Everything within 2 x CLUSTER_KM can end up in the same cluster as this report.
  const rows = await recentNear(env, pt.lat, pt.lon, CLUSTER_KM * 2);
  if (!rows.some((x) => x.pid === r.pid)) rows.push(r);
  for (const c of findClustersWithMembers(rows)) if (c.pids.has(r.pid)) return c.cluster;
  return null;
}

// Keeps which pids went into each cluster (server side only, never returned).
export function findClustersWithMembers(rows, opts) {
  const out = [];
  const pts = rows.map((r) => ({ r, pt: publicPoint(r) }));
  const left = new Set(pts.keys());
  const { min = CLUSTER_MIN, km = CLUSTER_KM } = opts || {};
  for (;;) {
    let best = null;
    for (const i of left) {
      const nb = [...left].filter((j) => haversineKm(pts[i].pt.lat, pts[i].pt.lon, pts[j].pt.lat, pts[j].pt.lon) <= km);
      if (!best || nb.length > best.nb.length) best = { i, nb };
    }
    if (!best || best.nb.length < min) break;
    best.nb.forEach((j) => left.delete(j));
    out.push({ cluster: describe(best.nb.map((j) => pts[j])), pids: new Set(best.nb.map((j) => pts[j].r.pid)) });
  }
  return out;
}

function num(url, name, dflt, min, max, fields) {
  const raw = url.searchParams.get(name);
  if (raw === null || raw === '') {
    if (dflt === undefined) { fields[name] = 'required'; return NaN; }
    return dflt;
  }
  const v = Number(raw);
  if (!Number.isFinite(v) || v < min || v > max) fields[name] = `${min} to ${max}`;
  return v;
}

export async function clusters(req, env, url, ctx) {
  const f = {};
  // Rounded to 0.01 deg like everything else the app sends, so the cache key can't pin anyone down either.
  const q = {
    lat: Math.round(num(url, 'lat', undefined, -90, 90, f) * 100) / 100,
    lng: Math.round(num(url, 'lng', undefined, -180, 180, f) * 100) / 100,
    radius_km: Math.round(num(url, 'radius_km', 150, 5, 500, f)),
  };
  if (Object.keys(f).length) fail(400, 'invalid', { fields: f });
  const iph = await hash(env, clientIp(req, env));
  if (await rateLimited(env, [[`clusters|ip|${iph}`, 60, 60]])) fail(429, 'slow', { retry_after: 60 });

  const key = new URL('https://cache.encounteratlas.internal/v1/clusters');
  for (const k of ['lat', 'lng', 'radius_km']) key.searchParams.set(k, String(q[k]));
  const cache = typeof caches !== 'undefined' ? caches.default : null;
  const hit = cache && (await cache.match(key.toString()));
  if (hit) {
    const res = new Response(hit.body, hit);
    res.headers.set('x-cache', 'hit');
    return res;
  }

  // A cluster centred inside the circle can draw on reports up to CLUSTER_KM beyond it.
  const rows = await recentNear(env, q.lat, q.lng, q.radius_km + CLUSTER_KM);
  const found = findClusters(rows)
    .map((c) => ({ ...c, distance_km: Math.round(haversineKm(q.lat, q.lng, c.lat, c.lng)) }))
    .filter((c) => c.distance_km <= q.radius_km)
    .sort((a, b) => a.distance_km - b.distance_km);
  const res = json({
    query: q,
    rule: { min_reports: CLUSTER_MIN, within_km: CLUSTER_KM, window_days: WINDOW_DAYS },
    count: found.length, clusters: found,
  }, 200, { 'cache-control': 'public, max-age=60', 'x-cache': 'miss' });
  if (cache) ctx.waitUntil(cache.put(key.toString(), res.clone()));
  return res;
}

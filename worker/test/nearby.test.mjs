// /v1/reports/nearby against the local Worker started by test/run.sh (runs after api.test.mjs, same database).
// Filters (radius, days, category), approved-only, newest first, cursor paging, the antimeridian, privacy
// (public cell rounded to 0.01 deg, living traditions at ~100 km, no links/videos), CORS, cache, rate limit.
import { bbox, haversineKm, summary } from '../src/nearby.js';

const API = process.env.API || 'http://127.0.0.1:8788';
const SITE = 'http://127.0.0.1:8825';
let pass = 0, failed = 0;
const ok = (cond, name, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); } else { failed++; console.log(`  FAIL ${name} ${extra}`); }
};
const section = (s) => console.log(`\n${s}`);
let ipN = 0;
const freshIp = () => `10.${(ipN >> 8) + 120}.${ipN++ & 255}.9`;

async function call(path, { ip = freshIp(), origin = SITE } = {}) {
  const res = await fetch(API + path, { headers: { origin, 'x-test-ip': ip } });
  return { status: res.status, data: await res.json().catch(() => null), headers: res.headers };
}
const near = (q, opts) => call('/v1/reports/nearby?' + new URLSearchParams(q), opts);

section('Geometry (unit)');
ok(Math.abs(haversineKm(45.42, -75.7, 51.05, -114.07) - 2900) < 60, 'haversine Ottawa to Calgary is about 2,900 km');
ok(haversineKm(-17.75, 179.98, -17.75, -179.98) < 5, 'haversine across the antimeridian is short');
let b = bbox(-17.75, 179.9, 50);
ok(b.lons.length === 2 && b.lons[0][1] === 180 && b.lons[1][0] === -180, 'bbox east of 179 splits into two longitude ranges', JSON.stringify(b));
b = bbox(-17.75, -179.9, 50);
ok(b.lons.length === 2, 'bbox west of -179 splits too', JSON.stringify(b));
b = bbox(89.8, 10, 50);
ok(b.lons.length === 1 && b.lons[0][0] === -180 && b.lons[0][1] === 180, 'bbox near the pole covers every longitude');
ok(summary('word '.repeat(200)).length <= 280 && summary('short') === 'short', 'summary capped at 280 characters');

section('Setup: reports around Wakefield QC, one in Fiji, one in Calgary');
const login = await fetch(API + '/mod/login', { method: 'POST', headers: { origin: API, 'x-test-ip': '10.250.0.2' },
  body: new URLSearchParams({ password: 'letmein-local' }), redirect: 'manual' });
const COOKIE = (login.headers.get('set-cookie') || '').split(';')[0];
const day = (n) => new Date(Date.now() - n * 86400e3).toISOString().slice(0, 10);
const LONG = 'A tall dark shape crossed the trail about forty metres ahead of us and stepped over a fallen log without slowing down. '.repeat(6);
const base = { seen_time: '', loc_source: 'map', duration: '', sounds: '', smells: '', witnesses: 1, display_name: '', anonymous: true,
  videos: ['https://youtu.be/dQw4w9WgXcQ'], links: ['https://example.com/photo-of-it.jpg'], turnstile: 'XXXX.DUMMY.TOKEN',
  story: 'Something moved along the treeline at dusk and we watched it for a minute before it was gone.' };
async function report(fields, approve = true) {
  const f = new FormData();
  f.append('data', JSON.stringify({ ...base, ...fields }));
  const r = await fetch(API + '/api/reports', { method: 'POST', headers: { origin: SITE, 'x-test-ip': freshIp() }, body: f });
  const d = await r.json();
  if (!d.id) throw new Error('submit failed: ' + JSON.stringify(d));
  if (approve) {
    await fetch(API + '/mod/action', { method: 'POST', headers: { origin: API, cookie: COOKIE, accept: 'application/json' },
      body: new URLSearchParams({ act: 'approve', id: d.id }) });
  }
  return d.id;
}
const EX = { lat: 45.42153, lon: -75.69719 };
const A = await report({ creature: 'bigfoot', seen_date: day(3), lat: EX.lat, lon: EX.lon, place: 'Near Wakefield, Quebec', story: LONG });
const B = await report({ creature: 'ufo-orbs', seen_date: day(10), lat: 45.401, lon: -75.703, place: 'Ottawa' });
const C = await report({ creature: 'other', other_what: 'Glowing deer', seen_date: day(5), lat: 45.46, lon: -75.64, place: 'Chelsea' });
const D = await report({ creature: 'bigfoot', seen_date: day(60), lat: EX.lat, lon: EX.lon, place: 'Old one' });
const E = await report({ creature: 'wendigo', seen_date: day(2), lat: EX.lat, lon: EX.lon, place: 'Gatineau Park' });
const F = await report({ creature: 'ufo-saucer', seen_date: day(1), lat: -17.75, lon: 179.98, place: 'Off Fiji' });
const G = await report({ creature: 'bigfoot', seen_date: day(1), lat: EX.lat, lon: EX.lon, place: 'Pending one' }, false);
const H = await report({ creature: 'bigfoot', seen_date: day(1), lat: 51.05, lon: -114.07, place: 'Calgary' });
ok(true, '8 reports filed (7 approved, 1 pending)');
// api.test.mjs ran first on the same database and left approved Wakefield reports: compare only ours.
const MINE = new Set([A, B, C, D, E, F, G, H]);
const mine = (list) => list.map((x) => x.id).filter((id) => MINE.has(id));

section('Validation');
let r = await near({ lng: -75.7 });
ok(r.status === 400 && r.data.fields.lat === 'required', 'lat is required');
r = await near({ lat: 45.4, lng: -75.7, radius_km: 300 });
ok(r.status === 400 && r.data.fields.radius_km, 'radius over 250 refused');
r = await near({ lat: 45.4, lng: -75.7, radius_km: 2 });
ok(r.status === 400 && r.data.fields.radius_km, 'radius under 5 refused');
r = await near({ lat: 45.4, lng: -75.7, days: 0 });
ok(r.status === 400 && r.data.fields.days, 'days under 1 refused');
r = await near({ lat: 45.4, lng: -75.7, limit: 101 });
ok(r.status === 400 && r.data.fields.limit, 'limit over 100 refused');
r = await near({ lat: 45.4, lng: -75.7, category: 'bigfoot' });
ok(r.status === 400 && r.data.fields.category, 'unknown category refused');
r = await near({ lat: 45.4, lng: -75.7, cursor: 'not-a-cursor' });
ok(r.status === 400 && r.data.fields.cursor, 'bad cursor refused');

section('Results');
r = await near({ lat: EX.lat, lng: EX.lon, radius_km: 100 });
let ids = mine(r.data.reports);
ok(r.status === 200 && JSON.stringify(ids) === JSON.stringify([E, A, C, B]), 'approved reports in radius and last 30 days, newest sighting first',
  JSON.stringify(r.data.reports.map((x) => [x.place, x.seen_date])));
ok(!ids.includes(G), 'pending report never returned');
ok(!ids.includes(D) && !ids.includes(H) && !ids.includes(F), 'old, far and other-hemisphere reports left out');
r = await near({ lat: EX.lat, lng: EX.lon });
ok(r.status === 200 && r.data.query.radius_km === 50 && r.data.query.days === 30 && r.data.query.limit === 50, 'defaults: 50 km, 30 days, 50 results');
ok(!r.data.reports.some((x) => x.id === E), 'living-tradition report sits at its ~100 km cell centre, outside a 50 km circle here');
r = await near({ lat: EX.lat, lng: EX.lon, radius_km: 100, days: 365 });
ok(r.data.reports.some((x) => x.id === D), 'days=365 brings back the 60-day-old report');

section('Privacy');
r = await near({ lat: EX.lat, lng: EX.lon, radius_km: 100 });
const ra = r.data.reports.find((x) => x.id === A), re = r.data.reports.find((x) => x.id === E);
const twoDp = (v) => Math.abs(v * 100 - Math.round(v * 100)) < 1e-6;
ok(r.data.reports.every((x) => twoDp(x.lat) && twoDp(x.lng)), 'every point rounded to 0.01 degrees');
ok(ra.lat !== Math.round(EX.lat * 100) / 100 || ra.lng !== Math.round(EX.lon * 100) / 100, 'point is the public 5 km cell, not the rounded exact point',
  JSON.stringify([ra.lat, ra.lng]));
ok(ra.precision_km === 5 && re.precision_km === 100, 'precision_km 5, and 100 for living traditions');
const rlat = Math.round(Math.round(Math.round(EX.lat / 0.9) * 0.9 * 1e4) / 1e4 * 100) / 100;
ok(re.lat === rlat, 'wendigo at the ~100 km cell centre', JSON.stringify([re.lat, rlat]));
const keys = new Set(r.data.reports.flatMap((x) => Object.keys(x)));
ok(!['links', 'videos', 'photos', 'exact', 'story', 'pub_lat', 'name', 'display_name'].some((k) => keys.has(k)), 'no links, videos, story text or names', [...keys].join(','));
ok(!JSON.stringify(r.data).includes('example.com') && !JSON.stringify(r.data).includes('youtu'), 'submitted links never appear anywhere in the response');
ok(ra.summary.length <= 280 && ra.summary.endsWith('…'), 'long story cut to a 280-character summary');
ok(ra.url.endsWith(`/reports/${A}/`) && ra.category === 'creature' && ra.creature_name === 'Bigfoot', 'url, category and name');

section('Category');
const cat = async (c) => mine((await near({ lat: EX.lat, lng: EX.lon, radius_km: 100, category: c, limit: 100 })).data.reports);
ok(JSON.stringify(await cat('ufo')) === JSON.stringify([B]), 'ufo');
ok(JSON.stringify(await cat('creature')) === JSON.stringify([E, A]), 'creature');
ok(JSON.stringify(await cat('other')) === JSON.stringify([C]), 'other');

section('Cursor paging');
const all = (await near({ lat: EX.lat, lng: EX.lon, radius_km: 100, limit: 100 })).data.reports.map((x) => x.id);
const pages = [];
let cur = null, n = 0;
do {
  const p = await near({ lat: EX.lat, lng: EX.lon, radius_km: 100, limit: 2, ...(cur ? { cursor: cur } : {}) });
  ok(p.data.count <= 2, `page ${++n} has at most 2`);
  pages.push(...p.data.reports.map((x) => x.id));
  cur = p.data.next_cursor;
} while (cur && n < 20);
ok(all.length > 2 && JSON.stringify(pages) === JSON.stringify(all) && cur === null, 'pages of 2 add up to the full list, no overlap, then end',
  `${pages.length} vs ${all.length}`);

section('Antimeridian');
r = await near({ lat: -17.75, lng: -179.95, radius_km: 50 });
ok(r.data.reports.some((x) => x.id === F), 'report at 179.98 E found from 179.95 W');
r = await near({ lat: -17.75, lng: 179.9, radius_km: 50 });
ok(r.data.reports.some((x) => x.id === F), 'and from 179.9 E');

section('CORS and cache');
r = await near({ lat: 10, lng: 10 });
ok(r.headers.get('access-control-allow-origin') === SITE, 'site origin allowed');
r = await near({ lat: 10, lng: 10 }, { origin: 'https://evil.example' });
ok(!r.headers.get('access-control-allow-origin'), 'other origins get no CORS header');
const q = { lat: 45.4, lng: -75.6, radius_km: 77 };
const c1 = await near(q), c2 = await near(q);
ok(c1.headers.get('x-cache') === 'miss' && c2.headers.get('x-cache') === 'hit' && /max-age=60/.test(c2.headers.get('cache-control')),
  '60 s cache: second identical call is a hit', `${c1.headers.get('x-cache')} ${c2.headers.get('x-cache')}`);

section('Rate limit (60 a minute per IP)');
let last;
for (let i = 0; i < 61; i++) last = await near({ lat: 1, lng: i }, { ip: '10.199.0.1' });
ok(last.status === 429 && last.data.state === 'slow', '61st request in a minute refused', String(last.status));
r = await near({ lat: 1, lng: 1 }, { ip: '10.199.0.2' });
ok(r.status === 200, 'another IP is unaffected');

console.log(`\n${pass} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

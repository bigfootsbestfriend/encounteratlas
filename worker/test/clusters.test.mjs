// Witness clusters ("flap in progress"): /v1/clusters and the cluster wording on approval alerts, against the local
// Worker started by test/run.sh (runs after the other suites, same database, PUSH_MODE=log). Areas used here
// (Point Pleasant WV, Edmonton, Thunder Bay, Fiji) are not used by the other suites.
import { readFileSync } from 'node:fs';
import { findClusters, shortPlace, sinceDate } from '../src/clusters.js';

const API = process.env.API || 'http://127.0.0.1:8788';
const LOG = process.env.LOG;
const SITE = 'http://127.0.0.1:8825';
let pass = 0, failed = 0;
const ok = (cond, name, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); } else { failed++; console.log(`  FAIL ${name} ${extra}`); }
};
const section = (s) => console.log(`\n${s}`);
let ipN = 0;
const freshIp = () => `10.${(ipN >> 8) + 200}.${ipN++ & 255}.5`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const day = (n) => new Date(Date.now() - n * 86400e3).toISOString().slice(0, 10);

section('Clustering (unit)');
const row = (pid, creature, lat, lon, d = day(0), place = 'Point Pleasant, West Virginia') => ({ pid, creature, pub_lat: lat, pub_lon: lon, seen_date: d, place });
let cs = findClusters([row('a', 'mothman', 38.84, -82.14), row('b', 'mothman', 38.9, -82.1), row('c', 'ufo-orbs', 38.7, -82.2, day(2))]);
ok(cs.length === 1 && cs[0].count === 3, 'three reports within 50 km make one cluster', JSON.stringify(cs));
ok(cs[0].first_seen === day(2) && cs[0].last_seen === day(0), 'first and last sighting dates');
ok(cs[0].categories.creature === 2 && cs[0].categories.ufo === 1 && cs[0].categories.other === 0, 'category counts');
ok(cs[0].creatures[0].name === 'Mothman' && cs[0].creatures[0].count === 2, 'creature names counted');
ok(cs[0].place === 'Point Pleasant, West Virginia' && cs[0].precision_km === 10, 'place label and 10 km precision');
ok(Math.abs(cs[0].lat * 10 - Math.round(cs[0].lat * 10)) < 1e-9 && Math.abs(cs[0].lng * 10 - Math.round(cs[0].lng * 10)) < 1e-9, 'centre rounded to 0.1 deg');
ok(findClusters([row('a', 'mothman', 38.84, -82.14), row('b', 'mothman', 38.9, -82.1)]).length === 0, 'two reports are not a cluster');
ok(findClusters([row('a', 'bigfoot', 53.55, -113.49), row('b', 'bigfoot', 53.55, -113.49), row('c', 'bigfoot', 54.6, -113.49)]).length === 0, 'third report 115 km away: no cluster');
cs = findClusters([row('a', 'wendigo', 48.38, -89.25, day(0), 'Secret Lake Road 12'), row('b', 'bigfoot', 48.4, -89.3), row('c', 'bigfoot', 48.45, -89.2)]);
ok(cs.length === 1 && cs[0].precision_km === 100 && cs[0].place === '', 'living tradition in it: region precision, no place label', JSON.stringify(cs));
ok(!JSON.stringify(cs).includes('Wendigo') && cs[0].creatures.every((c) => c.name !== 'Wendigo'), 'living tradition never named');
cs = findClusters([row('a', 'ufo-orbs', -17.75, 179.98), row('b', 'ufo-orbs', -17.76, -179.99), row('c', 'ufo-orbs', -17.7, 179.9)]);
ok(cs.length === 1 && Math.abs(Math.abs(cs[0].lng) - 180) < 0.3, 'cluster across the antimeridian has a sensible centre', JSON.stringify(cs[0]));
ok(shortPlace('Near Wakefield, Quebec') === 'Wakefield, Quebec' && shortPlace('123 Main St, Banff') === '' && shortPlace('') === '', 'short place: "near" dropped, addresses never used');
ok(sinceDate(3, Date.parse('2026-10-24T12:00:00Z')) === '2026-10-21', 'window is the last 3 days');

section('Setup');
const login = await fetch(API + '/mod/login', { method: 'POST', headers: { origin: API, 'x-test-ip': '10.250.0.4' },
  body: new URLSearchParams({ password: 'letmein-local' }), redirect: 'manual' });
const COOKIE = (login.headers.get('set-cookie') || '').split(';')[0];
const base = { seen_time: '', loc_source: 'map', duration: '', sounds: '', smells: '', witnesses: 1, display_name: '', anonymous: true,
  videos: ['https://youtu.be/dQw4w9WgXcQ'], links: ['https://example.com/photo-of-it.jpg'], turnstile: 'XXXX.DUMMY.TOKEN',
  story: 'A huge grey shape with wings stood up by the road and the eyes caught the headlights before it lifted off over the trees.' };
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
async function call(path, { ip = freshIp(), origin = SITE } = {}) {
  const res = await fetch(API + path, { headers: { origin, 'x-test-ip': ip } });
  return { status: res.status, data: await res.json().catch(() => null), headers: res.headers };
}
const get = (q, opts) => call('/v1/clusters?' + new URLSearchParams(q), opts);
const pushes = () => (LOG ? readFileSync(LOG, 'utf8') : '').split('\n').filter((l) => l.includes('PUSHLOG ')).map((l) => JSON.parse(l.slice(l.indexOf('PUSHLOG ') + 8)));
const key = (n) => 'C' + String(n).padStart(3, '0') + 'x'.repeat(83);
const sub = await fetch(API + '/v1/push/subscribe', { method: 'POST', headers: { origin: SITE, 'content-type': 'application/json', 'x-test-ip': freshIp() },
  body: JSON.stringify({ endpoint: 'https://fcm.googleapis.com/fcm/send/point-pleasant', p256dh: key(7), auth: 'p'.repeat(22),
    lat: 38.84, lng: -82.14, radius_km: 50, categories: '', units: 'mi', turnstile: 'XXXX.DUMMY.TOKEN' }) }).then((r) => r.json());
ok(!!sub.id, 'alert subscriber at Point Pleasant');

const n0 = pushes().length;
const P1 = await report({ creature: 'mothman', seen_date: day(2), lat: 38.8445, lon: -82.1371, place: 'Point Pleasant, West Virginia' });
await sleep(600);
const P2 = await report({ creature: 'mothman', seen_date: day(1), lat: 38.87, lon: -82.1, place: 'Near Point Pleasant, West Virginia' });
await sleep(600);
await report({ creature: 'mothman', seen_date: day(0), lat: 38.9, lon: -82.2, place: 'Point Pleasant, West Virginia' }, false); // pending
const mine = (from) => pushes().slice(from).filter((p) => p.payload.kind === 'alert' && p.to === sub.id);
let alerts = mine(n0);
ok(alerts.length === 2 && alerts.every((p) => /^New .* report \d+ mi away$/.test(p.payload.title)), 'first two get the normal title',
  JSON.stringify(alerts.map((p) => p.payload.title)));

section('/v1/clusters');
let r = await get({ lat: 38.84, lng: -82.14 });
ok(r.status === 200 && r.data.count === 0, 'two recent approved reports and a pending one: no cluster yet', JSON.stringify(r.data));
const n1 = pushes().length;
const P3 = await report({ creature: 'ufo-orbs', seen_date: day(0), lat: 38.81, lon: -82.18, place: 'Point Pleasant, West Virginia' });
await sleep(1000);
alerts = mine(n1);
ok(alerts.length === 1 && alerts[0].payload.title === '3 reports near Point Pleasant, West Virginia in the last 3 days', 'third approval: the alert names the flap',
  JSON.stringify(alerts.map((p) => p.payload.title)));
ok(alerts[0]?.payload.cluster?.count === 3 && alerts[0]?.payload.url.endsWith(`/reports/${P3}/?source=alert`), 'alert still opens the new report');
const P4 = await report({ creature: 'ufo-orbs', seen_date: day(9), lat: 38.85, lon: -82.15, place: 'Point Pleasant, West Virginia' }); // too old to count
r = await get({ lat: 38.84, lng: -82.14, radius_km: 100 });
const c = r.data.clusters[0];
ok(r.status === 200 && r.data.count === 1 && c.count === 3, 'endpoint returns the cluster', JSON.stringify(r.data));
ok(c.first_seen === day(2) && c.last_seen === day(0) && c.categories.creature === 2 && c.categories.ufo === 1, 'dates and categories');
ok(c.place === 'Point Pleasant, West Virginia' && c.distance_km < 20, 'place and distance from the query point');
const body = JSON.stringify(r.data);
ok(![P1, P2, P3, P4].some((id) => body.includes(id)) && !/youtu|example\.com|story|pid|links/.test(body), 'no report ids, links or story text');
ok(r.data.rule.min_reports === 3 && r.data.rule.within_km === 50 && r.data.rule.window_days === 3, 'rule echoed');
r = await get({ lat: 53.55, lng: -113.49 });
ok(r.status === 200 && r.data.count === 0, 'Edmonton: nothing');

section('Living traditions');
await report({ creature: 'wendigo', seen_date: day(0), lat: 48.38, lon: -89.25, place: 'Thunder Bay, Ontario' });
await report({ creature: 'wendigo', seen_date: day(1), lat: 48.42, lon: -89.3, place: 'Thunder Bay, Ontario' });
await report({ creature: 'wendigo', seen_date: day(1), lat: 48.45, lon: -89.2, place: 'Kakabeka Falls, Ontario' });
r = await get({ lat: 48.38, lng: -89.25 });
const w = r.data.clusters?.[0];
ok(w && w.count === 3 && w.precision_km === 100 && w.place === '' && w.creatures.length === 0, 'region precision, no place, not named', JSON.stringify(r.data));

section('Validation, CORS, cache, rate limit');
r = await get({ lng: 1 });
ok(r.status === 400 && r.data.fields.lat === 'required', 'lat required');
r = await get({ lat: 10, lng: 10, radius_km: 900 });
ok(r.status === 400 && r.data.fields.radius_km, 'radius over 500 refused');
r = await get({ lat: 10, lng: 10 });
ok(r.headers.get('access-control-allow-origin') === SITE, 'site origin allowed');
r = await get({ lat: 10, lng: 10 }, { origin: 'https://evil.example' });
ok(!r.headers.get('access-control-allow-origin'), 'other origins get no CORS header');
const c1 = await get({ lat: 12.3456, lng: 45.6789, radius_km: 77 }), c2 = await get({ lat: 12.35, lng: 45.68, radius_km: 77 });
ok(c1.headers.get('x-cache') === 'miss' && c2.headers.get('x-cache') === 'hit' && /max-age=60/.test(c2.headers.get('cache-control')),
  'point rounded to 0.01 deg, 60 s cache', `${c1.headers.get('x-cache')} ${c2.headers.get('x-cache')}`);
let last;
for (let i = 0; i < 61; i++) last = await get({ lat: 2, lng: i }, { ip: '10.198.0.1' });
ok(last.status === 429 && last.data.state === 'slow', '61st request in a minute refused', String(last.status));

console.log(`\n${pass} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

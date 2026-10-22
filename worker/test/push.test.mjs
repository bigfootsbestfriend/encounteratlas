// Push alerts and moderation by notification, against the local Worker started by test/run.sh (PUSH_MODE=log:
// every push is written to the wrangler log as "PUSHLOG {...}" instead of being sent). Also the submit-time
// competitor blocklist and the stored "Was it a planet?" result.
import { readFileSync } from 'node:fs';

const API = process.env.API || 'http://127.0.0.1:8788';
const LOG = process.env.LOG;
const SITE = 'http://127.0.0.1:8825';
let pass = 0, failed = 0;
const ok = (cond, name, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); } else { failed++; console.log(`  FAIL ${name} ${extra}`); }
};
const section = (s) => console.log(`\n${s}`);
let ipN = 0;
const freshIp = () => `10.${(ipN >> 8) + 160}.${ipN++ & 255}.7`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const post = async (path, body, headers = {}) => {
  const r = await fetch(API + path, { method: 'POST', headers: { origin: SITE, 'content-type': 'application/json', 'x-test-ip': freshIp(), ...headers }, body: JSON.stringify(body) });
  return { status: r.status, data: await r.json().catch(() => null) };
};
const pushes = () => readFileSync(LOG, 'utf8').split('\n').filter((l) => l.includes('PUSHLOG ')).map((l) => JSON.parse(l.slice(l.indexOf('PUSHLOG ') + 8)));
const key = (n) => 'B' + String(n).padStart(3, '0') + 'x'.repeat(83); // 87 chars like a real p256dh
const sub = (name, extra = {}) => ({ endpoint: `https://fcm.googleapis.com/fcm/send/${name}`, p256dh: key(name.length), auth: 'a'.repeat(22),
  lat: 51.18, lng: -115.57, radius_km: 50, categories: '', units: 'km', turnstile: 'XXXX.DUMMY.TOKEN', ...extra });

const login = await fetch(API + '/mod/login', { method: 'POST', headers: { origin: API, 'x-test-ip': '10.250.0.3' },
  body: new URLSearchParams({ password: 'letmein-local' }), redirect: 'manual' });
const COOKIE = (login.headers.get('set-cookie') || '').split(';')[0];
const day = (n) => new Date(Date.now() - n * 86400e3).toISOString().slice(0, 10);
const base = { seen_time: '', loc_source: 'map', duration: '', sounds: '', smells: '', witnesses: 1, display_name: '', anonymous: true,
  videos: [], links: [], turnstile: 'XXXX.DUMMY.TOKEN', seen_date: day(1),
  story: 'A bright light hovered over the ridge for two minutes, then shot off to the north without a sound.' };
async function file(fields) {
  const f = new FormData();
  f.append('data', JSON.stringify({ ...base, ...fields }));
  const r = await fetch(API + '/api/reports', { method: 'POST', headers: { origin: SITE, 'x-test-ip': freshIp() }, body: f });
  return { status: r.status, data: await r.json() };
}
async function approve(id) {
  const r = await fetch(API + '/mod/action', { method: 'POST', headers: { origin: API, cookie: COOKIE, accept: 'application/json' },
    body: new URLSearchParams({ act: 'approve', id }) });
  return r.json();
}

section('Subscribe, update, unsubscribe');
let r = await post('/v1/push/subscribe', sub('x', { endpoint: 'https://evil.example/push' }));
ok(r.status === 400 && r.data.fields.endpoint, 'endpoint must be a real push service');
r = await post('/v1/push/subscribe', sub('x', { radius_km: 400 }));
ok(r.status === 400 && r.data.fields.radius_km, 'radius over 250 refused');
r = await post('/v1/push/subscribe', sub('x', { categories: 'ufo,dragons' }));
ok(r.status === 400 && r.data.fields.categories, 'unknown category refused');
r = await post('/v1/push/subscribe', sub('x', { turnstile: '' }));
ok(r.status === 403, 'needs the spam check');
const all = await post('/v1/push/subscribe', sub('banff-all', { lat: 51.1784, lng: -115.5708 }));
ok(all.status === 201 && all.data.id && all.data.manage_token, 'subscribed (all categories)');
const ufo = await post('/v1/push/subscribe', sub('canmore-ufo', { lat: 51.09, lng: -115.35, categories: 'ufo', units: 'mi' }));
ok(ufo.status === 201, 'subscribed (UFO only, miles)');
const far = await post('/v1/push/subscribe', sub('far-away', { lat: 49.28, lng: -123.12 }));
const gone = await post('/v1/push/subscribe', sub('gone-device', { endpoint: 'https://fcm.googleapis.com/fcm/send/gone-1' }));
r = await post('/v1/push/update', { id: all.data.id, manage_token: 'wrong', lat: 51.18, lng: -115.57, radius_km: 60 });
ok(r.status === 404, 'update with the wrong token refused');
r = await post('/v1/push/update', { id: all.data.id, manage_token: all.data.manage_token, lat: 51.18, lng: -115.57, radius_km: 60, categories: '' });
ok(r.status === 200, 'update with the right token');
const again = await post('/v1/push/subscribe', sub('banff-all', { lat: 51.1784, lng: -115.5708 }));
ok(again.status === 201 && again.data.id === all.data.id && again.data.manage_token !== all.data.manage_token, 'same endpoint again: same id, new token');
all.data.manage_token = again.data.manage_token;
await sleep(800);
ok(pushes().filter((p) => p.payload.title === 'New alert subscriber').length === 0, 'no mod device yet, so no subscriber push');

section('Moderator device');
let m = await fetch(API + '/mod/push/register', { method: 'POST', headers: { origin: API, 'content-type': 'application/json' }, body: '{}' });
ok(m.status === 401 || m.status === 403, 'registering a mod device needs the mod sign-in', String(m.status));
m = await fetch(API + '/mod/push/register', { method: 'POST', headers: { origin: API, cookie: COOKIE, 'content-type': 'application/json' },
  body: JSON.stringify({ endpoint: 'https://fcm.googleapis.com/fcm/send/mikes-phone', p256dh: key(9), auth: 'm'.repeat(22) }) });
ok(m.status === 200, 'mod device registered');
const pg = await fetch(API + '/mod/push', { headers: { cookie: COOKIE } });
const html = await pg.text();
ok(pg.status === 200 && /Turn on alerts on this device/.test(html) && /script-src 'nonce-/.test(pg.headers.get('content-security-policy')), '/mod/push page with a nonce script');
ok((await fetch(API + '/mod/sw.js')).headers.get('service-worker-allowed') === '/mod/', '/mod/sw.js served for scope /mod/');
await post('/v1/push/subscribe', sub('another-reader', { lat: 10, lng: 10 }));
await sleep(800);
ok(pushes().some((p) => p.payload.title === 'New alert subscriber'), 'new subscriber -> Mike\'s phone');

section('New report -> moderation push with Approve / Reject');
const before = pushes().length;
const u1 = await file({ creature: 'ufo-orbs', lat: 51.2, lon: -115.55, place: 'Banff' });
ok(u1.status === 201, 'UFO report near Banff filed');
await sleep(800);
const modPush = pushes().slice(before).find((p) => p.payload.kind === 'mod' && p.payload.id === u1.data.id);
ok(modPush && modPush.payload.approve && modPush.payload.reject, 'mod push has both button tokens');
r = await post('/mod/push-act', { id: u1.data.id, act: 'approve', t: 'nope' }, { origin: API });
ok(r.status === 403, 'bad button token refused');
r = await post('/mod/push-act', { id: u1.data.id, act: 'approve', t: modPush.payload.reject }, { origin: API });
ok(r.status === 403, 'reject token can\'t approve');
const n0 = pushes().length;
r = await post('/mod/push-act', { id: u1.data.id, act: 'approve', t: modPush.payload.approve }, { origin: API });
ok(r.status === 200 && r.data.status === 'approved', 'approved from the notification');
await sleep(1000);
let sent = pushes().slice(n0).filter((p) => p.payload.kind === 'alert' && p.payload.id === u1.data.id);
const to = (s) => sent.filter((p) => p.to === s.data.id);
ok(to(all).length === 1 && to(ufo).length === 1 && to(far).length === 0, 'nearby subscribers alerted, far one not');
ok(/^New .* report \d+ km away$/.test(to(all)[0]?.payload.title || '') && / mi away$/.test(to(ufo)[0]?.payload.title || ''), 'distance in each subscriber\'s units', JSON.stringify(sent.map((p) => p.payload.title)));
ok(to(all)[0]?.payload.url.endsWith(`/reports/${u1.data.id}/?source=alert`), 'tap opens the report page');
let st = await (await fetch(API + '/mod/push-stats', { headers: { cookie: COOKIE } })).json();
ok(st.mod_devices === 1 && st.active >= 4, 'push-stats counts', JSON.stringify(st));

section('Categories, living traditions, dead subscriptions, daily cap');
const n1 = pushes().length;
const b1 = await file({ creature: 'bigfoot', lat: 51.17, lon: -115.6, place: 'Sulphur Mountain', story: 'A huge dark figure crossed the trail ahead of us and stepped over a fallen log without slowing down at all.' });
await approve(b1.data.id);
await sleep(1000);
sent = pushes().slice(n1).filter((p) => p.payload.kind === 'alert');
ok(to(all).length === 1 && to(ufo).length === 0, 'creature report skips the UFO-only subscriber');
const w1 = await file({ creature: 'wendigo', lat: 51.19, lon: -115.58, place: 'Banff', story: 'We heard something walking around the cabin at night and the air went very cold for a few minutes.' });
const n2 = pushes().length;
await approve(w1.data.id);
await sleep(1000);
sent = pushes().slice(n2).filter((p) => p.payload.kind === 'alert');
ok(sent.length >= 1 && sent.every((p) => / in your region$/.test(p.payload.title)), 'living tradition says "in your region", no distance', JSON.stringify(sent.map((p) => p.payload.title)));
st = await (await fetch(API + '/mod/push-stats', { headers: { cookie: COOKIE } })).json();
const n3 = pushes().length;
const u2 = await file({ creature: 'ufo-orbs', lat: 51.18, lon: -115.57, place: 'Banff again' });
await approve(u2.data.id);
await sleep(1000);
sent = pushes().slice(n3).filter((p) => p.payload.kind === 'alert');
ok(to(all).length === 0, 'fourth alert of the day held back (cap 3)', JSON.stringify(sent.map((p) => p.to)));
ok(to(ufo).length === 1, 'UFO-only subscriber still under the cap gets it');
ok(sent.every((p) => p.to !== gone.data.id), 'the gone subscription was switched off after its 410');

section('Submit-time blocklist and sky check');
r = await file({ creature: 'bigfoot', lat: 51.2, lon: -115.5, links: ['https://www.bfro.net/GDB/show_report.asp?id=1'] });
ok(r.status === 400 && /other sighting databases/.test(r.data.fields?.links || ''), 'competitor link refused with a friendly message', JSON.stringify(r.data));
r = await file({ creature: 'ufo-orbs', lat: 51.2, lon: -115.5, story: 'I also filed this with NUFORC last week, it was a bright orb over the lake for a while.' });
ok(r.status === 400 && r.data.fields?.story, 'competitor name in the story refused');
const sky = await file({ creature: 'ufo-orbs', lat: 51.2, lon: -115.5, place: 'Sky test', sky_check: { candidates: ['Venus', 'Jupiter'], answer: 'no' } });
const bf = await file({ creature: 'bigfoot', lat: 51.2, lon: -115.5, place: 'Not a UFO', sky_check: { candidates: ['Venus'], answer: 'no' },
  story: 'A tall dark shape crossed the road in front of the car and was gone into the trees in a couple of seconds.' });
const q = await (await fetch(API + '/mod/queue.json?view=pending', { headers: { cookie: COOKIE } })).json();
const qs = q.reports.find((x) => x.pid === sky.data.id), qb = q.reports.find((x) => x.pid === bf.data.id);
ok(qs && qs.sky && qs.sky.answer === 'no' && qs.sky.candidates.join() === 'Venus,Jupiter', 'sky check stored and shown to /mod');
ok(qb && qb.sky === null, 'sky check ignored for non-UFO reports');

section('Unsubscribe');
r = await post('/v1/push/unsubscribe', { id: ufo.data.id, manage_token: ufo.data.manage_token });
ok(r.status === 200, 'unsubscribed');
const n4 = pushes().length;
const u3 = await file({ creature: 'ufo-orbs', lat: 51.1, lon: -115.4, place: 'Canmore' });
await approve(u3.data.id);
await sleep(1000);
sent = pushes().slice(n4).filter((p) => p.payload.kind === 'alert');
ok(to(ufo).length === 0, 'no alerts after unsubscribing');

console.log(`\n${pass} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

// End-to-end test against a local `wrangler dev` (run via test/run.sh, which starts a fresh database).
// submit -> moderate -> approve -> GeoJSON/photo links -> vote rules (duplicate, hidden until 10, rate limits,
// network bursts, swing freeze, AI flag) -> owner edit/withdraw.
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const API = process.env.API || 'http://127.0.0.1:8788';
const SITE = 'http://127.0.0.1:8825';
const PERSIST = process.env.PERSIST;
const here = new URL('.', import.meta.url);
let pass = 0, failed = 0;
const ok = (cond, name, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); } else { failed++; console.log(`  FAIL ${name} ${extra}`); }
};
const section = (s) => console.log(`\n${s}`);

let ipN = 0;
const freshIp = () => `10.${(ipN >> 8) + 20}.${ipN++ & 255}.7`; // every call a different /24

async function call(method, path, { body, session, ip = '10.0.0.1', form, headers = {} } = {}) {
  const h = { origin: SITE, 'x-test-ip': ip, ...headers };
  if (session) h.authorization = `Bearer ${session}`;
  let b;
  if (form) b = form;
  else if (body !== undefined) { b = JSON.stringify(body); h['content-type'] = 'application/json'; }
  const res = await fetch(API + path, { method, headers: h, body: b, redirect: 'manual' });
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch { /* html */ }
  return { status: res.status, data, text, headers: res.headers };
}

let userN = 0;
async function signIn(label = 'user') {
  const email = `${label}${userN++}@example.test`;
  const s = await call('POST', '/api/auth/start', { body: { email, turnstile: 'XXXX.DUMMY.TOKEN' }, ip: freshIp() });
  const t = new URL(s.data.dev_link).searchParams.get('signin');
  const v = await call('POST', '/api/auth/verify', { body: { t } });
  return { email, session: v.data.session, t };
}

function sql(command) {
  return execFileSync('npx', ['-y', 'wrangler@4', 'd1', 'execute', 'encounters', '--local', '--persist-to', PERSIST, '--json', '--command', command],
    { cwd: new URL('..', here), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}

// A JPEG carrying everything an attacker or a phone might add: EXIF with GPS, a PHP comment, and a
// PHP payload after the end-of-image marker (the ConsoleVariations-style polyglot).
const clean = new Uint8Array(readFileSync(new URL('fixture.jpg', here)));
const exif = new TextEncoder().encode('Exif\0\0GPSLatitude=45.4215 GPSLongitude=-75.6972 Make=Pixel');
const php = new TextEncoder().encode("<?php system($_GET['c']); ?>");
const seg = (marker, payload) => new Uint8Array([0xff, marker, (payload.length + 2) >> 8, (payload.length + 2) & 255, ...payload]);
const evil = new Uint8Array([0xff, 0xd8, ...seg(0xe1, exif), ...seg(0xfe, php), ...clean.subarray(2), ...php]);
const png = new Uint8Array(readFileSync(new URL('fixture.png', here)));
const has = (bytes, s) => Buffer.from(bytes).includes(Buffer.from(s));

const EXACT = { lat: 45.42153, lon: -75.69719 };
const baseReport = {
  creature: 'bigfoot', seen_date: '2026-09-30', seen_time: '21:40', lat: EXACT.lat, lon: EXACT.lon, loc_source: 'gps',
  place: 'Near Wakefield, Quebec', story: 'Walking the dog on the trail at dusk, a tall dark shape crossed about 40 m ahead and stepped over a fallen log.',
  duration: 'About 10 seconds', sounds: 'Two wood knocks', smells: 'Wet dog', witnesses: 2, display_name: 'Trail Walker', anonymous: true,
  videos: ['https://youtu.be/dQw4w9WgXcQ', 'https://www.tiktok.com/@someone/video/7234567890123456789', 'https://vimeo.com/76979871',
    'https://youtu.be/aqz-KE-bpKQ', 'https://vimeo.com/22439234'],
  turnstile: 'XXXX.DUMMY.TOKEN',
};
function reportForm(data, photos = []) {
  const f = new FormData();
  f.append('data', JSON.stringify(data));
  photos.forEach((p, i) => f.append('photo', new Blob([p], { type: 'image/jpeg' }), `p${i}.jpg`));
  return f;
}

async function modLogin() {
  const r = await fetch(API + '/mod/login', { method: 'POST', headers: { origin: API, 'x-test-ip': '10.250.0.1' },
    body: new URLSearchParams({ password: 'letmein-local' }), redirect: 'manual' });
  return (r.headers.get('set-cookie') || '').split(';')[0];
}
async function mod(act, id, extra = {}, cookie) {
  const r = await fetch(API + '/mod/action', { method: 'POST', headers: { origin: API, cookie, accept: 'application/json' },
    body: new URLSearchParams({ act, id, ...extra }) });
  return { status: r.status, data: await r.json().catch(() => null) };
}
const queue = async (cookie, view = 'pending') => (await fetch(`${API}/mod/queue.json?view=${view}`, { headers: { cookie } })).json();

// ---------------------------------------------------------------------------------------------
section('Accounts');
const A = await signIn('alice');
ok(A.session, 'magic link signs in');
const reuse = await call('POST', '/api/auth/verify', { body: { t: A.t } });
ok(reuse.status === 400 && reuse.data.state === 'used', 'sign-in link works only once');
const forged = await call('POST', '/api/auth/verify', { body: { t: A.t.slice(0, -3) + 'abc' } });
ok(forged.status === 400 && forged.data.state === 'invalid', 'tampered link rejected');
const noTs = await call('POST', '/api/auth/start', { body: { email: 'x@example.test' }, ip: freshIp() });
ok(noTs.status === 403 && noTs.data.state === 'turnstile', 'sign-in needs Turnstile');
const meA = await call('GET', '/api/me', { session: A.session });
ok(meA.status === 200 && meA.data.user.weight === 0.2, 'brand-new account votes at weight 0.2', JSON.stringify(meA.data));

section('Submit');
let r = await call('POST', '/api/reports', { form: reportForm({ ...baseReport, turnstile: '' }), session: A.session, ip: '10.1.1.1' });
ok(r.status === 403 && r.data.state === 'turnstile', 'report without Turnstile rejected');
r = await call('POST', '/api/reports', { form: reportForm({ ...baseReport, story: 'too short', lat: '' }), session: A.session, ip: '10.1.1.1' });
ok(r.status === 400 && r.data.fields.story && r.data.fields.location, 'missing story/location reported per field');
r = await call('POST', '/api/reports', { form: reportForm({ ...baseReport, videos: ['https://evil.example/video.mp4'] }), session: A.session, ip: '10.1.1.1' });
ok(r.status === 400 && r.data.fields.videos, 'non YouTube/TikTok/Vimeo video link rejected');
r = await call('POST', '/api/reports', { form: reportForm(baseReport, [clean]), session: A.session, ip: '10.1.2.2' });
ok(r.status === 400 && r.data.fields.links, 'file uploads refused (links only)');
for (const [bad, why] of [['http://imgur.com/a.jpg', 'plain http'], ['javascript:alert(1)', 'javascript:'], ['https://127.0.0.1/a.jpg', 'IP address'],
  ['https://user:pw@imgur.com/a', 'credentials'], ['https://localhost/a.jpg', 'localhost']]) {
  r = await call('POST', '/api/reports', { form: reportForm({ ...baseReport, links: [bad] }), session: A.session, ip: '10.1.2.2' });
  ok(r.status === 400 && r.data.fields.links, `photo link rejected: ${why}`);
}
r = await call('POST', '/api/reports', { form: reportForm({ ...baseReport, links: Array.from({ length: 6 }, (_, i) => `https://imgur.com/p${i}`) }), session: A.session, ip: '10.1.2.2' });
ok(r.status === 400 && r.data.fields.links, 'more than 5 photo links rejected');
const LINKS = ['https://imgur.com/abc123', 'https://www.flickr.com/photos/someone/1234#frag'];
r = await call('POST', '/api/reports', { form: reportForm({ ...baseReport, links: LINKS }), session: A.session, ip: '10.1.1.1' });
ok(r.status === 201 && r.data.status === 'pending', 'valid report with photo links accepted as pending', JSON.stringify(r.data));
const PID = r.data.id;

let pub = await call('GET', `/api/reports/${PID}`);
ok(pub.status === 404, 'pending report is not public');
const own = await call('GET', `/api/reports/${PID}`, { session: A.session });
ok(own.status === 200 && own.data.report.status === 'pending' && own.data.report.exact.lat === EXACT.lat, 'owner sees own pending report with exact point');
ok(own.data.report.links.length === 2 && own.data.report.links[1].url === 'https://www.flickr.com/photos/someone/1234', 'owner sees photo links (fragment dropped)');
let gj = await call('GET', '/api/reports.geojson');
ok(!gj.data.features.some((f) => f.properties.id === PID), 'pending report not in GeoJSON');

section('Rate limit on reports (3 per IP per hour)');
let codes = [];
for (let i = 0; i < 3; i++) codes.push((await call('POST', '/api/reports', { form: reportForm(baseReport), ip: '10.1.1.1' })).status);
ok(codes.join() === '201,201,429', 'fourth report from one IP in an hour gets 429', codes.join());

section('Moderation');
let q = await fetch(`${API}/mod/queue.json`);
ok(q.status === 401, 'queue needs moderator sign-in');
const bad = await fetch(API + '/mod/login', { method: 'POST', headers: { origin: API }, body: new URLSearchParams({ password: 'nope' }) });
ok(bad.status === 403, 'wrong moderator password rejected');
const COOKIE = await modLogin();
ok(/^ea_mod=/.test(COOKIE), 'moderator signs in (cookie)');
const page = await fetch(`${API}/mod`, { headers: { cookie: COOKIE } });
const html = await page.text();
ok(page.status === 200 && html.includes(PID) && page.headers.get('content-security-policy').includes("default-src 'none'"), 'moderation page lists the report, locked-down CSP');
const csrf = await fetch(API + '/mod/action', { method: 'POST', headers: { cookie: COOKIE, origin: 'https://evil.example' }, body: new URLSearchParams({ act: 'approve', id: PID }) });
ok(csrf.status === 403, 'cross-site moderation POST refused');
const pend = await queue(COOKIE);
const pr = pend.reports.find((x) => x.pid === PID);
ok(pr && pr.lat === EXACT.lat && pr.links.length === 2, 'moderator sees exact location and photo links');
// reject the two spare reports, approve the real one
for (const x of pend.reports.filter((x) => x.pid !== PID)) await mod('reject', x.pid, { note: 'duplicate' }, COOKIE);
const ap = await mod('approve', PID, {}, COOKIE);
ok(ap.status === 200 && /approved/.test(ap.data.done), 'moderator approves');

section('Public view after approval');
pub = await call('GET', `/api/reports/${PID}`);
const R = pub.data.report;
ok(pub.status === 200 && !R.exact && R.name === null, 'approved report public, no exact point, anonymous name hidden');
ok(!JSON.stringify(pub.data).includes('example.test'), 'no email in public JSON');
const dKm = Math.hypot((R.lat - EXACT.lat) * 111, (R.lon - EXACT.lon) * 111 * Math.cos(EXACT.lat * Math.PI / 180));
ok(R.lat !== EXACT.lat && dKm < 4 && Math.abs(R.lat / 0.045 - Math.round(R.lat / 0.045)) < 1e-6, `public point snapped to ~5 km grid (${dKm.toFixed(2)} km off)`);
ok(R.videos.length === 5 && R.videos[1].url === 'https://www.tiktok.com/@someone/video/7234567890123456789', 'video links normalised');
gj = await call('GET', '/api/reports.geojson');
const feat = gj.data.features.find((f) => f.properties.id === PID);
ok(feat && feat.geometry.coordinates[1] === R.lat && feat.properties.n === 'Bigfoot', 'approved report appears in GeoJSON at the public point');
ok(!gj.data.features.some((f) => f.geometry.coordinates[1] === EXACT.lat), 'exact point never in GeoJSON');
const list = await call('GET', '/api/reports?limit=5');
ok(list.data.reports[0]?.id === PID && list.data.reports[0].n_links === 2, 'recent reports list shows it with its photo-link count');
ok(R.links.length === 2 && R.links[1].host === 'flickr.com', 'public report has photo links with host names');
const noImg = await fetch(`${API}/img/${'0'.repeat(24)}.jpg`);
ok(noImg.status === 404, 'no photo store: /img always 404');
const cors = await fetch(API + '/api/reports', { headers: { origin: 'https://evil.example' } });
ok(!cors.headers.get('access-control-allow-origin'), 'no CORS for other origins');

section('Voting rules');
const RI = `r:${PID}`, P1 = `v:${PID}:3`, P2 = `v:${PID}:4`;
let v = await call('POST', '/api/votes', { body: { item: RI, choice: 'real', turnstile: 'x' } });
ok(v.status === 401, 'voting needs an account');
v = await call('POST', '/api/votes', { body: { item: RI, choice: 'real' }, session: A.session });
ok(v.status === 403 && v.data.state === 'turnstile', 'voting needs Turnstile');
v = await call('POST', '/api/votes', { body: { item: RI, choice: 'mis', turnstile: 'x' }, session: A.session });
ok(v.status === 400 && v.data.state === 'reason', 'Misidentified needs a reason tag');
v = await call('POST', '/api/votes', { body: { item: RI, choice: 'real', turnstile: 'x' }, session: A.session, ip: '10.2.0.1' });
ok(v.status === 200 && v.data.pass && v.data.n === 1 && !v.data.results, 'first vote counts; results hidden under 10 votes');
const passA = v.data.pass;
v = await call('POST', '/api/votes', { body: { item: RI, choice: 'hoax', pass: passA }, session: A.session, ip: '10.2.0.1' });
ok(v.status === 409 && v.data.state === 'duplicate', 'second vote on same item rejected');
const dupRows = JSON.parse(sql(`SELECT COUNT(*) AS n FROM votes WHERE item = '${RI}'`))[0].results[0].n;
ok(dupRows === 1, 'database holds one vote for the account');
let dbDup = '';
try { sql(`INSERT INTO votes (item, user_id, choice, weight, ip_hash, net_hash) SELECT item, user_id, 'hoax', 1, 'x', 'x' FROM votes WHERE item = '${RI}'`); }
catch (e) { dbDup = String(e.stdout || e.stderr || e.message); }
ok(/UNIQUE/i.test(dbDup), 'UNIQUE(item, user_id) enforced by the database itself');
v = await call('POST', '/api/votes', { body: { item: P1, choice: 'mis', reason: 'cgi-ai', pass: passA }, session: A.session, ip: '10.2.0.1' });
ok(v.status === 200 && !v.data.pass, 'Turnstile pass reused for the next vote');

// 9 more accounts vote on the report from different networks -> 10 votes
const voters = [];
for (let i = 0; i < 9; i++) voters.push(await signIn('voter'));
for (const [i, u] of voters.entries()) {
  v = await call('POST', '/api/votes', { body: { item: RI, choice: i < 6 ? 'real' : i < 8 ? 'hoax' : 'mis', reason: 'bear', turnstile: 'x' },
    session: u.session, ip: freshIp() });
}
ok(v.status === 200 && v.data.n === 10 && v.data.results, '10th voter sees results', JSON.stringify(v.data));
// 7 of 10 said real, but Alice (approved report = active) weighs 0.5 and the 9 brand-new accounts 0.2 each:
// real = (0.5 + 6*0.2) / (0.5 + 9*0.2) = 73.9%
ok(v.data.results && v.data.results.real === 73.9 && v.data.results.reasons.bear === 100,
  'weighted shares: active account 0.5 vs new 0.2 -> 73.9% real; misidentified = bear', JSON.stringify(v.data.results));
const outsider = await signIn('outsider');
let g = await call('GET', `/api/votes?items=${RI}`, { session: outsider.session });
ok(g.data.items[0].n === 10 && !g.data.items[0].results, 'results stay hidden from someone who has not voted');
g = await call('GET', `/api/votes?items=${RI}`);
ok(!g.data.items[0].results, 'results hidden when signed out');
g = await call('GET', `/api/votes?items=${RI}`, { session: A.session });
ok(g.data.items[0].results && g.data.items[0].mine.choice === 'real', 'earlier voter now sees results + own vote');

section('Rate limits on votes (test config: 4/hour per account, 6/hour per IP)');
const B = voters[0]; // already voted once this hour
const items = [P1, P2, `v:${PID}:0`, `v:${PID}:1`];
codes = [];
let passB;
for (const it of items) {
  v = await call('POST', '/api/votes', { body: { item: it, choice: 'real', turnstile: 'x', pass: passB }, session: B.session, ip: freshIp() });
  passB = v.data.pass || passB;
  codes.push(v.status);
}
ok(codes.join() === '200,200,200,429', 'account limited after 4 votes in an hour', codes.join());
const shared = [];
for (let i = 0; i < 7; i++) shared.push(await signIn('cafe'));
const ipItems = [P2, `v:${PID}:0`, `v:${PID}:1`, `v:${PID}:2`, P2, `v:${PID}:0`, `v:${PID}:1`];
codes = [];
for (const [i, u] of shared.entries()) {
  // 7 accounts behind one IP (spread over items so the per-network hold doesn't kick in first)
  codes.push((await call('POST', '/api/votes', { body: { item: ipItems[i], choice: 'hoax', turnstile: 'x' }, session: u.session, ip: '10.66.66.66' })).status);
}
ok(codes.slice(0, 6).every((c) => c === 200) && codes[6] === 429, 'IP limited after 6 votes in an hour', codes.join());

section('Burst from one network');
const net = [];
for (let i = 0; i < 4; i++) net.push(await signIn('dorm'));
const V2 = `v:${PID}:2`;
const states = [];
for (const [i, u] of net.entries()) {
  v = await call('POST', '/api/votes', { body: { item: V2, choice: 'hoax', turnstile: 'x' }, session: u.session, ip: `10.77.77.${i + 1}` });
  states.push(v.data.state);
}
// V2 already has 1 vote from 10.66.66.66; the dorm network gets 3 counted, the 4th held
ok(states.join() === 'ok,ok,ok,held', '4th vote from the same /24 on one item is held', states.join());
let fl = await queue(COOKIE, 'flagged');
const burst = fl.flagged.find((x) => x.item === V2);
ok(burst && burst.flag === 'burst' && burst.held === 1, 'burst item flagged for moderators with 1 held vote');

section('AI flag');
const fa = await call('POST', '/api/flag', { body: { item: P2, kind: 'ai' }, session: outsider.session });
const fa2 = await call('POST', '/api/flag', { body: { item: P2, kind: 'ai' }, session: outsider.session });
ok(fa.data.state === 'ok' && fa2.data.state === 'already', 'AI flag counted once per account');
fl = await queue(COOKIE, 'flagged');
ok(fl.flagged[0].flag === 'ai' && [P1, P2].includes(fl.flagged[0].item), 'AI-flagged items fast-tracked to the top of the review queue',
  fl.flagged.map((x) => x.item + ':' + x.flag).join(' '));

section('Swing detection');
const s2 = await call('POST', '/api/reports', { form: reportForm({ ...baseReport, creature: 'ufo-orbs', videos: [] }), session: A.session, ip: '10.3.3.3' });
await mod('approve', s2.data.id, {}, COOKIE);
const SI = `r:${s2.data.id}`;
const early = [];
for (let i = 0; i < 10; i++) early.push(await signIn('early'));
for (const u of early) await call('POST', '/api/votes', { body: { item: SI, choice: 'real', turnstile: 'x' }, session: u.session, ip: freshIp() });
sql(`UPDATE votes SET at = at - 7200 WHERE item = '${SI}'`); // that baseline was two hours ago
const late = [];
for (let i = 0; i < 6; i++) late.push(await signIn('late'));
const lateStates = [];
for (const u of late) {
  v = await call('POST', '/api/votes', { body: { item: SI, choice: 'hoax', turnstile: 'x' }, session: u.session, ip: freshIp() });
  lateStates.push(v.status);
}
ok(lateStates.slice(0, 5).every((c) => c === 200) && lateStates[5] === 423, 'sudden swing to "hoax" freezes the item (next vote 423)', lateStates.join());
g = await call('GET', `/api/votes?items=${SI}`, { session: late[0].session });
ok(g.data.items[0].frozen && !g.data.items[0].results, 'frozen item shows no results');
fl = await queue(COOKIE, 'flagged');
const sw = fl.flagged.find((x) => x.item === SI);
ok(sw && sw.frozen === 1 && sw.flag === 'swing', 'swing flagged for moderators', sw && sw.flag_note);
await mod('void_recent', SI, { minutes: '60' }, COOKIE);
await mod('unfreeze', SI, {}, COOKIE);
v = await call('POST', '/api/votes', { body: { item: SI, choice: 'real', turnstile: 'x' }, session: late[5].session, ip: freshIp() });
ok(v.status === 200 && v.data.n === 11, 'moderator voids the burst + unfreezes; voting resumes', `${v.status} n=${v.data.n}`);

section('Owner edit and withdraw');
const other = await call('PATCH', `/api/reports/${PID}`, { body: { ...baseReport }, session: outsider.session });
ok(other.status === 404, 'someone else cannot edit the report');
const ed = await call('PATCH', `/api/reports/${PID}`, { body: { ...baseReport, story: baseReport.story + ' Edited: it was closer to 30 m.', links: [LINKS[0]] }, session: A.session });
ok(ed.status === 200 && ed.data.status === 'pending', 'owner edit goes back to moderation');
pub = await call('GET', `/api/reports/${PID}`);
ok(pub.status === 404, 'edited report hidden until re-approved');
await mod('approve', PID, {}, COOKIE);
pub = await call('GET', `/api/reports/${PID}`);
ok(pub.data.report.links.length === 1 && /30 m/.test(pub.data.report.story), 'after re-approval: edit live, removed photo link gone');
const wd = await call('DELETE', `/api/reports/${PID}`, { session: A.session });
pub = await call('GET', `/api/reports/${PID}`);
gj = await call('GET', '/api/reports.geojson');
ok(wd.status === 200 && pub.status === 404 && !gj.data.features.some((f) => f.properties.id === PID), 'owner can withdraw; gone from API and map');

console.log(`\n${pass} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

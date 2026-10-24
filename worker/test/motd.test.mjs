// Mystery of the day voting (item 'm:<slug>', src/motd.js + generated src/motd_items.js).
// Pick rule unit tests, then API tests against the local `wrangler dev` from test/run.sh.
import { MOTD } from '../src/motd_items.js';
import { MOTD_SLUGS, motdSlugFor, utcDay } from '../src/motd.js';

const API = process.env.API || 'http://127.0.0.1:8788';
const SITE = 'http://127.0.0.1:8825';
let pass = 0, failed = 0;
const ok = (cond, name, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); } else { failed++; console.log(`  FAIL ${name} ${extra}`); }
};
const section = (s) => console.log(`\n${s}`);

section('Pick rule');
const first = MOTD.eras[0];
ok(MOTD_SLUGS.size >= 30 && first.order.length === new Set(first.order).size, 'list has 30+ cases, no duplicates', String(MOTD_SLUGS.size));
ok(motdSlugFor(first.from - 1) === null, 'no case before the schedule starts');
ok(motdSlugFor(first.from) === first.order[0] && motdSlugFor(first.from + 1) === first.order[1], 'day by day through the order');
const lastEra = MOTD.eras[MOTD.eras.length - 1];
const cycle = [];
for (let d = lastEra.from; d < lastEra.from + lastEra.order.length; d++) cycle.push(motdSlugFor(d));
ok(new Set(cycle).size === lastEra.order.length, `no repeats within one full cycle (${lastEra.order.length} days)`);
ok(motdSlugFor(lastEra.from + lastEra.order.length) === motdSlugFor(lastEra.from), 'cycle wraps around');
ok(utcDay(Date.UTC(2026, 9, 24, 23, 59)) === utcDay(Date.UTC(2026, 9, 24, 0, 0)) && utcDay(Date.UTC(2026, 9, 25)) === utcDay(Date.UTC(2026, 9, 24)) + 1,
  'days change at midnight UTC');
ok(!['dyatlov-pass', 'roanoke-lost-colony', 'mary-celeste', 'flannan-isles-lighthouse', 'bennington-triangle', 'nahanni-headless-valley']
  .some((s) => MOTD_SLUGS.has(s)), 'vanishings and deaths are left out');

let ipN = 0;
const freshIp = () => `10.${(ipN >> 8) + 140}.${ipN++ & 255}.9`;
async function call(method, path, { body, session, ip = '10.0.0.1' } = {}) {
  const h = { origin: SITE, 'x-test-ip': ip };
  if (session) h.authorization = `Bearer ${session}`;
  if (body !== undefined) h['content-type'] = 'application/json';
  const res = await fetch(API + path, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: res.status, data: await res.json().catch(() => null) };
}
let userN = 0;
async function signIn(label) {
  const s = await call('POST', '/api/auth/start', { body: { email: `${label}${userN++}@example.test`, turnstile: 'XXXX.DUMMY.TOKEN' }, ip: freshIp() });
  const t = new URL(s.data.dev_link).searchParams.get('signin');
  return (await call('POST', '/api/auth/verify', { body: { t } })).data.session;
}

section('Votes on mystery-of-the-day cases');
const today = motdSlugFor(utcDay());
const other = [...MOTD_SLUGS].find((s) => s !== today);
const T = `m:${today}`, O = `m:${other}`;
ok(!!today, 'there is a case today', today);

const lone = await signIn('motd');
let v = await call('POST', '/api/votes', { body: { item: 'm:not-a-real-case', choice: 'real', turnstile: 'x' }, session: lone, ip: freshIp() });
ok(v.status === 404, 'unknown case slug refused');
v = await call('POST', '/api/votes', { body: { item: 'm:../../etc', choice: 'real', turnstile: 'x' }, session: lone, ip: freshIp() });
ok(v.status === 404, 'malformed id refused');
let g = await call('GET', `/api/votes?items=m:not-a-real-case,${T}`);
ok(g.data.items.length === 1 && g.data.items[0].item === T && g.data.items[0].today === true, 'GET skips unknown cases and marks today\'s', JSON.stringify(g.data));

const voters = [];
for (let i = 0; i < 10; i++) voters.push(await signIn('mv'));
for (const [i, s] of voters.entries()) {
  v = await call('POST', '/api/votes', { body: { item: T, choice: i < 7 ? 'mis' : 'real', reason: 'balloon', turnstile: 'x' }, session: s, ip: freshIp() });
}
ok(v.status === 200 && v.data.n === 10 && v.data.today && !v.data.results, "today's case: 10th voter still sees no results", JSON.stringify(v.data));
g = await call('GET', `/api/votes?items=${T}`, { session: voters[0] });
ok(g.data.items[0].n === 10 && !g.data.items[0].results && g.data.items[0].mine, "today's results hidden from earlier voters too");

for (const [i, s] of voters.entries()) {
  v = await call('POST', '/api/votes', { body: { item: O, choice: i < 4 ? 'hoax' : 'real', turnstile: 'x' }, session: s, ip: freshIp() });
  if (i === 8) ok(v.status === 200 && v.data.n === 9 && !v.data.results && !v.data.today, "another day's case: hidden under 10 votes");
}
ok(v.data.results && v.data.results.real === 60 && v.data.results.hoax === 40, "another day's case: results at 10 votes", JSON.stringify(v.data.results));
g = await call('GET', `/api/votes?items=${O}`);
ok(g.data.items[0].results && g.data.items[0].results.real === 60, "past case results are public, even signed out (for yesterday's reveal)");
const outsider = await signIn('motdout');
g = await call('GET', `/api/votes?items=${O},${T}`, { session: outsider });
ok(g.data.items.find((x) => x.item === O).results && !g.data.items.find((x) => x.item === T).results, "someone who never voted sees the past results, not today's");

console.log(`\n${pass} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

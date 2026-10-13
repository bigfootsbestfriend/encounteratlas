// Fills a LOCAL dev Worker with a few made-up, clearly-labelled demo reports so the pages have something
// to show. Usage: (cd worker && npm run dev) in one terminal, then `node test/seed.mjs` (API=http://127.0.0.1:8787).
// Never point this at production.

const API = process.env.API || 'http://127.0.0.1:8787';
if (!/127\.0\.0\.1|localhost/.test(API)) throw new Error('seed.mjs only runs against a local Worker');
let n = 0;
const ip = () => `10.${100 + (n >> 8)}.${n++ & 255}.9`;

async function call(method, path, { body, session, form } = {}) {
  const headers = { 'x-test-ip': ip() };
  if (session) headers.authorization = `Bearer ${session}`;
  if (body) headers['content-type'] = 'application/json';
  const r = await fetch(API + path, { method, headers, body: form || (body && JSON.stringify(body)) });
  return r.json();
}
async function signIn(email) {
  const s = await call('POST', '/api/auth/start', { body: { email, turnstile: 'XXXX.DUMMY.TOKEN' } });
  const t = new URL(s.dev_link).searchParams.get('signin');
  return (await call('POST', '/api/auth/verify', { body: { t } })).session;
}

const DEMO = [
  { creature: 'bigfoot', seen_date: '2026-09-27', seen_time: '19:50', lat: 47.8021, lon: -121.5562, place: 'Near Index, Washington', witnesses: 2,
    story: '[Demo report] We were hiking out along the river trail at dusk when my wife stopped dead. About 60 yards upslope something very tall and dark stepped between two cedars, turned its whole upper body to look at us, then walked off without a sound.\n\nWe heard two loud knocks a minute later, further up the ridge.',
    duration: 'About 15 seconds', sounds: 'Two wood knocks, then nothing', smells: 'Like a wet dog mixed with skunk', links: ['https://imgur.com/demo-woods'], anonymous: false, display_name: 'Rain City Hiker',
    videos: ['https://www.youtube.com/watch?v=dQw4w9WgXcQ'] },
  { creature: 'ufo-orbs', seen_date: '2026-10-03', seen_time: '22:15', lat: 44.0521, lon: -79.4613, place: 'Lake Simcoe, Ontario', witnesses: 4,
    story: '[Demo report] Three amber lights hovered over the lake in a loose triangle for several minutes, then the middle one shot off to the north. No sound at all. Not a plane, no blinking.',
    duration: '4 to 5 minutes', sounds: 'None', smells: '', links: ['https://www.flickr.com/photos/demo/1234567890'], anonymous: true },
  { creature: 'dogman', seen_date: '2026-08-14', seen_time: '02:30', lat: 44.7631, lon: -85.6206, place: 'Grand Traverse County, Michigan', witnesses: 1, date_approx: true,
    story: '[Demo report] Driving home on a county road, my headlights caught something crouched in the ditch. It stood up on two legs, easily taller than my truck window, with a long canine snout. It did not run. It just watched me go by.',
    duration: 'A few seconds', sounds: 'A low growl through the open window', smells: 'Rotten meat', anonymous: true },
  { creature: 'other', other_what: 'Glowing figure on the road', seen_date: '2026-09-02', seen_time: '23:05', lat: 35.5951, lon: -82.5515, place: 'Outside Asheville, North Carolina', witnesses: 2,
    story: '[Demo report] A pale, glowing human-shaped figure was standing in the middle of the road. As we slowed down it faded out from the feet up. My friend saw it too and we pulled over shaking.',
    duration: '10 seconds', sounds: '', smells: '', anonymous: true },
];

const COOKIE = (await fetch(API + '/mod/login', { method: 'POST', headers: { origin: API }, body: new URLSearchParams({ password: process.env.MOD_PASSWORD || 'letmein-local' }), redirect: 'manual' }))
  .headers.get('set-cookie').split(';')[0];
const author = await signIn('demo-author@example.test');
const ids = [];
for (const d of DEMO) {
  const f = new FormData();
  f.append('data', JSON.stringify({ ...d, loc_source: 'map', turnstile: 'XXXX.DUMMY.TOKEN' }));
  const r = await call('POST', '/api/reports', { form: f, session: author });
  if (!r.id) throw new Error(JSON.stringify(r));
  ids.push(r.id);
  await fetch(API + '/mod/action', { method: 'POST', headers: { origin: API, cookie: COOKIE, accept: 'application/json' }, body: new URLSearchParams({ act: 'approve', id: r.id }) });
}
// 12 votes on the first report so its results unlock for voters
for (let i = 0; i < 12; i++) {
  const s = await signIn(`demo-voter${i}-${Date.now()}@example.test`);
  const choice = i < 6 ? 'real' : i < 9 ? 'mis' : 'hoax';
  await call('POST', '/api/votes', { body: { item: `r:${ids[0]}`, choice, reason: choice === 'mis' ? (i % 2 ? 'bear' : 'costume') : '', turnstile: 'XXXX.DUMMY.TOKEN' }, session: s });
}
// one pending report so the moderation queue has something in it
const f = new FormData();
f.append('data', JSON.stringify({ ...DEMO[2], creature: 'mothman', place: 'Point Pleasant, West Virginia', lat: 38.8445, lon: -82.1371, story: '[Demo report, pending] Huge grey winged shape on the old TNT area road with red eyes that reflected the headlights.', turnstile: 'XXXX.DUMMY.TOKEN' }));
await call('POST', '/api/reports', { form: f });
console.log('seeded approved reports:', ids.join(' '));

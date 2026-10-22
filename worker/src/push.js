// Push alerts (the field app): readers save an area and get a notification when a report near it is approved;
// Mike's own devices (role 'mod') get each new pending report with Approve / Reject buttons.
//   POST /v1/push/subscribe   {endpoint, p256dh, auth, lat, lng, radius_km, categories, units, turnstile} -> {id, manage_token}
//   POST /v1/push/update      {id, manage_token, lat, lng, radius_km, categories, units}                  -> {state: 'ok'}
//   POST /v1/push/unsubscribe {id, manage_token}                                                           -> {state: 'ok'}
// Web web apps can't track location in the background, so alerts go by the saved area only. Sending happens in
// ctx.waitUntil after the mod action, so approving stays instant. Secrets: VAPID_PRIVATE (JWK JSON) and
// MOD_PUSH_KEY (signs the Approve / Reject buttons). VAPID_PUBLIC is a plain var (the site ships it too).
import { CREATURES } from './creatures.js';
import { LIVING_TRADITIONS } from './index.js';
import { haversineKm, category, publicPoint, summary } from './nearby.js';
import { sendPush, validEndpoint, b64u } from './webpush.js';
import { fail, json, hash, clientIp, rateLimited, turnstileOk, randomId, sendEmail, emailLayout, esc, line, now } from './util.js';

export const DAILY_CAP = 3;
const BATCH = 50;
const CATS = ['ufo', 'creature', 'other'];
const round2 = (x) => Math.round(x * 100) / 100;
const today = () => new Date().toISOString().slice(0, 10);

// Competitor names never go out in a notification (titles and summaries come from readers' own words).
export const BLOCKED = /bfro|nuforc|mufon|enigma\s*labs|enigmalabs|cryptid\s*catchers|cryptidcatchers|cryptid\s*atlas|cryptidatlas/i;

const vapid = (env) => (env.VAPID_PUBLIC && env.VAPID_PRIVATE
  ? { publicKey: env.VAPID_PUBLIC, privateJwk: env.VAPID_PRIVATE, subject: 'mailto:hello@encounteratlas.com' } : null);

function area(b, fields) {
  const lat = Number(b.lat), lng = Number(b.lng), radius = Math.round(Number(b.radius_km));
  if (!Number.isFinite(lat) || Math.abs(lat) > 90) fields.lat = '-90 to 90';
  if (!Number.isFinite(lng) || Math.abs(lng) > 180) fields.lng = '-180 to 180';
  if (!Number.isFinite(radius) || radius < 5 || radius > 250) fields.radius_km = '5 to 250';
  const cats = (Array.isArray(b.categories) ? b.categories : String(b.categories || '').split(','))
    .map((c) => String(c).trim()).filter(Boolean);
  if (cats.some((c) => !CATS.includes(c))) fields.categories = CATS.join(' | ');
  return { lat: round2(lat), lng: round2(lng), radius_km: radius, categories: [...new Set(cats)].sort().join(','), units: b.units === 'mi' ? 'mi' : 'km' };
}

async function owned(env, b) {
  const id = line(b.id, 40), tok = String(b.manage_token || '');
  if (!id || !tok) fail(400, 'invalid');
  const s = await env.DB.prepare('SELECT * FROM push_subs WHERE id = ?1').bind(id).first();
  if (!s || s.manage_token_hash !== await hash(env, 'push|' + tok, 43)) fail(404, 'not_found');
  return s;
}

export async function pushApi(req, env, p, ctx, body) {
  const b = await body(req);
  if (p === '/v1/push/subscribe') {
    const fields = {};
    if (!validEndpoint(b.endpoint)) fields.endpoint = 'push service URL';
    if (!/^[A-Za-z0-9_-]{80,100}$/.test(String(b.p256dh || ''))) fields.p256dh = 'base64url P-256 key';
    if (!/^[A-Za-z0-9_-]{16,32}$/.test(String(b.auth || ''))) fields.auth = 'base64url secret';
    const a = area(b, fields);
    if (Object.keys(fields).length) fail(400, 'invalid', { fields });
    const ip = clientIp(req, env);
    if (!(await turnstileOk(env, b.turnstile, ip))) fail(403, 'turnstile');
    if (await rateLimited(env, [[`push|ip|${await hash(env, ip)}`, 10, 3600]])) fail(429, 'slow');
    const token = randomId(24);
    const prev = await env.DB.prepare('SELECT id FROM push_subs WHERE endpoint = ?1').bind(b.endpoint).first();
    const id = prev ? prev.id : randomId(9);
    await env.DB.prepare(
      `INSERT INTO push_subs (id, endpoint, p256dh, auth, manage_token_hash, lat, lng, radius_km, categories, units)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
       ON CONFLICT (endpoint) DO UPDATE SET p256dh = ?3, auth = ?4, manage_token_hash = ?5, lat = ?6, lng = ?7, radius_km = ?8,
         categories = ?9, units = ?10, active = 1, fail_count = 0, role = ''`,
    ).bind(id, b.endpoint, b.p256dh, b.auth, await hash(env, 'push|' + token, 43), a.lat, a.lng, a.radius_km, a.categories, a.units).run();
    if (!prev) ctx.waitUntil(tellMike(env, a).catch((e) => console.error(e)));
    return json({ state: 'ok', id, manage_token: token }, 201);
  }
  if (p === '/v1/push/update') {
    const s = await owned(env, b);
    const fields = {};
    const a = area(b, fields);
    if (Object.keys(fields).length) fail(400, 'invalid', { fields });
    await env.DB.prepare('UPDATE push_subs SET lat = ?2, lng = ?3, radius_km = ?4, categories = ?5, units = ?6, active = 1 WHERE id = ?1')
      .bind(s.id, a.lat, a.lng, a.radius_km, a.categories, a.units).run();
    return json({ state: 'ok' });
  }
  if (p === '/v1/push/unsubscribe') {
    const s = await owned(env, b);
    await env.DB.prepare('UPDATE push_subs SET active = 0 WHERE id = ?1').bind(s.id).run();
    return json({ state: 'ok' });
  }
  return json({ state: 'not_found' }, 404);
}

// Mike hears about every new alert subscriber (email plus his phone), like email signups. Only the rough area.
async function tellMike(env, a) {
  const what = a.categories ? a.categories.replace(/,/g, ', ') : 'everything';
  const where = `${a.lat.toFixed(1)}, ${a.lng.toFixed(1)} (within ${a.radius_km} km)`;
  const jobs = [];
  if (env.OWNER_EMAIL) {
    jobs.push(sendEmail(env, {
      to: [env.OWNER_EMAIL], subject: 'New sighting-alert subscriber',
      ...emailLayout({ preheader: where, heading: 'Someone turned on sighting alerts', signature: false,
        paras: [`Area: <strong>${esc(where)}</strong>`, `Alerts for: ${esc(what)}`],
        text: `Someone turned on sighting alerts.\nArea: ${where}\nAlerts for: ${what}` }),
    }));
  }
  jobs.push(sendToMods(env, { kind: 'info', title: 'New alert subscriber', body: `${where}, ${what}`, url: `${env.SITE}/near-me/` }));
  await Promise.all(jobs);
}

// Sends to a set of subscription rows; dead ones (404/410) are switched off, 5 failures in a row too.
// Local dev (PUSH_MODE=log): nothing leaves the machine; each push is logged for the tests, and an endpoint
// containing /gone answers 410 like an expired subscription.
async function deliver(env, rows, payloadFor, opts) {
  const v = vapid(env), logMode = env.PUSH_MODE === 'log';
  if ((!v && !logMode) || !rows.length) return { sent: 0 };
  let sent = 0;
  for (let i = 0; i < rows.length; i += BATCH) {
    await Promise.all(rows.slice(i, i + BATCH).map(async (s) => {
      let status = 0;
      try {
        if (logMode) { status = s.endpoint.includes('/gone') ? 410 : 201; console.log('PUSHLOG ' + JSON.stringify({ to: s.id, payload: payloadFor(s) })); }
        else ({ status } = await sendPush(s, payloadFor(s), v, opts));
      } catch (e) { console.error('push', e); }
      if (status >= 200 && status < 300) {
        sent++;
        await env.DB.prepare('UPDATE push_subs SET fail_count = 0 WHERE id = ?1').bind(s.id).run();
      } else if (status === 404 || status === 410) {
        await env.DB.prepare('UPDATE push_subs SET active = 0 WHERE id = ?1').bind(s.id).run();
      } else {
        await env.DB.prepare('UPDATE push_subs SET fail_count = fail_count + 1, active = CASE WHEN fail_count + 1 >= 5 THEN 0 ELSE active END WHERE id = ?1')
          .bind(s.id).run();
      }
    }));
  }
  return { sent };
}

const what = (r) => (r.creature === 'other' ? r.other_what || 'sighting' : CREATURES[r.creature] || 'sighting');
const clean = (s, fallback) => (BLOCKED.test(s) ? fallback : s);

// Which active reader subscriptions an approved report reaches, and whether each is still under today's cap.
export async function matchSubs(env, r) {
  const pt = publicPoint(r);
  const cat = category(r.creature);
  const dlat = 250 / 111 + 0.05;
  const rows = (await env.DB.prepare(
    `SELECT * FROM push_subs WHERE active = 1 AND role = '' AND lat BETWEEN ?1 AND ?2`,
  ).bind(pt.lat - dlat, pt.lat + dlat).all()).results;
  const day = today();
  const out = [];
  for (const s of rows) {
    const km = haversineKm(s.lat, s.lng, pt.lat, pt.lon);
    if (km > s.radius_km) continue;
    if (s.categories && !s.categories.split(',').includes(cat)) continue;
    const used = s.sent_day === day ? s.sent_today : 0;
    out.push({ s, km, capped: used >= DAILY_CAP });
  }
  return out;
}

// Called (in waitUntil) when a report is approved: alert every subscriber whose saved area contains it.
export async function notifyNearby(env, pid) {
  const r = await env.DB.prepare(`SELECT * FROM reports WHERE pid = ?1 AND status = 'approved'`).bind(pid).first();
  if (!r) return { sent: 0 };
  const day = today();
  const hits = (await matchSubs(env, r)).filter((x) => !x.capped);
  if (!hits.length) return { sent: 0 };
  // Count the alert before sending, so two approvals at once can't both slip under the cap.
  await env.DB.batch(hits.map(({ s }) => env.DB.prepare(
    `UPDATE push_subs SET sent_today = CASE WHEN sent_day = ?2 THEN sent_today + 1 ELSE 1 END, sent_day = ?2, last_sent_at = ?3 WHERE id = ?1`,
  ).bind(s.id, day, new Date().toISOString())));
  const kmOf = new Map(hits.map((x) => [x.s.id, x.km]));
  const region = LIVING_TRADITIONS.has(r.creature);
  const name = what(r);
  const label = category(r.creature) === 'ufo' && name.toLowerCase().indexOf('ufo') === -1 ? `${name} (UFO)` : name;
  const site = String(env.SITE || 'https://encounteratlas.com').replace(/\/$/, '');
  const body = clean(summary([r.place, r.story].filter(Boolean).join(': '), 140), 'Tap to read the report.');
  return deliver(env, hits.map((x) => x.s), (s) => {
    const km = kmOf.get(s.id);
    const dist = s.units === 'mi' ? `${Math.max(1, Math.round(km / 1.609344))} mi` : `${Math.max(1, Math.round(km))} km`;
    return {
      kind: 'alert', id: r.pid,
      title: clean(region ? `New ${label} report in your region` : `New ${label} report ${dist} away`, 'New report near you'),
      body, url: `${site}/reports/?id=${r.pid}&source=alert`,
    };
  });
}

// ---------- moderation by notification ----------

async function modKey(env) {
  if (!env.MOD_PUSH_KEY) return null;
  return crypto.subtle.importKey('raw', new TextEncoder().encode(env.MOD_PUSH_KEY), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}
// A button token is good for one report, one action, 7 days. It only ever goes to Mike's own devices (encrypted).
export async function actToken(env, pid, act) {
  const k = await modKey(env);
  if (!k) return '';
  const exp = now() + 7 * 86400;
  const sig = await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(`mp|${pid}|${act}|${exp}`));
  return `${exp}.${b64u(sig)}`;
}
export async function checkActToken(env, pid, act, t) {
  const k = await modKey(env);
  const [exp, sig] = String(t || '').split('.');
  if (!k || !sig || !(Number(exp) > now())) return false;
  try {
    const raw = Uint8Array.from(atob(sig.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((sig.length + 3) % 4)), (c) => c.charCodeAt(0));
    return await crypto.subtle.verify('HMAC', k, raw, new TextEncoder().encode(`mp|${pid}|${act}|${exp}`));
  } catch { return false; }
}

export async function sendToMods(env, payload) {
  const rows = (await env.DB.prepare(`SELECT * FROM push_subs WHERE active = 1 AND role = 'mod'`).all()).results;
  return deliver(env, rows, () => payload, { urgency: 'high' });
}

// New pending report -> Mike's phone, with Approve / Reject buttons (handled by /mod/sw.js -> POST /mod/push-act).
export async function notifyMods(env, pid, origin) {
  const r = await env.DB.prepare('SELECT * FROM reports WHERE pid = ?1').bind(pid).first();
  if (!r) return { sent: 0 };
  return sendToMods(env, {
    kind: 'mod', id: r.pid,
    title: `New report: ${what(r)}`,
    body: summary([r.seen_date, r.place, r.story].filter(Boolean).join(' · '), 180),
    url: `${origin}/mod`,
    approve: await actToken(env, r.pid, 'approve'),
    reject: await actToken(env, r.pid, 'reject'),
  });
}

export async function registerMod(env, b) {
  if (!validEndpoint(b.endpoint) || !/^[A-Za-z0-9_-]{80,100}$/.test(String(b.p256dh || '')) || !/^[A-Za-z0-9_-]{16,32}$/.test(String(b.auth || ''))) fail(400, 'invalid');
  await env.DB.prepare(
    `INSERT INTO push_subs (id, endpoint, p256dh, auth, manage_token_hash, role) VALUES (?1, ?2, ?3, ?4, '', 'mod')
     ON CONFLICT (endpoint) DO UPDATE SET p256dh = ?3, auth = ?4, role = 'mod', active = 1, fail_count = 0`,
  ).bind(randomId(9), b.endpoint, b.p256dh, b.auth).run();
  return sendToMods(env, { kind: 'info', title: 'Moderation alerts are on', body: 'New reports will show up here with Approve and Reject buttons.', url: '/mod' });
}

// Numbers for the sitewatch digest (GET /mod/push-stats with the mod cookie, or the stats key).
export async function pushStats(env) {
  const t = now();
  const iso = (s) => new Date((t - s) * 1000).toISOString();
  const r = await env.DB.prepare(
    `SELECT SUM(active = 1 AND role = '') AS active, SUM(role = '' AND created_at > ?1) AS new_24h, SUM(role = '' AND created_at > ?2) AS new_7d,
            SUM(active = 1 AND role = 'mod') AS mod_devices FROM push_subs`,
  ).bind(iso(86400), iso(7 * 86400)).first();
  return { active: r.active || 0, new_24h: r.new_24h || 0, new_7d: r.new_7d || 0, mod_devices: r.mod_devices || 0 };
}

// Encounter Atlas API: encounter reports, email sign-in and "Real or hoax?" voting.
// Cloudflare Worker + D1 (DB). No uploads: photos come in as links only. See DEPLOY.md for setup and README-style notes.
//
// Public (CORS for SITE + EXTRA_ORIGINS):
//   GET  /api/config                      turnstile site key, vote choices, thresholds
//   POST /api/auth/start   {email, turnstile, r?}   emails a sign-in link to <SITE>/reports/?signin=...
//   POST /api/auth/verify  {t}            single-use link token -> {session, user}
//   GET  /api/me                          (Bearer session) account + own reports, any status
//   PATCH /api/me          {name}
//   POST /api/reports      multipart: data=<JSON> (videos + photo links inside; file uploads refused)   new report (pending)
//   GET  /api/reports?limit&before&creature   recent approved reports (summaries)
//   GET  /api/reports.geojson             approved reports, public (~5 km) points only
//   GET  /v1/reports/nearby?lat&lng&radius_km&days&category&limit&cursor   field app: approved reports near a point
//                                         (public cell centres rounded to 0.01 deg, no links; 60/min per IP)
//   GET  /v1/clusters?lat&lng&radius_km   "flap in progress": 3+ approved reports within 50 km in the last 3 days
//                                         (clusters.js; rounded centre, counts and dates only; 60/min per IP)
//   POST /v1/push/subscribe|update|unsubscribe   sighting alerts for a saved area (push.js)
//   GET  /api/reports/<pid>               an approved report, or your own in any status (Bearer)
//   PATCH /api/reports/<pid>              (owner) edit text/location/videos, remove photos -> back to pending
//   DELETE /api/reports/<pid>             (owner) withdraw
//   GET  /api/votes?items=a,b             counts; your vote; results once you voted AND 10+ votes
//                                         (m:<slug> mystery-of-the-day cases: results for everyone at 10+, never on the day it runs)
//   POST /api/votes        {item, choice, reason?, turnstile | pass}
//   POST /api/flag         {item, kind: 'ai'}
//   GET  /img/<id>.jpg                    approved photos only, sanitised JPEG, locked-down headers
// Moderators (password from MOD_PASSWORD, cookie session): /mod, see mod.js.

import { CREATURES } from './creatures.js';
import { sanitizeJpeg, BadImage } from './jpeg.js';
import { handleMod } from './mod.js';
import { nearby, category } from './nearby.js';
import { clusters } from './clusters.js';
import { pushApi, notifyMods, BLOCKED } from './push.js';
import { privatizePlace, publicPlace } from './place.js';
import { MOTD_SLUGS, motdIsToday } from './motd.js';
import {
  HttpError, fail, json, sign, verify, hash, randomId, randomPid, clientIp, network, int, rateLimited, turnstileOk,
  sendEmail, emailLayout, line, para, esc, now,
} from './util.js';

export const CHOICES = ['real', 'hoax', 'mis'];
export const REASONS = ['bear', 'plane', 'satellite', 'starlink', 'balloon', 'drone', 'costume', 'cgi-ai', 'pareidolia', 'other'];
const EMAIL = /^[^\s@<>()",;:]{1,64}@[^\s@<>()",;:]{1,190}\.[a-z]{2,}$/i;
const SESSION_DAYS = 90;
const LINK_MINUTES = 30;
const PASS_MINUTES = 30;
const MAX_PHOTOS = 5;
const MAX_PHOTO_BYTES = 6 * 1024 * 1024;
const MAX_BODY = 32 * 1024 * 1024;

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const p = url.pathname;
    try {
      if (p === '/mod' || p.startsWith('/mod/')) return await handleMod(req, env, url, ctx);
      if (p.startsWith('/img/')) return await image(env, p, url);
      if (!p.startsWith('/api/') && !p.startsWith('/v1/')) return new Response('Not found', { status: 404 });
      if (req.method === 'OPTIONS') return cors(req, env, new Response(null, { status: 204 }));
      return cors(req, env, await api(req, env, url, ctx));
    } catch (err) {
      if (err instanceof HttpError) return cors(req, env, json(err.body, err.status));
      console.error(err.stack || err);
      return cors(req, env, json({ state: 'error' }, 500));
    }
  },
  async scheduled(event, env) {
    const t = now();
    await env.DB.batch([
      env.DB.prepare('DELETE FROM hits WHERE at < ?1').bind(t - 3 * 86400),
      env.DB.prepare('DELETE FROM used_links WHERE at < ?1').bind(t - 2 * 86400),
    ]);
  },
};

function origins(env) {
  return [env.SITE, ...String(env.EXTRA_ORIGINS || '').split(',')].map((s) => s.trim()).filter(Boolean);
}

function cors(req, env, res) {
  const o = req.headers.get('origin');
  if (o && origins(env).includes(o)) {
    res = new Response(res.body, res);
    res.headers.set('access-control-allow-origin', o);
    res.headers.set('access-control-allow-methods', 'GET, POST, PATCH, DELETE, OPTIONS');
    res.headers.set('access-control-allow-headers', 'content-type, authorization');
    res.headers.set('access-control-max-age', '86400');
    res.headers.append('vary', 'origin');
  }
  return res;
}

async function api(req, env, url, ctx) {
  const p = url.pathname, m = req.method;
  if (p === '/api/config' && m === 'GET') {
    return json({ turnstile: env.TURNSTILE_SITEKEY, choices: CHOICES, reasons: REASONS, threshold: int(env, 'VOTE_THRESHOLD', 10) },
      200, { 'cache-control': 'public, max-age=300' });
  }
  if (p === '/api/auth/start' && m === 'POST') return authStart(req, env);
  if (p === '/api/auth/verify' && m === 'POST') return authVerify(req, env);
  if (p === '/api/me' && m === 'GET') return me(req, env);
  if (p === '/api/me' && m === 'PATCH') return updateMe(req, env);
  if (p === '/api/reports' && m === 'POST') return submit(req, env, ctx);
  if (p === '/api/reports' && m === 'GET') return listReports(env, url);
  if (p === '/api/reports.geojson' && m === 'GET') return geojson(env);
  if (p === '/v1/reports/nearby' && m === 'GET') return nearby(req, env, url, ctx);
  if (p === '/v1/clusters' && m === 'GET') return clusters(req, env, url, ctx);
  if (p.startsWith('/v1/push/') && m === 'POST') return pushApi(req, env, p, ctx, body);
  const rm = p.match(/^\/api\/reports\/([a-z0-9]{10})$/);
  if (rm && m === 'GET') return getReport(req, env, rm[1]);
  if (rm && m === 'PATCH') return editReport(req, env, rm[1]);
  if (rm && m === 'DELETE') return withdrawReport(req, env, rm[1]);
  if (p === '/api/votes' && m === 'GET') return getVotes(req, env, url);
  if (p === '/api/votes' && m === 'POST') return castVote(req, env);
  if (p === '/api/flag' && m === 'POST') return flag(req, env);
  if (p === '/api/contact' && m === 'POST') return contact(req, env);
  return json({ state: 'not_found' }, 404);
}

async function body(req) {
  if (Number(req.headers.get('content-length') || 0) > 64 * 1024) fail(413, 'too_big');
  return req.json().catch(() => fail(400, 'bad_json'));
}

// ---------------- contact form ----------------

export const TOPICS = { general: 'General', advertise: 'Advertising', correction: 'Correction or source', takedown: 'Takedown or privacy', press: 'Press' };

// Emails the message to CONTACT_TO (default hello@) with reply-to set to the sender. Nothing is stored except rate-limit rows.
async function contact(req, env) {
  const b = await body(req);
  if (line(b.website, 100)) return json({ state: 'ok' });  // honeypot: bots fill the hidden field
  const name = line(b.name, 100), email = line(b.email, 254).toLowerCase(), message = para(b.message, 5000);
  const topic = TOPICS[b.topic] ? b.topic : 'general';
  if (!EMAIL.test(email)) fail(400, 'email');
  if (message.length < 10) fail(400, 'message');
  const ip = clientIp(req, env);
  if (!(await turnstileOk(env, b.turnstile, ip))) fail(403, 'turnstile');
  const iph = await hash(env, ip);
  if (await rateLimited(env, [[`contact|ip|${iph}`, 4, 3600], [`contact|em|${await hash(env, email)}`, 6, 86400]])) fail(429, 'slow');
  const res = await sendEmail(env, {
    to: [env.CONTACT_TO || 'hello@encounteratlas.com'], reply_to: email,
    subject: `[Encounter Atlas] ${TOPICS[topic]}: ${name || email}`,
    ...emailLayout({
      preheader: message.slice(0, 120), heading: `New message: ${TOPICS[topic]}`, signature: false,
      paras: [`<strong>From:</strong> ${esc(name || '(no name)')} &lt;${esc(email)}&gt;`, esc(message).replace(/\n/g, '<br>')],
      footer: 'Sent from the contact form on encounteratlas.com. Reply to this email to answer them directly.',
      text: `From: ${name || '(no name)'} <${email}>\nTopic: ${TOPICS[topic]}\n\n${message}`,
    }),
  });
  return json({ state: 'ok', ...(res.logged ? { logged: true } : {}) });
}

// ---------------- accounts ----------------

async function session(req, env, required = true) {
  const h = req.headers.get('authorization') || '';
  const t = h.startsWith('Bearer ') ? h.slice(7) : '';
  const pl = t ? await verify(env, t) : null;
  if (!pl || pl[0] !== 's' || now() - Number(pl[2]) > SESSION_DAYS * 86400) {
    if (required) fail(401, 'signin');
    return null;
  }
  const u = await env.DB.prepare('SELECT * FROM users WHERE id = ?1').bind(Number(pl[1])).first();
  if (!u || u.banned) {
    if (required) fail(401, 'signin');
    return null;
  }
  if (now() - u.last_seen > 3600) await env.DB.prepare('UPDATE users SET last_seen = ?1 WHERE id = ?2').bind(now(), u.id).run();
  return u;
}

async function authStart(req, env) {
  const b = await body(req);
  const email = line(b.email, 254).toLowerCase();
  if (!EMAIL.test(email)) fail(400, 'email');
  const ip = clientIp(req, env);
  if (!(await turnstileOk(env, b.turnstile, ip))) fail(403, 'turnstile');
  const iph = await hash(env, ip);
  if (await rateLimited(env, [[`auth|ip|${iph}`, 6, 3600], [`auth|em|${await hash(env, email)}`, 3, 3600]])) fail(429, 'slow');
  const r = /^[a-z0-9]{10}$/.test(b.r || '') ? b.r : '';
  return json({ state: 'sent', ...(await mailLink(env, email, r, 'signin')) });
}

async function mailLink(env, email, r, why) {
  const t = await sign(env, `l|${email}|${now()}|${randomId(8)}|${r}`);
  const link = `${env.SITE}/reports/?signin=${encodeURIComponent(t)}`;
  const intro = why === 'report'
    ? 'Thanks for your report. It will appear on the map once a moderator has checked it. Use this link to sign in, follow it and make changes:'
    : 'Here is your sign-in link for Encounter Atlas. It lets you vote and edit your reports:';
  const note = `The link works once, for ${LINK_MINUTES} minutes. If you didn't ask for it, you can ignore this email.`;
  const res = await sendEmail(env, {
    to: [email], reply_to: env.CONTACT_TO || 'hello@encounteratlas.com',
    subject: why === 'report' ? 'Your encounter report' : 'Your Encounter Atlas sign-in link',
    ...emailLayout({
      preheader: why === 'report' ? 'Thanks for your report. Here is your link to follow it.' : 'Your one-time sign-in link.',
      heading: why === 'report' ? 'Thanks for your report' : 'Your sign-in link',
      paras: [esc(intro)], button: { href: link, label: 'Sign in to Encounter Atlas' }, note: esc(note),
      text: `${intro}\n\n${link}\n\n${note}`,
    }),
  });
  return res.logged && env.DEV === '1' ? { dev_link: link } : {};
}

async function authVerify(req, env) {
  const b = await body(req);
  const pl = await verify(env, b.t);
  if (!pl || pl[0] !== 'l') fail(400, 'invalid');
  const [, email, ts, nonce, r] = pl;
  if (now() - Number(ts) > LINK_MINUTES * 60) fail(400, 'expired');
  const fresh = await env.DB.prepare('INSERT OR IGNORE INTO used_links (nonce) VALUES (?1)').bind(nonce).run();
  if (!fresh.meta.changes) fail(400, 'used');
  const u = await env.DB.prepare(
    `INSERT INTO users (email) VALUES (?1) ON CONFLICT (email) DO UPDATE SET last_seen = unixepoch() RETURNING *`,
  ).bind(email).first();
  if (u.banned) fail(403, 'banned');
  return json({ state: 'ok', session: await sign(env, `s|${u.id}|${now()}`), user: publicUser(u), r: r || '' });
}

function publicUser(u) {
  return { email: u.email, name: u.name, since: u.created };
}

async function me(req, env) {
  const u = await session(req, env);
  const reports = (await env.DB.prepare(
    `SELECT pid AS id, status, creature, other_what, seen_date, place, created, mod_note FROM reports
     WHERE user_id = ?1 AND status != 'withdrawn' ORDER BY created DESC LIMIT 100`,
  ).bind(u.id).all()).results;
  return json({ user: { ...publicUser(u), weight: await weightFor(env, u) }, reports });
}

async function updateMe(req, env) {
  const u = await session(req, env);
  const b = await body(req);
  await env.DB.prepare('UPDATE users SET name = ?1 WHERE id = ?2').bind(line(b.name, 40), u.id).run();
  return json({ state: 'ok' });
}

// New accounts count for less until they're older or have done something real.
export async function weightFor(env, u) {
  const age = (now() - u.created) / 86400;
  const s = await env.DB.prepare(
    `SELECT (SELECT COUNT(*) FROM reports WHERE user_id = ?1 AND status = 'approved') AS rep,
            (SELECT COUNT(*) FROM votes WHERE user_id = ?1 AND voided = 0) AS votes`,
  ).bind(u.id).first();
  const active = s.rep > 0 || s.votes >= 10;
  if (age < 1) return active ? 0.5 : 0.2;
  if (age < 7) return active ? 0.8 : 0.5;
  return 1;
}

// ---------------- reports ----------------

// ~5 km grid: the public point is the centre of the cell the real point falls in, so it can't be
// averaged back out across edits the way random jitter can.
// Living traditions (site/build.py LIVING_TRADITIONS) are only mapped to the nearest region: a ~100 km grid.
export const LIVING_TRADITIONS = new Set(['skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
  'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo']);
export function fuzz(lat, lon, region = false) {
  const step = region ? 0.9 : 0.045; // ~100 km or ~5 km of latitude
  const plat = Math.round(lat / step) * step;
  const lstep = step / Math.max(0.15, Math.cos((plat * Math.PI) / 180));
  let plon = Math.round(lon / lstep) * lstep;
  if (plon > 180) plon -= 360;
  if (plon < -180) plon += 360;
  return [Math.round(plat * 1e4) / 1e4, Math.round(plon * 1e4) / 1e4];
}

export function normalizeVideo(raw) {
  let u;
  try { u = new URL(String(raw).trim()); } catch { return null; }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
  const host = u.hostname.toLowerCase().replace(/^(www|m|music)\./, '');
  const seg = u.pathname.split('/').filter(Boolean);
  const yt = /^[A-Za-z0-9_-]{11}$/;
  if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
    let id = u.searchParams.get('v');
    if (!id && ['shorts', 'live', 'embed'].includes(seg[0])) id = seg[1];
    if (id && yt.test(id)) return { p: 'youtube', id, url: `https://www.youtube.com/watch?v=${id}` };
  } else if (host === 'youtu.be') {
    if (seg[0] && yt.test(seg[0])) return { p: 'youtube', id: seg[0], url: `https://www.youtube.com/watch?v=${seg[0]}` };
  } else if (host === 'tiktok.com') {
    const i = seg.indexOf('video');
    if (seg[0]?.startsWith('@') && i === 1 && /^\d{8,25}$/.test(seg[2] || '') && /^@[\w.]{1,30}$/.test(seg[0]))
      return { p: 'tiktok', id: seg[2], url: `https://www.tiktok.com/${seg[0]}/video/${seg[2]}` };
  } else if (host === 'vm.tiktok.com' || host === 'vt.tiktok.com') {
    if (/^[A-Za-z0-9]{5,15}$/.test(seg[0] || '')) return { p: 'tiktok', id: seg[0], url: `https://${host}/${seg[0]}/` };
  } else if (host === 'vimeo.com') {
    if (/^\d{4,12}$/.test(seg[0] || '')) return { p: 'vimeo', id: seg[0], url: `https://vimeo.com/${seg[0]}` };
  } else if (host === 'player.vimeo.com') {
    if (seg[0] === 'video' && /^\d{4,12}$/.test(seg[1] || '')) return { p: 'vimeo', id: seg[1], url: `https://vimeo.com/${seg[1]}` };
  }
  return null;
}

// Validates the report fields. Throws HttpError 400 {state:'invalid', fields:{name: why}}.
function readFields(d) {
  const bad = {};
  const r = {};
  r.creature = line(d.creature, 60);
  if (r.creature !== 'other' && !CREATURES[r.creature]) bad.creature = 'Pick what you saw';
  r.other_what = r.creature === 'other' ? line(d.other_what, 80) : '';
  if (r.creature === 'other' && r.other_what.length < 2) bad.other_what = 'Say what it was, in a few words';
  r.seen_date = line(d.seen_date, 10);
  const dt = /^\d{4}-\d{2}-\d{2}$/.test(r.seen_date) ? Date.parse(r.seen_date + 'T00:00:00Z') : NaN;
  if (!Number.isFinite(dt) || dt > Date.now() + 2 * 86400e3 || r.seen_date < '1900-01-01') bad.seen_date = 'Enter the date it happened';
  r.seen_time = line(d.seen_time, 5);
  if (r.seen_time && !/^([01]\d|2[0-3]):[0-5]\d$/.test(r.seen_time)) bad.seen_time = 'Use a time like 21:30';
  r.date_approx = d.date_approx ? 1 : 0;
  r.lat = Number(d.lat);
  r.lon = Number(d.lon);
  if (d.lat === '' || d.lat == null || !Number.isFinite(r.lat) || !Number.isFinite(r.lon) || Math.abs(r.lat) > 90 || Math.abs(r.lon) > 180)
    bad.location = 'Set the place on the map';
  r.loc_source = ['gps', 'map', 'place'].includes(d.loc_source) ? d.loc_source : 'map';
  r.place = line(d.place, 120);
  r.story = para(d.story, 6000);
  if (r.story.length < 30) bad.story = 'Tell us what happened (a few sentences)';
  r.duration = line(d.duration, 80);
  r.sounds = para(d.sounds, 600);
  r.smells = para(d.smells, 600);
  r.witnesses = Math.min(999, Math.max(1, Math.round(Number(d.witnesses) || 1)));
  r.display_name = line(d.display_name, 40);
  r.anonymous = d.anonymous === false || d.anonymous === 0 ? 0 : 1;
  if (!r.display_name) r.anonymous = 1;
  const vids = Array.isArray(d.videos) ? d.videos.map((v) => String(v || '').trim()).filter(Boolean) : [];
  if (vids.length > 5) bad.videos = 'Up to 5 video links';
  r.videos = [];
  vids.slice(0, 5).forEach((v) => {
    const n = normalizeVideo(v);
    if (!n) bad.videos = 'Only YouTube, TikTok or Vimeo links';
    else if (!r.videos.some((x) => x.url === n.url)) r.videos.push(n);
  });
  // Photo links: we never take uploads, only https links to wherever the witness hosts the photo.
  const lks = Array.isArray(d.links) ? d.links.map((v) => String(v || '').trim()).filter(Boolean) : [];
  if (lks.length > 5) bad.links = 'Up to 5 photo links';
  r.links = [];
  lks.slice(0, 5).forEach((v) => {
    const n = normalizeLink(v);
    if (!n) bad.links = 'Photo links must be full https:// web addresses';
    else if (!r.links.some((x) => x.url === n.url)) r.links.push(n);
  });
  // Links to other sighting databases and competitor hubs never reach /mod (Mike's rule): ask for their own words.
  if (r.links.some((l) => BLOCKED.test(l.host)) || BLOCKED.test(r.story) || BLOCKED.test(r.place)) {
    const msg = 'Links to other sighting databases can\'t be used here. Please remove it and tell it in your own words.';
    if (r.links.some((l) => BLOCKED.test(l.host))) bad.links = msg; else bad.story = msg;
  }
  r.sky = skyCheck(d.sky_check, r.creature);
  if (Object.keys(bad).length) fail(400, 'invalid', { fields: bad });
  [r.pub_lat, r.pub_lon] = fuzz(r.lat, r.lon, LIVING_TRADITIONS.has(r.creature));
  return r;
}

// A place that looks like a street address becomes its area, and the stored point is snapped (see place.js).
async function withPrivatePlace(r) {
  if (await privatizePlace(r)) [r.pub_lat, r.pub_lon] = fuzz(r.lat, r.lon, LIVING_TRADITIONS.has(r.creature));
  return r;
}

// "Was it a planet?" result from the form (UFO reports only): which bright things lined up, and the witness's answer.
function skyCheck(v, creature) {
  if (!v || typeof v !== 'object' || category(creature) !== 'ufo') return null;
  const candidates = (Array.isArray(v.candidates) ? v.candidates : []).map((c) => line(c, 40)).filter(Boolean).slice(0, 6);
  const answer = v.answer === 'no' && candidates.length ? 'no' : 'none';
  return JSON.stringify({ candidates, answer });
}

// A public https web address on a real hostname (no IPs, no localhost, no credentials), max 500 chars.
export function normalizeLink(v) {
  if (v.length > 500) return null;
  let u;
  try { u = new URL(v); } catch { return null; }
  if (u.protocol !== 'https:' || u.username || u.password || u.port) return null;
  const host = u.hostname.toLowerCase();
  if (!/^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$/.test(host) || host === 'localhost') return null;
  u.hash = '';
  return { url: u.href, host: host.replace(/^www\./, '') };
}

async function submit(req, env, ctx) {
  if (Number(req.headers.get('content-length') || 0) > MAX_BODY) fail(413, 'too_big');
  const ctype = req.headers.get('content-type') || '';
  if (!ctype.startsWith('multipart/form-data')) fail(400, 'multipart');
  const form = await req.formData().catch(() => fail(400, 'bad_form'));
  let d;
  try { d = JSON.parse(String(form.get('data') || '')); } catch { fail(400, 'bad_json'); }
  if (d.website) return json({ state: 'ok', id: randomPid(), status: 'pending' }); // honeypot: pretend
  const user = await session(req, env, false);
  const ip = clientIp(req, env);
  if (!(await turnstileOk(env, d.turnstile, ip))) fail(403, 'turnstile');
  const f = await withPrivatePlace(readFields(d));
  const email = user ? '' : line(d.email, 254).toLowerCase();
  if (email && !EMAIL.test(email)) fail(400, 'invalid', { fields: { email: 'Check your email address' } });

  // Uploads are switched off for good (Mike, 2026-10-12): photos come in as links only.
  if (form.getAll('photo').length) fail(400, 'invalid', { fields: { links: 'We don\'t take uploads. Paste a link to the photo instead.' } });
  const iph = await hash(env, ip);
  const rules = [[`rep|ip|${iph}`, int(env, 'REPORTS_IP_HOUR', 3), 3600], [`rep|ipd|${iph}`, int(env, 'REPORTS_IP_DAY', 10), 86400]];
  if (user) rules.push([`rep|u|${user.id}`, int(env, 'REPORTS_USER_DAY', 6), 86400]);
  if (await rateLimited(env, rules)) fail(429, 'slow');

  let uid = user ? user.id : null;
  if (!uid && email) {
    const u = await env.DB.prepare('INSERT INTO users (email) VALUES (?1) ON CONFLICT (email) DO UPDATE SET email = email RETURNING id')
      .bind(email).first();
    uid = u.id;
  }
  const pid = randomPid();
  const row = await env.DB.prepare(
    `INSERT INTO reports (pid, user_id, creature, other_what, seen_date, seen_time, date_approx, lat, lon, pub_lat, pub_lon,
       loc_source, place, story, duration, sounds, smells, witnesses, display_name, anonymous, videos, ip_hash, links)
     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, ?19, ?20, ?21, ?22, ?23) RETURNING id`,
  ).bind(pid, uid, f.creature, f.other_what, f.seen_date, f.seen_time, f.date_approx, f.lat, f.lon, f.pub_lat, f.pub_lon,
    f.loc_source, f.place, f.story, f.duration, f.sounds, f.smells, f.witnesses, f.display_name, f.anonymous,
    JSON.stringify(f.videos), iph, JSON.stringify(f.links)).first();
  if (f.sky) await env.DB.prepare('INSERT INTO report_sky (report_id, data) VALUES (?1, ?2)').bind(row.id, f.sky).run();
  ctx.waitUntil(notifyMods(env, pid, new URL(req.url).origin).catch((e) => console.error(e)));
  let extra = {};
  if (!user && email) extra = await mailLink(env, email, pid, 'report').catch((e) => (console.error(e), {}));
  if (env.OWNER_EMAIL) {
    const what = f.creature === 'other' ? f.other_what : CREATURES[f.creature];
    const modUrl = new URL('/mod', req.url).href;
    ctx.waitUntil(sendEmail(env, {
      to: [env.OWNER_EMAIL], subject: `New encounter report: ${what}`,
      ...emailLayout({
        preheader: `${what}, ${f.seen_date}`, heading: `New report: ${what}`, signature: false,
        paras: [`<strong>${esc(f.seen_date)}</strong> · ${esc(f.place || 'no place name')}`, esc(f.story.slice(0, 600)).replace(/\n/g, '<br>')],
        button: { href: modUrl, label: 'Review in moderation' },
        text: `${what}, ${f.seen_date}, ${f.place || 'no place name'}\n\n${f.story.slice(0, 600)}\n\nReview: ${modUrl}`,
      }),
    }).catch((e) => console.error(e)));
  }
  return json({ state: 'ok', id: pid, status: 'pending', ...extra }, 201);
}

const photoUrl = (env, id) => `/img/${id}.jpg`;

function publicReport(env, r, photos) {
  const vids = JSON.parse(r.videos || '[]');
  return {
    id: r.pid, creature: r.creature, creature_name: CREATURES[r.creature] || '', other_what: r.other_what,
    seen_date: r.seen_date, seen_time: r.seen_time, date_approx: !!r.date_approx,
    lat: r.pub_lat, lon: r.pub_lon, approx_km: 5, place: publicPlace(r.place),
    story: r.story, duration: r.duration, sounds: r.sounds, smells: r.smells, witnesses: r.witnesses,
    name: r.anonymous ? null : r.display_name || null,
    photos: photos.map((p) => ({ id: p.id, url: photoUrl(env, p.id), w: p.w, h: p.h, item: `p:${p.id}` })),
    videos: vids.map((v, i) => ({ provider: v.p, id: v.id, url: v.url, item: `v:${r.pid}:${i}` })),
    links: JSON.parse(r.links || '[]'),
    item: `r:${r.pid}`, created: r.created, approved_at: r.approved_at,
  };
}

async function getReport(req, env, pid) {
  const r = await env.DB.prepare('SELECT * FROM reports WHERE pid = ?1').bind(pid).first();
  if (!r) fail(404, 'not_found');
  let owner = false;
  if (r.status !== 'approved' || req.headers.get('authorization')) {
    const u = await session(req, env, false);
    owner = !!(u && r.user_id === u.id);
    if (!owner && r.status !== 'approved') fail(404, 'not_found');
  }
  const photos = (await env.DB.prepare('SELECT id, w, h FROM photos WHERE report_id = ?1 AND removed = 0 ORDER BY idx')
    .bind(r.id).all()).results;
  const out = publicReport(env, r, photos);
  if (owner) {
    // Owner view: exact point and status, for editing. Photo URLs for unapproved reports go through /img
    // with the owner's session, so they aren't public.
    Object.assign(out, { owner: true, status: r.status, exact: { lat: r.lat, lon: r.lon }, loc_source: r.loc_source,
      display_name: r.display_name, anonymous: !!r.anonymous, mod_note: r.mod_note });
    if (r.status !== 'approved') {
      for (const p of out.photos) p.url = `/img/${p.id}.jpg?k=${encodeURIComponent(await sign(env, `i|${p.id}|${now()}`))}`;
    }
  }
  return json({ report: out }, 200, { 'cache-control': owner ? 'private, no-store' : 'public, max-age=60' });
}

async function listReports(env, url) {
  const limit = Math.min(50, Math.max(1, Number(url.searchParams.get('limit')) || 24));
  const before = Number(url.searchParams.get('before')) || 4e9;
  const creature = url.searchParams.get('creature') || '';
  const where = ['status = \'approved\'', 'approved_at < ?1'];
  const args = [before];
  if (creature && (CREATURES[creature] || creature === 'other')) { where.push('creature = ?2'); args.push(creature); }
  const rows = (await env.DB.prepare(
    `SELECT r.*, (SELECT id FROM photos WHERE report_id = r.id AND removed = 0 ORDER BY idx LIMIT 1) AS photo,
            (SELECT COUNT(*) FROM photos WHERE report_id = r.id AND removed = 0) AS n_photos
     FROM reports r WHERE ${where.join(' AND ')} ORDER BY approved_at DESC LIMIT ${limit + 1}`,
  ).bind(...args).all()).results;
  const more = rows.length > limit;
  const reports = rows.slice(0, limit).map((r) => ({
    id: r.pid, creature: r.creature, creature_name: CREATURES[r.creature] || '', other_what: r.other_what,
    seen_date: r.seen_date, date_approx: !!r.date_approx, place: publicPlace(r.place), lat: r.pub_lat, lon: r.pub_lon,
    snippet: r.story.length > 220 ? r.story.slice(0, 210).replace(/\s+\S*$/, '') + '…' : r.story,
    photo: r.photo ? photoUrl(env, r.photo) : null, n_photos: r.n_photos, n_videos: JSON.parse(r.videos).length,
    n_links: JSON.parse(r.links || '[]').length,
    witnesses: r.witnesses, approved_at: r.approved_at,
  }));
  return json({ reports, next: more ? reports[reports.length - 1].approved_at : null }, 200, { 'cache-control': 'public, max-age=60' });
}

// First ~160 characters of the story, cut at a word, for map popups.
function snip(t) {
  t = String(t || '').replace(/\s+/g, ' ').trim();
  return t.length <= 160 ? t : t.slice(0, 160).replace(/\s+\S*$/, '') + '…';
}

async function geojson(env) {
  const rows = (await env.DB.prepare(
    `SELECT pid, creature, other_what, seen_date, place, pub_lat, pub_lon, substr(story, 1, 220) AS story FROM reports
     WHERE status = 'approved' ORDER BY approved_at DESC LIMIT 20000`,
  ).all()).results;
  const features = rows.map((r) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [r.pub_lon, r.pub_lat] },
    properties: { id: r.pid, c: r.creature, n: r.creature === 'other' ? r.other_what : CREATURES[r.creature] || '',
      t: publicPlace(r.place), d: r.seen_date, s: snip(r.story) },
  }));
  return json({ type: 'FeatureCollection', features }, 200, { 'cache-control': 'public, max-age=300' });
}

async function ownReport(req, env, pid) {
  const u = await session(req, env);
  const r = await env.DB.prepare('SELECT * FROM reports WHERE pid = ?1').bind(pid).first();
  if (!r || r.user_id !== u.id || r.status === 'withdrawn') fail(404, 'not_found');
  return { u, r };
}

async function editReport(req, env, pid) {
  const { u, r } = await ownReport(req, env, pid);
  if (await rateLimited(env, [[`edit|u|${u.id}`, 20, 86400]])) fail(429, 'slow');
  const b = await body(req);
  const f = await withPrivatePlace(readFields(b));
  const remove = Array.isArray(b.remove_photos) ? b.remove_photos.filter((x) => /^[0-9a-f]{24}$/.test(x)) : [];
  // Any edit goes back through moderation; the public sees nothing until it's approved again.
  await env.DB.prepare(
    `UPDATE reports SET creature=?2, other_what=?3, seen_date=?4, seen_time=?5, date_approx=?6, lat=?7, lon=?8, pub_lat=?9,
       pub_lon=?10, loc_source=?11, place=?12, story=?13, duration=?14, sounds=?15, smells=?16, witnesses=?17,
       display_name=?18, anonymous=?19, videos=?20, links=?21, status='pending', updated=unixepoch() WHERE id=?1`,
  ).bind(r.id, f.creature, f.other_what, f.seen_date, f.seen_time, f.date_approx, f.lat, f.lon, f.pub_lat, f.pub_lon,
    f.loc_source, f.place, f.story, f.duration, f.sounds, f.smells, f.witnesses, f.display_name, f.anonymous,
    JSON.stringify(f.videos), JSON.stringify(f.links)).run();
  for (const id of remove) {
    const ph = await env.DB.prepare('UPDATE photos SET removed = 1 WHERE id = ?1 AND report_id = ?2 RETURNING id').bind(id, r.id).first();
    if (ph && env.PHOTOS) await env.PHOTOS.delete(`p/${id}.jpg`);
  }
  return json({ state: 'ok', status: 'pending' });
}

async function withdrawReport(req, env, pid) {
  const { r } = await ownReport(req, env, pid);
  const ph = (await env.DB.prepare('SELECT id FROM photos WHERE report_id = ?1').bind(r.id).all()).results;
  if (ph.length && env.PHOTOS) await env.PHOTOS.delete(ph.map((p) => `p/${p.id}.jpg`));
  await env.DB.batch([
    env.DB.prepare(`UPDATE reports SET status = 'withdrawn', updated = unixepoch() WHERE id = ?1`).bind(r.id),
    env.DB.prepare('UPDATE photos SET removed = 1 WHERE report_id = ?1').bind(r.id),
  ]);
  return json({ state: 'ok' });
}

// Photos are only ever served from here: our own random key, the sanitised bytes, a fixed content type,
// nosniff, and a CSP sandbox so even a browser that tried to render it as a document couldn't run anything.
export const IMG_HEADERS = {
  'content-type': 'image/jpeg',
  'x-content-type-options': 'nosniff',
  'content-security-policy': "default-src 'none'; sandbox",
  'content-disposition': 'inline',
  'cross-origin-resource-policy': 'cross-origin',
};

async function image(env, p, url) {
  const m = p.match(/^\/img\/([0-9a-f]{24})\.jpg$/);
  if (!m || !env.PHOTOS) return new Response('Not found', { status: 404 }); // uploads are off; no photo store
  // ?k= is a short-lived signed key the API hands an owner (or moderator) for photos not yet public.
  const k = url.searchParams.get('k');
  const kp = k ? await verify(env, k) : null;
  const signed = kp && kp[0] === 'i' && kp[1] === m[1] && now() - Number(kp[2]) < 3600;
  const ok = signed ? true : await env.DB.prepare(
    `SELECT 1 FROM photos ph JOIN reports r ON r.id = ph.report_id WHERE ph.id = ?1 AND ph.removed = 0 AND r.status = 'approved'`,
  ).bind(m[1]).first();
  if (!ok) return new Response('Not found', { status: 404 });
  const obj = await env.PHOTOS.get(`p/${m[1]}.jpg`);
  if (!obj) return new Response('Not found', { status: 404 });
  return new Response(obj.body, { headers: { ...IMG_HEADERS, 'cache-control': signed ? 'private, max-age=600' : 'public, max-age=86400' } });
}

// ---------------- voting ----------------

// Resolves an item key to its report, or null if it doesn't exist / isn't public.
export async function resolveItem(env, item, any = false) {
  const st = any ? '' : ` AND r.status = 'approved'`;
  let m;
  if ((m = /^r:([a-z0-9]{10})$/.exec(item))) {
    return env.DB.prepare(`SELECT r.id, r.pid FROM reports r WHERE r.pid = ?1${st}`).bind(m[1]).first();
  }
  if ((m = /^p:([0-9a-f]{24})$/.exec(item))) {
    return env.DB.prepare(`SELECT r.id, r.pid FROM photos ph JOIN reports r ON r.id = ph.report_id WHERE ph.id = ?1 AND ph.removed = 0${st}`)
      .bind(m[1]).first();
  }
  // Witness stories (site/sections/stories.py): ids are slugs. Unknown ids just collect votes nobody sees.
  if ((m = /^s:([a-z0-9][a-z0-9-]{2,79})$/.exec(item))) return { id: 0, pid: null, story: m[1] };
  // Mystery of the day (site/sections/motd.py): only cases on the build-generated list (motd_items.js).
  if ((m = /^m:([a-z0-9][a-z0-9-]{2,79})$/.exec(item))) return MOTD_SLUGS.has(m[1]) ? { id: 0, pid: null, motd: m[1] } : null;
  if ((m = /^v:([a-z0-9]{10}):([0-4])$/.exec(item))) {
    const r = await env.DB.prepare(`SELECT r.id, r.pid, r.videos FROM reports r WHERE r.pid = ?1${st}`).bind(m[1]).first();
    return r && JSON.parse(r.videos).length > Number(m[2]) ? r : null;
  }
  return null;
}

// Weighted shares. Moderators get everything; the public only after voting, and only at 10+ votes.
export async function tally(env, item, uid, full = false) {
  const rows = (await env.DB.prepare(
    `SELECT choice, reason, COUNT(*) AS n, SUM(weight) AS w FROM votes WHERE item = ?1 AND voided = 0 AND held = 0 GROUP BY choice, reason`,
  ).bind(item).all()).results;
  const it = await env.DB.prepare('SELECT frozen, flag, ai_flags FROM items WHERE item = ?1').bind(item).first();
  const mine = uid ? await env.DB.prepare('SELECT choice, reason FROM votes WHERE item = ?1 AND user_id = ?2').bind(item, uid).first() : null;
  const n = rows.reduce((s, r) => s + r.n, 0);
  const threshold = int(env, 'VOTE_THRESHOLD', 10);
  const out = { item, n, threshold, frozen: !!(it && it.frozen), mine: mine ? { choice: mine.choice, reason: mine.reason } : null };
  // Mystery of the day: today's case shows no results to anyone (they go up the next UTC day); after that the
  // results are public at the threshold, voted or not, so the page can show yesterday's verdict.
  const motd = item.startsWith('m:');
  if (motd && motdIsToday(item.slice(2))) out.today = true;
  const open = motd ? !out.today : !!mine;
  if (full || (open && n >= threshold && !out.frozen)) {
    const W = rows.reduce((s, r) => s + r.w, 0) || 1;
    const share = (pred) => Math.round((1000 * rows.filter(pred).reduce((s, r) => s + r.w, 0)) / W) / 10;
    const mis = rows.filter((r) => r.choice === 'mis');
    const misW = mis.reduce((s, r) => s + r.w, 0) || 1;
    out.results = {
      real: share((r) => r.choice === 'real'), hoax: share((r) => r.choice === 'hoax'), mis: share((r) => r.choice === 'mis'),
      reasons: Object.fromEntries(REASONS.map((k) => [k, Math.round((1000 * mis.filter((r) => r.reason === k).reduce((s, r) => s + r.w, 0)) / misW) / 10])
        .filter(([, v]) => v > 0)),
    };
  }
  if (full && it) Object.assign(out, { flag: it.flag, ai_flags: it.ai_flags });
  return out;
}

async function getVotes(req, env, url) {
  const items = String(url.searchParams.get('items') || '').split(',').filter(Boolean).slice(0, 20);
  const u = await session(req, env, false);
  const out = [];
  for (const it of items) {
    if (!(await resolveItem(env, it))) continue;
    out.push(await tally(env, it, u && u.id));
  }
  return json({ items: out, signed_in: !!u }, 200, { 'cache-control': 'private, no-store' });
}

async function setFlag(env, item, flag, note, freeze = false) {
  await env.DB.prepare(
    `INSERT INTO items (item, frozen, flag, flag_note, flagged_at) VALUES (?1, ?2, ?3, ?4, unixepoch())
     ON CONFLICT (item) DO UPDATE SET frozen = MAX(frozen, ?2), flag = ?3, flag_note = ?4, flagged_at = unixepoch()`,
  ).bind(item, freeze ? 1 : 0, flag, note).run();
}

async function castVote(req, env) {
  const u = await session(req, env);
  const b = await body(req);
  const item = String(b.item || '');
  const choice = String(b.choice || '');
  if (!CHOICES.includes(choice)) fail(400, 'choice');
  const reason = choice === 'mis' ? String(b.reason || '') : '';
  if (choice === 'mis' && !REASONS.includes(reason)) fail(400, 'reason');
  if (!(await resolveItem(env, item))) fail(404, 'not_found');
  const ip = clientIp(req, env);

  // Human check: a fresh Turnstile token, or the short-lived pass we hand out after one succeeds.
  let pass = null;
  const pl = b.pass ? await verify(env, b.pass) : null;
  const passOk = pl && pl[0] === 'h' && Number(pl[1]) === u.id && now() - Number(pl[2]) < PASS_MINUTES * 60;
  if (!passOk) {
    if (!(await turnstileOk(env, b.turnstile, ip))) fail(403, 'turnstile');
    pass = await sign(env, `h|${u.id}|${now()}`);
  }

  if (await env.DB.prepare('SELECT 1 FROM votes WHERE item = ?1 AND user_id = ?2').bind(item, u.id).first()) fail(409, 'duplicate');
  const it = await env.DB.prepare('SELECT frozen FROM items WHERE item = ?1').bind(item).first();
  if (it && it.frozen) fail(423, 'frozen');

  const iph = await hash(env, ip);
  const neth = await hash(env, network(ip));
  if (await rateLimited(env, [
    [`vote|u|${u.id}`, int(env, 'VOTE_USER_HOUR', 40), 3600],
    [`vote|ud|${u.id}`, int(env, 'VOTE_USER_DAY', 200), 86400],
    [`vote|ip|${iph}`, int(env, 'VOTE_IP_HOUR', 60), 3600],
  ])) fail(429, 'slow');

  // Several accounts voting on the same item from one network: count the first few, hold the rest.
  const sameNet = await env.DB.prepare('SELECT COUNT(*) AS n FROM votes WHERE item = ?1 AND net_hash = ?2 AND at > ?3')
    .bind(item, neth, now() - 86400).first();
  const held = sameNet.n >= int(env, 'NET_ITEM_MAX', 3) ? 1 : 0;
  const weight = await weightFor(env, u);
  const ins = await env.DB.prepare(
    `INSERT INTO votes (item, user_id, choice, reason, weight, ip_hash, net_hash, held) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
     ON CONFLICT (item, user_id) DO NOTHING`,
  ).bind(item, u.id, choice, reason, weight, iph, neth, held).run();
  if (!ins.meta.changes) fail(409, 'duplicate');
  if (held) await setFlag(env, item, 'burst', 'Several accounts voted from one network; extra votes held');
  if (reason === 'cgi-ai') await aiFlag(env, item, u.id);
  await swingCheck(env, item);
  return json({ state: held ? 'held' : 'ok', pass, ...(await tally(env, item, u.id)) });
}

// Swing detection: compare the weighted shares before the last hour with the shares now. A big jump
// on an item that already had a settled baseline freezes it for a moderator.
export async function swingCheck(env, item) {
  const win = int(env, 'SWING_WINDOW', 3600);
  const t = now() - win;
  const rows = (await env.DB.prepare(
    `SELECT choice, at > ?2 AS recent, COUNT(*) AS n, SUM(weight) AS w FROM votes WHERE item = ?1 AND voided = 0 AND held = 0
     GROUP BY choice, recent`,
  ).bind(item, t).all()).results;
  const sum = (f) => rows.filter(f).reduce((s, r) => s + r.w, 0);
  const count = (f) => rows.filter(f).reduce((s, r) => s + r.n, 0);
  const baseN = count((r) => !r.recent), recentN = count((r) => r.recent);
  const baseW = sum((r) => !r.recent) || 1, allW = sum(() => true) || 1;
  if (baseN >= int(env, 'SWING_MIN_BASE', 10) && recentN >= int(env, 'SWING_MIN_RECENT', 5)) {
    for (const c of CHOICES) {
      const before = sum((r) => !r.recent && r.choice === c) / baseW;
      const after = sum((r) => r.choice === c) / allW;
      if (Math.abs(after - before) >= Number(env.SWING_DELTA || 0.25)) {
        await setFlag(env, item, 'swing', `"${c}" went from ${Math.round(before * 100)}% to ${Math.round(after * 100)}% in ${Math.round(win / 60)} min`, true);
        return true;
      }
    }
  } else if (baseN < 10 && recentN >= int(env, 'SURGE_VOTES', 40)) {
    // A brand-new item suddenly getting lots of votes: flag (don't freeze) so someone looks.
    const cur = await env.DB.prepare('SELECT flag FROM items WHERE item = ?1').bind(item).first();
    if (!cur || !cur.flag) await setFlag(env, item, 'surge', `${recentN} votes in ${Math.round(win / 60)} min`);
  }
  return false;
}

async function aiFlag(env, item, uid) {
  const r = await env.DB.prepare('INSERT OR IGNORE INTO flags (item, user_id, kind) VALUES (?1, ?2, ?3)').bind(item, uid, 'ai').run();
  if (!r.meta.changes) return false;
  // Any AI flag puts the item in the review queue; items with more flags sort first.
  await env.DB.prepare(
    `INSERT INTO items (item, flag, flag_note, flagged_at, ai_flags) VALUES (?1, 'ai', 'Flagged as possibly AI-generated', unixepoch(), 1)
     ON CONFLICT (item) DO UPDATE SET ai_flags = ai_flags + 1,
       flag = CASE WHEN flag IN ('', 'ai') THEN 'ai' ELSE flag END,
       flag_note = CASE WHEN flag IN ('', 'ai') THEN 'Flagged as possibly AI-generated' ELSE flag_note END,
       flagged_at = COALESCE(flagged_at, unixepoch())`,
  ).bind(item).run();
  return true;
}

async function flag(req, env) {
  const u = await session(req, env);
  const b = await body(req);
  const item = String(b.item || '');
  if (b.kind !== 'ai') fail(400, 'kind');
  if (!(await resolveItem(env, item))) fail(404, 'not_found');
  if (await rateLimited(env, [[`flag|u|${u.id}`, 30, 86400]])) fail(429, 'slow');
  const fresh = await aiFlag(env, item, u.id);
  return json({ state: fresh ? 'ok' : 'already' });
}

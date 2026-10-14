// Moderation page, served by the Worker itself at /mod (same origin as the API, never on the static site).
// Password = MOD_PASSWORD secret. Session = signed, HttpOnly, SameSite=Strict cookie scoped to /mod.
// Every POST must come from this origin (Origin header check) on top of the SameSite cookie.

import { CREATURES } from './creatures.js';
import { tally } from './index.js';
import { json, sign, verify, hash, clientIp, rateLimited, esc, now } from './util.js';

const COOKIE = 'ea_mod';
const HOURS = 12;

async function isMod(req, env) {
  const c = (req.headers.get('cookie') || '').split(/;\s*/).find((x) => x.startsWith(COOKIE + '='));
  const pl = c ? await verify(env, decodeURIComponent(c.slice(COOKIE.length + 1))) : null;
  return !!(pl && pl[0] === 'm' && now() - Number(pl[1]) < HOURS * 3600);
}

async function sameSecret(env, a, b) {
  // Compare HMACs of both strings so the comparison time doesn't leak the password.
  const [x, y] = await Promise.all([hash(env, 'pw|' + a, 43), hash(env, 'pw|' + b, 43)]);
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return d === 0 && a.length > 0;
}

const HEAD = {
  'content-type': 'text/html; charset=utf-8',
  'cache-control': 'no-store',
  'x-content-type-options': 'nosniff',
  'x-frame-options': 'DENY',
  'referrer-policy': 'same-origin',  // no-referrer made Chrome send Origin: null on form posts
  'content-security-policy': "default-src 'none'; img-src 'self' https://img.youtube.com; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
};

export async function handleMod(req, env, url) {
  const p = url.pathname;
  if (req.method === 'POST') {
    const o = req.headers.get('origin');
    // Same-origin form posts: Origin matches, or (older/privacy-mode browsers) Origin is null but Fetch Metadata says same-origin.
    const same = o === url.origin || (o === 'null' && req.headers.get('sec-fetch-site') === 'same-origin');
    if (!same) return new Response('Bad origin', { status: 403 });
  }
  if (p === '/mod/login' && req.method === 'POST') {
    const f = await req.formData();
    const ip = clientIp(req, env);
    if (await rateLimited(env, [[`modlogin|${await hash(env, ip)}`, 8, 900]])) return page('Slow down', '<p>Too many tries. Wait 15 minutes.</p>', 429);
    if (!env.MOD_PASSWORD || !(await sameSecret(env, String(f.get('password') || ''), env.MOD_PASSWORD))) {
      return page('Moderation', loginForm('That password is wrong.'), 403);
    }
    const tok = await sign(env, `m|${now()}`);
    return new Response(null, { status: 303, headers: { location: '/mod',
      'set-cookie': `${COOKIE}=${encodeURIComponent(tok)}; Path=/mod; HttpOnly; Secure; SameSite=Strict; Max-Age=${HOURS * 3600}` } });
  }
  if (!(await isMod(req, env))) {
    if (p === '/mod/queue.json') return json({ state: 'signin' }, 401);
    return page('Moderation', loginForm(), p === '/mod' ? 200 : 401);
  }
  if (p === '/mod/logout' && req.method === 'POST') {
    return new Response(null, { status: 303, headers: { location: '/mod', 'set-cookie': `${COOKIE}=; Path=/mod; HttpOnly; Secure; SameSite=Strict; Max-Age=0` } });
  }
  if (p === '/mod/action' && req.method === 'POST') return action(req, env, url);
  if (p === '/mod/queue.json') return json(await queue(env, url.searchParams.get('view') || 'pending'));
  if (p === '/mod' && req.method === 'GET') return dashboard(env, url);
  return new Response('Not found', { status: 404 });
}

function loginForm(msg = '') {
  return `<h1>Moderation</h1>${msg ? `<p class="err">${esc(msg)}</p>` : ''}
<form method="post" action="/mod/login" class="login"><label>Password <input type="password" name="password" autocomplete="current-password" required autofocus></label>
<button>Sign in</button></form>`;
}

async function queue(env, view) {
  const out = { view, reports: [], flagged: [] };
  if (view === 'flagged') {
    const items = (await env.DB.prepare(
      `SELECT * FROM items WHERE frozen = 1 OR flag != '' OR ai_flags > 0
       ORDER BY (flag = 'ai') DESC, ai_flags DESC, frozen DESC, flagged_at DESC LIMIT 100`,
    ).all()).results;
    for (const it of items) {
      const t = await tally(env, it.item, null, true);
      const held = await env.DB.prepare('SELECT COUNT(*) AS n FROM votes WHERE item = ?1 AND held = 1 AND voided = 0').bind(it.item).first();
      const story = it.item.startsWith('s:') ? it.item.slice(2) : null;
      const pid = story ? null : it.item.split(':')[0] === 'p'
        ? (await env.DB.prepare('SELECT r.pid FROM photos ph JOIN reports r ON r.id = ph.report_id WHERE ph.id = ?1').bind(it.item.slice(2)).first())?.pid
        : it.item.split(':')[1];
      out.flagged.push({ ...it, tally: t, held: held.n, pid, story });
    }
    return out;
  }
  const status = view === 'recent' ? 'approved' : view === 'rejected' ? 'rejected' : 'pending';
  const order = status === 'pending' ? 'r.updated ASC' : 'r.updated DESC';
  const rows = (await env.DB.prepare(
    `SELECT r.*, u.email, u.created AS u_created FROM reports r LEFT JOIN users u ON u.id = r.user_id
     WHERE r.status = ?1 ORDER BY ${order} LIMIT 50`,
  ).bind(status).all()).results;
  for (const r of rows) {
    const photos = (await env.DB.prepare('SELECT id, w, h, bytes FROM photos WHERE report_id = ?1 AND removed = 0 ORDER BY idx').bind(r.id).all()).results;
    for (const ph of photos) ph.url = `/img/${ph.id}.jpg?k=${encodeURIComponent(await sign(env, `i|${ph.id}|${now()}`))}`;
    out.reports.push({ ...r, videos: JSON.parse(r.videos), links: JSON.parse(r.links || '[]'), photos });
  }
  return out;
}

async function action(req, env, url) {
  const f = await req.formData();
  const act = String(f.get('act') || '');
  const id = String(f.get('id') || '');
  const note = String(f.get('note') || '').slice(0, 300);
  const back = String(f.get('back') || 'pending').replace(/[^a-z]/g, '');
  const D = env.DB;
  let done = '';
  if (act === 'approve' || act === 'reject') {
    const st = act === 'approve' ? 'approved' : 'rejected';
    const r = await D.prepare(
      `UPDATE reports SET status = ?2, mod_note = ?3, approved_at = CASE WHEN ?2 = 'approved' THEN unixepoch() ELSE approved_at END
       WHERE pid = ?1 AND status != 'withdrawn' RETURNING pid`,
    ).bind(id, st, note).first();
    done = r ? `${st} ${id}` : 'not found';
  } else if (act === 'remove_photo') {
    const r = await D.prepare('UPDATE photos SET removed = 1 WHERE id = ?1 RETURNING id').bind(id).first();
    if (r && env.PHOTOS) await env.PHOTOS.delete(`p/${id}.jpg`);
    done = r ? 'photo removed' : 'not found';
  } else if (act === 'unfreeze') {
    await D.prepare(`UPDATE items SET frozen = 0, flag = '', flag_note = '', ai_flags = 0 WHERE item = ?1`).bind(id).run();
    done = 'unfrozen';
  } else if (act === 'clear') {
    await D.prepare(`UPDATE items SET flag = '', flag_note = '', ai_flags = 0 WHERE item = ?1`).bind(id).run();
    done = 'flag cleared';
  } else if (act === 'release_held') {
    await D.prepare('UPDATE votes SET held = 0 WHERE item = ?1 AND held = 1').bind(id).run();
    done = 'held votes counted';
  } else if (act === 'void_held') {
    await D.prepare('UPDATE votes SET voided = 1 WHERE item = ?1 AND held = 1').bind(id).run();
    done = 'held votes voided';
  } else if (act === 'void_recent') {
    const mins = Math.min(10080, Math.max(5, Number(f.get('minutes')) || 60));
    const r = await D.prepare('UPDATE votes SET voided = 1 WHERE item = ?1 AND at > ?2').bind(id, now() - mins * 60).run();
    done = `${r.meta.changes} votes voided`;
  } else {
    return new Response('Unknown action', { status: 400 });
  }
  if ((req.headers.get('accept') || '').includes('application/json')) return json({ state: 'ok', done });
  return new Response(null, { status: 303, headers: { location: `/mod?view=${back}&done=${encodeURIComponent(done)}` } });
}

const when = (t) => (t ? new Date(t * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC' : '');

function btn(act, id, label, back, extra = '', cls = '') {
  return `<form method="post" action="/mod/action" class="inl"><input type="hidden" name="act" value="${act}"><input type="hidden" name="id" value="${esc(id)}">
<input type="hidden" name="back" value="${back}">${extra}<button class="${cls}">${label}</button></form>`;
}

async function dashboard(env, url) {
  const view = ['pending', 'flagged', 'recent', 'rejected'].includes(url.searchParams.get('view')) ? url.searchParams.get('view') : 'pending';
  const q = await queue(env, view);
  const counts = await env.DB.prepare(
    `SELECT (SELECT COUNT(*) FROM reports WHERE status = 'pending') AS pending,
            (SELECT COUNT(*) FROM items WHERE frozen = 1 OR flag != '' OR ai_flags > 0) AS flagged`,
  ).first();
  const tabs = [['pending', `Pending (${counts.pending})`], ['flagged', `Flagged votes (${counts.flagged})`], ['recent', 'Approved'], ['rejected', 'Rejected']]
    .map(([k, n]) => `<a href="/mod?view=${k}"${k === view ? ' class="on"' : ''}>${n}</a>`).join('');
  const done = url.searchParams.get('done');
  let html = `<header><h1>Moderation</h1><nav>${tabs}</nav><form method="post" action="/mod/logout" class="inl"><button class="ghost">Sign out</button></form></header>`;
  if (done) html += `<p class="done">Done: ${esc(done)}</p>`;
  if (view === 'flagged') {
    if (!q.flagged.length) html += '<p>Nothing flagged.</p>';
    for (const it of q.flagged) {
      const t = it.tally;
      const res = t.results ? `Real ${t.results.real}% · Hoax ${t.results.hoax}% · Misidentified ${t.results.mis}%` +
        (Object.keys(t.results.reasons).length ? ` (${Object.entries(t.results.reasons).map(([k, v]) => `${k} ${v}%`).join(', ')})` : '') : '';
      html += `<article class="card${it.frozen ? ' frozen' : ''}"><h2>${esc(it.item)} ${it.frozen ? '<span class="tag red">frozen</span>' : ''}
${it.flag ? `<span class="tag">${esc(it.flag)}</span>` : ''}${it.ai_flags ? `<span class="tag ai">AI flags: ${it.ai_flags}</span>` : ''}</h2>
<p>${esc(it.flag_note)} <span class="muted">${when(it.flagged_at)}</span></p>
<p>${t.n} counted votes${it.held ? `, <b>${it.held} held</b>` : ''}. ${esc(res)}</p>
<p>${it.pid ? `Report: <a href="${esc(env.SITE)}/reports/?id=${esc(it.pid)}" target="_blank" rel="noopener">${esc(it.pid)}</a>` : ''}${it.story ? `Witness story: <a href="${esc(env.SITE)}/stories/${esc(it.story)}/" target="_blank" rel="noopener">${esc(it.story)}</a>` : ''}</p>
<div class="acts">${btn('unfreeze', it.item, 'Unfreeze + clear', view)}${btn('clear', it.item, 'Clear flag only', view, '', 'ghost')}
${it.held ? btn('release_held', it.item, 'Count held votes', view, '', 'ghost') + btn('void_held', it.item, 'Void held votes', view, '', 'ghost') : ''}
${btn('void_recent', it.item, 'Void votes from last', view, '<input name="minutes" type="number" value="60" min="5" max="10080" aria-label="minutes"> min ', 'ghost')}
${it.pid ? btn('reject', it.pid, 'Unpublish report', view, '<input name="note" placeholder="note" aria-label="note">', 'red') : ''}</div></article>`;
    }
  } else {
    if (!q.reports.length) html += `<p>No ${view} reports.</p>`;
    for (const r of q.reports) {
      const what = r.creature === 'other' ? `Something else: ${r.other_what}` : CREATURES[r.creature] || r.creature;
      const photos = r.photos.map((ph) => `<figure><a href="${esc(ph.url)}" target="_blank"><img src="${esc(ph.url)}" alt="" loading="lazy"></a>
<figcaption>${ph.w}×${ph.h}, ${Math.round(ph.bytes / 1024)} KB ${btn('remove_photo', ph.id, 'Remove', view, '', 'ghost small')}</figcaption></figure>`).join('');
      // Photo links open in a new tab with no referrer; check them before approving (they're on other people's servers).
      const lks = r.links.map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer nofollow">photo on ${esc(l.host)}: ${esc(l.url)}</a></li>`).join('');
      const vids = r.videos.map((v) => `<li><a href="${esc(v.url)}" target="_blank" rel="noopener noreferrer">${esc(v.p)}: ${esc(v.url)}</a></li>`).join('');
      const osm = `https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lon}#map=14/${r.lat}/${r.lon}`;
      html += `<article class="card"><h2>${esc(what)} <span class="muted">${esc(r.pid)}</span></h2>
<dl><dt>When</dt><dd>${esc(r.seen_date)} ${esc(r.seen_time)}${r.date_approx ? ' (approximate)' : ''}</dd>
<dt>Where</dt><dd>${esc(r.place) || '<i>no place name</i>'} · exact <a href="${osm}" target="_blank" rel="noopener noreferrer">${r.lat.toFixed(5)}, ${r.lon.toFixed(5)}</a> (${esc(r.loc_source)}) · public ${r.pub_lat}, ${r.pub_lon}</dd>
<dt>Duration</dt><dd>${esc(r.duration)}</dd><dt>Witnesses</dt><dd>${r.witnesses}</dd>
<dt>Sounds</dt><dd>${esc(r.sounds)}</dd><dt>Smells</dt><dd>${esc(r.smells)}</dd>
<dt>By</dt><dd>${r.anonymous ? 'Anonymous publicly' : esc(r.display_name)} · ${r.email ? esc(r.email) + ` (account since ${when(r.u_created).slice(0, 10)})` : 'no email'} · ip ${esc(r.ip_hash.slice(0, 8))}</dd>
<dt>Sent</dt><dd>${when(r.created)}${r.updated > r.created + 5 ? `, edited ${when(r.updated)}` : ''}</dd></dl>
<div class="story">${esc(r.story)}</div>
${photos ? `<div class="photos">${photos}</div>` : ''}${lks ? `<p><b>Photo links</b> (open each one and check it before approving)</p><ul>${lks}</ul>` : ''}${vids ? `<ul>${vids}</ul>` : ''}
<div class="acts">${r.status !== 'approved' ? btn('approve', r.pid, 'Approve', view, '<input name="note" placeholder="note (optional)" aria-label="note">') : ''}
${r.status !== 'rejected' ? btn('reject', r.pid, r.status === 'approved' ? 'Unpublish' : 'Reject', view, '<input name="note" placeholder="reason (shown to the reporter)" aria-label="reason">', 'red') : ''}
${r.status === 'approved' ? `<a href="${esc(env.SITE)}/reports/?id=${esc(r.pid)}" target="_blank" rel="noopener">View on site</a>` : ''}</div></article>`;
    }
  }
  return page('Moderation', html);
}

function page(title, inner, status = 200) {
  return new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(title)} | Encounter Atlas</title><style>
body{margin:0;background:#E4EBE6;color:#15241E;font:16px/1.5 system-ui,sans-serif}main{max-width:980px;margin:0 auto;padding:16px}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;background:#13261F;color:#C9D3A4;margin:-16px -16px 16px;padding:14px 16px}
header h1{margin:0;font-size:1.3rem;color:#F3F1DA}nav{display:flex;gap:6px;flex-wrap:wrap;flex:1}nav a{color:#C9D3A4;text-decoration:none;padding:4px 10px;border-radius:99px}
nav a.on{background:#C9D3A4;color:#13261F}.card{background:#fff;border:1px solid #D3DED7;border-radius:12px;padding:14px 16px;margin:0 0 14px}
.card.frozen{border-color:#E5483B}.card h2{margin:0 0 8px;font-size:1.15rem}dl{display:grid;grid-template-columns:7rem 1fr;gap:2px 10px;margin:0 0 10px;font-size:.93rem}
dt{font-weight:700;color:#4D6157}dd{margin:0}.story{white-space:pre-wrap;background:#F4F7F5;border-radius:8px;padding:10px 12px;margin:0 0 10px}
.photos{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 10px}figure{margin:0;width:180px}figure img{width:180px;height:140px;object-fit:cover;border-radius:8px;display:block}
figcaption{font-size:.8rem;color:#4D6157}.acts{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.inl{display:inline-flex;gap:6px;align-items:center;margin:0}
button{font:700 .95rem system-ui;background:#F2B33D;color:#13261F;border:0;border-radius:99px;padding:8px 14px;cursor:pointer}
button.ghost{background:#fff;box-shadow:inset 0 0 0 2px #13261F}button.red{background:#E5483B;color:#fff}button.small{padding:2px 8px;font-size:.8rem}
input{font:inherit;padding:6px 8px;border:1px solid #B9C7BE;border-radius:6px}input[type=number]{width:5em}
.tag{font-size:.75rem;background:#13261F;color:#C9D3A4;padding:2px 8px;border-radius:99px;margin-left:6px;vertical-align:middle}.tag.red{background:#E5483B;color:#fff}
.tag.ai{background:#8E8CF0;color:#13261F}.muted{color:#4D6157;font-weight:400;font-size:.9rem}.done{background:#13261F;color:#C9D3A4;padding:8px 12px;border-radius:8px}
.err{color:#B3261E;font-weight:700}.login{display:flex;gap:10px;flex-wrap:wrap;align-items:end}a{color:#7A4E00}
</style></head><body><main>${inner}</main></body></html>`, { status, headers: HEAD });
}


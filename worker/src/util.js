// Shared helpers: HMAC tokens (same scheme as the Shorebite/newsletter Workers), hashing, rate limits,
// Turnstile, email, small response helpers.

export const enc = new TextEncoder();
export const now = () => Math.floor(Date.now() / 1000);
export const b64 = (buf) =>
  btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
export const unb64 = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
export const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

export class HttpError extends Error {
  constructor(status, state, extra = {}) {
    super(state);
    this.status = status;
    this.body = { state, ...extra };
  }
}
export const fail = (status, state, extra) => { throw new HttpError(status, state, extra); };

export function json(o, status = 200, headers = {}) {
  return new Response(JSON.stringify(o), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'x-content-type-options': 'nosniff', ...headers },
  });
}

const keys = new Map();
function hmacKey(env) {
  if (!env.TOKEN_SECRET || env.TOKEN_SECRET.length < 16) throw new Error('TOKEN_SECRET missing or too short');
  if (!keys.has(env.TOKEN_SECRET)) {
    keys.set(env.TOKEN_SECRET, crypto.subtle.importKey('raw', enc.encode(env.TOKEN_SECRET), { name: 'HMAC', hash: 'SHA-256' },
      false, ['sign', 'verify']));
  }
  return keys.get(env.TOKEN_SECRET);
}

export async function sign(env, payload) {
  const sig = await crypto.subtle.sign('HMAC', await hmacKey(env), enc.encode(payload));
  return b64(enc.encode(payload)) + '.' + b64(sig);
}

// Returns the payload split on "|", or null.
export async function verify(env, token) {
  const [p, s] = String(token || '').split('.');
  if (!p || !s || token.length > 600) return null;
  try {
    const payload = unb64(p);
    const ok = await crypto.subtle.verify('HMAC', await hmacKey(env), unb64(s), payload);
    return ok ? new TextDecoder().decode(payload).split('|') : null;
  } catch {
    return null;
  }
}

export async function hash(env, text, n = 22) {
  const sig = await crypto.subtle.sign('HMAC', await hmacKey(env), enc.encode('h|' + text));
  return b64(sig).slice(0, n);
}

export function randomId(bytes = 12) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))].map((x) => x.toString(16).padStart(2, '0')).join('');
}

export function randomPid() {
  const abc = '23456789abcdefghjkmnpqrstuvwxyz'; // no 0/o/1/l/i
  return [...crypto.getRandomValues(new Uint8Array(10))].map((x) => abc[x % abc.length]).join('');
}

// Client IP. In local dev (DEV=1) tests can pretend to be other people with x-test-ip.
export function clientIp(req, env) {
  if (env.DEV === '1' && req.headers.get('x-test-ip')) return req.headers.get('x-test-ip');
  return req.headers.get('cf-connecting-ip') || '0.0.0.0';
}

// Network prefix: IPv4 /24, IPv6 /48. Votes bursting from one network get held.
export function network(ip) {
  if (ip.includes(':')) return ip.split(':').slice(0, 3).join(':') + '::/48';
  return ip.split('.').slice(0, 3).join('.') + '.0/24';
}

export function int(env, name, dflt) {
  const v = Number(env[name]);
  return Number.isFinite(v) && v > 0 ? v : dflt;
}

// Sliding-window rate limit over several keys at once: [[key, max, windowSeconds], ...].
// Returns true (limited) without recording anything if any key is over; otherwise records a hit for each.
export async function rateLimited(env, rules) {
  const t = now();
  const counts = await env.DB.batch(rules.map(([k, , win]) =>
    env.DB.prepare('SELECT COUNT(*) AS n FROM hits WHERE k = ?1 AND at > ?2').bind(k, t - win)));
  for (let i = 0; i < rules.length; i++) if (counts[i].results[0].n >= rules[i][1]) return true;
  const seen = new Set();
  await env.DB.batch(rules.filter(([k]) => !seen.has(k) && seen.add(k))
    .map(([k]) => env.DB.prepare('INSERT INTO hits (k, at) VALUES (?1, ?2)').bind(k, t)));
  return false;
}

// Cloudflare Turnstile. Locally (DEV=1) the official test secrets answer without a network call:
// 1x0000... always passes, 2x0000... always fails, exactly like the real siteverify does for them.
export async function turnstileOk(env, token, ip) {
  if (!token || typeof token !== 'string' || token.length > 2048) return false;
  const secret = env.TURNSTILE_SECRET || '';
  if (env.DEV === '1' && secret.startsWith('1x0000000000000000000000000000000')) return true;
  if (env.DEV === '1' && secret.startsWith('2x0000000000000000000000000000000')) return false;
  if (!secret) return false;
  const body = new FormData();
  body.append('secret', secret);
  body.append('response', token);
  if (ip && ip !== '0.0.0.0') body.append('remoteip', ip);
  const res = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body });
  const d = await res.json().catch(() => ({}));
  if (d.success !== true) console.log(`turnstile rejected: ${JSON.stringify(d['error-codes'] || [])} host=${d.hostname || ''}`);
  return d.success === true;
}

// Resend. With EMAIL_MODE=log (local dev) nothing is sent; the caller gets the message back instead.
export async function sendEmail(env, msg) {
  if (env.EMAIL_MODE === 'log' || !env.RESEND_API_KEY) {
    console.log(`[email not sent] to=${msg.to} subject=${msg.subject}`);
    return { logged: true };
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { authorization: `Bearer ${env.RESEND_API_KEY}`, 'content-type': 'application/json' },
    body: JSON.stringify({ from: env.FROM, ...msg }),
  });
  if (!res.ok) throw new Error(`resend: ${res.status} ${await res.text()}`);
  return { sent: true };
}

// Plain one-line text: strips control characters and collapses whitespace.
export function line(v, max) {
  return String(v ?? '').replace(/[\u0000-\u001f\u007f​-‏‪-‮⁦-⁩]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
}
// Multi-line text: keeps newlines (max two in a row).
export function para(v, max) {
  return String(v ?? '').replace(/\r\n?/g, '\n').replace(/[\u0000-\u0009\u000b-\u001f\u007f​-‏‪-‮⁦-⁩]/g, ' ')
    .replace(/[ \t]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim().slice(0, max);
}

// ---------------- branded email ----------------
// One layout for every email the Worker sends: dark header with the folded-map mark and wordmark, a cream card,
// and Mike's signature. Tables and inline styles only (Gmail, Outlook, Apple Mail); images are PNGs on the site.
// paras: HTML strings the caller has already escaped. Returns { html, text } with a matching plain-text version.
const ASSET = 'https://encounteratlas.com/static/email/';
const C = { spruce: '#13261F', cream: '#F6F0E2', page: '#E7E9E1', ink: '#1F2A24', muted: '#5D6B62', lantern: '#F2B33D', line: '#DDD3BC' };
const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
export function emailLayout({ preheader = '', heading = '', paras = [], button = null, note = '', text = '', signature = true, footer = '' }) {
  const p = (h) => `<p style="margin:0 0 16px;font:16px/1.55 ${FONT};color:${C.ink}">${h}</p>`;
  const btn = button ? `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 20px"><tr><td bgcolor="${C.lantern}" style="border-radius:999px">
<a href="${esc(button.href)}" style="display:inline-block;padding:13px 24px;font:700 16px ${FONT};color:${C.spruce};text-decoration:none;border-radius:999px">${esc(button.label)}</a></td></tr></table>` : '';
  const sig = signature ? `<tr><td style="padding:0 32px 28px"><table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-top:1px solid ${C.line}"><tr>
<td width="56" valign="top" style="padding-top:18px"><img src="${ASSET}mike-96.png" width="48" height="48" alt="" style="display:block;border:0;border-radius:24px"></td>
<td valign="top" style="padding-top:18px;font:15px/1.5 ${FONT};color:${C.ink}"><strong>Mike Johnston</strong> · Encounter Atlas<br>
<span style="color:${C.muted}">Got a question? Just reply to this email.</span><br>
<a href="https://encounteratlas.com/" style="color:#8A5A00;text-decoration:underline">encounteratlas.com</a></td></tr></table></td></tr>` : '';
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only"><title>${esc(heading || 'Encounter Atlas')}</title></head>
<body style="margin:0;padding:0;background:${C.page}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">${esc(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="${C.page}" style="background:${C.page}"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;background:${C.cream};border-radius:16px;overflow:hidden" bgcolor="${C.cream}">
<tr><td bgcolor="${C.spruce}" style="background:${C.spruce};padding:18px 32px"><a href="https://encounteratlas.com/" style="text-decoration:none">
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td valign="middle"><img src="${ASSET}logo-mark-96.png" width="48" height="48" alt="" style="display:block;border:0"></td>
<td valign="middle" style="padding-left:12px;font:700 22px Georgia,'Times New Roman',serif;color:#E8E0B8">Encounter Atlas</td></tr></table></a></td></tr>
<tr><td style="padding:28px 32px 8px">${heading ? `<h1 style="margin:0 0 14px;font:700 22px/1.3 Georgia,'Times New Roman',serif;color:${C.spruce}">${esc(heading)}</h1>` : ''}
${paras.map(p).join('\n')}${btn}${note ? `<p style="margin:0 0 20px;font:14px/1.5 ${FONT};color:${C.muted}">${note}</p>` : ''}</td></tr>
${sig}${footer ? `<tr><td style="padding:0 32px 24px;font:13px/1.5 ${FONT};color:${C.muted}">${footer}</td></tr>` : ''}
</table></td></tr></table></body></html>`;
  const plain = text + (signature ? '\n\n-- \nMike Johnston · Encounter Atlas\nGot a question? Just reply to this email.\nhttps://encounteratlas.com/' : '');
  return { html, text: plain };
}

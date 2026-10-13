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

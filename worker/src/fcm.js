// Firebase Cloud Messaging (HTTP v1) sender for the Android / iPhone app's sighting alerts. WebCrypto only, like
// webpush.js: no Firebase Admin SDK, no Node APIs.
//   fcmConfig(env)                 -> parsed service account from the FCM_SERVICE_ACCOUNT secret (JSON key file), or null
//   fcmMessage(token, payload, o)  -> the v1 "message" object (exported for the tests)
//   sendFcm(sa, token, payload, o) -> { status }  200 sent; 404 the app was uninstalled or the token is stale (switch
//                                     the row off); -1 our side is broken (bad key, FCM down), so the row is not blamed
// The OAuth access token (1 hour) is cached per isolate and reused until 5 minutes before it expires.

const te = new TextEncoder();
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const b64uStr = (s) => b64u(te.encode(s));
const SCOPE = 'https://www.googleapis.com/auth/firebase.messaging';
const TOKEN_URL = 'https://oauth2.googleapis.com/token';

// FCM registration tokens: letters, digits, '-', '_' and ':' (about 150-200 characters today).
export const validFcmToken = (t) => typeof t === 'string' && /^[A-Za-z0-9_:-]{32,512}$/.test(t);

export function fcmConfig(env) {
  if (!env.FCM_SERVICE_ACCOUNT) return null;
  try {
    const sa = JSON.parse(env.FCM_SERVICE_ACCOUNT);
    return sa && sa.client_email && sa.private_key && sa.project_id ? sa : null;
  } catch { return null; }
}

let cached = null; // { email, token, exp }
export function _resetFcmCache() { cached = null; }

async function signingKey(pem) {
  const der = Uint8Array.from(atob(String(pem).replace(/-----[^-]+-----/g, '').replace(/\s+/g, '')), (c) => c.charCodeAt(0));
  return crypto.subtle.importKey('pkcs8', der, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']);
}

// OAuth 2.0 for service accounts: a JWT signed RS256 with the account's key, swapped for an access token.
export async function accessToken(sa, nowSec = Math.floor(Date.now() / 1000)) {
  if (cached && cached.email === sa.client_email && cached.exp - 300 > nowSec) return cached.token;
  const head = b64uStr(JSON.stringify({ alg: 'RS256', typ: 'JWT', ...(sa.private_key_id ? { kid: sa.private_key_id } : {}) }));
  const body = b64uStr(JSON.stringify({ iss: sa.client_email, scope: SCOPE, aud: sa.token_uri || TOKEN_URL, iat: nowSec, exp: nowSec + 3600 }));
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', await signingKey(sa.private_key), te.encode(`${head}.${body}`));
  const res = await fetch(sa.token_uri || TOKEN_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: `${head}.${body}.${b64u(sig)}` }),
  });
  const j = await res.json().catch(() => ({}));
  if (!res.ok || !j.access_token) throw new Error(`fcm oauth ${res.status} ${j.error || ''}`);
  cached = { email: sa.client_email, token: j.access_token, exp: nowSec + (Number(j.expires_in) || 3600) };
  return cached.token;
}

// Same payload the Web Push alerts carry ({kind, id, title, body, url, ...}); FCM data values must be strings.
export function fcmMessage(token, payload, { ttl = 86400, urgency = 'normal' } = {}) {
  const data = {};
  for (const [k, v] of Object.entries(payload || {})) {
    if (v == null || k === 'title' || k === 'body') continue;
    data[k] = typeof v === 'string' ? v : JSON.stringify(v);
  }
  const title = String(payload.title || 'Encounter Atlas'), body = String(payload.body || '');
  return {
    token,
    notification: { title, body },
    data,
    android: {
      priority: urgency === 'high' ? 'HIGH' : 'NORMAL',
      ttl: `${ttl}s`,
      notification: { channel_id: 'alerts', icon: 'ic_stat_ea', color: '#13261F', ...(payload.id ? { tag: String(payload.id) } : {}) },
    },
    apns: { headers: { 'apns-expiration': String(Math.floor(Date.now() / 1000) + ttl) }, payload: { aps: { sound: 'default' } } },
  };
}

export async function sendFcm(sa, token, payload, opts = {}) {
  let auth;
  try { auth = await accessToken(sa); } catch (e) { console.error(e); return { status: -1 }; }
  const res = await fetch(`https://fcm.googleapis.com/v1/projects/${encodeURIComponent(sa.project_id)}/messages:send`, {
    method: 'POST',
    headers: { authorization: `Bearer ${auth}`, 'content-type': 'application/json' },
    body: JSON.stringify({ message: fcmMessage(token, payload, opts) }),
  });
  if (res.ok) return { status: 200 };
  const err = await res.json().catch(() => ({}));
  const code = ((err.error && err.error.details) || []).map((d) => d.errorCode).find(Boolean) || (err.error && err.error.status) || '';
  // Stale or unknown token: the app was uninstalled or reinstalled. Switch that row off.
  if (res.status === 404 || code === 'UNREGISTERED') return { status: 404 };
  // A malformed token is the device row's fault too.
  if (res.status === 400 && code === 'INVALID_ARGUMENT' && /token/i.test((err.error && err.error.message) || '')) return { status: 404 };
  // 401/403 (our key or project), 429/5xx (FCM busy): not the subscriber's fault.
  if (res.status === 401 || res.status === 403 || res.status === 429 || res.status >= 500) {
    if (res.status === 401) cached = null;
    console.error('fcm', res.status, code);
    return { status: -1 };
  }
  return { status: res.status };
}

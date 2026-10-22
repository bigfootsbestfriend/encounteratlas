// Web Push with WebCrypto only (works in Workers and Node 20+): VAPID (RFC 8292) and aes128gcm payload
// encryption (RFC 8188 + RFC 8291). No library, no Node APIs.
//   vapidKeys(): new key pair -> { publicKey: base64url raw P-256 point, privateJwk: JSON string }
//   sendPush(sub, payload, vapid) -> { status } where sub = { endpoint, p256dh, auth }, vapid = { publicKey, privateJwk, subject }

const te = new TextEncoder();
export const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
export const unb64u = (s) => Uint8Array.from(atob(String(s).replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((String(s).length + 3) % 4)), (c) => c.charCodeAt(0));
const cat = (...parts) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let i = 0;
  for (const p of parts) { out.set(p, i); i += p.length; }
  return out;
};

async function hmac(key, data) {
  const k = await crypto.subtle.importKey('raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, data));
}
// HKDF with one Expand block (every length we need is <= 32 bytes).
async function hkdf(salt, ikm, info, len) {
  const prk = await hmac(salt, ikm);
  return (await hmac(prk, cat(info, new Uint8Array([1])))).slice(0, len);
}

export async function vapidKeys() {
  const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const raw = await crypto.subtle.exportKey('raw', kp.publicKey);
  return { publicKey: b64u(raw), privateJwk: JSON.stringify(await crypto.subtle.exportKey('jwk', kp.privateKey)) };
}

// VAPID JWT for the push service's origin, signed ES256 (WebCrypto already returns the raw r||s JOSE wants).
export async function vapidHeader(endpoint, vapid, ttlSeconds = 12 * 3600) {
  const aud = new URL(endpoint).origin;
  const head = b64u(te.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const body = b64u(te.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + ttlSeconds, sub: vapid.subject })));
  const key = await crypto.subtle.importKey('jwk', JSON.parse(vapid.privateJwk), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, te.encode(`${head}.${body}`));
  return `vapid t=${head}.${body}.${b64u(sig)}, k=${vapid.publicKey}`;
}

// aes128gcm body for one subscription: salt | record size | key id length | sender public key | ciphertext.
export async function encrypt(payload, p256dh, auth) {
  const uaPublic = unb64u(p256dh), authSecret = unb64u(auth);
  const as = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const asPublic = new Uint8Array(await crypto.subtle.exportKey('raw', as.publicKey));
  const uaKey = await crypto.subtle.importKey('raw', uaPublic, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, as.privateKey, 256));
  const ikm = await hkdf(authSecret, shared, cat(te.encode('WebPush: info\0'), uaPublic, asPublic), 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, te.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, te.encode('Content-Encoding: nonce\0'), 12);
  const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const plain = cat(te.encode(payload), new Uint8Array([2])); // 0x02: last (and only) record, no padding
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, plain));
  const rs = new Uint8Array([0, 0, 16, 0]); // 4096
  return cat(salt, rs, new Uint8Array([asPublic.length]), asPublic, ct);
}

export async function sendPush(sub, payload, vapid, { ttl = 86400, urgency = 'normal' } = {}) {
  const body = await encrypt(typeof payload === 'string' ? payload : JSON.stringify(payload), sub.p256dh, sub.auth);
  const res = await fetch(sub.endpoint, {
    method: 'POST',
    headers: { authorization: await vapidHeader(sub.endpoint, vapid), 'content-encoding': 'aes128gcm',
      'content-type': 'application/octet-stream', ttl: String(ttl), urgency },
    body,
  });
  return { status: res.status };
}

// Only real browser push services, so a subscription can't make the Worker POST to an arbitrary URL.
const PUSH_HOSTS = [/\.googleapis\.com$/, /^updates\.push\.services\.mozilla\.com$/, /\.push\.services\.mozilla\.com$/,
  /\.notify\.windows\.com$/, /^web\.push\.apple\.com$/, /\.push\.apple\.com$/];
export function validEndpoint(e) {
  let u;
  try { u = new URL(String(e)); } catch { return false; }
  return u.protocol === 'https:' && String(e).length <= 1000 && !u.port && PUSH_HOSTS.some((re) => re.test(u.hostname));
}

// FCM HTTP v1 sender (src/fcm.js) with a throwaway RSA key and a fake fetch: the OAuth JWT is signed correctly,
// the access token is cached, the message has the right shape, and FCM's error answers map to the right status.
// Runs in plain Node (no Worker, nothing leaves the machine).
import { fcmConfig, fcmMessage, sendFcm, accessToken, validFcmToken, _resetFcmCache } from '../src/fcm.js';

let pass = 0, failed = 0;
const ok = (cond, name, extra = '') => {
  if (cond) { pass++; console.log(`  ok   ${name}`); } else { failed++; console.log(`  FAIL ${name} ${extra}`); }
};
const section = (s) => console.log(`\n${s}`);
const unb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
const part = (jwt, i) => JSON.parse(new TextDecoder().decode(unb64u(jwt.split('.')[i])));

const kp = await crypto.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const pkcs8 = btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.exportKey('pkcs8', kp.privateKey))));
const pem = `-----BEGIN PRIVATE KEY-----\n${pkcs8.match(/.{1,64}/g).join('\n')}\n-----END PRIVATE KEY-----\n`;
const SA = { type: 'service_account', project_id: 'ea-test', private_key_id: 'kid123', private_key: pem,
  client_email: 'fcm@ea-test.iam.gserviceaccount.com', token_uri: 'https://oauth2.googleapis.com/token' };
const TOKEN = 'dEvIcE:APA91b' + 'Q'.repeat(140);

// Fake network: records every request and answers from `next` (a function of the request).
const calls = [];
let next = () => ({ status: 200, body: { name: 'projects/ea-test/messages/1' } });
globalThis.fetch = async (url, init = {}) => {
  const req = { url: String(url), method: init.method, headers: init.headers || {}, body: init.body };
  calls.push(req);
  if (req.url === SA.token_uri) return new Response(JSON.stringify({ access_token: 'ya29.test-token', expires_in: 3599, token_type: 'Bearer' }), { status: 200 });
  const r = next(req);
  return new Response(JSON.stringify(r.body || {}), { status: r.status });
};

section('Config and tokens');
ok(fcmConfig({}) === null, 'no secret: off');
ok(fcmConfig({ FCM_SERVICE_ACCOUNT: 'not json' }) === null, 'bad JSON: off');
ok(fcmConfig({ FCM_SERVICE_ACCOUNT: JSON.stringify({ project_id: 'x' }) }) === null, 'incomplete key: off');
ok(fcmConfig({ FCM_SERVICE_ACCOUNT: JSON.stringify(SA) })?.project_id === 'ea-test', 'service account parsed');
ok(validFcmToken(TOKEN) && !validFcmToken('short') && !validFcmToken('https://evil.example/' + 'x'.repeat(50)) && !validFcmToken(null), 'token format');

section('OAuth');
_resetFcmCache();
const at = await accessToken(SA, 1_800_000_000);
ok(at === 'ya29.test-token', 'access token returned');
const tokReq = calls.find((c) => c.url === SA.token_uri);
const form = new URLSearchParams(String(tokReq.body));
ok(form.get('grant_type') === 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'JWT bearer grant');
const jwt = form.get('assertion');
const head = part(jwt, 0), claims = part(jwt, 1);
ok(head.alg === 'RS256' && head.kid === 'kid123', 'RS256 header with the key id');
ok(claims.iss === SA.client_email && claims.aud === SA.token_uri && claims.scope === 'https://www.googleapis.com/auth/firebase.messaging'
  && claims.exp - claims.iat === 3600 && claims.iat === 1_800_000_000, 'claims', JSON.stringify(claims));
const [h, b, s] = jwt.split('.');
ok(await crypto.subtle.verify('RSASSA-PKCS1-v1_5', kp.publicKey, unb64u(s), new TextEncoder().encode(`${h}.${b}`)), 'signature verifies with the public key');
const n0 = calls.length;
await accessToken(SA, 1_800_000_000 + 1000);
ok(calls.length === n0, 'token reused within the hour');
await accessToken(SA, 1_800_000_000 + 3400);
ok(calls.length === n0 + 1, 'token refreshed 5 minutes before it expires');

section('Message');
const payload = { kind: 'alert', id: 'abc123defg', title: 'New Loch Ness Monster report 4 mi away', body: 'Dores Beach: a long dark hump',
  url: 'https://encounteratlas.com/reports/abc123defg/?source=alert', cluster: { count: 3 } };
const m = fcmMessage(TOKEN, payload);
ok(m.token === TOKEN && m.notification.title === payload.title && m.notification.body === payload.body, 'notification title and body');
ok(m.data.url === payload.url && m.data.kind === 'alert' && m.data.id === 'abc123defg' && m.data.cluster === '{"count":3}' && !('title' in m.data),
  'data: strings only, url for the tap', JSON.stringify(m.data));
ok(m.android.notification.channel_id === 'alerts' && m.android.notification.icon === 'ic_stat_ea' && m.android.notification.tag === 'abc123defg'
  && m.android.ttl === '86400s' && m.android.priority === 'NORMAL', 'android channel, icon, tag, ttl');
ok(fcmMessage(TOKEN, payload, { urgency: 'high' }).android.priority === 'HIGH', 'high urgency');

section('Sending');
let r = await sendFcm(SA, TOKEN, payload);
const send = calls[calls.length - 1];
ok(r.status === 200, 'sent');
ok(send.url === 'https://fcm.googleapis.com/v1/projects/ea-test/messages:send' && send.headers.authorization === 'Bearer ya29.test-token', 'v1 endpoint with the bearer token');
ok(JSON.parse(send.body).message.token === TOKEN, 'body is {message}');
next = () => ({ status: 404, body: { error: { code: 404, status: 'NOT_FOUND', details: [{ errorCode: 'UNREGISTERED' }] } } });
ok((await sendFcm(SA, TOKEN, payload)).status === 404, 'UNREGISTERED -> 404 (row switched off)');
next = () => ({ status: 400, body: { error: { code: 400, status: 'INVALID_ARGUMENT', message: 'The registration token is not a valid FCM registration token', details: [{ errorCode: 'INVALID_ARGUMENT' }] } } });
ok((await sendFcm(SA, TOKEN, payload)).status === 404, 'invalid token -> 404');
next = () => ({ status: 403, body: { error: { code: 403, status: 'PERMISSION_DENIED', details: [{ errorCode: 'SENDER_ID_MISMATCH' }] } } });
ok((await sendFcm(SA, TOKEN, payload)).status === -1, 'our key / project problem -> -1 (row not blamed)');
next = () => ({ status: 503, body: { error: { code: 503, status: 'UNAVAILABLE' } } });
ok((await sendFcm(SA, TOKEN, payload)).status === -1, 'FCM down -> -1');
next = () => ({ status: 401, body: { error: { code: 401, status: 'UNAUTHENTICATED' } } });
const n1 = calls.length;
ok((await sendFcm(SA, TOKEN, payload)).status === -1, '401 -> -1');
next = () => ({ status: 200, body: {} });
await sendFcm(SA, TOKEN, payload);
ok(calls.slice(n1).filter((c) => c.url === SA.token_uri).length === 1, 'after a 401 the access token is fetched again');
_resetFcmCache();
globalThis.fetch = async () => new Response('{"error":"invalid_grant"}', { status: 400 });
ok((await sendFcm(SA, TOKEN, payload)).status === -1, 'OAuth refused -> -1');

console.log(`\n${pass} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

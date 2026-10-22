// Sends one moderation test push (kind 'mod', id 'testreport') to Mike's registered mod devices.
// Usage: node tools/mod_test_push.mjs ~/Work/encounteratlas/worker
import { readFileSync } from 'fs';
const W = process.argv[2];
const { sendPush, b64u } = await import(W + '/src/webpush.js');
const env = Object.fromEntries(readFileSync(process.env.HOME + '/.config/kitchen-magpie/encounteratlas-vapid.env', 'utf8')
  .split('\n').filter((l) => l.includes('=') && !l.startsWith('#')).map((l) => { const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1).replace(/^['"]|['"]$/g, '')]; }));
const cf = Object.fromEntries(readFileSync(process.env.HOME + '/.config/kitchen-magpie/cloudflare.env', 'utf8').split('\n').filter((l) => l.includes('=')).map((l) => { const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1).replace(/^['"]|['"]$/g, '')]; }));
const q = await (await fetch('https://api.cloudflare.com/client/v4/accounts/f400124b466f991834ee7f05e61ae247/d1/database/55137f45-5eae-4b19-aff6-307856223ef0/query', {
  method: 'POST', headers: { authorization: 'Bearer ' + cf.CLOUDFLARE_API_TOKEN, 'content-type': 'application/json' },
  body: JSON.stringify({ sql: "SELECT * FROM push_subs WHERE active = 1 AND role = 'mod'" }) })).json();
const rows = q.result[0].results;
const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(env.MOD_PUSH_KEY), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
const tok = async (act) => { const exp = Math.floor(Date.now() / 1000) + 7 * 86400;
  return `${exp}.${b64u(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`mp|testreport|${act}|${exp}`)))}`; };
const payload = { kind: 'mod', id: 'testreport', title: 'TEST report: Bigfoot (not real)',
  body: 'Test only · Tap Approve or Reject to try one-tap moderation. No real report is changed.',
  url: 'https://api.encounteratlas.com/mod', approve: await tok('approve'), reject: await tok('reject') };
const vapid = { publicKey: env.VAPID_PUBLIC, privateJwk: env.VAPID_PRIVATE, subject: 'mailto:hello@encounteratlas.com' };
for (const s of rows) { const r = await sendPush(s, payload, vapid, { urgency: 'high' }); console.log(s.id, 'status', r.status); }
console.log('devices', rows.length);

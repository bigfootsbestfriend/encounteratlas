// Screenshot a page with headless Chromium, waiting real time (WebGL maps need it).
// usage: node tools/shot.mjs URL out.png [width] [height] [waitMs]
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const [url, out, w = '1300', h = '850', wait = '9000', js = ''] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random() * 500);
const chrome = spawn('chromium', ['--headless=new', `--remote-debugging-port=${port}`, '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader', `--window-size=${w},${h}`, '--hide-scrollbars', `--user-data-dir=${mkdtempSync(join(tmpdir(), 'shot-'))}`, 'about:blank'],
  { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws;
for (let i = 0; i < 50; i++) {
  try { const t = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); ws = t.find((x) => x.type === 'page').webSocketDebuggerUrl; break; } catch { await sleep(200); }
}
const sock = new WebSocket(ws);
await new Promise((r) => sock.addEventListener('open', r));
let id = 0; const pending = new Map();
sock.addEventListener('message', (m) => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d.result); pending.delete(d.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); sock.send(JSON.stringify({ id: i, method, params })); });
await send('Emulation.setDeviceMetricsOverride', { width: +w, height: +h, deviceScaleFactor: 1, mobile: +w < 600 });
await send('Page.navigate', { url });
await sleep(+wait);
if (js) { await send('Runtime.evaluate', { expression: js, awaitPromise: true }); await sleep(1200); }
const shot = await send('Page.captureScreenshot', { format: 'png' });
writeFileSync(out, Buffer.from(shot.data, 'base64'));
chrome.kill();
process.exit(0);

// Generate one creature silhouette with Gemini, clean it to pure black, trace it to SVG.
// usage: set -a; . ~/.config/kitchen-magpie/gemini.env; set +a
//        node tools/genart.mjs <slug> "<creature description>"
// Writes design/art-raw/<slug>-N.png (gitignored), design/art-src/<slug>.svg, and appends to design/art-src/gen-log.csv.
// Stops if the logged spend would pass the cap (Mike: $30 total, stop at $25).
import { readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const potrace = require('./node_modules/potrace');

const ROOT = new URL('..', import.meta.url).pathname;
const MODEL = 'gemini-3.1-flash-image';
const COST = 0.04;   // estimated USD per image
const STOP = 25;     // leave headroom under the $30 cap
const LOG = ROOT + 'design/art-src/gen-log.csv';
const [slug, desc] = process.argv.slice(2);
if (!slug || !desc) { console.error('usage: genart.mjs <slug> "<description>"'); process.exit(2); }
if (!process.env.GEMINI_API_KEY) { console.error('GEMINI_API_KEY not set'); process.exit(2); }

mkdirSync(ROOT + 'design/art-raw', { recursive: true });
if (!existsSync(LOG)) writeFileSync(LOG, 'time,slug,model,est_usd\n');
const spent = readFileSync(LOG, 'utf8').trim().split('\n').slice(1).reduce((s, l) => s + (+l.split(',')[3] || 0), 0);
if (spent + COST > STOP) { console.error(`budget stop: $${spent.toFixed(2)} logged`); process.exit(3); }

const prompt = `A single solid black silhouette of ${desc}, full body, side or three-quarter view, in a natural mid-motion pose. ` +
  'Realistic, anatomically believable proportions, like a professional wildlife silhouette or a vintage national park poster cut-out. ' +
  'Pure black fill only, no grey, no shading, no internal lines, no outline. No ground, no shadow, no background scenery, no text. ' +
  'Plain flat white background with an even margin around the figure. Square 1:1.';
const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, {
  method: 'POST',
  headers: { 'content-type': 'application/json', 'x-goog-api-key': process.env.GEMINI_API_KEY },
  body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { responseModalities: ['IMAGE'], imageConfig: { aspectRatio: '1:1' } } }),
});
appendFileSync(LOG, `${new Date().toISOString()},${slug},${MODEL},${COST}\n`);  // count every billed call
const j = await res.json();
const part = j?.candidates?.[0]?.content?.parts?.find((p) => p.inlineData);
if (!res.ok || !part) { console.error('no image:', res.status, JSON.stringify(j).slice(0, 300)); process.exit(1); }
let n = 1; while (existsSync(`${ROOT}design/art-raw/${slug}-${n}.png`)) n++;
const raw = `${ROOT}design/art-raw/${slug}-${n}.png`;
writeFileSync(raw, Buffer.from(part.inlineData.data, 'base64'));

// Pure black/white, trimmed, centred on a square with a 6% margin
const clean = `${ROOT}design/art-raw/${slug}-${n}-bw.png`;
execFileSync('magick', [raw, '-colorspace', 'gray', '-threshold', '55%', '-morphology', 'open', 'disk:1', '-trim', '+repage', clean]);
const [w, h] = execFileSync('magick', ['identify', '-format', '%w %h', clean]).toString().split(' ').map(Number);
const side = Math.round(Math.max(w, h) * 1.12);
execFileSync('magick', [clean, '-background', 'white', '-gravity', 'center', '-extent', `${side}x${side}`, '-resize', '800x800', clean]);

potrace.trace(clean, { threshold: 128, turdSize: 20, optTolerance: 0.4, color: '#000000', background: 'transparent' }, (err, svg) => {
  if (err) { console.error(err); process.exit(1); }
  writeFileSync(`${ROOT}design/art-src/${slug}.svg`, svg);
  const total = spent + COST;
  console.log(`${slug}: ${raw.replace(ROOT, '')} -> design/art-src/${slug}.svg  (logged spend $${total.toFixed(2)})`);
});

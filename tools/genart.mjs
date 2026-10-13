// Generate one creature silhouette with Gemini, clean it to pure black, trace it to SVG.
// usage: set -a; . ~/.config/kitchen-magpie/gemini.env; set +a
//        node tools/genart.mjs <slug> "<creature description>"
// Writes design/art-raw/<slug>-N.png (gitignored), design/art-src/<slug>.svg, and appends to design/art-src/gen-log.csv.
// Cost is worked out from the token counts Google returns (usageMetadata), not a flat guess: the first $30 ran out while the
// old flat 4c/image log said $12.92 (real 1K-image price is ~6.7c plus thinking tokens). Budget 2 (Mike, 2026-10-13): $30, stop at $25.
// One attempt per slug: a second call for the same slug needs RETRY=1 (and gets logged like any other).
import { readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const potrace = require('./node_modules/potrace');

const ROOT = new URL('..', import.meta.url).pathname;
const MODEL = 'gemini-3.1-flash-image';
// Google's standard rates (USD per 1M tokens): input 0.50, text+thinking output 3, image output 60 (1K image = 1120 tokens = 6.7c)
const RATE = { input: 0.5e-6, text: 3e-6, image: 60e-6 };
const EST = 0.10;    // pre-call guess per image (image + thinking), used for the budget check and for calls that return no usage
const STOP = 25;     // budget 2: $30 from Mike on 2026-10-13; leave headroom
const LOG = ROOT + 'design/art-src/gen-log2.csv';   // gen-log.csv is the first $30 (flat 4c guesses, undercounted)
const [slug, desc] = process.argv.slice(2);
if (!slug || !desc) { console.error('usage: genart.mjs <slug> "<description>"'); process.exit(2); }
if (!process.env.GEMINI_API_KEY) { console.error('GEMINI_API_KEY not set'); process.exit(2); }

mkdirSync(ROOT + 'design/art-raw', { recursive: true });
if (!existsSync(LOG)) writeFileSync(LOG, 'time,slug,model,status,prompt_tok,thought_tok,text_tok,image_tok,usd\n');
const rows = readFileSync(LOG, 'utf8').trim().split('\n').slice(1).filter(Boolean).map((l) => l.split(','));
const spent = rows.reduce((s, r) => s + (+r[8] || 0), 0);
if (spent + EST > STOP) { console.error(`budget stop: $${spent.toFixed(2)} logged`); process.exit(3); }
if (rows.some((r) => r[1] === slug) && !process.env.RETRY) { console.error(`${slug} already generated once; set RETRY=1 only if that image was unusable`); process.exit(4); }

const picto = desc.startsWith('PICTO:');  // small UI pictograms: bold shape, white cut-out details allowed
const object = picto || desc.startsWith('OBJECT:');
const what = object ? desc.slice(desc.indexOf(':') + 1).trim() : desc;
const prompt = picto
  ? `A bold solid black silhouette pictogram of ${what}. One simple, chunky, instantly readable shape that still works at 24 pixels, ` +
    'in the style of a vintage national park poster or park map symbol. Black fill only; a few important details may be shown as clean white cut-out gaps. ' +
    'No grey, no shading, no thin lines, no outline, no text, no background scenery beyond what is described. Plain flat white background with an even margin. Square 1:1.'
  : object
  ? `A single solid black silhouette of ${what}, as one bold iconic shape, seen from a dramatic but clear angle. ` +
    'Like a vintage national park poster cut-out: crisp edges, believable shape, no cartoon style. ' +
    'Pure black fill only, no grey, no shading, no internal lines, no outline. No ground, no background scenery, no text, no people unless described. ' +
    'Plain flat white background with an even margin around the subject. Square 1:1.'
  : `A single solid black silhouette of ${what}, full body, side or three-quarter view, in a natural mid-motion pose. ` +
  'Realistic, anatomically believable proportions, like a professional wildlife silhouette or a vintage national park poster cut-out. ' +
  'Pure black fill only, no grey, no shading, no internal lines, no outline. No ground, no shadow, no background scenery, no text. ' +
  'Plain flat white background with an even margin around the figure. Square 1:1.';
const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, {
  method: 'POST',
  headers: { 'content-type': 'application/json', 'x-goog-api-key': process.env.GEMINI_API_KEY },
  body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { responseModalities: ['IMAGE'], imageConfig: { aspectRatio: '1:1' } } }),
});
const j = await res.json().catch(() => ({}));
// Log every call, failed ones too, priced from what Google says it billed
const u = j.usageMetadata || {};
const out = Object.fromEntries((u.candidatesTokensDetails || []).map((d) => [d.modality, d.tokenCount]));
const tok = { prompt: u.promptTokenCount || 0, thought: u.thoughtsTokenCount || 0, text: out.TEXT || 0,
  image: out.IMAGE ?? (u.candidatesTokenCount || 0) - (out.TEXT || 0) };
const usd = u.totalTokenCount ? tok.prompt * RATE.input + (tok.thought + tok.text) * RATE.text + tok.image * RATE.image : (res.ok ? EST : 0);
appendFileSync(LOG, `${new Date().toISOString()},${slug},${MODEL},${res.status},${tok.prompt},${tok.thought},${tok.text},${tok.image},${usd.toFixed(4)}\n`);
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
  const total = spent + usd;
  console.log(`${slug}: ${raw.replace(ROOT, '')} -> design/art-src/${slug}.svg  (logged spend $${total.toFixed(2)})`);
});

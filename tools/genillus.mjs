// Generate one painted creature illustration with Gemini for the top of a creature page.
// usage: set -a; . ~/.config/kitchen-magpie/gemini.env; set +a
//        node tools/genillus.mjs <slug> "<scene description>"
// Writes design/art-raw/illus-<slug>-N.png (gitignored) and site/static/illus/<slug>.webp (1000px square).
// Shares the budget-2 ledger and $25 stop with genart.mjs; one attempt per slug unless RETRY=1.
import { readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const ROOT = new URL('..', import.meta.url).pathname;
const MODEL = 'gemini-3.1-flash-image';
const RATE = { input: 0.5e-6, text: 3e-6, image: 60e-6 };
const EST = 0.10, STOP = 25;
const LOG = ROOT + 'design/art-src/gen-log2.csv';
const [slug, desc] = process.argv.slice(2);
if (!slug || !desc) { console.error('usage: genillus.mjs <slug> "<description>"'); process.exit(2); }
if (!process.env.GEMINI_API_KEY) { console.error('GEMINI_API_KEY not set'); process.exit(2); }
const key = 'illus-' + slug;
const rows = readFileSync(LOG, 'utf8').trim().split('\n').slice(1).filter(Boolean).map((l) => l.split(','));
const spent = rows.reduce((s, r) => s + (+r[8] || 0), 0);
if (spent + EST > STOP) { console.error(`budget stop: $${spent.toFixed(2)} logged`); process.exit(3); }
if (rows.some((r) => r[1] === key) && !process.env.RETRY) { console.error(`${key} already generated once; set RETRY=1 only if it was unusable`); process.exit(4); }

const prompt = `${desc} Moody, atmospheric digital painting in a loose painterly style, like concept art for a nature documentary about legends. ` +
  'The creature is the clear subject, believable and grounded, with realistic anatomy and scale against the trees. ' +
  'Muted natural colours, soft fog and low light. No text, no lettering, no watermark, no signature, no border. Square 1:1.';
const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, {
  method: 'POST',
  headers: { 'content-type': 'application/json', 'x-goog-api-key': process.env.GEMINI_API_KEY },
  body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { responseModalities: ['IMAGE'], imageConfig: { aspectRatio: '1:1' } } }),
});
const j = await res.json().catch(() => ({}));
const u = j.usageMetadata || {};
const out = Object.fromEntries((u.candidatesTokensDetails || []).map((d) => [d.modality, d.tokenCount]));
const tok = { prompt: u.promptTokenCount || 0, thought: u.thoughtsTokenCount || 0, text: out.TEXT || 0,
  image: out.IMAGE ?? (u.candidatesTokenCount || 0) - (out.TEXT || 0) };
const usd = u.totalTokenCount ? tok.prompt * RATE.input + (tok.thought + tok.text) * RATE.text + tok.image * RATE.image : (res.ok ? EST : 0);
appendFileSync(LOG, `${new Date().toISOString()},${key},${MODEL},${res.status},${tok.prompt},${tok.thought},${tok.text},${tok.image},${usd.toFixed(4)}\n`);
const part = j?.candidates?.[0]?.content?.parts?.find((p) => p.inlineData);
if (!res.ok || !part) { console.error('no image:', res.status, JSON.stringify(j).slice(0, 300)); process.exit(1); }
mkdirSync(ROOT + 'design/art-raw', { recursive: true });
mkdirSync(ROOT + 'site/static/illus', { recursive: true });
let n = 1; while (existsSync(`${ROOT}design/art-raw/${key}-${n}.png`)) n++;
const raw = `${ROOT}design/art-raw/${key}-${n}.png`;
writeFileSync(raw, Buffer.from(part.inlineData.data, 'base64'));
const webp = `${ROOT}site/static/illus/${slug}.webp`;
execFileSync('magick', [raw, '-resize', '1000x1000^', '-gravity', 'center', '-extent', '1000x1000', '-strip', '-quality', '82', webp]);
console.log(`${slug}: ${raw.replace(ROOT, '')} -> site/static/illus/${slug}.webp  (logged spend $${(spent + usd).toFixed(2)})`);

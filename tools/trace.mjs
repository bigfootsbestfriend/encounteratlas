// Trace a black-on-white image (PNG or SVG) to a single-path SVG silhouette, trimmed and centred on a square.
// usage: node tools/trace.mjs <input.png|svg> <output.svg>
import { writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const potrace = require('./node_modules/potrace');

const [input, output] = process.argv.slice(2);
const tmp = join(mkdtempSync(join(tmpdir(), 'ea-trace-')), 'bw.png');
// No -threshold here: 1-bit output from ImageMagick comes back blank after -extent; potrace thresholds itself.
execFileSync('magick', [input, '-background', 'white', '-flatten', '-colorspace', 'gray', '-fuzz', '10%', '-trim', '+repage', tmp]);
const [w, h] = execFileSync('magick', ['identify', '-format', '%w %h', tmp]).toString().split(' ').map(Number);
const side = Math.round(Math.max(w, h) * 1.12);
execFileSync('magick', [tmp, '-background', 'white', '-gravity', 'center', '-extent', `${side}x${side}`, '-resize', '800x800', tmp]);
potrace.trace(tmp, { threshold: 128, turdSize: 20, optTolerance: 0.4, color: '#000000', background: 'transparent' }, (err, svg) => {
  if (err) { console.error(err); process.exit(1); }
  writeFileSync(output, svg);
  console.log(output);
});

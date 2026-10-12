// Rebuilds an uploaded JPEG from its image segments only, so nothing else the upload carried survives:
// no EXIF/GPS (APP1), no XMP, no ICC/maker notes, no comments (COM), no bytes after the end-of-image
// marker (where "polyglot" files hide PHP or HTML), and no other file type passed off as an image.
//
// The browser already re-encodes every photo through a canvas before upload (report.js), so a normal
// upload is a plain baseline/progressive JPEG and loses nothing here. Anything that doesn't parse as a
// well-formed JPEG is rejected outright.

const KEEP = new Set([
  0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf, // SOFn (frame headers)
  0xc4, // DHT
  0xcc, // DAC
  0xdb, // DQT
  0xdd, // DRI
]);

export class BadImage extends Error {}

export function sanitizeJpeg(input, { maxSide = 6000, minSide = 16 } = {}) {
  const b = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (b.length < 125 || b[0] !== 0xff || b[1] !== 0xd8 || b[2] !== 0xff) throw new BadImage('not a JPEG');
  const out = [new Uint8Array([0xff, 0xd8])];
  let i = 2, w = 0, h = 0, sawFrame = false, sawScan = false, ended = false;

  while (i < b.length) {
    if (b[i] !== 0xff) throw new BadImage('bad marker');
    while (b[i] === 0xff && i < b.length) i++; // fill bytes
    const m = b[i++];
    if (m === 0xd9) { ended = true; break; } // EOI: everything after it is dropped
    if (m === 0x01 || (m >= 0xd0 && m <= 0xd7)) continue; // TEM / stray RST: no payload
    if (i + 2 > b.length) throw new BadImage('truncated');
    const len = (b[i] << 8) | b[i + 1];
    if (len < 2 || i + len > b.length) throw new BadImage('bad segment length');
    const seg = b.subarray(i, i + len);

    if (m === 0xda) { // SOS: header, then entropy-coded data up to the next real marker
      if (!sawFrame) throw new BadImage('scan before frame');
      let j = i + len;
      while (j < b.length - 1) {
        if (b[j] === 0xff) {
          const n = b[j + 1];
          if (n === 0x00 || (n >= 0xd0 && n <= 0xd7) || n === 0xff) { j += n === 0xff ? 1 : 2; continue; }
          break;
        }
        j++;
      }
      out.push(new Uint8Array([0xff, m]), seg, b.subarray(i + len, j));
      sawScan = true;
      i = j;
      continue;
    }
    if (KEEP.has(m)) {
      if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xcc) {
        if (len < 8) throw new BadImage('bad frame header');
        h = (seg[3] << 8) | seg[4];
        w = (seg[5] << 8) | seg[6];
        sawFrame = true;
      }
      out.push(new Uint8Array([0xff, m]), seg);
    } else if (!((m >= 0xe0 && m <= 0xef) || m === 0xfe)) {
      // Only APPn and COM are dropped silently; any other marker means this isn't a normal photo.
      throw new BadImage('unexpected marker 0x' + m.toString(16));
    }
    i += len;
  }
  if (!ended || !sawScan) throw new BadImage('incomplete JPEG');
  if (w < minSide || h < minSide || w > maxSide || h > maxSide) throw new BadImage('odd dimensions');
  out.push(new Uint8Array([0xff, 0xd9]));

  const size = out.reduce((n, a) => n + a.length, 0);
  const res = new Uint8Array(size);
  let o = 0;
  for (const a of out) { res.set(a, o); o += a.length; }
  return { bytes: res, w, h };
}

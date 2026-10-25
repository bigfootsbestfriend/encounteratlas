"""Painted card art: Gemini images (one per creature, saved as <slug>.png in a folder) -> site/static/cards/art/<slug>.webp.

Trims the cream/white margin Gemini sometimes adds, crops to the card's art window (582 x 416 on the 750 grid,
about 1.4:1, centred), saves 2x size as WebP. Run with uv for Pillow/numpy:
  uv run --with pillow --with numpy python tools/card_art.py ~/Downloads/ea-cards [slug ...]
Then rebuild: _cards.py picks up every file in static/cards/art automatically."""
import os, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'static', 'cards', 'art')
W, H = 1164, 832   # 2x the art window


def trim_margin(im):
    a = np.asarray(im.convert('RGB')).astype(int)
    light = (a.min(axis=2) > 200) & (np.ptp(a, axis=2) < 60)   # cream/white paper
    rows = light.mean(axis=1) > 0.85
    cols = light.mean(axis=0) > 0.85
    def edge(flags):
        n = len(flags); lo, hi = 0, n
        while lo < n // 8 and flags[lo]: lo += 1
        while hi > n - n // 8 and flags[hi - 1]: hi -= 1
        return lo, hi
    t, b = edge(rows); l, r = edge(cols)
    pad = 6 if (t or l or b < len(rows) or r < len(cols)) else 0   # step past the border's own ink line
    return im.crop((l + pad if l else 0, t + pad if t else 0, r - pad if r < len(cols) else r, b - pad if b < len(rows) else b))


def fit(im):
    w, h = im.size
    target = W / H
    if w / h > target:
        nw = round(h * target); x = (w - nw) // 2; im = im.crop((x, 0, x + nw, h))
    else:
        nh = round(w / target); y = max(0, (h - nh) // 2 - round(h * 0.03)); im = im.crop((0, y, w, y + nh))   # keep heads in frame
    return im.resize((W, H), Image.LANCZOS)


def main():
    src = os.path.expanduser(sys.argv[1])
    only = set(sys.argv[2:])
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(src)):
        slug, ext = os.path.splitext(fn)
        if ext.lower() not in ('.png', '.jpg', '.jpeg', '.webp') or (only and slug not in only):
            continue
        im = fit(trim_margin(Image.open(os.path.join(src, fn)).convert('RGB')))
        im.save(os.path.join(OUT, slug + '.webp'), 'WEBP', quality=78, method=6)
        n += 1
    print(f'{n} card images written to {OUT}')


if __name__ == '__main__':
    main()

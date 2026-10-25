"""Small copies of the painted card art for strips and tiles (home page "Today's listen", the app home).

site/static/cards/art/<slug>.webp (1164 x 832, about 125 KB) -> site/static/cards/thumb/<slug>.webp (360 wide, about 18 KB).
Only redoes a thumb when its art is newer. Needs ImageMagick (magick). Run after tools/card_art.py:
  python3 tools/card_thumbs.py
_podplay.art_thumb() falls back to the full art when a thumb is missing, so a forgotten run only costs page weight."""
import os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'site', 'static', 'cards', 'art')
OUT = os.path.join(ROOT, 'site', 'static', 'cards', 'thumb')

os.makedirs(OUT, exist_ok=True)
done = 0
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith('.webp'):
        continue
    src, dst = os.path.join(SRC, fn), os.path.join(OUT, fn)
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        continue
    subprocess.run(['magick', src, '-resize', '360x', '-strip', '-quality', '72', dst], check=True)
    done += 1
print(f'card thumbs: {done} made, {len(os.listdir(OUT))} in {OUT}')

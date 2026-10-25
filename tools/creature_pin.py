"""Pinterest pin images (1000x1500, 2:3) for creature pages: the park-poster art big, then name, short line and logo.

usage: python3 tools/creature_pin.py [--force] [slug ...]
Writes site/static/pins/creatures/<slug>.jpg (rendered here and committed, like creature_og.py). ~/Work/ea-promo pins
one creature a day through Metricool using these.
Needs rsvg-convert, magick and the Zilla Slab + Public Sans fonts installed locally.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap

from creature_og import LABEL, ROOT, SKY, STATIC, esc

OUT = os.path.join(STATIC, 'pins', 'creatures')


def art(c):
    s = re.sub(r'<\?xml[^>]*>', '', open(os.path.join(STATIC, c['art'] + '.svg')).read())
    y = 250 if c['cat'] == 'aquatic' else 190
    return s.replace('<svg ', f'<svg x="210" y="{y}" width="580" height="580" ', 1)


def card(c):
    a, b = SKY.get(c['cat'], SKY['other'])
    for size, width in ((96, 15), (80, 18), (66, 22)):
        lines = textwrap.wrap(c['name'], width)
        if len(lines) <= 2:
            break
    lines = lines[:2]
    y0 = (1040 if len(lines) == 1 else 1020) + size
    name = ''.join(f'<tspan x="500" y="{y0 + i * size * 1.05:.0f}">{esc(t)}</tspan>' for i, t in enumerate(lines))
    sy = y0 + (len(lines) - 1) * size * 1.05 + 62
    wrapped = textwrap.wrap(c['summary'], 46)
    keep = 3 if len(lines) == 1 else 2
    summ = wrapped[:keep]
    if len(wrapped) > keep:
        summ[-1] = summ[-1].rstrip('.,;: ') + '…'
    summ = ''.join(f'<tspan x="500" dy="{0 if i == 0 else 40}">{esc(t)}</tspan>' for i, t in enumerate(summ))
    logo = re.sub(r'<\?xml[^>]*>', '', open(os.path.join(STATIC, 'logo-mark.svg')).read()).replace(
        '<svg ', '<svg x="300" y="1392" width="56" height="56" ', 1)
    ground = ('<rect x="80" y="760" width="840" height="170" fill="#2B4A55"/>' if c['cat'] == 'aquatic' else
              '<path d="M80 860L130 740 180 860 225 712 275 860 650 860 700 690 750 860 800 725 850 860 920 760V930H80Z" fill="#1E3A2F"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1000" height="1500" viewBox="0 0 1000 1500">
<defs><radialGradient id="g" cx="50%" cy="35%" r="80%"><stop offset="0" stop-color="#1F3A30"/><stop offset="1" stop-color="#11211B"/></radialGradient>
<linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>
<clipPath id="p"><rect x="80" y="130" width="840" height="800" rx="28"/></clipPath></defs>
<rect width="1000" height="1500" fill="url(#g)"/>
<text x="500" y="92" text-anchor="middle" font-family="Public Sans" font-weight="700" font-size="30" letter-spacing="3" fill="#F2B33D">{esc(c.get('label') or LABEL.get(c['cat'], 'CRYPTID'))}</text>
<g clip-path="url(#p)"><rect x="80" y="130" width="840" height="800" fill="url(#s)"/><circle cx="760" cy="260" r="76" fill="#F3E3B8" opacity=".9"/>
<path d="M80 740L200 620 300 690 420 560 560 670 680 590 920 700V930H80Z" fill="#5E4A3A" opacity=".5"/>{ground}{art(c)}</g>
<rect x="80" y="130" width="840" height="800" rx="28" fill="none" stroke="#F3E3B8" stroke-width="10"/>
<text text-anchor="middle" font-family="Zilla Slab" font-weight="700" font-size="{size}" fill="#E8EFD9">{name}</text>
<text x="500" y="{sy:.0f}" text-anchor="middle" font-family="Public Sans" font-size="30" fill="#A9BCA7">{summ}</text>
{logo}
<text x="372" y="1432" font-family="Zilla Slab" font-weight="700" font-size="34" fill="#E8EFD9">encounteratlas.com</text>
</svg>'''


def main(argv):
    force = '--force' in argv
    slugs = {a for a in argv if not a.startswith('--')}
    crit = json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for c in crit:
        if slugs and c['slug'] not in slugs:
            continue
        if not c.get('art') and os.path.exists(os.path.join(STATIC, 'art', c['slug'] + '.svg')):
            c['art'] = 'art/' + c['slug']
        if not c.get('art'):
            continue
        jpg = os.path.join(OUT, c['slug'] + '.jpg')
        if os.path.exists(jpg) and not force and not slugs:
            continue
        with tempfile.TemporaryDirectory() as td:
            svg, png = os.path.join(td, 'c.svg'), os.path.join(td, 'c.png')
            open(svg, 'w').write(card(c))
            subprocess.run(['rsvg-convert', '-w', '1000', '-h', '1500', '-o', png, svg], check=True)
            subprocess.run(['magick', png, '-strip', '-quality', '82', jpg], check=True)
        n += 1
    print(f'{n} pin images written to site/static/pins/creatures/')


if __name__ == '__main__':
    main(sys.argv[1:])

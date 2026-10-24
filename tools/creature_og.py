"""Share images (1200x630) for creature pages: name, category, short line and the park-poster art.

usage: python3 tools/creature_og.py [--force] [slug ...]
Writes site/static/og/creatures/<slug>.jpg; build.py uses one when it exists (og:image and the Article schema image).
Needs rsvg-convert, magick and the Zilla Slab + Public Sans fonts installed locally (rendered here and committed, not in CI).
"""
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
STATIC = os.path.join(ROOT, 'site', 'static')
OUT = os.path.join(STATIC, 'og', 'creatures')
# same skies as poster() in site/build.py
SKY = {'hominid': ('#E3A649', '#B5532F'), 'canid': ('#3B4C6B', '#1B2A3A'), 'winged': ('#3B4C6B', '#1B2A3A'),
       'aquatic': ('#E8B04A', '#C8693A'), 'entity': ('#3B4C6B', '#1B2A3A'), 'ufo': ('#2E3E5C', '#141E2E'), 'fae': ('#C97B9A', '#4A2E4F'), 'other': ('#E3A649', '#B5532F')}
LABEL = {'hominid': 'APE-MAN', 'canid': 'DOGMAN AND WOLF', 'winged': 'WINGED', 'aquatic': 'LAKE AND SEA MONSTER', 'entity': 'STRANGE BEING',
         'ufo': 'UFO', 'fae': 'FOLK AND FAE', 'other': 'CRYPTID'}
esc = lambda s: html.escape(s, quote=True)


def art(c):
    s = open(os.path.join(STATIC, c['art'] + '.svg')).read()
    s = re.sub(r'<\?xml[^>]*>', '', s)
    y = 158 if c['cat'] == 'aquatic' else 128
    return s.replace('<svg ', f'<svg x="724" y="{y}" width="390" height="390" ', 1)


def card(c):
    a, b = SKY.get(c['cat'], SKY['other'])
    for size, width in ((84, 13), (72, 15), (60, 19)):
        lines = textwrap.wrap(c['name'], width)
        if len(lines) <= 2:
            break
    lines = lines[:2]
    y0 = 250 if len(lines) == 1 else 215
    name = ''.join(f'<tspan x="70" y="{y0 + i * size * 1.05:.0f}">{esc(t)}</tspan>' for i, t in enumerate(lines))
    sy = y0 + (len(lines) - 1) * size * 1.05 + 64
    summ = textwrap.wrap(c['summary'], 40)[:3]
    if len(textwrap.wrap(c['summary'], 40)) > 3:
        summ[-1] = summ[-1].rstrip('.,;: ') + '…'
    summ = ''.join(f'<tspan x="70" dy="{0 if i == 0 else 38}">{esc(t)}</tspan>' for i, t in enumerate(summ))
    logo = re.sub(r'<\?xml[^>]*>', '', open(os.path.join(STATIC, 'logo-mark.svg')).read()).replace('<svg ', '<svg x="70" y="528" width="54" height="54" ', 1)
    ground = ('<rect x="690" y="470" width="460" height="110" fill="#2B4A55"/>' if c['cat'] == 'aquatic' else
              '<path d="M690 545L722 470 754 545 782 452 814 545 1022 545 1054 440 1086 545 1118 462 1150 545V580H690Z" fill="#1E3A2F"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="630" viewBox="0 0 1200 630">
<defs><radialGradient id="g" cx="30%" cy="50%" r="70%"><stop offset="0" stop-color="#1F3A30"/><stop offset="1" stop-color="#11211B"/></radialGradient>
<linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>
<clipPath id="p"><rect x="690" y="50" width="460" height="530" rx="22"/></clipPath></defs>
<rect width="1200" height="630" fill="url(#g)"/>
<g clip-path="url(#p)"><rect x="690" y="50" width="460" height="530" fill="url(#s)"/><circle cx="1040" cy="150" r="54" fill="#F3E3B8" opacity=".9"/>
<path d="M690 470L758 398 815 438 883 360 962 428 1030 374 1150 446V580H690Z" fill="#5E4A3A" opacity=".5"/>{ground}{art(c)}</g>
<rect x="690" y="50" width="460" height="530" rx="22" fill="none" stroke="#F3E3B8" stroke-width="8"/>
<text x="70" y="130" font-family="Public Sans" font-weight="700" font-size="24" letter-spacing="2.5" fill="#F2B33D">{LABEL.get(c['cat'], 'CRYPTID')}</text>
<text font-family="Zilla Slab" font-weight="700" font-size="{size}" fill="#E8EFD9">{name}</text>
<text x="70" y="{sy:.0f}" font-family="Public Sans" font-size="28" fill="#A9BCA7">{summ}</text>
{logo}
<text x="138" y="566" font-family="Zilla Slab" font-weight="700" font-size="32" fill="#E8EFD9">Encounter Atlas</text>
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
            subprocess.run(['rsvg-convert', '-w', '1200', '-h', '630', '-o', png, svg], check=True)
            subprocess.run(['magick', png, '-strip', '-quality', '84', jpg], check=True)
        n += 1
    print(f'{n} share images written to site/static/og/creatures/')


if __name__ == '__main__':
    main(sys.argv[1:])

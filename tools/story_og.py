"""Share images (1200x630) for witness story pages: title, creature silhouette, place and year.

usage: python3 tools/story_og.py [--force] [story-id ...]
Writes site/static/og/stories/<id>.jpg; build.py uses one when it exists. Needs rsvg-convert, magick and the
Zilla Slab + Public Sans fonts installed locally (rendered here and committed, not in CI).
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
OUT = os.path.join(STATIC, 'og', 'stories')
CAT = {'hominid': '#D9A05B', 'canid': '#D0633F', 'winged': '#B98ACB', 'aquatic': '#4FB3A9',
       'entity': '#9CC46B', 'fae': '#E58FB0', 'ufo': '#8E8CF0', 'other': '#E0C36A'}
esc = lambda s: html.escape(s, quote=True)


def art_svg(c, colour):
    """The creature's poster silhouette as an inline <svg>, recoloured."""
    path = os.path.join(STATIC, (c.get('art') or '') + '.svg')
    if not c.get('art') or not os.path.exists(path):
        return ''
    s = open(path).read()
    s = re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', f'fill="{colour}"', s)
    if 'fill=' not in s.split('>', 1)[0]:
        s = s.replace('<svg ', f'<svg fill="{colour}" ', 1)
    return s.replace('<svg ', '<svg x="700" y="95" width="440" height="440" opacity="0.95" ', 1)


def card(st, c):
    colour = CAT.get(c['cat'], CAT['other'])
    for size, width in ((70, 20), (60, 24), (52, 28)):
        lines = textwrap.wrap(st['title'], width)
        if len(lines) <= 3:
            break
    lines = lines[:3]
    lh = size * 1.1
    y0 = 215 if len(lines) < 3 else 195
    title = ''.join(f'<tspan x="70" y="{y0 + i * lh:.0f}">{esc(t)}</tspan>' for i, t in enumerate(lines))
    meta_y = y0 + (len(lines) - 1) * lh + 62
    meta = st['place'] if str(st['year']) in st['place'] else f'{st["place"]} · {st["year"]}'
    meta = ''.join(f'<tspan x="70" dy="{0 if i == 0 else 36}">{esc(t)}</tspan>' for i, t in enumerate(textwrap.wrap(meta, 42)[:2]))
    logo = open(os.path.join(STATIC, 'logo-mark.svg')).read().replace('<svg ', '<svg x="70" y="528" width="54" height="54" ', 1)
    logo = re.sub(r'<\?xml[^>]*>', '', logo)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="630" viewBox="0 0 1200 630">
<defs><radialGradient id="g" cx="78%" cy="50%" r="60%"><stop offset="0" stop-color="#1F3A30"/><stop offset="1" stop-color="#11211B"/></radialGradient></defs>
<rect width="1200" height="630" fill="url(#g)"/>
<rect x="0" y="0" width="1200" height="8" fill="{colour}"/>
{art_svg(c, colour)}
<text x="70" y="120" font-family="Public Sans" font-weight="700" font-size="24" letter-spacing="2.5" fill="{colour}">WITNESS STORY · {esc(c['name'].upper())}</text>
<text font-family="Zilla Slab" font-weight="700" font-size="{size}" fill="#E8EFD9">{title}</text>
<text x="70" y="{meta_y:.0f}" font-family="Public Sans" font-size="27" fill="#A9BCA7">{meta}</text>
{logo}
<text x="138" y="566" font-family="Zilla Slab" font-weight="700" font-size="32" fill="#E8EFD9">Encounter Atlas</text>
<text x="1130" y="566" text-anchor="end" font-family="Public Sans" font-size="24" fill="#F2B33D">encounteratlas.com</text>
</svg>'''


def main(argv):
    force = '--force' in argv
    ids = {a for a in argv if not a.startswith('--')}
    stories = json.load(open(os.path.join(ROOT, 'data', 'witness_stories.json')))
    crit = {c['slug']: c for c in json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))}
    # creatures.json may not carry the art path; build.py derives it from site/static/art/<slug>.svg
    for c in crit.values():
        if not c.get('art') and os.path.exists(os.path.join(STATIC, 'art', c['slug'] + '.svg')):
            c['art'] = 'art/' + c['slug']
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for st in stories:
        if ids and st['id'] not in ids:
            continue
        jpg = os.path.join(OUT, st['id'] + '.jpg')
        if os.path.exists(jpg) and not force and not ids:
            continue
        with tempfile.TemporaryDirectory() as td:
            svg, png = os.path.join(td, 'c.svg'), os.path.join(td, 'c.png')
            open(svg, 'w').write(card(st, crit[st['creature']]))
            subprocess.run(['rsvg-convert', '-w', '1200', '-h', '630', '-o', png, svg], check=True)
            subprocess.run(['magick', png, '-strip', '-quality', '84', jpg], check=True)
        n += 1
    print(f'{n} share images written to site/static/og/stories/')


if __name__ == '__main__':
    main(sys.argv[1:])

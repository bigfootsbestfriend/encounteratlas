#!/usr/bin/env python3
"""Make the downloadable files for /printables/silhouettes/ and /printables/coloring-pages/ from site/static/art/*.svg.

Needs rsvg-convert (CI doesn't have it), so run it here and commit site/static/printables/. Lists live in
data/printables.json. Usage: python3 tools/make_printables.py
"""
import json, os, re, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, 'site', 'static', 'art')
OUT = os.path.join(ROOT, 'site', 'static', 'printables')
cfg = json.load(open(os.path.join(ROOT, 'data', 'printables.json')))
names = {c['slug']: c['name'] for c in json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))}


def inner(slug, outline):
    s = open(os.path.join(ART, slug + '.svg'), encoding='utf-8').read()
    assert 'viewBox="0 0 800 800"' in s, slug
    body = re.search(r'<svg[^>]*>(.*)</svg>', s, re.S).group(1)
    if outline:
        body = re.sub(r' stroke(-width)?="[^"]*"', '', body)
        body = re.sub(r'fill="[^"]*"', 'fill="none" stroke="#000" stroke-width="3" stroke-linejoin="round"', body)
        assert 'stroke="#000"' in body, slug
    return body


os.makedirs(os.path.join(OUT, 'silhouettes'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'coloring'), exist_ok=True)
for slug in cfg['silhouettes']:
    subprocess.run(['rsvg-convert', '-w', '1600', '-h', '1600', '-a', os.path.join(ART, slug + '.svg'),
                    '-o', os.path.join(OUT, 'silhouettes', slug + '.png')], check=True)

pages = []
tmp = tempfile.mkdtemp()
for slug in cfg['coloring']:
    art = inner(slug, True)
    open(os.path.join(OUT, 'coloring', slug + '.svg'), 'w', encoding='utf-8').write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800">{art}</svg>\n')
    page = (f'<svg xmlns="http://www.w3.org/2000/svg" width="816" height="1056" viewBox="0 0 816 1056">'  # US Letter at 96 dpi
            f'<rect width="816" height="1056" fill="#fff"/>'
            f'<text x="408" y="96" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-weight="bold" font-size="40">{names[slug]}</text>'
            f'<g transform="translate(58,150) scale(0.875)">{art}</g>'
            f'<text x="408" y="1010" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-size="16" fill="#444">encounteratlas.com</text></svg>')
    f = os.path.join(tmp, slug + '.svg')
    open(f, 'w', encoding='utf-8').write(page)
    pages.append(f)
    subprocess.run(['rsvg-convert', '-f', 'pdf', f, '-o', os.path.join(OUT, 'coloring', slug + '.pdf')], check=True)
subprocess.run(['rsvg-convert', '-f', 'pdf', *pages, '-o', os.path.join(OUT, 'coloring', 'encounter-atlas-coloring-pages.pdf')], check=True)
print(len(cfg['silhouettes']), 'silhouettes,', len(pages), 'coloring pages')

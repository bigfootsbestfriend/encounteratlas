"""Copy traced creature silhouettes from design/art-src/ into site/static/art/ for the site.

Only slugs that exist in data/creatures.json are published (logo and test files stay behind). The fill becomes the
dark poster ink and the fixed width/height are dropped so the SVG scales to whatever box it's placed in.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'design', 'art-src')
OUT = os.path.join(ROOT, 'site', 'static', 'art')
INK = '#14211B'
PALE = {'alabama-white-thang': '#F1ECDD'}  # creatures known for their white coat stand out pale on the poster

slugs = {c['slug'] for c in json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))}
os.makedirs(OUT, exist_ok=True)
done, missing = [], []
for slug in sorted(slugs):
    src = os.path.join(SRC, slug + '.svg')
    if not os.path.exists(src):
        missing.append(slug)
        continue
    svg = open(src).read()
    svg = re.sub(r'\s(width|height)="[^"]*"', '', svg, count=2)
    svg = re.sub(r'fill="#0{3,6}"', f'fill="{PALE.get(slug, INK)}"', svg)
    open(os.path.join(OUT, slug + '.svg'), 'w').write(svg)
    done.append(slug)
print(f'published {len(done)}; no art yet for {len(missing)}: {", ".join(missing)}')

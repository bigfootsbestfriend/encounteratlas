"""Point the old creature icon names at the park-poster silhouettes.

Writes data/icon_art.json ({icon name: art slug}). build.py's icon() then draws those names as a CSS mask of
static/art/<slug>.svg, and the matching site/static/icons/<name>.svg files are rewritten from the art (fill
currentColor) so the map, search and size-comparison scripts that fetch icons by name get the new art too.
Pictograms that aren't creatures (folder, festival, q-* quiz answers, footprint...) are left alone.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, 'site', 'static', 'art')
ICONS = os.path.join(ROOT, 'site', 'static', 'icons')
# Generic names, and the less obvious picks for the category tiles (Mike finds Bigfoot overused)
PICK = {'hominid': 'yowie', 'lake': 'loch-ness-monster', 'entity': 'grey-aliens', 'winged': 'jersey-devil',
        'mib': 'men-in-black', 'orbs': 'ufo-orbs', 'serpent': 'sea-serpent', 'hound': 'black-shuck',
        'bigcat': 'beast-of-bodmin', 'bigfish': 'white-river-monster', 'pterosaur': 'ropen', 'imp': 'pukwudgie',
        'military': 'ufo-tic-tac'}

creatures = json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))
m = {}
for c in creatures:
    m.setdefault(c['icon'], c['slug'])
m.update(PICK)
m = {k: v for k, v in sorted(m.items()) if os.path.exists(os.path.join(ART, v + '.svg'))}
for name, slug in m.items():
    svg = open(os.path.join(ART, slug + '.svg')).read()
    svg = re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', 'fill="currentColor"', svg)
    open(os.path.join(ICONS, name + '.svg'), 'w').write(svg)
json.dump(m, open(os.path.join(ROOT, 'data', 'icon_art.json'), 'w'), indent=1)
print(f'{len(m)} icon names now use poster art')

"""Official government UFO programmes by country, 1946 to today: a timeline SVG for Wikimedia Commons and /press/.

Data: data/ufo_programs.json (each programme's dates come from the official sources listed on
https://encounteratlas.com/ufo/programs/). Plain SVG, system fonts, no scripts. Run: python3 programs_chart.py
Writes the file here and copies it to site/static/img/charts/ for the press page.
"""
import datetime, json, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
NAME = 'Official_UFO_programmes_by_country.svg'
ORDER = ['us', 'ca', 'gb', 'fr', 'es', 'it', 'be', 'dk', 'se', 'su', 'br', 'cl', 'ar', 'pe', 'uy', 'au', 'nz', 'jp']
NAMES = {'us': 'United States', 'ca': 'Canada', 'gb': 'United Kingdom', 'fr': 'France', 'es': 'Spain', 'it': 'Italy', 'be': 'Belgium',
         'dk': 'Denmark', 'se': 'Sweden', 'su': 'USSR', 'br': 'Brazil', 'cl': 'Chile', 'ar': 'Argentina', 'pe': 'Peru', 'uy': 'Uruguay',
         'au': 'Australia', 'nz': 'New Zealand', 'jp': 'Japan'}
CLOSED, ACTIVE, INK, GRID = '#7B78D6', '#E3A21A', '#222222', '#E2E2E2'

progs = json.load(open(os.path.join(ROOT, 'data', 'ufo_programs.json'), encoding='utf-8'))
now = datetime.date.today().year
Y0, Y1 = 1945, now + 1
rows = []
for cc in ORDER:
    ps = sorted([p for p in progs if p['country'] == cc], key=lambda p: (p['start'], p['name']))
    if ps:
        rows.append(('h', NAMES[cc]))
        rows += [('p', p) for p in ps]
assert len([r for r in rows if r[0] == 'p']) == len(progs), 'a country is missing from ORDER'

W, L, R, T = 1100, 260, 30, 100
RH, HH = 17, 22
H = T + sum(HH if k == 'h' else RH for k, _ in rows) + 60
pw = W - L - R
x = lambda y: L + (y - Y0) / (Y1 - Y0) * pw
out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="DejaVu Sans, Arial, sans-serif">',
       f'<title>Official government UFO programmes by country, 1946 to {now}</title>',
       f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
       f'<text x="20" y="38" font-size="22" font-weight="bold" fill="{INK}">Official government UFO programmes, 1946–{now}</text>',
       f'<text x="20" y="64" font-size="14" fill="#555555">{len(progs)} programmes, studies and standing reporting systems in {len({p["country"] for p in progs})} countries. Bars show the years each one ran.</text>']
for y in range(1950, Y1, 10):
    out.append(f'<line x1="{x(y):.1f}" x2="{x(y):.1f}" y1="{T - 8}" y2="{H - 50}" stroke="{GRID}"/>')
    out.append(f'<text x="{x(y):.1f}" y="{T - 14}" font-size="12" text-anchor="middle" fill="#555555">{y}</text>')
y = T
for kind, v in rows:
    if kind == 'h':
        out.append(f'<text x="20" y="{y + 16}" font-size="13" font-weight="bold" fill="{INK}">{v}</text>')
        y += HH
        continue
    s = v['start']
    e = v['end'] if v.get('end') else now
    col = ACTIVE if v['status'] == 'active' else CLOSED
    dash = ' stroke="#7B78D6" stroke-dasharray="3 2" fill-opacity="0.35"' if v['status'] == 'unclear' else ''
    out.append(f'<text x="32" y="{y + 12}" font-size="11.5" fill="#333333">{(v.get("short") or v["name"]).replace("&", "&amp;")}</text>')
    out.append(f'<rect x="{x(s):.1f}" y="{y + 3}" width="{max(x(e + 1) - x(s), 3):.1f}" height="{RH - 6}" rx="2" fill="{col}"{dash}/>')
    y += RH
ly = H - 30
out += [f'<rect x="20" y="{ly - 11}" width="18" height="11" fill="{ACTIVE}"/><text x="44" y="{ly - 1}" font-size="12" fill="{INK}">Still running</text>',
        f'<rect x="150" y="{ly - 11}" width="18" height="11" fill="{CLOSED}"/><text x="174" y="{ly - 1}" font-size="12" fill="{INK}">Closed</text>',
        f'<rect x="250" y="{ly - 11}" width="18" height="11" fill="{CLOSED}" fill-opacity="0.35" stroke="{CLOSED}" stroke-dasharray="3 2"/><text x="274" y="{ly - 1}" font-size="12" fill="{INK}">Status unknown</text>',
        f'<text x="20" y="{H - 8}" font-size="11" fill="#666666">Sources: each programme\'s official records, listed at encounteratlas.com/ufo/programs/ (Encounter Atlas, CC BY-SA 4.0).</text>',
        '</svg>']
open(os.path.join(HERE, NAME), 'w', encoding='utf-8').write('\n'.join(out))
shutil.copy(os.path.join(HERE, NAME), os.path.join(ROOT, 'site', 'static', 'img', 'charts', NAME))
print('ok', H)

"""Project Blue Book: reported UFO sightings per year, 1947-1969 (US Air Force figures), as an SVG for Wikimedia Commons.

Source: US Air Force "UFO Fact Sheet" table "Total UFO sightings, 1947 - 1969" (public domain US government work),
copy on Commons: https://commons.wikimedia.org/wiki/File:UFO_fact_sheet.pdf . Totals 12,618 sightings, 701 unidentified.
Plain SVG with system fonts and no scripts, as Commons recommends. Run: python3 blue_book_chart.py
"""
DATA = [(1947, 122, 12), (1948, 156, 7), (1949, 186, 22), (1950, 210, 27), (1951, 169, 22), (1952, 1501, 303), (1953, 509, 42),
        (1954, 487, 46), (1955, 545, 24), (1956, 670, 14), (1957, 1006, 14), (1958, 627, 10), (1959, 390, 12), (1960, 557, 14),
        (1961, 591, 13), (1962, 474, 15), (1963, 399, 14), (1964, 562, 19), (1965, 887, 16), (1966, 1112, 32), (1967, 937, 19),
        (1968, 375, 3), (1969, 146, 1)]
assert sum(d[1] for d in DATA) == 12618 and sum(d[2] for d in DATA) == 701

W, H = 1000, 600
L, R, T, B = 80, 30, 92, 70
pw, ph = W - L - R, H - T - B
YMAX = 1600
slot = pw / len(DATA)
bw = slot * 0.72
EXPL, UNID, INK, GRID = '#9DB7C9', '#C0392B', '#222222', '#DDDDDD'


def y(v):
    return T + ph - v / YMAX * ph


out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="DejaVu Sans, Arial, sans-serif">',
       f'<title>Project Blue Book: UFO sightings reported to the US Air Force, 1947 to 1969</title>',
       f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
       f'<text x="{L}" y="36" font-size="22" font-weight="bold" fill="{INK}">UFO sightings reported to the US Air Force, 1947–1969</text>',
       f'<text x="{L}" y="62" font-size="15" fill="#555555">Projects Sign, Grudge and Blue Book. 12,618 sightings in total; 701 were left "unidentified".</text>']
for v in range(0, YMAX + 1, 200):
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GRID}" stroke-width="1"/>')
    out.append(f'<text x="{L - 10}" y="{y(v) + 5:.1f}" font-size="13" text-anchor="end" fill="#555555">{v:,}</text>')
for i, (yr, tot, un) in enumerate(DATA):
    x = L + i * slot + (slot - bw) / 2
    out.append(f'<rect x="{x:.1f}" y="{y(tot):.1f}" width="{bw:.1f}" height="{y(0) - y(tot):.1f}" fill="{EXPL}"><title>{yr}: {tot:,} sightings, {un} unidentified</title></rect>')
    out.append(f'<rect x="{x:.1f}" y="{y(un):.1f}" width="{bw:.1f}" height="{y(0) - y(un):.1f}" fill="{UNID}"/>')
    out.append(f'<text x="{x + bw / 2:.1f}" y="{y(tot) - 6:.1f}" font-size="11" text-anchor="middle" fill="#444444">{tot:,}</text>')
    out.append(f'<text x="{x + bw / 2:.1f}" y="{y(0) + 18:.1f}" font-size="12" text-anchor="middle" fill="{INK}" '
               f'transform="rotate(-45 {x + bw / 2:.1f} {y(0) + 18:.1f})" dx="-8">{yr}</text>')
out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{INK}" stroke-width="1.5"/>')
lx, ly = W - R - 300, T + 4
out += [f'<rect x="{lx}" y="{ly}" width="16" height="16" fill="{EXPL}"/>',
        f'<text x="{lx + 24}" y="{ly + 13}" font-size="14" fill="{INK}">Explained (balloons, aircraft, stars…)</text>',
        f'<rect x="{lx}" y="{ly + 26}" width="16" height="16" fill="{UNID}"/>',
        f'<text x="{lx + 24}" y="{ly + 39}" font-size="14" fill="{INK}">Unidentified</text>',
        f'<text x="{L}" y="{H - 10}" font-size="12" fill="#666666">Source: US Air Force, "UFO Fact Sheet", table "Total UFO sightings, 1947 – 1969".</text>',
        '</svg>']
open('Project_Blue_Book_UFO_sightings_by_year_1947-1969.svg', 'w').write('\n'.join(out))
print('ok')

"""Make data/region_shapes.json: a small, simplified outline of every US state and Canadian province, already
projected to SVG pixels, for the dot-picture map on the state and province hubs (site/sections/_tripadd.py).

Sources (both public domain):
  US states: US Census Bureau cartographic boundary file cb_2023_us_state_20m (KML), fetched into data/raw/census/
  Canada:    Natural Earth ne_10m_admin_1_states_provinces (collector/geo.py fetches it into data/raw/naturalearth/)

Projection: plain equirectangular with longitudes squeezed by cos(middle latitude), fitted into a 600 x 400 box.
The projection numbers are stored with each shape so the build can put dots in the same place.
Alaska is unwrapped across the dateline and the far western Aleutians are clipped.

Run: python3 tools/region_shapes.py
"""
import io, json, math, os, re, sys, urllib.request, zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'collector'))
import geo  # noqa: E402

CENSUS_URL = 'https://www2.census.gov/geo/tiger/GENZ2023/kml/cb_2023_us_state_20m.zip'
CENSUS = os.path.join(ROOT, 'data', 'raw', 'census', 'cb_2023_us_state_20m.kml')
BOX_W, BOX_H, PAD = 600, 400, 14
TOL = 1.1          # Douglas-Peucker tolerance, in output pixels
MIN_AREA = 6       # drop islands smaller than this many square pixels
MAX_CHARS = 5000   # aim for a few KB per shape
ALASKA_WEST = -172  # clip Aleutians west of this (after unwrapping the dateline)


def census_states():
    if not os.path.exists(CENSUS):
        os.makedirs(os.path.dirname(CENSUS), exist_ok=True)
        z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(CENSUS_URL).read()))
        open(CENSUS, 'wb').write(z.read('cb_2023_us_state_20m.kml'))
    kml = open(CENSUS, encoding='utf-8').read()
    out = {}
    for pm in re.findall(r'<Placemark[^>]*>(.*?)</Placemark>', kml, re.S):
        code = re.search(r'<SimpleData name="STUSPS">(\w+)</SimpleData>', pm).group(1)
        rings = []
        for poly in re.findall(r'<Polygon>(.*?)</Polygon>', pm, re.S):
            outer = re.search(r'<outerBoundaryIs>.*?<coordinates>(.*?)</coordinates>', poly, re.S).group(1)
            rings.append([tuple(map(float, p.split(',')[:2])) for p in outer.split()])
        out['US.' + code] = rings
    return out


def ne_provinces():
    out = {}
    for f in geo._load('ne_10m_admin_1_states_provinces'):
        p = f['properties']
        if p.get('iso_a2') != 'CA' or not p.get('gn_a1_code'):
            continue
        g = f['geometry']
        polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        out[p['gn_a1_code']] = [[tuple(c[:2]) for c in poly[0]] for poly in polys]
    return out


def dp(pts, tol):
    """Douglas-Peucker on a list of (x, y)."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy) or 1e-9
        best, bi = -1, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / n if (dx or dy) else math.hypot(x - x1, y - y1)
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(r):
    return abs(sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r)))) / 2


def shape(rings, wrap=False):
    if wrap:  # Alaska: put the islands past 180 next to the rest, then clip the far Aleutians
        rings = [[(x - 360 if x > 0 else x, y) for x, y in r] for r in rings]
        rings = [r for r in rings if sum(x for x, _ in r) / len(r) > ALASKA_WEST]
    lats = [y for r in rings for _, y in r]
    kx = math.cos(math.radians((min(lats) + max(lats)) / 2))
    xs = [x * kx for r in rings for x, _ in r]
    minx, maxx, maxy, miny = min(xs), max(xs), max(lats), min(lats)
    s = min((BOX_W - 2 * PAD) / (maxx - minx), (BOX_H - 2 * PAD) / (maxy - miny))
    w, h = round((maxx - minx) * s + 2 * PAD), round((maxy - miny) * s + 2 * PAD)
    proj = [[((x * kx - minx) * s + PAD, (maxy - y) * s + PAD) for x, y in r] for r in rings]
    for tol, min_area in ((TOL, MIN_AREA), (1.8, 12), (2.6, 25), (3.5, 40)):  # simplify harder until it's a few KB
        d = []
        for pr in proj:
            if area(pr) < min_area:
                continue
            pr = dp(pr, tol)
            if len(pr) < 4:
                continue
            pts = [(round(x), round(y)) for x, y in pr]
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
            d.append('M' + 'L'.join(f'{x} {y}' for x, y in pts) + 'Z')
        if sum(map(len, d)) <= MAX_CHARS:
            break
    # proj: x = (lon * kx - minx) * s + PAD, y = (maxlat - lat) * s + PAD
    return {'w': w, 'h': h, 'proj': [round(kx, 6), round(minx, 6), round(maxy, 6), round(s, 6), PAD], 'wrap': int(wrap), 'd': ''.join(d)}


def main():
    names = json.load(open(os.path.join(ROOT, 'data', 'admin1_us_ca.json'), encoding='utf-8'))
    src = {**census_states(), **ne_provinces()}
    out = {}
    for k in sorted(names):
        if k not in src:
            print('no shape for', k, names[k])
            continue
        out[k] = shape(src[k], wrap=(k == 'US.AK'))
    path = os.path.join(ROOT, 'data', 'region_shapes.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), separators=(',', ':'))
    sizes = sorted((len(v['d']), names[k]) for k, v in out.items())
    print(f'{len(out)} shapes, {os.path.getsize(path) / 1024:.0f} KB; biggest: {sizes[-3:]}')


if __name__ == '__main__':
    main()

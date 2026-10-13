"""Shared geography helpers: Natural Earth boundaries (public domain) for checking that a point lies inside the
country / state / province its record names, and label points to use as the centre of a region.

Files (fetched once into data/raw/naturalearth/, from github.com/nvkelso/natural-earth-vector):
  ne_10m_admin_0_countries.geojson         countries, keyed by ISO A2 (ISO_A2_EH)
  ne_10m_admin_1_states_provinces.geojson  states/provinces, keyed by GeoNames admin1 code (gn_a1_code, e.g. CA.01)
"""
import json, os, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
NE = os.path.join(ROOT, 'data', 'raw', 'naturalearth')
NE_URL = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/'


def _load(name):
    path = os.path.join(NE, name + '.geojson')
    if not os.path.exists(path):
        os.makedirs(NE, exist_ok=True)
        urllib.request.urlretrieve(NE_URL + name + '.geojson', path)
    return json.load(open(path, encoding='utf-8'))['features']


def _polys(geom):
    """-> list of (bbox, outer ring, holes). Rings are lists of (lon, lat)."""
    if not geom:
        return []
    raw = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    out = []
    for poly in raw:
        outer = poly[0]
        xs, ys = [p[0] for p in outer], [p[1] for p in outer]
        out.append(((min(xs), min(ys), max(xs), max(ys)), outer, poly[1:]))
    return out


def _in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _in(polys, lat, lon):
    for (x0, y0, x1, y1), outer, holes in polys:
        if x0 <= lon <= x1 and y0 <= lat <= y1 and _in_ring(lon, lat, outer) and not any(_in_ring(lon, lat, h) for h in holes):
            return True
    return False


class Areas:
    def __init__(self):
        self.a0, self.a0_label, self.a1, self.a1_label, self.a1_name = {}, {}, {}, {}, {}
        for f in _load('ne_10m_admin_0_countries'):
            p = f['properties']
            cc = p.get('ISO_A2_EH') if p.get('ISO_A2_EH') not in (None, '-99') else p.get('ISO_A2')
            if not cc or cc == '-99':
                continue
            self.a0.setdefault(cc, []).extend(_polys(f['geometry']))
            if cc not in self.a0_label or p.get('NAME') == p.get('ADMIN'):  # main entry wins over e.g. "Brazilian I."
                self.a0_label[cc] = (round(p['LABEL_Y'], 3), round(p['LABEL_X'], 3))
        for f in _load('ne_10m_admin_1_states_provinces'):
            p = f['properties']
            code = p.get('gn_a1_code') or ''
            if not code or code.endswith('.'):
                continue
            self.a1.setdefault(code, []).extend(_polys(f['geometry']))
            self.a1_label.setdefault(code, (round(p['latitude'], 3), round(p['longitude'], 3)))
            self.a1_name.setdefault(code, p['name'])

    def centre(self, cc, a1=None):
        """Label point of the province/state (if known) or the country: inside the area, unlike an average of towns."""
        if a1 and f'{cc}.{a1}' in self.a1_label:
            pt, polys = self.a1_label[f'{cc}.{a1}'], self.a1[f'{cc}.{a1}']
        elif cc in self.a0_label:
            pt, polys = self.a0_label[cc], self.a0[cc]
        else:
            return None
        if _in(polys, *pt):
            return pt
        # Some label points sit offshore (New Zealand): use the middle of the biggest polygon instead,
        # walking its bounding box on a grid until a point is on land.
        (x0, y0, x1, y1), outer, holes = max(polys, key=lambda p: (p[0][2] - p[0][0]) * (p[0][3] - p[0][1]))
        best = None
        for i in range(1, 20):
            for j in range(1, 20):
                lat, lon = y0 + (y1 - y0) * i / 20, x0 + (x1 - x0) * j / 20
                if _in([((x0, y0, x1, y1), outer, holes)], lat, lon):
                    d = (lat - (y0 + y1) / 2) ** 2 + (lon - (x0 + x1) / 2) ** 2
                    if best is None or d < best[0]:
                        best = (d, (round(lat, 3), round(lon, 3)))
        return best[1] if best else pt

    def inside(self, lat, lon, cc, a1=None, slack=0.12):
        """True / False, or None when there's no boundary to check against. `slack` (degrees) forgives coastal
        towns and islands that fall just outside the 1:10m coastline."""
        polys = self.a1.get(f'{cc}.{a1}') if a1 else None
        polys = polys or self.a0.get(cc)
        if not polys:
            return None
        if _in(polys, lat, lon):
            return True
        return any(_in(polys, lat + dy, lon + dx) for dy in (-slack, 0, slack) for dx in (-slack, 0, slack) if dx or dy)

    def where(self, lat, lon):
        """(cc, admin1 code or None) of the area containing the point, or (None, None)."""
        cc = next((k for k, v in self.a0.items() if _in(v, lat, lon)), None)
        a1 = next((k.split('.', 1)[1] for k, v in self.a1.items() if (not cc or k.startswith(cc + '.')) and _in(v, lat, lon)), None)
        return cc, a1

"""Fetch the driving route for each sample road trip in data/road_trips.json from the FOSSGIS OSRM server
(routing.openstreetmap.de, OpenStreetMap data) once, simplify it, and store it back in the same file under 'route'.
Run by hand when a trip's waypoints change: python3 tools/road_trip_routes.py [slug ...]"""
import json, math, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, 'data', 'road_trips.json')


def simplify(pts, tol_km=0.8):
    """Douglas-Peucker on lon/lat with an equirectangular km projection."""
    if len(pts) < 3:
        return pts
    lat0 = math.radians(sum(p[1] for p in pts) / len(pts))
    xy = [(p[0] * 111.32 * math.cos(lat0), p[1] * 110.57) for p in pts]
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = xy[a], xy[b]
        dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1e-9
        best, bi = 0, None
        for i in range(a + 1, b):
            d = abs(dy * (xy[i][0] - ax) - dx * (xy[i][1] - ay)) / L
            if d > best: best, bi = d, i
        if bi is not None and best > tol_km:
            keep[bi] = True; stack += [(a, bi), (bi, b)]
    return [[round(p[0], 4), round(p[1], 4)] for p, k in zip(pts, keep) if k]


trips = json.load(open(F))
only = set(sys.argv[1:])
for t in trips:
    if only and t['slug'] not in only:
        continue
    coords = ';'.join(f'{w[2]},{w[1]}' for w in t['waypoints'])
    url = f'https://routing.openstreetmap.de/routed-car/route/v1/driving/{coords}?overview=full&geometries=geojson'
    req = urllib.request.Request(url, headers={'user-agent': 'EncounterAtlasBuild/1.0 (+https://encounteratlas.com)'})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    r = d['routes'][0]
    t['route'] = simplify(r['geometry']['coordinates'])
    t['km'] = round(r['distance'] / 1000)
    t['hours'] = round(r['duration'] / 3600, 1)
    print(t['slug'], t['km'], 'km', t['hours'], 'h', len(r['geometry']['coordinates']), '->', len(t['route']), 'pts')
    time.sleep(1.5)
json.dump(trips, open(F, 'w'), ensure_ascii=False, indent=1)

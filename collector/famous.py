"""Geocode the famous cases in data/creatures.json -> data/famous_geo.json (for the map's creature layer).

Uses the same GeoNames matching as collector/bluebook.py. Places it can't match to a town fall back to
data/famous_overrides.json (hand-checked "place": [lat, lon]); anything still unmatched is printed.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bluebook as bb

ROOT = bb.ROOT
OVR = os.path.join(ROOT, 'data', 'famous_overrides.json')


def main():
    creatures = json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))
    overrides = json.load(open(OVR)) if os.path.exists(OVR) else {}
    countries, country_names, admin1, _admin1_cc, us_abbr, by_place, centres = bb.load_geonames()
    out, missing = [], []
    for c in creatures:
        for f in c.get('famous', []):
            place = f['place']
            lat = lon = None
            prec = 'place'
            if place in overrides:
                lat, lon = overrides[place]
            else:
                parts = [p.strip() for p in place.split(',')]
                cc = a1 = None
                if len(parts) >= 2:
                    kind, info = bb.resolve_region(bb.region_key(parts[-1]), admin1, country_names, us_abbr)
                    if kind == 'a1':
                        cc, a1, _ = info
                    elif kind == 'cc':
                        cc = info
                if cc:
                    for p in parts[:-1]:
                        for cand in bb.place_candidates(p):
                            for key in ((cc, a1 or '', cand), (cc, a1 or '', cand + '#full')) + (() if a1 else ((cc, '', cand),)):  # never jump to another state
                                hits = by_place.get(key)
                                if hits:
                                    _, lat, lon, _ = max(hits)
                                    break
                            if lat is not None:
                                break
                        if lat is not None:
                            break
            if lat is None:
                missing.append(place)
                continue
            out.append({'creature': c['slug'], 'cat': c['cat'], 'icon': c['icon'], 'name': f['name'], 'year': f['year'],
                        'place': place, 'lat': round(lat, 4), 'lon': round(lon, 4)})
    json.dump(out, open(os.path.join(ROOT, 'data', 'famous_geo.json'), 'w'), indent=0)
    print(f'{len(out)} famous cases placed; {len(missing)} need overrides:', file=sys.stderr)
    for m in sorted(set(missing)):
        print('  ', m, file=sys.stderr)


if __name__ == '__main__':
    main()

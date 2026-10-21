"""Archive layers for the /near-me/ map (the site and the app), split into 5-degree static JSON tiles.

Reads the map GeoJSON that site/build.py already wrote to _site/data/ (so the competitor scrub, the Blue Book
approximate-location rule and the geocoding checks are the same as on the full map) and writes _site/data/near/:

  index.json                    tile list, per-layer counts and a source/licence note for every dataset
  <lat0>_<lon0>.json            FeatureCollection for lat0..lat0+5, lon0..lon0+5 (south-west corner, floored)

Each feature has properties.src: bluebook | bluebook_approx | faa | pursue | canada.
bluebook_approx are the faded "about N files somewhere in X" rings, never pins.

site/sections/z_near_me.py calls build_tiles() during every build; run this file alone to rebuild just the tiles:
  python3 tools/near_me_tiles.py [--out DIR]
"""
import argparse, json, math, os, re
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, '_site', 'data')
STEP = 5

LAYERS = {
    'bluebook': ('bluebook.geojson', 'Project Blue Book (US Air Force, 1947 to 1969)',
                 'US National Archives, Sanitized Version of Project Blue Book Case Files. US federal records, public domain.'),
    'bluebook_approx': ('bluebook_approx.geojson', 'Project Blue Book, files with only a state, province or country',
                        'Same source. Drawn as faded rings, never as pins, because the place is approximate.'),
    'faa': ('ufo_faa.geojson', 'FAA pilot and controller UAP reports (2007 to 2024)',
            'US Federal Aviation Administration records. US federal records, public domain.'),
    'pursue': ('ufo_pursue.geojson', 'PURSUE declassified UAP records (2026)',
               'US Department of War. US federal records, public domain.'),
    'canada': ('ufo_canada.geojson', 'Canadian UFO Survey (1989 to 2025), sightings per town',
               'Compiled by Ufology Research. Credit by name only, no link (Mike, 2026-10-12). '
               'Rows from competitor groups are removed by collector/cufos.py.'),
}
BLOCKED = re.compile(r'bfro|nuforc|mufon|enigma ?labs|cryptid ?(catchers|atlas)', re.I)


def tile_key(lon, lat):
    la = min(85, max(-90, math.floor(lat / STEP) * STEP))
    lo = min(175, max(-180, math.floor(lon / STEP) * STEP))
    return f'{la}_{lo}'


def build_tiles(src_dir=SRC, out_dir=os.path.join(SRC, 'near')):
    """Returns (number of tiles, Counter of features per layer)."""
    tiles, counts = defaultdict(list), Counter()
    for src, (fn, _, _) in LAYERS.items():
        path = os.path.join(src_dir, fn)
        if not os.path.exists(path):
            raise FileNotFoundError(f'{path} missing: run python3 site/build.py first')
        for f in json.load(open(path))['features']:
            lon, lat = f['geometry']['coordinates'][:2]
            props = dict(f.get('properties') or {})
            props['src'] = src
            feat = {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(lon, 4), round(lat, 4)]}, 'properties': props}
            if BLOCKED.search(json.dumps(feat)):
                raise ValueError(f'blocked source name in {fn}: {json.dumps(feat)[:200]}')
            tiles[tile_key(lon, lat)].append(feat)
            counts[src] += 1
    tdir = out_dir
    os.makedirs(tdir, exist_ok=True)
    for old in os.listdir(tdir):
        if old.endswith('.json') and old != 'index.json' and old[:-5] not in tiles:
            os.remove(os.path.join(tdir, old))
    for k, feats in tiles.items():
        with open(os.path.join(tdir, k + '.json'), 'w') as fh:
            json.dump({'type': 'FeatureCollection', 'features': feats}, fh, separators=(',', ':'), ensure_ascii=False)
    index = {
        'step_deg': STEP,
        'tile_name': '<lat0>_<lon0>.json, south-west corner floored to a multiple of 5',
        'layers': {k: {'title': t, 'source': s, 'count': counts[k]} for k, (_, t, s) in LAYERS.items()},
        'tiles': {k: Counter(f['properties']['src'] for f in v) for k, v in sorted(tiles.items())},
    }
    with open(os.path.join(tdir, 'index.json'), 'w') as fh:
        json.dump(index, fh, separators=(',', ':'))
    return len(tiles), counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(SRC, 'near'))
    args = ap.parse_args()
    n, counts = build_tiles(SRC, args.out)
    print(f'{n} tiles, {sum(counts.values())} features ({dict(counts)}) -> {os.path.relpath(args.out, ROOT)}')


if __name__ == '__main__':
    main()

"""Sanity check: is every map point inside the country / state / province its record names?

Uses Natural Earth boundaries (public domain, collector/geo.py) and GeoNames admin1 names. Exact points that fall
outside their named area are listed as MISMATCH; approximate points are checked too (their centre must be inside).
  python3 tools/geo_check.py            report
  python3 tools/geo_check.py --strict   exit 1 when anything is off (for the build)
"""
import json, os, re, sys, unicodedata
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'collector'))
from geo import Areas  # noqa: E402

GEO = os.path.join(ROOT, 'data', 'raw', 'geonames')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z ]+', ' ', s)).strip()


COUNTRY = {}
for line in open(os.path.join(GEO, 'countryInfo.txt'), encoding='utf-8'):
    if not line.startswith('#'):
        p = line.split('\t')
        COUNTRY[norm(p[4])] = p[0]
COUNTRY.update({'usa': 'US', 'us': 'US', 'u s': 'US', 'united states': 'US', 'america': 'US', 'uk': 'GB', 'england': 'GB',
                'scotland': 'GB', 'wales': 'GB', 'northern ireland': 'GB', 'great britain': 'GB', 'united kingdom': 'GB',
                'russia': 'RU', 'ussr': 'RU', 'soviet union': 'RU', 'south korea': 'KR', 'north korea': 'KP', 'iran': 'IR',
                'czech republic': 'CZ', 'czechia': 'CZ', 'the netherlands': 'NL', 'holland': 'NL', 'vietnam': 'VN', 'laos': 'LA',
                'bolivia': 'BO', 'venezuela': 'VE', 'tanzania': 'TZ', 'syria': 'SY', 'taiwan': 'TW', 'congo': 'CD',
                'democratic republic of the congo': 'CD', 'ivory coast': 'CI', 'papua new guinea': 'PG', 'new guinea': 'PG'})
ADMIN1 = defaultdict(list)  # norm(name) -> [(cc, code)]
for line in open(os.path.join(GEO, 'admin1CodesASCII.txt'), encoding='utf-8'):
    key, name, ascii_name, _ = line.rstrip('\n').split('\t')
    cc, code = key.split('.')
    for n in {norm(name), norm(ascii_name)}:
        ADMIN1[n].append((cc, code))
US_POSTAL = {code.lower(): code for n, v in ADMIN1.items() for cc, code in v if cc == 'US'}


def claim(rec):
    """-> (cc, admin1 code or None) the record says it is in, from its fields and place text."""
    cc = rec.get('cc') or (rec.get('country') if len(str(rec.get('country') or '')) == 2 else None)
    if not cc and rec.get('country'):
        cc = COUNTRY.get(norm(rec['country']))
    texts = [rec.get(k) for k in ('state', 'region', 'a1name') if rec.get(k)]
    place = rec.get('place') or ''
    parts = [x.strip() for x in re.split(r'[,;(]', place) if x.strip(' )')]
    texts += list(reversed(parts))
    if not cc:
        for t in reversed(parts):
            if norm(t) in COUNTRY:
                cc = COUNTRY[norm(t)]
                break
    for t in texts:
        n = norm(t)
        hits = ADMIN1.get(n, [])
        if cc:
            hits = [h for h in hits if h[0] == cc]
        elif len({h[0] for h in hits}) > 1:
            hits = [h for h in hits if h[0] in ('US', 'CA', 'AU', 'GB')] or hits
        if hits:
            return hits[0][0], hits[0][1]
        if cc == 'US' and n in US_POSTAL:
            return 'US', US_POSTAL[n]
    return cc, None


# Checked by hand: the point is right and the area guess from the text is wrong (sea, small islands, name clashes).
KNOWN_OK = {
    'UAP 11/9/2020': 'Bimini: small island outside the 1:10m coastline',
    'Unresolved UAP Report, Africa, 2025': 'Djibouti: city and region share the name; point is in Djibouti',
    'State Department UAP Cable 005, Mexico, September 16, 2003': '"Mexico" is the country, not Mexico State',
    'An old tale of an eight-foot hairy giant in Georgia': 'US state, not the country',
    'A copper-coloured killer of calves in Bartow County': 'US state, not the country',
    'A dragon on the Flat Rock derrick': 'Mexico, Missouri',
    'A white serpent off the New England coast': 'at sea off Massachusetts',
    'An eagle tries to carry off a girl': 'Pitcairn, New York',
    "1793 sloop captain's sighting": 'Middle Island, Lake Erie is in Ontario',
    'Nimitz encounter': 'at sea off San Diego', 'Nimitz "Tic Tac"': 'at sea off San Diego',
    'Wolf Island carcass stunt': 'coastal island, Georgia (US)',
    'First photographs of a live giant squid in the deep sea': 'at sea off the Ogasawara Islands',
    'First video of a giant squid in its natural habitat': 'at sea off the Ogasawara Islands',
    'The Hessdalen lights': 'Trondelag: Natural Earth still uses the old county code',
    'The Flannan Isles lighthouse keepers': 'small island outside the 1:10m coastline',
    'Washington, DC flap': 'Washington DC, not Washington state',
    'Kinross incident': 'over Lake Superior (Canadian waters)',
}


def datasets():
    d = lambda f: json.load(open(os.path.join(ROOT, 'data', f), encoding='utf-8'))
    for r in d('bluebook.json'):
        if r.get('lat') is not None and r['precision'] != 'coords':
            yield 'bluebook', r['title'], r, r['precision'] in ('region', 'country'), (r['cc'], r['a1'])
    for f in ('ufo_cases_faa.json', 'ufo_cases_pursue.json'):
        for r in d(f):
            if r.get('lat') is not None and r.get('precision') not in ('coords', 'sea', 'area', 'none'):
                yield f.split('.')[0], r.get('title') or r.get('place') or r.get('region'), r, r.get('precision') != 'place', None
    for r in d('historic.json'):
        if r.get('lat') is not None:
            yield 'historic', r.get('title') or r['place'], r, bool(r.get('approx')), None
    for f, key in (('famous_geo.json', 'name'), ('places.json', 'name'), ('close_encounters.json', 'name'), ('mysteries.json', 'name'),
                   ('military.json', 'name')):
        for r in d(f):
            if r.get('lat') is not None:
                yield f.split('.')[0], r[key], r, bool(r.get('approx')), None


def main():
    A = Areas()
    stats, bad = Counter(), []
    for name, title, r, approx, given in datasets():
        cc, a1 = given or claim(r)
        if not cc:
            stats[name, 'no area named'] += 1
            continue
        ok = A.inside(float(r['lat']), float(r['lon']), cc, a1)
        if ok is None:
            stats[name, 'no boundary'] += 1
        elif ok:
            stats[name, 'ok'] += 1
        elif title in KNOWN_OK:
            stats[name, 'ok (checked by hand)'] += 1
        else:
            stats[name, 'MISMATCH'] += 1
            got = A.where(float(r['lat']), float(r['lon']))
            bad.append((name, title, r.get('place') or r.get('region') or '', f'{cc}.{a1}' if a1 else cc, f'{got[0]}.{got[1]}', r['lat'], r['lon']))
    by = defaultdict(dict)
    for (n, k), v in stats.items():
        by[n][k] = v
    for n, v in by.items():
        print(f'{n:22} {dict(sorted(v.items()))}')
    for b in bad:
        print('MISMATCH', ' | '.join(str(x) for x in b))
    if '--strict' in sys.argv and bad:
        sys.exit(1)


if __name__ == '__main__':
    main()

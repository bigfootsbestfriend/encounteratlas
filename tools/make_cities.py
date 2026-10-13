"""Writes data/cities.json for the "Was it a planet?" tool's place picker, from GeoNames cities1000 (CC BY 4.0).
US and Canadian towns from 8,000 people, big cities elsewhere. Rows: [name, state/province or country, lat, lon].
  python3 tools/make_cities.py
"""
import json, os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
G = os.path.join(ROOT, 'data', 'raw', 'geonames')
adm = {}
for line in open(os.path.join(G, 'admin1CodesASCII.txt'), encoding='utf-8'):
    k, n, _, _ = line.rstrip('\n').split('\t')
    adm[k] = n
cn = {}
for line in open(os.path.join(G, 'countryInfo.txt'), encoding='utf-8'):
    if not line.startswith('#'):
        p = line.split('\t')
        cn[p[0]] = p[4]
rows = []
for line in open(os.path.join(G, 'cities1000.txt'), encoding='utf-8'):
    p = line.split('\t')
    pop, cc = int(p[14] or 0), p[8]
    if (cc in ('US', 'CA') and pop >= 8000) or (cc in ('GB', 'AU', 'NZ', 'IE') and pop >= 40000) or pop >= 250000:
        reg = adm.get(f'{cc}.{p[10]}', '') if cc in ('US', 'CA', 'AU') else cn.get(cc, cc)
        rows.append((pop, [p[1], reg, round(float(p[4]), 3), round(float(p[5]), 3)]))
rows.sort(key=lambda r: -r[0])
json.dump([r for _, r in rows], open(os.path.join(ROOT, 'data', 'cities.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print(len(rows), 'places')

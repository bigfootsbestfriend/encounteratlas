"""National Archives UAP Records Collection (Record Group 615) -> data/ufo_rg615.json + data/ufo_cases_faa.json.

RG 615 was created under NDAA FY2024 section 1841: agencies send copies of their UAP records to NARA.
US federal records, no copyright in the US (public domain), so we copy item titles, dates, NARA's
descriptions and, for the FAA series, the text of each pilot report.

Source: the National Archives Catalog. NARA's bulk-download page only exports series-level JSON, so
item records come from the catalog's own (keyless) search endpoint, the one catalog.archives.gov uses:
  https://catalog.archives.gov/proxy/records/parentNaId/<naId>?page=N&limit=100
Raw pages are cached in data/raw/nara-rg615/. Delete them to refresh.

FAA reports come in two layouts:
  - Washington Operations Center (WOC) logs, which carry the event latitude and longitude;
  - Skywatch incident reports, which name only the reporting facility. For those we geocode the
    place NARA's description gives ("an event that was reported in the Braymer, Missouri area").
"""
import glob, json, os, re, sys, time, urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ufo_geo  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
RAW = os.path.join(ROOT, 'data', 'raw', 'nara-rg615')
RG615 = 445887258
API = 'https://catalog.archives.gov/proxy/records/parentNaId/{}?page={}&limit=100'
FAA = 493468575
LOC_FIX = {'Cockburn Town, Grand Turk Island': 'Cockburn Town, Turks and Caicos Islands'}
SHORT = {  # agency names as shown on the site
    580103959: 'National Security Agency', 493468575: 'Federal Aviation Administration', 608806625: 'Department of State',
    488808322: 'Nuclear Regulatory Commission', 665701604: 'Customs and Border Protection',
    656595571: 'Department of the Air Force', 580705010: 'FBI', 493468579: 'ODNI', 493468580: 'Office of the Secretary of Defense / AARO',
}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'EncounterAtlas/1.0 (+https://encounteratlas.com)',
                                               'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def children(na_id):
    out, page = [], 1
    while True:
        path = os.path.join(RAW, f'{na_id}-p{page}.json')
        if not os.path.exists(path):
            os.makedirs(RAW, exist_ok=True)
            print('fetching', na_id, 'page', page, file=sys.stderr)
            json.dump(get(API.format(na_id, page)), open(path, 'w'))
            time.sleep(1)
        hits = json.load(open(path))['body']['hits']['hits']
        out += [h['_source']['record'] for h in hits]
        if len(hits) < 100:
            return out
        page += 1


def text_of(rec):
    return '\n'.join(d.get('completeExtractedText') or '' for d in rec.get('digitalObjects') or [])


def pdf_of(rec):
    objs = rec.get('digitalObjects') or []
    return objs[0].get('objectUrl', '') if objs else ''


def ymd(d):
    return d.get('logicalDate', '') if d else ''


def iso(m, d, y, hh='', mm=''):
    y = int(y)
    y = y + 2000 if y < 100 else y
    return f'{y:04d}-{int(m):02d}-{int(d):02d}' + (f'T{int(hh):02d}:{int(mm):02d}' if hh != '' else '')


def parse_faa(rec):
    t = text_of(rec)
    note = rec.get('scopeAndContentNote') or ''
    flat = re.sub(r'[ \t]+', ' ', t)
    r = {'id': rec['naId'], 'title': rec['title'], 'pdf': pdf_of(rec),
         'uap': next((v['number'] for v in rec.get('variantControlNumbers', []) if v.get('note', '').startswith('This is the UAP')), '')}
    lat = lon = None
    if 'Washington Operations Center' in t:
        r['src'] = 'WOC'
        m = re.search(r'Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2}):\d{2}\s*(AM|PM)?\s*(?:\(([^)]*)\))?', flat)
        if m:
            hh = int(m.group(4)) % 12 + (12 if m.group(6) == 'PM' else 0) if m.group(6) else int(m.group(4))
            r['date'] = iso(m.group(1), m.group(2), m.group(3), hh, m.group(5))
            r['tz'] = m.group(7).split()[-1] if m.group(7) else ''
        lats = re.findall(r'Latitude:\s*(-?\d+\.\d+)', flat)
        if len(lats) >= 2:
            lat, lon = float(lats[0]), float(lats[1])
            if lat == 0 and lon == 0:
                lat = lon = None
        d = re.search(r'DESCRIPTION\s*(.*)', t, re.S)
        desc = re.sub(r'\s+', ' ', d.group(1)).strip() if d else ''
        desc = re.sub(r'\s*WOC (202-267-)?7-3333.*$', '', desc)
        r['text'] = desc
        m = re.search(r'FAA OPS:\s*([^/]+)/', desc)
        r['loc'] = m.group(1).strip().title() if m else ''
        m = re.search(r'ADVISED (?:THAT )?([A-Z][A-Z ]+? \d{1,5}|N\d+[A-Z]*),\s*(?:[A-Z]+ )?([A-Z0-9]{3,4})\b', desc)
        r['flight'] = m.group(1).title() if m else ''
        r['aircraft'] = m.group(2) if m else ''
    else:
        r['src'] = 'Skywatch'
        m = re.search(r'Date:\s*(\d{1,2}):(\d{2})\s+(\d{1,2})/(\d{1,2})/(\d{4})', flat)
        if m:
            r['date'] = iso(m.group(3), m.group(4), m.group(5), m.group(1), m.group(2))
            r['tz'] = 'UTC'
        def field(name):
            m = re.search(name + r':\s*([^\n]*)', t)
            v = m.group(1).strip() if m else ''
            return '' if re.match(r'^[A-Z][a-z]+( [A-Z][a-z]+)*:', v) else v
        r['flight'] = field('Callsign')
        r['aircraft'] = field('Aircraft')
        r['facility'] = field('Reporting Facility')
        r['optype'] = field('Operator Type')
        d = re.search(r'REMARKS\s*(.*?)(SKYWATCH INCIDENT REPORT|$)', t, re.S)
        r['text'] = re.sub(r'\s+', ' ', d.group(1)).strip() if d else ''
        r['loc'] = ''
    m = re.search(r'reported (?:in|near|over) (?:the ?)?(.+?)(?: \(([A-Z0-9]{3,4})\))? area', note)
    if m:
        r['loc'] = LOC_FIX.get(m.group(1).strip(), m.group(1).strip())
    fac = re.search(r'This report is from (?:the )?([^()]+?), ([A-Z][a-z]+(?: [A-Z][a-z]+)?) \(Z[A-Z]{2}\)', note)
    r['from'] = f'{fac.group(1)}, {fac.group(2)}'.replace(' Center,', ',') if fac else ''
    if not r.get('date') and rec.get('coverageStartDate'):
        r['date'] = ymd(rec['coverageStartDate'])
    if not r.get('date'):
        m = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', rec['title'])
        if m:
            r['date'] = iso(m.group(1), m.group(2), m.group(3))
    fl = re.findall(r'\bFL ?(\d{2,3})\b', r['text'])
    r['fl'] = int(fl[0]) * 100 if fl else None
    r['starlink'] = bool(re.search(r'starlink', r['text'], re.I))
    r['radar'] = any(not t.lower().endswith('not ') for t in
                     (r['text'][max(0, m.start() - 4):m.start()] for m in re.finditer(r'observed on (atc )?(facility )?radar', r['text'], re.I)))
    geo = ufo_geo.geocode(r['loc']) if r['loc'] else None
    if not geo and lat is None and r['from']:
        geo = ufo_geo.geocode(r['from'])
        if geo:  # only the air traffic control centre is known: its area spans several states
            geo = (geo[0], geo[1], 'facility', geo[3], geo[4])
    if lat is not None:
        r.update(lat=round(lat, 4), lon=round(lon, 4), precision='coords')
        if geo:
            r['cc'], r['region'] = geo[3], geo[4]
    elif geo:
        r.update(lat=round(geo[0], 4), lon=round(geo[1], 4), precision=geo[2], cc=geo[3], region=geo[4])
    else:
        r.update(lat=None, lon=None, precision='none')
    if not r.get('region') and r['loc']:
        reg = ufo_geo._region(r['loc'].split(',')[-1])
        if reg:
            r['cc'], r['region'] = reg[0], reg[2]
    return r


def main():
    series = children(RG615)
    out = []
    faa = []
    for s in sorted(series, key=lambda s: -(s.get('itemCount') or 0)):
        items = children(s['naId'])
        if s['naId'] == FAA:
            faa = [parse_faa(i) for i in items]
        out.append({
            'naId': s['naId'], 'title': s['title'], 'agency': SHORT.get(s['naId'], s['title']),
            'start': ymd(s.get('inclusiveStartDate')), 'end': ymd(s.get('inclusiveEndDate')),
            'count': len(items),
            'items': sorted(({'naId': i['naId'], 'title': i['title'].strip(), 'pdf': pdf_of(i),
                              'kind': (i.get('digitalObjects') or [{}])[0].get('objectType', ''),
                              'note': (i.get('scopeAndContentNote') or '').strip()}
                             for i in items), key=lambda i: i['title'].lower()) if s['naId'] != FAA else [],
        })
    json.dump({'recordGroup': RG615, 'series': out}, open(os.path.join(ROOT, 'data', 'ufo_rg615.json'), 'w'),
              indent=0, ensure_ascii=False)
    faa.sort(key=lambda r: r.get('date') or '')
    json.dump(faa, open(os.path.join(ROOT, 'data', 'ufo_cases_faa.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    print(len(out), 'series;', len(faa), 'FAA reports', dict(Counter(r['precision'] for r in faa)),
          dict(Counter(r['src'] for r in faa)), file=sys.stderr)


if __name__ == '__main__':
    main()

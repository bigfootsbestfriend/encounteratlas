"""Project Blue Book (USAF, 1947-1969) case list -> data/bluebook.json.

Source: National Archives "Sanitized Version of Project Blue Book Case Files" (naId 597821),
bulk JSON export. US federal records, no copyright in the US.
Each case title reads "Place, State-or-Country, Month Year". Places are matched to GeoNames
(cities with 1,000+ people, CC BY 4.0). Unmatched places fall back to the state or country
centre and are marked approximate.
"""
import json, os, re, sys, unicodedata, urllib.request
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
RAW = os.path.join(ROOT, 'data', 'raw')
SRC_URL = 'https://catalog.archives.gov/medialz/bulk-downloads/uaps/JSON/catalog-export-597821.json'
SRC = os.path.join(RAW, 'bluebook-597821.json')
GEO = os.path.join(RAW, 'geonames')
GEO_URL = 'https://download.geonames.org/export/dump/'
OUT = os.path.join(ROOT, 'data', 'bluebook.json')

MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                       'september', 'october', 'november', 'december'], 1)}
# Spellings seen in the titles that GeoNames won't know.
REGION_ALIASES = {
    's carolina': 'south carolina', 'n carolina': 'north carolina', 'so carolina': 'south carolina',
    'no carolina': 'north carolina', 'n dakota': 'north dakota', 's dakota': 'south dakota',
    'w virginia': 'west virginia', 'wva': 'west virginia', 'washington dc': 'district of columbia',
    'dc': 'district of columbia', 'd c': 'district of columbia', 'mass': 'massachusetts', 'penn': 'pennsylvania',
    'calif': 'california', 'conn': 'connecticut', 'n mexico': 'new mexico', 'n jersey': 'new jersey',
    'n york': 'new york', 'n hampshire': 'new hampshire', 'england': 'united kingdom', 'scotland': 'united kingdom',
    'wales': 'united kingdom', 'great britain': 'united kingdom', 'uk': 'united kingdom', 'okinawa': 'japan',
    'korea': 'south korea', 'formosa': 'taiwan', 'west germany': 'germany', 'w germany': 'germany',
    'newfoundland': 'newfoundland and labrador', 'labrador': 'newfoundland and labrador',
    'iran': 'iran', 'persia': 'iran', 'holland': 'netherlands', 'ussr': 'russia', 'russia': 'russia',
    'pacific ocean': 'ocean', 'atlantic ocean': 'ocean', 'atlantic': 'ocean', 'pacific': 'ocean',
    'gulf of mexico': 'ocean', 'at sea': 'ocean', 'canal zone': 'panama',
}
# Old-style and postal state abbreviations as typed on the case folders (dots removed, lower case).
US_ABBR = {
    'ala': 'alabama', 'ariz': 'arizona', 'ark': 'arkansas', 'cal': 'california', 'calif': 'california',
    'colo': 'colorado', 'conn': 'connecticut', 'del': 'delaware', 'fla': 'florida', 'ill': 'illinois',
    'ind': 'indiana', 'kan': 'kansas', 'kans': 'kansas', 'ky': 'kentucky', 'md': 'maryland', 'mass': 'massachusetts',
    'mich': 'michigan', 'minn': 'minnesota', 'miss': 'mississippi', 'mo': 'missouri', 'mont': 'montana',
    'neb': 'nebraska', 'nebr': 'nebraska', 'nev': 'nevada', 'nh': 'new hampshire', 'nj': 'new jersey',
    'nm': 'new mexico', 'nmex': 'new mexico', 'n mex': 'new mexico', 'ny': 'new york', 'nc': 'north carolina',
    'nd': 'north dakota', 'ndak': 'north dakota', 'okla': 'oklahoma', 'ore': 'oregon', 'oreg': 'oregon',
    'pa': 'pennsylvania', 'penna': 'pennsylvania', 'ri': 'rhode island', 'sc': 'south carolina',
    'sd': 'south dakota', 'sdak': 'south dakota', 'tenn': 'tennessee', 'tex': 'texas', 'vt': 'vermont',
    'va': 'virginia', 'wash': 'washington', 'wva': 'west virginia', 'w va': 'west virginia', 'wis': 'wisconsin',
    'wisc': 'wisconsin', 'wyo': 'wyoming', 'ga': 'georgia', 'la': 'louisiana', 'me': 'maine', 'ia': 'iowa',
    'hawaiian islands': 'hawaii', 'hawaiian is': 'hawaii', 'ut': 'utah', 'id': 'idaho', 'az': 'arizona',
    'ca': 'california', 'co': 'colorado', 'tx': 'texas', 'fl': 'florida', 'oh': 'ohio', 'mi': 'michigan',
    'il': 'illinois', 'in': 'indiana', 'wi': 'wisconsin', 'mn': 'minnesota', 'ok': 'oklahoma', 'ks': 'kansas',
    'ne': 'nebraska', 'nv': 'nevada', 'or': 'oregon', 'wa': 'washington', 'tn': 'tennessee', 'ky ': 'kentucky',
    'al': 'alabama', 'ms': 'mississippi', 'ar': 'arkansas', 'wv': 'west virginia', 'md ': 'maryland',
    'de': 'delaware', 'ct': 'connecticut', 'ma': 'massachusetts', 'wy': 'wyoming', 'mt': 'montana', 'ak': 'alaska',
}
COORD_RE = re.compile(r'(\d{1,2})\.?(\d{2})\s*([NS])\s+(\d{1,3})\.?(\d{2})\s*([EW])')
PLACE_NOISE = re.compile(r'\b(n|s|e|w|ne|nw|se|sw|north|south|east|west|near|nr|vic|vicinity|of|area|airport|'
                         r'afb|air force base|nas|naval air station|aaf|afs|air station|base|field|mts?|county|co)\b')


def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z ]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def fetch(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print('downloading', url, file=sys.stderr)
        urllib.request.urlretrieve(url, path)


def load_cases():
    fetch(SRC_URL, SRC)
    text = open(SRC, encoding='utf-8').read()
    # NARA's export is missing the commas between records.
    text = re.sub(r'\}\s*\n  \{', '},\n  {', text)
    return json.loads(text)


def load_geonames():
    for f in ('admin1CodesASCII.txt', 'countryInfo.txt'):
        fetch(GEO_URL + f, os.path.join(GEO, f))
    cities_txt = os.path.join(GEO, 'cities1000.txt')
    if not os.path.exists(cities_txt):
        import zipfile
        z = os.path.join(GEO, 'cities1000.zip')
        fetch(GEO_URL + 'cities1000.zip', z)
        zipfile.ZipFile(z).extractall(GEO)
    countries, country_names = {}, {}
    for line in open(os.path.join(GEO, 'countryInfo.txt'), encoding='utf-8'):
        if line.startswith('#'):
            continue
        p = line.rstrip('\n').split('\t')
        countries[p[0]] = p[4]
        country_names[norm(p[4])] = p[0]
    country_names.update({'usa': 'US', 'united states': 'US', 'south korea': 'KR', 'russia': 'RU',
                          'united kingdom': 'GB', 'iran': 'IR', 'taiwan': 'TW', 'netherlands': 'NL'})
    admin1 = {}  # norm(name) -> (cc, code, name); US states + Canadian provinces + Australian states
    for line in open(os.path.join(GEO, 'admin1CodesASCII.txt'), encoding='utf-8'):
        key, name, ascii_name, _ = line.rstrip('\n').split('\t')
        cc, code = key.split('.')
        if cc in ('US', 'CA', 'AU'):
            admin1[norm(ascii_name)] = (cc, code, ascii_name)
    us_abbr = {}
    for line in open(os.path.join(GEO, 'admin1CodesASCII.txt'), encoding='utf-8'):
        key = line.split('\t')[0]
        if key.startswith('US.'):
            us_abbr[key[3:].lower()] = norm(line.split('\t')[2])
    by_place = defaultdict(list)  # (cc, admin1 or '', norm(name)) -> [(pop, lat, lon, name)]
    sums = defaultdict(lambda: [0.0, 0.0, 0])
    for line in open(cities_txt, encoding='utf-8'):
        p = line.rstrip('\n').split('\t')
        name, asciiname, alts = p[1], p[2], p[3]
        lat, lon, cc, a1, pop = float(p[4]), float(p[5]), p[8], p[10], int(p[14] or 0)
        rec = (pop, lat, lon, name)
        names = {norm(name), norm(asciiname)}
        if cc in ('US', 'CA', 'AU'):
            names |= {norm(a) for a in alts.split(',') if a and len(a) < 40}
        for n in names:
            if n:
                by_place[(cc, a1, n)].append(rec)
                by_place[(cc, '', n)].append(rec)
        for k in ((cc, a1), (cc, '')):
            s = sums[k]
            s[0] += lat; s[1] += lon; s[2] += 1
    # Full US + Canada files: small towns (cities1000 skips places under 1,000 people) and air bases,
    # which many case folders are named after. Used only when nothing bigger matches.
    import zipfile
    for cc in ('US', 'CA'):
        txt = os.path.join(GEO, cc + '.txt')
        if not os.path.exists(txt):
            z = os.path.join(GEO, cc + '.zip')
            fetch(GEO_URL + cc + '.zip', z)
            zipfile.ZipFile(z).extract(cc + '.txt', GEO)
        for line in open(txt, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            fclass, fcode = p[6], p[7]
            if not (fclass == 'P' or fcode in ('MILB', 'AIRB', 'AIRF', 'AIRP', 'INSM', 'ISL', 'LK', 'MT', 'PRK')):
                continue
            rec = (-1, float(p[4]), float(p[5]), p[1])  # pop -1: loses to any cities1000 match
            for n in {norm(p[1]), norm(p[2])}:
                if n and (cc, p[10], n) not in by_place:
                    by_place[(cc, p[10], n + '#full')].append(rec)
    centres = {k: (round(v[0] / v[2], 3), round(v[1] / v[2], 3)) for k, v in sums.items()}
    return countries, country_names, admin1, us_abbr, by_place, centres


def region_key(region):
    r = norm(region.replace('.', ''))
    r = re.sub(r'\b(area|vicinity|vic|and|state|territory)\b', ' ', r)
    return re.sub(r'\s+', ' ', r).strip()


def resolve_region(r, admin1, country_names, us_abbr):
    r = REGION_ALIASES.get(r, r)
    r = US_ABBR.get(r, r)
    r = us_abbr.get(r, r)
    r = REGION_ALIASES.get(r, r)
    if r in admin1:
        return 'a1', admin1[r]
    if r in country_names:
        return 'cc', country_names[r]
    if r == 'ocean':
        return 'ocean', None
    return None, None


def place_candidates(place):
    raw = norm(place)
    out = [raw]
    cleaned = re.sub(r'\s+', ' ', PLACE_NOISE.sub(' ', raw)).strip()
    if cleaned and cleaned != raw:
        out.append(cleaned)
    afb = re.sub(r'\b(afb|aafb|afs)\b.*$', 'air force base', raw).strip()
    if afb != raw:
        out.insert(0, afb)
    if cleaned.startswith(('st ', 'ft ', 'mt ')):
        out.append({'st': 'saint', 'ft': 'fort', 'mt': 'mount'}[cleaned[:2]] + cleaned[2:])
    return out


def main():
    cases = load_cases()
    countries, country_names, admin1, us_abbr, by_place, centres = load_geonames()
    out, stats = [], defaultdict(int)
    title_re = re.compile(r'^(.*?),?\s*([A-Za-z]+)\.?\s+(\d{4})\s*$')
    for c in cases:
        title = c.get('title', '').strip()
        clean = re.sub(r'\s*-\s*Incident Number:.*$', '', title)
        m = title_re.match(clean)
        year = month = None
        rest = clean
        if m and norm(m.group(2)) in MONTHS:
            rest, month, year = m.group(1), MONTHS[norm(m.group(2))], int(m.group(3))
        else:
            rest = re.sub(r',?\s*(\[?illegible\]?|\[?blank\]?|summer|winter|spring|fall|\d{4}|\s)+$', '', clean, flags=re.I)
            if c.get('coverageStartDate'):
                year = c['coverageStartDate'].get('year')
                month = c['coverageStartDate'].get('month')
        rest = re.sub(r'\s*&\s*vicinity', '', rest, flags=re.I)
        lat = lon = None
        cc = a1 = None
        precision = 'none'
        place, region_name = rest, ''
        cm = COORD_RE.search(rest)
        if cm:
            la = int(cm.group(1)) + int(cm.group(2)) / 60
            lo = int(cm.group(4)) + int(cm.group(5)) / 60
            lat = round(-la if cm.group(3) == 'S' else la, 3)
            lon = round(-lo if cm.group(6) == 'W' else lo, 3)
            precision = 'coords'
            region_name = 'At sea' if re.search(r'pacific|atlantic|ocean|sea|gulf', rest, re.I) else ''
            place = rest
        else:
            parts = [p.strip() for p in rest.split(',') if p.strip()]
            kind = info = None
            if len(parts) >= 2:
                place = ', '.join(parts[:-1])
                kind, info = resolve_region(region_key(parts[-1]), admin1, country_names, us_abbr)
                region_name = parts[-1]
            if kind is None:
                # No comma ("BILOXI MISS", "CARIBOU MAINE"): try the last one or two words as the region.
                words = rest.replace(',', ' ').split()
                for k in (2, 1):
                    if len(words) > k:
                        kd, inf = resolve_region(region_key(' '.join(words[-k:])), admin1, country_names, us_abbr)
                        if kd:
                            kind, info, place, region_name = kd, inf, ' '.join(words[:-k]), ' '.join(words[-k:])
                            break
                if kind is None and len(parts) == 1:
                    kd, inf = resolve_region(region_key(parts[0]), admin1, country_names, us_abbr)
                    if kd:
                        kind, info, place, region_name = kd, inf, '', parts[0]
            if kind == 'a1':
                cc, a1, region_name = info
            elif kind == 'cc':
                cc = info
                region_name = countries.get(cc, region_name)
            elif kind == 'ocean':
                region_name = 'At sea'
            if region_key(place) in ('washington d c', 'washington dc', 'washington'):
                if region_key(region_name) in ('d c', 'dc', 'district of columbia'):
                    cc, a1, region_name = admin1['district of columbia']
            if cc and place and '[blank]' not in place.lower() and 'illegible' not in place.lower():
                for cand in place_candidates(place) + [c + '#full' for c in place_candidates(place)]:
                    hits = by_place.get((cc, a1 or '', cand))
                    if hits:
                        pop, lat, lon, _ = max(hits)
                        precision = 'place'
                        break
            if lat is None and cc:
                ctr = centres.get((cc, a1 or ''))
                if ctr:
                    lat, lon = ctr
                    precision = 'region' if a1 else 'country'
        stats[precision] += 1
        img = (c.get('digitalObjects') or [{}])[0].get('objectUrl')
        out.append({
            'id': c['naId'], 'title': title, 'place': (place.title() if place.isupper() else place).strip(),
            'region': region_name, 'cc': cc, 'a1': a1, 'year': year, 'month': month,
            'lat': lat, 'lon': lon, 'precision': precision,
            'pages': len(c.get('digitalObjects') or []), 'img': img,
        })
    out.sort(key=lambda x: (x['year'] or 0, x['month'] or 0, x['title']))
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(len(out), 'cases', dict(stats), file=sys.stderr)


if __name__ == '__main__':
    main()

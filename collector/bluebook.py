"""Project Blue Book (USAF, 1947-1969) case list -> data/bluebook.json.

Source: National Archives "Sanitized Version of Project Blue Book Case Files" (naId 597821),
bulk JSON export. US federal records, no copyright in the US.
Each case title reads "Place, State-or-Country, Month Year". Places are matched to GeoNames
(cities with 1,000+ people, CC BY 4.0). Unmatched places fall back to the state or country
centre and are marked approximate.
"""
import json, os, re, sys, unicodedata, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
    # Canadian provinces as typed on the folders
    'bc': 'british columbia', 'b c': 'british columbia', 'brit columbia': 'british columbia', 'alta': 'alberta',
    'sask': 'saskatchewan', 'man': 'manitoba', 'ont': 'ontario', 'que': 'quebec', 'pq': 'quebec', 'p q': 'quebec',
    'n s': 'nova scotia', 'ns': 'nova scotia', 'n b': 'new brunswick', 'nb': 'new brunswick', 'pei': 'prince edward island',
    'p e i': 'prince edward island', 'nwt': 'northwest territories', 'n w t': 'northwest territories',
    'northwest': 'northwest territories', 'nfld': 'newfoundland and labrador', 'labador': 'newfoundland and labrador',
    'yukon': 'yukon', 'new foundland': 'newfoundland and labrador', 'babrador': 'newfoundland and labrador',
    'susk': 'saskatchewan', 'soviet union': 'russia', 'siberia': 'russia',
}
# Old names of bases and towns (after place_candidates cleaning) -> the GeoNames name, or fixed (lat, lon) for
# places GeoNames' populated-place files don't carry.
PLACE_ALIASES = {
    'goose': 'happy valley goose bay', 'goose bay': 'happy valley goose bay', 'goose ab': 'happy valley goose bay',
    'harmon': 'stephenville', 'ernest harmon': 'stephenville', 'pepperrell': 'st john s', 'pepperell': 'st john s',
    'cornerbrooke': 'corner brook', 'winsor': 'grand falls windsor', 'gander ab': 'gander',
    'thule': (76.531, -68.703), 'thule ab': (76.531, -68.703), 'narsarssuak': (61.161, -45.426), 'narsarssuak ab': (61.161, -45.426),
    'sondrestrom': (67.009, -50.689), 'sondrestrom ab': (67.009, -50.689), 'sondre stromfjord': (67.009, -50.689),
    'prince christian': (60.049, -43.150), 'simiutak': (60.683, -46.583),
    'narsarsuaq': (61.161, -45.426), 'kangerlussuaq': (67.009, -50.689), 'north star bay': (76.531, -68.703),
    'indian house lake': (56.25, -64.70), 'saint john': (45.273, -66.063),
    'gimili rcaf station': 'gimli', 'gimili': 'gimli', 'gimli rcaf station': 'gimli', 'port arthur': (48.382, -89.246),
    'port harrison': (58.453, -78.102), 'caledor east': 'caledon east', 'curling east': 'corner brook', 'curling': 'corner brook',
    'riga': (56.946, 24.106), 'winnepeg': 'winnipeg',
    'stalingrad': 'volgograd', 'leningrad': 'saint petersburg', 'sverdlovsk': 'yekaterinburg', 'gorky': 'nizhniy novgorod',
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
SOVIET = {'RU', 'UA', 'BY', 'LV', 'LT', 'EE', 'GE', 'AM', 'AZ', 'KZ', 'UZ', 'TM', 'KG', 'TJ', 'MD'}
_DEG = r"(?:\s*(?:degrees|deg)\s*|\.|\s+)?"
COORD_RE = re.compile(r"(\d{1,2})" + _DEG + r"(\d{2})'?\s*([NS])\s*[-\s]\s*(\d{1,3})" + _DEG + r"(\d{2})'?\s*([EW])", re.I)
PLACE_NOISE = re.compile(r'\b(n|s|e|w|ne|nw|se|sw|north|south|east|west|near|nr|vic|vicinity|of|area|airport|'
                         r'afb|air force base|nas|naval air station|aaf|afs|air station|base|field|mts?|county|co|canada|in)\b')


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
    admin1_cc = {}  # (cc, norm(name)) -> (cc, code, name), every country
    admin1 = {}  # norm(name) -> (cc, code, name); US states + Canadian provinces + Australian states
    for line in open(os.path.join(GEO, 'admin1CodesASCII.txt'), encoding='utf-8'):
        key, name, ascii_name, _ = line.rstrip('\n').split('\t')
        cc, code = key.split('.')
        if cc in ('US', 'CA', 'AU'):
            admin1[norm(ascii_name)] = (cc, code, ascii_name)
        admin1_cc[(cc, norm(ascii_name))] = (cc, code, ascii_name)
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
        names |= {norm(a) for a in alts.split(',') if a and len(a) < 40 and a.isascii()}
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
                if n and (cc, '', n) not in by_place:
                    by_place[(cc, '', n + '#full')].append(rec)
    centres = {k: (round(v[0] / v[2], 3), round(v[1] / v[2], 3)) for k, v in sums.items()}
    return countries, country_names, admin1, admin1_cc, us_abbr, by_place, centres


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
    for c in list(out):
        if c in PLACE_ALIASES:
            out.insert(0, PLACE_ALIASES[c])
    if ',' in place:  # "Pepperrell AFB, Newfoundland, Thule": try each part
        for part in place.split(','):
            out += [c for c in place_candidates(part) if c not in out]
    return out


def main():
    cases = load_cases()
    countries, country_names, admin1, admin1_cc, us_abbr, by_place, centres = load_geonames()
    from geo import Areas
    areas = Areas()
    fixes = defaultdict(int)
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
                kind, info = resolve_region(region_key(re.sub(r'\(.*?\)', '', parts[-1])), admin1, country_names, us_abbr)
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
            if kind == 'cc':
                # "Edmonton, Alberta, Canada" / "North Bay Ontario, Canada" / "Kingsville, Canada (Ontario)":
                # the province or state sits before the country (or in brackets after it).
                paren = re.search(r'\(([^)]+)\)', parts[-1]) if parts else None
                trials = [(paren.group(1), place)] if paren else []
                trials.append((place, ''))  # "Ontario, Canada": the place is the province
                pp = [x.strip() for x in place.split(',') if x.strip()]
                if len(pp) >= 2:
                    trials.append((pp[-1], ', '.join(pp[:-1])))
                ws = place.split()
                trials += [(' '.join(ws[-k:]), ' '.join(ws[:-k])) for k in (3, 2, 1) if len(ws) > k]
                for reg, rest_place in trials:
                    rk = region_key(reg)
                    rk = REGION_ALIASES.get(rk, rk)
                    hit = admin1_cc.get((info, rk))
                    if hit:
                        kind, info, place, region_name = 'a1', hit, rest_place, reg
                        break
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
                # First candidate whose point lies inside the named province/state/country wins.
                ussr = bool(re.search(r'u\.?s\.?s\.?r|soviet', rest, re.I))
                seen_pts = []
                for cand in place_candidates(place) + [c + '#full' for c in place_candidates(place) if isinstance(c, str)]:
                    if isinstance(cand, tuple):
                        pt = cand
                    else:
                        hits = by_place.get((cc, a1 or '', cand))
                        pt = max(hits)[1:3] if hits else None
                    if not pt:
                        continue
                    ok = areas.inside(pt[0], pt[1], cc, a1)
                    if ok is False and ussr and areas.where(*pt)[0] in SOVIET:
                        ok, cc, a1 = True, areas.where(*pt)[0], None  # Riga, USSR -> Latvia
                    if ok is False:
                        seen_pts.append(pt)
                        continue
                    lat, lon = pt
                    precision = 'place'
                    break
                if lat is None and seen_pts:
                    fixes['outside_area_demoted'] += 1
                    print('  only matches outside its area, demoted:', title, seen_pts[0], file=sys.stderr)
            if lat is None and cc:
                ctr = areas.centre(cc, a1) or centres.get((cc, a1 or ''))
                if ctr:
                    lat, lon = ctr
                    precision = 'region' if a1 else 'country'
        stats[precision] += 1
        img = (c.get('digitalObjects') or [{}])[0].get('objectUrl')
        out.append({
            'id': c['naId'], 'title': title, 'place': (place.title() if place.isupper() else place).strip(),
            'region': region_name, 'country': countries.get(cc, '') if cc else '', 'cc': cc, 'a1': a1, 'year': year, 'month': month,
            'lat': lat, 'lon': lon, 'precision': precision,
            'pages': len(c.get('digitalObjects') or []), 'img': img,
        })
    out.sort(key=lambda x: (x['year'] or 0, x['month'] or 0, x['title']))
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(len(out), 'cases', dict(stats), dict(fixes), file=sys.stderr)


if __name__ == '__main__':
    main()

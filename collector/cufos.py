"""Canadian UFO Survey case list (1989 to 2025), compiled each year by Ufology Research (Winnipeg).

Source: the survey's "1989 to 2025 Data" PDF (an Excel export), saved in data/raw/cufos/1989-2025.pdf.
Mike approved the survey as a source (2026-10-12): credit it, but don't link to it.
Mike's rule still applies inside it: rows the survey got from MUFON, NUFORC or Enigma Labs are left out entirely,
and the remaining notes are scrubbed of those names. The survey's own source codes are never shown.

Each row is geocoded to its town with GeoNames (CA.txt). Places that can't be found keep only their province and are
marked approximate. Writes data/ufo_cases_canada.json.
  python3 collector/cufos.py
"""
import difflib, json, os, re, subprocess, sys, unicodedata
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import Areas  # noqa: E402

PDF = os.path.join(ROOT, 'data', 'raw', 'cufos', '1989-2025.pdf')
GEO = os.path.join(ROOT, 'data', 'raw', 'geonames', 'CA.txt')

# Survey province codes -> (GeoNames admin1 code, name)
PROV = {'AB': ('01', 'Alberta'), 'BC': ('02', 'British Columbia'), 'MB': ('03', 'Manitoba'), 'NB': ('04', 'New Brunswick'),
        'NL': ('05', 'Newfoundland and Labrador'), 'NF': ('05', 'Newfoundland and Labrador'), 'LB': ('05', 'Newfoundland and Labrador'),
        'NS': ('07', 'Nova Scotia'), 'ON': ('08', 'Ontario'), 'PE': ('09', 'Prince Edward Island'), 'PEI': ('09', 'Prince Edward Island'),
        'PI': ('09', 'Prince Edward Island'), 'PQ': ('10', 'Quebec'), 'QC': ('10', 'Quebec'), 'SK': ('11', 'Saskatchewan'), 'YT': ('12', 'Yukon'), 'YK': ('12', 'Yukon'),
        'NT': ('13', 'Northwest Territories'), 'NWT': ('13', 'Northwest Territories'), 'NU': ('14', 'Nunavut')}
BLOCKED_SRC = re.compile(r'mufon|nuforc|enigma', re.I)
BLOCKED_TXT = re.compile(r'\b(mufon|nuforc|enigma\s*labs?|bfro)\b', re.I)
MISPARSED = re.compile(r'(?:^|\s)\d{1,5}\s+\S+\s+\d|\b(?:Internet|UFOROM|SPPRC|Vike)\b|UFOS in Canada|^[a-z]{1,3}\s+\d')
# How each sighting was seen (the survey's TYPE code)
TYPES = {'nl': 'Night light', 'nd': 'Night disc', 'dd': 'Daytime disc', 'c1': 'Close encounter (1st kind)',
         'c2': 'Close encounter (2nd kind, physical traces)', 'c3': 'Close encounter (3rd kind, beings seen)',
         'c4': 'Close encounter (4th kind, abduction claim)', 'rd': 'Radar', 'ph': 'Photo or video', 'ux': 'Unusual event'}
EVAL = {'u': 'unexplained', 'p': 'possible explanation', 'i': 'not enough information', 'e': 'explained'}
COLOURS = {'white', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'multi', 'silver', 'gray', 'grey', 'black', 'gold',
           'pink', 'amber', 'brown', 'violet', 'clear', 'bronze', 'metallic', 'various', 'blue-white', 'red-orange', 'multiple'}
SHAPES = {'ps': 'point of light', 'ball': 'ball', 'sphere': 'sphere', 'disc': 'disc', 'disk': 'disc', 'oval': 'oval',
          'triangle': 'triangle', 'fireball': 'fireball', 'cigar': 'cigar', 'cylinder': 'cylinder', 'boomerang': 'boomerang',
          'diamond': 'diamond', 'irregular': 'irregular', 'round': 'round', 'rectangle': 'rectangle', 'square': 'square',
          'arrow': 'arrow', 'cone': 'cone', 'star': 'star', 'chevron': 'chevron', 'egg': 'egg', 'cross': 'cross', 'ring': 'ring',
          'light': 'light', 'lights': 'lights', 'saucer': 'saucer', 'cube': 'cube', 'tictac': 'Tic Tac', 'tic-tac': 'Tic Tac'}
ABBR = [(r'\bobjs\.?(?=\s|$|[,;:])', 'objects'), (r'\bobj\.?(?=\s|$|[,;:])', 'object'), (r'\btri\.', 'triangle'), (r'\bw/', 'with '), (r'\ba/c\b', 'aircraft'), (r'\bnr\.?\b', 'near'),
        (r'\bmtns?\.?\b', 'mountains'), (r'\bstat\.', 'stationary'), (r'\bhoriz\.', 'horizon'), (r'\bmins?\.', 'minutes'),
        (r'\bcntre\b', 'centre'), (r'\boffcr\b', 'officer'), (r'\breprtd\b', 'reported'), (r'\bapprox\.', 'approximately')]
# Old or misspelled names in the survey -> GeoNames name
ALIASES = {'east vancouver': 'vancouver', 'north surrey': 'surrey', 'rosemont': 'montreal', 'ahunstic': 'montreal',
           'ahuntsic': 'montreal', 'three rivers': 'trois rivieres', 'bagotville': 'saguenay', 'resolute bay': 'resolute',
           'cap de la madeline': 'cap de la madeleine', 'birds hill': 'birds hill', 'bird s hill': 'birds hill',
           'bird s hill park': 'birds hill', 'gibson s': 'gibsons', 'sherbrook': 'sherbrooke', 'tsawassen': 'tsawwassen',
           'shelbourne': 'shelburne', 'port colbourne': 'port colborne', 'drummonville': 'drummondville', 'pentiction': 'penticton',
           'st catherines': 'saint catharines', 'saint catherines': 'saint catharines', 'wabamum': 'wabamun', 'thetford': 'thetford mines',
           'saint saveur': 'saint sauveur', 'neufchatel': 'quebec'}
TAIL = re.compile(r'\s(\d{1,2})(?:\s+(\d{1,2}))?\s+(?:(\S+)\s+)?([iupeIUPE])(?:\s+(.*))?$')


def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\bst[e]?[\.\-\s]+', lambda m: 'saint ' if m.group(0).strip(' .-') == 'st' else 'sainte ', s)
    s = re.sub(r'\bmt\.?\s', 'mount ', s)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s)).strip()


def nice_place(s):
    s = re.sub(r'\s+', ' ', s).strip(' ,')
    return s.title() if s.isupper() or s.islower() else s


def nice_note(s):
    s = (s or '').strip()
    if not s:
        return ''
    if s.isupper():
        s = s.lower()
    for a, b in ABBR:
        s = re.sub(a, b, s, flags=re.I)
    s = re.sub(r'^N\d\d/\d+:\s*', '', s)  # NRC file number
    s = re.sub(r'\s*;?\s*see N\d\d/\d+', '', s)
    s = re.sub(r'\bNRC\s*N?\d+(/\d+)?;?\s*', '', s).strip(' ;')
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:1].upper() + s[1:] if s else ''


def gazetteer():
    """norm(name) -> {admin1: (lat, lon, pop)} for populated places and a few landforms people report from."""
    out = defaultdict(dict)
    keep = {'P', 'L', 'T', 'H', 'S', 'A'}
    for line in open(GEO, encoding='utf-8'):
        p = line.split('\t')
        if p[6] not in keep or (p[6] == 'A' and p[7] != 'ADM3'):  # ADM3 = old boroughs (Scarborough, North York)
            continue
        pop = int(p[14] or 0) + (1 if p[6] == 'P' else 0)
        names = {p[1], p[2]} | ({a for a in p[3].split(',') if a} if p[6] == 'P' and pop > 500 else set())
        for n in names:
            k = norm(n)
            if not k:
                continue
            cur = out[k].get(p[10])
            if cur is None or pop > cur[2]:
                out[k][p[10]] = (float(p[4]), float(p[5]), pop)
    return out


def parse_rows(text):
    for line in text.splitlines():
        if not re.match(r'\s*(19|20)\d\d\s', line):
            continue
        t = line.split()
        pi = next((i for i, x in enumerate(t) if i >= 1 and x.upper() in PROV), None)
        if pi is None:
            continue
        head, rest = t[:pi], line.split(None, pi + 1)
        year = int(head[0])
        nums, place = [], []
        for x in head[1:]:
            if not place and re.fullmatch(r'\d{1,4}', x) and len(nums) < 3:
                nums.append(int(x))
            else:
                place.append(x)
        m = d = tm = None
        if len(nums) == 3:
            m, d, tm = nums
        elif len(nums) == 2:
            m, x = nums
            d, tm = (x, None) if x <= 31 and m <= 12 else (None, x)
        elif len(nums) == 1:
            m = nums[0]
        if m and not 1 <= m <= 12:
            m, d = None, None
        if d and not 1 <= d <= 31:
            d = None
        after = rest[pi + 1] if len(rest) > pi + 1 else ''
        tl = TAIL.search(' ' + after)
        mid = (' ' + after)[:tl.start()] if tl else after
        src = (tl.group(3) or '') if tl else ''
        ev = tl.group(4).lower() if tl else ''
        note = (tl.group(5) or '') if tl else ''
        strange = int(tl.group(1)) if tl and tl.group(2) else None
        if tl and tl.group(3) and re.fullmatch(r'\d{1,2}', tl.group(3)):  # "str rel" both present and source missing
            src = ''
        mt = mid.split()
        typ = mt[0].lower() if mt and mt[0].lower() in TYPES else ''
        mt = mt[1:] if typ else mt
        dur = col = wit = shape = None
        for x in mt:
            xl = x.lower()
            if re.fullmatch(r'\d+', x):
                if dur is None and col is None and wit is None and int(x) > 0 and len(mt) > 1 and (mt.index(x) == 0):
                    dur = int(x)
                elif wit is None:
                    wit = int(x)
            elif xl in COLOURS and col is None:
                col = 'grey' if xl == 'gray' else ('multicoloured' if xl in ('multi', 'multiple', 'various') else xl)
            elif xl in SHAPES and shape is None:
                shape = SHAPES[xl]
        yield {'year': year, 'm': m, 'd': d, 'tm': tm, 'place': nice_place(' '.join(place)), 'prov': t[pi].upper(), 'type': typ,
               'dur': dur, 'colour': col, 'wit': wit, 'shape': shape, 'str': strange, 'eval': ev, 'src': src, 'note': note}


def main():
    text = subprocess.run(['pdftotext', '-layout', PDF, '-'], capture_output=True, text=True, check=True).stdout
    gaz, A = gazetteer(), Areas()
    by_prov = defaultdict(list)
    for n, v in gaz.items():
        for a in v:
            if v[a][2] > 0:
                by_prov[a].append(n)
    out, stats, missed = [], Counter(), Counter()
    seen = set()
    for r in parse_rows(text):
        if BLOCKED_SRC.search(r['src']) or BLOCKED_TXT.search(r['note']) or BLOCKED_TXT.search(r['place']):
            stats['left out (blocked source)'] += 1
            continue
        if MISPARSED.search(r['place']):  # columns ran together: the source code and ratings landed in the place name
            stats['left out (row not parsed cleanly)'] += 1
            print('  misparsed, dropped:', r['place'][:70], file=sys.stderr)
            continue
        a1, pname = PROV[r['prov']]
        note = nice_note(r['note'])
        key = (r['year'], r['m'], r['d'], r['tm'], r['place'].lower(), r['prov'], note.lower())
        if key in seen:  # the survey sometimes lists one report twice (two investigators)
            stats['duplicate'] += 1
            continue
        seen.add(key)
        lat = lon = None
        prec = 'region'
        k = norm(r['place'])
        k = re.sub(r'\b(area|region|district|vicinity|near|outside|north|south|east|west|of|n|s|e|w|ne|nw|se|sw)$', '', k).strip()
        k = ALIASES.get(k, k)
        hit = gaz.get(k, {}).get(a1) or (gaz.get(k, {}).get('14') if a1 == '13' else None)  # NWT split in 1999: Nunavut
        if not hit and ' ' in k:  # "Lake Kashagawigamog" vs "Kashagawigamog Lake", or a trailing word
            hit = gaz.get(' '.join(k.split()[1:] + k.split()[:1]), {}).get(a1) or gaz.get(k.rsplit(' ', 1)[0], {}).get(a1)
        if not hit and len(k) >= 7:  # typos: closest name in the same province
            close = difflib.get_close_matches(k, by_prov[a1], n=1, cutoff=0.9)
            hit = gaz[close[0]][a1] if close else None
        if hit and (A.inside(hit[0], hit[1], 'CA', a1) or (a1 == '13' and A.inside(hit[0], hit[1], 'CA', '14'))):
            lat, lon, prec = hit[0], hit[1], 'place'
        else:
            lat, lon = A.centre('CA', a1)
            if r['place']:
                missed[(r['place'], r['prov'])] += 1
        date = f"{r['year']}" + (f"-{r['m']:02d}" if r['m'] else '') + (f"-{r['d']:02d}" if r['m'] and r['d'] else '')
        time = f"{r['tm'] // 100:02d}:{r['tm'] % 100:02d}" if r['tm'] is not None and r['tm'] < 2400 and r['tm'] % 100 < 60 else ''
        out.append({'id': f'cus-{len(out) + 1}', 'date': date, 'time': time, 'place': r['place'], 'prov': pname, 'a1': a1,
                    'type': r['type'], 'dur': r['dur'], 'colour': r['colour'], 'wit': r['wit'], 'shape': r['shape'],
                    'strange': r['str'], 'eval': r['eval'], 'note': note, 'lat': round(lat, 4), 'lon': round(lon, 4), 'precision': prec})
        stats[prec] += 1
    json.dump(out, open(os.path.join(ROOT, 'data', 'ufo_cases_canada.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(out)} cases', dict(stats), file=sys.stderr)
    print('most common unplaced:', missed.most_common(40), file=sys.stderr)


if __name__ == '__main__':
    main()

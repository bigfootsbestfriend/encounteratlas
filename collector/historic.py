"""Historic encounter reports from public-domain US newspapers (before 1927) -> data/historic.json.

Source pages: Library of Congress, Chronicling America (US newspapers, digitised by the National Digital
Newspaper Program). Everything here was printed in the US before 1927, so it is in the public domain.

Why not the LoC search API directly? In Oct 2026 www.loc.gov answered every request (API and browser alike)
with a Cloudflare bot check, and the old chroniclingamerica.loc.gov host returned 503. So the text search runs
over "American Stories" (Dell Research / Harvard, CC BY 4.0 on Hugging Face), which is article-level OCR of the
same Chronicling America page scans. Every hit keeps its LCCN, date, edition and page sequence, so each case
still cites and links the original LoC page.

Steps:
  python3 collector/historic.py scan [YEAR ...]  stream each year's archive once, keep articles that match the
                                                 topic patterns (cache: $HIST_CACHE or data/raw/historic)
  python3 collector/historic.py cluster          group reprints of the same story, write review files
  python3 collector/historic.py assemble PICKS   merge hand-written cases with every printing of each story
  python3 collector/historic.py geo              geocode the hand-written cases in data/historic.json in place

Cases themselves are written by hand (summaries in our own words) into data/historic.json; this script
never copies newspaper text into the site.
"""
import json, os, re, sys, tarfile, time, urllib.error, urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CACHE = os.environ.get('HIST_CACHE') or os.path.join(ROOT, 'data', 'raw', 'historic')
OUT = os.path.join(ROOT, 'data', 'historic.json')
AS_URL = 'https://huggingface.co/datasets/dell-research-harvard/AmericanStories/resolve/main/faro_{y}.tar.gz'
UA = 'EncounterAtlas-historic/1.0 (research; one request at a time)'

TOPICS = {
    'airship': r'air[\s-]?ships?\b|flying machine|aerial (?:ship|machine|navigat)|mystery of the air|(?:strange|mysterious) (?:object|light)s? in the (?:sky|heavens)',
    'wild-man': r'wild (?:man|woman|men)\b|wildman|hairy (?:man|men|giant|monster|creature|wild)|man[\s-]ape|ape[\s-]man|gorilla|(?:giant|monster)\s+(?:man|ape)\b',
    'sea-serpent': r'sea[\s-]?serpent|sea[\s-]?monster|lake (?:serpent|monster)|(?:serpent|monster) (?:in|of) (?:the )?(?:lake|river|bay|pond)|water monster',
    'jersey-devil': r'jersey devil|leeds devil|leed.?s devil|wing(?:ed)? (?:devil|monster)|(?:the|a) devil.{0,40}(?:hoof|tracks?|footprints?)',
    'phantom-light': r'(?:phantom|mysterious|spook|spooky|ghost|ghostly|weird|uncanny|unexplained) lights?\b|jack[\s-]o.?lantern|will.o.?the.?wisp',
    'giant-bird': r'(?:giant|monster|monstrous|enormous|immense|huge|mammoth|gigantic) (?:bird|eagle|vulture|condor)|thunder[\s-]?bird|(?:winged|flying) (?:monster|dragon|serpent|reptile)',
    'creature': r'(?:strange|mysterious|unknown|nondescript|queer|weird|hideous) (?:animal|beast|creature|monster|thing)|what is it\?|\bwhat-is-it\b|a monster\b',
}
TOPIC_RE = {k: re.compile(v, re.I) for k, v in TOPICS.items()}
# Cheap literal prefilter on the lower-cased page JSON before any regex work (pages are ~10x the archive size).
LITERALS = [w.encode() for w in (
    'serpent', 'monster', 'airship', 'air ship', 'air-ship', 'flying machine', 'aerial', 'wild man', 'wild woman',
    'wildman', 'wild men', 'hairy', 'gorilla', 'man-ape', 'ape-man', 'devil', 'phantom light', 'mysterious light',
    'strange light', 'spook light', 'ghost light', 'weird light', 'will-o', 'jack-o', 'giant bird', 'monster bird',
    'enormous bird', 'immense bird', 'huge bird', 'thunder bird', 'thunderbird', 'strange animal', 'strange beast',
    'strange creature', 'mysterious animal', 'mysterious beast', 'unknown animal', 'nondescript', 'what is it')]
# Words that suggest a first-hand sighting story rather than politics, circus ads or a sermon.
SIGHT_RE = re.compile(r'\b(?:seen|saw|sighted|appeared|witness|reported|frightened|terror|scared|chased|shot at|'
                      r'tracks|footprints|hair(?:y)?|feet long|glowing|hovering|excitement|startled|captured|'
                      r'farmer|hunters?|fishermen|residents|neighborhood)\b', re.I)
NOISE_RE = re.compile(r'\b(?:circus|museum|menagerie|admission|tickets?|matinee|theatre|theater|opera house|'
                      r'side show|sideshow|for sale|price|cents|novel|chapter|serial story|copyright|'
                      r'republican|democrat|tariff|senator|congress|convention|candidate)\b', re.I)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def articles(scan):
    """Rebuild articles (headline + body pieces) from a page's layout boxes."""
    groups = defaultdict(list)
    for b in scan.get('bboxes') or []:
        if b.get('class') in ('article', 'headline') and b.get('raw_text'):
            groups[b.get('full_article_id')].append(b)
    for aid, bs in groups.items():
        bs.sort(key=lambda b: b.get('reading_order_id') or 0)
        head = ' '.join(b['raw_text'] for b in bs if b['class'] == 'headline').strip()
        body = '\n'.join(b['raw_text'] for b in bs if b['class'] == 'article').strip()
        yield aid, head, body


def scan_year(y):
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, f'cand_{y}.jsonl')
    if os.path.exists(out):
        return y, 'cached'
    tmp = out + '.part'
    url = AS_URL.format(y=y)
    for attempt in range(6):
        try:
            n_pages = n_hits = 0
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'w', encoding='utf-8') as fo:
                tf = tarfile.open(fileobj=r, mode='r|gz')
                for m in tf:
                    if not m.isfile() or not m.name.endswith('.json'):
                        continue
                    raw = tf.extractfile(m).read()
                    n_pages += 1
                    low = raw.lower()
                    if not any(w in low for w in LITERALS):
                        continue
                    scan = json.loads(raw)
                    # 1840-05-23_p2_sn87065543_00415662026_1840052301_0006.json
                    base = os.path.basename(m.name)[:-5]
                    parts = base.split('_')
                    date, page, lccn, reel, issue, seq = (parts + [''] * 6)[:6]
                    for aid, head, body in articles(scan):
                        text = head + '\n' + body
                        topics = [k for k, rx in TOPIC_RE.items() if rx.search(text)]
                        if not topics:
                            continue
                        sight = len(SIGHT_RE.findall(text))
                        noise = len(NOISE_RE.findall(text))
                        if sight < 2 or noise > sight:
                            continue
                        n_hits += 1
                        fo.write(json.dumps({
                            'date': date, 'page': page.lstrip('p'), 'lccn': lccn, 'ed': issue[-2:] if issue else '01',
                            'seq': seq.lstrip('0') or '1', 'paper': scan.get('lccn', {}).get('title', ''),
                            'state': scan.get('lccn', {}).get('state', ''), 'aid': aid, 'topics': topics,
                            'sight': sight, 'head': head[:300], 'text': body[:5000]}, ensure_ascii=False) + '\n')
            os.replace(tmp, out)
            return y, f'{n_pages} pages, {n_hits} hits'
        except (urllib.error.URLError, OSError, tarfile.TarError, EOFError) as e:
            wait = 30 * (attempt + 1)
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                wait = 120 * (attempt + 1)
            log(y, 'retry in', wait, 's:', e)
            time.sleep(wait)
    return y, 'FAILED'


def cmd_scan(years):
    years = years or ([1896, 1897, 1909] + [y for y in range(1830, 1927) if y not in (1896, 1897, 1909)])
    workers = int(os.environ.get('HIST_WORKERS', '3'))
    with ProcessPoolExecutor(workers) as ex:
        for y, status in ex.map(scan_year, years):
            log(y, status)


# ---------- clustering reprints ----------
WORD = re.compile(r'[a-z]{3,}')


def shingles(text, k=5):
    w = WORD.findall(text.lower())
    return {' '.join(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


def cmd_cluster():
    cands = []
    for f in sorted(os.listdir(CACHE)):
        if f.startswith('cand_') and f.endswith('.jsonl'):
            for line in open(os.path.join(CACHE, f), encoding='utf-8'):
                cands.append(json.loads(line))
    log(len(cands), 'candidates')
    # Union-find over shared 5-word shingles (reprints share long runs of identical wording).
    parent = list(range(len(cands)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    sh = [shingles(c['head'] + ' ' + c['text']) for c in cands]
    index = defaultdict(list)
    for i, s in enumerate(sh):
        for g in s:
            index[g].append(i)
    for i, s in enumerate(sh):
        cnt = defaultdict(int)
        for g in s:
            lst = index[g]
            if len(lst) > 400:  # boilerplate phrase
                continue
            for j in lst:
                if j > i:
                    cnt[j] += 1
        for j, n in cnt.items():
            if n >= 8 and n >= 0.15 * min(len(s), len(sh[j])):
                parent[find(j)] = find(i)
    groups = defaultdict(list)
    for i in range(len(cands)):
        groups[find(i)].append(i)
    clusters = []
    for g in groups.values():
        items = sorted((cands[i] for i in g), key=lambda c: c['date'])
        best = max(items, key=lambda c: (c['sight'], len(c['text'])))
        clusters.append({'n': len(items), 'first': items[0]['date'], 'topics': best['topics'], 'best': best,
                         'papers': [{k: c[k] for k in ('date', 'page', 'lccn', 'ed', 'seq', 'paper', 'state')} for c in items]})
    clusters.sort(key=lambda c: c['first'])
    json.dump(clusters, open(os.path.join(CACHE, 'clusters.json'), 'w'), ensure_ascii=False)
    log(len(clusters), 'clusters')


# ---------- assembling hand-written cases ----------
SMALL = {'a', 'an', 'and', 'the', 'of', 'in', 'on', 'at', 'for', 'to', 'by', 'de', 'la', 'le'}


def paper_name(title):
    """'The Rodney telegraph. (Rodney, Miss.) 1838-1840' -> ('The Rodney Telegraph', 'Rodney, Miss.')"""
    m = re.match(r'^(.*?)\s*\(([^)]*)\)', title)
    name, place = (m.group(1), m.group(2)) if m else (title, '')
    name = re.sub(r'\s*\[volume\]|\s*\[microfilm reel\]|[.\s]+$', '', name, flags=re.I).strip()
    words = name.split()
    name = ' '.join(w if (w.isupper() and len(w) > 1) else (w.lower() if i and w.lower() in SMALL else w[:1].upper() + w[1:])
                    for i, w in enumerate(words))
    place = re.sub(r'\s*\[.*?\]', '', place).strip()
    return name, place


def loc_url(c):
    return f'https://www.loc.gov/resource/{c["lccn"]}/{c["date"]}/ed-{int(c.get("ed") or 1)}/?sp={c["seq"]}'


def cmd_assemble(picks_path):
    """picks.json: hand-written cases. Each has 'refs': ["lccn/date/seq", ...] (any printing of the story);
    every printing in the same cluster is added to 'papers' (earliest first), plus any extra refs listed."""
    clusters = json.load(open(os.path.join(CACHE, 'clusters.json'), encoding='utf-8'))
    where = {}
    for i, cl in enumerate(clusters):
        for p in cl['papers']:
            where[f'{p["lccn"]}/{p["date"]}/{p["seq"]}'] = i
    page_text = defaultdict(str)  # (lccn, date, seq) -> matched article text on that page
    for f in os.listdir(CACHE):
        if f.startswith('cand_') and f.endswith('.jsonl'):
            for line in open(os.path.join(CACHE, f), encoding='utf-8'):
                c = json.loads(line)
                page_text[(c['lccn'], c['date'], c['seq'])] += c['head'] + ' ' + c['text'] + ' '
    picks = json.load(open(picks_path, encoding='utf-8'))
    old = {c['id']: c for c in json.load(open(OUT, encoding='utf-8'))} if os.path.exists(OUT) else {}
    out, seen_ids = [], set()
    for pk in picks:
        assert pk['id'] not in seen_ids, pk['id']
        seen_ids.add(pk['id'])
        papers, seen = [], set()
        for ref in pk['refs']:
            if ref not in where:
                raise SystemExit(f'{pk["id"]}: unknown ref {ref}')
            for p in clusters[where[ref]]['papers']:
                key = (p['lccn'], p['date'], p['seq'])
                if key in seen or (pk.get('only') and f'{p["lccn"]}/{p["date"]}/{p["seq"]}' not in pk['refs']):
                    continue
                # 'kw': a regex the story must contain on that page (guards against loose reprint grouping)
                if pk.get('kw') and not re.search(pk['kw'], re.sub(r'\s+', ' ', page_text[key]), re.I):
                    if f'{p["lccn"]}/{p["date"]}/{p["seq"]}' in pk['refs']:
                        log(pk['id'], 'kw not found on listed ref', key)
                    continue
                seen.add(key)
                name, place = paper_name(p['paper'])
                papers.append({'paper': name, 'place': place, 'date': p['date'], 'page': p['page'] if p['page'] != 'na' else p['seq'],
                               'lccn': p['lccn'], 'url': loc_url(p)})
        papers.sort(key=lambda p: p['date'])
        case = {k: v for k, v in pk.items() if k not in ('refs', 'only', 'kw')}
        case['papers'] = papers
        prev = old.get(pk['id'])
        if prev and not pk.get('fixed') and prev.get('lat') is not None and prev.get('town') == pk.get('town') and prev.get('state') == pk.get('state'):
            case.update({k: prev[k] for k in ('lat', 'lon', 'approx')})
        out.append(case)
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log(len(out), 'cases,', sum(len(c['papers']) for c in out), 'newspaper pages')


# ---------- geocoding ----------
def cmd_geo():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bluebook as bb
    countries, country_names, admin1, _admin1_cc, us_abbr, by_place, centres = bb.load_geonames()
    cases = json.load(open(OUT, encoding='utf-8'))
    stats = defaultdict(int)
    for c in cases:
        if c.get('fixed'):  # coordinates set by hand (a lake, a bay, a stretch of coast)
            stats['fixed'] += 1
            continue
        kind, info = bb.resolve_region(bb.region_key(c['state']), admin1, country_names, us_abbr)
        lat = lon = None
        approx = True
        if kind == 'a1':
            cc, a1, _ = info
            for place in [c.get('town') or ''] + (c.get('alt') or []):
                if not place:
                    continue
                for cand in bb.place_candidates(place) + [p + '#full' for p in bb.place_candidates(place)]:
                    hits = by_place.get((cc, a1, cand))
                    if hits:
                        # Prefer a place whose own name matches over one that only lists it as an alternate name.
                        exact = [h for h in hits if bb.norm(h[3]) == cand.replace('#full', '')]
                        _, lat, lon, _ = max(exact or hits)
                        approx = place != c.get('town') or bool(c.get('near'))
                        break
                if lat is not None:
                    break
            if lat is None:
                lat, lon = centres[(cc, a1)]
            stats['place' if not approx else 'approx'] += 1
        else:
            stats['none'] += 1
            log('no region for', c['id'], c['state'])
        c['lat'], c['lon'], c['approx'] = (round(lat, 4) if lat is not None else None,
                                           round(lon, 4) if lon is not None else None, approx)
    json.dump(cases, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log(len(cases), 'cases', dict(stats))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'scan':
        cmd_scan([int(a) for a in sys.argv[2:]])
    elif cmd == 'cluster':
        cmd_cluster()
    elif cmd == 'assemble':
        cmd_assemble(sys.argv[2])
    elif cmd == 'geo':
        cmd_geo()
    else:
        print(__doc__)

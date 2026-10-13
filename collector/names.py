"""Find old newspaper stories that name a specific creature (Wendigo, Hodag, Piasa, Bear Lake monster, ...).

historic.py scans for broad topics (sea serpent, wild man, airship); this pass streams the same American Stories
archive (Dell Research / Harvard, CC BY 4.0: OCR of Library of Congress Chronicling America pages) and keeps
articles that use a creature's name or one of its aliases from data/creatures.json.

  python3 collector/names.py scan [YEAR ...]   -> data/raw/historic/names_<year>.jsonl (one line per article)
  python3 collector/names.py report            -> hits per creature and per term, to spot noisy terms

Nothing here goes on the site directly. Stories are picked by hand and written up in our own words into
data/creature_stories.json, each citing the original newspaper page at the Library of Congress.
"""
import json, os, re, sys, tarfile, time, unicodedata, urllib.error, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from historic import AS_URL, CACHE, ROOT, SIGHT_RE, UA, articles, log

# Aliases that are ordinary words, abbreviations or modern jargon: they would match thousands of unrelated articles.
SKIP = set('''abc abduction agriglyphs athol bek beks bep bessie blob btm btmm ce4 champ did disc dwarfs dwarves duba
fairies flir1 gimbal gnomes gofast grays greys hili howie howler iceman juma knackers knockers libby lob luring manny
mem mib momo moonie mothership mugwump puck puk rake redcomb roswell selma sirena shuck silencers snally tessie whitey
yahoo brownies goblins hobgoblin duende lutin lutine nisse pixies saurians catawampus kappa salvaje nuno lechuza iara
yara sedapa follet hob puca bucca mawas nordics grays howler whitey dobby trasgo trasno sharlie morag storsie issie
altie selma flessie cressie chessie mussie ponik ringdocus kerit gambo indava duwas iceman martinico horven
black dog wild man wild men forest giant sea serpent lake monster flying disc flying saucer flying saucers giant bird
little people wild woman hairy man the beast white thing bigfoot track black panther big cat'''.split())
SKIP_PHRASES = {'black dog', 'wild man', 'wild men', 'forest giant', 'sea serpent', 'lake monster', 'flying disc',
                'flying saucer', 'giant bird', 'little people', 'wild woman', 'hairy man', 'big cat', 'black panther',
                'wild man of the woods', 'sea monster', 'giant squid', 'giant octopus', 'the beast', 'devil dog',
                'good people', 'the bird', 'the gentry', 'short man', 'the fae', 'the rake', 'hat man', 'the hat man', 'black mass', 'axe man', 'green monster', 'water spirit', 'big bird', 'river child', 'king otter', 'shadow people', 'shadow person', 'black monkey', 'monkey man', 'sea giant', 'corpse dog', 'old ned', 'the thing that comes', 'fair folk', 'wee folk', 'fair family', 'hidden people', 'hidden folk', 'garden gnome', 'sea maid', 'blue men', 'the whooper', 'the paddler', 'crop circle', 'horned rabbit', 'owl woman', 'grass man', 'yellow top', 'the strange one', 'lake demon', 'white thing', 'the white thing', 'bloody cap', 'old shock', 'goat man', 'amabie', 'nunda', 'ebens', 'bloop', 'yeti'}


def norm(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().strip()


def load_terms():
    terms = defaultdict(set)
    for c in json.load(open(os.path.join(ROOT, 'data', 'creatures.json'))):
        for t in [c['name']] + c['aliases']:
            t = norm(t)
            if len(t) < 4 or t in SKIP or t.startswith('the ') or t in SKIP_PHRASES or not re.search('[a-z]', t):
                continue
            terms[t].add(c['slug'])
    return terms


def trie_regex(words):
    """One regex for many literals, factored by common prefixes so the engine doesn't try each word in turn."""
    trie = {}
    for w in words:
        node = trie
        for ch in w:
            node = node.setdefault(ch, {})
        node[''] = True

    def emit(node):
        alts, end = [], '' in node
        for ch in sorted(k for k in node if k):
            alts.append(re.escape(ch) + emit(node[ch]))
        if not alts:
            return ''
        body = alts[0] if len(alts) == 1 else '(?:' + '|'.join(alts) + ')'
        return f'(?:{body})?' if end else body
    return emit(trie)


TERMS = load_terms()
# OCR turns spaces and hyphens into either; match both.
RX = re.compile(r'\b(?:' + trie_regex(sorted(TERMS)).replace(r'\ ', r'[\s-]+').replace(r'\-', r'[\s-]?') + r')\b', re.I)
BRX = re.compile(RX.pattern.encode(), re.I)
KEY = defaultdict(set)  # term with spaces and hyphens removed -> slugs (OCR mixes them up)
for _t, _s in TERMS.items():
    KEY[re.sub(r'[\s-]+', '', _t)] |= _s


def scan_year(y):
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, f'names_{y}.jsonl')
    if os.path.exists(out):
        return y, 'cached'
    tmp = out + '.part'
    for attempt in range(6):
        try:
            n_pages = n_hits = 0
            req = urllib.request.Request(AS_URL.format(y=y), headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'w', encoding='utf-8') as fo:
                tf = tarfile.open(fileobj=r, mode='r|gz')
                for m in tf:
                    if not m.isfile() or not m.name.endswith('.json'):
                        continue
                    raw = tf.extractfile(m).read()
                    n_pages += 1
                    if not BRX.search(raw):
                        continue
                    scan = json.loads(raw)
                    parts = (os.path.basename(m.name)[:-5].split('_') + [''] * 6)[:6]
                    date, page, lccn, reel, issue, seq = parts
                    for aid, head, body in articles(scan):
                        text = head + '\n' + body
                        found = {norm(x) for x in RX.findall(text)}
                        if not found:
                            continue
                        sight = len(SIGHT_RE.findall(text))
                        if sight < 1:
                            continue
                        slugs = sorted({s for t in found for s in KEY.get(re.sub(r'[\s-]+', '', t), ())})
                        n_hits += 1
                        fo.write(json.dumps({
                            'date': date, 'page': page.lstrip('p'), 'lccn': lccn, 'ed': issue[-2:] if issue else '01',
                            'seq': seq.lstrip('0') or '1', 'paper': scan.get('lccn', {}).get('title', ''),
                            'state': scan.get('lccn', {}).get('state', ''), 'aid': aid, 'terms': sorted(found),
                            'slugs': slugs, 'sight': sight, 'head': head[:300], 'text': body[:6000]}, ensure_ascii=False) + '\n')
            os.replace(tmp, out)
            return y, f'{n_pages} pages, {n_hits} hits'
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return y, 'no archive'
            wait = (120 if e.code == 429 else 30) * (attempt + 1)
            log(y, 'retry in', wait, 's:', e)
            time.sleep(wait)
        except (urllib.error.URLError, OSError, tarfile.TarError, EOFError) as e:
            log(y, 'retry in', 30 * (attempt + 1), 's:', e)
            time.sleep(30 * (attempt + 1))
    return y, 'FAILED'


def cmd_scan(years):
    years = years or list(range(1774, 1964))
    with ProcessPoolExecutor(int(os.environ.get('HIST_WORKERS', '4'))) as ex:
        for y, status in ex.map(scan_year, years):
            log(y, status)


def cmd_report():
    by_slug, by_term = Counter(), Counter()
    for f in sorted(os.listdir(CACHE)):
        if f.startswith('names_') and f.endswith('.jsonl'):
            for line in open(os.path.join(CACHE, f), encoding='utf-8'):
                a = json.loads(line)
                by_slug.update(a['slugs'])
                by_term.update(a['terms'])
    print('per creature:', by_slug.most_common())
    print('per term:', by_term.most_common(80))


if __name__ == '__main__':
    cmd, *rest = sys.argv[1:] or ['report']
    {'scan': lambda: cmd_scan([int(y) for y in rest]), 'report': cmd_report}[cmd]()

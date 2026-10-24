"""Fill in an `audio` field (the show's own https enclosure URL) for every episode in data/podcasts_episodes.json.

Run after collector/podcasts.py (the weekly podcast workflow does). The site's podcast player streams these URLs
straight from each show's host, so nothing is re-hosted and the creators keep their download counts.

Where the URL comes from, in order:
1. iTunes search results already cached by collector/podcasts.py under data/raw/podcasts/ (episodeUrl, no network).
2. iTunes lookup: https://itunes.apple.com/lookup?id=<show_id>&entity=podcastEpisode&limit=200, matched on the
   trackId in the episode's Apple URL (?i=<trackId>).
3. The show's RSS feed (podcasts.json, else the feedUrl from the lookup), matched on the normalised title.

Only https URLs are kept. An http URL is upgraded to https and HEAD-checked; if that fails the episode gets no audio.
Raw responses are cached under data/raw/podcasts/ for CACHE_DAYS (FRESH=1 ignores the cache).
"""
import glob, hashlib, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
RAW = os.path.join(ROOT, 'data', 'raw', 'podcasts')
P_EPS = os.path.join(ROOT, 'data', 'podcasts_episodes.json')
P_SHOWS = os.path.join(ROOT, 'data', 'podcasts.json')
UA = 'EncounterAtlas-research/1.0 (https://encounteratlas.com)'
CACHE_DAYS = 6
FRESH = os.environ.get('FRESH') == '1'
GAP = 3.1  # Apple allows about 20 requests a minute
NOW = datetime.now(timezone.utc)
_last = [0.0]


def _cache_path(key):
    return os.path.join(RAW, hashlib.sha1(key.encode()).hexdigest()[:20] + '.json')


def _cached(key):
    cp = _cache_path(key)
    if not FRESH and os.path.exists(cp) and time.time() - os.path.getmtime(cp) < CACHE_DAYS * 86400:
        try:
            with open(cp) as f:
                return True, json.load(f)['data']
        except (ValueError, KeyError):
            pass
    return False, None


def _store(key, data):
    with open(_cache_path(key), 'w') as f:
        json.dump({'url': key, 'at': NOW.isoformat(), 'data': data}, f)


def _get(u, gap=0.0, timeout=40, limit=None):
    if gap:
        wait = _last[0] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    req = urllib.request.Request(u, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit) if limit else r.read()


def lookup(show_id):
    u = f'https://itunes.apple.com/lookup?id={show_id}&entity=podcastEpisode&limit=200'
    hit, data = _cached(u)
    if hit:
        return data
    for attempt in range(5):
        try:
            data = json.loads(_get(u, GAP).decode('utf-8', 'replace'))
            _store(u, data)
            return data
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                pause = 45 * (attempt + 1)
                print(f'  {e.code} from Apple, pausing {pause}s', file=sys.stderr)
                time.sleep(pause)
                continue
            print(f'  HTTP {e.code} for {u}', file=sys.stderr)
            return None
        except Exception as e:
            print(f'  {type(e).__name__} for {u}, retrying', file=sys.stderr)
            time.sleep(8)
    return None


ITEM_RE = re.compile(r'<item[\s>].*?</item>', re.S | re.I)
TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.S | re.I)
ENC_RE = re.compile(r'<enclosure\b[^>]*\burl=["\']([^"\']+)["\']', re.I)


def feed_items(feed):
    """[[title, enclosure], ...] from a show's RSS feed. Feeds can be many MB, so the parsed pairs are cached."""
    key = 'rss-items:' + feed
    hit, data = _cached(key)
    if hit:
        return data
    items = []
    try:
        raw = _get(feed, 0.5, timeout=45, limit=40 * 1024 * 1024).decode('utf-8', 'replace')
        for it in ITEM_RE.findall(raw):
            t, enc = TITLE_RE.search(it), ENC_RE.search(it)
            if t and enc:
                title = re.sub(r'^<!\[CDATA\[(.*)\]\]>$', r'\1', t.group(1).strip(), flags=re.S)
                items.append([html.unescape(title).strip(), html.unescape(enc.group(1)).strip()])
    except Exception as e:
        print(f'  feed failed ({type(e).__name__}): {feed}', file=sys.stderr)
    _store(key, items)
    return items


def norm(s):
    s = html.unescape(s or '').lower()
    return re.sub(r'[^a-z0-9]+', '', s)


_https_ok = {}


def https_only(u):
    """Return an https URL for u, or '' if there isn't a working one."""
    if not u:
        return ''
    u = u.strip()
    if u.startswith('https://'):
        return u
    if not u.startswith('http://'):
        return ''
    s = 'https://' + u[len('http://'):]
    if s in _https_ok:
        return s if _https_ok[s] else ''
    ok = False
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(s, method=method, headers={'User-Agent': UA, 'Range': 'bytes=0-1'})
            with urllib.request.urlopen(req, timeout=20) as r:
                ok = r.status < 400 and r.geturl().startswith('https://')
            break
        except urllib.error.HTTPError as e:
            if e.code in (405, 403) and method == 'HEAD':
                continue  # some hosts refuse HEAD
            break
        except Exception:
            break
    time.sleep(0.3)
    _https_ok[s] = ok
    return s if ok else ''


def track_id(url):
    m = re.search(r'[?&]i=(\d+)', url or '')
    return int(m.group(1)) if m else None


def main():
    os.makedirs(RAW, exist_ok=True)
    data = json.load(open(P_EPS, encoding='utf-8'))
    shows = {s['id']: s for s in json.load(open(P_SHOWS, encoding='utf-8'))['shows']}
    eps = [e for v in data['creatures'].values() for e in v]

    # 1. cached search results
    known = {}
    for f in glob.glob(os.path.join(RAW, '*.json')):
        try:
            d = json.load(open(f))['data']
        except Exception:
            continue
        if isinstance(d, dict):
            for r in d.get('results', []):
                if r.get('wrapperType') == 'podcastEpisode' and r.get('episodeUrl') and r.get('trackId'):
                    known[r['trackId']] = r['episodeUrl']
    src = {'cache': 0, 'lookup': 0, 'rss': 0}
    raw_url = {}
    for e in eps:
        tid = track_id(e['url'])
        if tid in known:
            raw_url[id(e)] = known[tid]
            src['cache'] += 1

    # 2. iTunes lookup per show, 3. RSS fallback
    todo = {}
    for e in eps:
        if id(e) not in raw_url:
            todo.setdefault(e['show_id'], []).append(e)
    print(f'{len(eps)} episodes, {src["cache"]} from cached search results, {len(todo)} shows to look up', file=sys.stderr)
    for n, (sid, lst) in enumerate(todo.items(), 1):
        d = lookup(sid) or {}
        res = d.get('results', [])
        by_tid = {r.get('trackId'): r.get('episodeUrl') for r in res if r.get('wrapperType') == 'podcastEpisode'}
        by_title = {norm(r.get('trackName')): r.get('episodeUrl') for r in res if r.get('wrapperType') == 'podcastEpisode'}
        feed = (shows.get(sid) or {}).get('feed') or next((r.get('feedUrl') for r in res if r.get('feedUrl')), '')
        rss = None
        for e in lst:
            u = by_tid.get(track_id(e['url'])) or by_title.get(norm(e['title']))
            if u:
                raw_url[id(e)] = u
                src['lookup'] += 1
                continue
            if feed:
                if rss is None:
                    rss = {norm(t): enc for t, enc in feed_items(feed)}
                u = rss.get(norm(e['title']))
                if u:
                    raw_url[id(e)] = u
                    src['rss'] += 1
        if n % 25 == 0:
            print(f'  {n}/{len(todo)} shows', file=sys.stderr)

    filled = 0
    for e in eps:
        a = https_only(raw_url.get(id(e), ''))
        if a:
            e['audio'] = a
            filled += 1
        else:
            e.pop('audio', None)
    with open(P_EPS, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print(f'audio: {filled}/{len(eps)} episodes ({100 * filled / max(1, len(eps)):.1f}%); '
          f'found via cache {src["cache"]}, lookup {src["lookup"]}, rss {src["rss"]}; '
          f'{sum(1 for v in _https_ok.values() if not v)} http-only URLs dropped', file=sys.stderr)


if __name__ == '__main__':
    main()

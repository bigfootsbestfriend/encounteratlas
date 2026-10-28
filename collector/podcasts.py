"""Podcast directory -> data/podcasts.json + data/podcasts_episodes.json. Rerun weekly.

Source: Apple's free iTunes Search / Lookup API (no key). Show descriptions come from each show's
own RSS feed (first chunk only). Raw responses are cached under data/raw/podcasts/ for CACHE_DAYS,
so a rerun inside that window costs no network; FRESH=1 ignores the cache.

Steps
1. Search shows for every term in SEARCH_TERMS, plus every show in NOTABLE by name.
2. Prefilter on name, genre, size and freshness; look up the survivors' latest episodes.
3. Tag topics from the show name and recent episode titles, score, dedupe, keep the best ~250.
4. For every creature in data/creatures.json, search episodes and keep the best 10.

Apple rate-limits at roughly 20 requests a minute, so requests are spaced out and back off on 403/429.
A full cold run takes about 20 minutes.
"""
import concurrent.futures, hashlib, html, json, math, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
RAW = os.path.join(ROOT, 'data', 'raw', 'podcasts')
OUT_SHOWS = os.path.join(ROOT, 'data', 'podcasts.json')
OUT_EPS = os.path.join(ROOT, 'data', 'podcasts_episodes.json')
CACHE_DAYS = 6
FRESH = os.environ.get('FRESH') == '1'
UA = 'EncounterAtlas/1.0 (+https://encounteratlas.com; weekly podcast directory)'
NOW = datetime.now(timezone.utc)
MAX_SHOWS = 250

SEARCH_TERMS = [
    'bigfoot', 'sasquatch', 'squatch', 'bigfoot encounters', 'bigfoot research', 'wood ape', 'yeti', 'skunk ape',
    'dogman', 'dogman encounters', 'werewolf encounters', 'upright canine',
    'cryptid', 'cryptids', 'cryptozoology', 'mothman', 'chupacabra', 'lake monster', 'monster encounters',
    'cryptid stories', 'creature encounters', 'wendigo',
    'ufo', 'uap', 'ufo podcast', 'ufo sightings', 'aliens', 'alien abduction', 'extraterrestrial', 'disclosure ufo',
    'close encounters', 'military ufo', 'ufo whistleblower',
    'paranormal', 'paranormal podcast', 'paranormal encounters', 'ghost stories', 'true ghost stories', 'haunted',
    'high strangeness', 'unexplained', 'unexplained mysteries', 'strange encounters', 'fortean', 'skinwalker',
    'skinwalker ranch', 'true scary stories', 'creepy encounters', 'supernatural stories',
    'military paranormal', 'wartime stories', 'soldier paranormal', 'military encounters', 'veteran ghost stories',
]

# Shows people actually recommend. Searched by name; kept even if their titles are generic.
# Value: topics to add if the episode titles don't already show them.
NOTABLE = {
    'Sasquatch Chronicles': ['bigfoot'],
    'Dogman Encounters Radio': ['dogman'],
    'Bigfoot Society': ['bigfoot'],
    'Bigfoot and Beyond with Cliff and Bobo': ['bigfoot'],
    'That UFO Podcast': ['ufo'],
    'Mysterious Universe': ['paranormal', 'ufo', 'cryptids'],
    'Astonishing Legends': ['paranormal', 'cryptids'],
    'Unexplained': ['paranormal'],
    'MrBallen Podcast: Strange, Dark & Mysterious Stories': ['paranormal'],
    'Weekly Strange': ['paranormal', 'cryptids'],
    'Small Town Monsters': ['cryptids'],
    'Where Did the Road Go?': ['paranormal', 'ufo'],
    'Expanded Perspectives': ['paranormal', 'ufo', 'cryptids'],
    "Jim Harold's Paranormal Podcast": ['paranormal'],
    "Jim Harold's Campfire": ['paranormal'],
    'Monster Talk': ['cryptids'],
    'The Confessionals': ['paranormal', 'cryptids'],
    'Spaced Out Radio Show': ['paranormal', 'ufo'],
    'Strange Familiars': ['paranormal', 'cryptids'],
    'The Unexplained with Howard Hughes': ['paranormal', 'ufo'],
    'Black Vault Radio': ['ufo'],
    'Weaponized with Jeremy Corbell & George Knapp': ['ufo', 'military'],
    'Somewhere in the Skies': ['ufo', 'paranormal'],
    'Cryptonaut Podcast': ['cryptids'],
    'Lore': ['paranormal'],
    'Myths and Legends': ['cryptids'],
    'Into the Fray': ['paranormal', 'cryptids'],
    'Mysterious Circumstances': ['paranormal'],
    'Sasquatch Odyssey': ['bigfoot'],
    'Bigfoot Collectors Club': ['bigfoot'],
    'Bigfoot Eyewitness Radio': ['bigfoot'],
    'Monsters Among Us': ['paranormal', 'cryptids'],
    'Ghost Stories Podcast': ['paranormal'],
    'The Best of Coast to Coast AM': ['paranormal', 'ufo'],
    'Reality Check with Ross Coulthart': ['ufo'],
    'The Cryptid Factor': ['cryptids'],
    'Mysterious Radio': ['paranormal', 'ufo'],
    'Midnight Society': ['paranormal'],
    'Week in Weird': ['paranormal'],
    'Unexplained Mysteries': ['paranormal'],
    'UFO Chronicles Podcast': ['ufo'],
    'Dark Histories': ['paranormal'],
    'Bigfoot Report': ['bigfoot'],
    'Bigfoot Field Guide': ['bigfoot'],
    'Wartime Stories': ['military', 'paranormal'],
}

TOPICS = {
    'bigfoot': ('Bigfoot', 'bigfoot',
                r'bigfoot|sasquatch|squatch|wood ?ape|\byeti|skunk ?ape|yowie|grassman|forest giant|wild ?man of'),
    'dogman': ('Dogman', 'dogman',
               r'dog ?man|dogmen|werewol|upright canine|wolf ?man|rougarou|loup.garou|beast of bray|wendigo|skinwalker'),
    'cryptids': ('Cryptids', 'mothman',
                 r'cryptid|cryptozoo|mothman|chupacabra|jersey devil|thunderbird|lake monster|nessie|loch ness|sea serpent'
                 r'|ogopogo|lizard ?man|flatwoods|bunyip|monsters?\b(?! energy)|creature|beast\b|legend trip'),
    'ufo': ('UFOs and UAP', 'saucer',
            r'\bufos?\b|\buaps?\b|\balien|extraterrestrial|abduct|disclosure|flying saucer|roswell|close encounter'
            r'|\bet\b contact|area 51|grusch|skinwalker ranch|tic ?tac|nimitz|non.?human intelligence|\bnhi\b'),
    'paranormal': ('Paranormal', 'ghost',
                   r'paranormal|ghost|haunt|supernatural|unexplained|high strangeness|poltergeist|occult|fortean'
                   r'|demonic|shadow (people|figure)|spooky|creepy|scary|spirit box|mysterious'),
    'military': ('Military encounters', 'military',
                 r'military|soldier|veteran|wartime|\bwar stor|\barmy\b|\bnavy\b|pentagon|special forces|marine corps|pilot'),
}
TOPIC_RE = {k: re.compile(v[2], re.I) for k, v in TOPICS.items()}
# Genres that are never a fit (audio fiction, film recaps, music, kids, business...).
BAD_GENRES = {'Music', 'Music Commentary', 'Music History', 'Music Interviews', 'Video Games', 'Science Fiction', 'Drama',
              'Comedy Fiction', 'Fiction', 'Fantasy Sports', 'Sports', 'Business', 'Investing', 'Kids & Family',
              'Stories for Kids', 'Education for Kids', 'TV & Film', 'Film Reviews', 'TV Reviews', 'After Shows',
              'Film History', 'Film Interviews', 'Christianity', 'Bible', 'Health & Fitness', 'Fitness', 'Nutrition',
              'Animation & Manga', 'Careers', 'Marketing', 'Entrepreneurship', 'Management', 'Language Learning',
              'Hinduism', 'Islam', 'Judaism', 'Buddhism', 'Sexuality', 'Relationships', 'Parenting', 'Hobbies', 'Automotive',
              'Basketball', 'Football', 'Baseball', 'Soccer', 'Hockey', 'Wrestling', 'Golf', 'Running', 'Cricket', 'Rugby'}
NON_EN = re.compile(r'\b(de la|los|las|el|historias|fantasmas|misterios?|relatos|terror|paranormales|und|der|die|das'
                    r'|och|het|een|são|não|uma|para|del|leyendas|ovnis?|extraterrestres)\b', re.I)
JUNK = re.compile(r'\b(asmr|meditation|sleep sounds|sermon|church|hypnosis|audiobook|white noise|rain sounds|horoscope'
                  r'|astrology|tarot|manifest|pop culture|biographies|fantasy football|nba|nfl|wrestling|pokemon|minecraft|fortnite|anime)\b', re.I)


# Mike's rule: no links to or data from BFRO, NUFORC or MUFON, and no links to competing cryptid/encounter hubs or maps.
# Shows produced by those organisations are left out (and logged); shows that only mention them are fine.
BLOCKED_HOSTS = re.compile(r'(^|\.)(bfro\.net|nuforc\.org|mufon\.com|cryptidcatchers?\.\w+|cryptidatlas\.\w+'
                           r'|enigmalabs\.\w+)$', re.I)
# Publishers of what look like auto-generated daily "content farm" shows.
FARM_PUBLISHERS = re.compile(r'mystic circle|caloroga|cyberclaw|silas vance|^sezgin$|^tomys$', re.I)
ORG_RE = re.compile(r'\bbfro\b|bigfoot field researchers|\bnuforc\b|national ufo reporting|\bmufon\b|mutual ufo network', re.I)
LEFT_OUT = []  # organisation-produced shows we skipped, for the log
URL_RE = re.compile(r'(https?://|www\.)\S+|\b\S+\.(com|net|org|io|co|tv|fm)(/\S*)?\b', re.I)

# ---------- fetching ----------
_last = [0.0]
_gap = [3.1]


def _cache_path(u):
    return os.path.join(RAW, hashlib.sha1(u.encode()).hexdigest()[:20] + '.json')


def itunes(path, **params):
    """GET an iTunes endpoint (search/lookup), cached and throttled. Returns the parsed JSON or None."""
    u = f'https://itunes.apple.com/{path}?' + urllib.parse.urlencode(params)
    cp = _cache_path(u)
    if not FRESH and os.path.exists(cp) and time.time() - os.path.getmtime(cp) < CACHE_DAYS * 86400:
        with open(cp) as f:
            return json.load(f)['data']
    for attempt in range(6):
        wait = _last[0] + _gap[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(u, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode('utf-8', 'replace'))
            with open(cp, 'w') as f:
                json.dump({'url': u, 'at': NOW.isoformat(), 'data': data}, f)
            return data
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                _gap[0] = min(_gap[0] * 1.5, 10)
                pause = 45 * (attempt + 1)
                print(f'  {e.code} from Apple, pausing {pause}s (gap now {_gap[0]:.1f}s)', file=sys.stderr)
                time.sleep(pause)
                continue
            print(f'  HTTP {e.code} for {u}', file=sys.stderr)
            return None
        except Exception as e:  # network blip
            print(f'  {type(e).__name__} for {u}, retrying', file=sys.stderr)
            time.sleep(10)
    return None


def feed_description(feed):
    """First <description>/<itunes:summary> from a show's RSS feed (reads only the first 96 KB). Cached."""
    if not feed:
        return ''
    cp = _cache_path('rss:' + feed)
    if not FRESH and os.path.exists(cp) and time.time() - os.path.getmtime(cp) < CACHE_DAYS * 86400:
        with open(cp) as f:
            return json.load(f)['data']
    desc = ''
    try:
        req = urllib.request.Request(feed, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            head = r.read(98304).decode('utf-8', 'replace')
        head = head.split('<item', 1)[0]
        m = (re.search(r'<itunes:summary[^>]*>(.*?)</itunes:summary>', head, re.S) or
             re.search(r'<description[^>]*>(.*?)</description>', head, re.S))
        if m:
            desc = clean_text(m.group(1))
    except Exception:
        desc = ''
    with open(cp, 'w') as f:
        json.dump({'url': feed, 'at': NOW.isoformat(), 'data': desc}, f)
    return desc


def clean_text(s):
    s = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', s, flags=re.S)
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    s = html.unescape(s)
    s = URL_RE.sub('', s)  # descriptions are shown as plain text; never carry their links (BFRO etc.)
    return re.sub(r'\s+', ' ', s).strip()


def blocked_org_only(name):
    """Shows produced by BFRO, NUFORC or MUFON (their name in the show title or publisher) are left out."""
    return bool(ORG_RE.search(name))


def safe_feed(feed):
    """No links to BFRO/NUFORC/MUFON or competing hubs, even as an RSS link. Apple links are fine."""
    return '' if BLOCKED_HOSTS.search(urllib.parse.urlsplit(feed or '').netloc) else feed


def short(s, n):
    s = clean_text(s or '')
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(' ', 1)[0].rstrip(',.;:-')
    return cut + '…'


def days_ago(iso):
    if not iso:
        return 99999
    try:
        return (NOW - datetime.fromisoformat(iso.replace('Z', '+00:00'))).days
    except ValueError:
        return 99999


def clean_url(u):
    return re.sub(r'[?&]uo=\d+', '', u or '').replace('itunes.apple.com', 'podcasts.apple.com')


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


# ---------- shows ----------
def collect_shows():
    os.makedirs(RAW, exist_ok=True)
    cands = {}

    def add(r, term, rank, notable=None):
        if r.get('kind') != 'podcast' or not r.get('collectionId'):
            return
        c = cands.setdefault(r['collectionId'], {'r': r, 'terms': set(), 'best_rank': 999, 'notable': None})
        c['terms'].add(term)
        c['best_rank'] = min(c['best_rank'], rank)
        if notable:
            c['notable'] = notable

    print(f'searching {len(SEARCH_TERMS)} terms...', file=sys.stderr)
    for t in SEARCH_TERMS:
        d = itunes('search', media='podcast', term=t, country='US', limit=200)
        for i, r in enumerate((d or {}).get('results', [])):
            add(r, t, i)
    print(f'checking {len(NOTABLE)} notable shows...', file=sys.stderr)
    missing = []
    for name in NOTABLE:
        d = itunes('search', media='podcast', term=name, country='US', limit=10)
        best, best_sim = None, 0
        for r in (d or {}).get('results', []):
            sim = SequenceMatcher(None, norm(name), norm(r.get('collectionName'))).ratio()
            if norm(name) in norm(r.get('collectionName')):
                sim = max(sim, .9)
            # equal names: the original has far more episodes than copycat re-uploads
            if sim > best_sim or (sim == best_sim and best and (r.get('trackCount') or 0) > (best.get('trackCount') or 0)):
                best, best_sim = r, sim
        if best and best_sim >= .72:
            add(best, 'notable', 0, notable=name)
        else:
            missing.append(name)
    if missing:
        print('  not found on Apple:', ', '.join(missing), file=sys.stderr)

    # prefilter before spending lookups
    pre = []
    for cid, c in cands.items():
        r = c['r']
        name = f"{r.get('collectionName', '')} {r.get('artistName', '')}"
        genres = set(r.get('genres', [])) - {'Podcasts'}
        if genres & BAD_GENRES and not c['notable'] or (r.get('trackCount') or 0) < 10 and c['notable']:
            continue
        if not c['notable']:
            if (r.get('trackCount') or 0) < 4 or JUNK.search(name) or NON_EN.search(r.get('collectionName', '')):
                continue
            if FARM_PUBLISHERS.search(r.get('artistName', '')):
                continue
            if days_ago(r.get('releaseDate')) > 730 and (r.get('trackCount') or 0) < 150:
                continue
        name_topics = [k for k, rx in TOPIC_RE.items() if rx.search(r.get('collectionName', ''))]
        if c['notable'] or name_topics or len(c['terms']) >= 3:
            c['name_topics'] = name_topics
            pre.append(c)
    pre.sort(key=lambda c: (not c['notable'], -len(c['name_topics']), c['best_rank'], -len(c['terms'])))
    pre = pre[:420]
    print(f'{len(cands)} candidates, {len(pre)} pass the prefilter; looking up episodes...', file=sys.stderr)

    shows = []
    for i, c in enumerate(pre):
        if i % 50 == 0:
            print(f'  lookup {i}/{len(pre)}', file=sys.stderr)
        r = c['r']
        d = itunes('lookup', id=r['collectionId'], entity='podcastEpisode', limit=40, country='US')
        res = (d or {}).get('results', [])
        if not res:
            continue
        show = next((x for x in res if x.get('kind') == 'podcast'), r)
        eps = [x for x in res if x.get('wrapperType') == 'podcastEpisode']
        eps.sort(key=lambda x: x.get('releaseDate', ''), reverse=True)
        titles = [x.get('trackName', '') for x in eps]
        # Only use episode descriptions lightly (they're full of ads); titles carry the signal.
        ep_topics = {}
        for k, rx in TOPIC_RE.items():
            hits = sum(1 for t in titles if rx.search(t))
            ep_topics[k] = hits / max(len(titles), 1)
        non_en = sum(1 for t in titles if NON_EN.search(t)) / max(len(titles), 1)
        if non_en > .35 and not c['notable']:
            continue
        name = f"{show.get('collectionName', '')} {show.get('artistName', '')}"
        if blocked_org_only(name):
            LEFT_OUT.append(f"{show.get('collectionName')} ({show.get('artistName')}) {clean_url(show.get('collectionViewUrl'))}")
            continue
        # The show title counts on its own; the publisher name only with some support from episode titles.
        topics = [k for k in TOPICS if TOPIC_RE[k].search(show.get('collectionName', '')) or
                  (TOPIC_RE[k].search(show.get('artistName', '')) and ep_topics[k] >= .1) or (ep_topics[k] >= .15 and ep_topics[k] * len(titles) >= 2)]
        if c['notable']:
            topics = list(dict.fromkeys(topics + NOTABLE[c['notable']]))
        # Military only counts alongside something strange (otherwise it's a war-history show).
        if 'military' in topics and not (set(topics) - {'military'}):
            topics = []
        if not topics:
            continue
        any_rate = sum(1 for t in titles if any(rx.search(t) for rx in TOPIC_RE.values())) / max(len(titles), 1)
        strong_name = bool(c['name_topics'])
        if not c['notable'] and not strong_name and any_rate < .3:
            continue
        if not c['notable'] and any_rate < .12:  # catchy name, but the episodes are about something else
            continue
        eps = [x for x in eps if days_ago(x.get('releaseDate')) >= 0]  # drop scheduled (future-dated) episodes
        latest = eps[0]['releaseDate'] if eps else show.get('releaseDate', '')
        age = days_ago(latest)
        n = show.get('trackCount') or len(eps)
        recent30 = sum(1 for x in eps if days_ago(x.get('releaseDate')) <= 30)
        if recent30 == len(eps) and len(eps) >= 10:  # the lookup window is full: estimate from posting rate
            span = max(days_ago(eps[-1].get('releaseDate')), 1)
            recent30 = round(len(eps) * 30 / span)
        # 20+ episodes a month from a young show is almost always auto-generated filler
        if not c['notable'] and recent30 >= 20 and n <= 120:
            continue
        stale = age > 730
        if stale and not c['notable'] and not (n >= 150 and strong_name):
            continue
        score = (12 if c['notable'] else 0) + 4 * strong_name + 8 * any_rate + 2.2 * math.log1p(n)
        score += 3 if age <= 30 else 1.5 if age <= 180 else 0 if age <= 365 else -3 if age <= 730 else -6
        score += max(0, 4 - c['best_rank'] / 15) + min(len(c['terms']), 6) * .5
        ep0 = eps[0] if eps else None
        shows.append({
            'id': show['collectionId'],
            'name': show.get('collectionName', '').strip(),
            'publisher': (show.get('artistName') or '').strip(),
            'genre': show.get('primaryGenreName', ''),
            'episodes': n,
            'latest': (latest or '')[:10],
            'recent30': recent30,
            'apple': clean_url(show.get('collectionViewUrl')),
            'feed': safe_feed(show.get('feedUrl', '')),
            'art': show.get('artworkUrl600') or show.get('artworkUrl100', ''),
            'explicit': show.get('collectionExplicitness') == 'explicit',
            'topics': topics,
            'notable': bool(c['notable']),
            'stale': stale,
            'score': round(score, 2),
            'last_ep': {'title': ep0.get('trackName', ''), 'date': ep0.get('releaseDate', '')[:10],
                        'url': clean_url(ep0.get('trackViewUrl'))} if ep0 else None,
        })

    # Copycat re-uploads reuse a big show's exact name (e.g. a 140-episode "MrBallen Podcast" clone on a generic
    # audiobook account): for each name keep only the show with the most episodes, which is the original.
    best = {}
    for s in shows:
        k = norm(s['name'])
        if k not in best or s['episodes'] > best[k]['episodes']:
            best[k] = s
    shows = [s for s in shows if best[norm(s['name'])] is s]
    # dedupe: same normalised name, or same feed
    shows.sort(key=lambda s: -s['score'])
    seen, out = set(), []
    for s in shows:
        keys = {('n', norm(s['name'])), ('f', s['feed'].rstrip('/').lower())} - {('f', '')}
        if keys & seen:
            continue
        seen |= keys
        out.append(s)
    out = out[:MAX_SHOWS]

    print(f'fetching {len(out)} feed descriptions...', file=sys.stderr)
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for s, desc in zip(out, ex.map(lambda s: feed_description(s['feed']), out)):
            s['about'] = short(desc, 300)
    return out


# ---------- creature episodes ----------
CTX = (r'cryptid|monster|creature|sighting|encounter|bigfoot|sasquatch|paranormal|legend|ufo|uap|alien|myster|unexplained'
       r'|strange|folklore|myth|beast|lake|swamp|investigat|witness|haunt|spooky|creepy|scary|weird')
UFO_CTX = r'ufo|uap|alien|sighting|navy|pilot|unidentified|disclosure|saucer|craft|sky|military'
# slug: (search terms, regex an episode's title/description must match, context regex or None, exclude regex or None)
CREATURE_Q = {
    'bigfoot': (['bigfoot', 'sasquatch'], r'bigfoot|sasquatch', None, None),
    'yeti': (['yeti', 'abominable snowman'], r'\byeti\b|abominable snowman', CTX, r'cooler|tumbler'),
    'yowie': (['yowie'], r'\byowies?\b', None, None),
    'skunk-ape': (['skunk ape'], r'skunk ?ape', None, None),
    'fouke-monster': (['fouke monster', 'boggy creek monster'], r'fouke|boggy creek', None, None),
    'honey-island-swamp-monster': (['honey island swamp monster'], r'honey island', None, None),
    'momo': (['momo missouri monster', 'missouri monster'], r'missouri monster|\bmomo\b', r'monster|bigfoot|louisiana, mo|cryptid', r'challenge'),
    'almas': (['almas wildman', 'almasty'], r'\balmas\b|almasty', CTX, None),
    'yeren': (['yeren', 'chinese wildman'], r'yeren|chinese wild ?man', None, None),
    'orang-pendek': (['orang pendek'], r'orang pendek', None, None),
    'dogman': (['dogman', 'dogman encounter', 'beast of bray road'], r'dog ?man|dogmen|beast of bray road', CTX, r'pilkey|dav |graphic novel'),
    'rougarou': (['rougarou', 'loup garou'], r'rougarou|loup.garou', None, None),
    'chupacabra': (['chupacabra'], r'chupacabra', None, None),
    'mothman': (['mothman'], r'moth ?man', None, None),
    'thunderbird': (['thunderbird cryptid', 'thunderbird sighting', 'thunderbird giant bird'], r'thunderbirds?\b', CTX + r'|bird|wingspan', r'mozilla|\bford\b|thunderbirds are go|email'),
    'jersey-devil': (['jersey devil'], r'(?<!new )jersey devil(?!s)', None, None),
    'owlman': (['owlman', 'owlman of mawnan'], r'owl ?man\b', CTX, None),
    'kongamato': (['kongamato'], r'kongamato', None, None),
    'loch-ness-monster': (['loch ness monster', 'nessie'], r'loch ness|\bnessie\b', CTX, None),
    'ogopogo': (['ogopogo'], r'ogopogo', None, None),
    'champ': (['lake champlain monster', 'champ lake monster'], r'lake champlain|\bchampy\b|\bchamp\b', r'monster|serpent|creature|cryptid|lake', None),
    'bessie': (['lake erie monster', 'south bay bessie'], r'lake erie monster|bessie', r'monster|serpent|lake erie|cryptid', None),
    'cadborosaurus': (['cadborosaurus', 'caddy sea serpent'], r'cadborosaurus|\bcaddy\b', r'serpent|monster|cryptid|sea', None),
    'bear-lake-monster': (['bear lake monster'], r'bear lake monster', None, None),
    'flathead-lake-monster': (['flathead lake monster'], r'flathead lake monster|flessie', None, None),
    'mokele-mbembe': (['mokele mbembe'], r'mokele.?mbembe', None, None),
    'bunyip': (['bunyip'], r'bunyip', CTX, None),
    'flatwoods-monster': (['flatwoods monster', 'braxton county monster'], r'flatwoods|braxton county', None, None),
    'dover-demon': (['dover demon'], r'dover demon', None, None),
    'hopkinsville-goblins': (['hopkinsville goblins', 'kelly hopkinsville'], r'hopkinsville|kelly.{0,30}(goblin|little green)', None, None),
    'loveland-frog': (['loveland frogman', 'loveland frog'], r'loveland (frog|lizard)', None, None),
    'lizard-man': (['lizard man scape ore swamp', 'lizard man of lee county'], r'lizard ?man', r'scape ore|lee county|south carolina|swamp|cryptid|monster|sighting', None),
    'mongolian-death-worm': (['mongolian death worm'], r'death worm|olgoi', None, None),
    'tatzelwurm': (['tatzelwurm'], r'tatzelwurm', None, None),
    'ufo-saucer': (['flying saucer'], r'flying saucers?|flying disc', UFO_CTX, None),
    'ufo-triangle': (['black triangle ufo', 'triangle ufo'], r'triangle', UFO_CTX, None),
    'ufo-orbs': (['marfa lights', 'foo fighters ufo', 'ufo orbs'], r'marfa lights|\borbs?\b|foo fighters', UFO_CTX + r'|lights|ww2|wwii|world war', r'grohl|concert|album'),
    'ufo-tic-tac': (['tic tac ufo', 'nimitz ufo'], r'tic.?tac|nimitz', UFO_CTX, None),
}


def collect_episodes(creatures, shows):
    by_id = {s['id']: s for s in shows}
    out = {}
    for c in creatures:
        q = CREATURE_Q.get(c['slug'])
        if not q:
            q = ([c['name']], re.escape(c['name'].lower()), CTX, None)
        terms, must, ctx, excl = q
        must_re, ctx_re = re.compile(must, re.I), re.compile(ctx, re.I) if ctx else None
        excl_re = re.compile(excl, re.I) if excl else None
        found = {}
        for t in terms:
            d = itunes('search', media='podcast', entity='podcastEpisode', term=t, country='US', limit=150)
            for rank, e in enumerate((d or {}).get('results', [])):
                if e.get('wrapperType') != 'podcastEpisode':
                    continue
                title, desc = e.get('trackName', ''), clean_text(e.get('description') or e.get('shortDescription') or '')
                text = f'{title} {desc} {e.get("collectionName", "")}'
                in_title = bool(must_re.search(title))
                if not (in_title or must_re.search(desc)):
                    continue
                if ctx_re and not ctx_re.search(text):
                    continue
                if excl_re and excl_re.search(text):
                    continue
                if blocked_org_only(e.get('collectionName', '')) or BLOCKED_HOSTS.search(urllib.parse.urlsplit(e.get('feedUrl') or '').netloc):
                    continue
                if NON_EN.search(title) and not by_id.get(int(e.get('collectionId', 0))):
                    continue
                if any(g.get('name') in BAD_GENRES for g in e.get('genres', []) if isinstance(g, dict)):
                    continue
                age = days_ago(e.get('releaseDate'))
                show = by_id.get(int(e.get('collectionId', 0)))
                score = (4 if in_title else 1) + (3 if show else 0) + (show['score'] / 12 if show else 0)
                score += 3 if age <= 180 else 2 if age <= 365 else 1 if age <= 1095 else 0
                score += max(0, 3 - rank / 20)
                mins = round((e.get('trackTimeMillis') or 0) / 60000)
                key = e.get('trackId')
                if key in found and found[key]['_s'] >= score:
                    continue
                found[key] = {'_s': score, 'title': title.strip(), 'show': e.get('collectionName', ''),
                              'show_id': int(e.get('collectionId', 0)), 'date': (e.get('releaseDate') or '')[:10],
                              'mins': mins, 'url': clean_url(e.get('trackViewUrl')),
                              'art': e.get('artworkUrl600') or e.get('artworkUrl160', ''),
                              'about': short(desc, 260), 'in_dir': bool(show)}
        # best first, max 2 per show, drop near-duplicate titles (part 1/part 2 reposts)
        picked, per_show, titles = [], {}, set()
        for e in sorted(found.values(), key=lambda e: -e['_s']):
            tk = norm(re.sub(r'\b(part|pt|ep|episode)\b.*', '', e['title']))[:40]
            if per_show.get(e['show_id'], 0) >= 2 or (tk and tk in titles):
                continue
            per_show[e['show_id']] = per_show.get(e['show_id'], 0) + 1
            titles.add(tk)
            e.pop('_s')
            picked.append(e)
            if len(picked) == 10:
                break
        out[c['slug']] = picked
        print(f'  {c["slug"]}: {len(picked)} episodes', file=sys.stderr)
    return out


def main():
    creatures = json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))
    shows = collect_shows()
    print(f'{len(shows)} shows kept', file=sys.stderr)
    if LEFT_OUT:
        print('left out (made by BFRO/NUFORC/MUFON):\n  ' + '\n  '.join(LEFT_OUT), file=sys.stderr)
    with open(OUT_SHOWS, 'w') as f:
        json.dump({'updated': NOW.strftime('%Y-%m-%d'), 'topics': {k: v[0] for k, v in TOPICS.items()}, 'shows': shows},
                  f, indent=1, ensure_ascii=False)
    print('searching creature episodes...', file=sys.stderr)
    eps = collect_episodes(creatures, shows)
    with open(OUT_EPS, 'w') as f:
        json.dump({'updated': NOW.strftime('%Y-%m-%d'), 'creatures': eps}, f, indent=1, ensure_ascii=False)
    print(f'wrote {OUT_SHOWS} ({len(shows)} shows) and {OUT_EPS} '
          f'({sum(len(v) for v in eps.values())} episodes, {sum(1 for v in eps.values() if v)} creatures)', file=sys.stderr)


if __name__ == '__main__':
    main()

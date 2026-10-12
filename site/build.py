"""Builds the Encounter Atlas static site into _site/ (stdlib only).

Inputs: data/creatures.json (hand-written), data/bluebook.json (collector/bluebook.py),
data/military.json (hand-written). Output: plain HTML pages + a few JSON/GeoJSON files.
"""
import html, json, os, re, shutil, sys
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.environ.get('OUT_DIR') or os.path.join(ROOT, '_site')
STATIC = os.path.join(ROOT, 'site', 'static')
SITE_URL = os.environ.get('SITE_URL', 'https://encounteratlas.com').rstrip('/')
BASE = os.environ.get('BASE_PATH', '').rstrip('/')  # '/encounteratlas' on the GitHub Pages preview
LAUNCHED = False  # noindex everywhere until Mike has reviewed the site
CF_BEACON = os.environ.get('CF_BEACON', '')

CATS = {
    'hominid': ('Hairy hominids', 'Upright, ape-like giants of the woods and mountains'),
    'canid': ('Dogmen and beasts', 'Upright canines, werewolves and livestock killers'),
    'winged': ('Winged things', 'Red-eyed fliers and impossible birds'),
    'aquatic': ('Lake and sea monsters', 'Long necks, humps and serpents in deep water'),
    'entity': ('Strange visitors', 'Small grey beings, frogmen and things from the sky'),
    'other': ('Odd creatures', 'Desert worms, Alpine lizards and other one-offs'),
    'ufo': ('UFOs and UAP', 'Saucers, triangles, orbs and what the military tracked'),
}
MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']
US_STATES = {}


def esc(s):
    return html.escape(str(s), quote=True)


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def url(path):
    return BASE + path


def icon(name, cls='ico'):
    svg = open(os.path.join(STATIC, 'icons', name + '.svg')).read().strip()
    return svg.replace('<svg ', f'<svg class="{cls}" aria-hidden="true" focusable="false" ', 1)


def write(path, text):
    full = os.path.join(OUT, path.lstrip('/'))
    if full.endswith('/'):
        full += 'index.html'
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(text)


NAV = [('/map/', 'Map'), ('/creatures/', 'Creatures'), ('/ufo/', 'UFO files'), ('/military/', 'Military'),
       ('/places/', 'Places'), ('/podcasts/', 'Podcasts'), ('/report/', 'Report')]


def page(path, title, body, desc='', body_class='', head_extra='', canonical=True):
    full_title = title if title.startswith('Encounter Atlas') else f'{title} | Encounter Atlas'
    nav = ''.join(f'<a href="{url(p)}"{" aria-current=page" if path.startswith(p) else ""}>{esc(n)}</a>'
                  for p, n in NAV)
    robots = '' if LAUNCHED else '<meta name="robots" content="noindex">'
    beacon = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
              f'data-cf-beacon=\'{{"token": "{CF_BEACON}"}}\'></script>') if CF_BEACON else ''
    canon = f'<link rel="canonical" href="{SITE_URL}{path}">' if canonical else ''
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}{canon}
<meta name="theme-color" content="#13261F">
<link rel="icon" href="{url('/static/favicon.svg')}" type="image/svg+xml">
<link rel="manifest" href="{url('/manifest.webmanifest')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,600;0,700;1,400&family=Zilla+Slab:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{url('/static/site.css')}">
{head_extra}
</head>
<body class="{body_class}">
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <a class="brand" href="{url('/')}"><span class="lantern" aria-hidden="true"></span>Encounter Atlas</a>
  <nav class="nav" aria-label="Main">{nav}</nav>
</header>
<main id="main">
{body}
</main>
<footer class="foot">
  <div class="foot-in">
    <p class="foot-brand"><span class="lantern" aria-hidden="true"></span>Encounter Atlas</p>
    <p>Sightings, creatures and official files, mapped. Reports are what witnesses say they saw. We don't claim they're real, and we don't claim they're not.</p>
    <p class="foot-links"><a href="{url('/about/')}">About and sources</a><a href="{url('/creatures/')}">Creature index</a><a href="{url('/ufo/')}">UFO files</a><a href="{url('/report/')}">Report an encounter</a></p>
    <p class="small">Air Force case files: US National Archives, Record Group 341. Place data: GeoNames (CC BY 4.0). Map: OpenFreeMap, OpenMapTiles, OpenStreetMap contributors.</p>
  </div>
</footer>
{beacon}
</body>
</html>
'''


def badge(c, size='md'):
    return (f'<span class="badge badge-{size} cat-{c["cat"]}">{icon(c["icon"])}</span>')


def creature_card(c):
    aka = f'<span class="aka">aka {esc(", ".join(c["aliases"][:2]))}</span>' if c['aliases'] else ''
    return (f'<a class="crit" href="{url("/creatures/" + c["slug"] + "/")}" data-cat="{c["cat"]}" '
            f'data-names="{esc((c["name"] + " " + " ".join(c["aliases"]) + " " + c["region"]).lower())}">'
            f'{badge(c)}<span class="crit-txt"><span class="crit-name">{esc(c["name"])}</span>{aka}'
            f'<span class="crit-sum">{esc(c["summary"])}</span></span></a>')


def build_creatures(creatures, by_slug):
    groups = defaultdict(list)
    for c in creatures:
        groups[c['cat']].append(c)
    chips = ''.join(f'<button type="button" class="chip" data-filter="{k}" aria-pressed="false">'
                    f'<span class="dot cat-{k}"></span>{esc(v[0])}</button>' for k, v in CATS.items() if groups[k])
    sections = ''
    for k, (label, blurb) in CATS.items():
        if not groups[k]:
            continue
        cards = ''.join(creature_card(c) for c in sorted(groups[k], key=lambda c: c['name']))
        sections += (f'<section class="cat-group" data-group="{k}"><h2 class="cat-h"><span class="dot cat-{k}"></span>'
                     f'{esc(label)}</h2><p class="cat-blurb">{esc(blurb)}</p><div class="crit-grid">{cards}</div></section>')
    body = f'''
<section class="band band-dark index-head">
  <div class="wrap">
    <h1>Creature index</h1>
    <p class="lede">{len(creatures)} creatures and phenomena, from Bigfoot to the Navy's Tic Tac. Search by any name: Sasquatch, Nessie, goat-sucker.</p>
    <div class="search-row">
      <label class="visually-hidden" for="q">Search creatures</label>
      <input id="q" type="search" placeholder="Search by name, nickname or place" autocomplete="off">
    </div>
    <div class="chips" role="group" aria-label="Filter by type">{chips}</div>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  {sections}
  <p class="empty" hidden>No creature by that name yet. <a href="{url('/report/')}">Tell us about it</a> and we'll add it.</p>
</div></div>
<script src="{url('/static/index.js')}" defer></script>'''
    write('/creatures/', page('/creatures/', 'Creature index: cryptids, monsters and UFO types', body,
                              'Searchable index of cryptids and UFO types with alternative names, famous cases and what witnesses report.'))

    for c in creatures:
        aka = (f'<p class="aka-line">Also called {esc(", ".join(c["aliases"]))}</p>' if c['aliases'] else '')
        facts = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in
                        [('Where', c['region']), ('Size', c['size']), ('Habitat', c['habitat']),
                         ('First reported', c['first'])] if v)
        body_p = ''.join(f'<p>{esc(p)}</p>' for p in c['body'])
        signs = ''.join(f'<li>{esc(s)}</li>' for s in c['signs'])
        cases = ''.join(f'<li><span class="yr">{f["year"]}</span><span><strong>{esc(f["name"])}</strong>'
                        f'<br><span class="muted">{esc(f["place"])}</span></span></li>'
                        for f in sorted(c['famous'], key=lambda f: f['year']))
        rel = ''.join(creature_card(by_slug[s]) for s in c['related'] if s in by_slug)
        wiki = f'https://en.wikipedia.org/wiki/{c["wiki"].replace(" ", "_")}' if c.get('wiki') else ''
        ufo_note = ''
        if c['cat'] == 'ufo':
            ufo_note = (f'<p class="callout">{icon("folder", "ico ico-inline")} Browse 10,622 US Air Force Project Blue Book '
                        f'case files on the <a href="{url("/map/")}">map</a> or <a href="{url("/ufo/")}">by state</a>.</p>')
        body = f'''
<section class="band band-dark creature-head cat-{c['cat']}">
  <div class="wrap creature-head-in">
    {badge(c, 'xl')}
    <div>
      <p class="crumb"><a href="{url('/creatures/')}">Creature index</a> / {esc(CATS[c['cat']][0])}</p>
      <h1>{esc(c['name'])}</h1>
      {aka}
      <p class="lede">{esc(c['summary'])}</p>
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap creature-body">
  <article class="prose">
    {body_p}
    {ufo_note}
    <h2>What witnesses report</h2>
    <ul class="signs">{signs}</ul>
    <h2>Famous cases</h2>
    <ol class="timeline">{cases}</ol>
    <h2>Seen one?</h2>
    <p><a class="btn" href="{url('/report/')}">Report an encounter</a></p>
  </article>
  <aside class="facts">
    <dl>{facts}</dl>
    {f'<p class="more"><a href="{wiki}" rel="noopener">Read more on Wikipedia</a></p>' if wiki else ''}
  </aside>
</div>
{f'<div class="wrap"><h2 class="rel-h">Related</h2><div class="crit-grid">{rel}</div></div>' if rel else ''}
</div>'''
        write(f'/creatures/{c["slug"]}/', page(f'/creatures/{c["slug"]}/', f'{c["name"]}: sightings, facts and other names',
                                               body, f'{c["summary"]} Also called {", ".join(c["aliases"][:4])}.'
                                               if c['aliases'] else c['summary']))


def case_line(b):
    when = f'{MONTHS[b["month"]]} {b["year"]}' if b.get('month') and b.get('year') else (str(b['year']) if b.get('year') else 'Date unknown')
    place = b['place'] or b['region'] or 'Unknown place'
    scan = f' <a class="muted" href="{esc(b["img"])}" rel="noopener">first page</a>' if b.get('img') else ''
    return (f'<li><span class="yr">{esc(when)}</span><span><a href="https://catalog.archives.gov/id/{b["id"]}" rel="noopener">'
            f'{esc(place)}</a>{scan}</span></li>')


def region_slug(b):
    if b['cc'] == 'US' and b['a1']:
        return 'us-' + slugify(b['region'])
    if b['cc']:
        return slugify(b['region'] or b['cc'])
    return 'unknown'


def build_ufo(bluebook):
    by_region = defaultdict(list)
    for b in bluebook:
        by_region[region_slug(b)].append(b)
    names = {}
    for k, v in by_region.items():
        b = v[0]
        names[k] = b['region'] if b['cc'] else 'Place unclear or at sea'
    years = Counter(b['year'] for b in bluebook if b.get('year'))
    ymax = max(years.values())
    bars = ''
    for y in range(1947, 1970):
        n = years.get(y, 0)
        h = round(100 * n / ymax)
        bars += (f'<div class="bar" style="--h:{h}%" title="{y}: {n:,} cases"><span class="bar-n">{n:,}</span>'
                 f'<span class="bar-y">{"&#8217;" + str(y)[2:] if y % 2 else "&#8217;" + str(y)[2:]}</span></div>')
    us = sorted((k for k in by_region if k.startswith('us-')), key=lambda k: names[k])
    other = sorted((k for k in by_region if not k.startswith('us-') and k != 'unknown'), key=lambda k: -len(by_region[k]))
    def links(keys):
        return ''.join(f'<li><a href="{url("/ufo/blue-book/" + k + "/")}">{esc(names[k])}</a> <span class="muted">{len(by_region[k]):,}</span></li>' for k in keys)
    top = Counter({names[k]: len(by_region[k]) for k in us}).most_common(1)[0]
    body = f'''
<section class="band band-dark">
  <div class="wrap">
    <p class="crumb">UFO files</p>
    <h1>Project Blue Book: the Air Force UFO files</h1>
    <p class="lede">From 1947 to 1969 the US Air Force investigated {len(bluebook):,} UFO reports. Every case folder is now public at the National Archives. We've put them on a map and sorted them by state and country.</p>
    <p><a class="btn" href="{url('/map/')}">Open the map</a></p>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <h2>Cases by year</h2>
  <p>{max(years, key=years.get)} was the busiest year, with {ymax:,} reports. The big spikes match famous flaps: the Washington, DC sightings of 1952, the Levelland wave of 1957 and the Michigan “swamp gas” reports of 1966.</p>
  <div class="bars" role="img" aria-label="Bar chart of Blue Book cases per year, 1947 to 1969">{bars}</div>
  <h2>United States</h2>
  <p>{esc(top[0])} has the most case folders ({top[1]:,}).</p>
  <ul class="cols">{links(us)}</ul>
  <h2>Rest of the world</h2>
  <p>Air Force personnel overseas and allied militaries also sent in reports.</p>
  <ul class="cols">{links(other)}</ul>
  <p class="small">{len(by_region.get('unknown', [])):,} folders have no readable place (marked “[Blank]” or “[Illegible]” on the original). <a href="{url('/ufo/blue-book/unknown/')}">See them here</a>.</p>
  <h2>About these files</h2>
  <p>Each link opens the case folder in the National Archives catalog, where you can read the scanned pages: witness forms, teletype messages, sketches and the Air Force's conclusion. Names of witnesses were blacked out before release. Most cases were explained as aircraft, balloons, stars or planets. 701 stayed “unidentified”.</p>
</div></div>'''
    write('/ufo/', page('/ufo/', 'Project Blue Book UFO files by state, year and map', body,
                        f'All {len(bluebook):,} US Air Force Project Blue Book UFO case files (1947-1969), mapped and listed by state and country.'))
    for k, cases in by_region.items():
        cases = sorted(cases, key=lambda b: (b['year'] or 0, b['month'] or 0))
        nm = names[k] if k != 'unknown' else 'Place unclear or unreadable'
        ys = Counter(b['year'] for b in cases if b.get('year'))
        peak = f' The busiest year was {max(ys, key=ys.get)}, with {max(ys.values())} reports.' if ys else ''
        items = ''.join(case_line(b) for b in cases)
        body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/ufo/')}">UFO files</a> / Project Blue Book</p>
  <h1>UFO sightings in {esc(nm)}: Air Force files</h1>
  <p class="lede">{len(cases):,} Project Blue Book case {'file' if len(cases) == 1 else 'files'} from {esc(nm)}, 1947 to 1969.{peak}</p>
  <p><a class="btn" href="{url('/map/')}">See them on the map</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <ol class="timeline cases">{items}</ol>
  <p class="small">Links open the original folder at the US National Archives.</p>
</div></div>'''
        write(f'/ufo/blue-book/{k}/', page(f'/ufo/blue-book/{k}/', f'UFO sightings in {nm}: {len(cases):,} Air Force Blue Book files',
                                           body, f'{len(cases):,} US Air Force Project Blue Book UFO case files from {nm}, with dates, places and links to the scanned originals.'))


def build_map_data(bluebook):
    """Compact GeoJSON for the map. Approximate (state/country-level) points get a small, stable
    jitter so they don't stack into one dot."""
    feats = []
    for i, b in enumerate(bluebook):
        if b.get('lat') is None:
            continue
        lat, lon = b['lat'], b['lon']
        if b['precision'] in ('region', 'country'):
            r = 0.6 if b['precision'] == 'region' else 1.5
            h = (b['id'] * 2654435761) % 2**32
            lat += ((h & 0xffff) / 0xffff - 0.5) * r
            lon += ((h >> 16) / 0xffff - 0.5) * r * 1.3
        when = f'{MONTHS[b["month"]][:3]} {b["year"]}' if b.get('month') and b.get('year') else (b.get('year') or '')
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(lon, 3), round(lat, 3)]},
                      'properties': {'id': b['id'], 't': (b['place'] or b['region'] or '')[:60], 'r': b['region'] or '',
                                     'w': str(when), 'y': b.get('year') or 0, 'a': 1 if b['precision'] in ('region', 'country') else 0}})
    os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
    with open(os.path.join(OUT, 'data', 'bluebook.geojson'), 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'))
    return len(feats)


def build_layer_data(creatures, military):
    """Small GeoJSON layers for the map: famous creature cases and military encounters."""
    by_slug = {c['slug']: c for c in creatures}
    fam_path = os.path.join(ROOT, 'data', 'famous_geo.json')
    famous = json.load(open(fam_path)) if os.path.exists(fam_path) else []
    feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [f['lon'], f['lat']]},
              'properties': {'s': f['creature'], 'n': by_slug[f['creature']]['name'], 'c': f['cat'], 'i': by_slug[f['creature']]['icon'],
                             't': f['name'], 'y': f['year'], 'p': f['place']}}
             for f in famous if f['creature'] in by_slug]
    with open(os.path.join(OUT, 'data', 'famous.geojson'), 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': feats}, fh, separators=(',', ':'))
    mil = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [m['lon'], m['lat']]},
            'properties': {'t': m['name'], 'y': m['date'][:4], 'p': m['place'], 'b': m['branch']}}
           for m in military if 'lat' in m]
    with open(os.path.join(OUT, 'data', 'military.geojson'), 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': mil}, fh, separators=(',', ':'))


def build_military(military):
    items = ''
    for m in sorted(military, key=lambda m: m['date']):
        src = ''.join(f'<a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}</a>' for s in m.get('sources', []))
        items += (f'<li class="mil"><span class="yr">{esc(m["date"][:4])}</span><div><h3>{esc(m["name"])}</h3>'
                  f'<p class="muted">{esc(m["place"])} · {esc(m["branch"])}</p><p>{esc(m["summary"])}</p>'
                  f'{f"<p class=src>Sources: {src}</p>" if src else ""}</div></li>')
    body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb">Military</p>
  <h1>Military encounters</h1>
  <p class="lede">Pilots, radar operators and soldiers have reported some of the strangest things on record, and the military has kept files on them since the 1940s.</p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <p>The Air Force's own Project Blue Book alone holds {10622:,} case files. <a href="{url('/ufo/')}">Browse them by state</a>. Below are the military cases people still talk about.</p>
  <ol class="timeline mil-list">{items}</ol>
</div></div>'''
    write('/military/', page('/military/', 'Military UFO and creature encounters', body,
                             'The most famous military UFO and UAP encounters, from WWII foo fighters to the Navy Tic Tac, with official sources.'))


def build_home(creatures, n_points, bluebook):
    featured = [c for c in creatures if c['slug'] in ('bigfoot', 'dogman', 'mothman', 'loch-ness-monster', 'chupacabra',
                                                       'ufo-tic-tac', 'jersey-devil', 'flatwoods-monster')]
    cards = ''.join(creature_card(c) for c in featured)
    head = (f'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
            f'<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
            f'<script src="{url("/static/map.js")}" defer></script>')
    body = f'''
<section class="hero-map" aria-label="Map of encounters">
  <div id="map" class="map" data-base="{BASE}"></div>
  <div class="map-panel">
    <h1>Every strange thing, on one map</h1>
    <p>{n_points:,} Air Force UFO files are pinned so far. Bigfoot, Dogman and the rest are next, with your reports.</p>
    <div class="map-actions">
      <button type="button" class="btn" data-locate>Show what's near me</button>
      <a class="btn btn-ghost" href="{url('/creatures/')}">Browse creatures</a>
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <h2>Meet the locals</h2>
  <p class="lede-dark">Every creature has its other names, what witnesses report and the cases that made it famous.</p>
  <div class="crit-grid">{cards}</div>
  <p><a href="{url('/creatures/')}">See all {len(creatures)} creatures</a></p>
</div></div>
<div class="band band-dark"><div class="wrap split">
  <div>
    {icon('folder', 'ico ico-lg')}
    <h2>The Air Force kept files</h2>
    <p>Project Blue Book collected {len(bluebook):,} UFO reports between 1947 and 1969. Find the ones from your state, read the original scans, and see where they cluster.</p>
    <p><a class="btn" href="{url('/ufo/')}">Open the UFO files</a></p>
  </div>
  <div>
    {icon('military', 'ico ico-lg')}
    <h2>Military encounters</h2>
    <p>Foo fighters over Germany, radar returns over the White House, a Tic Tac off San Diego. The cases pilots and soldiers reported.</p>
    <p><a class="btn" href="{url('/military/')}">Read the cases</a></p>
  </div>
</div></div>'''
    write('/', page('/', 'Encounter Atlas: Bigfoot, UFO and cryptid sightings mapped', body,
                    'A map of Bigfoot, Dogman, UFO and cryptid encounters, a searchable creature index, and the US Air Force Project Blue Book files.',
                    body_class='home', head_extra=head))
    write('/map/', page('/map/', 'Encounter map', f'''
<section class="hero-map full" aria-label="Map of encounters">
  <div id="map" class="map" data-base="{BASE}"></div>
  <div class="map-panel compact">
    <h1>Encounter map</h1>
    <p>{n_points:,} Air Force UFO files (1947 to 1969). Tap a dot for the case.</p>
    <button type="button" class="btn" data-locate>Near me</button>
  </div>
</section>''', 'Map of UFO and cryptid encounters, including every US Air Force Project Blue Book case.', body_class='home mapper', head_extra=head))


def build_static_pages():
    write('/report/', page('/report/', 'Report an encounter', f'''
<section class="band band-dark"><div class="wrap">
  <h1>Report an encounter</h1>
  <p class="lede">Saw something you can't explain? The report form is being built now and opens soon, with photo and video uploads and a pin on the map.</p>
</div></section>
<div class="band band-mist"><div class="wrap prose">
  <h2>What to write down now, while it's fresh</h2>
  <ul class="signs">
    <li>Date, time and how long it lasted</li>
    <li>Exactly where you were, and where it was from you</li>
    <li>Size, shape, colour and how it moved</li>
    <li>Sounds and smells</li>
    <li>Weather and light: moon, clouds, headlights</li>
    <li>Who else saw it</li>
  </ul>
  <p>Take photos of tracks with something for scale, like a boot or a phone. Don't post your exact location publicly if it's private land.</p>
</div></div>''', 'Report a Bigfoot, Dogman, UFO or other strange encounter.'))
    write('/about/', page('/about/', 'About and sources', f'''
<section class="band band-dark"><div class="wrap"><h1>About Encounter Atlas</h1>
<p class="lede">One place for strange sightings: creatures, UFOs and the official files, mapped and searchable.</p></div></section>
<div class="band band-mist"><div class="wrap prose">
<h2>Sources</h2>
<ul>
<li><strong>Project Blue Book case files</strong>, US Air Force, 1947 to 1969. US National Archives, Record Group 341, microfilm T1206. US federal records, no copyright in the United States. Places were matched automatically from the folder titles; dots marked “approximate” are placed at the state or country, not the exact spot.</li>
<li><strong>Place names</strong>: GeoNames, licensed CC BY 4.0.</li>
<li><strong>Map tiles</strong>: OpenFreeMap, built on OpenMapTiles and OpenStreetMap data.</li>
<li><strong>Creature entries</strong> are written by us from published accounts. Each links to further reading.</li>
</ul>
<h2>Our stance</h2>
<p>We collect reports and evidence and let you decide. A report on this site means someone said they saw something, not that it's proven.</p>
</div></div>''', 'Sources and approach behind Encounter Atlas.'))
    write('/404.html', page('/404.html', 'Page not found', f'''
<section class="band band-dark"><div class="wrap"><h1>Nothing out here</h1>
<p class="lede">That page doesn't exist, or it wandered off into the woods.</p>
<p><a class="btn" href="{url('/')}">Back to the map</a></p></div></section>''', canonical=False))


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(STATIC, os.path.join(OUT, 'static'))
    creatures = json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))
    by_slug = {c['slug']: c for c in creatures}
    bad = [(c['slug'], r) for c in creatures for r in c['related'] if r not in by_slug]
    if bad:
        print('unknown related slugs:', bad, file=sys.stderr)
    bluebook = json.load(open(os.path.join(ROOT, 'data', 'bluebook.json')))
    mil_path = os.path.join(ROOT, 'data', 'military.json')
    military = json.load(open(mil_path)) if os.path.exists(mil_path) else []
    n_points = build_map_data(bluebook)
    build_layer_data(creatures, military)
    build_home(creatures, n_points, bluebook)
    build_creatures(creatures, by_slug)
    build_ufo(bluebook)
    build_military(military)
    build_static_pages()
    # Each site/sections/*.py module owns one part of the site (places, podcasts, ...) and exposes
    # build(ctx). ctx gives it the shared helpers and loaded data, so sections never edit this file.
    import importlib.util, types
    ctx = types.SimpleNamespace(ROOT=ROOT, OUT=OUT, STATIC=STATIC, SITE_URL=SITE_URL, BASE=BASE, page=page, write=write,
                                url=url, esc=esc, icon=icon, slugify=slugify, badge=badge, creature_card=creature_card,
                                creatures=creatures, by_slug=by_slug, bluebook=bluebook, military=military, CATS=CATS, MONTHS=MONTHS)
    sec_dir = os.path.join(ROOT, 'site', 'sections')
    for fn in sorted(os.listdir(sec_dir)) if os.path.isdir(sec_dir) else []:
        if fn.endswith('.py') and not fn.startswith('_'):
            spec = importlib.util.spec_from_file_location('sec_' + fn[:-3], os.path.join(sec_dir, fn))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.build(ctx)
    with open(os.path.join(OUT, 'manifest.webmanifest'), 'w') as f:
        json.dump({'name': 'Encounter Atlas', 'short_name': 'Encounters', 'start_url': BASE + '/map/', 'display': 'standalone',
                   'background_color': '#13261F', 'theme_color': '#13261F',
                   'icons': [{'src': BASE + '/static/favicon.svg', 'sizes': 'any', 'type': 'image/svg+xml'}]}, f)
    if BASE == '':
        open(os.path.join(OUT, 'CNAME'), 'w').write(SITE_URL.split('//')[1] + '\n')
    pages = []
    for d, _, files in os.walk(OUT):
        for fn in files:
            if fn == 'index.html':
                pages.append('/' + os.path.relpath(d, OUT).replace('.', '').strip('/') + '/')
    pages = sorted(p.replace('//', '/') for p in pages)
    with open(os.path.join(OUT, 'sitemap.xml'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.writelines(f'<url><loc>{SITE_URL}{p}</loc></url>\n' for p in pages)
        f.write('</urlset>\n')
    with open(os.path.join(OUT, 'robots.txt'), 'w') as f:
        f.write(f'User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n')
    print(f'built {len(pages)} pages, {n_points:,} map points', file=sys.stderr)


if __name__ == '__main__':
    main()

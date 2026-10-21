"""/near-me/: sightings near you. A normal indexable page AND the app's home screen (the PWA and the Play Store
Trusted Web Activity both open here), so it is mobile-first, full-bleed with safe-area padding, and works with no
browser bar.

Named z_near_me.py so it runs after the sections that write the map GeoJSON it tiles (ufo_canada.py etc.).

At load (full HTML, no JS needed): intro, the 30 latest approved reader reports as cards (fetched from the Worker at
build time, like the newsletter does), region hub chips, report and email CTAs, sources.
static/nearme.js acts only when a control is used: "Use my location", "Pick a place" (static/data/cities.json, no
outside geocoder), radius (km or miles), category and time chips. Then the map shows reader reports from the
Worker's /v1/reports/nearby plus the archive layers from data/near/<lat0>_<lon0>.json (5-degree tiles).
"""
import datetime, json, os, re, sys, urllib.request

API = os.environ.get('EA_API', 'https://api.encounteratlas.com').rstrip('/')
MAPLIBRE = '4.7.1'
RADII_KM = [10, 25, 50, 100, 250]
RADII_MI = [5, 15, 30, 60, 150]   # sent as km (8, 24, 48, 97, 241)
DAYS = [(7, 'Past week'), (30, 'Past month'), (90, 'Past 3 months'), (365, 'Past year')]
CATS = [('', 'Everything'), ('ufo', 'UFOs'), ('creature', 'Creatures'), ('other', 'Something else')]


def latest_reports(n=30):
    try:
        req = urllib.request.Request(f'{API}/api/reports?limit={n}', headers={'user-agent': 'EncounterAtlasBuild/1.0 (+https://encounteratlas.com)'})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r).get('reports', [])[:n]
    except Exception as err:
        print(f'near-me: reader reports skipped: {err!r}')
        return []


def nice_date(d):
    try:
        x = datetime.date.fromisoformat(d)
        return x.strftime('%B %-d, %Y')
    except Exception:
        return d or ''


def build(ctx):
    E, U = ctx.esc, ctx.url
    sys.path.insert(0, os.path.join(ctx.ROOT, 'tools'))
    from near_me_tiles import build_tiles, LAYERS
    n_tiles, counts = build_tiles(os.path.join(ctx.OUT, 'data'), os.path.join(ctx.OUT, 'data', 'near'))
    print(f'near-me: {n_tiles} archive tiles, {sum(counts.values()):,} points')

    # ---- latest reader reports (static cards) ----
    reports = latest_reports()
    cards = []
    for r in reports:
        c = ctx.by_slug.get(r.get('creature'))
        what = r.get('creature_name') or r.get('other_what') or 'Something strange'
        badge = ctx.badge(c, 'sm') if c else '<span class="badge badge-sm cat-other"><span class="q" aria-hidden="true">?</span></span>'
        cat = c['cat'] if c else 'other'
        where = r.get('place') or ''
        cards.append(
            f'<li class="nm-card cat-{cat}"><a href="{U("/reports/?id=" + r["id"])}">{badge}<span class="nm-card-body">'
            f'<b>{E(what)}</b><span class="nm-meta">{E(where + " · " if where else "")}{E(nice_date(r.get("seen_date")))}'
            f'{" (about)" if r.get("date_approx") else ""}</span>'
            f'<span class="nm-snip">{E(r.get("snippet") or "")}</span></span></a></li>')
    latest = (f'<ul class="nm-cards" data-area="latest-reports">{"".join(cards)}</ul>' if cards else
              f'<p class="nm-none">No reader reports yet. <a href="{U("/report/")}">Be the first to report one</a>.</p>')

    # ---- region hubs ----
    regions = getattr(ctx, 'regions', {}) or {}
    ca = sorted((v for k, v in regions.items() if k.startswith('CA.')), key=lambda x: x[1])
    us = sorted((v for k, v in regions.items() if k.startswith('US.')), key=lambda x: x[1])
    chip = lambda p, n: f'<a class="nm-chip" href="{U(p)}">{E(n)}</a>'
    world = [('/ufo/countries/', 'UFO files by country'), ('/ufo/cases/', 'Famous UFO cases worldwide'), ('/places/', 'Places to visit'),
             ('/history/', 'Old newspaper stories'), ('/map/', 'The full world map')]
    hubs = (f'<div class="nm-hubs" data-area="region-hubs">'
            f'<h3>Around the world</h3><p class="nm-chips">{"".join(chip(p, n) for p, n in world)}</p>'
            f'<h3>Canada</h3><p class="nm-chips">{chip("/canada/", "All of Canada")}{"".join(chip(p, n) for p, n in ca)}</p>'
            f'<h3>United States</h3><p class="nm-chips">{chip("/us/", "All states")}{"".join(chip(p, n) for p, n in us)}</p></div>')

    radius = ''.join(f'<button type="button" class="nm-opt" data-km="{k}" data-mi="{m}" aria-pressed="{"true" if k == 50 else "false"}">'
                     f'<span class="u-km">{k} km</span><span class="u-mi" hidden>{m} mi</span></button>' for k, m in zip(RADII_KM, RADII_MI))
    cats = ''.join(f'<button type="button" class="nm-opt{" cat-" + c if c else ""}" data-cat="{c}" aria-pressed="{"true" if not c else "false"}">{E(n)}</button>'
                   for c, n in CATS)
    days = ''.join(f'<button type="button" class="nm-opt" data-days="{d}" aria-pressed="{"true" if d == 30 else "false"}">{E(n)}</button>' for d, n in DAYS)
    total = sum(counts.values())
    # For the fallback to /api/reports.geojson (nearme.js fromFeed): UFO slugs for the category filter, and the
    # Worker's LIVING_TRADITIONS (read from its source, the list that decides the ~100 km public point).
    worker_src = open(os.path.join(ctx.ROOT, 'worker', 'src', 'index.js'), encoding='utf-8').read()
    living = re.findall(r"'([a-z0-9-]+)'", re.search(r'LIVING_TRADITIONS = new Set\(\[(.*?)\]\)', worker_src, re.S).group(1))
    cfg = json.dumps({'api': API, 'base': ctx.BASE, 'tiles': U('/data/near/'), 'cities': U('/data/cities.json'),
                      'report': U('/report/'), 'reports': U('/reports/?id='),
                      'ufo': [c['slug'] for c in ctx.creatures if c['cat'] == 'ufo'], 'living': living},
                     separators=(',', ':')).replace('</', '<\\/')
    sources = ''.join(f'<li><b>{E(t)}</b> ({counts[k]:,} on this map). {E(s.split(" Credit by name")[0].split(" Rows from")[0])}</li>'
                      for k, (_, t, s) in LAYERS.items() if k != 'bluebook_approx')

    body = f'''
<section class="nm-hero" data-area="near-me-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/')}">Home</a> / Near me</p>
    <h1>UFO and cryptid sightings near me</h1>
    <p class="lede">See what people have reported around you: Bigfoot, Dogman, lake monsters, strange lights and UFOs. Use your location or pick a
    town anywhere in the world. You'll get reader reports from the last few weeks, plus {total:,} official UFO files and survey sightings from the archives.</p>
    <p class="nm-install" id="nm-install" hidden><button type="button" class="btn btn-ghost" id="nm-install-btn">Install the app</button>
      <span>Opens straight to this page, full screen, and works with a weak signal.</span></p>
    <p class="nm-install nm-ios" id="nm-ios" hidden>On iPhone: tap Share, then <b>Add to Home Screen</b> to keep this as an app.</p>
  </div>
</section>
<section class="nm-tool" data-area="near-me-tool" aria-label="Search near a place">
  <div class="wrap">
    <div class="nm-where">
      <button type="button" class="btn nm-locate" id="nm-locate"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="currentColor"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/></svg><span>Use my location</span></button>
      <form class="nm-pick" id="nm-pick" role="search" onsubmit="return false">
        <label for="nm-place" class="nm-label">Or pick a place</label>
        <div class="nm-pick-row"><input type="text" id="nm-place" list="nm-cities" placeholder="Town or city" autocomplete="off" enterkeyhint="search">
        <datalist id="nm-cities"></datalist><button type="submit" class="btn btn-ghost nm-go">Go</button></div>
      </form>
    </div>
    <p class="nm-status" id="nm-status" role="status" aria-live="polite"></p>
    <div class="nm-filters">
      <div class="nm-row" role="group" aria-label="How far">
        <span class="nm-row-h">How far</span><div class="nm-opts" id="nm-radius">{radius}</div>
        <button type="button" class="nm-unit" id="nm-unit" aria-pressed="false">Show miles</button>
      </div>
      <div class="nm-row" role="group" aria-label="What"><span class="nm-row-h">What</span><div class="nm-opts" id="nm-cat">{cats}</div></div>
      <div class="nm-row" role="group" aria-label="When"><span class="nm-row-h">When</span><div class="nm-opts" id="nm-days">{days}</div></div>
    </div>
  </div>
  <div class="nm-mapwrap" id="nm-mapwrap" hidden>
    <div id="nm-map" class="nm-map" aria-label="Map of sightings near the chosen place"></div>
    <p class="nm-legend"><span class="lg lg-rep">Reader reports</span><span class="lg lg-bb">Air Force files</span><span class="lg lg-ring">Area only (faded ring)</span><span class="lg lg-faa">FAA pilot reports</span><span class="lg lg-pur">Pentagon files</span><span class="lg lg-ca">Canadian UFO Survey</span></p>
  </div>
  <div class="wrap"><div class="nm-results" id="nm-results" aria-live="polite"></div></div>
</section>
<section class="band band-mist" data-area="latest">
  <div class="wrap">
    <h2>Latest reader reports</h2>
    <p class="lede-dark">The newest encounters our readers sent in, checked by a person before they go up. Locations are shown to about 5 km so nobody's home is on the map.</p>
    {latest}
    <p class="nm-cta"><a class="btn" href="{U('/report/')}">Report an encounter</a> <a class="btn btn-quiet" href="{U('/reports/')}">All reader reports</a></p>
  </div>
</section>
<section class="band band-dark" data-area="hubs">
  <div class="wrap">
    <h2>Browse by area</h2>
    <p class="lede">Every state, province and country we have files for, with its creatures, famous cases, UFO files and places to visit.</p>
    {hubs}
  </div>
</section>
<section class="band band-mist" data-area="alerts">
  <div class="wrap nm-alerts">
    {ctx.signup_box('near-me', 'New sightings in your inbox', 'One short email every Thursday with the newest reader reports and strange stories from around the world. Free.')}
  </div>
</section>
<section class="band band-mist nm-about" data-area="about">
  <div class="wrap">
    <h2>What's on this map</h2>
    <ul class="nm-src">
      <li><b>Reader reports</b>. Sent in through our report form and read by a person before they go up. Shown to about 5 km. Reports about creatures from living Indigenous and local traditions are shown only to the nearest region, about 100 km.</li>
      {sources}
    </ul>
    <p>Air Force files that only name a state or country are drawn as a faded ring over that area, never as a pin. Archive files come from every year; the time buttons apply to reader reports.</p>
    <p><b>Your location stays yours.</b> We round it to about 1 km before searching and don't save it. Picking a place uses a town list on this site, not an outside service.</p>
  </div>
</section>
<script type="application/json" id="nm-config">{cfg}</script>'''

    head = (f'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/{MAPLIBRE}/maplibre-gl.min.css">'
            f'<link rel="stylesheet" href="{U("/static/nearme.css")}">'
            f'<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/{MAPLIBRE}/maplibre-gl.min.js" defer></script>'
            f'<script src="{U("/static/nearme.js")}" defer></script>')
    ctx.write('/near-me/', ctx.page('/near-me/', 'UFO and cryptid sightings near me', body,
                                    'See UFO, Bigfoot and cryptid sightings near you: recent reader reports plus Air Force, FAA and Canadian UFO Survey files, anywhere in the world.',
                                    body_class='nearme', head_extra=head, viewport_fit=True))

    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if os.path.exists(sp):
        items = json.load(open(sp, encoding='utf-8'))
        items.append({'t': 'Sightings near me', 'a': 'near me nearby local my area around me map location', 'k': 'Reports and UFO files around you',
                      'u': U('/near-me/'), 'i': 'saucer', 'c': 'ufo'})
        json.dump(items, open(sp, 'w', encoding='utf-8'), separators=(',', ':'))

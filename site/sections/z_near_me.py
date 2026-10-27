"""/near-me/: sightings near you. A normal indexable page AND the app's home screen (the PWA and the Play Store
Trusted Web Activity both open here), so it is mobile-first, full-bleed with safe-area padding, and works with no
browser bar.

Named z_near_me.py so it runs after the sections that write the map GeoJSON it tiles (ufo_canada.py etc.).

At load (full HTML, no JS needed): intro, the 30 latest approved reader reports as cards (fetched from the Worker at
build time, like the newsletter does), region hub chips, report and email CTAs, sources.
static/nearme.js acts only when a control is used: "Use my location", "Pick a place" (static/data/cities.json, no
outside geocoder), radius (km or miles), category and time chips. Then the map shows reader reports from the
Worker's /v1/reports/nearby plus the archive layers from data/near/<lat0>_<lon0>.json (5-degree tiles).

Also here (2026-10-24):
- App hub: a row of big icon buttons to the app's other features (plain links, no JS).
- Then and now: an era slider plus era buttons (old newspapers, Blue Book, Canadian UFO Survey, FAA, PURSUE, reader
  reports) that filter the map and list, with a count per era. Old newspaper stories come from /data/historic.geojson
  (written by historic.py), loaded only when a search runs.
- Flap in progress: the Worker's /v1/clusters (3+ approved reports within 50 km in 3 days). The build asks the API
  once; until the endpoint answers, the page never calls it (no 404s in the console), and any failure stays silent.
"""
import datetime, json, os, re, sys, urllib.request

API = os.environ.get('EA_API', 'https://api.encounteratlas.com').rstrip('/')
MAPLIBRE = '4.7.1'
RADII_KM = [10, 25, 50, 100, 250]
RADII_MI = [5, 15, 30, 60, 150]   # sent as km (8, 24, 48, 97, 241)
DAYS = [(7, 'Past week'), (30, 'Past month'), (90, 'Past 3 months'), (365, 'Past year')]
CATS = [('', 'Everything'), ('ufo', 'UFOs'), ('creature', 'Creatures'), ('other', 'Something else')]
# Then and now. src = layers in the era; years = dated archive files from other layers (the Greek cases) join by year.
ERAS = [
    {'id': 'all', 'name': 'Every era', 'span': '1800s to today'},
    {'id': 'papers', 'name': 'Old newspapers', 'span': '1800s to 1920s', 'src': ['historic'], 'years': [1700, 1929]},
    {'id': 'bluebook', 'name': 'Project Blue Book', 'span': '1947 to 1969', 'src': ['bluebook', 'bluebook_approx'], 'years': [1947, 1969]},
    {'id': 'canada', 'name': 'Canadian UFO Survey', 'span': '1989 to 2025', 'src': ['canada'], 'years': [1989, 2025]},
    {'id': 'faa', 'name': 'FAA pilot reports', 'span': '2007 to 2024', 'src': ['faa']},
    {'id': 'pursue', 'name': 'PURSUE files', 'span': 'released 2026', 'src': ['pursue']},
    {'id': 'today', 'name': 'Reader reports', 'span': 'today', 'src': ['reports']},
]
# App hub: (path, label, icon, tone)
HUB = [('/road-trip/', 'Road trip', 'roadside', 'road'), ('/cards/', 'Collector cards', 'bigfoot', 'cards'),
       ('/tools/skywatch/', "Tonight's sky", 'telescope', 'sky'), ('/stories/campfire/', 'Campfire stories', 'campfire', 'fire'),
       ('/journal/', 'Field journal', 'clipboard', 'journal'), ('/map/', 'Full map', 'ufo-globe', 'map'),
       ('/podcasts/', 'Podcasts', 'headphones', 'pod'),
       ('/report/', 'Report a sighting', 'ufo-report', 'report')]


# Headphones for the podcast tile, same flat white style.
HEADPHONES = ('<svg class="ico" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
              '<path d="M32 8C18 8 8 19 8 33v13h6V33c0-10.5 7.9-19 18-19s18 8.5 18 19v13h6V33C56 19 46 8 32 8z"/>'
              '<rect x="8" y="36" width="14" height="22" rx="5"/><rect x="42" y="36" width="14" height="22" rx="5"/></svg>')


# The icon set has no campfire, so this one is drawn here in the same flat white style.
CAMPFIRE = ('<svg class="ico" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
            '<path d="M32 4c3 9 13 14 13 27a13 13 0 0 1-26 0c0-7 4-11 6-15 1 5 3 7 5 8-1-8 0-14 2-20z"/>'
            '<path d="M32 26c2 5 7 8 7 14a7 7 0 0 1-14 0c0-4 2-6 4-9 0 3 1 4 2 5 0-4 0-7 1-10z" fill="#C0582A"/>'
            '<path d="M8 50l46 10 2-6-46-10zM56 50 10 60l-2-6 46-10z"/></svg>')


def clusters_live():
    """True when the Worker answers /v1/clusters (deployed). EA_CLUSTERS=1/0 forces it for local tests."""
    force = os.environ.get('EA_CLUSTERS')
    if force in ('0', '1'):
        return force == '1'
    try:
        req = urllib.request.Request(f'{API}/v1/clusters?lat=0&lng=0', headers={'user-agent': 'EncounterAtlasBuild/1.0 (+https://encounteratlas.com)'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200 and 'clusters' in json.load(r)
    except Exception:
        return False


def latest_reports(n=30):
    try:
        req = urllib.request.Request(f'{API}/api/reports?limit={n}', headers={'user-agent': 'EncounterAtlasBuild/1.0 (+https://encounteratlas.com)'})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r).get('reports', [])[:n]
    except Exception as err:
        print(f'near-me: reader reports skipped: {err!r}')
        return []


SYNODIC = 29.530588853
NEW_MOON = datetime.datetime(2000, 1, 6, 18, 14, tzinfo=datetime.timezone.utc)  # a known new moon
MOON_NAMES = [(.03, 'New moon'), (.22, 'Waxing crescent'), (.28, 'First quarter'), (.47, 'Waxing gibbous'), (.53, 'Full moon'),
              (.72, 'Waning gibbous'), (.78, 'Last quarter'), (.97, 'Waning crescent'), (1.01, 'New moon')]


def moon(when):
    """(phase 0..1 with 0 = new, fraction lit, name). nearme.js has the same sums for the visitor's own clock."""
    import math
    p = ((when - NEW_MOON).total_seconds() / 86400 / SYNODIC) % 1
    lit = (1 - math.cos(2 * math.pi * p)) / 2
    return p, lit, next(n for lim, n in MOON_NAMES if p < lim)


def moon_svg(p):
    """The lit part of the moon as an SVG path on a radius-20 disc centred at 24,24 (mirrored in nearme.js moonPath)."""
    import math
    rx = abs(math.cos(2 * math.pi * p)) * 20
    if p < .5:
        outer, inner = 1, (0 if p < .25 else 1)
    else:
        outer, inner = 0, (0 if p < .75 else 1)
    return f'M24 4A20 20 0 0 {outer} 24 44A{rx:.2f} 20 0 0 {inner} 24 4Z'


def moon_note(lit):
    return ('Dark sky, good for spotting lights' if lit < .35 else
            'Bright moon, faint stuff hides' if lit > .85 else f'{round(lit * 100)}% lit')


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
        # reports.py's coarse place (no street addresses, region only for living traditions) when it has one
        where = getattr(ctx, 'report_where', {}).get(r['id'], r.get('place') or '')
        cards.append(
            f'<li class="nm-card cat-{cat}"><a href="{U("/reports/" + r["id"] + "/")}">{badge}<span class="nm-card-body">'
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
    # Web Push public key: the Worker's wrangler.toml is the one place it lives.
    toml = open(os.path.join(ctx.ROOT, 'worker', 'wrangler.toml'), encoding='utf-8').read()
    vm = re.search(r'^VAPID_PUBLIC\s*=\s*"([A-Za-z0-9_-]+)"', toml, re.M)
    # Old newspaper stories: historic.py's topic pages hold each story (#h-<id>).
    try:
        sys.path.insert(0, os.path.join(ctx.ROOT, 'site', 'sections'))
        from historic import TOPICS as HTOPICS
        hist_topics = {k: U('/history/' + v[0] + '/') for k, v in HTOPICS.items()}
    except Exception:
        hist_topics = {}
    # Hub tiles; nearme.js fills the badges from what's already on the device (collected cards, a podcast to resume)
    badge = lambda t: f'<span class="nm-badge" data-badge="{t}" hidden></span>' if t in ('cards', 'pod') else ''
    hub = ''.join(f'<li style="--i:{i}"><a class="nm-app tone-{t}" href="{U(p)}"><span class="nm-app-ico">{CAMPFIRE if ic == "campfire" else HEADPHONES if ic == "headphones" else ctx.icon(ic)}'
                  f'{badge(t)}</span>'
                  f'<span class="nm-app-name">{E(n)}</span></a></li>' for i, (p, n, ic, t) in enumerate(HUB))
    n_cards = len([f for f in os.listdir(os.path.join(ctx.ROOT, 'site', 'static', 'cards', 'art')) if f.endswith('.webp')]) \
        if os.path.isdir(os.path.join(ctx.ROOT, 'site', 'static', 'cards', 'art')) else 0

    # "At a glance": tonight's moon (build day here, the visitor's clock in nearme.js) and the mystery of the day.
    # motd.py ran first and wrote /data/motd.json; the next 8 UTC days go in the config so the tile stays right
    # between builds.
    mp, mlit, mname = moon(datetime.datetime.now(datetime.timezone.utc))
    motd_days, motd_html = {}, ''
    try:
        mj = json.load(open(os.path.join(ctx.OUT, 'data', 'motd.json'), encoding='utf-8'))
        today = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.date(1970, 1, 1)).days
        for d in range(today, today + 8):
            era = None
            for e in mj['eras']:
                if e['from'] <= d:
                    era = e
            if era and era['order']:
                c = mj['cases'].get(era['order'][(d - era['from']) % len(era['order'])])
                if c:
                    motd_days[d] = [c['n'], U(c['u'])]
        if today in motd_days:
            motd_html = (f'<a class="nm-gl nm-gl-motd" href="{U("/mystery-of-the-day/")}"><span class="nm-gl-ico nm-gl-q" aria-hidden="true">?</span>'
                         f'<span class="nm-gl-t"><small>Mystery of the day</small><b id="nm-motd">{E(motd_days[today][0])}</b>'
                         f'<span class="nm-gl-sub">What do you think it was?</span></span></a>')
    except (OSError, ValueError, KeyError) as err:
        print(f'near-me: mystery of the day tile skipped: {err!r}')
    glance = (f'<div class="nm-glance">'
              f'<a class="nm-gl nm-gl-moon" href="{U("/tools/skywatch/")}"><svg class="nm-gl-ico nm-moon" viewBox="0 0 48 48" aria-hidden="true">'
              f'<circle cx="24" cy="24" r="20" fill="#2A3B36"/><path id="nm-moon-lit" d="{moon_svg(mp)}" fill="#F3E3B8"/></svg>'
              f'<span class="nm-gl-t"><small>Tonight\'s sky</small><b id="nm-moon-name">{E(mname)}</b>'
              f'<span class="nm-gl-sub" id="nm-moon-note">{E(moon_note(mlit))}</span></span></a>{motd_html}</div>')
    sys.path.insert(0, os.path.join(ctx.ROOT, 'site', 'sections'))
    import _podplay
    listen = _podplay.todays_listen(ctx, 'near')
    flap_on = clusters_live()
    print(f'near-me: flap card {"on" if flap_on else "off (the Worker has no /v1/clusters yet)"}')
    cfg = json.dumps({'api': API, 'base': ctx.BASE, 'vapid': vm.group(1) if vm else '',
                      'sitekey': os.environ.get('TURNSTILE_SITEKEY', '1x00000000000000000000AA'), 'tiles': U('/data/near/'), 'cities': U('/data/cities.json'),
                      'report': U('/report/'), 'reports': U('/reports/'),
                      'ufo': [c['slug'] for c in ctx.creatures if c['cat'] == 'ufo'], 'living': living,
                      'historic': U('/data/historic.geojson'), 'htopics': hist_topics,
                      'eras': [{k: e[k] for k in ('id', 'name', 'span', 'src', 'years') if k in e} for e in ERAS], 'clusters': flap_on,
                      'motd': motd_days, 'cards_total': n_cards},
                     separators=(',', ':')).replace('</', '<\\/')
    era_btns = ''.join(f'<button type="button" class="nm-era" data-era="{e["id"]}" data-i="{i}" aria-pressed="{"true" if i == 0 else "false"}">'
                       f'<b>{E(e["name"])}</b><span class="nm-era-span">{E(e["span"])}</span><span class="nm-era-n"></span></button>'
                       for i, e in enumerate(ERAS))
    sources = ''.join(f'<li><b>{E(t)}</b> ({counts[k]:,} on this map). {E(s.split(" Credit by name")[0].split(" Rows from")[0])}</li>'
                      for k, (_, t, s) in LAYERS.items() if k != 'bluebook_approx')

    body = f'''
<section class="nm-hero" data-area="near-me-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/')}">Home</a> / Near me</p>
    <p class="nm-hello" id="nm-hello" hidden></p>
    <h1>UFO and cryptid sightings near me</h1>
    <p class="lede">See what people have reported around you: Bigfoot, Dogman, lake monsters, strange lights and UFOs. Use your location or pick a
    town anywhere in the world. You'll get reader reports from the last few weeks, plus {total:,} official UFO files and survey sightings from the archives.</p>
    {glance}
    <nav class="nm-hub" aria-label="More in the app"><ul>{hub}</ul></nav>
    {listen}
    <p class="nm-play">{ctx.play_badge('near-me', 62)}<span>Get alerts for sightings near you in the Android app.</span></p>
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
    <div class="nm-flap-slot" id="nm-flap" aria-live="polite"></div>
    <div class="nm-alert" id="nm-alert" hidden>
      <button type="button" class="btn btn-ghost nm-alert-btn" id="nm-alert-btn">Alert me about new reports here</button>
      <p class="nm-alert-st" id="nm-alert-st" role="status" aria-live="polite"></p>
      <div class="nm-alert-ts" id="nm-alert-ts"></div>
    </div>
    <div class="nm-filters">
      <div class="nm-row" role="group" aria-label="How far">
        <span class="nm-row-h">How far</span><div class="nm-opts" id="nm-radius">{radius}</div>
        <button type="button" class="nm-unit" id="nm-unit" aria-pressed="false">Show miles</button>
      </div>
      <div class="nm-row" role="group" aria-label="What"><span class="nm-row-h">What</span><div class="nm-opts" id="nm-cat">{cats}</div></div>
      <div class="nm-row" role="group" aria-label="When (reader reports)"><span class="nm-row-h">When</span><div class="nm-opts" id="nm-days">{days}</div></div>
    </div>
    <fieldset class="nm-then" id="nm-then">
      <legend class="nm-row-h">Then and now</legend>
      <p class="nm-then-help">Slide back through time, from old newspaper stories to this month's reader reports. The map and the list show one era at a time.</p>
      <label class="nm-then-lab" for="nm-era-range">Era: <output id="nm-era-out" for="nm-era-range">{E(ERAS[0]["name"])}, {E(ERAS[0]["span"])}</output></label>
      <input type="range" id="nm-era-range" class="nm-era-range" min="0" max="{len(ERAS) - 1}" step="1" value="0" aria-valuetext="{E(ERAS[0]["name"])}, {E(ERAS[0]["span"])}">
      <div class="nm-eras" id="nm-eras" role="group" aria-label="Pick an era">{era_btns}</div>
      <p class="nm-era-st" id="nm-era-st" role="status" aria-live="polite"></p>
    </fieldset>
  </div>
  <div class="nm-mapwrap" id="nm-mapwrap" hidden>
    <div id="nm-map" class="nm-map" aria-label="Map of sightings near the chosen place"></div>
    <p class="nm-legend"><span class="lg lg-rep">Reader reports</span><span class="lg lg-bb">Air Force files</span><span class="lg lg-ring">Area only (faded ring)</span><span class="lg lg-faa">FAA pilot reports</span><span class="lg lg-pur">Pentagon files</span><span class="lg lg-ca">Canadian UFO Survey</span><span class="lg lg-gr">Greek close encounters</span><span class="lg lg-hi">Old newspaper stories</span></p>
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
    <div class="nm-push" id="alerts">
      <h2>Sighting alerts on your phone</h2>
      <p>Pick a place above, then tap <b>Alert me about new reports here</b>. When a moderator approves a new report inside your circle,
      your phone gets a notification, at most three a day. Alerts follow the place you saved, not where you are: we never track your location.
      You can change the place or turn alerts off from this page at any time.</p>
      <p class="nm-push-ios small">On iPhone, add this page to your Home Screen first (Share, then Add to Home Screen) and open it from there.</p>
    </div>
    {ctx.signup_box('near-me', 'New sightings in your inbox', 'One short email every Thursday with the newest reader reports and strange stories from around the world. Free.')}
  </div>
</section>
<section class="band band-mist nm-about" data-area="about">
  <div class="wrap">
    <h2>What's on this map</h2>
    <ul class="nm-src">
      <li><b>Reader reports</b>. Sent in through our report form and read by a person before they go up. Shown to about 5 km. Reports about creatures from living Indigenous and local traditions are shown only to the nearest region, about 100 km.</li>
      {sources}
      <li><b>Old newspaper stories</b> (1800s to 1920s). Wild men, sea serpents, airships and ghost lights from US and New Zealand papers, retold in our own words with a link to each original page. <a href="{U('/history/')}">See them all</a>.</li>
      <li><b>Flap in progress</b>. When three or more approved reader reports land within 50 km of each other in three days, the area gets a highlighted card. It only counts reports, it never shows where anyone lives, and creatures from living traditions are counted to the nearest region only.</li>
    </ul>
    <p>Air Force files that only name a state or country are drawn as a faded ring over that area, never as a pin. The Then and now slider picks an era; the When buttons apply to reader reports. Greek close encounters show up in the era that matches their year.</p>
    <p><b>Your location stays yours.</b> We round it to about 1 km before searching and don't save it. Picking a place uses a town list on this site, not an outside service.</p>
  </div>
</section>
<script type="application/json" id="nm-config">{cfg}</script>'''

    head = (f'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/{MAPLIBRE}/maplibre-gl.min.css">'
            f'<link rel="stylesheet" href="{U("/static/nearme.css")}">' + (_podplay.head(ctx) if listen else '') +
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

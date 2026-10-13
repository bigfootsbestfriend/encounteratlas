"""Builds the Encounter Atlas static site into _site/ (stdlib only).

Inputs: data/creatures.json (hand-written), data/bluebook.json (collector/bluebook.py),
data/military.json (hand-written). Output: plain HTML pages + a few JSON/GeoJSON files.
"""
import html, json, os, re, shutil, sys, urllib.parse
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
    'fae': ('Fairies and little people', 'Fae, pixies, hidden folk and little people from every continent'),
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


ICON_ART = json.load(open(os.path.join(ROOT, 'data', 'icon_art.json'))) if os.path.exists(os.path.join(ROOT, 'data', 'icon_art.json')) else {}


def tile_icon(name):
    """Tile icon with the silhouette scaled to a shared optical size (equal bounding-box area, never past the box)."""
    tag = icon(name)
    if name not in ICON_ART:
        return tag
    d = ' '.join(re.findall(r' d="([^"]+)"', open(os.path.join(STATIC, 'art', ICON_ART[name] + '.svg')).read()))
    n = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', d)]
    x0, x1, y0, y1 = min(n[0::2]), max(n[0::2]), min(n[1::2]), max(n[1::2])
    w, h = x1 - x0, y1 - y0
    k = min(560 / (w * h) ** .5, 790 / max(w, h))  # scale vs the 800 viewBox
    pos = lambda c: (.5 - c / 800 * k) / (1 - k) * 100 if abs(1 - k) > .01 else 50
    return tag.replace('" aria-hidden', f';--ms:{k * 100:.1f}%;--mx:{pos((x0 + x1) / 2):.1f}%;--my:{pos((y0 + y1) / 2):.1f}%" aria-hidden', 1)


def icon(name, cls='ico'):
    if name in ICON_ART:  # creature names draw the poster silhouette as a mask, so it takes the surrounding colour
        src = url('/static/art/' + ICON_ART[name] + '.svg')
        return f'<span class="{cls} art-ico" style="--m:url({src})" aria-hidden="true"></span>'
    svg = open(os.path.join(STATIC, 'icons', name + '.svg')).read().strip()
    return svg.replace('<svg ', f'<svg class="{cls}" aria-hidden="true" focusable="false" ', 1)


_CE = None


def story_url(creature_slug, year):
    """The full write-up for a famous case, if one exists (a close-encounters case page with that creature and year)."""
    global _CE
    if _CE is None:
        fp = os.path.join(ROOT, 'data', 'close_encounters.json')
        _CE = {}
        for x in (json.load(open(fp)) if os.path.exists(fp) else []):
            years = {x['year']} | ({1955, 1972} if x['slug'].startswith('loveland') else set())
            for cr in x.get('creatures', []):
                for y in years:
                    _CE.setdefault((cr, y), url('/encounters/' + x['slug'] + '/'))
                _CE.setdefault((cr, 'first'), (url('/encounters/' + x['slug'] + '/'), x['name']))
    return _CE.get((creature_slug, year), '')


def crit_icon(c, cls='ico'):
    """A creature's own poster silhouette as a colour-taking mask; falls back to its shared icon."""
    if c.get('art'):
        src = url('/static/' + c['art'] + '.svg')
        return f'<span class="{cls} art-ico" style="--m:url({src})" aria-hidden="true"></span>'
    return icon(c['icon'], cls)


_EXT_A = re.compile(r'<a\b(?![^>]*\btarget=)([^>]*\bhref="https?://(?!(?:www\.)?encounteratlas\.com)[^"]*"[^>]*)>')


def external_new_tab(html_text):
    """Every link to another site opens in a new tab, so readers keep their place here."""
    def fix(m):
        attrs = m.group(1)
        if 'rel="' in attrs:
            attrs = re.sub(r'rel="([^"]*)"', lambda r: 'rel="' + ' '.join(dict.fromkeys(r.group(1).split() + ['noopener'])) + '"', attrs)
        else:
            attrs += ' rel="noopener"'
        return f'<a{attrs} target="_blank">'
    return _EXT_A.sub(fix, html_text)


def write(path, text):
    full = os.path.join(OUT, path.lstrip('/'))
    if full.endswith('/'):
        full += 'index.html'
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(external_new_tab(text) if full.endswith('.html') else text)


EA_API = os.environ.get('EA_API', '').rstrip('/')  # report Worker; empty until it's deployed
MAP_API = f' data-api="{EA_API}"' if EA_API else ''
UFO_MENU = [('/ufo/', 'UFO sightings'), ('/ufo/canada/', 'Canada sightings map'), ('/ufo/blue-book/', 'Air Force Blue Book files'), ('/ufo/releases/', 'Official releases'),
            ('/ufo/countries/', 'UFO files by country'), ('/military/', 'Military encounters')]
RES_MENU = [('/places/', 'Places to visit'), ('/guides/', 'Field guides'), ('/gear/', 'Field gear'), ('/tools/', 'Tools'), ('/podcasts/', 'Podcasts')]
NAV = [('/map/', 'Map'), ('/creatures/', 'Creatures'), ('UFOs', UFO_MENU)] + ([('/reports/', 'Reports')] if EA_API else []) + [
    ('/encounters/', 'Encounters'), ('/mysteries/', 'Mysteries'), ('/history/', 'History'), ('Resources', RES_MENU)]


def nav_html(path):
    """Top nav; a (label, [links]) entry becomes a dropdown (<details>, so it works without JS)."""
    out = ''
    for p, n in NAV:
        if isinstance(n, list):
            on = any(path.startswith(q) for q, _ in n)
            links = ''.join(f'<a href="{url(q)}"{" aria-current=page" if path.startswith(q) and not any(path.startswith(r) and len(r) > len(q) for r, _ in n) else ""}>{esc(m)}</a>' for q, m in n)
            out += (f'<details class="nav-dd{" on" if on else ""}"><summary>{esc(p)}<svg viewBox="0 0 10 6" width="10" height="6" aria-hidden="true">'
                    f'<path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></summary><div class="dd-menu">{links}</div></details>')
        else:
            out += f'<a href="{url(p)}"{" aria-current=page" if path.startswith(p) else ""}>{esc(n)}</a>'
    return out


def page(path, title, body, desc='', body_class='', head_extra='', canonical=True):
    full_title = title if title.startswith('Encounter Atlas') else f'{title} | Encounter Atlas'
    nav = nav_html(path)
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
<link rel="apple-touch-icon" href="{url('/static/apple-touch-icon.png')}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Encounter Atlas">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE_URL}{path}">
<meta property="og:image" content="{SITE_URL}/static/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,600;0,700;1,400&family=Zilla+Slab:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{url('/static/site.css')}">
{head_extra}
</head>
<body class="{body_class}">
<a class="skip" href="#main">Skip to content</a>
<div class="print-brand" aria-hidden="true"><img src="{url('/static/logo-mark.svg')}" alt="" width="44" height="44"><div><b>Encounter Atlas</b><span>Cryptids, UFOs and close encounters, mapped</span></div><span class="pb-url">encounteratlas.com</span></div>
<div class="print-foot" aria-hidden="true">Printed from encounteratlas.com{esc(path)} · Free to print and share · Report what you saw at encounteratlas.com/report</div>
<header class="top">
  <a class="brand" href="{url('/')}"><img class="mark" src="{url('/static/logo-mark.svg')}" alt="" width="42" height="42">Encounter Atlas</a>
  <nav class="nav" aria-label="Main">{nav}</nav>
  <a class="report-btn" href="{url('/report/')}"{' aria-current="page"' if path.startswith('/report/') else ''}><span class="rb-dot" aria-hidden="true"></span><span class="rb-long">Report an encounter</span><span class="rb-short" aria-hidden="true">Report</span></a>
</header>
<main id="main">
{body}
</main>
<footer class="foot">
  <div class="foot-in">
    <p class="foot-brand"><img class="mark" src="{url('/static/logo-mark.svg')}" alt="" width="42" height="42">Encounter Atlas</p>
    <p>Sightings, creatures and official files, mapped. Reports are what witnesses say they saw. We don't claim they're real, and we don't claim they're not.</p>
    <p class="foot-links"><a href="{url('/about/')}">About and sources</a><a href="{url('/creatures/')}">Creature index</a><a href="{url('/ufo/')}">UFO sightings</a><a href="{url('/encounters/')}">Close encounters</a><a href="{url('/mysteries/')}">Mysteries</a><a href="{url('/report/')}">Report an encounter</a><a href="{url('/gear/')}">Gear</a><a href="{url('/contact/')}">Contact us</a><a href="{url('/advertise/')}">Advertise with us</a><a href="{url('/privacy/')}">Privacy policy</a></p>
    <p class="small">As an Amazon Associate we earn from qualifying purchases. <a href="{url('/privacy/')}#affiliate">About our affiliate links</a>.</p>
    <p class="small">Air Force case files: US National Archives, Record Group 341. Canadian sightings: the Canadian UFO Survey, Ufology Research. Place data: GeoNames (CC BY 4.0). Map: OpenFreeMap, OpenMapTiles, OpenStreetMap contributors.</p>
  </div>
</footer>
{beacon}
<script src="{url('/static/amz.js')}" defer></script>
<script>if ('serviceWorker' in navigator) navigator.serviceWorker.register('{url('/sw.js')}');</script>
<script>(function(){{const dd=[...document.querySelectorAll('.nav-dd')];dd.forEach(d=>d.addEventListener('toggle',()=>{{if(d.open)dd.forEach(o=>{{if(o!==d)o.open=false;}});}}));document.addEventListener('click',e=>{{dd.forEach(d=>{{if(d.open&&!d.contains(e.target))d.open=false;}});}});document.addEventListener('keydown',e=>{{if(e.key==='Escape')dd.forEach(d=>{{if(d.open){{d.open=false;d.querySelector('summary').focus();}}}});}});}})();</script>
</body>
</html>
'''


def badge(c, size='md'):
    if c.get('art'):
        px = 168 if size == 'xl' else 64
        return (f'<span class="badge badge-{size} art cat-{c["cat"]}"><img src="{url("/static/" + c["art"] + ".svg")}" alt="" '
                f'width="{px}" height="{px}" loading="lazy"></span>')
    return (f'<span class="badge badge-{size} cat-{c["cat"]}">{icon(c["icon"])}</span>')


def mini(c):
    """Small creature mark for chips: the silhouette if we have one, else the old icon."""
    if c.get('art'):
        return f'<span class="mini art cat-{c["cat"]}"><img src="{url("/static/" + c["art"] + ".svg")}" alt="" width="26" height="26" loading="lazy"></span>'
    return icon(c['icon'])


POSTER_SKY = {'hominid': ('#E3A649', '#B5532F'), 'canid': ('#3B4C6B', '#1B2A3A'), 'winged': ('#3B4C6B', '#1B2A3A'),
              'aquatic': ('#E8B04A', '#C8693A'), 'entity': ('#3B4C6B', '#1B2A3A'), 'ufo': ('#2E3E5C', '#141E2E'), 'fae': ('#C97B9A', '#4A2E4F'), 'other': ('#E3A649', '#B5532F')}


def poster(c):
    """Park-poster frame for a creature page: dusk sky, ridgeline, pines, and the silhouette in front."""
    a, b = POSTER_SKY.get(c['cat'], POSTER_SKY['other'])
    sid = 'sky-' + c['slug']
    ground = ('<rect y="160" width="200" height="40" fill="#2B4A55"/>' if c['cat'] == 'aquatic' else
              '<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="#1E3A2F"/>')
    return (f'<svg class="poster" viewBox="0 0 200 200" role="img" aria-label="{esc(c["name"])} silhouette">'
            f'<defs><linearGradient id="{sid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>'
            f'<clipPath id="c{sid}"><rect x="6" y="6" width="188" height="188" rx="10"/></clipPath></defs>'
            f'<g clip-path="url(#c{sid})"><rect width="200" height="200" fill="url(#{sid})"/><circle cx="150" cy="52" r="24" fill="#F3E3B8" opacity=".9"/>'
            f'<path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="#5E4A3A" opacity=".5"/>{ground}'
            f'<image href="{url("/static/" + c["art"] + ".svg")}" x="22" y="{34 if c["cat"] == "aquatic" else 26}" width="160" height="160"/></g>'
            f'<rect x="6" y="6" width="188" height="188" rx="10" fill="none" stroke="#F3E3B8" stroke-width="4"/></svg>')


def creature_card(c, sort=None):
    """sort: on the creature index, a dict of sort keys (n sightings, loc, size, first and last year) shown as a meta line."""
    aka = f'<span class="aka">aka {esc(", ".join(c["aliases"][:2]))}</span>' if c['aliases'] else ''
    data = meta = ''
    if sort:
        data = ''.join(f' data-{k}="{esc(str(v))}"' for k, v in sort.items() if k != 'place')
        n = sort['n']
        meta = (f'<span class="crit-meta"><span class="cm-n">{f"{n} sighting" + ("s" if n != 1 else "") + " on file" if n else "No sightings on file yet"}</span>'
                f'<span class="cm-loc">{esc(sort["place"])}</span></span>')
    return (f'<a class="crit" href="{url("/creatures/" + c["slug"] + "/")}" data-cat="{c["cat"]}"{data} '
            f'data-names="{esc((c["name"] + " " + " ".join(c["aliases"]) + " " + c["region"]).lower())}">'
            f'{badge(c)}<span class="crit-txt"><span class="crit-name">{esc(c["name"])}</span>{aka}'
            f'<span class="crit-sum">{esc(c["summary"])}</span>{meta}</span></a>')


def build_creatures(creatures, by_slug):
    groups = defaultdict(list)
    for c in creatures:
        groups[c['cat']].append(c)
    chips = ''.join(f'<button type="button" class="chip" data-filter="{k}" aria-pressed="false">'
                    f'<span class="dot cat-{k}"></span>{esc(v[0])}</button>' for k, v in CATS.items() if groups[k])
    # Sort keys for the index. "Sightings on file" = famous cases + close encounters + historic newspaper reports
    # (reader reports join once the Worker is live).
    def jload(f):
        fp = os.path.join(ROOT, 'data', f)
        return json.load(open(fp, encoding='utf-8')) if os.path.exists(fp) else []
    countries = jload('countries.json') or {}
    sizes = (jload('sizes.json') or {}).get('sizes', {}) if isinstance(jload('sizes.json'), dict) else {}
    hist = Counter(x.get('creature') for x in jload('historic.json') if x.get('creature'))
    close_n = Counter(s for x in jload('close_encounters.json') for s in x.get('creatures', []))
    keys = {}
    for c in creatures:
        yrs = [f['year'] for f in c['famous'] if isinstance(f.get('year'), int)]
        m = re.search(r'\b(1[0-9]{3}|20[0-9]{2})', c.get('first') or '')
        first = min(yrs + ([int(m.group(1))] if m else [])) if (yrs or m) else 9999
        cc = c['cc'][0] if c['cc'] else ''
        cname = (countries.get(cc) or [cc])[0] if cc else 'Worldwide'
        keys[c['slug']] = {'n': len(c['famous']) + close_n[c['slug']] + hist[c['slug']], 'first': first,
                           'last': max(yrs) if yrs else 0, 'size': (sizes.get(c['slug']) or {}).get('draw', 0),
                           'loc': (cname + ' ' + c['region']).lower(), 'place': c['region'] if cname in c['region'] or cname == 'Worldwide' else f'{c["region"]}, {cname}'}
    sections = ''
    for k, (label, blurb) in CATS.items():
        if not groups[k]:
            continue
        cards = ''.join(creature_card(c, keys[c['slug']]) for c in sorted(groups[k], key=lambda c: (-keys[c['slug']]['n'], c['name'])))
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
    <div class="sort-row"><label for="sort">Sort each group by</label>
      <select id="sort">
        <option value="most">Most sightings</option><option value="fewest">Fewest sightings</option>
        <option value="recent">Most recent sighting</option><option value="oldest">Oldest first record</option>
        <option value="loc">Location (country, then region)</option><option value="size">Biggest first</option>
        <option value="az">Name, A to Z</option>
      </select>
      <span class="sort-note">Sightings on file: famous cases, close encounters and historic newspaper reports.</span></div>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  {sections}
  <p class="empty" hidden>No creature by that name yet. <a href="{url('/report/')}">Tell us about it</a> and we'll add it.</p>
</div></div>
<script src="{url('/static/index.js')}" defer></script>'''
    write('/creatures/', page('/creatures/', 'Creature index: cryptids, monsters and UFO types', body,
                              'Searchable index of cryptids and UFO types with alternative names, famous cases and what witnesses report.'))

    def load(name):
        fp = os.path.join(ROOT, 'data', name)
        return json.load(open(fp)) if os.path.exists(fp) else []
    places = load('places.json')
    guides = load('guides.json')
    fam_geo = Counter(f['creature'] for f in load('famous_geo.json'))
    close_enc = load('close_encounters.json')
    CAT_GUIDES = {'hominid': ['bigfoot-expedition', 'casting-tracks', 'trail-cameras'], 'canid': ['dogman-and-night-encounters', 'trail-cameras'],
                  'ufo': ['skywatching'], 'winged': ['dogman-and-night-encounters'], 'aquatic': [], 'entity': ['dogman-and-night-encounters'], 'fae': [], 'other': []}
    PLACE_KIND = {'museum': 'Museum', 'festival': 'Festival', 'attraction': 'Roadside stop', 'expedition': 'Tour'}

    def extras(c):
        """Map, places, guides and the contribution panel: the 'what next' part of each creature page."""
        out = ''
        n = fam_geo.get(c['slug'], 0)
        np = sum(c['slug'] in (x.get('creatures') or []) for x in places)
        if n or np:  # no card when there is nothing of this creature's own to pin
            what = [f'{n} famous case{"s" if n != 1 else ""}'] if n else []
            what += [f'{np} place{"s" if np != 1 else ""} to visit'] if np else []
            out += (f'<a class="next-card next-map cat-{c["cat"]}" href="{url("/map/?creature=" + c["slug"])}">{crit_icon(c)}'
                    f'<span><b>See {esc(c["name"])} on the map</b><small>{" and ".join(what)} pinned'
                    f'{", plus reader reports" if EA_API else ""}</small></span></a>')
        ce = [x for x in close_enc if c['slug'] in x.get('creatures', [])][:5]
        if ce:
            items = ''.join(f'<li><a href="{url("/encounters/" + x["slug"] + "/")}">{esc(x["name"])}</a><small>{esc(x["place"])}, {x["year"]}</small></li>' for x in ce)
            out += f'<div class="next-block"><h3>Close encounters</h3><ul class="next-list">{items}</ul></div>'
        pl = [x for x in places if c['slug'] in (x.get('creatures') or [])][:6]
        if pl:
            items = ''.join(f'<li><a href="{url("/places/" + x["slug"] + "/")}">{esc(x["name"])}</a>'
                            f'<small>{esc(PLACE_KIND.get(x["type"], "Place"))}{", " + esc(x["city"]) if x.get("city") else ""}'
                            f'{", " + esc(x["region"]) if x.get("region") else ""}</small></li>' for x in pl)
            out += f'<div class="next-block"><h3>Go see it</h3><ul class="next-list">{items}</ul></div>'
        return out

    def guide_band(c):
        """Field guides for this creature, as a full-width band of cards (more prominent than the old sidebar list)."""
        gs = [g for g in guides if c['slug'] in (g.get('creatures') or [])]
        gs += [g for g in guides if g['slug'] in CAT_GUIDES.get(c['cat'], []) and g not in gs]
        if len(gs) < 3:
            gs += [g for g in guides if g['slug'] == 'how-to-report' and g not in gs]
        gs = gs[:3]
        if not gs:
            return ''
        cards = ''.join(f'<a class="cg-card" href="{url("/guides/" + g["slug"] + "/")}"><span class="cg-ico tone-{g.get("tone", "other")}">{icon(g["icon"])}</span>'
                        f'<span><span class="cg-kick">{esc(g.get("kicker") or "Field guide")}</span><b>{esc(g.get("short") or g["title"])}</b>'
                        f'<small>{esc(g.get("blurb") or "")}</small><span class="cg-go">Read the guide{" · printable checklist" if g.get("printable") else ""}</span></span></a>' for g in gs)
        return (f'<section class="band band-dark cg-band" id="guides"><div class="wrap"><h2>{"Out where the stories are told?" if kind(c) == "folklore" else "Watching the skies?" if kind(c) == "ufo" else "Going looking for the " + esc(c["name"]) + "?"}</h2>'
                f'<p class="lede-dark">Our field guides cover where to go, what to bring and how to come back with evidence that holds up.</p>'
                f'<div class="cg-grid">{cards}</div><p class="cg-all"><a href="{url("/guides/")}">All field guides</a></p></div></section>')

    # Books, documentaries and gear (Amazon Associates). Every book/documentary is checked to exist first
    # (tools/verify_media.py -> data/media.json). Living traditions get no shopping at all.
    MEDIA = load('media.json') or {'books': [], 'docs': []}
    for _d in MEDIA['docs']:
        _b = re.sub(r'^\d{4} ', '', _d['blurb'])
        _d['blurb'] = _b[:1].upper() + _b[1:]
    CANDS = {(b['t'], b['a']): b for b in (load('media_candidates.json') or {}).get('books', [])}
    GROUPS = {'hominid': ['@hominid'], 'aquatic': ['@lake', '@sea'], 'ufo': ['@ufo'], 'entity': ['@ufo'], 'fae': ['@fae']}
    GEAR = {
        'ufo': [('Astronomy binoculars', 'astronomy binoculars', 'binoculars'), ('Planisphere star finder', 'planisphere star chart', 'stars'),
                ('Phone tripod for night shots', 'phone tripod night sky', 'tripod'), ('Red-light headlamp', 'red light headlamp astronomy', 'lamp')],
        'aquatic': [('Waterproof binoculars', 'waterproof binoculars', 'binoculars'), ('Waterproof action camera', 'waterproof action camera', 'camera'),
                    ('Phone telephoto lens', 'phone telephoto lens', 'camera'), ('Dry bag', 'dry bag', 'pack')],
        'woods': [('Trail camera', 'trail camera', 'camera'), ('Thermal monocular', 'thermal monocular', 'binoculars'),
                  ('Track casting plaster', 'plaster casting kit animal tracks', 'track'), ('Digital audio recorder', 'digital audio recorder', 'mic')],
    }
    AMZ_TAG = 'encountersatlas-20'
    AUDIBLE = 'https://www.amazon.com/hz/audible/mlp?tag=' + AMZ_TAG  # Audible free-trial page (Associates bounty)

    def amz(q, index=''):
        return ('https://www.amazon.com/s?' + urllib.parse.urlencode({'k': q, **({'i': index} if index else {}), 'tag': AMZ_TAG}))

    def media_band(c):
        sl = c['slug']
        if sl in LIVING_TRADITIONS:
            return ''
        groups = GROUPS.get(c['cat'], [])
        spec = [b for b in MEDIA['books'] if sl in b['for']][:6]
        general = []
        if len(spec) < 3:
            general = [b for b in MEDIA['books'] if any(g in b['for'] for g in groups) and b not in spec]
            general += [b for b in MEDIA['books'] if '@general' in b['for'] and b not in spec and b not in general]
            general = general[:max(0, 3 - len(spec))]
        docs = [d for d in MEDIA['docs'] if sl in d['for']]
        docs += [d for d in MEDIA['docs'] if any(g in d['for'] for g in groups) and d not in docs]
        docs = docs[:3]

        def book_card(b, i):
            cand = next((v for (bt, ba), v in CANDS.items() if v['for'] == b['for'] and ba.lower() in b['author'].lower()), None)
            title = cand['t'] if cand else b['title']
            author = b['author'].split(',')[0] if ', ' not in b['author'] or b['author'].count(',') > 1 else b['author']
            if re.match(r'^[A-Z][a-z]+, [A-Z]', author):  # "Owen, David" -> "David Owen"
                author = ' '.join(reversed(author.split(', ', 1)))
            href = amz(f'{title} {author.split(",")[0]}', 'stripbooks')
            return (f'<a class="md-book tone-{i % 5}" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">'
                    f'<span class="md-spine" aria-hidden="true"></span><span class="md-txt"><b>{esc(title)}</b><small>{esc(author)}</small>'
                    f'<span class="md-go">Find it on Amazon</span></span></a>')
        out = ''
        if spec or general:
            out += f'<h3>Books about the {esc(c["name"])}</h3><div class="md-grid">{"".join(book_card(b, i) for i, b in enumerate(spec))}</div>' if spec else ''
            if general:
                out += (f'<h3>{"More good reads" if spec else "General books on " + ("UFOs" if c["cat"] in ("ufo", "entity") else "fairy lore" if c["cat"] == "fae" else "cryptids")}</h3>'
                        f'{"" if spec else "<p class=md-note>No book is devoted to this one yet, so here are the best general guides.</p>"}'
                        f'<div class="md-grid">{"".join(book_card(b, i + len(spec)) for i, b in enumerate(general))}</div>')
        if spec or general:
            out += (f'<p class="md-listen">Prefer to listen? <a href="{AUDIBLE}" rel="sponsored nofollow noopener" target="_blank">Try Audible free</a> '
                    f'and hear cryptid and UFO books on the drive to the trailhead.</p>')
        if docs:
            cards = ''.join(f'<div class="md-doc"><span class="md-ico">{icon("ufo-film")}</span><span class="md-txt"><b>{esc(d["title"])}</b>'
                            f'<small>{d["year"]} · {esc(d["blurb"])}</small>'
                            f'<span class="md-links"><a href="{esc(amz(d["title"] + " " + str(d["year"]), "instant-video"))}" rel="sponsored nofollow noopener" target="_blank">Watch on Amazon</a>'
                            f'<a href="https://www.justwatch.com/us/search?q={urllib.parse.quote(d["title"])}" rel="noopener nofollow" target="_blank">Where to stream</a>'
                            f'<a href="{esc(d["wiki"])}" rel="noopener" target="_blank">About it</a></span></span></div>' for d in docs)
            out += f'<h3>Watch</h3><div class="md-grid">{cards}</div>'
        if kind(c) not in ('single', 'folklore'):
            gear = GEAR['ufo' if c['cat'] in ('ufo', 'entity') else 'aquatic' if c['cat'] == 'aquatic' else 'woods']
            chips = ''.join(f'<a class="md-chip" href="{esc(amz(q))}" rel="sponsored nofollow noopener" target="_blank">{esc(n)}</a>' for n, q, _ in gear)
            out += (f'<h3>Gear for the field</h3><div class="md-chips">{chips}'
                    f'<a class="md-chip md-merch" href="{esc(amz(("UFO" if c["cat"] == "ufo" else c["name"]) + " shirt"))}" rel="sponsored nofollow noopener" target="_blank">'
                    f'{esc("UFO" if c["cat"] == "ufo" else c["name"])} shirts and gifts</a><a class="md-chip" href="{url("/gear/")}">All field gear</a></div>')
        elif kind(c) == 'folklore' and c['cat'] == 'fae':
            out += (f'<h3>Shop</h3><div class="md-chips"><a class="md-chip md-merch" href="{esc(amz(c["name"] + " gifts"))}" rel="sponsored nofollow noopener" target="_blank">'
                    f'{esc(c["name"])} gifts and decor</a></div>')
        if not out:
            return ''
        return (f'<section class="band band-mist md-band" id="books"><div class="wrap"><h2>Read, watch and gear up <a class="md-aff" href="{url("/privacy/")}#affiliate">(affiliate links)</a></h2>{out}'
                f'</div></section>')

    COUNTRIES = load('countries.json') or {}
    if isinstance(COUNTRIES, list):
        COUNTRIES = {}
    famous_details = {}
    for fn in ('famous_details_a.json', 'famous_details_b.json'):
        d = load(fn)
        if isinstance(d, dict):
            famous_details.update(d)

    KINDS = load('creature_kinds.json') or {}
    # Folklore hybrid (Mike approved 2026-10-12): stories first, then modern claimed sightings, and both
    # actions in the box. Living traditions get a respect note, and their reports are shown at region precision only (enforced by the Worker's LIVING_TRADITIONS; keep both lists in sync).
    FOLK_HYBRID = True
    LIVING_TRADITIONS = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
                         'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}

    def kind(c):
        """cryptid (still reported), single (one exhibit, hoax or incident), folklore (a told tradition) or ufo."""
        return 'ufo' if c['cat'] == 'ufo' else KINDS.get(c['slug'], 'cryptid')

    def seen_box(c):
        k, n, sl = kind(c), esc(c['name']), c['slug']
        extra = ''
        if k == 'single':
            h, p = f'Know more about the {n}?', ('Found an old article, a photo or a mistake on this page? Send it in. '
                                                 'Every note is read by a person, and we credit sources.')
            acts = f'<a class="btn" href="{url("/report/?about=" + sl)}">Add a detail or correction</a>'
        elif k == 'folklore' and FOLK_HYBRID:
            h = 'Seen something, or heard a local story?'
            p = ('Tell us what happened, or share a story passed down in your family or community. '
                 'Every report is read by a person, and you can stay anonymous.')
            if sl in LIVING_TRADITIONS:
                p += (' This is part of a living tradition. Please write respectfully, and we only map reports '
                      'to the nearest region, never an exact spot.')
            acts = (f'<a class="btn" href="{url("/report/?creature=" + sl)}">Report an encounter</a>\n        '
                    f'<a class="btn btn-ghost" href="{url("/report/?story=" + sl)}">Share a story</a>')
        elif k == 'folklore':
            h, p = 'Heard a local story, or had an experience?', ('Stories passed down in families and communities matter. '
                                                                   'Share yours in your own words, and you can stay anonymous.')
            acts = f'<a class="btn" href="{url("/report/?creature=" + sl)}">Share your story</a>'
        else:
            h = 'Seen one?' if k == 'ufo' else f'Seen the {n}?'
            p = 'Tell us what happened. Every report is read by a person before it goes on the map, and you can stay anonymous.'
            label = 'Report a sighting' if k == 'ufo' else f'Report a {n} encounter'
            acts = f'<a class="btn" href="{url("/report/?creature=" + sl)}">{label}</a>'
            if os.path.exists(os.path.join(ROOT, 'data', 'identify.json')):
                acts += f'\n        <a class="btn btn-ghost" href="{url("/tools/what-did-i-see/")}">Not sure what it was?</a>'
            extra = f'<p class="seen-print"><a href="{url("/printables/after-an-encounter/")}">Print a record sheet</a> to fill in while it\'s fresh.</p>'
        return (f'<section class="seen-box cat-{c["cat"]}" aria-labelledby="seen-{sl}">\n      {crit_icon(c)}\n      <div>\n'
                f'        <h2 id="seen-{sl}">{h}</h2>\n        <p>{p}</p>\n        <p class="seen-actions">{acts}</p>\n        {extra}\n      </div>\n    </section>')

    def related_groups(c):
        """Two labelled groups: similar creatures (same kind) and others reported in the same country or continent."""
        cur = [by_slug[s] for s in c['related'] if s in by_slug]
        cc = set(c['cc'])
        conts = {COUNTRIES.get(x, ['', ''])[1] for x in cc} - {''}
        def near(o):
            return 2 if cc & set(o['cc']) else (1 if conts & {COUNTRIES.get(x, ['', ''])[1] for x in o['cc']} else 0)
        same = [o for o in creatures if o['cat'] == c['cat'] and o['slug'] != c['slug']]
        similar = [o for o in cur if o['cat'] == c['cat']]
        similar += sorted((o for o in same if o not in similar), key=lambda o: (-near(o), o['name']))
        similar = similar[:6]
        others = [o for o in creatures if o['slug'] != c['slug'] and o not in similar and near(o)]
        others.sort(key=lambda o: (-(o in cur), -near(o), o['name']))
        nearby = others[:6]
        if cc and any(near(o) == 2 for o in nearby):
            where = ', '.join(COUNTRIES.get(x, [x])[0] for x in sorted(cc)[:3])
        else:
            names = {'NA': 'North America', 'SA': 'South America', 'EU': 'Europe', 'AF': 'Africa', 'AS': 'Asia', 'OC': 'Oceania', 'AN': 'Antarctica'}
            where = ', '.join(names.get(x, x) for x in sorted(conts)) or 'the same part of the world'
        out = ''
        if similar:
            out += (f'<h2 class="rel-h">Similar creatures</h2><p class="rel-why">Other {esc(CATS[c["cat"]][0].lower())} from around the world.</p>'
                    f'<div class="crit-grid">{"".join(creature_card(o) for o in similar)}</div>')
        if nearby:
            out += (f'<h2 class="rel-h">Also from {esc(where)}</h2><p class="rel-why">Different creatures from the same part of the world.</p>'
                    f'<div class="crit-grid">{"".join(creature_card(o) for o in nearby)}</div>')
        return f'<div class="wrap rel-wrap">{out}</div>' if out else ''

    def case_item(c, f):
        d = famous_details.get(c['slug'] + '|' + f['name']) or {}
        story = story_url(c['slug'], f['year'])
        extra = ''
        if d.get('summary'):
            extra += f'<p class="case-sum">{esc(d["summary"])}</p>'
        links = []
        if story:
            links.append(f'<a class="full-story" href="{story}">Read the full story</a>')
        if d.get('source_url'):
            links.append(f'<a class="case-src" href="{esc(d["source_url"])}" rel="noopener">Source: {esc(d.get("source_title") or "read more")}</a>')
        if links:
            extra += f'<p class="case-links">{"".join(links)}</p>'
        return (f'<li><span class="yr">{f["year"]}</span><span><strong>{esc(f["name"])}</strong>'
                f'<br><span class="muted">{esc(f["place"])}</span>{extra}</span></li>')

    for c in creatures:
        aka = (f'<p class="aka-line">Also called {esc(", ".join(c["aliases"]))}</p>' if c['aliases'] else '')
        facts = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in
                        [('Where', c['region']), ('Size', c['size']), ('Setting' if kind(c) == 'single' else 'Habitat', c['habitat']),
                         ({'single': 'When', 'folklore': 'Earliest record'}.get(kind(c), 'First reported'), c['first'])] if v)
        body_p = ''.join(f'<p>{esc(p)}</p>' for p in c['body'])
        signs = ''.join(f'<li>{esc(s)}</li>' for s in c['signs'])
        fam = sorted(c['famous'], key=lambda f: f['year'])
        modern = ''
        if kind(c) == 'folklore' and FOLK_HYBRID:
            yr = lambda f: f['year'] if isinstance(f['year'], int) else 0
            modern = ''.join(case_item(c, f) for f in fam if yr(f) >= 1900)
            fam = [f for f in fam if yr(f) < 1900]
        cases = ''.join(case_item(c, f) for f in fam)
        first_story = story_url(c['slug'], 'first')
        rel = ''.join(creature_card(by_slug[s]) for s in c['related'] if s in by_slug)
        wiki = f'https://en.wikipedia.org/wiki/{c["wiki"].replace(" ", "_")}' if c.get('wiki') else ''
        ufo_note = ''
        if c['cat'] == 'ufo':
            ufo_note = (f'<p class="callout">{icon("folder", "ico ico-inline")} Browse 10,622 US Air Force Project Blue Book '
                        f'case files on the <a href="{url("/map/")}">map</a> or <a href="{url("/ufo/blue-book/")}">by state</a>.</p>')
        gb, mb = (guide_band(c) if kind(c) != 'single' else ''), media_band(c)
        jumps = [('#cases', 'Timeline' if kind(c) == 'single' else 'Famous cases') if cases else None, ('#modern', 'Modern reports') if modern else None,
                 ('#facts', 'Facts'), ('#guides', 'Field guides') if gb else None, ('#books', 'Books and gear') if mb else None, ('#related', 'Similar creatures')]
        jump = '<nav class="jump" aria-label="On this page">' + ''.join(f'<a href="{h}">{t}</a>' for h, t in filter(None, jumps)) + '</nav>'
        body = f'''
<section class="band band-dark creature-head cat-{c['cat']}">
  <div class="wrap creature-head-in">
    {poster(c) if c.get('art') else badge(c, 'xl')}
    <div>
      <p class="crumb"><a href="{url('/creatures/')}">Creature index</a> / {esc(CATS[c['cat']][0])}</p>
      <h1>{esc(c['name'])}</h1>
      {aka}
      <p class="lede">{esc(c['summary'])}</p>
      {f'<p class="lede-story"><a href="{first_story[0]}">Read the full story: {esc(first_story[1])}</a></p>' if first_story else ''}
      {jump}
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap creature-body">
  <article class="prose">
    {'<h2>The story</h2>' if kind(c) == 'single' else ''}
    {body_p}
    {ufo_note}
    <h2>{ {'single': 'What was shown or claimed', 'folklore': 'What the stories say'}.get(kind(c), 'What witnesses report') }</h2>
    <ul class="signs">{signs}</ul>
    {f'<h2 id="cases">{"Timeline" if kind(c) == "single" else "Famous cases"}</h2><ol class="timeline">{cases}</ol>' if cases else ''}
    {f'<h2 id="modern">Modern reports</h2><ol class="timeline">{modern}</ol>' if modern else ''}
    {seen_box(c)}
  </article>
  <aside class="side">
    <div class="facts" id="facts">
      <dl>{facts}</dl>
      {f'<p class="more"><a href="{wiki}" rel="noopener">Read more on Wikipedia</a></p>' if wiki else ''}
    </div>
    {extras(c)}
  </aside>
</div>
</div>
{gb}
{mb}
<div class="band band-mist" id="related">{related_groups(c)}</div>'''
        write(f'/creatures/{c["slug"]}/', page(f'/creatures/{c["slug"]}/', f'{c["name"]}: ' + {'single': 'the story, facts and other names', 'folklore': 'stories, facts and other names'}.get(kind(c), 'sightings, facts and other names'),
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
        return slugify(b.get('country') or b['region'] or b['cc'])
    return 'unknown'


def build_ufo(bluebook):
    by_region = defaultdict(list)
    for b in bluebook:
        by_region[region_slug(b)].append(b)
    names = {}
    for k, v in by_region.items():
        b = v[0]
        names[k] = (b['region'] if b['cc'] == 'US' else b.get('country') or b['region']) if b['cc'] else 'Place unclear or at sea'
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
    <p class="crumb"><a href="{url('/ufo/')}">UFOs</a> / Air Force files</p>
    <h1>Project Blue Book: the Air Force UFO files</h1>
    <p class="lede">From 1947 to 1969 the US Air Force investigated {len(bluebook):,} UFO reports. Every case folder is now public at the National Archives. We've put them on a map and sorted them by state and country.</p>
    <nav class="tiles ufo-more" aria-label="More official UFO files">
      <a class="tile" href="{url('/ufo/releases/')}">{icon('folder')}<span>Every official release, 13 countries</span></a>
      <a class="tile" href="{url('/ufo/files/pursue/')}">{icon('military')}<span>The Pentagon's 2026 files</span></a>
      <a class="tile" href="{url('/ufo/files/faa/')}">{icon('saucer')}<span>FAA pilot reports, 2007 to 2024</span></a>
      <a class="tile" href="{url('/ufo/canada/')}">{icon('saucer')}<span>Canada sightings, 1989 to today</span></a>
      <a class="tile" href="{url('/ufo/countries/')}">{icon('ufo-globe') if os.path.exists(os.path.join(STATIC, 'icons', 'ufo-globe.svg')) else icon('saucer')}<span>UFO files by country</span></a>
      <a class="tile" href="{url('/encounters/')}">{icon('entity')}<span>Close encounters with beings</span></a>
    </nav>
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
    write('/ufo/blue-book/', page('/ufo/blue-book/', 'Project Blue Book UFO files by state, year and map', body,
                        f'All {len(bluebook):,} US Air Force Project Blue Book UFO case files (1947-1969), mapped and listed by state and country.'))
    for k, cases in by_region.items():
        cases = sorted(cases, key=lambda b: (b['year'] or 0, b['month'] or 0))
        nm = names[k] if k != 'unknown' else 'Place unclear or unreadable'
        ys = Counter(b['year'] for b in cases if b.get('year'))
        peak = f' The busiest year was {max(ys, key=ys.get)}, with {max(ys.values())} reports.' if ys else ''
        items = ''.join(case_line(b) for b in cases)
        body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/ufo/')}">UFOs</a> / <a href="{url('/ufo/blue-book/')}">Project Blue Book</a></p>
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
    """GeoJSON for the map. Files pinned to a place go in bluebook.geojson. Files that only name a state, province or
    country are never drawn as a pin: they go in bluebook_approx.geojson as one faded "about N files somewhere in X"
    ring per area, at a point inside it, linking to that area's list."""
    feats, approx = [], {}
    for b in bluebook:
        if b.get('lat') is None:
            continue
        if b['precision'] in ('region', 'country'):
            key = (b['cc'], b['a1'] if b['precision'] == 'region' else None)
            a = approx.setdefault(key, {'lat': b['lat'], 'lon': b['lon'], 'n': 0, 'k': region_slug(b),
                                        'name': b['region'] if b['precision'] == 'region' else (b.get('country') or b['region'])})
            a['n'] += 1
            continue
        when = f'{MONTHS[b["month"]][:3]} {b["year"]}' if b.get('month') and b.get('year') else (b.get('year') or '')
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(b['lon'], 3), round(b['lat'], 3)]},
                      'properties': {'id': b['id'], 't': (b['place'] or b['region'] or '')[:60], 'r': b['region'] or '',
                                     'w': str(when), 'y': b.get('year') or 0, 'a': 0}})
    os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
    with open(os.path.join(OUT, 'data', 'bluebook.geojson'), 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'))
    ap = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(a['lon'], 3), round(a['lat'], 3)]},
           'properties': {'n': a['n'], 't': a['name'], 'u': url(f'/ufo/blue-book/{a["k"]}/')}}
          for a in sorted(approx.values(), key=lambda a: -a['n'])]
    with open(os.path.join(OUT, 'data', 'bluebook_approx.geojson'), 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': ap}, f, separators=(',', ':'))
    return len(feats)


def build_layer_data(creatures, military):
    """Small GeoJSON layers for the map: famous creature cases and military encounters."""
    by_slug = {c['slug']: c for c in creatures}
    fam_path = os.path.join(ROOT, 'data', 'famous_geo.json')
    famous = json.load(open(fam_path)) if os.path.exists(fam_path) else []
    feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [f['lon'], f['lat']]},
              'properties': {'s': f['creature'], 'n': by_slug[f['creature']]['name'], 'c': f['cat'], 'i': by_slug[f['creature']].get('art') or by_slug[f['creature']]['icon'],
                             't': f['name'], 'y': f['year'], 'p': f['place'], 'u': story_url(f['creature'], f['year'])}}
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
  <p class="crumb"><a href="{url('/ufo/')}">UFOs</a> / Military</p>
  <h1>Military encounters</h1>
  <p class="lede">Pilots, radar operators and soldiers have reported some of the strangest things on record, and the military has kept files on them since the 1940s.</p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <p>The Air Force's own Project Blue Book alone holds {10622:,} case files. <a href="{url('/ufo/blue-book/')}">Browse them by state</a>. Below are the military cases people still talk about.</p>
  <ol class="timeline mil-list">{items}</ol>
</div></div>'''
    write('/military/', page('/military/', 'Military UFO and creature encounters', body,
                             'The most famous military UFO and UAP encounters, from WWII foo fighters to the Navy Tic Tac, with official sources.'))


TILES = [('hominid', 'yeti', 'Bigfoot and hairy giants'), ('canid', 'dogman', 'Dogmen and beasts'),
         ('winged', 'mothman', 'Winged things'), ('aquatic', 'lake', 'Lake monsters'),
         ('entity', 'entity', 'Strange visitors'), ('fae', 'fairy', 'Fairies and little people'), ('ufo', 'saucer', 'UFOs and UAP')]
MAP_HEAD = None


def map_head():
    return (f'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
            f'<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
            f'<script src="{url("/static/map.js")}" defer></script>')


def filter_bar(creatures, famous_slugs):
    """Type chips, then category chips and a creature search; picking a category (or typing) shows that group's
    creature chips, wrapped onto lines rather than one long sideways row. map.js wires them up."""
    types = [('all', 'Everything'), ('cryptid', 'Cryptids'), ('ufo', 'UFOs'), ('military', 'Military'), ('places', 'Places to visit'), ('events', 'Events and gatherings')]
    tchips = ''.join(f'<button type="button" class="tchip" data-type="{k}" aria-pressed="{str(k == "all").lower()}">{esc(v)}</button>'
                     for k, v in types)
    crit = [c for c in creatures if c['slug'] in famous_slugs]
    order = {k: i for i, k in enumerate(CATS)}
    crit.sort(key=lambda c: (order[c['cat']], c['name']))
    counts = Counter(c['cat'] for c in crit)
    rep = {cat: ic for cat, ic, _ in TILES}
    catchips = ''.join(f'<button type="button" class="catchip cat-{k}" data-cat="{k}" aria-pressed="false">{icon(rep.get(k, "worm"))}'
                       f'<span>{esc(CATS[k][0])}</span><small>{counts[k]}</small></button>' for k in CATS if counts.get(k))
    cchips = ''.join(f'<button type="button" class="cchip cat-{c["cat"]}" data-creature="{c["slug"]}" data-cat="{c["cat"]}" '
                     f'data-names="{esc((c["name"] + " " + " ".join(c["aliases"])).lower())}" aria-pressed="false" hidden>'
                     f'{mini(c)}<span>{esc(c["name"])}</span></button>' for c in crit)
    return (f'<div class="filters" aria-label="Filter the map"><div class="tchips" role="group" aria-label="Encounter type">{tchips}</div>'
            f'<div class="cfind"><div class="catchips" role="group" aria-label="Creature type">{catchips}</div>'
            f'<input type="search" class="cfind-in" placeholder="Find a creature" aria-label="Find a creature on the map" autocomplete="off"></div>'
            f'<div class="cchips" role="group" aria-label="Creature" hidden>{cchips}</div><p class="cfind-none" hidden>No creature by that name has a pin yet.</p></div>')


def build_search_index(creatures, bluebook, military):
    """Small JSON index for the home search box: creatures (with aliases), UFO file regions, military cases."""
    items = [{'t': c['name'], 'a': ' '.join(c['aliases']), 'k': CATS[c['cat']][0], 'u': url('/creatures/' + c['slug'] + '/'), 'i': c.get('art') or c['icon'], 'c': c['cat']}
             for c in creatures]
    regions = Counter()
    names = {}
    for b in bluebook:
        k = region_slug(b)
        if k != 'unknown':
            regions[k] += 1
            names[k] = b['region']
    items += [{'t': f'UFO files: {names[k]}', 'a': names[k], 'k': f'{n:,} Air Force files', 'u': url('/ufo/blue-book/' + k + '/'), 'i': 'folder', 'c': 'ufo'}
              for k, n in regions.items()]
    ce_path = os.path.join(ROOT, 'data', 'close_encounters.json')
    for x in (json.load(open(ce_path)) if os.path.exists(ce_path) else []):
        items.append({'t': x['name'], 'a': x['place'] + ' ' + ' '.join(x.get('creatures', [])), 'k': f'Close encounter, {x["year"]}',
                      'u': url('/encounters/' + x['slug'] + '/'), 'i': 'art/' + (x['creatures'] or ['grey-aliens'])[0], 'c': 'entity'})
    items += [{'t': m['name'], 'a': m['place'], 'k': 'Military encounter, ' + m['date'][:4], 'u': url('/military/'), 'i': 'military', 'c': 'ufo'}
              for m in military]
    with open(os.path.join(OUT, 'data', 'search.json'), 'w') as f:
        json.dump(items, f, separators=(',', ':'))


def build_home(creatures, n_points, bluebook, military):
    fam_path = os.path.join(ROOT, 'data', 'famous_geo.json')
    famous_slugs = {f['creature'] for f in json.load(open(fam_path))} if os.path.exists(fam_path) else set()
    cu_path = os.path.join(ROOT, 'data', 'ufo_cases_canada.json')
    n_canada = len(json.load(open(cu_path))) if os.path.exists(cu_path) else 0
    featured = [c for c in creatures if c['slug'] in ('bigfoot', 'dogman', 'mothman', 'loch-ness-monster', 'chupacabra',
                                                       'ufo-tic-tac', 'jersey-devil', 'flatwoods-monster', 'fairies')]
    cards = ''.join(creature_card(c) for c in featured)
    tiles = ''.join(f'<a class="tile cat-{cat}" href="{url("/map/?cat=" + cat)}">{tile_icon(ic)}<span>{esc(label)}</span></a>'
                    for cat, ic, label in TILES)
    tiles += f'<a class="tile tile-mil" href="{url("/map/?type=military")}">{tile_icon("military")}<span>Military encounters</span></a>'
    build_search_index(creatures, bluebook, military)
    body = f'''
<section class="home-hero">
  <div class="wrap">
    <h1>Every strange thing, on one map</h1>
    <p class="lede">Bigfoot, Dogman, lake monsters, UFOs and what the military saw. {len(creatures)} creatures, {len(bluebook):,} Air Force files, {n_canada:,} Canadian sightings, and soon, your reports.</p>
    <div class="search" data-index="{url('/data/search.json')}">
      <label class="visually-hidden" for="home-q">Search</label>
      <input id="home-q" type="search" placeholder="Search: Sasquatch, Ohio, Roswell..." autocomplete="off">
      <ul class="search-results" hidden></ul>
    </div>
    <nav class="tiles" aria-label="Browse by type">{tiles}</nav>
  </div>
</section>
<section class="map-block" aria-label="Encounter map">
  <div class="wrap">
    <div class="map-block-head">
      <h2>The encounter map</h2>
      <div class="map-block-actions"><button type="button" class="btn btn-sm" data-locate>Use my location</button>
      <a class="btn btn-sm btn-ghost" href="{url('/map/')}">Full screen</a></div>
    </div>
    {filter_bar(creatures, famous_slugs)}
  </div>
  <div class="map-frame"><div id="map" class="map" data-base="{BASE}"{MAP_API}></div></div>
</section>
<div class="band band-mist"><div class="wrap">
  <div class="near" hidden>
    <h2>Near you</h2>
    <ol class="timeline near-list"></ol>
  </div>
  <div class="this-month">
    <h2>This month in the Air Force files</h2>
    <p class="lede-dark">UFO reports the Air Force logged in <span class="month-name">this month</span>, 1947 to 1969.</p>
    <ol class="timeline cases month-list"><li><span class="yr"></span><span>Loading...</span></li></ol>
  </div>
  <h2>Meet the locals</h2>
  <p class="lede-dark">Every creature has its other names, what witnesses report and the cases that made it famous.</p>
  <div class="crit-grid home-crits">{cards}</div>
  <p><a href="{url('/creatures/')}">See all {len(creatures)} creatures</a></p>
</div></div>
<div class="band band-dark"><div class="wrap split split-3">
  <div>
    {icon('folder', 'ico ico-lg')}
    <h2>The Air Force kept files</h2>
    <p>Project Blue Book collected {len(bluebook):,} UFO reports between 1947 and 1969. Find the ones from your state, read the original scans, and see where they cluster.</p>
    <p><a class="btn" href="{url('/ufo/blue-book/')}">Open the Air Force files</a></p>
  </div>
  <div>
    {icon('ufo-globe', 'ico ico-lg')}
    <h2>Canada's UFO sightings</h2>
    <p>{n_canada:,} reports from every province and territory since 1989, from the Canadian UFO Survey. See your town's sightings and the ones nobody could explain.</p>
    <p><a class="btn" href="{url('/ufo/canada/')}">Open the Canada map</a></p>
  </div>
  <div>
    {icon('military', 'ico ico-lg')}
    <h2>Military encounters</h2>
    <p>Foo fighters over Germany, radar returns over the White House, a Tic Tac off San Diego. The cases pilots and soldiers reported.</p>
    <p><a class="btn" href="{url('/military/')}">Read the cases</a></p>
  </div>
</div></div>
<script src="{url('/static/home.js')}" defer></script>'''
    write('/', page('/', 'Encounter Atlas: Bigfoot, UFO and cryptid sightings mapped', body,
                    'A map of Bigfoot, Dogman, UFO and cryptid encounters, a searchable creature index, and the US Air Force Project Blue Book files.',
                    body_class='home', head_extra=map_head()))
    write('/map/', page('/map/', 'Encounter map', f'''
<section class="map-full" aria-label="Encounter map">
  <div class="map-full-bar">
    {filter_bar(creatures, famous_slugs)}
    <button type="button" class="btn btn-sm" data-locate>Near me</button>
  </div>
  <div class="map-frame full"><div id="map" class="map" data-base="{BASE}"{MAP_API}></div>
    <a class="map-exit" href="{url('/')}" hidden><svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>Exit full map</a></div>
</section>''', 'Map of Bigfoot, Dogman, UFO and cryptid encounters, military cases and every US Air Force Project Blue Book file.',
                        body_class='mapper', head_extra=map_head()))


def build_static_pages():
    write('/report/', page('/report/', 'Report an encounter', f'''
<section class="band band-dark"><div class="wrap">
  <h1>Report an encounter</h1>
  <p class="lede">Saw something you can't explain? The report form is being built now and opens soon, with links to your photos and videos and a pin on the map.</p>
</div></section>
<div class="band band-mist"><div class="wrap prose">
  <p><a class="btn" href="{url('/printables/after-an-encounter/')}">Print the encounter record sheet</a></p>
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
  <h2>What to bring next time</h2>
  <p>A trail camera, a red-light headlamp and an audio recorder catch most of what people miss. See <a href="{url('/gear/')}">field gear for investigators</a>.</p>
</div></div>''', 'Report a Bigfoot, Dogman, UFO or other strange encounter.'))
    write('/about/', page('/about/', 'About and sources', f'''
<section class="band band-dark"><div class="wrap"><h1>About Encounter Atlas</h1>
<p class="lede">One place for strange sightings: creatures, UFOs and the official files, mapped and searchable.</p></div></section>
<div class="band band-mist"><div class="wrap prose">
<h2>Sources</h2>
<ul>
<li><strong>Project Blue Book case files</strong>, US Air Force, 1947 to 1969. US National Archives, Record Group 341, microfilm T1206. US federal records, no copyright in the United States. Places were matched automatically from the folder titles; dots marked “approximate” are placed at the state or country, not the exact spot.</li>
<li><strong>Canadian UFO sightings, 1989 to 2025</strong>: the Canadian UFO Survey, compiled each year by Ufology Research (Winnipeg) from reports to police, airports, the military, researchers and UFO groups. We left out reports the survey received from MUFON, NUFORC and Enigma Labs. Ratings (explained, unexplained...) are the survey's; notes are lightly tidied. Places were matched to towns with GeoNames.</li>
<li><strong>Place names</strong>: GeoNames, licensed CC BY 4.0.</li>
<li><strong>Map tiles</strong>: OpenFreeMap, built on OpenMapTiles and OpenStreetMap data.</li>
<li><strong>Creature entries</strong> are written by us from published accounts. Each links to further reading.</li>
</ul>
<h2>Our stance</h2>
<p>We collect reports and evidence and let you decide. A report on this site means someone said they saw something, not that it's proven.</p>
</div></div>''', 'Sources and approach behind Encounter Atlas.'))
    write('/privacy/', page('/privacy/', 'Privacy', f'''
<section class="band band-dark"><div class="wrap"><h1>Privacy</h1>
<p class="lede">What we keep when you use Encounter Atlas or send us a report, who can see it, and how to get it removed. Short version: your exact location, your email address and your IP address are never made public.</p></div></section>
<div class="band band-mist"><div class="wrap prose">
<p class="small">Last updated: October 12, 2026.</p>

<h2>Just reading the site</h2>
<ul>
<li><strong>No ads, no tracking cookies, no account needed.</strong> You can read every page and use the map and tools without signing up.</li>
<li><strong>Visitor counts:</strong> we don't run visitor analytics right now. If we add them, we'll use a cookie-free service that only shows totals, like page views and countries, and we'll update this page first.</li>
<li><strong>Things your browser remembers, not us:</strong> your sort choice on the creature index, and a draft of a report you haven't sent yet (stored only on your device so you don't lose them). Clearing your browser data removes them.</li>
<li><strong>Other services the pages load:</strong> map tiles from OpenFreeMap, fonts from Google Fonts and code libraries from cdnjs. Like any website, these see your IP address when they send the file. Witness videos only load from YouTube (in its privacy-enhanced mode) when you press play.</li>
</ul>

<h2>Sending a report</h2>
<p>When you report an encounter we keep what you type and choose: the date and time, what you saw, the story, sounds, smells, how many people were there, links to any photos and videos, and where it happened.</p>
<ul>
<li><strong>Your exact location is private.</strong> Only our moderators see the exact spot. The public map shows the report on a grid of about 5 km (3 miles), never the exact point, so nobody can find your home or a private spot from it.</li>
<li><strong>We don't take photo or video uploads.</strong> You can link to pictures and videos you've posted elsewhere (Imgur, Flickr, YouTube and so on). Those files stay on that service, under its rules. Some services keep the GPS location inside a photo, so check before you share a link.</li>
<li><strong>Your name is optional.</strong> Reports are anonymous unless you choose to show a display name.</li>
<li><strong>Every report is checked by a person</strong> before it appears on the site, and we can turn down reports that break our rules.</li>
<li><strong>Spam protection:</strong> forms use Cloudflare Turnstile to check you're not a bot, and we store a scrambled one-way code made from your IP address (not the address itself) to spot floods of fake reports or votes.</li>
</ul>

<h2>Accounts and voting</h2>
<ul>
<li>Signing in uses a one-time link sent to your email. We keep your email address and, if you choose one, a display name. There's no password for us to lose.</li>
<li>Your email is never shown on the site, never sold and never added to a mailing list. We only use it to sign you in and, if we need to, to contact you about one of your reports.</li>
<li>When you vote "real or hoax", we keep the vote, the account that cast it and the scrambled IP code, so each account counts once and vote-stuffing can be caught. Results are shown as totals, never as who voted what.</li>
</ul>

<h2>Who can see what</h2>
<ul>
<li><strong>Everyone:</strong> approved reports (story, date, approximate area, photo and video links, display name if you chose one) and vote totals.</li>
<li><strong>Our moderators only:</strong> the exact location, your email address and the scrambled IP code, to check reports and stop abuse.</li>
<li><strong>Service providers that run the site for us:</strong> Cloudflare (hosting for reports and the database), Resend (sends the sign-in emails and passes contact-form messages to our inbox) and GitHub (hosts the public pages). They process data only to provide those services.</li>
<li>We don't sell or rent anyone's information, and we don't share it with advertisers or other sighting organisations.</li>
</ul>

<h2>Removing your report or account</h2>
<ul>
<li>If you sent a report while signed in, you can edit or withdraw it yourself from the report page. Withdrawing removes it from the site straight away.</li>
<li>To remove a report sent without an account, delete your account, or ask what we hold about you, email <a href="mailto:hello@encounteratlas.com">hello@encounteratlas.com</a>. We reply within 30 days.</li>
<li>Sign-ins expire after 90 days on a device, and you can sign out at any time.</li>
</ul>

<h2 id="affiliate">Affiliate links</h2>
<p>Some links on creature pages (books, documentaries, gear and shirts) go to Amazon.com. As an Amazon Associate we earn from qualifying purchases. It costs you nothing extra, and it never decides what we write: books are listed because they're about the creature, not because of a deal. These links are marked as sponsored for search engines.</p>
<p>When you click one, Amazon may set its own cookies to credit the sale to us. That happens on Amazon's site, under <a href="https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ" rel="noopener">Amazon's privacy notice</a>. We don't get your name, address or what else you buy, only order totals.</p>
<h2>Children</h2>
<p>Encounter Atlas is meant for adults and teens. If you're under 13, please ask a parent or guardian to send a report for you.</p>

<h2>Changes</h2>
<p>If we change how we handle your information, we'll update this page and the date at the top.</p>
<p>See also: <a href="{url('/about/')}">About and sources</a>.</p>
</div></div>''', 'What Encounter Atlas keeps when you read the site or send a report, who can see it, and how to have it removed.'))
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
    for c in creatures:  # park-poster silhouettes (site/static/art/<slug>.svg) replace the old icons where we have them
        if os.path.exists(os.path.join(STATIC, 'art', c['slug'] + '.svg')):
            c['art'] = 'art/' + c['slug']
    bad = [(c['slug'], r) for c in creatures for r in c['related'] if r not in by_slug]
    if bad:
        print('unknown related slugs:', bad, file=sys.stderr)
    bluebook = json.load(open(os.path.join(ROOT, 'data', 'bluebook.json')))
    mil_path = os.path.join(ROOT, 'data', 'military.json')
    military = json.load(open(mil_path)) if os.path.exists(mil_path) else []
    n_points = build_map_data(bluebook)
    build_layer_data(creatures, military)
    build_home(creatures, n_points, bluebook, military)
    build_creatures(creatures, by_slug)
    build_ufo(bluebook)
    build_military(military)
    build_static_pages()
    # Each site/sections/*.py module owns one part of the site (places, podcasts, ...) and exposes
    # build(ctx). ctx gives it the shared helpers and loaded data, so sections never edit this file.
    import importlib.util, types
    ctx = types.SimpleNamespace(ROOT=ROOT, OUT=OUT, STATIC=STATIC, SITE_URL=SITE_URL, BASE=BASE, page=page, write=write,
                                url=url, esc=esc, icon=icon, crit_icon=crit_icon, slugify=slugify, badge=badge, creature_card=creature_card,
                                creatures=creatures, by_slug=by_slug, bluebook=bluebook, military=military, CATS=CATS, MONTHS=MONTHS)
    sec_dir = os.path.join(ROOT, 'site', 'sections')
    for fn in sorted(os.listdir(sec_dir)) if os.path.isdir(sec_dir) else []:
        if fn.endswith('.py') and not fn.startswith('_'):
            spec = importlib.util.spec_from_file_location('sec_' + fn[:-3], os.path.join(sec_dir, fn))
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                mod.build(ctx)
            except Exception as e:  # SKIP_BROKEN_SECTIONS=1 for local previews while a section is half-built
                if not os.environ.get('SKIP_BROKEN_SECTIONS'):
                    raise
                print(f'warning: section {fn} skipped: {e!r}', file=sys.stderr)
    with open(os.path.join(OUT, 'manifest.webmanifest'), 'w') as f:
        json.dump({'name': 'Encounter Atlas', 'short_name': 'Encounters', 'start_url': BASE + '/map/', 'display': 'standalone',
                   'background_color': '#13261F', 'theme_color': '#13261F',
                   'description': 'Report and explore Bigfoot, Dogman, UFO and cryptid encounters on a live map.',
                   'icons': [{'src': BASE + '/static/app-192.png', 'sizes': '192x192', 'type': 'image/png'},
                             {'src': BASE + '/static/app-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
                             {'src': BASE + '/static/favicon.svg', 'sizes': 'any', 'type': 'image/svg+xml'}]}, f)
    shutil.copy(os.path.join(ROOT, 'site', 'sw.js'), os.path.join(OUT, 'sw.js'))
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

"""Road trip mode (/road-trip/), sample trips (/road-trip/<slug>/) and collector cards (/cards/).

Named z_road_trip.py so it runs after the sections that write the GeoJSON it reads (famous, places, mysteries,
encounters, historic). Writes /data/roadtrip.json: every stop a trip can pass (places, famous cases, mysteries,
encounters, old newspaper stories) plus the collectible cards (one per creature that has a real spot to visit,
living traditions left out). static/roadtrip.js plans trips in the browser (route from the FOSSGIS OSRM server,
OpenStreetMap data, straight-line fallback) and static/cards.js keeps the collection on the device.

The sample trips' routes are cached in data/road_trips.json by tools/road_trip_routes.py, and their stops are worked
out here at build time so each trip page is complete HTML. Trips with fewer than 8 stops are noindexed."""
import importlib.util, json, math, os

CORRIDOR_KM = 40
CHECKIN_KM = 25
# Same list as LIVING_TRADITIONS in site/build.py and the Worker: info only, never collectible
LIVING = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
          'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}
HPAGE = {'airship': 'airships-1896-1897', 'airship-1909': 'phantom-airships-1909', 'wild-man': 'wild-men', 'sea-serpent': 'sea-serpents',
         'jersey-devil': 'jersey-devil-1909', 'giant-bird': 'giant-birds', 'phantom-light': 'phantom-lights', 'creature': 'strange-creatures'}
KIND = {'place': ('Place to visit', '#9CC46B'), 'case': ('Famous case', '#D9A05B'), 'mystery': ('Mystery', '#E07A4F'),
        'encounter': ('Close encounter', '#8E8CF0'), 'newspaper': ('Old newspaper story', '#C9B27A')}


def hav(a1, o1, a2, o2):
    r = math.pi / 180
    h = math.sin((a2 - a1) * r / 2) ** 2 + math.cos(a1 * r) * math.cos(a2 * r) * math.sin((o2 - o1) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(min(1, h)))


def densify(route, step=4):
    """Points every ~4 km along the route with the distance from the start: [(lat, lon, km)]."""
    out, acc = [], 0
    for (o1, a1), (o2, a2) in zip(route, route[1:]):
        d = hav(a1, o1, a2, o2)
        n = max(1, int(d / step))
        out += [(a1 + (a2 - a1) * i / n, o1 + (o2 - o1) * i / n, acc + d * i / n) for i in range(n)]
        acc += d
    out.append((route[-1][1], route[-1][0], acc))
    return out


def along(samples, lat, lon, max_km):
    """(km off the route, km from the start) for the closest sample, or None if it's outside the corridor."""
    best = None
    for a, o, k in samples:
        if abs(a - lat) > 1 or abs(o - lon) > 1.5:
            continue
        d = hav(lat, lon, a, o)
        if d <= max_km and (best is None or d < best[0]):
            best = (d, k)
    return best


def build(ctx):
    E, U = ctx.esc, ctx.url
    D = os.path.join(ctx.OUT, 'data')
    gj = lambda f: json.load(open(os.path.join(D, f + '.geojson')))['features']

    # ---------- every stop a trip can pass ----------
    stops = []   # [kind, lat, lon, title, sub, url, creature]
    for x in gj('places'):
        p = x['properties']; lon, lat = x['geometry']['coordinates']
        stops.append(['place', lat, lon, p['name'], ', '.join(v for v in (p.get('type'), p.get('city'), p.get('region')) if v),
                      U('/places/' + p['slug'] + '/'), p.get('c') or ''])
    case_place = {}   # a famous case's place name, used as the card spot label (case titles read oddly there)
    for x in gj('famous'):
        p = x['properties']; lon, lat = x['geometry']['coordinates']
        if p['s'] in LIVING:
            continue
        stops.append(['case', lat, lon, p['t'], f"{p['n']}, {p['p']}{', ' + str(p['y']) if p.get('y') else ''}",
                      p.get('u') or U('/creatures/' + p['s'] + '/'), p['s']])
        case_place[(p['t'], p['s'])] = p['p']
    for f, kind in (('mysteries', 'mystery'), ('encounters', 'encounter')):
        for x in gj(f):
            p = x['properties']; lon, lat = x['geometry']['coordinates']
            stops.append([kind, lat, lon, p['n'], f"{p['p']}, {p['d']}", p['u'], ''])
    for x in gj('historic'):
        p = x['properties']; lon, lat = x['geometry']['coordinates']
        if p.get('a') or p.get('c') in LIVING:   # area-only stories don't have a spot to drive to
            continue
        stops.append(['newspaper', lat, lon, p['t'], f"{p['p']}, {p['d']}", U(f"/history/{HPAGE.get(p['k'], 'strange-creatures')}/#h-{p['id']}"), p.get('c') or ''])
    for s in stops:
        s[1], s[2] = round(s[1], 4), round(s[2], 4)

    # ---------- collectible cards ----------
    spots = {}
    for s in stops:
        c = s[6]
        if s[0] in ('place', 'case') and c and c in ctx.by_slug and c not in LIVING:
            spots.setdefault(c, []).append([s[1], s[2], s[3] if s[0] == 'place' else case_place.get((s[3], c), s[3])])
    cards = {}
    for slug, sp in spots.items():
        c = ctx.by_slug[slug]
        n = len(sp)
        cards[slug] = {'n': c['name'], 'c': c['cat'], 'art': U(f"/static/{c['art']}.svg") if c.get('art') else '',
                       'r': 'Unique' if n == 1 else 'Uncommon' if n <= 3 else 'Common', 'spots': sp}
    hunts = json.load(open(os.path.join(ctx.ROOT, 'data', 'hunts.json')))
    for h in hunts:
        h['creatures'] = [s for s in h['creatures'] if s in cards]
    trips = json.load(open(os.path.join(ctx.ROOT, 'data', 'road_trips.json')))
    with open(os.path.join(D, 'roadtrip.json'), 'w') as f:
        json.dump({'stops': stops, 'cards': cards, 'hunts': hunts, 'checkin_km': CHECKIN_KM,
                   'trips': {t['slug']: {'title': t['title'], 'waypoints': t['waypoints'], 'route': t['route']} for t in trips}}, f, separators=(',', ':'), ensure_ascii=False)
    print(f'road trip: {len(stops)} stops, {len(cards)} cards')

    head = (f'<link rel="stylesheet" href="{U("/static/roadtrip.css")}"><link rel="stylesheet" href="{U("/static/cards.css")}">'
            '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">')
    cfg = lambda extra='': (f'<script type="application/json" id="rt-config">{json.dumps({"data": U("/data/roadtrip.json"), "cities": U("/data/cities.json"), "tiles": U("/data/near/"), "cards": U("/cards/"), "api": "https://api.encounteratlas.com", "living": sorted(LIVING), **(extra or {})})}</script>'
                            f'<script src="{U("/static/cards.js")}" defer></script><script src="{U("/static/roadtrip.js")}" defer></script>')

    def card_html(slug, c, hunt=False):
        art = f'<img src="{c["art"]}" alt="" width="96" height="96" loading="lazy">' if c['art'] else ctx.badge(ctx.by_slug[slug], 'lg')
        return (f'<li class="cc cat-{c["c"]}{" cc-hunt" if hunt else ""}" data-card="{slug}"><a href="{U("/creatures/" + slug + "/")}">'
                f'<span class="cc-art">{art}</span><span class="cc-name">{E(c["n"])}</span>'
                f'<span class="cc-meta"><span class="cc-r cc-r-{c["r"].lower()}">{c["r"]}</span> {len(c["spots"])} spot{"s" if len(c["spots"]) != 1 else ""}</span>'
                f'<span class="cc-got" hidden>Collected</span></a></li>')

    # ---------- sample trips ----------
    trip_pages = []
    for t in trips:
        samples = densify(t['route'])
        wp_km = [min(samples, key=lambda s: hav(w[1], w[2], s[0], s[1]))[2] for w in t['waypoints']]
        hits = []
        for s in stops:
            b = along(samples, s[1], s[2], CORRIDOR_KM)
            if b:
                hits.append((b[1], b[0], s))
        hits.sort(key=lambda h: (h[0], h[2][3]))
        legs = []
        for i in range(len(t['waypoints']) - 1):
            a, b = wp_km[i], wp_km[i + 1]
            leg = [h for h in hits if a - 0.01 <= h[0] < b or (i == len(t['waypoints']) - 2 and h[0] >= a)]
            if leg:
                legs.append((t['waypoints'][i][0], t['waypoints'][i + 1][0], leg))
        crit = sorted({h[2][6] for h in hits if h[2][6] in cards})
        trip_pages.append((t, len(hits), crit))
        leg_html = ''
        seen = set()
        for frm, to, leg in legs:
            items = ''
            for km, off, s in leg:
                key = (s[3], s[5])
                if key in seen:
                    continue
                seen.add(key)
                lab, col = KIND[s[0]]
                items += (f'<li class="rt-stop k-{s[0]}"><span class="rt-km" data-km="{round(km)}">{round(km)} km</span>'
                          f'<span class="rt-dot" style="--k:{col}" aria-hidden="true"></span><span class="rt-txt"><a href="{s[5]}">{E(s[3])}</a>'
                          f'<small>{lab} · {E(s[4])}{" · " + str(round(off)) + " km off the route" if off >= 5 else ""}</small></span></li>')
            if items:
                leg_html += f'<h3 class="rt-leg">{E(frm.split(",")[0])} to {E(to.split(",")[0])}</h3><ol class="rt-stops">{items}</ol>'
        cards_html = ''.join(card_html(s, cards[s]) for s in crit)
        dirs = 'https://www.google.com/maps/dir/' + '/'.join(f'{w[1]},{w[2]}' for w in t['waypoints'])
        n = len(seen)
        body = f'''
<section class="band band-dark rt-hero"><div class="wrap">
  <p class="crumb"><a href="{U('/road-trip/')}">Road trips</a></p>
  <h1>{E(t['title'])}</h1>
  <p class="lede">{E(t['intro'][0])}</p>
  <ul class="rt-stats"><li><b>{t['km']:,} km</b><span>{round(t['km'] / 1.609344):,} mi</span></li><li><b>{t['hours']:g} h</b><span>of driving</span></li>
    <li><b>{n}</b><span>stops</span></li><li><b>{len(crit)}</b><span>cards to collect</span></li></ul>
  <p class="rt-actions"><a class="btn" href="{U('/road-trip/')}?trip={t['slug']}">Open in the planner</a> <a class="btn btn-ghost" href="{dirs}">Directions</a></p>
</div></section>
<div class="band band-mist"><div class="wrap rt-body">
  <article class="prose">
    <p>{E(t['intro'][1])}</p>
    <div class="rt-mapwrap"><div id="rt-map" class="rt-map" data-trip="{t['slug']}" aria-label="Map of the route and its stops"></div></div>
    <h2>Stops along the way</h2>
    <p class="rt-note">Everything within {CORRIDOR_KM} km of the road, in the order you'll pass it. Distances are from the start.</p>
    {leg_html}
    {f'<h2>Cards you can collect on this trip</h2><p>Stand within {CHECKIN_KM} km of one of these spots and tap "I\'m here" in the planner or on the <a href="{U("/cards/")}">cards page</a> to add the card to your collection.</p><ul class="cc-grid">{cards_html}</ul>' if cards_html else ''}
    <p class="rt-src">Route from OpenStreetMap data (FOSSGIS routing). Always check road conditions, opening hours and festival dates before you go.</p>
  </article>
</div></div>{cfg({"trip": t['slug']})}'''
        ctx.write(f'/road-trip/{t["slug"]}/', ctx.page(f'/road-trip/{t["slug"]}/', t['title'] + ': cryptid and UFO road trip', body,
                  f'{t["title"]}: {n} cryptid, UFO and mystery stops along {t["km"]:,} km, in driving order, with a map and directions.',
                  head_extra=head, noindex=n < 8, article={'published': '2026-10-24'}))

    # ---------- planner ----------
    trip_cards = ''.join(
        f'<li><a href="{U("/road-trip/" + t["slug"] + "/")}"><b>{E(t["title"])}</b><span>{t["km"]:,} km · {n} stops · {len(c)} card{"s" if len(c) != 1 else ""}</span></a></li>'
        for t, n, c in trip_pages)
    body = f'''
<section class="band band-dark rt-hero"><div class="wrap">
  <h1>Cryptid and UFO road trip planner</h1>
  <p class="lede">Put in where you're starting and where you're headed and it'll find every monster museum, famous sighting, mystery spot and old newspaper story along the way, in the order you'll drive past them.</p>
  <form id="rt-form" class="rt-form" autocomplete="off">
    <label for="rt-from">From</label>
    <div class="rt-row"><input id="rt-from" list="rt-cities" placeholder="Town or city" required><button type="button" class="btn btn-ghost btn-sm" id="rt-here">Use my location</button></div>
    <label for="rt-to">To</label>
    <input id="rt-to" list="rt-cities" placeholder="Town or city" required>
    <datalist id="rt-cities"></datalist>
    <fieldset class="rt-chips"><legend>How far off the road you'll go</legend>
      <button type="button" data-km="10" data-mi="5" aria-pressed="false">10 km</button><button type="button" data-km="25" data-mi="15" aria-pressed="false">25 km</button>
      <button type="button" data-km="40" data-mi="25" aria-pressed="true">40 km</button><button type="button" data-km="80" data-mi="50" aria-pressed="false">80 km</button>
      <button type="button" class="rt-unit" aria-pressed="false">Miles</button></fieldset>
    <button type="submit" class="btn">Plan my trip</button>
  </form>
  <p id="rt-status" class="rt-status" aria-live="polite"></p>
</div></section>
<div class="band band-mist" id="rt-out" hidden><div class="wrap">
  <div class="rt-mapwrap"><div id="rt-map" class="rt-map" aria-label="Map of your route and its stops"></div></div>
  <div id="rt-results"></div>
</div></div>
<div class="band band-mist"><div class="wrap prose rt-about">
  <h2>Trips to start with</h2>
  <ul class="rt-trips">{trip_cards}</ul>
  <h2>How it works</h2>
  <p>The route comes from OpenStreetMap, and then we check every place to visit, famous creature case, mystery, close encounter and old newspaper story on the site against it. You also get a count of the Air Force UFO files, FAA pilot reports and Canadian UFO Survey towns along the road, so you know which stretches have the most going on.</p>
  <p>Your start and end points stay in your browser (they only go to the routing server as coordinates rounded to about a kilometre). Save a trip and it's kept on your phone, so it still works when you lose signal out in the middle of nowhere.</p>
  <h2>Collect the cards</h2>
  <p>Every creature with a real spot you can visit has a card. When you're within {CHECKIN_KM} km of one of those spots, tap "I'm here" and it goes in your collection. There's no account and nothing to sign up for. See them all on the <a href="{U('/cards/')}">cards page</a>.</p>
</div></div>{cfg()}'''
    ctx.write('/road-trip/', ctx.page('/road-trip/', 'Cryptid and UFO road trip planner', body,
              'Plan a road trip past every Bigfoot museum, UFO site, famous monster sighting and mystery along your route, anywhere in the world. Free, no sign-up.',
              head_extra=head))

    # ---------- cards (page builder in _cards.py) ----------
    spec = importlib.util.spec_from_file_location('ea_cards_page', os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cards.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.build_cards(ctx, cards, hunts, CHECKIN_KM)

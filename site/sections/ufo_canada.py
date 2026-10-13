"""Canadian UFO sightings, 1989 to 2025: /ufo/canada/, /ufo/canada/<province>/, /ufo/canada/<province>/<town>/.

Data: data/ufo_cases_canada.json (collector/cufos.py), from the Canadian UFO Survey compiled by Ufology Research.
Mike's rules: credit the survey by name but don't link to it; rows it took from MUFON, NUFORC or Enigma are already
left out by the collector, and the survey's own source codes are never shown.
Writes OUT/data/ufo_canada.geojson (light, for the hub and the main map) and OUT/data/ufo_canada_<a1>.geojson (full
notes, one per province).
"""
import json, os
from collections import Counter, defaultdict

CREDIT = 'the Canadian UFO Survey, compiled each year since 1989 by Ufology Research of Winnipeg'
MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
TYPE_NAME = {'nl': 'Light at night', 'nd': 'Object at night', 'dd': 'Object by day', 'c1': 'Close encounter', 'c2': 'Close encounter, traces left',
             'c3': 'Close encounter, beings seen', 'c4': 'Abduction claim', 'rd': 'Seen on radar', 'ph': 'Photo or video', 'ux': 'Unusual event'}
EVAL = {'u': ('Unexplained', 'u'), 'p': ('Possibly explained', 'p'), 'i': ('Not enough information', 'i'), 'e': ('Explained', 'e')}
TOWN_MIN = 25  # towns with at least this many reports get their own page
PROV_LIST = 300  # latest reports listed on a province page (all of them are on its map)


def fmt(d):
    p = d.split('-')
    if len(p) == 3:
        return f'{MONTHS[int(p[1])][:3]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MONTHS[int(p[1])]} {p[0]}'
    return p[0]


def build(ctx):
    E, U = ctx.esc, ctx.url
    p = os.path.join(ctx.ROOT, 'data', 'ufo_cases_canada.json')
    if not os.path.exists(p):
        return
    cases = json.load(open(p, encoding='utf-8'))
    cases.sort(key=lambda r: (r['date'], r['time']), reverse=True)
    css = (f'<link rel="stylesheet" href="{U("/static/ufo_archive.css")}"><link rel="stylesheet" href="{U("/static/ufo_canada.css")}">'
           '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>')
    js = f'<script src="{U("/static/ufo_archive.js")}" defer></script><script src="{U("/static/ufo_canada.js")}" defer></script>'
    by_prov = defaultdict(list)
    for r in cases:
        by_prov[r['prov']].append(r)
    pslug = {pv: ctx.slugify(pv) for pv in by_prov}
    town_key = lambda r: (r['prov'], r['place'].strip().lower())
    towns = Counter(town_key(r) for r in cases if r['precision'] == 'place' and r['place'])
    town_name = {}
    for r in cases:
        if r['precision'] == 'place' and r['place']:
            town_name.setdefault(town_key(r), r['place'])
    town_pages = {k for k, n in towns.items() if n >= TOWN_MIN}
    tslug = {k: ctx.slugify(town_name[k]) for k in town_pages}

    def town_url(r):
        k = town_key(r)
        return U(f'/ufo/canada/{pslug[r["prov"]]}/{tslug[k]}/') if k in town_pages else ''

    # --- GeoJSON ---------------------------------------------------------------------------------
    def feat(r, full):
        props = {'w': r['date'], 't': r['place'] or r['prov'], 'e': r['eval'] or 'i', 'a': 0 if r['precision'] == 'place' else 1}
        if full:
            props.update({'r': r['prov'], 'd': r['note'][:220], 'h': ', '.join(x for x in (r.get('colour'), r.get('shape')) if x),
                          'k': TYPE_NAME.get(r['type'], '')})
        tu = town_url(r)
        if tu:
            props['u'] = tu
        return {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [r['lon'], r['lat']]}, 'properties': props}

    # Light file for the hub and the main map: one dot per town, with its counts (clusters sum them).
    os.makedirs(os.path.join(ctx.OUT, 'data'), exist_ok=True)
    spots = {}
    for r in cases:
        k = (r['lat'], r['lon'])
        s_ = spots.setdefault(k, {'t': r['place'] if r['precision'] == 'place' else r['prov'], 'r': r['prov'], 'n': 0, 'nu': 0,
                                  'a': 0 if r['precision'] == 'place' else 1, 'u': town_url(r) or U(f'/ufo/canada/{pslug[r["prov"]]}/')})
        s_['n'] += 1
        s_['nu'] += r['eval'] == 'u'
    with open(os.path.join(ctx.OUT, 'data', 'ufo_canada.geojson'), 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]}, 'properties': v} for (lat, lon), v in spots.items()]},
            f, separators=(',', ':'))
    for pv, rs in by_prov.items():
        with open(os.path.join(ctx.OUT, 'data', f'ufo_canada_{rs[0]["a1"]}.geojson'), 'w') as f:
            json.dump({'type': 'FeatureCollection', 'features': [feat(r, True) for r in rs]}, f, separators=(',', ':'))

    # --- shared bits -----------------------------------------------------------------------------
    def mapbox(src, label, bounds, cluster=True):
        towns = src == 'ufo_canada'
        return (f'<div class="cu-map" data-geojson="{U("/data/" + src + ".geojson")}" data-bounds="{bounds}" data-cluster="{1 if cluster else 0}" data-towns="{1 if towns else 0}" '
                f'role="img" aria-label="{E(label)}"></div>' + (
                '<p class="cu-legend"><span><i class="cu-e-p"></i>Town (bigger = more reports)</span><span><i class="cu-e-u"></i>Many unexplained</span>'
                '<span><i style="background:#8E8CF0"></i>Group of towns: tap to zoom in</span></p>' if towns else
                '<p class="cu-legend"><span><i class="cu-e-u"></i>Unexplained</span><span><i class="cu-e-i"></i>Not enough information</span>'
                '<span><i class="cu-e-p"></i>Possibly explained</span><span><i class="cu-e-e"></i>Explained</span></p>'))

    def bounds(rs):
        pts = [(r['lon'], r['lat']) for r in rs if r['precision'] == 'place']
        if not pts:
            return '-141,41,-52,70'
        xs, ys = sorted(x for x, _ in pts), sorted(y for _, y in pts)
        lo, hi = len(xs) // 100, len(xs) - 1 - len(xs) // 100  # ignore the odd far-flung outlier
        return f'{xs[lo] - .6:.2f},{ys[lo] - .4:.2f},{xs[hi] + .6:.2f},{ys[hi] + .4:.2f}'

    def bars(rs):
        years = Counter(int(r['date'][:4]) for r in rs)
        ymax = max(years.values())
        return ('<div class="bars" role="img" aria-label="Bar chart of reports per year">' +
                ''.join(f'<div class="bar" style="--h:{round(100 * years.get(y, 0) / ymax)}%" title="{y}: {years.get(y, 0)} reports">'
                        f'<span class="bar-n">{years.get(y, 0)}</span><span class="bar-y">&#8217;{str(y)[2:]}</span></div>'
                        for y in range(1989, max(years) + 1)) + '</div>')

    def item(r, show_prov=False, link=True):
        ev, cls = EVAL.get(r['eval'], ('', 'i'))
        what = ' · '.join(x for x in (TYPE_NAME.get(r['type'], ''), ', '.join(x for x in (r.get('colour'), r.get('shape')) if x),
                                      (f'{r["wit"]} witness' + ('es' if r['wit'] != 1 else '')) if r.get('wit') else '',
                                      (f'{r["dur"] // 60} min' if r['dur'] >= 120 else f'{r["dur"]} sec') if r.get('dur') else '') if x)
        place = r['place'] or 'Place not given'
        tu = town_url(r) if link else ''
        pl = f'<a href="{tu}">{E(place)}</a>' if tu else E(place)
        where = pl + (f', {E(r["prov"])}' if show_prov else '')
        hay = ' '.join([place, r['prov'], r['note'], what, ev]).lower()
        tm = f' <span class="muted">{r["time"]}</span>' if r['time'] else ''
        badge = f'<span class="cu-ev cu-e-{cls}">{ev}</span>' if ev else ''
        note = f'<p class="cu-note">{E(r["note"])}</p>' if r['note'] else ''
        approx = '<p class="muted small">Placed in the middle of the province: the town was not found.</p>' if r['precision'] != 'place' else ''
        return (f'<li class="ua-faa cu-case" data-hay="{E(hay)}"><div class="ua-faa-h"><span class="ua-faa-d">{E(fmt(r["date"]))}{tm}</span>'
                f'<strong>{where}</strong>{badge}</div><p class="ua-faa-what">{E(what)}</p>{note}{approx}</li>')

    def caselist(rs, n_total, placeholder, limit=30, show_prov=False, link=True):
        return (f'<div class="ua-filter"><label class="visually-hidden" for="ua-q">Search reports</label>'
                f'<input id="ua-q" type="search" placeholder="{E(placeholder)}" autocomplete="off"><p class="ua-count" aria-live="polite"></p></div>'
                f'<ol class="ua-faas" data-filter-list data-limit="{limit}">{"".join(item(r, show_prov, link) for r in rs)}</ol>'
                f'<p class="ua-more"><button type="button" class="btn" data-more>Show more reports</button></p><p class="empty" hidden>No report matches.</p>')

    def evbar(rs):
        c = Counter(r['eval'] or 'i' for r in rs)
        n = sum(c.values())
        segs = ''.join(f'<span class="cu-e-{k}" style="flex:{c[k]}" title="{EVAL[k][0]}: {c[k]:,}"></span>' for k in 'upie' if c[k])
        keys = ''.join(f'<li><i class="cu-e-{k}"></i><b>{round(100 * c[k] / n)}%</b> {EVAL[k][0].lower()}</li>' for k in 'upie' if c[k])
        return f'<div class="cu-evbar" role="img" aria-label="How the reports were rated">{segs}</div><ul class="cu-evkey">{keys}</ul>'

    def shapes(rs, n=8):
        c = Counter(r['shape'] for r in rs if r.get('shape') and r['shape'] not in ('point of light', 'light', 'lights'))
        top = c.most_common(n)
        if not top:
            return ''
        mx = top[0][1]
        return ('<ul class="cu-hbars">' + ''.join(f'<li><span>{E(s[:1].upper() + s[1:])}</span><i style="--w:{round(100 * v / mx)}%"></i><b>{v:,}</b></li>'
                                                for s, v in top) + '</ul>')

    def hilite(rs, n):
        """Most striking cases: rated unexplained, close encounters and radar first, then strangeness, newest first."""
        pick = [r for r in rs if r['eval'] == 'u' and r['note']]
        pick.sort(key=lambda r: (r['type'] in ('c1', 'c2', 'c3', 'c4', 'rd'), r.get('strange') or 0, r['date']), reverse=True)
        return pick[:n]

    about = (f'<h2>About this data</h2><p>These reports come from {CREDIT}. Each year the survey gathers sightings sent to police, '
             f'airports, the military, researchers and UFO groups across the country, and rates each one. We left out every report the survey received from MUFON, NUFORC or Enigma Labs, so the totals here are lower than in the survey itself.</p>'
             f'<p>The ratings are the survey\'s: <b>explained</b> means a likely cause was found (a plane, a planet, a satellite re-entry), '
             f'<b>possibly explained</b> means there\'s a good guess, and <b>unexplained</b> means the investigators couldn\'t find one. '
             f'Notes are short summaries, lightly tidied. Most places are the nearest town, not the exact spot.</p>')

    # --- /ufo/canada/ ----------------------------------------------------------------------------
    n = len(cases)
    n_u = sum(1 for r in cases if r['eval'] == 'u')
    n_ce = sum(1 for r in cases if r['type'] in ('c1', 'c2', 'c3', 'c4'))
    y0 = min(int(r['date'][:4]) for r in cases)
    yc = Counter(int(r['date'][:4]) for r in cases)
    peak = max(yc, key=yc.get)
    provs = sorted(by_prov.items(), key=lambda kv: -len(kv[1]))
    pgrid = ''.join(f'<li><a href="{U("/ufo/canada/" + pslug[pv] + "/")}"><b>{E(pv)}</b><span>{len(rs):,} reports</span>'
                    f'<small>{sum(1 for r in rs if r["eval"] == "u"):,} unexplained</small></a></li>' for pv, rs in provs)
    top_towns = sorted(town_pages, key=lambda k: -towns[k])[:36]
    tlist = ''.join(f'<li><a href="{U(f"/ufo/canada/{pslug[k[0]]}/{tslug[k]}/")}">{E(town_name[k])}</a> <span class="muted">{towns[k]:,}</span></li>'
                    for k in top_towns)
    best = hilite(cases, 60)
    body = f'''
<section class="band band-dark ua-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/ufo/')}">UFOs</a> / <a href="{U('/ufo/countries/canada/')}">Canada</a> / Sightings map</p>
    <h1>UFO sightings in Canada, 1989 to today</h1>
    <p class="lede">{n:,} UFO reports from every province and territory, put on one map. Each has a date, a place and the investigators' verdict.
    Find the sightings near you, see which towns report the most, and read the {n_u:,} that nobody could explain.</p>
    <ul class="ua-stats"><li><b>{n:,}</b> reports</li><li><b>{n_u:,}</b> unexplained</li><li><b>{n_ce:,}</b> close encounters</li><li><b>{peak}</b> busiest year</li></ul>
  </div>
</section>
<div class="band band-dark cu-mapband"><div class="wrap">{mapbox('ufo_canada', 'Map of UFO sightings across Canada', '-141,41,-52,70')}
<p class="small muted">Zoom in to split the clusters; tap a dot for the town. <button type="button" class="linkbtn" data-locate-cu>Show reports near me</button></p></div></div>
<div class="band band-mist"><div class="wrap">
  <h2>By province and territory</h2>
  <ul class="cu-pgrid">{pgrid}</ul>
  <div class="cu-two">
    <section><h2>How the reports were rated</h2>{evbar(cases)}
      <p>Most sightings turn out to have an ordinary cause, often a plane, a bright planet or a satellite. The survey marks a report <b>unexplained</b> only when the investigators ran out of explanations.</p></section>
    <section><h2>What people saw</h2>{shapes(cases)}<p class="small muted">Not counted: plain points of light, the most common report by far.</p></section>
  </div>
  <h2>Reports by year</h2>
  <p>Sightings climbed through the 2000s and peaked in {peak} with {yc[peak]:,} reports. Since 2019 a new kind of report keeps turning up: lines of lights crossing the sky, which is how Starlink satellites look just after launch.</p>
  {bars(cases)}
  <h2>Towns with the most reports</h2>
  <p>Big cities lead because more people are looking up. Each town has its own page with its map and reports.</p>
  <ul class="cols">{tlist}</ul>
  <h2>Unexplained cases worth reading</h2>
  <p>Close encounters, radar cases and the strangest sightings the investigators could not explain, newest first.</p>
  {caselist(best, len(best), 'Search these cases: triangle, landed, Winnipeg...', limit=20, show_prov=True)}
  {about}
  <p>More on Canada: <a href="{U('/ufo/countries/canada/')}">Canada's official UFO files</a> · <a href="{U('/ufo/blue-book/')}">US Air Force files that mention Canada</a> · <a href="{U('/report/')}">Report your own sighting</a></p>
</div></div>{js}'''
    ctx.write('/ufo/canada/', ctx.page('/ufo/canada/', 'UFO sightings in Canada: map of reports since 1989', body,
                                       f'Map of {n:,} UFO sightings in Canada from 1989 to {max(yc)}, by province and town, with {n_u:,} unexplained cases and close encounters.',
                                       head_extra=css))

    # --- /ufo/canada/<province>/ -----------------------------------------------------------------
    for pv, rs in provs:
        pu = sum(1 for r in rs if r['eval'] == 'u')
        ptowns = sorted((k for k in towns if k[0] == pv), key=lambda k: -towns[k])
        def tlink(k):
            return f'<a href="{U(f"/ufo/canada/{pslug[k[0]]}/{tslug[k]}/")}">{E(town_name[k])}</a>' if k in town_pages else E(town_name[k])
        tl = ''.join(f'<li>{tlink(k)} <span class="muted">{towns[k]:,}</span></li>' for k in ptowns[:60])
        yc = Counter(int(r['date'][:4]) for r in rs)
        peak = max(yc, key=yc.get)
        lead = ptowns[0] if ptowns else None
        others = ''.join(f'<a class="md-chip" href="{U("/ufo/canada/" + pslug[o] + "/")}">{E(o)}</a>' for o, _ in provs if o != pv)
        best = hilite(rs, 12)
        best_html = (f'<h2>Unexplained cases worth reading</h2><ol class="ua-faas">{"".join(item(r) for r in best)}</ol>') if best else ''
        body = f'''
<section class="band band-dark ua-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/ufo/')}">UFOs</a> / <a href="{U('/ufo/canada/')}">Canada sightings</a> / {E(pv)}</p>
    <h1>UFO sightings in {E(pv)}</h1>
    <p class="lede">{len(rs):,} UFO reports from {E(pv)} since {min(yc)}{f", most of them from {E(town_name[lead])}" if lead and towns[lead] > len(rs) * .25 else ""}. {pu:,} were never explained.</p>
    <ul class="ua-stats"><li><b>{len(rs):,}</b> reports</li><li><b>{pu:,}</b> unexplained</li><li><b>{len(ptowns):,}</b> towns</li><li><b>{peak}</b> busiest year</li></ul>
  </div>
</section>
<div class="band band-dark cu-mapband"><div class="wrap">{mapbox(f'ufo_canada_{rs[0]["a1"]}', f'Map of UFO sightings in {pv}', bounds(rs), cluster=len(rs) > 400)}</div></div>
<div class="band band-mist"><div class="wrap">
  <div class="cu-two">
    <section><h2>How the reports were rated</h2>{evbar(rs)}</section>
    <section><h2>What people saw</h2>{shapes(rs, 6)}</section>
  </div>
  <h2>Reports by year</h2>{bars(rs)}
  {best_html}
  <h2>Towns</h2><ul class="cols">{tl}</ul>
  <h2>Latest reports from {E(pv)}</h2>
  <p>The {min(len(rs), PROV_LIST):,} most recent{f" of {len(rs):,}" if len(rs) > PROV_LIST else ""}. Every report is on the map above, and each town in the list has its own page.</p>
  {caselist(rs[:PROV_LIST], len(rs), f'Search the latest {min(len(rs), PROV_LIST):,} reports: town, triangle, orange...')}
  {about}
  <h2>Other provinces and territories</h2><p class="md-chips">{others}</p>
</div></div>{js}'''
        ctx.write(f'/ufo/canada/{pslug[pv]}/', ctx.page(f'/ufo/canada/{pslug[pv]}/', f'UFO sightings in {pv}: map and reports', body,
                                                       f'{len(rs):,} UFO sightings in {pv} since {min(yc)}, mapped by town, with {pu:,} unexplained cases and every report listed.',
                                                       head_extra=css))

    # --- /ufo/canada/<province>/<town>/ ----------------------------------------------------------
    for k in town_pages:
        pv = k[0]
        rs = [r for r in by_prov[pv] if town_key(r) == k]
        name = town_name[k]
        pu = sum(1 for r in rs if r['eval'] == 'u')
        yc = Counter(int(r['date'][:4]) for r in rs)
        peak = max(yc, key=yc.get)
        lat, lon = rs[0]['lat'], rs[0]['lon']
        near = sorted((t for t in town_pages if t != k),
                      key=lambda t: (next(r for r in by_prov[t[0]] if town_key(r) == t)['lat'] - lat) ** 2 +
                                    ((next(r for r in by_prov[t[0]] if town_key(r) == t)['lon'] - lon) * .6) ** 2)[:8]
        nearby = ''.join(f'<a class="md-chip" href="{U(f"/ufo/canada/{pslug[t[0]]}/{tslug[t]}/")}">{E(town_name[t])}</a>' for t in near)
        sh = Counter(r['shape'] for r in rs if r.get('shape') and r['shape'] not in ('point of light', 'light', 'lights')).most_common(1)
        best = hilite(rs, 6)
        body = f'''
<section class="band band-dark ua-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/ufo/canada/')}">Canada sightings</a> / <a href="{U('/ufo/canada/' + pslug[pv] + '/')}">{E(pv)}</a> / {E(name)}</p>
    <h1>UFO sightings in {E(name)}, {E(pv)}</h1>
    <p class="lede">{len(rs):,} UFO reports from {E(name)} since {min(yc)}. The busiest year was {peak}, with {yc[peak]}.
    {f"The most common shape after plain lights: {E(sh[0][0])}." if sh else ""} {pu:,} {"was" if pu == 1 else "were"} never explained.</p>
    <ul class="ua-stats"><li><b>{len(rs):,}</b> reports</li><li><b>{pu:,}</b> unexplained</li><li><b>{min(yc)}</b> first report</li><li><b>{max(yc)}</b> latest</li></ul>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <div class="cu-two">
    <section><h2>How the reports were rated</h2>{evbar(rs)}</section>
    <section><h2>Reports by year</h2>{bars(rs)}</section>
  </div>
  {f'<h2>Unexplained cases worth reading</h2><ol class="ua-faas">{"".join(item(r, link=False) for r in best)}</ol>' if best else ''}
  <h2>Every report from {E(name)}</h2>
  {caselist(rs, len(rs), f'Search {len(rs):,} reports: triangle, orange, hovering...', link=False)}
  <p class="cu-cta"><a class="btn" href="{U('/report/')}">Seen something over {E(name)}? Report it</a>
  <a class="btn btn-ghost" href="{U('/guides/skywatching/')}">How to tell a UFO from a plane or satellite</a></p>
  <h2>Nearby towns</h2><p class="md-chips">{nearby}</p>
  {about}
</div></div>{js}'''
        path = f'/ufo/canada/{pslug[pv]}/{tslug[k]}/'
        ctx.write(path, ctx.page(path, f'UFO sightings in {name}, {pv}', body,
                                 f'{len(rs):,} UFO sightings reported in {name}, {pv} since {min(yc)}, with dates, shapes, what investigators concluded and {pu:,} unexplained cases.',
                                 head_extra=css))

    # --- home search: provinces and town pages ---------------------------------------------------
    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if os.path.exists(sp):
        items = json.load(open(sp, encoding='utf-8'))
        items += [{'t': f'UFO sightings: {pv}', 'a': pv + ' canada', 'k': f'{len(rs):,} reports since 1989', 'u': U(f'/ufo/canada/{pslug[pv]}/'),
                   'i': 'saucer', 'c': 'ufo'} for pv, rs in provs]
        items += [{'t': f'UFO sightings: {town_name[k]}, {k[0]}', 'a': town_name[k] + ' ' + k[0], 'k': f'{towns[k]:,} reports',
                   'u': U(f'/ufo/canada/{pslug[k[0]]}/{tslug[k]}/'), 'i': 'saucer', 'c': 'ufo'} for k in town_pages]
        with open(sp, 'w', encoding='utf-8') as f:
            json.dump(items, f, separators=(',', ':'))

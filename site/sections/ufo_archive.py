"""Official UFO releases archive: /ufo/releases/, /ufo/countries/, /ufo/files/faa/, /ufo/files/pursue/.

Data (all hand-checked or collected from official sources):
  data/ufo_releases.json    index of official releases worldwide (hand-written, every item links to its source)
  data/ufo_countries.json   short official history per country (hand-written)
  data/ufo_rg615.json       National Archives Record Group 615 series and items (collector/ufo_rg615.py)
  data/ufo_cases_faa.json   FAA pilot UAP reports from RG 615, geocoded (collector/ufo_rg615.py)
  data/ufo_cases_pursue.json  Department of War PURSUE releases, geocoded (collector/ufo_pursue.py)
Writes OUT/data/ufo_faa.geojson and OUT/data/ufo_pursue.geojson for the maps.
"""
import json, os, re
from collections import Counter, defaultdict

TYPES = {
    'documents': ('Documents', 'folder'), 'report': ('Reports', 'ufo-report'), 'videos': ('Videos', 'ufo-film'),
    'hearing': ('Hearings', 'ufo-hearing'), 'dataset': ('Datasets', 'ufo-dataset'),
}
TYPE_ONE = {'documents': 'Documents', 'report': 'Report', 'videos': 'Videos', 'hearing': 'Hearing', 'dataset': 'Dataset'}
KIND = {'document': ('Document', 'ufo-report'), 'video': ('Video', 'ufo-film'), 'image': ('Image', 'saucer'),
        'audio': ('Audio', 'ufo-hearing')}
MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December']
MAPLIBRE = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>')
APPROX = {'region', 'country', 'area', 'facility'}
# Countries that appear only as places in the US files. GeoNames calls a few of them by long names.
SHORT_NAMES = {'The Netherlands': 'Netherlands'}


def load(ctx, name, default):
    p = os.path.join(ctx.ROOT, 'data', name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


def fmt_date(d):
    if not d:
        return 'Undated'
    p = d.split('T')[0].split('-')
    if len(p) == 3:
        return f'{MONTHS[int(p[1])]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MONTHS[int(p[1])]} {p[0]}'
    return p[0]


def short_date(d):
    if not d:
        return 'Undated'
    p = d.split('T')[0].split('-')
    if len(p) == 3:
        return f'{MONTHS[int(p[1])][:3]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MONTHS[int(p[1])][:3]} {p[0]}'
    return p[0]


def build(ctx):
    E, U = ctx.esc, ctx.url
    releases = load(ctx, 'ufo_releases.json', [])
    if not releases:
        return
    countries = load(ctx, 'ufo_countries.json', [])
    rg615 = load(ctx, 'ufo_rg615.json', {'series': []})
    faa = load(ctx, 'ufo_cases_faa.json', [])
    pursue = load(ctx, 'ufo_cases_pursue.json', [])
    css = f'<link rel="stylesheet" href="{U("/static/ufo_archive.css")}">'
    js = f'<script src="{U("/static/ufo_archive.js")}" defer></script>'
    by_code = {c['code']: c for c in countries}
    series = {s['naId']: s for s in rg615.get('series', [])}
    releases.sort(key=lambda r: (r.get('date') or '0000'), reverse=True)

    # --- countries known from located case records (PURSUE places outside the US) ---------------
    cname = {c['code']: c['name'] for c in countries}
    for o in pursue:
        cc = (o.get('cc') or '').lower()
        if cc and cc not in cname and o['precision'] in ('country', 'place'):
            cname[cc] = SHORT_NAMES.get(o['region'], o['region'])
    cslug = {cc: (by_code[cc]['slug'] if cc in by_code else ctx.slugify(n)) for cc, n in cname.items()}
    rel_by_cc = defaultdict(list)
    for r in releases:
        rel_by_cc[r['country']].append(r)
    pursue_by_cc = defaultdict(list)
    for o in pursue:
        if o.get('cc'):
            pursue_by_cc[o['cc'].lower()].append(o)

    def cpill(cc, link=True):
        name = cname.get(cc, cc.upper())
        inner = f'<span class="ua-cc">{E(cc.upper())}</span>{E(name)}'
        return (f'<a class="ua-country" href="{U("/ufo/countries/" + cslug[cc] + "/")}">{inner}</a>' if link and cc in cslug
                else f'<span class="ua-country">{inner}</span>')

    def tbadge(t, size='sm'):
        return f'<span class="ua-tb ua-tb-{size} ua-t-{t}">{ctx.icon(TYPES[t][1])}</span>'

    def ext(url, text):
        return f'<a class="ua-ext" href="{E(url)}" rel="noopener">{E(text)}<span aria-hidden="true"> &#8599;</span></a>'

    def rel_card(r, compact=False):
        t = r['type']
        size = f'<span class="ua-size">{E(r["size"])}</span>' if r.get('size') else ''
        why = '' if compact else f'<p class="ua-why"><strong>Why it matters:</strong> {E(r["why"])}</p>'
        hay = ' '.join([r['title'], r['agency'], r['summary'], cname.get(r['country'], ''), r.get('period', '')]).lower()
        return (f'<li class="ua-rel" data-type="{t}" data-country="{r["country"]}" data-hay="{E(hay)}">'
                f'<span class="ua-when">{E(short_date(r.get("date")))}</span>'
                f'<div class="ua-card">{tbadge(t)}<div class="ua-card-txt">'
                f'<p class="ua-meta">{cpill(r["country"])}<span class="ua-type">{E(TYPE_ONE[t])}</span>{size}</p>'
                f'<h3><a href="{U("/ufo/releases/" + r["slug"] + "/")}">{E(r["title"])}</a></h3>'
                f'<p class="ua-agency">{E(r["agency"])}</p><p class="ua-sum">{E(r["summary"])}</p>{why}'
                f'<p class="ua-links">{ext(r["url"], "Official source")}'
                f'<a href="{U("/ufo/releases/" + r["slug"] + "/")}">Details</a></p></div></div></li>')

    def timeline(items, compact=False):
        out, year = '', None
        for r in items:
            y = (r.get('date') or '')[:4] or 'Undated'
            if y != year:
                if year is not None:
                    out += '</ol></section>'
                out += f'<section class="ua-year" data-year="{y}"><h2 class="ua-year-h">{y}</h2><ol class="ua-tl">'
                year = y
            out += rel_card(r, compact)
        return out + ('</ol></section>' if year is not None else '')

    # --- GeoJSON for the maps ----------------------------------------------------------------
    def feat(lat, lon, props):
        return {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(lon, 4), round(lat, 4)]}, 'properties': props}

    faa_feats = []
    for r in faa:
        if r.get('lat') is None:
            continue
        what = ' '.join(x for x in (r.get('flight'), r.get('aircraft')) if x)
        faa_feats.append(feat(r['lat'], r['lon'], {
            'id': r['id'], 't': r.get('loc') or r.get('region') or 'Unknown place', 'r': r.get('region') or '',
            'w': (r.get('date') or '')[:10], 'y': int((r.get('date') or '0')[:4] or 0), 'a': 1 if r['precision'] in APPROX else 0,
            'k': 'faa', 'f': what, 'd': r['text'][:180] + ('...' if len(r['text']) > 180 else ''),
            'u': r['pdf'], 's': 'FAA pilot report'}))
    pursue_feats = []
    for o in pursue:
        if o.get('lat') is None:
            continue
        pursue_feats.append(feat(o['lat'], o['lon'], {
            'id': o['id'], 't': o['title'][:90], 'r': o['loc'], 'w': o.get('date_label') or '', 'y': int((o.get('date') or '0')[:4] or 0),
            'a': 1 if o['precision'] in APPROX else 0, 'k': o['kind'], 'u': o['url'], 's': o['agency'] + ', PURSUE release ' + str(o['tranche'])}))
    os.makedirs(os.path.join(ctx.OUT, 'data'), exist_ok=True)
    for name, feats in (('ufo_faa', faa_feats), ('ufo_pursue', pursue_feats)):
        with open(os.path.join(ctx.OUT, 'data', name + '.geojson'), 'w') as f:
            json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'))

    def mapbox(sources, label, height='tall', fit=True, bounds=''):
        src = ','.join(U('/data/' + s + '.geojson') for s in sources)
        return (f'<div class="ua-map ua-map-{height}" data-geojson="{src}" data-fit="{1 if fit else 0}" '
                f'data-bounds="{E(bounds)}" data-label="{E(label)}" role="img" aria-label="{E(label)}"></div>')

    n_mapped = len(faa_feats) + len(pursue_feats)
    n_countries = len({r['country'] for r in releases})

    # --- /ufo/releases/ ------------------------------------------------------------------------
    decades = defaultdict(list)
    for r in releases:
        if r.get('date'):
            decades[int(r['date'][:3]) * 10].append(r)
    dmax = max(len(v) for v in decades.values())
    strip = ''
    for d in range(min(decades), 2030, 10):
        dots = ''.join(f'<a class="ua-dot ua-t-{r["type"]}" href="#r-{r["slug"]}" title="{E(short_date(r["date"]) + ": " + r["title"])}">'
                       f'<span class="visually-hidden">{E(r["title"])}</span></a>'
                       for r in sorted(decades.get(d, []), key=lambda r: r['date']))
        strip += (f'<div class="ua-dec"><div class="ua-dec-dots" style="--n:{dmax}">{dots}</div>'
                  f'<span class="ua-dec-y">{d}s</span><span class="ua-dec-n">{len(decades.get(d, []))}</span></div>')
    legend = ''.join(f'<span><i class="ua-dot ua-t-{k}"></i>{E(v[0])}</span>' for k, v in TYPES.items())
    tchips = ''.join(f'<button type="button" class="chip" data-type="{k}" aria-pressed="false">'
                     f'<i class="ua-dot ua-t-{k}"></i>{E(v[0])}</button>' for k, v in TYPES.items())
    copts = ''.join(f'<option value="{cc}">{E(cname[cc])} ({len(v)})</option>'
                    for cc, v in sorted(rel_by_cc.items(), key=lambda kv: (-len(kv[1]), cname[kv[0]])))
    first = min(r['date'] for r in releases if r.get('date'))[:4]
    cards = timeline(releases)
    # anchor ids for the decade strip
    for r in releases:
        cards = cards.replace(f'<a href="{U("/ufo/releases/" + r["slug"] + "/")}">{E(r["title"])}</a></h3>',
                              f'<a id="r-{r["slug"]}" href="{U("/ufo/releases/" + r["slug"] + "/")}">{E(r["title"])}</a></h3>', 1)
    body = f'''
<section class="band band-dark ua-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/ufo/')}">UFO files</a> / Official releases</p>
    <h1>Every official UFO release, on one timeline</h1>
    <p class="lede">Governments have been opening their UFO files since the 1950s. Here are {len(releases)} of the big releases from {n_countries} countries: document dumps, reports to parliament, cockpit videos, hearings and open case databases. Each one links straight to the official source.</p>
    <ul class="ua-stats">
      <li><b>{len(releases)}</b> releases</li><li><b>{n_countries}</b> countries</li>
      <li><b>{first}</b> earliest</li><li><b>{n_mapped:,}</b> case records mapped</li>
    </ul>
    <div class="ua-strip" aria-label="Releases by decade">{strip}</div>
    <p class="ua-legend">{legend}</p>
  </div>
</section>
<div class="band band-mist ua-body"><div class="wrap">
  <div class="ua-filter" role="search">
    <label class="visually-hidden" for="ua-q">Search releases</label>
    <input id="ua-q" type="search" placeholder="Search: Roswell, Navy, Condign, FAA..." autocomplete="off">
    <label class="visually-hidden" for="ua-c">Country</label>
    <select id="ua-c"><option value="">All countries</option>{copts}</select>
    <div class="chips ua-chips" role="group" aria-label="Filter by type">{tchips}</div>
    <p class="ua-count" aria-live="polite"></p>
  </div>
  <div class="ua-list" data-filter-list>{cards}</div>
  <p class="empty" hidden>Nothing matches. Try another word or clear the filters.</p>
  <h2>Browse by country</h2>
  <ul class="ua-cgrid">{''.join(f'<li><a href="{U("/ufo/countries/" + cslug[cc] + "/")}"><span class="ua-cc">{E(cc.upper())}</span>{E(cname[cc])}<span class="muted">{len(v)} release{"s" if len(v) != 1 else ""}</span></a></li>' for cc, v in sorted(rel_by_cc.items(), key=lambda kv: cname[kv[0]]))}</ul>
  <p class="small">Dates are when each release came out, not when the events happened. Summaries are ours; follow the links for the originals.</p>
</div></div>{js}'''
    ctx.write('/ufo/releases/', ctx.page('/ufo/releases/', 'Official UFO releases: a timeline of government disclosure', body,
                                        f'{len(releases)} official UFO and UAP releases from {n_countries} countries, from Project Blue Book to the 2026 Pentagon files, each linked to its source.',
                                        head_extra=css))

    # --- /ufo/releases/<slug>/ -------------------------------------------------------------------
    for r in releases:
        t = r['type']
        facts = [('Country', cpill(r['country'])), ('Released by', E(r['agency'])), ('Released', E(fmt_date(r.get('date')))),
                 ('Covers', E(r.get('period') or '')), ('Type', E(TYPE_ONE[t])), ('Size', E(r.get('size') or '')),
                 ('Reuse', E(r.get('reuse') or ''))]
        dl = ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in facts if v)
        extra = ''.join(f'<li>{ext(l["url"], l["name"])}</li>' for l in r.get('links', []))
        inside = ''
        s = series.get(r.get('rg615'))
        if s and s['items']:
            rows = ''.join(
                f'<li><span class="ua-it-k">{E((i["kind"] or "").replace("Portable Document File (PDF)", "PDF").replace("Video File", "Video") or "File")}</span>'
                f'<span><a href="{E(i["pdf"] or "https://catalog.archives.gov/id/" + str(i["naId"]))}" rel="noopener">{E(i["title"])}</a>'
                + (f'<br><span class="muted">{E(i["note"])}</span>' if i.get('note') else '') +
                f' <a class="muted small" href="https://catalog.archives.gov/id/{i["naId"]}" rel="noopener">catalog</a></span></li>'
                for i in s['items'])
            inside = f'<h2>What is in it</h2><p>All {s["count"]} items in this series, as listed by the National Archives. Links open the scanned file.</p><ul class="ua-items">{rows}</ul>'
        elif r.get('rg615') == 493468575 and faa:
            inside = (f'<h2>What is in it</h2><p>{len(faa)} pilot and controller reports. We have mapped {len(faa_feats)} of them and sorted them by state.</p>'
                      f'<p><a class="btn" href="{U("/ufo/files/faa/")}">Browse the FAA reports</a></p>')
        if r.get('local') and not inside:
            label = {'/ufo/': 'Browse the Blue Book files', '/ufo/files/pursue/': 'Browse all PURSUE files',
                     '/ufo/files/faa/': 'Browse the FAA reports'}.get(r['local'], 'Browse the files')
            inside = f'<h2>Browse it here</h2><p><a class="btn" href="{U(r["local"])}">{label}</a></p>'
        more = [x for x in rel_by_cc[r['country']] if x['slug'] != r['slug']][:6]
        more_html = ''.join(f'<li><span class="yr">{E((x.get("date") or "")[:4])}</span><span><a href="{U("/ufo/releases/" + x["slug"] + "/")}">{E(x["title"])}</a></span></li>' for x in more)
        body = f'''
<section class="band band-dark ua-hero creature-head">
  <div class="wrap creature-head-in">
    {tbadge(t, 'xl')}
    <div>
      <p class="crumb"><a href="{U('/ufo/releases/')}">Official releases</a> / {cpill(r['country'], link=False)}</p>
      <h1>{E(r['title'])}</h1>
      <p class="lede">{E(r['summary'])}</p>
      <p class="ua-cta"><a class="btn" href="{E(r['url'])}" rel="noopener">Open the official source<span aria-hidden="true"> &#8599;</span></a></p>
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap creature-body">
  <article class="prose">
    <h2>Why it matters</h2>
    <p>{E(r['why'])}</p>
    {f'<h2>Related official links</h2><ul class="ua-linklist">{extra}</ul>' if extra else ''}
    {inside}
    {f'<h2>More from {E(cname.get(r["country"], ""))}</h2><ol class="timeline">{more_html}</ol><p><a href="{U("/ufo/countries/" + cslug[r["country"]] + "/")}">The full story in {E(cname.get(r["country"], ""))}</a></p>' if more else ''}
  </article>
  <aside class="facts"><dl>{dl}</dl><p class="more">{ext(r['url'], 'Official source')}</p></aside>
</div></div>'''
        ctx.write(f'/ufo/releases/{r["slug"]}/', ctx.page(f'/ufo/releases/{r["slug"]}/', r['title'], body,
                                                         r['summary'][:155], head_extra=css))

    # --- FAA pilot reports -----------------------------------------------------------------------
    def faa_item(r):
        when = fmt_date(r.get('date'))
        tm = (r.get('date') or '')[11:16]
        what = ' · '.join(x for x in (r.get('flight'), r.get('aircraft'), f'{r["fl"]:,} ft' if r.get('fl') else '') if x)
        flags = ''.join(f'<span class="ua-flag ua-flag-{k}">{v}</span>' for k, v in
                        (('starlink', 'Starlink mentioned'), ('radar', 'Seen on radar')) if r.get(k))
        place = r.get('loc') or (('Near ' + r['from']) if r.get('from') else '') or r.get('region') or 'Place not given'
        hay = ' '.join([place, r.get('region') or '', r['text'], r.get('flight') or '', r.get('aircraft') or '']).lower()
        return (f'<li class="ua-faa" data-hay="{E(hay)}"><div class="ua-faa-h"><span class="ua-faa-d">{E(when)}'
                f'{(" <span class=muted>" + E(tm) + " " + E(r.get("tz") or "") + "</span>") if tm else ""}</span>'
                f'<strong>{E(place)}</strong>{flags}</div>'
                f'<p class="ua-faa-what">{E(what)}</p><p class="ua-tty">{E(r["text"])}</p>'
                f'<p class="ua-faa-src"><a href="{E(r["pdf"])}" rel="noopener">Original report (PDF)</a>'
                f' <a class="muted" href="https://catalog.archives.gov/id/{r["id"]}" rel="noopener">National Archives catalog</a>'
                f'{" <span class=muted>(placed approximately)</span>" if r["precision"] in APPROX else ""}</p></li>')

    if faa:
        by_state = defaultdict(list)
        for r in faa:
            by_state[r.get('region') or 'Place not given'].append(r)
        years = Counter(int(r['date'][:4]) for r in faa if r.get('date'))
        y0, y1 = min(years), max(years)
        ymax = max(years.values())
        bars = ''.join(f'<div class="bar" style="--h:{round(100 * years.get(y, 0) / ymax)}%" title="{y}: {years.get(y, 0)} reports">'
                       f'<span class="bar-n">{years.get(y, 0)}</span><span class="bar-y">&#8217;{str(y)[2:]}</span></div>'
                       for y in range(max(y0, 2007), y1 + 1))
        top = sorted(by_state.items(), key=lambda kv: -len(kv[1]))
        states = ''.join(f'<li><a href="{U("/ufo/files/faa/" + ctx.slugify(k) + "/")}">{E(k)}</a> <span class="muted">{len(v)}</span></li>'
                         for k, v in sorted(by_state.items()) if k != 'Place not given')
        if by_state.get('Place not given'):
            states += f'<li><a href="{U("/ufo/files/faa/place-not-given/")}">No place given</a> <span class="muted">{len(by_state["Place not given"])}</span></li>'
        n_star = sum(1 for r in faa if r.get('starlink'))
        n_radar = sum(1 for r in faa if r.get('radar'))
        fls = [r['fl'] for r in faa if r.get('fl')]
        med = sorted(fls)[len(fls) // 2] if fls else 0
        latest = sorted(faa, key=lambda r: r.get('date') or '', reverse=True)
        body = f'''
<section class="band band-dark ua-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/ufo/releases/')}">Official releases</a> / <a href="{U('/ufo/releases/rg615-faa-uap-reports/')}">FAA records</a></p>
    <div class="ua-head-row">{tbadge('dataset', 'lg')}<h1>What pilots reported to the FAA</h1></div>
    <p class="lede">{len(faa):,} reports of lights and objects called in by airline, cargo and private crews, logged by the Federal Aviation Administration and released through the National Archives in 2025. Here they are on a map.</p>
    <ul class="ua-stats">
      <li><b>{len(faa):,}</b> reports</li><li><b>{y0} to {y1}</b></li><li><b>{med:,} ft</b> typical altitude</li><li><b>{n_star}</b> mention Starlink</li>
    </ul>
  </div>
</section>
{mapbox(['ufo_faa'], 'Map of FAA pilot UAP reports', bounds='-128,22,-64,50')}
<div class="band band-mist"><div class="wrap">
  <h2>Reports by year</h2>
  <p>Most arrived in 2023, after the FAA began routing pilot UAP reports to the Pentagon's new UAP office. Most are brief: a callsign, an altitude and a few words, usually lights. Only {n_radar} say the object also showed up on air traffic control radar.</p>
  <div class="bars" role="img" aria-label="Bar chart of FAA UAP reports per year">{bars}</div>
  <h2>By state</h2>
  <p>{E(top[0][0])} has the most reports ({len(top[0][1])}), then {E(top[1][0])} and {E(top[2][0])}. Reports are placed where the FAA logged the position, or at the town named in the National Archives description.</p>
  <ul class="cols">{states}</ul>
  <h2>Latest reports</h2>
  <div class="ua-filter"><label class="visually-hidden" for="ua-q">Search reports</label>
  <input id="ua-q" type="search" placeholder="Search all {len(faa)} reports: orb, Starlink, Denver, B737..." autocomplete="off"><p class="ua-count" aria-live="polite"></p></div>
  <ol class="ua-faas" data-filter-list data-limit="30">{''.join(faa_item(r) for r in latest)}</ol>
  <p class="ua-more"><button type="button" class="btn" data-more>Show more reports</button></p>
  <p class="empty" hidden>No report matches.</p>
  <h2>About these reports</h2>
  <p>The text is the FAA's own, in its original style: Washington Operations Center logs are in capitals and use aviation shorthand (FL350 means 35,000 feet; ARTCC is a regional air traffic control centre). Times are as logged, local or UTC. Each report links to its scanned original at the National Archives. US federal records are public domain.</p>
</div></div>{js}'''
        ctx.write('/ufo/files/faa/', ctx.page('/ufo/files/faa/', 'FAA pilot UFO reports: map and full text', body,
                                             f'{len(faa)} FAA pilot and air traffic control UAP reports from {y0} to {y1}, mapped and searchable, with links to the National Archives originals.',
                                             head_extra=css + MAPLIBRE))
        bb_regions = {b['region'] for b in ctx.bluebook if b.get('cc') == 'US' and b.get('a1')}

        def bb_link(nm):
            return (f'<a href="{U("/ufo/blue-book/us-" + ctx.slugify(nm) + "/")}">Air Force Blue Book files from {E(nm)}</a>'
                    if nm in bb_regions else f'<a href="{U("/ufo/")}">Air Force Blue Book files</a>')

        for st, rs in by_state.items():
            rs = sorted(rs, key=lambda r: r.get('date') or '', reverse=True)
            pts = [r for r in rs if r.get('lat') is not None]
            bounds = ''
            if pts:
                la = [r['lat'] for r in pts]; lo = [r['lon'] for r in pts]
                pad = 1.2
                bounds = f'{min(lo) - pad},{min(la) - pad},{max(lo) + pad},{max(la) + pad}'
            nm = st
            over = ('the ' + nm) if re.search(r'Ocean|Bahamas|District', nm) else nm
            body = f'''
<section class="band band-dark ua-hero"><div class="wrap">
  <p class="crumb"><a href="{U('/ufo/files/faa/')}">FAA pilot reports</a> / {E(nm)}</p>
  <h1>{'FAA pilot reports with no place given' if st == 'Place not given' else 'Pilot UFO reports over ' + E(over)}</h1>
  <p class="lede">{len(rs)} {'report' if len(rs) == 1 else 'reports'} from aircrews in the FAA's released UAP files{', ' + E(fmt_date(rs[-1].get('date'))) + ' to ' + E(fmt_date(rs[0].get('date'))) if len(rs) > 1 else ''}.</p>
</div></section>
{mapbox(['ufo_faa'], 'Map of FAA reports in ' + nm, height='short', bounds=bounds) if bounds else ''}
<div class="band band-mist"><div class="wrap">
  <ol class="ua-faas">{''.join(faa_item(r) for r in rs)}</ol>
  <p><a href="{U('/ufo/files/faa/')}">All FAA reports</a> · {bb_link(nm)}</p>
</div></div>{js}'''
            ctx.write(f'/ufo/files/faa/{ctx.slugify(st)}/', ctx.page(f'/ufo/files/faa/{ctx.slugify(st)}/',
                      ('FAA pilot UFO reports with no place given' if st == 'Place not given' else f'Pilot UFO reports over {over}: FAA files'), body,
                      f'{len(rs)} FAA pilot UAP reports from {nm}, with dates, altitudes, what crews saw and links to the National Archives originals.',
                      head_extra=css + (MAPLIBRE if bounds else '')))

    # --- PURSUE files ----------------------------------------------------------------------------
    def pcard(o):
        k, ic = KIND[o['kind']]
        when = o.get('date_label') or ''
        where = o.get('loc') or ''
        meta = ' · '.join(x for x in (when if when != 'N/A' else '', where) if x)
        hay = ' '.join([o['id'], o['title'], o['agency'], o['desc'], where, when]).lower()
        return (f'<li class="ua-pc" data-kind="{o["kind"]}" data-agency="{E(o["agency"])}" data-tranche="{o["tranche"]}" data-hay="{E(hay)}">'
                f'<a class="ua-pc-top" href="{E(o["url"])}" rel="noopener" tabindex="-1" aria-hidden="true">'
                f'<span class="ua-pc-ico">{ctx.icon(ic)}</span><span class="ua-pc-code">{E(o["id"])}</span>'
                f'{"<span class=ua-pc-red>Redacted</span>" if o.get("redacted") else ""}</a>'
                f'<div class="ua-pc-txt"><p class="ua-meta"><span class="ua-type">{k}</span><span class="ua-size">{E(o["agency"])}</span>'
                f'<span class="ua-size">Release {o["tranche"]}</span></p>'
                f'<h3><a href="{E(o["url"])}" rel="noopener">{E(o["title"])}</a></h3>'
                f'{f"<p class=ua-agency>{E(meta)}</p>" if meta else ""}'
                f'<p class="ua-sum">{E(o["desc"][:260] + ("..." if len(o["desc"]) > 260 else ""))}</p>'
                f'<p class="ua-id small"><a href="{E(o["url"])}" rel="noopener">{"Watch on DVIDS" if o["kind"] == "video" else "Listen on DVIDS" if o["kind"] == "audio" else "Open the file"}</a></p></div></li>')

    if pursue:
        tr = sorted({(o['tranche'], o['release']) for o in pursue})
        tcount = Counter(o['tranche'] for o in pursue)
        kinds = Counter(o['kind'] for o in pursue)
        ags = Counter(o['agency'] for o in pursue)
        tstrip = ''.join(f'<li><button type="button" class="ua-tr" data-tranche="{n}" aria-pressed="false"><b>Release {n}</b>'
                         f'<span>{E(short_date(d))}</span><span class="muted">{tcount[n]} files</span></button></li>' for n, d in tr)
        kchips = ''.join(f'<button type="button" class="chip" data-kind="{k}" aria-pressed="false">{E(KIND[k][0] + ("" if k == "audio" else "s"))} <span class="muted">{n}</span></button>'
                         for k, n in kinds.most_common())
        aopts = ''.join(f'<option value="{E(a)}">{E(a)} ({n})</option>' for a, n in ags.most_common())
        lst = sorted(pursue, key=lambda o: (-o['tranche'], not o.get('featured'), o['id']))
        body = f'''
<section class="band band-dark ua-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/ufo/releases/')}">Official releases</a> / <a href="{U('/ufo/releases/pursue-war-department-uap-files/')}">PURSUE</a></p>
    <div class="ua-head-row">{tbadge('documents', 'lg')}<h1>The Pentagon's 2026 UFO files</h1></div>
    <p class="lede">Since May 2026 the Department of War has been posting declassified UFO records in batches under PURSUE, the Presidential Unsealing and Reporting System for UAP Encounters. These are the {len(pursue)} files released so far, from 1940s flying-saucer memos to 2025 drone-camera video, with the cases the government still can't explain.</p>
    <ul class="ua-tranches">{tstrip}</ul>
  </div>
</section>
{mapbox(['ufo_pursue'], 'Map of PURSUE files with a known location', fit=False, bounds='-150,-10,140,62')}
<div class="band band-mist"><div class="wrap">
  <p class="small">{len(pursue_feats)} of the {len(pursue)} files name a place we can map; dots for a country, sea or region are placed in the middle of it. Space and orbit files (Apollo, Gemini, the Moon) are listed below but not mapped.</p>
  <div class="ua-filter" role="search">
    <label class="visually-hidden" for="ua-q">Search the files</label>
    <input id="ua-q" type="search" placeholder="Search: Apollo, Iraq, orb, Blue Book, FBI..." autocomplete="off">
    <label class="visually-hidden" for="ua-a">Agency</label>
    <select id="ua-a"><option value="">All agencies</option>{aopts}</select>
    <div class="chips ua-chips" role="group" aria-label="Filter by file type">{kchips}</div>
    <p class="ua-count" aria-live="polite"></p>
  </div>
  <ul class="ua-pgrid" data-filter-list data-limit="48">{''.join(pcard(o) for o in lst)}</ul>
  <p class="ua-more"><button type="button" class="btn" data-more>Show more files</button></p>
  <p class="empty" hidden>No file matches.</p>
  <h2>About these files</h2>
  <p>Titles, dates, places and descriptions come from the Department of War's own PURSUE index. Every card opens the original file on war.gov or the Pentagon's DVIDS video site. US government works are public domain.</p>
</div></div>{js}'''
        ctx.write('/ufo/files/pursue/', ctx.page('/ufo/files/pursue/', 'PURSUE: the Pentagon\'s 2026 UFO files, searchable and mapped', body,
                                                f'All {len(pursue)} declassified UAP files released by the US Department of War under PURSUE in 2026: documents, videos, images and audio, with a map.',
                                                head_extra=css + MAPLIBRE))

    # --- /ufo/countries/ ---------------------------------------------------------------------------
    us_states_bb = Counter(b['region'] for b in ctx.bluebook if b.get('cc') == 'US' and b.get('a1'))
    bb_cc = Counter((b.get('cc') or '').lower() for b in ctx.bluebook if b.get('cc'))
    all_cc = sorted(set(rel_by_cc) | set(pursue_by_cc), key=lambda c: cname.get(c, c))
    for cc in all_cc:
        if cc not in cname:
            continue
        c = by_code.get(cc)
        name = cname[cc]
        rels = rel_by_cc.get(cc, [])
        pcs = sorted(pursue_by_cc.get(cc, []), key=lambda o: o.get('date') or '', reverse=True)
        parts = []
        if c:
            parts.append(''.join(f'<p>{E(p)}</p>' for p in c['body']))
            parts.append(f'<p class="callout"><strong>Our data:</strong> {E(c["data"])}</p>')
        if rels:
            parts.append(f'<h2>Official releases</h2><ol class="ua-tl ua-tl-compact">{"".join(rel_card(r, compact=True) for r in rels)}</ol>')
        cases = ''
        if cc == 'us':
            st_faa = Counter(r.get('region') for r in faa if r.get('region'))
            rows = ''.join(f'<li><strong>{E(s)}</strong> <span class="muted">'
                           f'{" · ".join(x for x in ((f"<a href={chr(34)}{U(chr(47) + "ufo/files/faa/" + ctx.slugify(s) + chr(47))}{chr(34)}>{st_faa[s]} FAA</a>") if st_faa.get(s) else "", (f"<a href={chr(34)}{U(chr(47) + "ufo/blue-book/us-" + ctx.slugify(s) + chr(47))}{chr(34)}>{us_states_bb[s]:,} Blue Book</a>") if us_states_bb.get(s) else "") if x)}'
                           f'</span></li>' for s in sorted(set(st_faa) | set(us_states_bb)))
            cases = (f'<h2>Case files by state</h2><p>Three official US datasets are mapped on this site: {len(ctx.bluebook):,} Air Force '
                     f'<a href="{U("/ufo/")}">Project Blue Book</a> folders (1947 to 1969), {len(faa):,} <a href="{U("/ufo/files/faa/")}">FAA pilot reports</a> '
                     f'and the <a href="{U("/ufo/files/pursue/")}">PURSUE files</a>.</p><ul class="cols ua-states">{rows}</ul>')
        if pcs and cc != 'us':
            cases += (f'<h2>{E(name)} in the US government files</h2><p>{len(pcs)} of the Pentagon\'s 2026 PURSUE files concern events in {E(name)}.</p>'
                      f'<ul class="ua-pgrid ua-pgrid-sm">{"".join(pcard(o) for o in pcs)}</ul>')
        elif pcs:
            cases += (f'<h2>PURSUE files placed in the United States</h2><ul class="ua-pgrid ua-pgrid-sm" data-filter-list data-limit="12">{"".join(pcard(o) for o in pcs)}</ul>'
                      f'<p class="ua-more"><button type="button" class="btn" data-more>Show more files</button></p>')
        if bb_cc.get(cc) and cc != 'us':
            bb_slug = ctx.slugify(next(b['region'] for b in ctx.bluebook if (b.get('cc') or '').lower() == cc))
            cases += f'<p>The US Air Force also logged <a href="{U("/ufo/blue-book/" + bb_slug + "/")}">{bb_cc[cc]} Blue Book case {"folder" if bb_cc[cc] == 1 else "folders"} from {E(name)}</a>.</p>'
        parts.append(cases)
        links = ''.join(f'<li>{ext(l["url"], l["name"])}</li>' for l in (c or {}).get('links', []))
        the = ('the ' + name) if name.startswith('United') else name
        lede = (f'Who collected UFO reports in {E(the)}: {E(c["bodies"])}.' if c else
                f'{E(name)} has no official UFO release in our index yet, but it appears in US government files.')
        facts = ''
        if c:
            facts = (f'<aside class="facts"><dl><div><dt>Official bodies</dt><dd>{E(c["bodies"])}</dd></div>'
                     f'<div><dt>Releases indexed</dt><dd>{len(rels)}</dd></div>'
                     f'{f"<div><dt>Mapped case records</dt><dd>{len(pcs) + (len(faa) if cc == chr(117) + chr(115) else 0):,}</dd></div>" if pcs or cc == "us" else ""}'
                     f'</dl>{f"<ul class=ua-linklist>{links}</ul>" if links else ""}</aside>')
        body = f'''
<section class="band band-dark ua-hero creature-head">
  <div class="wrap creature-head-in">
    <span class="ua-tb ua-tb-xl ua-globe">{ctx.icon('ufo-globe')}<span class="ua-cc ua-cc-big">{E(cc.upper())}</span></span>
    <div>
      <p class="crumb"><a href="{U('/ufo/releases/')}">Official releases</a> / <a href="{U('/ufo/countries/')}">Countries</a></p>
      <h1>{E(name)}: official UFO files</h1>
      <p class="lede">{lede}</p>
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap {'creature-body' if c else ''}">
  <article class="prose ua-prose">{''.join(parts)}</article>
  {facts}
</div></div>{js}'''
        ctx.write(f'/ufo/countries/{cslug[cc]}/', ctx.page(f'/ufo/countries/{cslug[cc]}/', f'{name}: official UFO files and releases', body,
                  (f'How {name} has handled UFO reports, with {len(rels)} official releases linked to their sources.' if c else
                   f'{len(pcs)} US government UFO files about events in {name}.'), head_extra=css))
    cards = ''
    for cc in sorted((c for c in all_cc if c in cname), key=lambda c: (-len(rel_by_cc.get(c, [])), cname[c])):
        nr, npc = len(rel_by_cc.get(cc, [])), len(pursue_by_cc.get(cc, []))
        bits = ' · '.join(x for x in ((f'{nr} release{"s" if nr != 1 else ""}' if nr else ''),
                                       (f'{npc} PURSUE file{"s" if npc != 1 else ""}' if npc else '')) if x)
        blurb = E(by_code[cc]['bodies']) if cc in by_code else 'Appears in US government files'
        cards += (f'<li><a class="ua-ccard{" ua-ccard-main" if cc in by_code else ""}" href="{U("/ufo/countries/" + cslug[cc] + "/")}">'
                  f'<span class="ua-cc ua-cc-big">{E(cc.upper())}</span><span><strong>{E(cname[cc])}</strong>'
                  f'<span class="ua-ccard-b">{blurb}</span><span class="muted small">{bits}</span></span></a></li>')
    body = f'''
<section class="band band-dark ua-hero"><div class="wrap">
  <p class="crumb"><a href="{U('/ufo/releases/')}">Official releases</a> / Countries</p>
  <h1>UFO files around the world</h1>
  <p class="lede">Which governments collect UFO reports, what they have released, and where to read it. {len(by_code)} countries have their own page; the rest appear in the US government's files.</p>
</div></section>
<div class="band band-mist"><div class="wrap"><ul class="ua-cards">{cards}</ul></div></div>'''
    ctx.write('/ufo/countries/', ctx.page('/ufo/countries/', 'UFO files by country: official releases worldwide', body,
                                         'Official UFO investigations and releases country by country: US, UK, Canada, France, Brazil, Chile and more.', head_extra=css))

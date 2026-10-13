"""Canada landing page (/canada/): everything on the site that happened in Canada, in one place.

Pulls from the other datasets (creatures with cc CA, famous cases and military cases whose point is inside Canada,
close encounters, mysteries, places, the Canadian UFO Survey). Nothing here is new data: it is a regional way in.
"""
import json, os, sys
from collections import Counter

MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def build(ctx):
    E, U = ctx.esc, ctx.url
    load = lambda f: json.load(open(os.path.join(ctx.ROOT, 'data', f), encoding='utf-8')) if os.path.exists(os.path.join(ctx.ROOT, 'data', f)) else []
    sys.path.insert(0, os.path.join(ctx.ROOT, 'collector'))
    from geo import Areas
    A = Areas()
    def inside(x):  # in Canada and not on the US side of a border city (Detroit/Windsor)
        if x.get('lat') is None:
            return False
        lat, lon = float(x['lat']), float(x['lon'])
        return A.inside(lat, lon, 'CA', slack=0.05) and not A.inside(lat, lon, 'US', slack=0)

    crit = [c for c in ctx.creatures if 'CA' in c['cc']]
    order = {'hominid': 0, 'canid': 1, 'aquatic': 2, 'winged': 3, 'other': 4, 'entity': 5, 'fae': 6, 'ufo': 7}
    crit.sort(key=lambda c: (order.get(c['cat'], 9), c['name']))
    fam = sorted((f for f in load('famous_geo.json') if inside(f) and f['creature'] in ctx.by_slug), key=lambda f: f['year'] if isinstance(f['year'], int) else 0)
    ce = [x for x in load('close_encounters.json') if (x.get('cc') or '').upper() == 'CA']
    my = [x for x in load('mysteries.json') if (x.get('cc') or '').upper() == 'CA']
    pl = [x for x in load('places.json') if x.get('country') == 'CA']
    mil = [m for m in load('military.json') if inside(m)]
    cu = load('ufo_cases_canada.json')
    provs = Counter(r['prov'] for r in cu)

    stats = [(len(crit), 'creatures'), (f'{len(cu):,}', 'UFO reports mapped'), (len(fam), 'famous cases'), (len(pl), 'places to visit')]
    fam_html = ''.join(
        f'<li><span class="yr">{f["year"]}</span><span><a href="{U("/creatures/" + f["creature"] + "/")}"><strong>{E(f["name"])}</strong></a>'
        f'<br><span class="muted">{E(ctx.by_slug[f["creature"]]["name"])} · {E(f["place"])}</span></span></li>' for f in fam)
    ce_html = ''.join(f'<li><a class="cn-card" href="{U("/encounters/" + x["slug"] + "/")}"><b>{E(x["name"])}</b><small>{E(x["place"])}, {x["year"]}</small>'
                      f'<span>{E(x["summary"][:170] + ("..." if len(x["summary"]) > 170 else ""))}</span></a></li>' for x in ce)
    ce_html += ''.join(f'<li><a class="cn-card" href="{U("/mysteries/" + x["slug"] + "/")}"><b>{E(x["name"])}</b><small>{E(x["place"])}</small>'
                       f'<span>{E(x["summary"][:170] + ("..." if len(x["summary"]) > 170 else ""))}</span></a></li>' for x in my)
    ce_html += ''.join(f'<li><a class="cn-card" href="{U("/military/")}"><b>{E(m["name"])}</b><small>{E(m["place"])}, {E(str(m["date"])[:4])}</small>'
                       f'<span>{E(m["summary"][:170] + ("..." if len(m["summary"]) > 170 else ""))}</span></a></li>' for m in mil)
    regions = sorted({x['region'] for x in pl if x.get('region')})
    pl_html = ''.join(f'<li><a class="cn-card cn-place" href="{U("/places/" + x["slug"] + "/")}"><b>{E(x["name"])}</b>'
                      f'<small>{E(", ".join(v for v in (x.get("city"), x.get("region")) if v))}</small>'
                      f'<span>{E((x.get("summary") or "")[:140] + ("..." if len(x.get("summary") or "") > 140 else ""))}</span></a></li>' for x in pl)
    reg_chips = ''.join(f'<a class="md-chip" href="{U("/places/" + ctx.slugify(r) + "/")}">{E(r)}</a>' for r in regions)  # places.py makes a page per region
    prov_chips = ''.join(f'<a class="md-chip" href="{U("/ufo/canada/" + ctx.slugify(p) + "/")}">{E(p)} <small>{n:,}</small></a>' for p, n in provs.most_common())
    lakes = [c for c in crit if c['cat'] == 'aquatic']
    body = f'''
<section class="band band-dark cn-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/')}">Home</a> / Canada</p>
    <h1>Sasquatch, lake monsters and UFOs in Canada</h1>
    <p class="lede">Canada gave the world the word Sasquatch, has a lake monster in almost every province, and these days logs about a thousand UFO reports a year.
    Here is everything on the site from coast to coast to coast.</p>
    <ul class="ua-stats">{''.join(f'<li><b>{v}</b> {E(k)}</li>' for v, k in stats)}</ul>
    <nav class="jump" aria-label="On this page"><a href="#creatures">Creatures</a><a href="#ufo">UFO sightings</a><a href="#cases">Famous cases</a><a href="#encounters">Encounters and mysteries</a><a href="#visit">Places to visit</a></nav>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <h2 id="creatures">Creatures reported in Canada</h2>
  <p>From the Sasquatch of the BC coast to {E(", ".join(c["name"] for c in lakes[:4]))} and the rest of the lake monsters.</p>
  <div class="crit-grid">{''.join(ctx.creature_card(c) for c in crit)}</div>

  <h2 id="ufo">UFO sightings by province</h2>
  <p>{len(cu):,} reports since 1989, mapped town by town. See what was seen over your town and which reports nobody could explain.</p>
  <p class="md-chips">{prov_chips}</p>
  <p><a class="btn" href="{U('/ufo/canada/')}">Open the Canada sightings map</a> <a class="btn btn-ghost-l" href="{U('/ufo/countries/canada/')}">Canada's official UFO files</a></p>

  <h2 id="cases">Famous cases in Canada</h2>
  <ol class="timeline">{fam_html}</ol>

  <h2 id="encounters">Close encounters, mysteries and military cases</h2>
  <ul class="cn-grid">{ce_html}</ul>

  <h2 id="visit">Places to visit</h2>
  <p>Museums, statues, festivals and the spots where it happened.</p>
  <ul class="cn-grid">{pl_html}</ul>
  {f'<h3>Places by province</h3><p class="md-chips">{reg_chips}</p>' if reg_chips else ''}

  <section class="cn-cta"><h2>Seen something in Canada?</h2>
  <p>Tell us what happened. Every report is read by a person before it goes on the map, and you can keep the exact spot private.</p>
  <p><a class="btn" href="{U('/report/')}">Report an encounter</a> <a class="btn btn-ghost" href="{U('/guides/')}">Field guides</a></p></section>
</div></div>'''
    css = f'<link rel="stylesheet" href="{U("/static/ufo_archive.css")}"><link rel="stylesheet" href="{U("/static/canada.css")}">'
    ctx.write('/canada/', ctx.page('/canada/', 'Sasquatch, lake monsters and UFOs in Canada', body,
                                   f'Canada\'s cryptids and UFOs in one place: {len(crit)} creatures from Sasquatch to Ogopogo, {len(cu):,} mapped UFO reports by province, famous cases and places to visit.',
                                   head_extra=css))

    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if os.path.exists(sp):
        items = json.load(open(sp, encoding='utf-8'))
        items.append({'t': 'Canada: creatures, UFOs and places', 'a': 'canada canadian sasquatch', 'k': f'{len(crit)} creatures, {len(cu):,} UFO reports',
                      'u': U('/canada/'), 'i': 'saucer', 'c': 'ufo'})
        json.dump(items, open(sp, 'w', encoding='utf-8'), separators=(',', ':'))

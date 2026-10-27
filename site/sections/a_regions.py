"""(Named a_regions.py so it runs before the other sections, which link to the hubs it makes via ctx.regions.)

State and province hubs: /us/, /us/<state>/ and /canada/<province>/ (the /canada/ page itself is canada.py).

Everything the site has for one state or province on one page: creatures with famous cases there, close encounters,
mysteries and military cases, UFO files (Air Force Blue Book, FAA pilot reports, the Canadian UFO Survey), old
newspaper reports, and places to visit. No new data: it is a "where I live" way in. A page is only made when the area
has at least 3 cases, places or newspaper reports besides UFO file counts, so no thin pages.
"""
import json, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _legend import legend_card, head as legend_head
import _tripadd


def build(ctx):
    E, U = ctx.esc, ctx.url
    load = lambda f: json.load(open(os.path.join(ctx.ROOT, 'data', f), encoding='utf-8')) if os.path.exists(os.path.join(ctx.ROOT, 'data', f)) else []
    sys.path.insert(0, os.path.join(ctx.ROOT, 'collector'))
    from geo import Areas
    A = Areas()
    ctx.areas = A  # reports.py reuses the loaded boundaries to name the region of each reader report
    names = load('admin1_us_ca.json')  # GeoNames admin1 names for the US and Canada (committed copy, CC BY 4.0)
    names.pop('US.DC', None)

    def where(x):
        if x.get('lat') is None:
            return None
        cc, a1 = A.where(float(x['lat']), float(x['lon']))
        return f'{cc}.{a1}' if cc in ('US', 'CA') and a1 else None

    by = defaultdict(lambda: defaultdict(list))
    for f in load('famous_geo.json'):
        if f['creature'] in ctx.by_slug and (k := where(f)):
            by[k]['fam'].append(f)
    for x in load('close_encounters.json'):
        if (k := where(x)):
            by[k]['ce'].append(x)
    for x in load('mysteries.json'):
        if (k := where(x)):
            by[k]['my'].append(x)
    for x in load('military.json'):
        if (k := where(x)):
            by[k]['mil'].append(x)
    name_key = {(k[:2], v): k for k, v in names.items()}
    for x in load('places.json'):
        if x.get('country') in ('US', 'CA') and (k := name_key.get((x['country'], x.get('region')))):
            by[k]['pl'].append(x)
    for h in load('historic.json'):
        if (k := name_key.get(('US', h.get('state')))):
            by[k]['hist'].append(h)
    bb = Counter(f'US.{b["a1"]}' for b in ctx.bluebook if b.get('cc') == 'US' and b.get('a1'))
    bb_slug = {f'US.{b["a1"]}': 'us-' + ctx.slugify(b['region']) for b in ctx.bluebook if b.get('cc') == 'US' and b.get('a1')}
    faa = Counter(name_key.get(('US', r.get('region'))) for r in load('ufo_cases_faa.json') if r.get('cc') == 'US')
    cu = Counter(name_key.get(('CA', r['prov'])) for r in load('ufo_cases_canada.json'))
    hist_pages = {k for k, v in by.items() if len(v['hist']) >= 5}  # historic.py makes a state page from 5 reports

    made = {}
    for k, nm in sorted(names.items(), key=lambda kv: kv[1]):
        d = by.get(k, {})
        if sum(len(d.get(x, [])) for x in ('fam', 'ce', 'my', 'mil', 'pl', 'hist')) < 3:  # no thin pages
            continue
        cc = k[:2]
        slug = ctx.slugify(nm)
        made[k] = (f'/{"us" if cc == "US" else "canada"}/{slug}/', nm)
    hubs = load('region_hubs.json') or {}  # hand-written copy: state hub titles/intros and multi-state region hubs
    state_over, regions = hubs.get('states', {}), hubs.get('regions', [])
    part_of = defaultdict(list)  # state name -> [(path, region name)] to link from that state's hub
    for r in regions:
        for st in r.get('link_from', []):
            part_of[st].append((f'/us/{r["slug"]}/', r['name'], r['h1']))
    css = f'<link rel="stylesheet" href="{U("/static/ufo_archive.css")}"><link rel="stylesheet" href="{U("/static/canada.css")}">' + legend_head(ctx)
    css_trip = css + _tripadd.head(ctx, spotmap=True)  # state and province hubs: mini map and road trip buttons

    def card(href, title, sub, text, cls=''):
        return (f'<li><a class="cn-card{cls}" href="{href}"><b>{E(title)}</b><small>{E(sub)}</small>'
                f'<span>{E(text[:160] + ("..." if len(text) > 160 else ""))}</span></a></li>')

    for k, (path, nm) in made.items():
        d, cc = by[k], k[:2]
        fam = sorted(d.get('fam', []), key=lambda f: f['year'] if isinstance(f['year'], int) else 0)
        crit = list(dict.fromkeys(f['creature'] for f in fam))
        hist = sorted(d.get('hist', []), key=lambda h: h.get('date') or '')
        stats = []
        if crit:
            stats.append((len(crit), 'creatures with famous cases'))
        if cc == 'US' and bb.get(k):
            stats.append((f'{bb[k]:,}', 'Air Force UFO files'))
        if cc == 'CA' and cu.get(k):
            stats.append((f'{cu[k]:,}', 'UFO reports since 1989'))
        if hist:
            stats.append((len(hist), 'old newspaper reports'))
        if d.get('pl'):
            stats.append((len(d['pl']), 'places to visit'))
        jumps = [('#creatures', 'Creatures') if crit else None, ('#ufo', 'UFO files'), ('#cases', 'Encounters and mysteries') if d.get('ce') or d.get('my') or d.get('mil') else None,
                 ('#history', 'Old newspapers') if hist else None, ('#visit', 'Places to visit') if d.get('pl') else None]
        parts = []
        if crit:
            fam_html = ''.join(f'<li><span class="yr">{f["year"]}</span><span><a href="{U("/creatures/" + f["creature"] + "/")}"><strong>{E(f["name"])}</strong></a>'
                               f'<br><span class="muted">{E(ctx.by_slug[f["creature"]]["name"])} · {E(f["place"])}</span></span></li>' for f in fam)
            parts.append(f'<h2 id="creatures">Creatures reported in {E(nm)}</h2><div class="crit-grid">{"".join(ctx.creature_card(ctx.by_slug[c]) for c in crit)}</div>'
                         f'<h3>Famous cases</h3><ol class="timeline">{fam_html}</ol>')
        ufo = []
        if cc == 'US' and bb.get(k):
            ufo.append(f'<li><a href="{U("/ufo/blue-book/" + bb_slug[k] + "/")}"><b>{bb[k]:,} US Air Force Project Blue Book files</b></a> from {E(nm)}, 1947 to 1969</li>')
        if cc == 'US' and faa.get(k):
            ufo.append(f'<li><a href="{U("/ufo/files/faa/" + ctx.slugify(nm) + "/")}"><b>{faa[k]} FAA pilot report{"s" if faa[k] != 1 else ""}</b></a> of lights and objects over {E(nm)}, 2007 to 2024</li>')
        if cc == 'CA' and cu.get(k):
            ufo.append(f'<li><a href="{U("/ufo/canada/" + ctx.slugify(nm) + "/")}"><b>{cu[k]:,} UFO reports</b></a> from {E(nm)} since 1989, mapped town by town (Canadian UFO Survey)</li>')
        ufo.append(f'<li>Saw a strange light? <a href="{U("/tools/was-it-a-planet/")}">Check whether it was a planet</a></li>')
        parts.append(f'<h2 id="ufo">UFO files</h2><ul class="also-links">{"".join(ufo)}</ul>')
        cases = ''.join(card(U('/encounters/' + x['slug'] + '/'), x['name'], f'{x["place"]}, {x["year"]}', x['summary']) for x in d.get('ce', []))
        cases += ''.join(card(U('/mysteries/' + x['slug'] + '/'), x['name'], x['place'], x['summary']) for x in d.get('my', []))
        cases += ''.join(card(U('/military/'), x['name'], f'{x["place"]}, {str(x["date"])[:4]}', x['summary']) for x in d.get('mil', []))
        if cases:
            parts.append(f'<h2 id="cases">Encounters and mysteries</h2><ul class="cn-grid">{cases}</ul>')
        if hist:
            items = ''.join(f'<li><span class="yr">{E((h.get("date") or "")[:4])}</span><span><strong>{E(h["title"])}</strong>'
                            f'<br><span class="muted">{E(h.get("town") or h.get("place") or "")}</span></span></li>' for h in hist[:12])
            more = (f'<p><a href="{U("/history/" + ctx.slugify(nm) + "/")}">All {len(hist)} newspaper reports from {E(nm)}</a></p>' if k in hist_pages
                    else f'<p><a href="{U("/history/")}">Browse all old newspaper reports</a></p>')
            parts.append(f'<h2 id="history">From the old newspapers</h2><p>Strange creatures, sea serpents and mystery airships reported in {E(nm)} papers before 1927.</p>'
                         f'<ol class="timeline">{items}</ol>{more}')
        if d.get('pl'):
            pls = ''.join(card(U('/places/' + x['slug'] + '/'), x['name'], x.get('city') or nm, x.get('summary') or '', ' cn-place')
                          .replace('</a></li>', '</a>' + _tripadd.button(ctx, x.get('lat'), x.get('lon'), x['name'], '/places/' + x['slug'] + '/', 'on-card') + '</li>')
                          for x in d['pl'])
            parts.append(f'<h2 id="visit">Places to visit</h2><ul class="cn-grid">{pls}</ul>'
                         f'<p><a href="{U("/places/" + ctx.slugify(nm) + "/")}">More about visiting in {E(nm)}</a> · <a href="{U("/events/")}">Events and festivals</a></p>')
        spots = ([('case', f.get('lat'), f.get('lon'), f['name'], '/creatures/' + f['creature'] + '/') for f in fam]
                 + [('encounter', x.get('lat'), x.get('lon'), x['name'], '/encounters/' + x['slug'] + '/') for x in d.get('ce', [])]
                 + [('mystery', x.get('lat'), x.get('lon'), x['name'], '/mysteries/' + x['slug'] + '/') for x in d.get('my', [])]
                 + [('military', x.get('lat'), x.get('lon'), x['name'], '/military/') for x in d.get('mil', [])]
                 + [('place', x.get('lat'), x.get('lon'), x['name'], '/places/' + x['slug'] + '/') for x in d.get('pl', [])])
        mini = _tripadd.spot_map(ctx, spots, nm)
        neigh = ''.join(f'<a class="md-chip" href="{U(p)}">{E(n)}</a>' for kk, (p, n) in sorted(made.items(), key=lambda kv: kv[1][1]) if kk[:2] == cc and kk != k)
        top = 'Canada' if cc == 'CA' else 'United States'
        cnames = [ctx.by_slug[c]['name'] for c in crit[:3]]
        lead = (f'{", ".join(cnames)}{" and more" if len(crit) > 3 else ""}: the creatures, UFO files and strange history of {E(nm)}, all in one place.'
                if cnames else f'UFO files, old newspaper reports and places to visit in {E(nm)}, all in one place.')
        if cc == 'CA':
            lead = lead.replace('UFO files', 'UFO sightings')
        o = state_over.get(nm, {}) if cc == 'US' else {}
        intro = (f'<div class="prose">{"".join(f"<p>{ctx.md_links(t)}</p>" for t in o["intro"])}</div>' if o.get('intro') else '')
        part = ''.join(f'<p>More from the mountains: <a href="{U(rp)}">{E(rh)}</a></p>' for rp, rn, rh in part_of.get(nm, []) if cc == 'US')
        body = f'''
<section class="band band-dark cn-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/canada/' if cc == 'CA' else '/us/')}">{top}</a> / {E(nm)}</p>
    <h1>{E(o['h1']) if o.get('h1') else ('Cryptids and UFOs' if cc == 'US' else ('Sasquatch, cryptids and UFOs' if 'bigfoot' in crit else 'Cryptids and UFOs')) + ' in ' + E(nm)}</h1>
    <p class="lede">{lead}</p>{part}
    <ul class="ua-stats">{''.join(f'<li><b>{v}</b> {E(t)}</li>' for v, t in stats)}</ul>
    <nav class="jump" aria-label="On this page">{''.join(f'<a href="{h}">{t}</a>' for h, t in filter(None, jumps))}</nav>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  {intro}{legend_card(ctx, cc, nm)}
  {mini}
  {''.join(parts)}
  <section class="cn-cta"><h2>Seen something in {E(nm)}?</h2>
  <p>Tell us what happened. Every report is read by a person before it goes on the map, and you can keep the exact spot private.</p>
  <p><a class="btn" href="{U('/report/')}">Report an encounter</a> <a class="btn btn-ghost" href="{U('/guides/')}">Field guides</a></p></section>
  <h2>{'Other provinces and territories' if cc == 'CA' else 'Other states'}</h2><p class="md-chips">{neigh}</p>
</div></div>'''
        big = 'bigfoot' in crit
        title = (f'{"Bigfoot, cryptids" if big else "Cryptids"} and UFOs in {nm}' if cc == 'US'
                 else f'{"Sasquatch, cryptids" if big else "Cryptids"} and UFOs in {nm}')
        desc = (f'Everything strange in {nm}: ' + ', '.join(f'{v} {t}' for v, t in stats[:4]) + '.')
        ctx.write(path, ctx.page(path, o.get('seo_title') or title, body, o.get('seo_desc') or desc, head_extra=css_trip if mini or d.get('pl') else css))

    # hand-written multi-state region hubs (/us/appalachia/), from data/region_hubs.json
    pl_by = {x['slug']: x for x in load('places.json')}
    st_key = {n: k for k, n in names.items() if k.startswith('US.')}
    for r in regions:
        path = f'/us/{r["slug"]}/'
        md = lambda ps: ''.join(f'<p>{ctx.md_links(t)}</p>' for t in ps)
        parts, jumps = [], []
        for b in r['blocks']:
            jumps.append((b['id'], b['h2']))
            h2 = f'<h2 id="{b["id"]}">{E(b["h2"])}</h2>'
            if b['type'] == 'text':
                parts.append(f'<section class="prose">{h2}{md(b["p"])}</section>')
            elif b['type'] == 'creatures':
                its = [i for i in b['items'] if i['slug'] in ctx.by_slug]
                tl = ''.join(f'<li><span class="yr">{E(i["year"])}</span><span><a href="{U("/creatures/" + i["slug"] + "/")}"><strong>{E(ctx.by_slug[i["slug"]]["name"])}</strong></a>'
                             f'<br><span class="muted">{E(i["line"])}</span></span></li>' for i in its)
                parts.append(f'{h2}<div class="crit-grid">{"".join(ctx.creature_card(ctx.by_slug[i["slug"]]) for i in its)}</div>'
                             f'<h3>Where and when</h3><ol class="timeline">{tl}</ol>')
            elif b['type'] == 'bluebook':
                li = ''.join(f'<li><a href="{U("/ufo/blue-book/" + bb_slug[st_key[st]] + "/")}"><b>{E(st)}</b></a>: {bb[st_key[st]]:,} Project Blue Book files, 1947 to 1969</li>'
                             for st in b['states'] if bb.get(st_key.get(st)))
                parts.append(f'{h2}<ul class="also-links">{li}</ul>')
            elif b['type'] == 'places':
                pls = ''.join(card(U('/places/' + x['slug'] + '/'), x['name'], f'{x.get("city")}, {x.get("region")}', x.get('summary') or '', ' cn-place')
                              for x in (pl_by[sl] for sl in b['slugs'] if sl in pl_by))
                parts.append(f'{h2}<ul class="cn-grid">{pls}</ul><p><a href="{U("/events/")}">All events and festivals</a></p>')
            elif b['type'] == 'states':
                chips = ''.join(f'<a class="md-chip" href="{U(made[st_key[st]][0])}">{E(st)}</a>' for st in r['states'] if st_key.get(st) in made)
                parts.append(f'{h2}<p class="md-chips">{chips}</p>')
        src = ''.join(f'<li><a href="{E(x["url"])}" rel="noopener">{E(x["title"])}</a></li>' for x in r.get('sources', []))
        body = f'''
<section class="band band-dark cn-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/us/')}">United States</a> / {E(r['name'])}</p>
    <h1>{E(r['h1'])}</h1>
    <p class="lede">{E(r['lede'])}</p>
    <nav class="jump" aria-label="On this page">{''.join(f'<a href="#{i}">{E(t)}</a>' for i, t in jumps)}</nav>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  {''.join(parts)}
  <p class="small muted">Sources: everything here comes from our own creature, case and place pages, each with its own sources, plus:</p><ul class="small muted">{src}</ul>
  <section class="cn-cta"><h2>Seen something in {E(r['name'])}?</h2>
  <p>Tell us what happened. Every report is read by a person before it goes on the map, and you can keep the exact spot private.</p>
  <p><a class="btn" href="{U('/report/')}">Report an encounter</a> <a class="btn btn-ghost" href="{U('/guides/')}">Field guides</a></p></section>
</div></div>'''
        ctx.write(path, ctx.page(path, r['seo_title'], body, r['seo_desc'], head_extra=css))

    # /us/ index
    us = sorted(((p, n, k) for k, (p, n) in made.items() if k[:2] == 'US'), key=lambda x: x[1])
    if us:
        grid = ''.join(f'<li><a href="{U(p)}"><b>{E(n)}</b><span>{len(set(f["creature"] for f in by[k].get("fam", [])))} creatures · {bb.get(k, 0):,} UFO files</span>'
                       f'<small>{len(by[k].get("pl", []))} places · {len(by[k].get("hist", []))} newspaper reports</small></a></li>' for p, n, k in us)
        body = f'''
<section class="band band-dark cn-hero"><div class="wrap">
  <p class="crumb"><a href="{U('/')}">Home</a> / United States</p>
  <h1>Cryptids and UFOs, state by state</h1>
  <p class="lede">Pick your state to see its creatures, famous cases, UFO files, old newspaper reports and places to visit.
  In Canada? <a href="{U('/canada/')}">Start here</a>.{''.join(f' By region: <a href="{U("/us/" + r["slug"] + "/")}">{E(r["h1"])}</a>.' for r in regions)}</p>
</div></section>
<div class="band band-mist"><div class="wrap">{legend_card(ctx, 'US')}<ul class="cu-pgrid st-grid">{grid}</ul></div></div>'''
        ctx.write('/us/', ctx.page('/us/', 'Cryptids, Bigfoot and UFOs by state', body,
                                   'Bigfoot, strange creatures, UFO files, old newspaper reports and places to visit for every US state.',
                                   head_extra=css + f'<link rel="stylesheet" href="{U("/static/ufo_canada.css")}">'))

    # search entries
    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if os.path.exists(sp):
        items = json.load(open(sp, encoding='utf-8'))
        items += [{'t': f'{n}: creatures and UFOs', 'a': n + (' canada' if p.startswith('/canada/') else ' state usa'), 'k': 'Everything in ' + n,
                   'u': U(p), 'i': 'saucer', 'c': 'other'} for p, n in made.values()]
        items += [{'t': r['h1'], 'a': r['name'] + ' region usa', 'k': r['lede'], 'u': U(f'/us/{r["slug"]}/'), 'i': 'saucer', 'c': 'other'} for r in regions]
        json.dump(items, open(sp, 'w', encoding='utf-8'), separators=(',', ':'))
    ctx.regions = made  # for other sections that want to link a state or province hub

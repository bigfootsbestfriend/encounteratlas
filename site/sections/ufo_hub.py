"""UFOs hub (/ufo/): sightings people have had, then the official files.

Famous sightings come from the famous cases of every UFO-category creature (shape pages like ufo-saucer, ufo-orbs), with
the hand-written summaries in data/famous_details_*.json. Reader sightings join once the reports Worker (EA_API) is live.
The Air Force Blue Book index lives at /ufo/blue-book/ (build.py); official releases in ufo_archive.py.
"""
import json, os


def build(ctx):
    U, E = ctx.url, ctx.esc
    load = lambda f: json.load(open(os.path.join(ctx.ROOT, 'data', f), encoding='utf-8')) if os.path.exists(os.path.join(ctx.ROOT, 'data', f)) else None
    details = {}
    for fn in ('famous_details_a.json', 'famous_details_b.json'):
        details.update(load(fn) or {})
    shapes = [c for c in ctx.creatures if c['cat'] == 'ufo']
    NOT_SIGHTINGS = {'crop-circles', 'cattle-mutilation', 'skinwalker-ranch'}  # their 'famous' entries are books, hoaxes, purchases
    cases = []
    for c in shapes:
        if c['slug'] in NOT_SIGHTINGS:
            continue
        for f in c.get('famous', []):
            d = details.get(c['slug'] + '|' + f['name']) or {}
            cases.append({**f, 'c': c, 'sum': d.get('summary', ''), 'src': d.get('source_url'), 'srct': d.get('source_title')})
    cases.sort(key=lambda x: -x['year'])
    close = load('close_encounters.json') or []
    api = os.environ.get('EA_API', '').rstrip('/')

    used = [c for c in shapes if any(x['c'] is c for x in cases)]
    chips = (f'<button type="button" class="ce-chip" data-f="" aria-pressed="true">All <span>{len(cases)}</span></button>'
             + ''.join(f'<button type="button" class="ce-chip" data-f="{c["slug"]}" aria-pressed="false">{E(c["name"])} '
                       f'<span>{sum(1 for x in cases if x["c"] is c)}</span></button>' for c in used))

    def card(x):
        c = x['c']
        s = x['sum'] if len(x['sum']) < 260 else x['sum'][:250].rsplit(' ', 1)[0] + '…'
        return (f'<article class="uh-card" data-f="{c["slug"]}"><a href="{U("/creatures/" + c["slug"] + "/")}">'
                f'{ctx.badge(c)}<span class="ce-txt"><span class="ce-meta">{x["year"]} · {E(x["place"])}</span>'
                f'<span class="ce-name">{E(x["name"])}</span>{f"<span class=ce-sum>{E(s)}</span>" if s else ""}'
                f'<span class="uh-shape">{E(c["name"])}</span></span></a></article>')

    by_dec = {}
    for x in cases:
        by_dec.setdefault(x['year'] // 10 * 10, []).append(x)
    groups = ''.join(f'<section class="ce-dec"><h3>The {d}s</h3><div class="ce-grid">{"".join(card(x) for x in v)}</div></section>'
                     for d, v in sorted(by_dec.items(), reverse=True))
    recent_close = sorted(close, key=lambda x: x['date'], reverse=True)[:4]
    close_html = ''.join(f'<li><a href="{U("/encounters/" + x["slug"] + "/")}">{E(x["name"])}</a><small>{E(x["place"])}, {x["year"]}</small></li>'
                         for x in recent_close)
    reader = (f'<p><a class="btn" href="{U("/reports/")}">Read reader sightings</a></p>' if api else
              '<p>Reader reports are opening soon. When they do, every sighting people send in will be pinned here and on the map, '
              'with the exact spot hidden if the witness prefers.</p>')
    tiles = [('/ufo/blue-book/', 'folder', 'Air Force Blue Book files, 1947 to 1969'), ('/ufo/releases/', 'folder', 'Every official release, 13 countries'),
             ('/ufo/canada/', 'ufo-globe', 'Canada sightings map, 1989 to today'),
             ('/ufo/files/pursue/', 'military', "The Pentagon's 2026 files"), ('/ufo/files/faa/', 'saucer', 'FAA pilot reports, 2007 to 2024'),
             ('/ufo/countries/', 'saucer', 'UFO files by country'), ('/military/', 'military', 'Military encounters')]
    tiles_html = ''.join(f'<a class="tile" href="{U(p)}">{ctx.icon(i)}<span>{E(t)}</span></a>' for p, i, t in tiles)
    shape_cards = ''.join(ctx.creature_card(c) for c in shapes)
    head = (f'<link rel="stylesheet" href="{U("/static/encounters.css")}">'
            f'<link rel="stylesheet" href="{U("/static/ufo_hub.css")}"><script src="{U("/static/ufo_hub.js")}" defer></script>')
    body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb">UFOs</p>
  <h1>UFO sightings</h1>
  <p class="lede">What people have seen in the sky, from Kenneth Arnold's "flying saucers" to Canada's Falcon Lake burns, plus the official files governments have released. Seen something yourself? Add it to the map.</p>
  <p class="uh-btns"><a class="btn" href="{U('/report/?creature=ufo-saucer')}">Report a UFO sighting</a> <a class="btn btn-ghost" href="{U('/map/')}">Open the map</a></p>
</div></section>
<div class="band band-mist ce-list"><div class="wrap">
  <h2>Famous sightings</h2>
  <p>{len(cases)} of the best-known UFO sightings, newest first. Filter by what people saw.</p>
  <div class="ce-chips uh-chips" role="group" aria-label="Filter by shape">{chips}</div>
  <p class="ce-status" aria-live="polite"></p>
  {groups}
  <div class="uh-two">
    <div class="uh-box"><h2>Sightings from readers</h2>{reader}<p><a href="{U('/report/?creature=ufo-saucer')}">Report what you saw</a></p></div>
    <div class="uh-box"><h2>Close encounters</h2><p>When witnesses said they saw the occupants, not just the craft.</p><ul class="next-list">{close_html}</ul>
      <p><a href="{U('/encounters/')}">All {len(close)} close encounters</a></p></div>
  </div>
  <h2>Official files</h2>
  <p>What governments, air forces and aviation agencies wrote down, with links to the original scans.</p>
  <nav class="tiles ufo-more" aria-label="Official UFO files">{tiles_html}</nav>
  <h2>What people see</h2>
  <p>Saucers, triangles, orbs and Tic Tacs: each shape has its own page with famous cases.</p>
  <div class="crit-grid">{shape_cards}</div>
</div></div>'''
    ctx.write('/ufo/', ctx.page('/ufo/', 'UFO sightings: famous cases, reader reports and official files', body,
                                f'{len(cases)} famous UFO sightings from {min(x["year"] for x in cases)} to today, close encounters, and official UFO files from the '
                                'US Air Force, the Pentagon, the FAA and 13 countries.', body_class='encounters ufo-hub', head_extra=head))

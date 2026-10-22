"""Close encounters in Greece: /ufo/greece/ (48 CE3 cases, 1901 to 2007, with one from Cyprus).

Data: data/ufo_cases_greece.json (collector/grufon.py), shared with Encounter Atlas by the Greek UFO Network (GRUFON)
in October 2026. Credit GRUFON by name and link its site (Mike approved the link, 2026-10-21). Stories are our own
retellings; the verdict line is GRUFON's. Writes OUT/data/ufo_greece.geojson for this page's map, the main map and Near me.
The map reuses the Canada map script (ufo_canada.js) and its colours: unexplained red, possibly explained gold.
"""
import json, os, re
from collections import Counter

CREDIT = 'the Greek UFO Network (GRUFON)'
GRUFON_LINK = '<a href="https://www.grufon.org/" target="_blank" rel="noopener">the Greek UFO Network (GRUFON)</a>'
MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
BEINGS = {'humanoid': 'Beings seen', 'strange': 'Strange figure', 'other': 'Craft or strange event'}


def fmt(d):
    p = d.split('-')
    if len(p) == 3:
        return f'{MONTHS[int(p[1])]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MONTHS[int(p[1])]} {p[0]}'
    return p[0]


def build(ctx):
    E, U = ctx.esc, ctx.url
    p = os.path.join(ctx.ROOT, 'data', 'ufo_cases_greece.json')
    if not os.path.exists(p):
        return
    cases = json.load(open(p, encoding='utf-8'))
    anchor = lambda r: 'case-' + r['id'].lower().replace('_', '-')

    os.makedirs(os.path.join(ctx.OUT, 'data'), exist_ok=True)
    feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [r['lon'], r['lat']]},
              'properties': {'w': r['date'], 't': r['place'], 'r': r['region'], 'e': 'p' if r['explained'] else 'u',
                             'k': BEINGS[r['beings']], 'h': r['verdict'], 'd': r['story'][:220], 'u': U('/ufo/greece/') + '#' + anchor(r)}}
             for r in cases]
    with open(os.path.join(ctx.OUT, 'data', 'ufo_greece.geojson'), 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'), ensure_ascii=False)

    n = len(cases)
    n_u = sum(1 for r in cases if not r['explained'])
    n_cy = sum(1 for r in cases if r['cc'] == 'CY')
    decades = Counter(r['year'] // 10 * 10 for r in cases)
    regions = Counter(r['region'] for r in cases)

    def item(r):
        cls = 'p' if r['explained'] else 'u'
        what = ' · '.join(x for x in (BEINGS[r['beings']], f'{r["witnesses"]} witness' + ('es' if r['witnesses'] != 1 else '')) if x)
        hay = ' '.join([r['place'], r['region'], r['story'], r['view'], r['verdict'], what, str(r['year'])]).lower()
        view = ''
        if r['view']:
            # "GRUFON thinks X" reads as "GRUFON's view: X"; notes of ours (date doubts) get a plain label
            m = re.match(r'GRUFON (?:says|thinks|notes|suggests|finds|points out)(?: that)? (.*)', r['view'], re.S)
            label, txt = ("GRUFON's view", m.group(1)[0].upper() + m.group(1)[1:]) if m else ('Note', r['view'])
            view = f'<p class="cu-note"><b>{label}:</b> {E(txt)}</p>'
        return (f'<li class="ua-faa cu-case" id="{anchor(r)}" data-hay="{E(hay)}"><div class="ua-faa-h"><span class="ua-faa-d">{E(fmt(r["date"]))}</span>'
                f'<strong>{E(r["place"])}, {E(r["region"])}</strong><span class="cu-ev cu-e-{cls}">{E(r["verdict"])}</span></div>'
                f'<p class="ua-faa-what">{E(what)}</p><p class="cu-note">{E(r["story"])}</p>{view}</li>')

    dec = ''.join(f'<li><span>{d}s</span><i style="--w:{round(100 * v / max(decades.values()))}%"></i><b>{v}</b></li>' for d, v in sorted(decades.items()))
    reg = ', '.join(f'{E(k)} ({v})' for k, v in regions.most_common(6))
    css = (f'<link rel="stylesheet" href="{U("/static/ufo_archive.css")}"><link rel="stylesheet" href="{U("/static/ufo_canada.css")}">'
           '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>')
    js = f'<script src="{U("/static/ufo_archive.js")}" defer></script><script src="{U("/static/ufo_canada.js")}" defer></script>'
    body = f'''
<section class="band band-dark ua-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/ufo/')}">UFOs</a> / Greece</p>
    <h1>Close encounters in Greece, 1901 to 2007</h1>
    <p class="lede">Shepherds on Penteli, firefighters at Vravrona, soldiers on the Evros border and a giant on a village road in Kilkis.
    These are {n} Greek cases where people said they saw the beings, not just the lights, with a verdict on each one from {CREDIT}.</p>
    <ul class="ua-stats"><li><b>{n}</b> close encounters</li><li><b>{n_u}</b> with no explanation found</li><li><b>{max(r["year"] for r in cases) - min(r["year"] for r in cases)}</b> years covered</li></ul>
  </div>
</section>
<div class="band band-dark cu-mapband"><div class="wrap"><div class="cu-map" data-geojson="{U('/data/ufo_greece.geojson')}" data-bounds="19.3,34.5,32.8,41.9" data-cluster="0" data-towns="0" role="region" aria-label="Map of close encounters in Greece and Cyprus"></div>
<p class="cu-legend"><span><i class="cu-e-u"></i>No explanation found</span><span><i class="cu-e-p"></i>GRUFON thinks there is a likely explanation</span></p>
<p class="small muted">Tap a dot to read the case. Places are the nearest village or town, not the exact spot.</p></div></div>
<div class="band band-mist"><div class="wrap">
  <div class="cu-two">
    <section><h2>When they happened</h2><ul class="cu-hbars">{dec}</ul>
      <p>The late 1970s were the busiest years, with {decades[1970]} cases in the 1970s and {sum(1 for r in cases if r['year'] == 1978)} in 1978 alone, from Crete to Pelion.</p></section>
    <section><h2>Where</h2><p>Attica, around Athens, leads by far, with Mount Penteli turning up again and again. After that: {reg}.{f" One case comes from Cyprus." if n_cy == 1 else ""}</p>
      <p>Several are winged figures, like the 1954 "winged man" of Kos and the figure an astronomer on Rhodes saw cross the face of the Moon in 1976.</p></section>
  </div>
  <h2>All {n} cases, oldest first</h2>
  <p>Each case is retold in our own words. The verdict is GRUFON's. "No explanation found" means their investigators could not find an ordinary cause; other verdicts, like "possibly a dream" or "probably made up", are their best judgement, not proof.</p>
  <div class="ua-filter"><label class="visually-hidden" for="ua-q">Search the Greek cases</label>
  <input id="ua-q" type="search" placeholder="Search: Penteli, winged, Crete, soldiers..." autocomplete="off"><p class="ua-count" aria-live="polite"></p></div>
  <ol class="ua-faas" data-filter-list data-limit="{n}">{"".join(item(r) for r in cases)}</ol>
  <p class="empty" hidden>No case matches.</p>
  <h2>About this data</h2>
  <p>These cases were shared with Encounter Atlas by {GRUFON_LINK}, which collects and investigates Greek UFO reports, from its catalogue of close encounters of the third kind (encounters where people say they saw beings). Thank you to GRUFON for sharing them.
  We retold each description in our own words, left out witnesses' names, and moved a few dots that the catalogue had placed at a regional centre to the village named in the case.</p>
  <p>More: <a href="{U('/ufo/cases/')}">Famous UFO cases worldwide</a> · <a href="{U('/map/')}">The world map</a> · <a href="{U('/near-me/')}">Sightings near you</a> · <a href="{U('/report/')}">Report your own sighting</a></p>
</div></div>{js}'''
    ctx.write('/ufo/greece/', ctx.page('/ufo/greece/', 'Close encounters in Greece: UFO landings and beings, 1901 to 2007', body,
                                       f'{n} Greek close encounters on one map, from a Penteli shepherd in 1901 to soldiers on the Evros border, each retold with the Greek UFO Network\'s verdict.',
                                       head_extra=css))

    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if os.path.exists(sp):
        items = json.load(open(sp, encoding='utf-8'))
        items.append({'t': 'Close encounters in Greece', 'a': 'greece greek cyprus athens crete rhodes penteli', 'k': f'{n} cases, 1901 to 2007',
                      'u': U('/ufo/greece/'), 'i': 'saucer', 'c': 'ufo'})
        with open(sp, 'w', encoding='utf-8') as f:
            json.dump(items, f, separators=(',', ':'))

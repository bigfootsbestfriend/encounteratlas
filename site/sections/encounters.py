"""Close encounters with beings: a hub (/encounters/) and one page per case, from data/close_encounters.json.

Cases are well-documented reports of beings or occupants (goblins, small humanoids, 'frogmen'), each with what
witnesses said, what investigators found, the explanations offered and sources. Map pins mark where it happened.
"""
import json, os

MON = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
STATUS = {'unexplained': ('Unexplained', 'No accepted explanation'), 'disputed': ('Disputed', 'Explanations offered, still argued over'),
          'explained': ('Explained', 'Most investigators accept an explanation'), 'hoax': ('Hoax', 'Admitted or proven hoax')}
COUNTRY = {'US': 'United States', 'FR': 'France', 'BR': 'Brazil', 'ZW': 'Zimbabwe', 'AU': 'Australia', 'PG': 'Papua New Guinea',
           'RU': 'Russia', 'SU': 'USSR', 'CA': 'Canada', 'GB': 'United Kingdom', 'DE': 'Germany', 'CH': 'Switzerland', 'SE': 'Sweden',
           'BE': 'Belgium', 'NZ': 'New Zealand'}


def build(ctx):
    path = os.path.join(ctx.ROOT, 'data', 'close_encounters.json')
    if not os.path.exists(path):
        return
    cases = json.load(open(path, encoding='utf-8'))
    for x in cases:
        x['creatures'] = [s for s in x.get('creatures', []) if s in ctx.by_slug]
    cases.sort(key=lambda x: (x['date'], x['slug']))
    E(ctx, cases).run()


def dateline(d):
    p = d.split('-')
    if len(p) == 3:
        return f'{MON[int(p[1])]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MON[int(p[1])]} {p[0]}'
    return p[0]


class E:
    BASE, GEO, LABEL = '/encounters/', 'encounters.geojson', 'Close encounters'

    def __init__(self, ctx, cases):
        self.c, self.cases = ctx, cases
        self.u, self.e = ctx.url, ctx.esc
        self.head = (f'<link rel="stylesheet" href="{self.u("/static/encounters.css")}">'
                     '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
                     '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
                     f'<script src="{self.u("/static/encounters.js")}" defer></script>')

    def run(self):
        self.geojson()
        self.hub()
        for x in self.cases:
            self.case(x)

    def url(self, x):
        return self.u(self.BASE + x['slug'] + '/')

    def mark(self, x):
        """The case's first related creature's silhouette, else a grey alien."""
        cr = self.c.by_slug.get((x['creatures'] or ['grey-aliens'])[0]) or self.c.by_slug.get('grey-aliens')
        return f'<span class="badge badge-md art cat-{cr["cat"]}"><img src="{self.u("/static/" + cr["art"] + ".svg")}" alt="" width="64" height="64" loading="lazy"></span>' if cr and cr.get('art') else ''

    def pill(self, x):
        return f'<span class="ce-pill s-{x["status"]}">{STATUS[x["status"]][0]}</span>'

    def no_beings(self, x):
        return x['beings'].lower().startswith('no beings')

    def card(self, x):
        e = self.e
        return (f'<article class="ce-card" data-s="{x["status"]}" data-b="{0 if self.no_beings(x) else 1}">'
                f'<a href="{self.url(x)}">{self.mark(x)}<span class="ce-txt"><span class="ce-meta">{e(dateline(x["date"]))} · {e(x["place"])}</span>'
                f'<span class="ce-name">{e(x["name"])}</span><span class="ce-sum">{e(x["summary"])}</span>{self.pill(x)}</span></a></article>')

    def geojson(self):
        feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [x['lon'], x['lat']]},
                  'properties': {'s': x['slug'], 'n': x['name'], 'd': dateline(x['date']), 'p': x['place'], 'st': x['status'],
                                 'u': self.url(x)}} for x in self.cases]
        os.makedirs(os.path.join(self.c.OUT, 'data'), exist_ok=True)
        with open(os.path.join(self.c.OUT, 'data', self.GEO), 'w', encoding='utf-8') as f:
            json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'), ensure_ascii=False)

    def hub(self):
        c, e = self.c, self.e
        n = len(self.cases)
        countries = len({x['cc'] for x in self.cases})
        counts = {k: sum(1 for x in self.cases if x['status'] == k) for k in STATUS}
        chips = (f'<button type="button" class="ce-chip" data-f="" aria-pressed="true">All <span>{n}</span></button>'
                 + ''.join(f'<button type="button" class="ce-chip" data-f="{k}" aria-pressed="false">{v[0]} <span>{counts[k]}</span></button>'
                           for k, v in STATUS.items() if counts[k])
                 + f'<button type="button" class="ce-chip" data-f="beings" aria-pressed="false">Beings seen <span>{sum(1 for x in self.cases if not self.no_beings(x))}</span></button>')
        by_dec = {}
        for x in self.cases:
            by_dec.setdefault(x['year'] // 10 * 10, []).append(x)
        groups = ''.join(f'<section class="ce-dec"><h2>The {d}s</h2><div class="ce-grid">{"".join(self.card(x) for x in v)}</div></section>'
                         for d, v in sorted(by_dec.items()))
        body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/ufo/')}">UFOs</a> / Close encounters</p>
  <h1>Close encounters with beings</h1>
  <p class="lede">{n} of the best-documented cases where people said they saw the occupants, not just the lights: goblins at a Kentucky farmhouse, a 'monster' at Flatwoods, small beings in a French lavender field. {countries} countries, {self.cases[0]['year']} to {self.cases[-1]['year']}.</p>
  <div class="ce-chips" role="group" aria-label="Filter cases">{chips}</div>
  <div class="map-frame ce-map"><div id="ce-map" class="map" data-geojson="{self.u('/data/encounters.geojson')}"></div></div>
</div></section>
<div class="band band-mist ce-list"><div class="wrap">
  <p class="ce-status" aria-live="polite"></p>
  {groups}
  <aside class="ce-note"><h2>How we write these up</h2><p>Each case says what the witnesses reported, in the order they told it, then what police, the Air Force's Project Blue Book or other investigators found and the explanations people have offered. "Disputed" means explanations exist but are still argued over; we only call something a hoax when it was admitted or proven. Where a case is in the Blue Book files at the National Archives, we link the folder.</p></aside>
</div></div>'''
        c.write('/encounters/', c.page('/encounters/', 'Close encounters with beings: Hopkinsville goblins, Flatwoods and more', body,
                                       f'{n} documented close encounters with beings, from the 1955 Kelly-Hopkinsville goblins to Flatwoods, '
                                       'Valensole and Pascagoula: what witnesses said, what investigators found, and sources.',
                                       body_class='encounters', head_extra=self.head))

    def case(self, x):
        c, e = self.c, self.e
        paras = ''.join(f'<p>{e(p)}</p>' for p in x['body'])
        off = ''.join(f'<li><b>{e(o["agency"])}</b> {e(o["note"])}</li>' for o in x.get('official', []))
        if x.get('bluebook'):
            off += (f'<li><b>Project Blue Book folder</b> <a href="https://catalog.archives.gov/id/{int(x["bluebook"])}" rel="noopener">'
                    f'Read the scanned Air Force file at the National Archives</a></li>')
        src = ''.join(f'<li><a href="{e(s["url"])}" rel="noopener">{e(s["title"])}</a></li>' for s in x['sources'])
        crs = ''.join(c.creature_card(c.by_slug[s]) for s in x['creatures'])
        i = self.cases.index(x)
        prev = self.cases[i - 1] if i else None
        nxt = self.cases[i + 1] if i + 1 < len(self.cases) else None
        pn = ''.join(f'<a class="ce-pn {k}" href="{self.url(y)}"><small>{lab}</small>{e(y["name"])}</a>'
                     for k, lab, y in (('prev', 'Earlier case', prev), ('next', 'Later case', nxt)) if y)
        country = COUNTRY.get(x['cc'], x['cc'])
        body = f'''
<section class="band band-dark ce-head"><div class="wrap ce-hero">
  {self.mark(x)}
  <div>
    <p class="crumb"><a href="{self.u(self.BASE)}">{self.LABEL}</a> / {e(str(x['year']))}</p>
    <h1>{e(x['name'])}</h1>
    <p class="ce-when">{e(dateline(x['date']))} · {e(x['place'])}</p>
    <p class="lede">{e(x['summary'])}</p>
  </div>
</div></section>
<div class="band band-mist"><div class="wrap ce-body">
  <article class="prose">{paras}</article>
  <aside class="ce-side">
    <div class="ce-facts">
      <p><b>Status</b>{self.pill(x)}<small>{e(x.get('status_note') or STATUS[x['status']][1])}</small></p>
      <p><b>What they saw</b>{e(x['beings'])}</p>
      <p><b>Witnesses</b>{e(x['witnesses'])}</p>
      <p><b>Where</b>{e(x['place'])}{'' if country in x['place'] else ', ' + e(country)}</p>
    </div>
    <div class="map-frame ce-mini"><div id="ce-map" class="map" data-geojson="{self.u('/data/' + self.GEO)}" data-focus="{x['slug']}"></div></div>
  </aside>
</div></div>
<div class="band ce-more"><div class="wrap">
  {f'<h2>Official records</h2><ul class="ce-off">{off}</ul>' if off else ''}
  {f'<h2>Related creatures</h2><div class="crit-grid">{crs}</div>' if crs else ''}
  <h2>Sources</h2><ul class="ce-src">{src}</ul>
  <nav class="ce-pns" aria-label="More cases">{pn}</nav>
  <p><a href="{self.u(self.BASE)}">All {len(self.cases)} {self.LABEL.lower()}</a></p>
</div></div>'''
        c.write(self.BASE + x['slug'] + '/', c.page(self.BASE + x['slug'] + '/', f'{x["name"]} ({x["year"]})', body,
                                                         x['summary'], body_class='encounters', head_extra=self.head))

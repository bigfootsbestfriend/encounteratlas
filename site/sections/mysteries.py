"""Unexplained mysteries: a hub (/mysteries/) and one page per case, from data/mysteries.json.

Strange events, places, lights, sounds and vanishings that are not creatures or close encounters. Each page gives what
happened, a timeline, every theory with how well it holds up, how to visit, photos (Wikimedia Commons, licence-checked,
data/mystery_photos.json) and sources. Map pins mark where it happened; the main map gets the same layer.
"""
import json, os

MON = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
TYPES = {'event': ('Strange events', 'Blasts, deaths and happenings nobody could explain at the time', '#E07A4F'),
         'place': ('Strange places', 'Valleys, islands and stretches of sea with a reputation', '#6FA8DC'),
         'lights': ('Mystery lights', 'Glowing lights that come back to the same spot', '#F2B33D'),
         'signal': ('Sounds and signals', 'Hums, bursts and noises from nowhere', '#7FC8A9'),
         'vanishing': ('Vanishings', 'People and crews who were never found', '#A99CF0')}
STATUS = {'unexplained': ('Unexplained', 'No accepted explanation'), 'disputed': ('Disputed', 'Explanations offered, still argued over'),
          'solved': ('Mostly solved', 'Most investigators accept an explanation'), 'legend': ('Legend', 'Real events wrapped in later storytelling')}
VERDICT = {'leading': 'Best fit', 'possible': 'Possible', 'unlikely': 'Unlikely', 'no-evidence': 'No evidence', 'disproved': 'Ruled out'}
COUNTRY = {'US': 'United States', 'CA': 'Canada', 'RU': 'Russia', 'NO': 'Norway', 'GB': 'United Kingdom'}


def build(ctx):
    path = os.path.join(ctx.ROOT, 'data', 'mysteries.json')
    if not os.path.exists(path):
        return
    cases = json.load(open(path, encoding='utf-8'))
    pp = os.path.join(ctx.ROOT, 'data', 'mystery_photos.json')
    photos = json.load(open(pp, encoding='utf-8')) if os.path.exists(pp) else {}
    for x in cases:
        x['creatures'] = [s for s in x.get('creatures', []) if s in ctx.by_slug]
        x['photos'] = photos.get(x['slug'], [])
    cases.sort(key=lambda x: (x['year'], x['slug']))
    M(ctx, cases).run()


def dateline(d):
    p = d.split('-')
    if len(p) == 3:
        return f'{MON[int(p[1])]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MON[int(p[1])]} {p[0]}'
    return p[0]


class M:
    def __init__(self, ctx, cases):
        self.c, self.cases = ctx, cases
        self.u, self.e = ctx.url, ctx.esc
        self.head = (f'<link rel="stylesheet" href="{self.u("/static/encounters.css")}">'
                     f'<link rel="stylesheet" href="{self.u("/static/mysteries.css")}">'
                     '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
                     '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
                     f'<script src="{self.u("/static/mysteries.js")}" defer></script>')

    def run(self):
        self.geojson()
        self.hub()
        for x in self.cases:
            self.case(x)

    def url(self, x):
        return self.u('/mysteries/' + x['slug'] + '/')

    def pill(self, x):
        return f'<span class="ce-pill my-s-{x["status"]}">{STATUS[x["status"]][0]}</span>'

    def tpill(self, x):
        return f'<span class="my-type" style="--t:{TYPES[x["type"]][2]}">{TYPES[x["type"]][0]}</span>'

    def thumb(self, x):
        ph = x['photos'][0] if x['photos'] else None
        if not ph:
            return f'<span class="my-thumb my-thumb-blank" style="--t:{TYPES[x["type"]][2]}" aria-hidden="true"></span>'
        return f'<img class="my-thumb" src="{self.u(ph["src"])}" alt="" width="320" height="200" loading="lazy">'

    def card(self, x):
        e = self.e
        return (f'<article class="my-card" data-t="{x["type"]}" data-s="{x["status"]}">'
                f'<a href="{self.url(x)}">{self.thumb(x)}<span class="my-txt"><span class="ce-meta">{e(str(x["year"]))} · {e(x["place"])}</span>'
                f'<span class="ce-name">{e(x["name"])}</span><span class="ce-sum">{e(x["summary"])}</span>'
                f'<span class="my-pills">{self.tpill(x)}{self.pill(x)}</span></span></a></article>')

    def geojson(self):
        feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [x['lon'], x['lat']]},
                  'properties': {'s': x['slug'], 'n': x['name'], 'd': str(x['year']), 'p': x['place'], 't': x['type'],
                                 'c': TYPES[x['type']][2], 'st': STATUS[x['status']][0], 'u': self.url(x)}} for x in self.cases]
        os.makedirs(os.path.join(self.c.OUT, 'data'), exist_ok=True)
        with open(os.path.join(self.c.OUT, 'data', 'mysteries.geojson'), 'w', encoding='utf-8') as f:
            json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'), ensure_ascii=False)

    def hub(self):
        c, e = self.c, self.e
        n = len(self.cases)
        tc = {k: sum(1 for x in self.cases if x['type'] == k) for k in TYPES}
        chips = (f'<button type="button" class="ce-chip" data-f="" aria-pressed="true">All <span>{n}</span></button>'
                 + ''.join(f'<button type="button" class="ce-chip" data-f="{k}" aria-pressed="false" style="--t:{v[2]}">'
                           f'<i class="my-dot" aria-hidden="true"></i>{v[0]} <span>{tc[k]}</span></button>'
                           for k, v in TYPES.items() if tc[k]))
        groups = ''.join(f'<section class="ce-dec my-group" data-t="{k}"><h2>{v[0]}</h2><p class="my-gsub">{e(v[1])}</p>'
                         f'<div class="my-grid">{"".join(self.card(x) for x in self.cases if x["type"] == k)}</div></section>'
                         for k, v in TYPES.items() if tc[k])
        body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb">Mysteries</p>
  <h1>Unexplained mysteries, mapped</h1>
  <p class="lede">{n} strange events, places, lights and vanishings, from the Tunguska blast to the Dyatlov Pass and the lost colony of Roanoke. Every theory gets an honest rating, from best fit to ruled out.</p>
  <div class="ce-chips" role="group" aria-label="Filter mysteries">{chips}</div>
  <div class="map-frame ce-map"><div id="my-map" class="map" data-geojson="{self.u('/data/mysteries.geojson')}"></div></div>
</div></section>
<div class="band band-mist ce-list"><div class="wrap">
  <p class="ce-status" aria-live="polite"></p>
  {groups}
  <aside class="ce-note"><h2>How we write these up</h2><p>We start with what was reported at the time, then list every serious theory with a plain rating: best fit, possible, unlikely, no evidence or ruled out. "Mostly solved" means most investigators accept an explanation, even if some people still argue. Where real people died or went missing, we stick to the official record and published sources and don't speculate about the people involved. Photos come from Wikimedia Commons, with the credit and licence under each one.</p></aside>
</div></div>'''
        c.write('/mysteries/', c.page('/mysteries/', 'Unexplained mysteries: Tunguska, Dyatlov Pass, Roanoke and more, mapped', body,
                                      f'{n} unexplained mysteries on a map: the Tunguska event, Dyatlov Pass, Oak Island, the Mary Celeste, '
                                      'Hessdalen lights and more, with every theory rated.', body_class='encounters mysteries', head_extra=self.head))

    def figure(self, ph, cls=''):
        e = self.e
        lic = (f'<a href="{e(ph["licence_url"])}" rel="noopener license">{e(ph["licence"])}</a>' if ph.get('licence_url') else e(ph['licence']))
        return (f'<figure class="my-fig {cls}"><img src="{self.u(ph["src"])}" alt="{e(ph["caption"])}" loading="lazy">'
                f'<figcaption>{e(ph["caption"])}<small>Photo: {e(ph["credit"])} · {lic} · '
                f'<a href="{e(ph["page"])}" rel="noopener">Wikimedia Commons</a></small></figcaption></figure>')

    def case(self, x):
        c, e = self.c, self.e
        paras = ''.join(f'<p>{e(p)}</p>' for p in x['body'])
        tl = ''.join(f'<li><b>{e(t["when"])}</b><span>{e(t["what"])}</span></li>' for t in x.get('timeline', []))
        th = ''.join(f'<li class="my-th v-{t["verdict"]}"><span class="my-v">{VERDICT[t["verdict"]]}</span>'
                     f'<b>{e(t["name"])}</b><p>{e(t["note"])}</p></li>' for t in x.get('theories', []))
        src = ''.join(f'<li><a href="{e(s["url"])}" rel="noopener">{e(s["title"])}</a></li>' for s in x['sources'])
        crs = ''.join(c.creature_card(c.by_slug[s]) for s in x['creatures'])
        hero = self.figure(x['photos'][0], 'my-hero-fig') if x['photos'] else ''
        more = ''.join(self.figure(p) for p in x['photos'][1:])
        i = self.cases.index(x)
        prev = self.cases[i - 1] if i else None
        nxt = self.cases[i + 1] if i + 1 < len(self.cases) else None
        pn = ''.join(f'<a class="ce-pn {k}" href="{self.url(y)}"><small>{lab}</small>{e(y["name"])}</a>'
                     for k, lab, y in (('prev', 'Earlier mystery', prev), ('next', 'Later mystery', nxt)) if y)
        country = COUNTRY.get(x['cc'], '')
        where = e(x['place']) + ('' if not country or country in x['place'] else ', ' + e(country))
        body = f'''
<section class="band band-dark ce-head"><div class="wrap my-hero">
  <div>
    <p class="crumb"><a href="{self.u('/mysteries/')}">Mysteries</a> / {e(TYPES[x['type']][0])}</p>
    <h1>{e(x['name'])}</h1>
    <p class="ce-when">{e(dateline(x['date']))} · {e(x['place'])}</p>
    <p class="lede">{e(x['summary'])}</p>
  </div>
  {hero}
</div></section>
<div class="band band-mist"><div class="wrap ce-body">
  <article class="prose">{paras}{more}</article>
  <aside class="ce-side">
    <div class="ce-facts">
      <p><b>Status</b>{self.pill(x)}<small>{e(x.get('status_note') or STATUS[x['status']][1])}</small></p>
      <p><b>Type</b>{self.tpill(x)}</p>
      <p><b>Where</b>{where}</p>
      {f'<p><b>Visiting</b>{e(x["visit"])}</p>' if x.get('visit') else ''}
    </div>
    <div class="map-frame ce-mini"><div id="my-map" class="map" data-geojson="{self.u('/data/mysteries.geojson')}" data-focus="{x['slug']}"></div></div>
  </aside>
</div></div>
<div class="band ce-more"><div class="wrap">
  {f'<h2>Timeline</h2><ol class="my-tl">{tl}</ol>' if tl else ''}
  {f'<h2>The theories, rated</h2><ul class="my-ths">{th}</ul>' if th else ''}
  {f'<h2>Related</h2><div class="crit-grid">{crs}</div>' if crs else ''}
  <h2>Sources</h2><ul class="ce-src">{src}</ul>
  <nav class="ce-pns" aria-label="More mysteries">{pn}</nav>
  <p><a href="{self.u('/mysteries/')}">All {len(self.cases)} mysteries</a></p>
</div></div>'''
        c.write('/mysteries/' + x['slug'] + '/', c.page('/mysteries/' + x['slug'] + '/', f'{x["name"]}: what happened and the theories', body,
                                                        x['summary'], body_class='encounters mysteries', head_extra=self.head, article={'updated': x.get('updated')}))

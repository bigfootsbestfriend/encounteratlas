"""Historic encounters: strange-creature, sea-serpent, wild-man and airship reports from old US and New Zealand newspapers.

Pages: /history/ (intro, decade strip, topic chips, map, every case), /history/<topic>/ (timeline per topic),
/history/<state>/ (states with 5+ cases). Writes /data/historic.geojson.

Data: data/historic.json (collector/historic.py). Summaries are our own words; each case cites the newspaper
pages (Library of Congress Chronicling America; National Library of New Zealand Papers Past) it came from. Sources and licences: data/historic_SOURCES.md.
"""
import json, os
from collections import Counter, defaultdict

# key: (page slug, chip label, page title, icon, colour)
TOPICS = {
    'airship': ('airships-1896-1897', 'Mystery airships, 1896-97', 'The mystery airship wave of 1896 and 1897', 'airship', '#8E8CF0'),
    'airship-1909': ('phantom-airships-1909', 'Phantom airships, 1909', 'The phantom airships of 1909', 'airship', '#7FB2F0'),
    'wild-man': ('wild-men', 'Wild men', 'Wild man and hairy giant reports', 'hominid', '#D9A05B'),
    'sea-serpent': ('sea-serpents', 'Sea serpents and lake monsters', 'Sea serpents and lake monsters', 'serpent', '#4FB3A9'),
    'jersey-devil': ('jersey-devil-1909', 'Jersey Devil, 1909', 'Jersey Devil week, January 1909', 'winged', '#B98ACB'),
    'giant-bird': ('giant-birds', 'Giant birds', 'Giant birds and flying monsters', 'thunderbird', '#E0A060'),
    'phantom-light': ('phantom-lights', 'Phantom lights', 'Phantom lights and ghost lights', 'orbs', '#F2B33D'),
    'creature': ('strange-creatures', 'Other strange creatures', 'Other strange creatures', 'eyeshine', '#9CC46B'),
}
TOPIC_INTRO = {
    'airship': 'From November 1896 in California to April 1897 across the Midwest, papers filled with lighted "airships" '
               'cruising at night. Some reports were honest puzzlement, many were jokes, and a few were elaborate hoaxes '
               'that newspapers printed with a wink.',
    'airship-1909': 'In 1909, with real aeroplanes in the news, night lights were again taken for secret airships: over the '
                    'Salton Sea in June, around San Francisco Bay in August and across New England in December, after a '
                    'Worcester businessman claimed he had flown to New York and back by night. In New Zealand the same winter, '
                    'Otago and Southland spent late July and early August watching for a "scareship".',
    'wild-man': 'Nineteenth-century papers loved a "wild man of the woods": a hairy figure seen by hunters, farmers or '
                'children, usually never caught. Some turned out to be escaped asylum patients or hermits; others are '
                'remembered today as early Bigfoot-type stories.',
    'sea-serpent': 'Sea serpents off New England, monsters in Midwestern lakes and long things in rivers. Sightings by '
                   'fishermen and steamboat crews ran next to obvious newspaper fun, so read each one with care.',
    'jersey-devil': 'In the third week of January 1909, towns across South Jersey and around Philadelphia reported hoof '
                    'prints in the snow and a winged, horse-headed creature. Schools closed, mills shut and the press '
                    'had a field day.',
    'giant-bird': 'Birds big enough to carry off a child, winged "dragons" and eagles with impossible wingspans. A few '
                  'were real large birds shot and measured; others grew with every retelling.',
    'phantom-light': 'Lights bobbing over swamps, railroad tracks and graveyards. The papers called them ghost lights, '
                     'jack-o\'-lanterns or simply "the mysterious light".',
    'creature': 'Everything else: nameless beasts in the swamp, "what-is-its" and creatures that fit no category.',
}
STATE_NAMES = ['Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware',
               'District of Columbia', 'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas',
               'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi',
               'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
               'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island',
               'South Carolina', 'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
               'West Virginia', 'Wisconsin', 'Wyoming']
MON = ['', 'Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.']
DECADES = list(range(1830, 1930, 10))
SOURCE_NOTE = ('Newspaper pages: Library of Congress, <a href="https://www.loc.gov/collections/chronicling-america/" rel="noopener">'
               'Chronicling America</a> (US newspapers published before 1927 are in the public domain). Text search: '
               '<a href="https://huggingface.co/datasets/dell-research-harvard/AmericanStories" rel="noopener">American Stories</a> '
               '(Dell, Bryan, Carlson and others, CC BY 4.0). New Zealand pages: National Library of New Zealand, '
               '<a href="https://paperspast.natlib.govt.nz/" rel="noopener">Papers Past</a>, found through the '
               '<a href="https://digitalnz.org/" rel="noopener">DigitalNZ</a> API. Summaries are our own. Place data: GeoNames (CC BY 4.0).')


def build(ctx):
    path = os.path.join(ctx.ROOT, 'data', 'historic.json')
    if not os.path.exists(path):
        return
    cases = json.load(open(path, encoding='utf-8'))
    cases = [c for c in cases if c['k'] in TOPICS]
    for c in cases:
        if c.get('creature') and c['creature'] not in ctx.by_slug:
            c['creature'] = ''
        for pp in c['papers']:  # a few LCCNs have no title in American Stories
            if not pp['paper'].strip():
                pp['paper'] = 'Unnamed newspaper'
            if not pp.get('place', '').strip():
                pp['place'] = 'place not recorded'
    cases.sort(key=lambda c: (c['date'], c['id']))
    H(ctx, cases).run()


def dateline(d):
    p = d.split('-')
    if len(p) == 3:
        return f'{MON[int(p[1])]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MON[int(p[1])]} {p[0]}'
    return p[0]


class H:
    def __init__(self, ctx, cases):
        self.c, self.cases = ctx, cases
        self.u, self.e = ctx.url, ctx.esc
        self.states = defaultdict(list)
        for x in cases:
            if x.get('state') in STATE_NAMES:
                self.states[x['state']].append(x)
            elif x.get('country') == 'NZ':
                self.states['New Zealand'].append(x)
        self.state_pages = {s: v for s, v in self.states.items() if len(v) >= 5}
        self.css = (f'<link rel="preconnect" href="https://fonts.googleapis.com">'
                    f'<link href="https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&display=swap" rel="stylesheet">'
                    f'<link rel="stylesheet" href="{self.u("/static/historic.css")}">')
        self.head = (self.css +
                     '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
                     '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
                     f'<script src="{self.u("/static/historic.js")}" defer></script>')

    def run(self):
        self.geojson()
        self.hub()
        for k in TOPICS:
            self.topic(k)
        for s in self.state_pages:
            self.state(s)

    # ---------- pieces ----------
    def topic_url(self, k):
        return self.u('/history/' + TOPICS[k][0] + '/')

    def card(self, x, show_topic=True):
        e, c = self.e, self.c
        k = x['k']
        p0 = x['papers'][0]
        more = len(x['papers']) - 1
        ico = c.icon(TOPICS[k][3], 'ico')
        topic = (f'<a class="hc-topic t-{k}" href="{self.topic_url(k)}">{ico}{e(TOPICS[k][1])}</a>' if show_topic else '')
        quote = f'<blockquote class="hc-quote">&ldquo;{e(x["quote"])}&rdquo;</blockquote>' if x.get('quote') else ''
        hoax = (f'<p class="hc-hoax"><span class="hc-stamp">Probably a hoax or tall tale</span> {e(x["hoax"])}</p>'
                if x.get('hoax') else '')
        crit = ''
        if x.get('creature'):
            cr = c.by_slug[x['creature']]
            crit = (f'<a class="hc-crit" href="{self.u("/creatures/" + cr["slug"] + "/")}">'
                    f'<span class="badge cat-{cr["cat"]}">{c.crit_icon(cr)}</span>{e(cr["name"])}</a>')
        carried = ''
        if more:
            items = ''.join(f'<li><a href="{e(p["url"])}" rel="noopener">{e(p["paper"])}</a>'
                            f'{", " + e(p["place"]) if p.get("place") else ""}, {e(dateline(p["date"]))}{", p. " + e(p["page"]) if p.get("page") else ""}</li>'
                            for p in x['papers'][1:])
            carried = (f'<details class="hc-more"><summary>Also printed in {more} other paper{"s" if more > 1 else ""}</summary>'
                       f'<ul>{items}</ul></details>')
        approx = ' <span class="hc-approx" title="Map pin marks the nearest town or the general area">approx.</span>' if x.get('approx') else ''
        names = ' '.join([x['title'], x.get('place', ''), x.get('state', ''), TOPICS[k][1]] + [p['paper'] for p in x['papers']]).lower()
        return f'''<article class="hc t-{k}" id="h-{e(x['id'])}" data-k="{k}" data-dec="{x['date'][:3]}0" data-names="{e(names)}">
  <header class="hc-mast"><span class="hc-paper">{e(p0['paper'])}</span><span class="hc-rule"></span>
    <span class="hc-dateline">{e(p0.get('place') or '')}{' · ' if p0.get('place') else ''}{e(dateline(p0['date']))}{' · Page ' + e(p0['page']) if p0.get('page') else ''}</span></header>
  <h3 class="hc-title">{e(x['title'])}</h3>
  <p class="hc-where">{c.icon('q-pin', 'ico')}<span>{e(x['place'])}{approx} · {e(dateline(x['date']))}</span></p>
  <p class="hc-sum">{e(x['summary'])}</p>
  {quote}{hoax}
  <footer class="hc-foot">{topic}{crit}<a class="hc-orig" href="{e(p0['url'])}" rel="noopener">{c.icon('newspaper', 'ico')}Read the original page</a></footer>
  {carried}
</article>'''

    def decade_strip(self, cases, link=False):
        cnt = Counter(int(x['date'][:3] + '0') for x in cases)
        top = max(cnt.values()) if cnt else 1
        cells = ''
        for d in DECADES:
            n = cnt.get(d, 0)
            h = 6 + round(94 * n / top) if n else 0
            inner = (f'<span class="hd-bar" style="--h:{h}%"></span><span class="hd-n">{n or ""}</span>'
                     f'<span class="hd-y">{d}s</span>')
            if n and not link:
                cells += f'<button type="button" class="hd" data-dec="{d}" aria-pressed="false" aria-label="{d}s: {n} cases">{inner}</button>'
            else:
                cells += f'<span class="hd{" is-empty" if not n else ""}">{inner}</span>'
        return f'<div class="hd-strip" role="group" aria-label="Cases by decade">{cells}</div>'

    def chips(self, cases):
        cnt = Counter(x['k'] for x in cases)
        out = f'<button type="button" class="chip hc-chip" data-k="" aria-pressed="true">All <span class="hc-n">{len(cases)}</span></button>'
        for k, t in TOPICS.items():
            if cnt[k]:
                out += (f'<button type="button" class="chip hc-chip t-{k}" data-k="{k}" aria-pressed="false">'
                        f'{self.c.icon(t[3], "ico")}{self.e(t[1])} <span class="hc-n">{cnt[k]}</span></button>')
        return f'<div class="chips hc-chips" role="group" aria-label="Filter by type">{out}</div>'

    def map_block(self, attrs=''):
        return (f'<div class="map-frame hc-map"><div id="hc-map" class="map" data-geojson="{self.u("/data/historic.geojson")}" '
                f'data-base="{self.c.BASE}" {attrs}></div></div>')

    def source_box(self):
        return (f'<aside class="hc-source"><h2>Where these come from</h2><p>Every case is an old newspaper report: US papers printed before 1927 '
                f'(public domain) and New Zealand papers from Papers Past. We read the original page, wrote a short summary in plain English '
                f'and link the page at the Library of Congress or Papers Past so you can read it yourself. When the same story was reprinted in many '
                f'papers, it is one case with every paper we found listed under it.</p>'
                f'<p>Old papers printed jokes, hoaxes and tall tales as news. Where the paper itself or later reporting says a story was '
                f'made up, we mark it. Nothing here proves any creature exists. Map pins mark where the event was said to happen, not '
                f'where the paper was printed; pins marked approximate show the nearest town or the state.</p>'
                f'<p class="small">{SOURCE_NOTE}</p></aside>')

    def topic_nav(self, current=''):
        cnt = Counter(x['k'] for x in self.cases)
        out = ''
        for k, t in TOPICS.items():
            if cnt[k]:
                cur = ' aria-current="page"' if k == current else ''
                out += (f'<a class="hc-tnav t-{k}" href="{self.topic_url(k)}"{cur}>{self.c.icon(t[3], "ico")}'
                        f'<strong>{self.e(t[1])}</strong><span>{cnt[k]} case{"s" if cnt[k] != 1 else ""}</span></a>')
        return f'<nav class="hc-tnavs" aria-label="Topics">{out}</nav>'

    def state_links(self):
        if not self.state_pages:
            return ''
        items = ''.join(f'<li><a href="{self.u("/history/" + self.c.slugify(s) + "/")}">{self.e(s)}</a> '
                        f'<span class="muted">{len(v)}</span></li>' for s, v in sorted(self.state_pages.items()))
        return f'<h2>By state or country</h2><ul class="cols">{items}</ul>'

    def timeline(self, cases, show_topic=False):
        out, last = '', None
        for x in cases:
            y = x['date'][:4]
            if y != last:
                out += f'<li class="ht-year"><span>{y}</span></li>'
                last = y
            out += f'<li class="ht-item">{self.card(x, show_topic=show_topic)}</li>'
        return f'<ol class="ht">{out}</ol>'

    # ---------- outputs ----------
    def geojson(self):
        feats = []
        for x in self.cases:
            if x.get('lat') is None:
                continue
            feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [x['lon'], x['lat']]},
                          'properties': {'id': x['id'], 't': x['title'], 'y': int(x['date'][:4]), 'd': dateline(x['date']),
                                         'p': x['place'], 'c': x.get('creature') or '', 'k': x['k'],
                                         'a': 1 if x.get('approx') else 0}})
        os.makedirs(os.path.join(self.c.OUT, 'data'), exist_ok=True)
        with open(os.path.join(self.c.OUT, 'data', 'historic.geojson'), 'w', encoding='utf-8') as f:
            json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'), ensure_ascii=False)

    def hub(self):
        e, c = self.e, self.c
        n = len(self.cases)
        papers = len({p.get('lccn') or p['paper'] for x in self.cases for p in x['papers']})
        y0, y1 = self.cases[0]['date'][:4], self.cases[-1]['date'][:4]
        by_dec = defaultdict(list)
        for x in self.cases:
            by_dec[int(x['date'][:3] + '0')].append(x)
        groups = ''.join(f'<section class="hc-dec" data-dec="{d}"><h2 class="hc-dec-h">The {d}s <span class="hc-n">{len(v)}</span></h2>'
                         f'<div class="hc-grid">{"".join(self.card(x) for x in v)}</div></section>'
                         for d, v in sorted(by_dec.items()))
        body = f'''
<section class="band band-dark hc-head"><div class="wrap">
  <p class="crumb">Historic encounters</p>
  <h1>Monsters in the old newspapers</h1>
  <p class="lede">{n} strange-creature, sea-serpent, wild-man and mystery-airship reports from {papers} newspapers in the United States and New Zealand, {y0} to {y1}. Each one is summarised in plain English and links to the original page at the Library of Congress or Papers Past.</p>
  {self.decade_strip(self.cases)}
  {self.chips(self.cases)}
  {self.map_block()}
</div></section>
<div class="band band-mist hc-list"><div class="wrap">
  {self.topic_nav()}
  <p class="hc-status" aria-live="polite"></p>
  {groups}
  <p class="empty" hidden>Nothing matches that filter.</p>
  {self.state_links()}
  {c.signup_box('hist', 'This week in the old newspapers', 'Every Thursday: the monster, wild-man and airship stories printed this same week a century or more ago, plus a creature of the week and new reader reports. Unsubscribe in one click.')}
  {self.source_box()}
</div></div>'''
        c.write('/history/', c.page('/history/', 'Historic monster, sea serpent and airship reports from old newspapers', body,
                                    f'{n} historic encounter reports from US and New Zealand newspapers, {y0} to {y1}: wild men, sea serpents, the '
                                    f'1896-97 mystery airships and the 1909 Jersey Devil, each linked to the original page.',
                                    body_class='historic', head_extra=self.head))

    def topic(self, k):
        e, c = self.e, self.c
        cs = [x for x in self.cases if x['k'] == k]
        if not cs:
            return
        slug, label, title, ic, col = TOPICS[k]
        hoaxes = sum(1 for x in cs if x.get('hoax'))
        reprints = sum(len(x['papers']) for x in cs)
        crit = sorted({x['creature'] for x in cs if x.get('creature')}, key=lambda s: c.by_slug[s]['name'])
        crit_html = (f'<h2>Related creature pages</h2><div class="crit-grid">{"".join(c.creature_card(c.by_slug[s]) for s in crit)}</div>'
                     if crit else '')
        body = f'''
<section class="band band-dark hc-head t-{k}"><div class="wrap">
  <p class="crumb"><a href="{self.u('/history/')}">Historic encounters</a> / {e(label)}</p>
  <div class="hc-topic-head"><span class="hc-topic-ico t-{k}">{c.icon(ic, 'ico')}</span><h1>{e(title)}</h1></div>
  <p class="lede">{e(TOPIC_INTRO[k])}</p>
  <p class="hc-facts"><span><b>{len(cs)}</b> case{'s' if len(cs) != 1 else ''}</span><span><b>{reprints}</b> newspaper pages</span>{f'<span><b>{hoaxes}</b> marked as probable hoaxes</span>' if hoaxes else ''}</p>
  {self.map_block(f'data-k="{k}"')}
</div></section>
<div class="band band-mist"><div class="wrap">
  {self.timeline(cs)}
  {crit_html}
  <h2>Other historic topics</h2>
  {self.topic_nav(k)}
  {self.source_box()}
</div></div>'''
        c.write(f'/history/{slug}/', c.page(f'/history/{slug}/', f'{title}: {len(cs)} newspaper reports', body,
                                            f'{TOPIC_INTRO[k][:200]} {len(cs)} reports, each linked to the original page.',
                                            body_class='historic', head_extra=self.head))

    def state(self, s):
        e, c = self.e, self.c
        cs = self.state_pages[s]
        slug = c.slugify(s)
        mix = Counter(x['k'] for x in cs)
        mix_txt = '; '.join(f'{TOPICS[k][1]} ({v})' for k, v in mix.most_common())
        others = ''.join(f'<li><a href="{self.u("/history/" + c.slugify(o) + "/")}">{e(o)}</a> <span class="muted">{len(v)}</span></li>'
                         for o, v in sorted(self.state_pages.items()) if o != s)
        body = f'''
<section class="band band-dark hc-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/history/')}">Historic encounters</a> / {e(s)}</p>
  <h1>Historic monster reports in {e(s)}</h1>
  <p class="lede">{len(cs)} old newspaper reports of strange things in {e(s)}. {e(mix_txt)}. Each links to the original page.</p>
  {self.map_block(f'data-ids="{e(",".join(x["id"] for x in cs))}"')}
</div></section>
<div class="band band-mist"><div class="wrap">
  {self.timeline(cs, show_topic=True)}
  {f'<h2>Other states and countries</h2><ul class="cols">{others}</ul>' if others else ''}
  <p><a class="btn" href="{self.u('/history/')}">All historic encounters</a></p>
  <p class="small muted">{SOURCE_NOTE}</p>
</div></div>'''
        c.write(f'/history/{slug}/', c.page(f'/history/{slug}/', f'Historic monster and mystery airship reports in {s}', body,
                                            f'{len(cs)} historic newspaper reports from {s}: {mix_txt}, each with a link to the original page.',
                                            body_class='historic', head_extra=self.head))

"""Places, events and expeditions.

Pages: /places/ (hub: map, filters, list by state/province/country), /places/<region>/, /places/<slug>/,
/places/museums/, /places/roadside-attractions/, /events/ (next 12 months), /expeditions/.
Also writes /data/places.geojson for the main map's "Places to visit" layer.

Data: data/places.json. Every entry was checked by hand against the source URL stored with it.
Event dates: `start`/`end` are the announced dates (if any); `month`/`when` describe the usual timing.
"""
import json, math, os
from collections import defaultdict
from datetime import date

TYPES = {  # key: (singular, plural, icon)
    'museum': ('Museum', 'Museums', 'museum'),
    'festival': ('Festival or event', 'Festivals and events', 'festival'),
    'attraction': ('Roadside attraction', 'Roadside attractions', 'roadside'),
    'expedition': ('Expedition or tour', 'Expeditions and tours', 'expedition'),
}
COUNTRY = {'US': 'United States', 'CA': 'Canada', 'GB': 'United Kingdom', 'AU': 'Australia', 'JP': 'Japan',
           'NP': 'Nepal', 'BR': 'Brazil', 'SE': 'Sweden', 'AR': 'Argentina'}
ABBR = {'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA', 'Colorado': 'CO',
        'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
        'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
        'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
        'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
        'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC',
        'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
        'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX',
        'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
        'Wisconsin': 'WI', 'Wyoming': 'WY', 'Alberta': 'AB', 'British Columbia': 'BC', 'Manitoba': 'MB',
        'New Brunswick': 'NB', 'Nova Scotia': 'NS', 'Ontario': 'ON', 'Quebec': 'QC', 'Saskatchewan': 'SK'}
MONTH_NAMES = {'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
               'November', 'December', 'Labor', 'Easter'}
SHORT = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def build(ctx):
    P = json.load(open(os.path.join(ctx.ROOT, 'data', 'places.json'), encoding='utf-8'))
    B = Builder(ctx, P)
    B.geojson()
    B.hub()
    B.type_pages()
    B.regions()
    B.details()
    B.events()
    B.expeditions()


class Builder:
    def __init__(self, ctx, places):
        self.c = ctx
        self.today = date.today()
        self.P = sorted(places, key=lambda p: p['name'].lower())
        self.by_slug = {p['slug']: p for p in self.P}
        for p in self.P:
            p['rg'] = self.region_slug(p)
            p['creatures'] = [s for s in p['creatures'] if s in ctx.by_slug]
        self.regions_map = defaultdict(list)
        for p in self.P:
            if p['rg']:
                self.regions_map[p['rg']].append(p)
        clash = set(self.regions_map) & (set(self.by_slug) | {'museums', 'roadside-attractions'})
        assert not clash, f'region slug clashes with a place slug: {clash}'
        self.head = (f'<link rel="stylesheet" href="{ctx.url("/static/places.css")}">')
        self.map_head = (self.head +
                         '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
                         '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
                         f'<script src="{ctx.url("/static/places.js")}" defer></script>')

    # ---------- helpers ----------
    def region_slug(self, p):
        if not p['region']:
            return ''
        if p['country'] in ('US', 'CA'):
            return self.c.slugify(p['region'])
        return self.c.slugify(COUNTRY[p['country']])

    def region_name(self, p):
        return p['region'] if p['country'] in ('US', 'CA') else COUNTRY[p['country']]

    def where(self, p, short=True):
        if not p['city']:
            return 'Various locations, ' + COUNTRY[p['country']]
        if p['country'] in ('US', 'CA'):
            reg = ABBR.get(p['region'], p['region']) if short else p['region']
            return f'{p["city"]}, {reg}'
        return f'{p["city"]}, {p["region"]}, {COUNTRY[p["country"]]}' if not short else f'{p["city"]}, {COUNTRY[p["country"]]}'

    def badge(self, p, size='md'):
        return f'<span class="pl-badge pl-badge-{size} t-{p["type"]}">{self.c.icon(TYPES[p["type"]][2])}</span>'

    def u(self, path):
        return self.c.url(path)

    def date_label(self, p):
        s = date.fromisoformat(p['start'])
        e = date.fromisoformat(p['end'] or p['start'])
        if s == e:
            return f'{SHORT[s.month]} {s.day}, {s.year}'
        if s.month == e.month:
            return f'{SHORT[s.month]} {s.day} to {e.day}, {s.year}'
        return f'{SHORT[s.month]} {s.day} to {SHORT[e.month]} {e.day}, {s.year}'

    def occurrence(self, p):
        """Next occurrence inside the coming 12 months: (year, month, day or None, label, status).
        status: 'set' (dates announced), 'past' (already happened this month), 'usual' (expected, not announced)."""
        t = self.today
        if p.get('start'):
            s = date.fromisoformat(p['start'])
            e = date.fromisoformat(p['end'] or p['start'])
            if e >= t:
                return s.year, s.month, s.day, self.date_label(p), 'set'
            if (s.year, s.month) == (t.year, t.month) or (e.year, e.month) == (t.year, t.month):
                return t.year, t.month, s.day, self.date_label(p), 'past'
        m = p['month']
        y = t.year if m > t.month or (m == t.month and not p.get('start')) else t.year + 1
        w = p['when']
        return y, m, None, (w if w.lower().startswith('usually') else 'Usually ' + (w if w.split()[0] in MONTH_NAMES else w[0].lower() + w[1:])), 'usual'

    def card(self, p, show_when=True):
        kind = TYPES[p['type']][0]
        extra = ''
        if show_when and p['type'] == 'festival' and p.get('month'):
            y, m, d, label, st = self.occurrence(p)
            txt = label if st != 'usual' else f'{label}. {y} dates not announced yet'
            extra += f'<span class="pl-when{" is-set" if st == "set" else ""}">{self.c.esc(txt)}</span>'
        if p.get('price') and p['type'] != 'festival':
            extra += f'<span class="pl-price">{self.c.esc(p["price"])}</span>'
        names = ' '.join([p['name'], p['city'] or '', p['region'] or '', COUNTRY[p['country']], kind] +
                         [self.c.by_slug[s]['name'] for s in p['creatures']]).lower()
        return (f'<a class="pl-card" href="{self.u("/places/" + p["slug"] + "/")}" data-type="{p["type"]}" '
                f'data-names="{self.c.esc(names)}">{self.badge(p)}<span class="pl-txt">'
                f'<span class="pl-kind">{self.c.esc(kind)} · {self.c.esc(self.where(p))}</span>'
                f'<span class="pl-name">{self.c.esc(p["name"])}</span>'
                f'<span class="pl-sum">{self.c.esc(p["summary"])}</span>{extra}</span></a>')

    def chips(self, places):
        counts = defaultdict(int)
        for p in places:
            counts[p['type']] += 1
        out = f'<button type="button" class="chip pl-chip" data-filter="" aria-pressed="true">Everything <span class="pl-n">{len(places)}</span></button>'
        for k, (one, many, ic) in TYPES.items():
            if counts[k]:
                out += (f'<button type="button" class="chip pl-chip" data-filter="{k}" aria-pressed="false">'
                        f'<span class="pl-chip-ico t-{k}">{self.c.icon(ic)}</span>{many} <span class="pl-n">{counts[k]}</span></button>')
        return f'<div class="chips pl-chips" role="group" aria-label="Filter by type">{out}</div>'

    def map_block(self, attrs=''):
        return (f'<div class="map-frame pl-map"><div id="pl-map" class="map" data-geojson="{self.u("/data/places.geojson")}" '
                f'data-base="{self.c.BASE}" {attrs}></div></div>')

    def grouped_lists(self, places, link_regions=True):
        """US states, then Canadian provinces, then the rest of the world by country."""
        by = defaultdict(list)
        loose = []
        for p in places:
            (by[p['rg']] if p['rg'] else loose).append(p)
        html = ''
        for cc, title in (('US', 'United States'), ('CA', 'Canada'), ('XX', 'Around the world')):
            keys = [k for k, v in by.items() if (v[0]['country'] == cc if cc != 'XX' else v[0]['country'] not in ('US', 'CA'))]
            if not keys and not (cc == 'US' and loose):
                continue
            keys.sort(key=lambda k: self.region_name(by[k][0]))
            blocks = ''
            for k in keys:
                nm = self.region_name(by[k][0])
                head = (f'<a href="{self.u("/places/" + k + "/")}">{self.c.esc(nm)}</a>' if link_regions else self.c.esc(nm))
                cards = ''.join(self.card(p) for p in sorted(by[k], key=lambda p: (list(TYPES).index(p['type']), p['name'])))
                blocks += (f'<section class="pl-group" data-group="{k}"><h3 class="pl-group-h">{head} '
                           f'<span class="pl-n">{len(by[k])}</span></h3><div class="pl-grid">{cards}</div></section>')
            if cc == 'US' and loose:
                blocks += (f'<section class="pl-group"><h3 class="pl-group-h">Travelling expeditions</h3>'
                           f'<div class="pl-grid">{"".join(self.card(p) for p in loose)}</div></section>')
            html += f'<section class="pl-country"><h2 class="pl-country-h">{title}</h2>{blocks}</section>'
        return html

    def upcoming(self, n=4):
        ev = []
        for p in self.P:
            if p['type'] == 'festival' and p.get('start'):
                e = date.fromisoformat(p['end'] or p['start'])
                if e >= self.today:
                    ev.append((p['start'], p))
        ev.sort(key=lambda x: x[0])
        return [p for _, p in ev[:n]]

    def date_tile(self, p):
        y, m, d, label, st = self.occurrence(p)
        return (f'<span class="pl-date{" is-tba" if d is None else ""}"><span class="pl-date-m">{SHORT[m]}</span>'
                f'<span class="pl-date-d">{d if d else "TBA"}</span></span>')

    def creature_title(self, places):
        cats = {self.c.by_slug[s]['cat'] for p in places for s in p['creatures']}
        if 'hominid' in cats and 'ufo' in cats:
            return 'Bigfoot and UFO'
        if 'hominid' in cats:
            return 'Bigfoot'
        if cats == {'ufo'}:
            return 'UFO'
        return 'Cryptid and UFO' if 'ufo' in cats else 'Cryptid'

    def jsonld(self, p):
        loc = {'@type': 'Place', 'name': p['name'] if p['type'] != 'festival' else (p['city'] or p['name']),
               'address': {'@type': 'PostalAddress', 'streetAddress': p.get('address') or '', 'addressLocality': p['city'] or '',
                           'addressRegion': p['region'] or '', 'addressCountry': p['country']}}
        if p['lat'] is not None and not p.get('approx'):
            loc['geo'] = {'@type': 'GeoCoordinates', 'latitude': p['lat'], 'longitude': p['lon']}
        if p['type'] == 'festival':
            if not p.get('start') or date.fromisoformat(p['end'] or p['start']) < self.today:
                return ''
            d = {'@context': 'https://schema.org', '@type': 'Event', 'name': p['name'], 'description': p['summary'],
                 'startDate': p['start'], 'endDate': p['end'] or p['start'], 'location': loc,
                 'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
                 'eventStatus': 'https://schema.org/EventScheduled'}
        else:
            kind = {'museum': 'Museum', 'attraction': 'TouristAttraction', 'expedition': 'TouristTrip'}[p['type']]
            d = {'@context': 'https://schema.org', '@type': kind, 'name': p['name'], 'description': p['summary']}
            if p['type'] != 'expedition':
                d.update({k: v for k, v in loc.items() if k in ('address', 'geo')})
        if p.get('url'):
            d['url'] = p['url']
        return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace('</', '<\\/') + '</script>'

    # ---------- outputs ----------
    def geojson(self):
        feats = []
        for p in self.P:
            if p['lat'] is None:
                continue
            feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [p['lon'], p['lat']]},
                          'properties': {'slug': p['slug'], 'name': p['name'], 'type': TYPES[p['type']][0], 'k': p['type'],
                                         'city': p['city'] or '', 'region': p['region'] or '', 'country': p['country'],
                                         'rg': p['rg'], 'c': ','.join(p['creatures']), 'a': 1 if p.get('approx') else 0}})
        os.makedirs(os.path.join(self.c.OUT, 'data'), exist_ok=True)
        with open(os.path.join(self.c.OUT, 'data', 'places.geojson'), 'w', encoding='utf-8') as f:
            json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'), ensure_ascii=False)

    def hub(self):
        c, esc = self.c, self.c.esc
        n = len(self.P)
        cnt = defaultdict(int)
        for p in self.P:
            cnt[p['type']] += 1
        up = ''.join(f'<a class="pl-up" href="{self.u("/places/" + p["slug"] + "/")}">{self.date_tile(p)}'
                     f'<span><span class="pl-up-name">{esc(p["name"])}</span><span class="pl-up-meta">{esc(self.where(p))} · '
                     f'{esc(self.date_label(p))}</span></span></a>' for p in self.upcoming(4))
        body = f'''
<section class="band band-dark pl-head">
  <div class="wrap">
    <p class="crumb">Places</p>
    <h1>Cryptid and UFO places to visit</h1>
    <p class="lede">{n} museums, festivals, roadside oddities and guided expeditions, from the steel Mothman in Point Pleasant to a real Bigfoot trap in the Oregon woods. Every listing was checked against a source.</p>
    <div class="search-row pl-search">
      <label class="visually-hidden" for="pl-q">Search places</label>
      <input id="pl-q" type="search" placeholder="Search: Ohio, Mothman, Roswell, museum..." autocomplete="off">
    </div>
    {self.chips(self.P)}
    {self.map_block()}
  </div>
</section>
<div class="band band-mist pl-coming"><div class="wrap">
  <div class="pl-coming-head"><h2>Coming up</h2><a class="pl-more" href="{self.u('/events/')}">Full events calendar</a></div>
  <div class="pl-ups">{up}</div>
</div></div>
<div class="band band-mist pl-list"><div class="wrap">
  {self.grouped_lists(self.P)}
  <p class="empty" hidden>Nothing matches that yet. Know a place we should add? <a href="{self.u('/report/')}">Tell us</a>.</p>
</div></div>
{self.cta()}<div class="band band-mist"><div class="wrap"><p class="g-gearlink">Heading out? See <a href="{c.url('/gear/')}">field gear for investigators</a>: trail cameras, thermal, binoculars and safety kit.</p></div></div>'''
        c.write('/places/', c.page('/places/', 'Bigfoot museums, UFO festivals and cryptid attractions to visit', body,
                                   f'{cnt["museum"]} cryptid and UFO museums, {cnt["festival"]} festivals, {cnt["attraction"]} roadside attractions and '
                                   f'{cnt["expedition"]} expeditions in the US, Canada and beyond, mapped with dates, prices and sources.',
                                   body_class='places', head_extra=self.map_head))

    def cta(self):
        ic = self.c.icon
        return f'''
<div class="band band-dark"><div class="wrap pl-cta">
  <a href="{self.u('/events/')}">{ic('festival', 'ico')}<strong>Events calendar</strong><span>Festivals and conferences for the next 12 months</span></a>
  <a href="{self.u('/places/museums/')}">{ic('museum', 'ico')}<strong>Museums</strong><span>Footprint casts, Mothman props and Roswell files</span></a>
  <a href="{self.u('/places/roadside-attractions/')}">{ic('roadside', 'ico')}<strong>Roadside attractions</strong><span>Statues, sighting boards and viewing spots</span></a>
  <a href="{self.u('/expeditions/')}">{ic('expedition', 'ico')}<strong>Expeditions</strong><span>Guided Bigfoot hunts, UFO tours and night hikes</span></a>
</div></div>'''

    def type_pages(self):
        c = self.c
        for key, path, h1, title, lede, desc in (
            ('museum', '/places/museums/', 'Bigfoot, cryptid and UFO museums',
             'Bigfoot museums and UFO museums in the US, Canada and beyond',
             'Track casts, witness sketches, Roswell timelines and at least one jar of Bigfoot scat. These are the museums worth a detour.',
             'Every Bigfoot, Mothman, cryptid and UFO museum we could verify in the US, Canada and worldwide, with addresses, prices and maps.'),
            ('attraction', '/places/roadside-attractions/', 'Bigfoot statues and UFO roadside attractions',
             'Bigfoot statues, UFO roadside attractions and monster photo stops',
             'Giant statues, sighting boards, landing pads and lonely pull-offs where the lights show up. Free, quick and very photogenic.',
             'Bigfoot statues, the Mothman statue, UFO landing pads, lake monster sculptures and mystery-light viewing spots, mapped.'),
        ):
            pl = [p for p in self.P if p['type'] == key]
            body = f'''
<section class="band band-dark pl-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/places/')}">Places</a> / {TYPES[key][1]}</p>
  <h1>{h1}</h1>
  <p class="lede">{lede} {len(pl)} so far.</p>
  {self.map_block(f'data-type="{key}"')}
</div></section>
<div class="band band-mist pl-list"><div class="wrap">{self.grouped_lists(pl)}</div></div>
{self.cta()}'''
            c.write(path, c.page(path, title, body, desc, body_class='places', head_extra=self.map_head))

    def regions(self):
        c, esc = self.c, self.c.esc
        all_regions = sorted(self.regions_map, key=lambda k: self.region_name(self.regions_map[k][0]))
        for k, pl in self.regions_map.items():
            nm = self.region_name(pl[0])
            what = self.creature_title(pl)
            h1 = f'{what} attractions in {nm}'
            sections = ''
            for t, (one, many, ic) in TYPES.items():
                sub = [p for p in pl if p['type'] == t]
                if sub:
                    sections += (f'<h2 class="pl-type-h"><span class="pl-chip-ico t-{t}">{c.icon(ic)}</span>{many}</h2>'
                                 f'<div class="pl-grid">{"".join(self.card(p) for p in sub)}</div>')
            crit = sorted({s for p in pl for s in p['creatures']}, key=lambda s: c.by_slug[s]['name'])
            crit_html = (f'<h2>Creatures you can chase here</h2><div class="crit-grid">{"".join(c.creature_card(c.by_slug[s]) for s in crit)}</div>'
                         if crit else '')
            same = [r for r in all_regions if r != k and self.regions_map[r][0]['country'] == pl[0]['country']] or \
                   [r for r in all_regions if r != k]
            others = ''.join(f'<li><a href="{self.u("/places/" + r + "/")}">{esc(self.region_name(self.regions_map[r][0]))}</a> '
                             f'<span class="muted">{len(self.regions_map[r])}</span></li>' for r in same)
            parts = defaultdict(int)
            for p in pl:
                parts[p['type']] += 1
            mix = ', '.join(f'{v} {TYPES[t][1].lower() if v > 1 else TYPES[t][0].lower()}' for t, v in parts.items())
            names = ', '.join(p['name'] for p in pl[:4])
            body = f'''
<section class="band band-dark pl-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/places/')}">Places</a> / {esc(nm)}</p>
  <h1>{esc(h1)}</h1>
  <p class="lede">{len(pl)} place{'s' if len(pl) != 1 else ''} to visit in {esc(nm)}: {esc(mix)}. Check opening times and dates with the official site before you set off.</p>
  {self.map_block(f'data-region="{k}"')}
</div></section>
<div class="band band-mist"><div class="wrap">
  {sections}
  {crit_html}
  <h2>More places</h2>
  <ul class="cols">{others}</ul>
  <p><a class="btn" href="{self.u('/places/')}">All places on the map</a></p>
</div></div>'''
            c.write(f'/places/{k}/', c.page(f'/places/{k}/', f'{h1}: museums, festivals and roadside stops', body,
                                            f'{h1}: {names}{" and more" if len(pl) > 4 else ""}. Addresses, dates, prices and a map.',
                                            body_class='places', head_extra=self.map_head))

    def nearest(self, p, n=4):
        if p['lat'] is None:
            return []
        def dist(q):
            la1, lo1, la2, lo2 = map(math.radians, (p['lat'], p['lon'], q['lat'], q['lon']))
            h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
            return 3958.8 * 2 * math.asin(math.sqrt(h))
        others = sorted(((dist(q), q) for q in self.P if q is not p and q['lat'] is not None), key=lambda x: x[0])
        return [(d, q) for d, q in others[:n] if d < 600]

    def details(self):
        c, esc = self.c, self.c.esc
        for p in self.P:
            one = TYPES[p['type']][0]
            rn = self.region_name(p) if p['rg'] else ''
            crumb = (f'<a href="{self.u("/places/")}">Places</a> / ' +
                     (f'<a href="{self.u("/places/" + p["rg"] + "/")}">{esc(rn)}</a> / ' if rn else '') + esc(one))
            facts = [('Type', one), ('Where', p.get('address') or self.where(p, short=False))]
            when_html = ''
            if p['type'] == 'festival' or p.get('month'):
                y, m, d, label, st = self.occurrence(p)
                facts.append(('When', p['when']))
                if p.get('start'):
                    facts.append(('Latest dates', self.date_label(p)))
                if st == 'set':
                    when_html = f'<p class="pl-when-big is-set">{c.icon("festival", "ico")} Next: {esc(label)}</p>'
                elif st == 'past':
                    when_html = f'<p class="pl-when-big">{c.icon("festival", "ico")} Just happened ({esc(label)}). Next year\'s dates are not out yet.</p>'
                else:
                    when_html = (f'<p class="pl-when-big">{c.icon("festival", "ico")} {esc(label)}. '
                                 f'{y} dates have not been announced yet.</p>')
            if p.get('price'):
                facts.append(('Price', p['price']))
            facts_html = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in facts)
            btns = ''
            if p.get('url'):
                btns += f'<a class="btn" href="{esc(p["url"])}" rel="noopener">Official site</a>'
            if p['lat'] is not None:
                q = f'{p["lat"]},{p["lon"]}' if not p.get('approx') else (p.get('address') or self.where(p, short=False))
                btns += (f'<a class="btn btn-ghost" href="https://www.google.com/maps/search/?api=1&amp;query={esc(q).replace(" ", "+")}" '
                         f'rel="noopener">Directions</a>')
            note = f'<p class="callout pl-note">{esc(p["note"])}</p>' if p.get('note') else ''
            crit = ''.join(c.creature_card(c.by_slug[s]) for s in p['creatures'])
            crit_html = f'<h2>The creature{"s" if len(p["creatures"]) > 1 else ""}</h2><div class="crit-grid pl-crit">{crit}</div>' if crit else ''
            near = self.nearest(p)
            near_html = ''
            if near:
                near_html = ('<h2>Nearby</h2><div class="pl-grid">' +
                             ''.join(self.card(q).replace('<span class="pl-kind">', f'<span class="pl-kind"><b>{"Same town" if d < 1.5 else f"{round(d):,} mi"}</b> · ', 1)
                                     for d, q in near) + '</div>')
            approx = ('<p class="small muted">Map pin is approximate: it marks the nearest town or the general area.</p>'
                      if p.get('approx') else '')
            mapb = self.map_block(f'data-focus="{p["slug"]}"') if p['lat'] is not None else ''
            body = f'''
<section class="band band-dark pl-head pl-detail-head t-{p['type']}"><div class="wrap pl-detail-in">
  {self.badge(p, 'xl')}
  <div>
    <p class="crumb">{crumb}</p>
    <h1>{esc(p['name'])}</h1>
    <p class="pl-where">{esc(self.where(p, short=False))}</p>
    <p class="lede">{esc(p['summary'])}</p>
    {when_html}
    <p class="pl-btns">{btns}</p>
  </div>
</div></section>
<div class="band band-mist"><div class="wrap creature-body">
  <article class="prose pl-prose">
    {note}
    {mapb}
    {approx}
    {crit_html}
    {near_html}
    <p class="small muted pl-src">Source: <a href="{esc(p['source'])}" rel="noopener">{esc(p['source'].split('/')[2].replace('www.', ''))}</a>. Hours, prices and dates change, so confirm with the organizer before you travel. Spotted something out of date? <a href="{self.u('/report/')}">Let us know</a>.</p>
  </article>
  <aside class="facts"><dl>{facts_html}</dl>
    <p class="more"><a href="{self.u('/places/' + p['rg'] + '/') if p['rg'] else self.u('/expeditions/')}">More in {esc(rn or 'expeditions')}</a></p>
  </aside>
</div></div>'''
            if p['type'] == 'festival':
                title = f'{p["name"]} {self.occurrence(p)[0]}: dates and details'
            else:
                title = f'{p["name"]}, {self.where(p)}: {one.lower()} guide'
            desc = p['summary'] + (f' {p["price"]}.' if p.get('price') and not p['price'].endswith('.') else '')
            c.write(f'/places/{p["slug"]}/', c.page(f'/places/{p["slug"]}/', title, body, desc[:300],
                                                    body_class='places', head_extra=self.map_head + self.jsonld(p)))

    def events(self):
        c, esc = self.c, self.c.esc
        t = self.today
        months = [((t.year * 12 + t.month - 1 + i) // 12, (t.month - 1 + i) % 12 + 1) for i in range(12)]
        slots = defaultdict(list)
        evs = [p for p in self.P if p['type'] == 'festival' or p.get('month')]
        for p in evs:
            y, m, d, label, st = self.occurrence(p)
            if (y, m) in months:
                slots[(y, m)].append((d or 99, p, label, st))
        nav = ''.join(f'<a href="#m-{y}-{m:02d}" class="pl-mnav{" is-now" if i == 0 else ""}{"" if slots[(y, m)] else " is-empty"}" data-ym="{y}-{m:02d}">'
                      f'{SHORT[m]}<span>{len(slots[(y, m)])}</span></a>' for i, (y, m) in enumerate(months))
        secs = ''
        for i, (y, m) in enumerate(months):
            rows = ''
            for d, p, label, st in sorted(slots[(y, m)], key=lambda x: (x[0], x[1]['name'])):
                status = {'set': 'Dates announced', 'past': 'Already happened', 'usual': f'{y} dates not announced yet'}[st]
                rows += (f'<li class="pl-ev is-{st}" data-type="{p["type"]}"><span class="pl-date{" is-tba" if d == 99 else ""}">'
                         f'<span class="pl-date-m">{SHORT[m]}</span><span class="pl-date-d">{d if d != 99 else "TBA"}</span></span>'
                         f'<div><h3><a href="{self.u("/places/" + p["slug"] + "/")}">{esc(p["name"])}</a></h3>'
                         f'<p class="pl-ev-meta">{esc(self.where(p))} · <strong>{esc(label)}</strong> · <span class="pl-ev-st">{esc(status)}</span></p>'
                         f'<p>{esc(p["summary"])}</p>'
                         + (f'<p class="pl-ev-links"><a href="{esc(p["url"])}" rel="noopener">Official site</a></p>' if p.get('url') else '')
                         + '</div></li>')
            if not rows:
                rows = '<li class="pl-ev-empty">Quiet month. A good time to visit a museum instead.</li>'
            now = ' is-now' if i == 0 else ''
            secs += (f'<section class="pl-month{now}" id="m-{y}-{m:02d}" data-ym="{y}-{m:02d}"><h2>{c.MONTHS[m]} {y}'
                     f'<span class="pl-now-tag">This month</span></h2><ol class="pl-evs">{rows}</ol></section>')
        nxt = self.upcoming(1)
        lead = (f' Next up: <a href="{self.u("/places/" + nxt[0]["slug"] + "/")}">{esc(nxt[0]["name"])}</a>, {esc(self.date_label(nxt[0]))}.'
                if nxt else '')
        y0, y1 = months[0][0], months[-1][0]
        span = f'{y0}' if y0 == y1 else f'{y0} and {y1}'
        body = f'''
<section class="band band-dark pl-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/places/')}">Places</a> / Events</p>
  <h1>Cryptid and UFO festivals, {span}</h1>
  <p class="lede">Mothman, Bigfoot, Rougarou and little green men all get their own parties. Here is the next 12 months, month by month.{lead}</p>
  <nav class="pl-mnavs" aria-label="Jump to month">{nav}</nav>
</div></section>
<div class="band band-mist"><div class="wrap">
  <p class="callout pl-note">Dates marked <strong>announced</strong> come from organizers or local news. Others show when the event usually happens; we add exact dates as soon as they are published.</p>
  {secs}
  <p><a class="btn" href="{self.u('/places/')}">See every place on the map</a></p>
</div></div>
<script src="{self.u('/static/places.js')}" defer></script>'''
        c.write('/events/', c.page('/events/', f'Cryptid festivals {span}: Bigfoot, Mothman and UFO event calendar', body,
                                   f'Bigfoot festivals, the Mothman Festival, Rougarou Fest, Roswell and other UFO festivals: a month-by-month calendar for {span} with dates and links.',
                                   body_class='places', head_extra=self.head))

    def expeditions(self):
        c, esc = self.c, self.c.esc
        ex = [p for p in self.P if p['type'] == 'expedition']
        cards = ''.join(self.card(p) for p in ex)
        body = f'''
<section class="band band-dark pl-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/places/')}">Places</a> / Expeditions</p>
  <h1>Bigfoot expeditions, UFO tours and night hikes</h1>
  <p class="lede">Want to go looking yourself? These are guided Bigfoot hunts, skywatch tours and monster cruises with real operators and published prices.</p>
  {self.map_block('data-type="expedition"')}
</div></section>
<div class="band band-mist"><div class="wrap">
  <div class="pl-grid">{cards}</div>
  <h2>Before you book</h2>
  <ul class="signs">
    <li>Prices here are what the operator or a booking site listed when we checked. Confirm before you pay.</li>
    <li>Nobody can promise a sighting. Good guides say so up front.</li>
    <li>Bring a headlamp with a red mode, layers and tick spray. Stay on public land unless the guide has permission.</li>
  </ul>
  <div class="pl-listyours">
    {c.icon('expedition', 'ico')}
    <div>
      <h2>List your expedition</h2>
      <p>Run Bigfoot expeditions, UFO skywatches, cryptid tours or monster cruises? Paid featured listings are coming soon, with your own page, photos and a pin on the map. Basic listings stay free for operators we can verify.</p>
      <p class="small muted">We're not taking sign-ups yet. Check back here soon.</p>
    </div>
  </div>
</div></div>
{self.cta()}<div class="band band-mist"><div class="wrap"><p class="g-gearlink">Heading out? See <a href="{c.url('/gear/')}">field gear for investigators</a>: trail cameras, thermal, binoculars and safety kit.</p></div></div>'''
        c.write('/expeditions/', c.page('/expeditions/', 'Bigfoot expeditions, UFO tours and cryptid night hikes', body,
                                        'Guided Bigfoot expeditions, Area 51 and Sedona UFO tours, Loch Ness sonar cruises and Bigfoot night hikes, with prices.',
                                        body_class='places', head_extra=self.map_head))

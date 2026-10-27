"""Famous UFO cases with exact dates, worldwide: a hub (/ufo/cases/) and one page per case, from data/famous_cases.json
(written by collector/famous_cases_src.py). Pages share the close-encounter layout (encounters.py's E class)."""
import importlib.util, json, os

# Short witness counts for the case-file header, read from each case's "witnesses" text (hand-checked, 2026-10-26).
WITNESSES = {
    'nuremberg-1561': 'Many', 'basel-1566': 'Many', 'angelholm-1946': '1', 'kenneth-arnold-1947': '1', 'roswell-1947': 'A handful',
    'mantell-1948': 'Many', 'mcminnville-1950': '3', 'lubbock-lights-1951': 'Many', 'trindade-1958': 'A ship\'s crew',
    'levelland-1957': '12+ drivers', 'shag-harbour-1967': '11+', 'berwyn-1974': 'Many', 'broad-haven-1977': '14 or 15',
    'petrozavodsk-1977': 'Thousands', 'valentich-1978': '1', 'clarenville-1978': '12', 'kaikoura-1978': 'Pilots, a TV crew',
    'dechmont-woods-1979': '1', 'cash-landrum-1980': '3', 'trans-en-provence-1981': '1', 'jal-1628-1986': '3',
    'knowles-family-1988': '4', 'belgian-wave-1989': '100+ the first night', 'calvine-1990': '2', 'phoenix-lights-1997': 'Thousands',
    'ohare-2006': 'About a dozen', 'alderney-2007': 'Several', 'stephenville-2008': 'Dozens', 'zacatecas-bonilla-1883': '1',
    'oloron-angel-hair-1952': 'Several', 'florence-stadium-1954': 'About 10,000', 'lakenheath-bentwaters-1956': 'Many',
    'manises-1979': 'A full flight', 'campeche-infrared-2004': 'A plane crew',
}

# "What do you think it was?" poll. Where our write-up leans one way, LEAN says which; cases without one are still open.
POLL = [('made', 'Aircraft, rocket or balloon'), ('natural', 'Something natural'), ('hoax', 'A hoax'), ('unknown', 'Truly unknown')]
LEAN = {
    'nuremberg-1561': 'natural', 'basel-1566': 'natural', 'roswell-1947': 'made', 'mantell-1948': 'made',
    'lubbock-lights-1951': 'natural', 'levelland-1957': 'natural', 'berwyn-1974': 'natural', 'petrozavodsk-1977': 'made',
    'kaikoura-1978': 'natural', 'jal-1628-1986': 'natural', 'phoenix-lights-1997': 'made', 'ohare-2006': 'natural',
    'stephenville-2008': 'made', 'zacatecas-bonilla-1883': 'natural', 'oloron-angel-hair-1952': 'natural', 'campeche-infrared-2004': 'made',
}


def build(ctx):
    path = os.path.join(ctx.ROOT, 'data', 'famous_cases.json')
    if not os.path.exists(path):
        return
    spec = importlib.util.spec_from_file_location('enc_sec', os.path.join(ctx.ROOT, 'site', 'sections', 'encounters.py'))
    enc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(enc)
    cases = json.load(open(path, encoding='utf-8'))
    for x in cases:
        x['creatures'] = [s for s in x.get('creatures', []) if s in ctx.by_slug]
    cases.sort(key=lambda x: (x['date'], x['slug']))

    class Cases(enc.E):
        BASE, GEO, LABEL = '/ufo/cases/', 'ufo-cases.geojson', 'Famous UFO cases'

        def __init__(self, ctx, cases):
            super().__init__(ctx, cases)
            self.head += (f'<link rel="stylesheet" href="{self.u("/static/ufo_cases.css")}">'
                          f'<script src="{self.u("/static/ufo_cases.js")}" defer></script>')

        def era(self, x):
            return 'Before 1900' if x['year'] < 1900 else f'The {x["year"] // 10 * 10}s'

        def shapes(self, x):
            return [s for s in x['creatures'] if ctx.by_slug[s]['cat'] == 'ufo']

        def card(self, x):
            return super().card(x).replace('<article class="ce-card"', f'<article class="ce-card" data-dec="{ctx.slugify(self.era(x))}" '
                                           f'data-k="{" ".join(self.shapes(x))}" data-slug="{x["slug"]}"', 1)

        def case_top(self, x):
            e = self.e
            n = self.cases.index(x) + 1
            wit = WITNESSES.get(x['slug'])
            cells = [('Date', enc.dateline(x['date'])), ('Place', x['place']), ('Witnesses', wit), ('Status', enc.STATUS[x['status']][0])]
            cells = ''.join(f'<div><dt>{k}</dt><dd>{e(v)}</dd></div>' for k, v in cells if v)
            return (f'<div class="band uc-fileband"><div class="wrap"><div class="uc-file uc-s-{x["status"]}">'
                    f'<p class="uc-stamp" aria-label="Case file {n} of {len(self.cases)}"><span>Case file</span><b>No. {n:02d}</b><small>of {len(self.cases)}</small></p>'
                    f'<p class="uc-ref">EA-UFO-{e(x["date"].replace("-", ""))}</p><dl class="uc-cells">{cells}</dl>'
                    '<button type="button" class="uc-copy" hidden>Copy link to this case</button></div></div></div>')

        def case_more(self, x):
            lean = LEAN.get(x['slug'], 'unknown' if x['status'] == 'unexplained' else '')
            opts = ''.join(f'<button type="button" class="uc-opt" data-o="{k}" aria-pressed="false">{lab}</button>' for k, lab in POLL)
            return (f'<section class="uc-poll" data-slug="{x["slug"]}" data-lean="{lean}" data-status="{x["status"]}" hidden>'
                    '<h2>What do you think it was?</h2><p class="uc-q">Make your call, then see our take. Your pick stays on this device.</p>'
                    f'<div class="uc-opts" role="group" aria-label="What do you think it was?">{opts}</div>'
                    '<div class="uc-res" aria-live="polite"></div></section>')

        def hub(self):
            c, e = self.c, self.e
            n = len(self.cases)
            names = sorted({enc.COUNTRY.get(x['cc'], x['cc']) for x in self.cases})
            counts = {k: sum(1 for x in self.cases if x['status'] == k) for k in enc.STATUS}
            eras = []
            for x in self.cases:
                if self.era(x) not in eras:
                    eras.append(self.era(x))
            kinds = {}
            for x in self.cases:
                for k in self.shapes(x):
                    kinds[k] = kinds.get(k, 0) + 1

            def row(label, key, items):
                return (f'<div class="uc-row" role="group" aria-label="Filter by {label.lower()}"><span class="uc-lab">{label}</span>'
                        f'<button type="button" class="uc-chip" data-g="{key}" data-f="" aria-pressed="true">All</button>'
                        + ''.join(f'<button type="button" class="uc-chip" data-g="{key}" data-f="{v}" aria-pressed="false">{e(t)} <span>{c}</span></button>'
                                  for v, t, c in items) + '</div>')
            chips = ('<div class="uc-filters" hidden>'
                     + row('Decade', 'dec', [(ctx.slugify(r), r.replace('The ', ''), sum(1 for x in self.cases if self.era(x) == r)) for r in eras])
                     + row('Shape', 'k', [(k, ctx.by_slug[k]['name'], c) for k, c in sorted(kinds.items(), key=lambda kv: -kv[1])])
                     + row('Verdict', 's', [(k, v[0], counts[k]) for k, v in enc.STATUS.items() if counts[k]])
                     + '<button type="button" class="uc-clear" hidden>Clear filters</button></div>')
            by_era = {}
            for x in self.cases:
                y = x['year']
                by_era.setdefault(self.era(x), []).append(x)
            groups = ''.join(f'<section class="ce-dec" data-dec="{ctx.slugify(k)}"><h2>{k}</h2><div class="ce-grid">{"".join(self.card(x) for x in v)}</div></section>'
                             for k, v in by_era.items())
            body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/ufo/')}">UFOs</a> / Famous cases</p>
  <h1>Famous UFO cases around the world</h1>
  <p class="lede">{n} of the best-known sightings, each on the day it happened: from the sky battle over Nuremberg in 1561 to Shag Harbour, the Kaikōura lights, the Belgian triangles and the Phoenix Lights. {len(names)} countries: {e(', '.join(names))}.</p>
  {chips}
  <div class="map-frame ce-map"><div id="ce-map" class="map" data-geojson="{self.u('/data/' + self.GEO)}"></div></div>
</div></section>
<div class="band band-mist ce-list"><div class="wrap">
  <p class="ce-status" aria-live="polite"></p>
  {groups}
  <aside class="ce-note"><h2>How we write these up</h2><p>Each case says what witnesses reported, then what police, air forces and other investigators found and the explanations offered. "Explained" means most investigators accept an explanation; "disputed" means explanations exist but are still argued over. Cases where people said they met the occupants are in <a href="{self.u('/encounters/')}">close encounters</a>; military cases are in <a href="{self.u('/military/')}">military encounters</a>.</p></aside>
</div></div>'''
            c.write(self.BASE, c.page(self.BASE, 'Famous UFO cases around the world: Shag Harbour, Phoenix Lights, Kaikōura and more', body,
                                      f'{n} famous UFO sightings from {len(names)} countries, from Nuremberg 1561 to Stephenville 2008: '
                                      'what witnesses saw, what investigators found, and sources.', body_class='encounters', head_extra=self.head))

    Cases(ctx, cases).run()

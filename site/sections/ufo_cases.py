"""Famous UFO cases with exact dates, worldwide: a hub (/ufo/cases/) and one page per case, from data/famous_cases.json
(written by collector/famous_cases_src.py). Pages share the close-encounter layout (encounters.py's E class)."""
import importlib.util, json, os


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

        def hub(self):
            c, e = self.c, self.e
            n = len(self.cases)
            names = sorted({enc.COUNTRY.get(x['cc'], x['cc']) for x in self.cases})
            counts = {k: sum(1 for x in self.cases if x['status'] == k) for k in enc.STATUS}
            chips = (f'<button type="button" class="ce-chip" data-f="" aria-pressed="true">All <span>{n}</span></button>'
                     + ''.join(f'<button type="button" class="ce-chip" data-f="{k}" aria-pressed="false">{v[0]} <span>{counts[k]}</span></button>'
                               for k, v in enc.STATUS.items() if counts[k]))
            by_era = {}
            for x in self.cases:
                y = x['year']
                by_era.setdefault('Before 1900' if y < 1900 else f'The {y // 10 * 10}s', []).append(x)
            groups = ''.join(f'<section class="ce-dec"><h2>{k}</h2><div class="ce-grid">{"".join(self.card(x) for x in v)}</div></section>'
                             for k, v in by_era.items())
            body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/ufo/')}">UFOs</a> / Famous cases</p>
  <h1>Famous UFO cases around the world</h1>
  <p class="lede">{n} of the best-known sightings, each on the day it happened: from the sky battle over Nuremberg in 1561 to Shag Harbour, the Kaikōura lights, the Belgian triangles and the Phoenix Lights. {len(names)} countries: {e(', '.join(names))}.</p>
  <div class="ce-chips" role="group" aria-label="Filter cases">{chips}</div>
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

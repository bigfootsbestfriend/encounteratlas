"""Local legend card for region hubs: the signature creature of a state, province or country, with its poster art.

Used by a_regions.py (/us/<state>/, /canada/<province>/, /us/), canada.py (/canada/) and places.py (/places/<region>/).
Call legend_card(ctx, cc, name) where cc is the country code and name is the page's region name ('Ohio', 'United Kingdom').
Pass name=None for a whole-country hub.

How the legend is picked (deterministic, data only):
  1. data/local_legends.json, keyed by region name, wins when it names a known creature.
  2. Otherwise the creature with the most famous cases (data/famous_geo.json) located in the region,
     then the most other mentions there (places to visit, old newspaper reports, close encounters and famous UFO cases),
     then the creature index's "sightings on file" count (famous + close encounters + newspapers), then name.
     LIVING_TRADITIONS creatures are never auto-picked.
  3. No creature at all: the region's best-known case (a famous UFO case, close encounter or mystery).
Static HTML only, no JS. Styles in site/static/legend.css.
"""
import ast, json, os, re
from collections import Counter, defaultdict

CSS = '/static/legend.css'


def _living(root):
    """LIVING_TRADITIONS, read from site/build.py so there's still only one list to keep in sync with the Worker."""
    src = open(os.path.join(root, 'site', 'build.py'), encoding='utf-8').read()
    m = re.search(r'LIVING_TRADITIONS = (\{[^}]*\})', src)
    return ast.literal_eval(m.group(1)) if m else set()


class _Legends:
    def __init__(self, ctx):
        self.c = ctx
        root = ctx.ROOT

        def load(f, empty=None):
            p = os.path.join(root, 'data', f)
            return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else ([] if empty is None else empty)
        self.living = _living(root)
        self.over = {k: v for k, v in load('local_legends.json', {}).items() if not k.startswith('_')}
        if not getattr(ctx, 'areas', None):
            import sys
            sys.path.insert(0, os.path.join(root, 'collector'))
            from geo import Areas
            ctx.areas = Areas()
        A = ctx.areas
        names = load('admin1_us_ca.json', {})
        self.key_of = {(k[:2], v): k for k, v in names.items()}  # ('US', 'Ohio') -> 'US.36'

        def keys(lat, lon):
            if lat in (None, ''):
                return []
            cc, a1 = A.where(float(lat), float(lon))
            return [k for k in (cc, f'{cc}.{a1}' if cc and a1 else None) if k]
        self.fam = defaultdict(lambda: defaultdict(list))   # region key -> creature -> famous cases there
        self.other = defaultdict(Counter)                   # region key -> creature -> other mentions
        self.what = defaultdict(lambda: defaultdict(Counter))  # region key -> creature -> {'places': n, 'hist': n, ...}
        self.pl = defaultdict(list)                          # region key -> places there
        self.cases = defaultdict(list)                       # region key -> (path, name, year) cases with no creature on file
        for f in load('famous_geo.json'):
            if f['creature'] in ctx.by_slug:
                for k in keys(f.get('lat'), f.get('lon')):
                    self.fam[k][f['creature']].append(f)
        for p in load('places.json'):
            ks = [p['country']] + ([self.key_of[(p['country'], p['region'])]] if (p['country'], p.get('region')) in self.key_of else [])
            for k in ks:
                self.pl[k].append(p)
                for s in p['creatures']:
                    self._add(k, s, 'places')
        for h in load('historic.json'):
            if h.get('creature') and ('US', h.get('state')) in self.key_of:
                for k in ('US', self.key_of[('US', h['state'])]):
                    self._add(k, h['creature'], 'hist')
        for f, base, kind in (('famous_cases.json', '/ufo/cases/', 'ufo'), ('close_encounters.json', '/encounters/', 'ce'),
                              ('mysteries.json', '/mysteries/', 'my')):
            for x in load(f):
                ks = keys(x.get('lat'), x.get('lon'))
                for k in ks:
                    for s in x.get('creatures') or []:
                        self._add(k, s, kind)
                    self.cases[k].append((base + x['slug'] + '/', x['name'], str(x.get('year') or x.get('date') or '')[:4]))
        self.hist = defaultdict(list)  # region key -> old newspaper reports (US states), for the last-resort legend
        for h in sorted(load('historic.json'), key=lambda h: h.get('date') or ''):
            if ('US', h.get('state')) in self.key_of:
                self.hist[self.key_of[('US', h['state'])]].append(h)
        self.fam_total = Counter(f['creature'] for f in load('famous_geo.json'))
        hist_n = Counter(x.get('creature') for x in load('historic.json'))
        close_n = Counter(s for x in load('close_encounters.json') for s in x.get('creatures', []))
        self.fame = {c['slug']: len(c['famous']) + close_n[c['slug']] + hist_n[c['slug']] for c in ctx.creatures}  # the /creatures/ "most sightings" order

    def _add(self, k, s, kind):
        if s in self.c.by_slug:
            self.other[k][s] += 1
            self.what[k][s][kind] += 1

    def pick(self, key, name):
        """-> (creature slug or None, override dict or None)"""
        o = self.over.get(name)
        if o and o.get('creature') in self.c.by_slug:
            return o['creature'], o
        pool = (set(self.fam[key]) | set(self.other[key])) - self.living
        if not pool:
            return None, None
        def rank(s):  # most cases here, then most other mentions, then the most local (share of its cases that are here), then fame
            n = len(self.fam[key][s])
            return (n, self.other[key][s], n / self.fam_total[s] if n else 0, self.fame.get(s, 0), [-ord(ch) for ch in s])
        best = max(pool, key=rank)
        return best, None

    def why(self, key, name, s):
        """One plain line on why this creature is the local legend, or '' when the data doesn't say."""
        n = len(self.fam[key][s])
        where = _the(name)
        if n:
            rivals = [r for r, v in self.fam[key].items() if r != s and r not in self.living]
            top = max((len(self.fam[key][r]) for r in rivals), default=0)
            line = f'{n} famous case{"s" if n != 1 else ""} in {where}'
            if top < n:
                other = 'UFO type or creature' if self.c.by_slug[s]['cat'] == 'ufo' else 'creature'
                return line + (f', more than any other {other}' if rivals else '')
            tied = sorted((self.c.by_slug[r]['name'] for r in rivals if len(self.fam[key][r]) == n))
            if top == n and tied:
                return line + ', tied with ' + _join(tied[:2]) + (' and others' if len(tied) > 2 else '') + ' for the most'
            return line
        w = self.what[key][s]
        labels = (('places', 'place to visit', 'places to visit'), ('hist', 'old newspaper report', 'old newspaper reports'),
                  ('ce', 'close encounter', 'close encounters'), ('ufo', 'famous UFO case', 'famous UFO cases'), ('my', 'mystery', 'mysteries'))
        bits = [f'{w[k]} {one if w[k] == 1 else many}' for k, one, many in labels if w.get(k)]
        return (_join(bits) + f' in {where}') if bits else ''

    def card(self, cc, name, places_link=True):
        c, E, U = self.c, self.c.esc, self.c.url
        key = cc if name is None or cc not in ('US', 'CA') else self.key_of.get((cc, name))
        if not key:
            return ''
        label = name or {'US': 'United States', 'CA': 'Canada'}.get(cc, cc)
        s, o = self.pick(key, label)
        o = o or {}
        if not s:
            return self.case_card(key, label, name)
        cr = c.by_slug[s]
        living = s in self.living
        why = self.why(key, label, s)
        blurb = o.get('blurb', '')
        art = _poster(c, cr)
        cases = sorted(self.fam[key][s], key=lambda f: f['year'] if isinstance(f['year'], int) else 9999)
        case_html = ''.join(f'<li><span class="lg-yr">{E(str(f["year"]))}</span>{E(f["name"])}</li>' for f in cases[:3])
        spots = [p for p in self.pl[key] if s in p['creatures']]
        extra = [p for sl in o.get('places', []) for p in self.pl[key] if p['slug'] == sl and p not in spots]
        spots = extra + spots
        links = [f'<a class="lg-btn" href="{U("/creatures/" + s + "/")}">Full {E(cr["name"])} profile</a>']
        if o.get('case'):
            links.append(f'<a class="lg-chip" href="{U(o["case"][0])}">{E(o["case"][1])}</a>')
        links += [f'<a class="lg-chip lg-place" href="{U("/places/" + p["slug"] + "/")}">{E(p["name"])}</a>' for p in spots[:3]]
        if len(spots) > 3 and name and places_link:
            links.append(f'<a class="lg-chip" href="{U("/places/" + c.slugify(name) + "/")}">All {len(spots)} places</a>')
        note = ('<p class="lg-note">This comes from a living tradition, so we share it as information only, '
                'out of respect for the people whose story it is.</p>' if living else '')
        return (f'<section class="lg-card cat-{cr["cat"]}" aria-labelledby="lg-{s}">'
                f'<div class="lg-art">{art}</div>'
                f'<div class="lg-txt"><p class="lg-eyebrow">Local legend of {E(_the(label))}</p>'
                f'<h2 id="lg-{s}">{E(cr["name"])}</h2>'
                + (f'<p class="lg-why">{E(why)}</p>' if why else '')
                + f'<p class="lg-sum">{E(blurb or cr["summary"].rstrip(".") + ".")}</p>'
                + (f'<ul class="lg-cases" aria-label="Famous cases here">{case_html}</ul>' if case_html else '')
                + note
                + f'<p class="lg-links">{"".join(links)}</p></div></section>')

    def case_card(self, key, label, name):
        """No creature on file here: the region's first famous case, else its oldest newspaper report."""
        E, U = self.c.esc, self.c.url
        if self.cases[key]:
            path, nm, yr = self.cases[key][0]
            why, go, ico = f'The best-known case on file in {_the(label)}' + (f', from {yr}' if yr else ''), 'Read the case', 'saucer'
            text = ''
        elif self.hist[key]:
            h = self.hist[key][0]
            nm, yr, ico = h['title'], (h.get('date') or '')[:4], 'folder'
            page = f'/history/{self.c.slugify(name)}/' if len(self.hist[key]) >= 5 else '/history/'  # historic.py makes a state page from 5 reports
            path, go = f'{page}#h-{h["id"]}', 'Read the old report'
            why = f'The oldest strange report we have from {_the(label)} papers, from {yr}'
            text = h.get('summary', '')
        else:
            return ''
        return (f'<section class="lg-card lg-case cat-other"><div class="lg-art lg-icon">{self.c.icon(ico)}</div>'
                f'<div class="lg-txt"><p class="lg-eyebrow">Local legend of {E(_the(label))}</p><h2>{E(nm)}</h2>'
                f'<p class="lg-why">{E(why)}</p>' + (f'<p class="lg-sum">{E(text)}</p>' if text else '')
                + f'<p class="lg-links"><a class="lg-btn" href="{U(path)}">{go}</a></p></div></section>')


def _join(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]


def _the(name):
    return ('the ' if name in ('United States', 'United Kingdom', 'Isle of Man', 'Netherlands', 'Philippines', 'Czech Republic') else '') + name


def _poster(ctx, cr):
    """The creature-page poster from build.py when it's reachable, else the big badge."""
    import sys
    poster = getattr(sys.modules.get('__main__'), 'poster', None)
    if poster and cr.get('art'):
        return poster(cr)
    return ctx.badge(cr, 'xl')


def head(ctx):
    return f'<link rel="stylesheet" href="{ctx.url(CSS)}">'


def legend_card(ctx, cc, name=None, places_link=True):
    if not getattr(ctx, 'legends', None):
        ctx.legends = _Legends(ctx)
    return ctx.legends.card(cc, name, places_link)

"""Interactive tools: /tools/ hub, /tools/what-did-i-see/ (identifier) and /tools/size-comparison/.

Data: data/identify.json (question/answer rules + everyday explanations) and data/sizes.json (settled sizes
with a basis note, plus creatures left out of the size tool and why). creatures.json is read at build time, so
new creatures are scored automatically; any creature missing from sizes.json has its 'size' text parsed here.

Re-seed sizes.json after creatures.json grows (keeps hand-edited entries):
    python3 site/sections/tools.py --seed-sizes
"""
import json, math, os, re, sys

CAT_ICON = {'hominid': 'hominid', 'canid': 'dogman', 'winged': 'winged', 'aquatic': 'lake', 'entity': 'entity', 'fae': 'fairy',
            'other': 'worm', 'ufo': 'saucer'}
DIM_WORD = {'height': 'tall', 'length': 'long', 'wingspan': 'wingspan', 'shoulder': 'at the shoulder', 'across': 'across'}
DEFAULT_CMP = ['bigfoot', 'dogman', 'mothman']

# ---------------------------------------------------------------- size parsing
UNIT = {'ft': 1, 'feet': 1, 'foot': 1, 'in': 1 / 12, 'inch': 1 / 12, 'inches': 1 / 12, 'm': 3.28084, 'cm': 0.0328084}
SIZE_WORDS = [  # word in the size text -> (dimension, lo ft, hi ft)
    ('elephant', 'height', 9, 13), ('horse', 'shoulder', 4.5, 5.5), ('donkey', 'shoulder', 3.5, 4.5),
    ('calf', 'shoulder', 3, 4), ('large dog', 'shoulder', 2.5, 3), ('small dog', 'shoulder', 1, 1.5),
    ('wolf', 'shoulder', 2.5, 3), ('panther', 'length', 6, 8), ('puma', 'length', 6, 8), ('bear', 'shoulder', 3, 3.5),
    ('teen', 'height', 5, 5.6), ('child', 'height', 3, 4.5), ('human', 'height', 5.5, 6.5), ('person', 'height', 5.5, 6.5),
    ('snake', 'length', 3, 6),
]
LEFT_OUT_RULES = [  # regex on size text -> reason
    (r'not applicable', 'An event or experience, not a creature with a body to measure.'),
    (r'acres', 'A place, not a creature.'),
    (r'hundreds|\bmile\b', 'Reports range from tens of feet to hundreds or more, so there is no single size to draw.'),
    (r'point of light|basketball', 'Seen as lights, with no solid body to measure.'),
    (r'^varies', 'Accounts disagree too much to settle on a size.'),
]
NUM = r'(\d+(?:\.\d+)?)'
U = r'(ft|feet|foot|inches|inch|in|cm|m)\b'


def _dim_after(t, end, cat):
    tail = t[end:end + 24]
    for w, d in (('wingspan', 'wingspan'), ('long', 'length'), ('shoulder', 'shoulder'), ('across', 'across'),
                 ('tall', 'height'), ('standing', 'height'), ('upright', 'height')):
        if w in tail:
            return d
    if 'wingspan' in t[:end]:
        return 'wingspan'
    return 'length' if cat in ('aquatic', 'other', 'ufo') else 'height'


def parse_size(text, cat):
    """Return (entry, None) or (None, reason). entry: dim, lo, hi (ft)."""
    t = (text or '').lower().strip()
    for rx, why in LEFT_OUT_RULES:
        if re.search(rx, t):
            return None, why
    nums = []
    for m in re.finditer(rf'(?:(about|around|over|up to|nearly)\s+)?{NUM}\s*(?:{U})?\s*(?:to|-|–)\s*{NUM}\s*{U}', t):
        u = UNIT[m.group(5)]
        u1 = UNIT[m.group(3)] if m.group(3) else u
        nums.append((m.start(), float(m.group(2)) * u1, float(m.group(4)) * u, _dim_after(t, m.end(), cat), m.group(1)))
    taken = [(a[0], 0) for a in nums]
    for m in re.finditer(rf'(?:(about|around|over|up to|nearly)\s+)?{NUM}\s*{U}(?:\s*(\d+)\s*in\b)?', t):
        if any(abs(m.start() - s) < 14 for s, _ in taken) or any(m.start() > n[0] and m.start() < n[0] + 20 for n in nums):
            continue
        v = float(m.group(2)) * UNIT[m.group(3)] + (float(m.group(4)) / 12 if m.group(4) else 0)
        q = m.group(1)
        lo, hi = (v, v * 1.2) if q == 'over' else (v * 0.5, v) if q == 'up to' else (v, v)
        nums.append((m.start(), lo, hi, _dim_after(t, m.end(), cat), q))
    nums.sort()
    words = []
    for w, d, lo, hi in SIZE_WORDS:
        i = t.find(w)
        if i >= 0:
            words.append((i, d, lo, hi, w))
    words.sort()
    if nums:
        p, lo, hi, dim, q = nums[0]
        if words and words[0][0] < p and ' to ' in t[words[0][0]:p + 1]:
            lo = words[0][2]
            dim = words[0][1] if dim not in ('height',) else dim
        e = {'dim': dim, 'lo': lo, 'hi': hi}
    elif words:
        e = {'dim': words[0][1], 'lo': min(w[2] for w in words), 'hi': max(w[3] for w in words), 'word': words[0][4]}
    else:
        return None, 'No size is given that we could draw with any confidence.'
    if 'or taller' in t:
        e['hi'] = e['hi'] * 1.25
    if 'plus tail' in t and e['dim'] == 'length':
        e['hi'] = e['hi'] * 1.6
    if cat == 'ufo' and e['dim'] != 'length':
        return None, 'Seen as lights or craft of no agreed size.'
    if e['hi'] < e['lo']:
        e['lo'], e['hi'] = e['hi'], e['lo']
    e['lo'], e['hi'] = round(e['lo'], 1), round(e['hi'], 1)
    e['draw'] = round((e['lo'] + e['hi']) / 2, 1)
    return e, None


def art_box(path):
    """Bounding box [x, y, w, h] of a traced silhouette, from its absolute path coordinates (control points included, close enough)."""
    d = ' '.join(re.findall(r' d="([^"]+)"', open(path).read()))
    nums = [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', d)]
    xs, ys = nums[0::2], nums[1::2]
    return [round(min(xs), 1), round(min(ys), 1), round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)]


def fmt_ft(v):
    if v < 3 and abs(v * 12 - round(v * 12)) < .01 and v != int(v):
        return f'{v:g} ft'
    return f'{round(v, 1):g} ft'


def size_text(e):
    lo, hi = e['lo'], e['hi']
    r = f'{lo:g} ft' if lo == hi else f'{lo:g} to {hi:g} ft'
    return f'{r} {DIM_WORD[e["dim"]]}'


def metres(e):
    lo, hi = e['lo'] / 3.28084, e['hi'] / 3.28084
    f = (lambda v: f'{v:.1f}') if hi < 10 else (lambda v: f'{v:.0f}')
    return f'{f(lo)} m' if e['lo'] == e['hi'] else f'{f(lo)} to {f(hi)} m'


def auto_basis(c, e):
    s = c.get('size', '')
    r = size_text(e)
    if 'tall tale' in s:
        return f'From tall tales, which put it at {r}. Not a witness measurement.'
    if 'original story' in s:
        return f'{r[0].upper() + r[1:]} comes from the original newspaper story.'
    if e.get('word'):
        return f'Described as "{s}". We drew it at {r}, a typical {e["word"]}.'
    if 'estimated' in s:
        return f'Witness estimates put it at {r}.'
    return f'Witness reports usually say {r}.'


def settled_sizes(ROOT, creatures):
    """sizes.json entries, falling back to parsing creatures.json for anything not settled yet."""
    data = json.load(open(os.path.join(ROOT, 'data', 'sizes.json'), encoding='utf-8'))
    sizes, left = {}, {}
    for c in creatures:
        s = c['slug']
        if s in data.get('left_out', {}):
            left[s] = data['left_out'][s]
        elif s in data.get('sizes', {}):
            sizes[s] = data['sizes'][s]
        else:
            e, why = parse_size(c.get('size', ''), c['cat'])
            if e:
                e['basis'] = auto_basis(c, e)
                e['auto'] = True
                sizes[s] = e
            else:
                left[s] = why
    return data, sizes, left


# ---------------------------------------------------------------- identifier scoring
def _has(word, text):
    return re.search(r'\b' + re.escape(word) + r'(?:s|es|ed|ing)?\b', text) is not None


def creature_fields(c):
    return {'habitat': (c.get('habitat') or '').lower(), 'summary': (c.get('summary') or '').lower(),
            'signs': ' | '.join(c.get('signs') or []).lower(), 'body': ' '.join(c.get('body') or []).lower(),
            'size': (c.get('size') or '').lower(), 'name': (c['name'] + ' ' + ' '.join(c.get('aliases') or [])).lower()}


def region_buckets(c, rq):
    if c['slug'] in rq.get('overrides', {}):
        return set(rq['overrides'][c['slug']]), False
    text = ' ' + (c.get('region') or '').lower() + ' '
    world = 'worldwide' in text
    pairs = sorted(((p, a['id']) for a in rq['answers'] for p in a['places']), key=lambda x: -len(x[0]))
    got = set()
    for p, b in pairs:
        rx = r'\b' + re.escape(p) + r'\b'
        if re.search(rx, text):
            got.add(b)
            text = re.sub(rx, ' ', text)
    got.discard('sea') if not world and got - {'sea'} and 'ocean' not in text else None
    if not got:
        for cc in c.get('cc') or []:
            got |= set(rq['cc_fallback'].get(cc, []))
    return got, world


def score_matrix(spec, creatures, sizes):
    fw, cap = spec['field_weights'], spec['word_cap']
    M = {}
    for q in spec['questions']:
        qw = q['weight']
        for a in q['answers']:
            row = {}
            for c in creatures:
                f = creature_fields(c)
                v = a.get('cats', {}).get(c['cat'], 0)
                if a.get('words'):
                    wv = sum(w * min(2, sum(1 for word in a['words'] if _has(word, f[k]))) for k, w in fw.items())
                    v += min(cap, wv)
                if q['id'] == 'size':
                    e = sizes.get(c['slug'])
                    if 'ft' in a and e:
                        lo, hi = e['lo'], e['hi']
                        if e['dim'] == 'shoulder':
                            lo, hi = lo * 1.5, hi * 1.5
                        lo, hi = lo * 0.9, hi * 1.1
                        a0, a1 = a['ft']
                        ov = max(0, min(a1, hi) - max(a0, lo))
                        v += 3 * min(1, ov / max(.5, min(hi - lo, a1 - a0)))
                    elif a['id'] == 'unknown' and not e:
                        v += 2
                if q['id'] == 'region':
                    b, world = region_buckets(c, q)
                    if world:
                        v += 3 if a['id'] == 'sea' else 3 * q.get('worldwide_score', .5)
                    if a['id'] in b:
                        v += 3 / math.sqrt(len(b))
                v += a.get('slugs', {}).get(c['slug'], 0)
                if v > 0:
                    row[c['slug']] = round(v * qw, 2)
            M[a['id']] = row
    return M


def ensure_reachable(spec, creatures, M):
    """Every creature must be able to land in the top 3. Search each creature's best answer set; if it still
    can't make the top 3, nudge it on its own region answer and try again. Returns the nudges applied."""
    qs = [[a['id'] for a in q['answers']] for q in spec['questions']]
    slugs = [c['slug'] for c in creatures]
    nudges = {}

    def rank_of(s, pick):
        tot = {x: sum(M[a].get(x, 0) for a in pick) for x in slugs}
        order = sorted(slugs, key=lambda x: (-tot[x], x != s))
        return order.index(s), tot

    def best_pick(s):
        pick = [max(ans, key=lambda a: M[a].get(s, 0)) for ans in qs]
        for _ in range(3):
            for i, ans in enumerate(qs):
                best = None
                for a in ans:
                    p = pick[:i] + [a] + pick[i + 1:]
                    r, tot = rank_of(s, p)
                    others = sorted((tot[x] for x in slugs if x != s), reverse=True)
                    key = (min(r, 3), -(tot[s] - others[2]))
                    if best is None or key < best[0]:
                        best = (key, a)
                pick[i] = best[1]
        return pick

    region_q = next(q for q in spec['questions'] if q['id'] == 'region')
    for _ in range(10):
        changed = False
        for s in slugs:
            pick = best_pick(s)
            r, tot = rank_of(s, pick)
            if r < 3:
                continue
            others = sorted((tot[x] for x in slugs if x != s), reverse=True)
            need = round(others[2] - tot[s] + 0.3, 2)
            ra = max((a['id'] for a in region_q['answers']), key=lambda a: M[a].get(s, 0))
            M[ra][s] = round(M[ra].get(s, 0) + need, 2)
            nudges[s] = round(nudges.get(s, 0) + need, 2)
            changed = True
        if not changed:
            break
    bad = [s for s in slugs if rank_of(s, best_pick(s))[0] >= 3]
    return nudges, bad


# ---------------------------------------------------------------- page helpers
class Tools:
    def __init__(self, ctx):
        self.c = ctx
        self.creatures = ctx.creatures
        self.head = f'<link rel="stylesheet" href="{ctx.url("/static/tools.css")}">'

    def icon(self, name, cat='other', cls='ico'):
        if not os.path.exists(os.path.join(self.c.STATIC, 'icons', name + '.svg')):
            name = CAT_ICON.get(cat, 'hominid')
        return self.c.icon(name, cls)

    def icon_name(self, c):
        n = c.get('icon') or ''
        return n if os.path.exists(os.path.join(self.c.STATIC, 'icons', n + '.svg')) else CAT_ICON.get(c['cat'], 'hominid')

    @staticmethod
    def jsdata(obj, id_):
        s = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/')
        return f'<script type="application/json" id="{id_}">{s}</script>'

    # ------------------------------------------------------------ hub
    def hub(self):
        c = self.c
        body = f'''
<section class="band band-dark tool-head">
  <div class="wrap">
    <h1>Field tools</h1>
    <p class="lede">Two quick tools for the trail and the kitchen table. Work out what you might have seen, or line the creatures up against a person.</p>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <div class="tool-cards">
    <a class="tool-card tool-card-id" href="{c.url('/tools/what-did-i-see/')}">
      <span class="tool-art" aria-hidden="true">{self.icon('eyeshine')}</span>
      <span class="tool-txt"><span class="tool-kicker">7 questions, about a minute</span>
      <span class="tool-name">What did I see?</span>
      <span class="tool-sum">Tap through where you were, how big it was, how it moved and what you heard. See which reports sound most like yours, and the everyday things that fool people most.</span>
      <span class="tool-go">Start the questions</span></span>
    </a>
    <a class="tool-card tool-card-size" href="{c.url('/tools/size-comparison/')}">
      <span class="tool-art" aria-hidden="true"><span class="tool-ruler"></span>{self.icon('human', cls='ico tool-human')}{self.icon('bigfoot', 'hominid', 'ico tool-big')}</span>
      <span class="tool-txt"><span class="tool-kicker">Pick up to 3</span>
      <span class="tool-name">Size comparison</span>
      <span class="tool-sum">Stand Bigfoot, Mothman or a lake monster against a 6 ft person on a measuring wall, in feet and metres. Every size comes with where the number came from.</span>
      <span class="tool-go">Compare sizes</span></span>
    </a>
  </div>
</div></div>'''
        c.write('/tools/', c.page('/tools/', 'Field tools: identify a sighting and compare cryptid sizes', body,
                                  'Free tools: a quick "What did I see?" identifier for strange sightings, and a cryptid size comparison against a 6 ft person.',
                                  body_class='tools', head_extra=self.head))

    # ------------------------------------------------------------ identifier
    def size_art(self, scale):
        src = os.path.join(self.c.STATIC, 'icons', 'human.svg')
        hp = re.search(r'<svg[^>]*>(.*)</svg>', open(src).read(), re.S).group(1)
        bx, by, bw, bh = art_box(src)
        k = 33.5 / bh  # person stands 33.5 units tall, feet on the ground line, centred at x 14.5
        tf = f'translate({14.5 - (bx + bw / 2) * k:.2f} {60 - (by + bh) * k:.2f}) scale({k:.4f})'
        h = min(56, 33 * scale)
        w = min(32, 10 + 14 * scale)
        return (f'<svg class="ico" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
                f'<g fill="currentColor" opacity=".6" transform="{tf}">{hp}</g>'
                f'<rect x="{28 + (34 - w) / 2:.1f}" y="{60 - h:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{min(w, h) / 2.4:.1f}" '
                f'style="fill:var(--eye,#F2B33D)"/><path d="M2 61H62" stroke="currentColor" stroke-width="2.5"/></svg>')

    def identify(self):
        c, ROOT = self.c, self.c.ROOT
        spec = json.load(open(os.path.join(ROOT, 'data', 'identify.json'), encoding='utf-8'))
        kp = os.path.join(ROOT, 'data', 'creature_kinds.json')
        kinds = json.load(open(kp)) if os.path.exists(kp) else {}
        live = [x for x in self.creatures if kinds.get(x['slug']) != 'single']  # one-off exhibits and incidents can't be "seen" today
        _, sizes, _ = settled_sizes(ROOT, live)
        M = score_matrix(spec, live, sizes)
        nudges, bad = ensure_reachable(spec, live, M)
        if nudges:
            print(f'tools: nudged {len(nudges)} creatures so every one can reach the top 3: '
                  + ', '.join(f'{k}+{v}' for k, v in sorted(nudges.items())), file=sys.stderr)
        if bad:
            print('tools: WARNING still unreachable in the identifier: ' + ', '.join(bad), file=sys.stderr)
        n = len(spec['questions'])
        steps = ''
        for i, q in enumerate(spec['questions']):
            cards = ''
            for a in q['answers']:
                if 'scale' in a:
                    art = self.size_art(a['scale'])
                elif a.get('icon'):
                    art = self.icon(a['icon'])
                else:
                    art = self.icon('q-pin')
                eye = f' style="--eye:{a["eye"]}"' if a.get('eye') else ''
                cards += (f'<li><button type="button" class="ans" data-a="{a["id"]}" aria-pressed="false">'
                          f'<span class="ans-ico"{eye}>{art}</span><span class="ans-label">{c.esc(a["label"])}</span></button></li>')
            region = ' ans-grid-text' if q['id'] == 'region' else ''
            steps += f'''
    <li class="idq-step" data-q="{q['id']}" id="q-{q['id']}">
      <p class="idq-num">Question {i + 1} of {n}</p>
      <h2 class="idq-h" tabindex="-1">{c.esc(q['q'])}</h2>
      <p class="idq-help">{c.esc(q['help'])}</p>
      <ul class="ans-grid{region}" role="list">{cards}</ul>
      <p class="idq-skip-row"><button type="button" class="idq-skip js-only">Not sure, skip this one</button></p>
    </li>'''
        mix = ''
        for e in spec['everyday']:
            mix += (f'<article class="mix" id="mix-{e["id"]}" data-id="{e["id"]}"><span class="mix-ico" aria-hidden="true">{self.icon(e["icon"])}</span>'
                    f'<div><h3>{c.esc(e["name"])}</h3><p>{c.esc(e["tells"])}</p></div></article>')
        data = {
            'q': [{'id': q['id'], 'w': q['weight'], 'a': [[a['id'], a['label']] for a in q['answers']]} for q in spec['questions']],
            'M': M,
            'c': {x['slug']: [x['name'], ', '.join(x['aliases'][:2]), x['summary'], x['cat'], x.get('art') or 'icons/' + self.icon_name(x)] for x in live},
            'e': {e['id']: e['fits'] for e in spec['everyday']},
            'icons': c.url('/static/icons/'), 'base': c.url(''),
        }
        n_c = len(live)
        body = f'''
<section class="band band-dark tool-head">
  <div class="wrap">
    <p class="crumb"><a href="{c.url('/tools/')}">Tools</a> / What did I see?</p>
    <h1>What did I see?</h1>
    <p class="lede">Seven quick questions about your sighting. We'll show which of the {n_c} creatures and phenomena in our files sound most like it, and the everyday things people most often mistake for them.</p>
  </div>
</section>
<div class="band band-mist id-band"><div class="wrap">
  <div class="idq" id="idq">
    <div class="idq-bar js-only" hidden>
      <button type="button" class="idq-back" aria-label="Back to the previous question">Back</button>
      <div class="idq-prog" role="progressbar" aria-label="Progress" aria-valuemin="0" aria-valuemax="{n}" aria-valuenow="0"><span></span></div>
    </div>
    <noscript><p class="callout">These are the questions the tool asks. Turn on JavaScript to tap through them and get a match, or read the common mix-ups below.</p></noscript>
    <ol class="idq-steps">{steps}
    </ol>
    <div class="idq-result" id="idq-result" aria-live="polite" tabindex="-1"></div>
  </div>

  <section class="mixups" aria-labelledby="mix-h">
    <h2 id="mix-h">Common mix-ups</h2>
    <p class="lede-dark">Most strange sightings turn out to be something ordinary seen in poor light. These are the ones that fool people most, and how to tell.</p>
    <div class="mix-grid">{mix}</div>
  </section>

  <section class="prose id-how">
    <h2>How the matching works</h2>
    <p>Each answer adds points to creatures whose descriptions fit: where they are reported, how big witnesses say they are, how they move, what people hear and see. Region counts most, because many creatures belong to one lake, swamp or county. The result is a list of reports that sound like yours, not proof of anything. We don't claim any of these creatures are real, and we don't claim they're not.</p>
    <p>Browse the full <a href="{c.url('/creatures/')}">creature index</a>, or compare sizes with the <a href="{c.url('/tools/size-comparison/')}">size comparison</a>.</p>
  </section>
</div></div>
{self.jsdata(data, 'idq-data')}
<script src="{c.url('/static/identify.js')}" defer></script>'''
        c.write('/tools/what-did-i-see/', c.page('/tools/what-did-i-see/', 'What did I see? Cryptid and UFO sighting identifier', body,
                                                  'Answer seven quick questions about a strange sighting and see which cryptids or UFO types it sounds like, plus the everyday things people mistake for them.',
                                                  body_class='tools', head_extra=self.head))

    # ------------------------------------------------------------ size comparison
    def sizes(self):
        c, ROOT = self.c, self.c.ROOT
        data, sizes, left = settled_sizes(ROOT, self.creatures)
        boxes = data.get('icon_box', {})
        by = {x['slug']: x for x in self.creatures}
        auto = [s for s, e in sizes.items() if e.get('auto')]
        if auto:
            print(f'tools: {len(auto)} sizes parsed on the fly (run tools.py --seed-sizes to settle them): ' + ', '.join(auto), file=sys.stderr)
        items = {}
        icon_src = {}
        for s, e in sizes.items():
            x = by[s]
            ic = self.icon_name(x)
            if os.path.exists(os.path.join(c.STATIC, 'art', s + '.svg')):  # each creature stands on the wall as its own poster silhouette
                ic = 'art/' + s
                boxes.setdefault(ic, art_box(os.path.join(c.STATIC, 'art', s + '.svg')))
            fit = 'w' if e['dim'] in ('length', 'wingspan', 'across') else 'h'
            draw = e['draw'] * (1.2 if e['dim'] == 'shoulder' else 1)
            items[s] = {'n': x['name'], 'cat': x['cat'], 'i': ic, 'b': boxes.get(ic, [0, 0, 64, 64]), 'f': fit, 'd': draw,
                        'lo': e['lo'], 'hi': e['hi'], 't': size_text(e), 'dim': e['dim']}
            icon_src[ic] = None
        human = data.get('human', {'ft': 6})
        hp = os.path.join(c.STATIC, 'art', 'pic-human.svg')
        hi, hb = ('art/pic-human', art_box(hp)) if os.path.exists(hp) else ('human', boxes.get('human', [21, 2, 22, 61]))
        items['human'] = {'n': 'Person', 'cat': 'human', 'i': hi, 'b': hb, 'f': 'h',
                          'd': human['ft'], 'lo': human['ft'], 'hi': human['ft'], 't': f'{human["ft"]:g} ft tall', 'dim': 'height'}
        icon_src[hi] = None
        for ic in icon_src:
            svg = open(os.path.join(c.STATIC, ic + '.svg' if ic.startswith('art/') else os.path.join('icons', ic + '.svg')), encoding='utf-8').read()
            icon_src[ic] = re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', 'fill="currentColor"', re.sub(r'^\s*<svg[^>]*>|</svg>\s*$', '', svg))
        default = [s for s in DEFAULT_CMP if s in items]
        stage = self.render_wall(['human'] + default, items, icon_src, 1000, 520)
        legend = self.legend(['human'] + default, items)

        chips = ''
        for s in sorted(sizes, key=lambda s: by[s]['name'].lower()):
            x = by[s]
            chips += (f'<button type="button" class="pchip cat-{x["cat"]}" data-s="{s}" aria-pressed="{"true" if s in default else "false"}" '
                      f'data-names="{c.esc((x["name"] + " " + " ".join(x["aliases"])).lower())}">'
                      f'<span class="mask-ico" style="--m:url({c.url("/static/" + ("" if items[s]["i"].startswith("art/") else "icons/") + items[s]["i"] + ".svg")})"></span>{c.esc(x["name"])}</button>')
        rows = ''
        for s in sorted(sizes, key=lambda s: -sizes[s]['hi']):
            e, x = sizes[s], by[s]
            rows += (f'<tr><th scope="row" data-v="{c.esc(x["name"].lower())}"><a href="{c.url("/creatures/" + s + "/")}">{c.esc(x["name"])}</a></th>'
                     f'<td data-v="{e["dim"]}">{c.esc(DIM_WORD[e["dim"]].capitalize() if e["dim"] != "shoulder" else "Shoulder height")}</td>'
                     f'<td data-v="{e["hi"]}">{c.esc(size_text(e).rsplit(" ft", 1)[0])} ft</td><td data-v="{e["hi"]}">{metres(e)}</td>'
                     f'<td class="basis">{c.esc(e["basis"])}</td></tr>')
        lefts = ''.join(f'<li><a href="{c.url("/creatures/" + s + "/")}">{c.esc(by[s]["name"])}</a>: {c.esc(why)}</li>'
                        for s, why in sorted(left.items(), key=lambda kv: by[kv[0]]['name'].lower()))
        cdata = {'items': items, 'icons': icon_src, 'def': default, 'base': c.url('')}
        names = ', '.join(by[s]['name'] for s in default)
        body = f'''
<section class="band band-dark tool-head">
  <div class="wrap">
    <p class="crumb"><a href="{c.url('/tools/')}">Tools</a> / Size comparison</p>
    <h1>How big is it?</h1>
    <p class="lede">Stand up to three creatures against a 6 ft person on a measuring wall. Sizes are what witnesses and stories describe, with a note on where each number comes from.</p>
  </div>
</section>
<section class="band band-dark cmp-band" aria-label="Size comparison">
  <div class="wrap">
    <figure class="cmp-stage" id="cmp-stage">
      <div class="cmp-svg">{stage}</div>
      <div class="cmp-legend" id="cmp-legend">{legend}</div>
      <figcaption class="visually-hidden" id="cmp-cap" aria-live="polite">Comparing a 6 ft person with {c.esc(names)}.</figcaption>
    </figure>
    <div class="cmp-pick">
      <div class="cmp-pick-head">
        <h2>Pick up to 3</h2>
        <button type="button" class="btn btn-ghost btn-sm js-only" id="cmp-clear" hidden>Clear</button>
        <button type="button" class="btn btn-ghost btn-sm js-only" id="cmp-share" hidden>Share this comparison</button>
      </div>
      <div class="search-row"><label class="visually-hidden" for="cmp-q">Find a creature</label>
        <input id="cmp-q" type="search" placeholder="Find a creature: Yeti, Nessie, Dogman" autocomplete="off"></div>
      <div class="pchips" role="group" aria-label="Creatures to compare">{chips}</div>
      <p class="small muted">Picking a fourth swaps out the oldest pick. The link in your address bar always matches what's on the wall.</p>
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <h2>Every size we have</h2>
  <p class="lede-dark">Tap a column heading to sort. Heights are standing height; lake monsters and serpents are total length; fliers with only a wingspan are measured wing tip to wing tip.</p>
  <div class="tbl-wrap"><table class="size-tbl" id="size-tbl">
    <thead><tr>
      <th scope="col" aria-sort="none"><button type="button" data-k="0">Creature</button></th>
      <th scope="col" aria-sort="none"><button type="button" data-k="1">Measured</button></th>
      <th scope="col" aria-sort="descending"><button type="button" data-k="2" data-num="1">Feet</button></th>
      <th scope="col" aria-sort="none"><button type="button" data-k="3" data-num="1">Metres</button></th>
      <th scope="col">Where the number comes from</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  <h2>Left out of the picker</h2>
  <p>These are in the <a href="{c.url('/creatures/')}">creature index</a> but can't be drawn honestly on a measuring wall:</p>
  <ul class="left-out">{lefts}</ul>
  <p>Not sure what you saw? Try <a href="{c.url('/tools/what-did-i-see/')}">What did I see?</a></p>
</div></div>
{self.jsdata(cdata, 'cmp-data')}
<script src="{c.url('/static/compare.js')}" defer></script>'''
        c.write('/tools/size-comparison/', c.page('/tools/size-comparison/', 'Cryptid size comparison: Bigfoot, Dogman, Mothman and more next to a person', body,
                                                   'Compare the reported sizes of Bigfoot, Dogman, Mothman, lake monsters and more against a 6 ft person, in feet and metres.',
                                                   body_class='tools', head_extra=self.head))

    def legend(self, keys, items):
        c = self.c
        out = ''
        for k in keys:
            it = items[k]
            name = (f'<a href="{c.url("/creatures/" + k + "/")}">{c.esc(it["n"])}</a>' if k != 'human'
                    else 'Average person')
            out += f'<div class="lg cat-{it["cat"]}"><span class="lg-n">{name}</span><span class="lg-s">{c.esc(it["t"])}</span></div>'
        return out

    @staticmethod
    def render_wall(keys, items, icons, VW, VH):
        """Same layout as compare.js draw(): equal columns, one shared ft scale, ground at the bottom."""
        L, R, T, B = 46, 46, 30, 12
        n = len(keys)
        colW = (VW - L - R) / n
        fig = []
        for k in keys:
            it = items[k]
            bx, by_, bw, bh = it['b']
            s = it['d'] / (bh if it['f'] == 'h' else bw)
            fig.append((k, it, s, bw * s, bh * s))
        maxH = max(f[4] for f in fig)
        top = maxH * 1.15
        px = min((VH - T - B) / top, min(colW * 0.86 / f[3] for f in fig))
        VH = max(220, round(T + B + top * px))
        topFt = (VH - T - B) / px
        step = next((st for st in (1, 2, 5, 10, 20, 50, 100, 200) if topFt / st <= 9 and st * px >= 18), 500)
        mstep = next((st for st in (.5, 1, 2, 5, 10, 20, 50) if topFt / 3.28084 / st <= 7 and st * 3.28084 * px >= 18), 100)
        gy = VH - B
        o = [f'<svg class="wall" viewBox="0 0 {VW} {VH}" role="img" aria-labelledby="cmp-cap" preserveAspectRatio="xMidYMax meet">',
             f'<rect class="wall-bg" x="{L}" y="{T - 10}" width="{VW - L - R}" height="{gy - T + 10}"/>']
        i = 0
        while i * step <= topFt:
            y = gy - i * step * px
            if i % 2:
                o.append(f'<rect class="wall-band" x="{L}" y="{max(T - 10, y - step * px):.1f}" width="{VW - L - R}" height="{min(step * px, y - T + 10):.1f}"/>')
            o.append(f'<line class="ft-line" x1="{L}" x2="{VW - R}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text class="ft-lbl" x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{i * step:g} ft</text>')
            i += 1
        j = 1
        while j * mstep * 3.28084 <= topFt:
            y = gy - j * mstep * 3.28084 * px
            o.append(f'<line class="m-line" x1="{VW - R - 14}" x2="{VW - R}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text class="m-lbl" x="{VW - R + 6}" y="{y + 4:.1f}">{j * mstep:g} m</text>')
            j += 1
        for idx, (k, it, s, wft, hft) in enumerate(fig):
            bx, by_, bw, bh = it['b']
            kk = s * px
            cx = L + colW * (idx + .5)
            x0, y0 = cx - (bx + bw / 2) * kk, gy - (by_ + bh) * kk
            o.append(f'<g class="fig cat-{it["cat"]}" transform="translate({x0:.1f} {y0:.1f}) scale({kk:.4f})" fill="currentColor" '
                     f'stroke-linecap="round" stroke-linejoin="round">{icons[it["i"]]}</g>')
            w, h = wft * px, hft * px
            if it['f'] == 'h':
                lx = cx + w / 2 + 8
                ylo, yhi = gy - it['lo'] * (1.2 if it['dim'] == 'shoulder' else 1) * px, gy - it['hi'] * (1.2 if it['dim'] == 'shoulder' else 1) * px
                o.append(f'<rect class="dim-range" x="{lx - 3:.1f}" y="{yhi:.1f}" width="6" height="{max(2, ylo - yhi):.1f}"/>'
                         f'<line class="dim" x1="{lx:.1f}" x2="{lx:.1f}" y1="{gy:.1f}" y2="{gy - h:.1f}"/>'
                         f'<line class="dim" x1="{lx - 5:.1f}" x2="{lx + 5:.1f}" y1="{gy - h:.1f}" y2="{gy - h:.1f}"/>')
                lbl = f'{it["d"]:g} ft' if k == 'human' else f'{it["lo"]:g}–{it["hi"]:g} ft' if it['lo'] != it['hi'] else f'{it["lo"]:g} ft'
                o.append(f'<text class="dim-lbl" x="{cx:.1f}" y="{gy - h - 8:.1f}" text-anchor="middle">{lbl}</text>')
            else:
                y = gy - h - 8
                o.append(f'<line class="dim" x1="{cx - w / 2:.1f}" x2="{cx + w / 2:.1f}" y1="{y:.1f}" y2="{y:.1f}"/>'
                         f'<line class="dim" x1="{cx - w / 2:.1f}" x2="{cx - w / 2:.1f}" y1="{y - 5:.1f}" y2="{y + 5:.1f}"/>'
                         f'<line class="dim" x1="{cx + w / 2:.1f}" x2="{cx + w / 2:.1f}" y1="{y - 5:.1f}" y2="{y + 5:.1f}"/>'
                         f'<text class="dim-lbl" x="{cx:.1f}" y="{y - 8:.1f}" text-anchor="middle">{it["lo"]:g}{"–" + format(it["hi"], "g") if it["lo"] != it["hi"] else ""} ft</text>')
        o.append(f'<line class="ground" x1="{L - 4}" x2="{VW - R + 4}" y1="{gy}" y2="{gy}"/></svg>')
        return ''.join(o)


def build(ctx):
    t = Tools(ctx)
    t.hub()
    t.identify()
    t.sizes()


# ---------------------------------------------------------------- seed sizes.json
if __name__ == '__main__' and '--seed-sizes' in sys.argv:
    ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    creatures = json.load(open(os.path.join(ROOT, 'data', 'creatures.json'), encoding='utf-8'))
    p = os.path.join(ROOT, 'data', 'sizes.json')
    data = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    data.setdefault('about', 'Sizes drawn by the size comparison tool (site/sections/tools.py). lo/hi/draw are in feet; '
                    'dim is what was measured (height, length, wingspan, shoulder). basis says where the number comes from. '
                    'left_out lists creatures the tool skips, with the reason shown on the page. icon_box is each icon\'s painted '
                    'area in its 64-unit viewBox, so silhouettes stand on the ground line at the right scale.')
    data.setdefault('human', {'ft': 6, 'basis': 'A 6 ft adult, for scale.'})
    data.setdefault('sizes', {})
    data.setdefault('left_out', {})
    added = []
    for c in creatures:
        s = c['slug']
        if s in data['sizes'] or s in data['left_out']:
            continue
        e, why = parse_size(c.get('size', ''), c['cat'])
        if e:
            e['basis'] = auto_basis(c, e)
            e.pop('word', None)
            data['sizes'][s] = e
        else:
            data['left_out'][s] = why
        added.append(s)
    order = {c['slug']: i for i, c in enumerate(creatures)}
    data['sizes'] = dict(sorted(data['sizes'].items(), key=lambda kv: order.get(kv[0], 1e9)))
    data['left_out'] = dict(sorted(data['left_out'].items(), key=lambda kv: order.get(kv[0], 1e9)))
    box = data.pop('icon_box', {})
    data['icon_box'] = box
    with open(p, 'w', encoding='utf-8') as f:
        f.write('{\n' + ',\n'.join(
            f'  {json.dumps(k)}: ' + (json.dumps(v, ensure_ascii=False) if k in ('about', 'human') else
                                     '{\n' + ',\n'.join(f'    {json.dumps(a)}: {json.dumps(b, ensure_ascii=False)}' for a, b in v.items()) + '\n  }')
            for k, v in data.items()) + '\n}\n')
    print('added', len(added), added)

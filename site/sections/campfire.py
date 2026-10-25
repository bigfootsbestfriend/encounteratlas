"""/stories/campfire/: campfire mode, for reading witness stories out loud around a fire at night.

At load (plain HTML, indexable): a short intro by Mike, the start button, and a list of every story in the mix, each
linking to the page it lives on (/stories/<id>/ for witness stories, the creature page's #cases or #papers list for
the short ones from data/creature_stories.json).

static/campfire.js only acts when "Start campfire mode" is tapped: a full-screen night view (deep red on black, no
white or blue light anywhere), one story at a time in shuffled order, next/back, swipe, arrow keys, A-/A+, exit,
Screen Wake Lock and an optional read-it-to-me (speechSynthesis). The stories come from OUT/data/campfire.json,
written here, so the mode works offline once the service worker has a copy.

Creatures in build.py's LIVING_TRADITIONS are left out entirely (info-only, never entertainment).
"""
import json, os, re

WPM = 150  # reading out loud, slower than the 230 the story pages use for silent reading


def living_traditions(ctx):
    """build.py keeps the list inside a function, so read it from the source. Falls back to the list as of 2026-10-24."""
    lt = getattr(ctx, 'LIVING_TRADITIONS', None)
    if lt:
        return set(lt)
    try:
        src = open(os.path.join(ctx.ROOT, 'site', 'build.py'), encoding='utf-8').read()
        m = re.search(r'LIVING_TRADITIONS\s*=\s*\{([^}]*)\}', src)
        found = set(re.findall(r"'([a-z0-9-]+)'", m.group(1))) if m else set()
        if found:
            return found
    except OSError:
        pass
    return {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
            'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}


def load(ctx, name, default):
    p = os.path.join(ctx.ROOT, 'data', name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


def minutes(paras):
    return max(1, round(sum(len(p.split()) for p in paras) / WPM))


def build(ctx):
    e, u = ctx.esc, ctx.url
    skip = living_traditions(ctx)

    long_ones, short_ones = [], []
    for st in load(ctx, 'witness_stories.json', []):
        c = ctx.by_slug.get(st['creature'])
        if not c or st['creature'] in skip:
            continue
        long_ones.append({'k': 'w', 'id': st['id'], 't': st['title'], 'c': c['name'], 'p': st['place'], 'w': st['when'],
                          'b': st['body'], 'u': u('/stories/' + st['id'] + '/'),
                          'cr': f"From {st['teller']} on {st['source']}, {st['posted'][:4]}. Retold by Encounter Atlas."})
    for slug, items in load(ctx, 'creature_stories.json', {}).items():
        c = ctx.by_slug.get(slug)
        if not c or slug in skip:
            continue
        for i, st in enumerate(items):
            continue  # Mike 2026-10-25: one-line case notes aren't campfire stories, so witness stories only
            if not st.get('summary'):
                continue
            anchor = '#papers' if st.get('kind') == 'newspaper' else '#cases'
            src = f" Source: {st['source_title']}." if st.get('source_title') else ''
            short_ones.append({'k': 's', 'id': f'{slug}-{i}', 't': st['name'], 'c': c['name'], 'p': st['place'], 'w': str(st['year']),
                               'b': [st['summary']], 'u': u('/creatures/' + slug + '/') + anchor,
                               'cr': f"From our {c['name']} page.{src}"})
    if not long_ones and not short_ones:
        return

    # Compact JSON for the night view (the service worker can precache it, so it works with no signal).
    os.makedirs(os.path.join(ctx.OUT, 'data'), exist_ok=True)
    with open(os.path.join(ctx.OUT, 'data', 'campfire.json'), 'w', encoding='utf-8') as f:
        json.dump({'v': 1, 'stories': long_ones + short_ones}, f, ensure_ascii=False, separators=(',', ':'))

    long_ones.sort(key=lambda x: (x['c'], x['t']))
    short_ones.sort(key=lambda x: (x['c'], x['w'], x['t']))

    def li(x):
        mins = f' · {minutes(x["b"])} min out loud' if x['k'] == 'w' else ''
        return (f'<li><a href="{e(x["u"])}">{e(x["t"])}</a>'
                f'<span class="cf-li-meta">{e(x["c"])} · {e(x["p"])} · {e(x["w"])}{mins}</span></li>')

    n = len(long_ones) + len(short_ones)
    cfg = json.dumps({'data': u('/data/campfire.json')}, separators=(',', ':')).replace('</', '<\\/')
    body = f'''
<section class="band band-dark cf-hero"><div class="wrap narrow">
  <p class="crumb"><a href="{u('/stories/')}">Witness stories</a> / Campfire mode</p>
  <h1>Campfire stories</h1>
  <p class="lede">Real witness stories to read out loud around the fire, one at a time, in big red type on a black screen so nobody loses their night vision.</p>
  <p class="cf-start-row"><button type="button" class="btn cf-start" data-cf-start disabled>Start campfire mode</button></p>
  <p class="cf-start-note small" data-cf-note>Shuffles all {n} stories. Swipe or use the arrows to move on.</p>
</div></section>
<div class="band band-mist"><div class="wrap narrow prose cf-about">
  <p>The fire's down to coals and somebody says "tell a scary story". Tap the button above, hand your phone to whoever's brave
  enough and it'll pull up a random story from the site in big red text on a black screen. Red light doesn't wreck your night
  vision the way a white screen does (it's why hunters and stargazers use red headlamps) so you can still see the treeline when
  you look up. Whether that's a good thing is up to you.</p>
  <p>Swipe or tap Next for another story, bump the text up with A+ if you're reading at arm's length, and your screen stays on
  while it's open on most phones. If nobody wants to do the voices there's a read it to me button too. Open this page once
  while you've got signal and campfire mode keeps working with none, which is handy because the good campsites never have any.</p>
  <p>Every one of these was told by a real person and we can't vouch for what any of them saw. We left out the stories about
  creatures from living Indigenous and local traditions, like the wendigo and the skinwalker. Those still belong to the
  people who tell them and it didn't feel right to turn them into campfire entertainment.</p>
</div></div>
<section class="band band-mist cf-list-band" aria-labelledby="cf-all"><div class="wrap narrow">
  <h2 id="cf-all">Every story in the mix</h2>
  <p class="small">{len(long_ones)} witness stories. Most take two to four minutes to read out loud.</p>
  <ul class="cf-list">{"".join(li(x) for x in long_ones)}</ul>
  <p class="small">Got one of your own? <a href="{u('/report/')}">Report an encounter</a> and it might end up in here.</p>
</div></section>
<script type="application/json" id="cf-config">{cfg}</script>'''

    head = (f'<link rel="stylesheet" href="{u("/static/campfire.css")}">'
            f'<script src="{u("/static/campfire.js")}" defer></script>')
    ctx.write('/stories/campfire/', ctx.page(
        '/stories/campfire/', 'Campfire stories: read witness stories out loud at night', body,
        f'{n} real witness stories about Bigfoot, Dogman, UFOs and more, made for reading out loud around a campfire: '
        'red-on-black night mode, big text, shuffled, works offline.',
        body_class='campfire', head_extra=head, viewport_fit=True, article={'verb': 'By', 'published': '2026-10-24'}))

    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if os.path.exists(sp):
        items = json.load(open(sp, encoding='utf-8'))
        items.append({'t': 'Campfire stories', 'a': 'campfire scary stories camping read aloud night mode red',
                      'k': 'Witness stories to read out loud at night', 'u': u('/stories/campfire/'), 'i': 'q-night', 'c': 'hominid'})
        json.dump(items, open(sp, 'w', encoding='utf-8'), separators=(',', ':'))
    print(f'campfire: {len(long_ones)} witness stories + {len(short_ones)} short ones')

"""Witness stories: longer first-hand accounts people have shared publicly (Reddit and similar), retold in our own words.

Pages: /stories/ (every story, newest encounter first, filter by creature) and /stories/<id>/ (one story).
Creature pages list their stories in a "Witness stories" section (site/build.py reads the same file).

Data: data/witness_stories.json, a list of
  {id, creature, title, when, year, place, teller, source, url, posted, dek, body: [paragraphs]}
Each story credits the person who told it and links the original post. Nothing is copied word for word except
short quotes. Anyone can ask for their story to be changed or removed through /contact/.
"""
import json, os, re

WPM = 230
FILTERS_AT = int(os.environ.get('WS_FILTERS_AT', '40'))  # show setting/place/sort filters once there are this many
# Same Worker and Turnstile settings as sections/reports.py: story pages carry the Real-or-hoax vote widget (vote.js).
API = os.environ.get('EA_API', 'https://api.encounteratlas.com').rstrip('/')
SITEKEY = os.environ.get('TURNSTILE_SITEKEY', '1x00000000000000000000AA')
SETTINGS = {'home': 'At home', 'camp': 'Camping', 'road': 'On the road', 'outdoors': 'In the woods', 'work': 'At work'}


def minutes(st):
    words = sum(len(p.split()) for p in st['body'])
    return max(1, round(words / WPM))


def load(ctx):
    p = os.path.join(ctx.ROOT, 'data', 'witness_stories.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []


def card(ctx, st, show_creature=True):
    """Story card, also used on creature pages (build.py has its own copy of this markup via story_cards)."""
    e, u = ctx.esc, ctx.url
    c = ctx.by_slug.get(st['creature'])
    who = f'<span class="ws-crit">{ctx.crit_icon(c)} {e(c["name"])}</span>' if (c and show_creature) else ''
    return (f'<a class="ws-card" href="{u("/stories/" + st["id"] + "/")}">{who}'
            f'<b>{e(st["title"])}</b><span class="ws-meta">{e(st["place"])} · {e(st["when"])}</span>'
            f'<span class="ws-dek">{e(st["dek"])}</span>'
            f'<span class="ws-go">Read the story · {minutes(st)} min</span></a>')


ZOOM_LABEL = {9: 'a few miles', 8: 'about 10 miles', 7: 'about 25 miles'}


def where(ctx, st, c):
    """A small map of the rough area. Many of these are people's homes, so it's always a soft circle, never a pin."""
    if not st.get('geo'):
        return ''
    lat, lon, z = st['geo']
    e, u = ctx.esc, ctx.url
    near = (f'The circle marks the rough area, within {ZOOM_LABEL[z]}, not an exact spot.' if z in ZOOM_LABEL
            else "The account doesn't say exactly where, so the circle is only a rough guide.")
    at = f'{lat:.2f},{lon:.2f},{min(z, 8)}'
    return (f'<section class="ws-where cat-{c["cat"]}">'
            f'<div class="ws-map" data-ws-map="{lat},{lon},{z}" role="img" aria-label="Map showing the rough area: {e(st["place"])}"></div>'
            f'<p><strong>Where it happened.</strong> {e(st["place"])}. {near} '
            f'<a href="{u("/map/?at=" + at)}">See other sightings nearby</a></p></section>')


def build(ctx):
    stories = load(ctx)
    if not stories:
        return
    e, u = ctx.esc, ctx.url
    head = f'<link rel="stylesheet" href="{u("/static/stories.css")}">'
    vote_head = (head + f'<link rel="stylesheet" href="{u("/static/report.css")}">'
                 f'<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" async defer></script>'
                 f'<script src="{u("/static/vote.js")}" defer></script>')
    cfg = json.dumps({'api': API, 'base': ctx.BASE, 'sitekey': SITEKEY}, separators=(',', ':')).replace('</', '<\\/')
    by_c = {}
    for st in stories:
        by_c.setdefault(st['creature'], []).append(st)

    for st in stories:
        c = ctx.by_slug[st['creature']]
        same = [x for x in by_c[st['creature']] if x['id'] != st['id']][:4]
        other = [x for x in stories if x['creature'] != st['creature']]
        other = sorted(other, key=lambda x: (x['creature'] == st['creature'], -len(x['body'])))[:4]
        body_html = ''.join(f'<p>{e(p)}</p>' for p in st['body'])
        quote = f'<blockquote class="ws-quote">{e(st["quote"])}</blockquote>' if st.get('quote') else ''
        more_same = (f'<h2>More {e(c["name"])} stories</h2><div class="ws-grid">{"".join(card(ctx, x, False) for x in same)}</div>'
                     if same else '')
        body = f'''
<section class="band band-dark ws-head cat-{c['cat']}"><div class="wrap narrow">
  <a class="ws-art" href="{u('/creatures/' + c['slug'] + '/')}" tabindex="-1" aria-hidden="true">{ctx.crit_icon(c, 'ico ws-art-ico')}</a>
  <p class="crumb"><a href="{u('/stories/')}">Witness stories</a> / <a href="{u('/creatures/' + c['slug'] + '/')}">{e(c['name'])}</a></p>
  <h1>{e(st['title'])}</h1>
  <p class="lede">{e(st['dek'])}</p>
  <p class="ws-byline">{e(st['place'])} · {e(st['when'])} · {minutes(st)} min read</p>
</div></section>
<div class="band band-mist"><div class="wrap narrow">
  <article class="prose ws-body">
    {quote}
    {body_html}
    <aside class="ws-credit">
      <p><strong>Where this comes from.</strong> {e(st['teller'])} shared this account publicly on {e(st['source'])}
      in {e(st['posted'][:4])}. We've retold it in our own words and kept their details as given; we can't verify it,
      and we don't claim it's true or false. <a href="{e(st['url'])}" rel="noopener nofollow">Read the original post</a>.</p>
      <p>Is this your story? <a href="{u('/contact/?about=story:' + st['id'])}">Tell us</a> and we'll credit you how you like,
      correct it, or take it down.</p>
    </aside>
  </article>
  {where(ctx, st, c)}
  <div class="ws-vote" data-vote-item="s:{st['id']}"></div>
  <script type="application/json" id="ea-config">{cfg}</script>
  <section class="seen-box cat-{c['cat']}">{ctx.crit_icon(c)}<div>
    <h2>Had an experience like this?</h2>
    <p>Tell us what happened. Every report is read by a person before it goes on the map, and you can stay anonymous.</p>
    <p class="seen-actions"><a class="btn" href="{u('/report/?creature=' + c['slug'])}">Report an encounter</a>
    <a class="btn btn-ghost" href="{u('/creatures/' + c['slug'] + '/')}">All about {e(c['name'])}</a></p>
  </div></section>
  {more_same}
  <h2>More witness stories</h2>
  <div class="ws-grid">{"".join(card(ctx, x) for x in other)}</div>
  {ctx.signup_box('ws', 'A new story every week', 'Witness stories, old-newspaper monsters and a creature of the week. One short email on Thursdays, unsubscribe in one click.')}
</div></div>'''
        ctx.write(f'/stories/{st["id"]}/', ctx.page(f'/stories/{st["id"]}/', f'{st["title"]}: a {c["name"]} encounter', body,
                                                   st['dek'], head_extra=vote_head + f'<script src="{u("/static/stories.js")}" defer></script>'))

    # Hub: newest encounters first, chips to filter by creature (all cards are in the HTML; JS only hides).
    # Once there are FILTERS_AT stories, a second row adds setting, place and sort. ?c=, ?s=, ?w= and ?o= preselect them.
    order = sorted(stories, key=lambda x: -x['year'])
    counts = sorted(by_c.items(), key=lambda kv: (-len(kv[1]), ctx.by_slug[kv[0]]['name']))
    chips = ''.join(f'<button type="button" class="chip" data-c="{k}">{e(ctx.by_slug[k]["name"])} <span>{len(v)}</span></button>'
                    for k, v in counts)
    cards = ''.join(f'<div data-c="{x["creature"]}" data-s="{x.get("setting", "")}" data-w="{e(x.get("country", ""))}|{e(x.get("region", ""))}" '
                    f'data-y="{x["year"]}" data-m="{sum(len(p.split()) for p in x["body"])}">{card(ctx, x)}</div>' for x in order)
    more = ''
    if len(stories) >= FILTERS_AT:
        n_set = {k: sum(1 for x in stories if x.get('setting') == k) for k in SETTINGS}
        set_chips = ''.join(f'<button type="button" class="chip" data-s="{k}">{v} <span>{n_set[k]}</span></button>'
                            for k, v in SETTINGS.items() if n_set[k])
        by_country = {}
        for x in stories:
            if x.get('country'):
                by_country.setdefault(x['country'], {}).setdefault(x.get('region', ''), 0)
                by_country[x['country']][x.get('region', '')] += 1
        opts = '<option value="">Anywhere</option>'
        for co, regs in sorted(by_country.items(), key=lambda kv: (kv[0] != 'United States', kv[0])):
            tot = sum(regs.values())
            opts += f'<option value="{e(co)}|">{e(co)} ({tot})</option>'
            if len(regs) > 1:
                opts += ''.join(f'<option value="{e(co)}|{e(r)}">&nbsp;&nbsp;{e(r)} ({n})</option>' for r, n in sorted(regs.items()) if r)
        more = f'''
  <div class="ws-filters">
    <div class="chips ws-set" role="group" aria-label="Filter by setting"><button type="button" class="chip on" data-s="">Anywhere <span>{len(stories)}</span></button>{set_chips}</div>
    <label class="ws-sel">Where <select data-w>{opts}</select></label>
    <label class="ws-sel">Sort <select data-o><option value="new">Newest encounter</option><option value="old">Oldest encounter</option><option value="long">Longest read</option><option value="short">Shortest read</option></select></label>
  </div>'''
    body = f'''
<section class="band band-dark"><div class="wrap">
  <h1>Witness stories</h1>
  <p class="lede">{len(stories)} first-hand accounts people have shared publicly, retold in full: what they saw, where, and what happened next. Each one credits the person who told it and links the original.</p>
  <div class="chips ws-chips" role="group" aria-label="Filter by creature"><button type="button" class="chip on" data-c="">All <span>{len(stories)}</span></button>{chips}</div>{more}
</div></section>
<div class="band band-mist"><div class="wrap">
  <p class="ws-count" data-count hidden></p>
  <div class="ws-grid ws-hub">{cards}</div>
  <p class="small">We can't verify these accounts and don't claim they're true or false. Your own story belongs here too: <a href="{u('/report/')}">report an encounter</a>.</p>
</div></div>
<script src="{u('/static/stories.js')}" defer></script>'''
    ctx.write('/stories/', ctx.page('/stories/', 'Witness stories: first-hand Bigfoot, Dogman and cryptid encounters', body,
                                    f'{len(stories)} first-hand cryptid and creature encounters, retold in full and credited to the people who lived them.',
                                    head_extra=head))

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


def build(ctx):
    stories = load(ctx)
    if not stories:
        return
    e, u = ctx.esc, ctx.url
    head = f'<link rel="stylesheet" href="{u("/static/stories.css")}">'
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
                                                   st['dek'], head_extra=head))

    # Hub: newest encounters first, chips to filter by creature (all cards are in the HTML; JS only hides).
    order = sorted(stories, key=lambda x: -x['year'])
    counts = sorted(by_c.items(), key=lambda kv: (-len(kv[1]), ctx.by_slug[kv[0]]['name']))
    chips = ''.join(f'<button type="button" class="chip" data-c="{k}">{e(ctx.by_slug[k]["name"])} <span>{len(v)}</span></button>'
                    for k, v in counts)
    cards = ''.join(f'<div data-c="{x["creature"]}">{card(ctx, x)}</div>' for x in order)
    body = f'''
<section class="band band-dark"><div class="wrap">
  <h1>Witness stories</h1>
  <p class="lede">{len(stories)} first-hand accounts people have shared publicly, retold in full: what they saw, where, and what happened next. Each one credits the person who told it and links the original.</p>
  <div class="chips ws-chips" role="group" aria-label="Filter by creature"><button type="button" class="chip on" data-c="">All <span>{len(stories)}</span></button>{chips}</div>
</div></section>
<div class="band band-mist"><div class="wrap">
  <div class="ws-grid ws-hub">{cards}</div>
  <p class="small">We can't verify these accounts and don't claim they're true or false. Your own story belongs here too: <a href="{u('/report/')}">report an encounter</a>.</p>
</div></div>
<script>(()=>{{const b=[...document.querySelectorAll('.ws-chips .chip')],c=[...document.querySelectorAll('.ws-hub>[data-c]')];
b.forEach(x=>x.addEventListener('click',()=>{{b.forEach(y=>y.classList.toggle('on',y===x));c.forEach(d=>d.hidden=!!x.dataset.c&&d.dataset.c!==x.dataset.c);}}));}})();</script>'''
    ctx.write('/stories/', ctx.page('/stories/', 'Witness stories: first-hand Bigfoot, Dogman and cryptid encounters', body,
                                    f'{len(stories)} first-hand cryptid and creature encounters, retold in full and credited to the people who lived them.',
                                    head_extra=head))

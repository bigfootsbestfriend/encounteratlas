"""Hand-written guides: costume guides (/costumes/), gift guides (/gifts/) and town trip guides (under /places/).

Data: data/articles.json = {"hubs": [...], "articles": [...]}. Each article is a list of blocks:
  text    {"t": "text", "kick": "...", "h": "...", "p": ["paragraph with [links](/path/)", ...]}
  shop    {"t": "shop", "h": "...", "why": "...", "items": [[name, amazon search, why], ...]}   (Amazon searches, like /gear/)
  steps   {"t": "steps", "h": "...", "p": [...], "items": ["step", ...]}
  faq     {"t": "faq", "items": [[question, answer], ...]}
  places  {"t": "places", "h": "...", "p": [...], "slugs": ["place-slug", ...]}                (cards from data/places.json)
  sources {"t": "sources", "items": [[name, url], ...]}
No shop blocks for LIVING_TRADITIONS creatures (Mike's rule): the build stops if an article with "creature" set to one has any.
Keep card counts even (2, 4, 6): the build stops on an odd shop or places block.
"""
import json, os, urllib.parse

TAG = 'encountersatlas-20'
SPONSORED = 'rel="sponsored nofollow noopener" target="_blank"'
LIVING = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
          'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}  # same list as build.py


def amz(q):
    return 'https://www.amazon.com/s?' + urllib.parse.urlencode({'k': q, 'tag': TAG})


def build(ctx):
    E, U, md = ctx.esc, ctx.url, ctx.md_links
    data = json.load(open(os.path.join(ctx.ROOT, 'data', 'articles.json'), encoding='utf-8'))
    places = {p['slug']: p for p in json.load(open(os.path.join(ctx.ROOT, 'data', 'places.json'), encoding='utf-8'))}
    head = (f'<link rel="stylesheet" href="{U("/static/creature-ia.css")}"><link rel="stylesheet" href="{U("/static/places.css")}">'
            f'<link rel="stylesheet" href="{U("/static/articles.css")}">')
    ps = lambda xs: ''.join(f'<p>{md(x)}</p>' for x in xs or [])

    def block(a, b, i):
        t = b['t']
        kick = f'<p class="blk-kick">{E(b["kick"])}</p>' if b.get('kick') else ''
        h = f'<h2>{E(b["h"])}</h2>' if b.get('h') else ''
        if t == 'text':
            return f'<section class="blk{" blk-intro" if i == 0 else ""}">{kick}{h}{ps(b["p"])}</section>'
        if t == 'shop':
            assert a.get('creature') not in LIVING, f'{a["path"]}: no shopping on living traditions'
            assert len(b['items']) % 2 == 0, f'{a["path"]}: odd shop block "{b.get("h")}"'
            cards = ''.join(f'<a class="md-book tone-{(i + j) % 5}" href="{E(amz(q))}" {SPONSORED}><span class="md-spine" aria-hidden="true"></span>'
                            f'<span class="md-txt"><b>{E(n)}</b><small>{E(w)}</small><span class="md-go">See options on Amazon</span></span></a>'
                            for j, (n, q, w) in enumerate(b['items']))
            why = f'<p>{md(b["why"])}</p>' if b.get('why') else ''
            return (f'<section class="blk ar-shop">{kick}{h}{why}<div class="md-grid">{cards}</div>'
                    f'<p class="ar-aff"><a class="md-aff" href="{U("/privacy/")}#affiliate">(affiliate links)</a></p></section>')
        if t == 'steps':
            return f'<section class="blk">{kick}{h}{ps(b.get("p"))}<ol class="ar-steps">{"".join(f"<li>{md(x)}</li>" for x in b["items"])}</ol></section>'
        if t == 'faq':
            return ('<section class="blk"><p class="blk-kick">Quick answers</p><h2>Questions people ask</h2>' +
                    ''.join(f'<div class="faq-item"><h3>{E(q)}</h3><p>{md(x)}</p></div>' for q, x in b['items']) + '</section>')
        if t == 'places':
            assert len(b['slugs']) % 2 == 0, f'{a["path"]}: odd places block'
            cards = ''
            for s in b['slugs']:
                p = places[s]
                cards += (f'<a class="pl-card" href="{U("/places/" + s + "/")}" data-type="{p["type"]}"><span class="pl-txt">'
                          f'<span class="pl-name">{E(p["name"])}</span><span class="pl-sum">{E(p["summary"])}</span>'
                          + (f'<span class="pl-price">{E(p["price"])}</span>' if p.get('price') else '') + '</span></a>')
            return f'<section class="blk ar-places">{kick}{h}{ps(b.get("p"))}<div class="pl-grid">{cards}</div></section>'
        if t == 'sources':
            return ('<section class="blk blk-src"><h2>Sources</h2><ul class="src-list">' +
                    ''.join(f'<li><a href="{E(u)}" rel="noopener">{E(n)}</a></li>' for n, u in b['items']) +
                    '</ul><p class="small muted">Hours, prices and dates change, so check the official site before you travel.</p></section>')
        raise ValueError(f'{a["path"]}: unknown block {t}')

    def faq_ld(a):
        qs = [x for b in a['blocks'] if b['t'] == 'faq' for x in b['items']]
        import re
        plain = lambda s: re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', s)
        return [{'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': plain(x)}} for q, x in qs]}] if qs else None

    hubs = {h['kind']: h for h in data['hubs']}
    for a in data['articles']:
        hub = hubs.get(a['kind'])
        crumb = (f'<a href="{U(hub["path"])}">{E(hub["crumb"])}</a> / ' if hub else f'<a href="{U("/places/")}">Places</a> / Trip guides / ')
        others = [o for o in data['articles'] if o['kind'] == a['kind'] and o is not a]
        more = ''
        if others:
            more = ('<aside class="facts ar-more"><h2>More guides</h2><ul>' +
                    ''.join(f'<li><a href="{U(o["path"])}">{E(o["h1"])}</a></li>' for o in others) +
                    ''.join(f'<li><a href="{U(p)}">{E(n)}</a></li>' for p, n in a.get('see', [])) + '</ul></aside>')
        body = f'''
<section class="band band-dark ar-head"><div class="wrap">
  <p class="crumb">{crumb}{E(a.get('short') or a['h1'])}</p>
  <h1>{E(a['h1'])}</h1>
  <p class="lede">{md(a['lede'])}</p>
</div></section>
<div class="band band-mist"><div class="wrap creature-body">
  <article class="prose ar-prose">{''.join(block(a, b, i) for i, b in enumerate(a['blocks']))}</article>
  {more}
</div></div>'''
        ctx.write(a['path'], ctx.page(a['path'], a['title'], body, a['desc'], body_class='articles', head_extra=head,
                                      ld=faq_ld(a), article={'published': a['published'], 'updated': a.get('updated'), 'verb': 'By'}))

    for h in data['hubs']:
        arts = [a for a in data['articles'] if a['kind'] == h['kind']]
        assert len(arts) % 2 == 0, f'{h["path"]}: odd number of cards'
        cards = ''.join(f'<a class="ar-card" href="{U(a["path"])}"><span class="ar-ico">{ctx.icon(a["icon"])}</span>'
                        f'<span class="ar-txt"><b>{E(a["h1"])}</b><small>{E(a["blurb"])}</small></span></a>' for a in arts)
        other = ''.join(f'<a class="btn btn-ghost" href="{U(o["path"])}">{E(o["h1"])}</a>' for o in data['hubs'] if o is not h)
        body = f'''
<section class="band band-dark ar-head"><div class="wrap">
  <p class="crumb">{E(h['crumb'])}</p>
  <h1>{E(h['h1'])}</h1>
  <p class="lede">{md(h['lede'])}</p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <div class="ar-cards">{cards}</div>
  <div class="prose ar-hubnote">{ps(h.get('p'))}</div>
  <p class="ar-other">{other}<a class="btn btn-ghost" href="{U('/gear/')}">Field gear</a></p>
</div></div>'''
        ctx.write(h['path'], ctx.page(h['path'], h['title'], body, h['desc'], body_class='articles', head_extra=head,
                                      noindex=len(arts) < 4))  # a two-card hub is too thin for Google until more guides exist

"""Creature comparison pages: /compare/ hub and /compare/<a>-vs-<b>/ from data/compare.json.

Each page puts two creatures side by side: posters, a fact table from data/creatures.json (also called, where, first
reported, size, habitat, signs), the hand-written differences, "could they be the same?", a "which did you see?"
checklist, and counts of famous cases and witness stories for each, with links into both creature pages.
"""
import json, os

SKY = {'hominid': ('#E3A649', '#B5532F'), 'canid': ('#3B4C6B', '#1B2A3A'), 'winged': ('#3B4C6B', '#1B2A3A'),
       'aquatic': ('#E8B04A', '#C8693A'), 'entity': ('#3B4C6B', '#1B2A3A'), 'ufo': ('#2E3E5C', '#141E2E'),
       'fae': ('#C97B9A', '#4A2E4F'), 'other': ('#E3A649', '#B5532F')}


def as_list(v):
    if isinstance(v, list):
        return v
    try:
        import ast
        x = ast.literal_eval(v)
        return x if isinstance(x, list) else [v]
    except Exception:
        return [v] if v else []


def build(ctx):
    path = os.path.join(ctx.ROOT, 'data', 'compare.json')
    if not os.path.exists(path):
        return
    pairs = [p for p in json.load(open(path, encoding='utf-8')) if p['a'] in ctx.by_slug and p['b'] in ctx.by_slug]
    sp = os.path.join(ctx.ROOT, 'data', 'witness_stories.json')
    stories = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else []
    stories = stories if isinstance(stories, list) else stories.get('stories', [])
    n_stories = {}
    for s in stories:
        n_stories[s.get('creature')] = n_stories.get(s.get('creature'), 0) + 1
    esc, url = ctx.esc, ctx.url

    def poster(c):
        a, b = SKY.get(c['cat'], SKY['other'])
        sid = 'cmp-' + c['slug']
        art = c.get('art')
        img = (f'<image href="{url("/static/" + art + ".svg")}" x="22" y="26" width="160" height="160"/>' if art else '')
        return (f'<svg class="poster cmp-poster" viewBox="0 0 200 200" role="img" aria-label="{esc(c["name"])}">'
                f'<defs><linearGradient id="{sid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>'
                f'<clipPath id="c{sid}"><rect x="6" y="6" width="188" height="188" rx="10"/></clipPath></defs>'
                f'<g clip-path="url(#c{sid})"><rect width="200" height="200" fill="url(#{sid})"/><circle cx="150" cy="52" r="24" fill="#F3E3B8" opacity=".9"/>'
                f'<path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="#5E4A3A" opacity=".5"/>'
                f'<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="#1E3A2F"/>{img}</g>'
                f'<rect x="6" y="6" width="188" height="188" rx="10" fill="none" stroke="#F3E3B8" stroke-width="4"/></svg>')

    def slug(p):
        return f'{p["a"]}-vs-{p["b"]}'

    def title(p):
        return f'{ctx.by_slug[p["a"]]["name"]} vs {ctx.by_slug[p["b"]]["name"]}'

    head = f'<link rel="stylesheet" href="{url("/static/compare.css")}">'
    for p in pairs:
        A, B = ctx.by_slug[p['a']], ctx.by_slug[p['b']]
        rows = [('Also called', ', '.join(as_list(A.get('aliases'))[:4]), ', '.join(as_list(B.get('aliases'))[:4])),
                ('Where', A.get('region', ''), B.get('region', '')),
                ('First reported', A.get('first', ''), B.get('first', '')),
                ('Size', A.get('size', ''), B.get('size', '')),
                ('Habitat', A.get('habitat', ''), B.get('habitat', '')),
                ('Signs', '; '.join(as_list(A.get('signs'))[:3]), '; '.join(as_list(B.get('signs'))[:3])),
                ('Famous cases', str(len(as_list(A.get('famous')))), str(len(as_list(B.get('famous'))))),
                ('Witness stories', str(n_stories.get(A['slug'], 0)), str(n_stories.get(B['slug'], 0)))]
        table = ('<div class="cmp-table" role="table" aria-label="Side by side facts">'
                 f'<div class="cmp-row cmp-headrow" role="row"><span role="columnheader"></span><span role="columnheader">{esc(A["name"])}</span><span role="columnheader">{esc(B["name"])}</span></div>'
                 + ''.join(f'<div class="cmp-row" role="row"><span class="cmp-k" role="rowheader">{esc(k)}</span><span role="cell">{esc(a)}</span><span role="cell">{esc(b)}</span></div>'
                           for k, a, b in rows if a or b) + '</div>')
        diffs = '<ul class="cmp-diffs">' + ''.join(
            (lambda d: f'<li><strong>{esc(d.split(":", 1)[0])}:</strong>{esc(d.split(":", 1)[1])}</li>' if ':' in d[:30] else f'<li>{esc(d)}</li>')(d)
            for d in p['diffs']) + '</ul>'
        tell = ('<div class="cmp-tell">'
                f'<div><h3>Probably {esc(A["name"])} if…</h3><ul>' + ''.join(f'<li>{esc(a)}</li>' for a, _ in p['tell']) + '</ul></div>'
                f'<div><h3>Probably {esc(B["name"])} if…</h3><ul>' + ''.join(f'<li>{esc(b)}</li>' for _, b in p['tell']) + '</ul></div></div>')
        more = [q for q in pairs if q is not p and ({q['a'], q['b']} & {p['a'], p['b']})][:4] or [q for q in pairs if q is not p][:4]
        more_html = '<ul class="cmp-more">' + ''.join(f'<li><a href="{url("/compare/" + slug(q) + "/")}">{esc(title(q))}</a></li>' for q in more) + '</ul>'
        faq = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': f'What is the difference between {A["name"]} and {B["name"]}?',
             'acceptedAnswer': {'@type': 'Answer', 'text': p['intro'] + ' ' + ' '.join(p['diffs'][:2])}},
            {'@type': 'Question', 'name': f'Are {A["name"]} and {B["name"]} the same thing?',
             'acceptedAnswer': {'@type': 'Answer', 'text': p['same']}}]}
        body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/creatures/')}">Creatures</a> / <a href="{url('/compare/')}">Compare</a></p>
  <div class="cmp-hero"><a href="{url('/creatures/' + A['slug'] + '/')}">{poster(A)}<span>{esc(A['name'])}</span></a>
    <span class="cmp-vs" aria-hidden="true">vs</span>
    <a href="{url('/creatures/' + B['slug'] + '/')}">{poster(B)}<span>{esc(B['name'])}</span></a></div>
  <h1>{esc(A['name'])} vs {esc(B['name'])}: what's the difference?</h1>
  <p class="lede">{esc(p['intro'])}</p>
</div></section>
<div class="band band-mist"><div class="wrap cmp-body">
  <h2>Side by side</h2>
  {table}
  <h2>The big differences</h2>
  {diffs}
  <h2>Could they be the same thing?</h2>
  <p>{esc(p['same'])}</p>
  <h2>Which one did you see?</h2>
  {tell}
  <p class="cmp-cta">Seen something like this? <a class="btn" href="{url('/report/')}">Report your encounter</a>
    <a class="btn btn-quiet" href="{url('/creatures/' + A['slug'] + '/')}">All about {esc(A['name'])}</a>
    <a class="btn btn-quiet" href="{url('/creatures/' + B['slug'] + '/')}">All about {esc(B['name'])}</a></p>
  <h2>More comparisons</h2>
  {more_html}
</div></div>
<script type="application/ld+json">{json.dumps(faq)}</script>'''
        ctx.write(f'/compare/{slug(p)}/', ctx.page(f'/compare/{slug(p)}/', f'{title(p)}: what\'s the difference?', body,
                                                  f'{A["name"]} or {B["name"]}? Where each is seen, what they look like, how the stories differ, and how to tell which one you saw.',
                                                  head_extra=head, article={'updated': p.get('updated')}))

    cards = ''.join(
        f'<a class="cmp-card" href="{url("/compare/" + slug(p) + "/")}"><span class="cmp-pair">{poster(ctx.by_slug[p["a"]])}{poster(ctx.by_slug[p["b"]])}</span>'
        f'<b>{esc(title(p))}</b><small>{esc(p["intro"][:110].rsplit(" ", 1)[0])}…</small></a>' for p in pairs)
    body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/creatures/')}">Creatures</a></p>
  <h1>Creature comparisons</h1>
  <p class="lede">Bigfoot or Yeti? Dogman or skinwalker? Grey or Nordic? Side-by-side guides to the creatures people mix up most, and how to tell which one you saw.</p>
</div></section>
<div class="band band-mist"><div class="wrap"><div class="cmp-grid">{cards}</div></div></div>'''
    ctx.write('/compare/', ctx.page('/compare/', 'Creature comparisons: Bigfoot vs Yeti, Dogman vs skinwalker and more', body,
                                    'Side-by-side guides to the cryptids and UFO types people mix up most.', head_extra=head))

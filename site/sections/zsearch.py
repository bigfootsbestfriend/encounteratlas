"""Adds places, mysteries, guides, old newspaper cases and the main hub pages to the site search index (OUT/data/search.json).

Named zsearch.py so it runs after every other section (they load in alphabetical order) and the pages it points to exist.
"""
import json, os

HUBS = [('/map/', 'The encounter map', 'map world everything pins', 'Map', 'saucer', 'ufo'),
        ('/ufo/', 'UFO sightings', 'ufo uap flying saucer', 'Hub', 'saucer', 'ufo'),
        ('/ufo/blue-book/', 'Project Blue Book files', 'air force blue book', 'Air Force files', 'folder', 'ufo'),
        ('/ufo/releases/', 'Official UFO releases', 'government disclosure documents', 'Timeline', 'folder', 'ufo'),
        ('/encounters/', 'Close encounters', 'aliens beings abduction landing', 'Hub', 'entity', 'entity'),
        ('/mysteries/', 'Unexplained mysteries', 'mystery unsolved', 'Hub', 'q-dusk', 'other'),
        ('/history/', 'Old newspaper reports', 'history newspapers 1800s', 'Hub', 'newspaper', 'other'),
        ('/places/', 'Places to visit', 'museum festival statue roadside', 'Hub', 'museum', 'other'),
        ('/events/', 'Events and festivals', 'festival conference gathering', 'Calendar', 'festival', 'other'),
        ('/guides/', 'Field guides', 'how to guide', 'Hub', 'expedition', 'hominid'),
        ('/gear/', 'Field gear', 'gear trail camera thermal binoculars equipment', 'What to pack', 'eyeshine', 'hominid'),
        ('/podcasts/', 'Podcasts', 'podcast listen episodes', 'Directory', 'q-howl', 'entity'),
        ('/tools/', 'Tools', 'quiz identify compare size', 'Hub', 'clipboard', 'other'),
        ('/report/', 'Report an encounter', 'report sighting submit tell', 'Report', 'clipboard', 'other')]


def build(ctx):
    U = ctx.url
    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if not os.path.exists(sp):
        return
    load = lambda f: json.load(open(os.path.join(ctx.ROOT, 'data', f), encoding='utf-8')) if os.path.exists(os.path.join(ctx.ROOT, 'data', f)) else []
    items = json.load(open(sp, encoding='utf-8'))
    have = {it['u'] for it in items}
    ok = lambda p: os.path.exists(os.path.join(ctx.OUT, p.strip('/'), 'index.html'))
    add = lambda it: (it['u'] not in have and ok(it['u'][len(ctx.BASE):] if ctx.BASE else it['u'])) and (items.append(it), have.add(it['u']))
    for path, t, a, k, i, c in HUBS:
        add({'t': t, 'a': a, 'k': k, 'u': U(path), 'i': i, 'c': c})
    for p in load('places.json'):
        add({'t': p['name'], 'a': ' '.join(x for x in (p.get('city'), p.get('region'), p.get('country')) if x) + ' ' + ' '.join(p.get('creatures') or []),
             'k': 'Place to visit' + (f', {p["city"]}' if p.get('city') else ''), 'u': U('/places/' + p['slug'] + '/'), 'i': 'museum', 'c': 'other'})
    for m in load('mysteries.json'):
        add({'t': m['name'], 'a': m.get('place', ''), 'k': f'Mystery, {m.get("year") or ""}'.strip(', '), 'u': U('/mysteries/' + m['slug'] + '/'), 'i': 'q-dusk', 'c': 'other'})
    for g in load('guides.json'):
        add({'t': g['title'], 'a': g.get('short', '') + ' guide how to', 'k': 'Field guide', 'u': U('/guides/' + g['slug'] + '/'), 'i': g.get('icon') or 'expedition', 'c': 'hominid'})
    HPAGE = {'airship': 'airships-1896-1897', 'airship-1909': 'phantom-airships-1909', 'wild-man': 'wild-men', 'sea-serpent': 'sea-serpents',
             'jersey-devil': 'jersey-devil-1909', 'giant-bird': 'giant-birds', 'phantom-light': 'phantom-lights', 'creature': 'strange-creatures'}
    for h in load('historic.json'):  # each old newspaper case, linked to its card (id="h-<id>") on the topic page
        pg = '/history/' + HPAGE.get(h['k'], '') + '/'
        u = U(pg) + '#h-' + h['id']
        if u in have or not ok(pg):
            continue
        cr = ctx.by_slug.get(h.get('creature') or '', {}).get('name', '')
        items.append({'t': h['title'], 'a': ' '.join(x for x in (h.get('town'), h.get('state'), h.get('place'), cr, 'newspaper') if x).lower(),
                      'k': f'Old newspaper, {h["date"][:4]}, {h.get("town") or h.get("state")}', 'u': u, 'i': 'newspaper', 'c': 'other'})
        have.add(u)
    json.dump(items, open(sp, 'w', encoding='utf-8'), separators=(',', ':'))

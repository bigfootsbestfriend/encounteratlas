"""Podcast player helpers shared by podcasts.py (writes /data/podcast-play.json, Play buttons on creature episode
pages) and z_road_trip.py ("Listen along" on trip pages). Not a section itself (leading underscore).

Audio is the show's own enclosure URL (data/podcasts_episodes.json "audio", filled by tools/podcast_audio.py) and is
streamed straight from the show's host by static/podplayer.js, so creators keep their download counts.
"""
import html, json, os

PER_CREATURE = 5      # in /data/podcast-play.json
PER_STOP = 3          # shown per creature in a "Listen along" list
# Same list as LIVING_TRADITIONS in site/build.py: info only, no playlists for them
LIVING = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
          'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}
MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
PLAY_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.1v13.8a1 1 0 0 0 1.5.86l11-6.9a1 1 0 0 0 0-1.72l-11-6.9A1 1 0 0 0 8 5.1z"/></svg>'
_cache = {}


def head(ctx):
    return (f'<link rel="stylesheet" href="{ctx.url("/static/podplayer.css")}">'
            f'<script src="{ctx.url("/static/podplayer.js")}" defer></script>')


def fmt_date(iso):
    try:
        y, m, d = (int(x) for x in iso[:10].split('-'))
        return f'{MON[m]} {d}, {y}'
    except (ValueError, AttributeError, IndexError):
        return ''


def entry(e, show_apple=''):
    """One episode in the player's compact form."""
    return {'t': e['title'], 's': e['show'], 'd': e.get('date', ''), 'm': e.get('mins') or 0, 'a': e['audio'],
            'art': (e.get('art') or '').replace('600x600bb', '160x160bb'), 'u': e['url'],
            'sa': show_apple or f'https://podcasts.apple.com/podcast/id{e["show_id"]}'}


def playable(ctx):
    """{slug: [entry, ...]} top PER_CREATURE episodes with audio per creature, living traditions left out."""
    if 'play' in _cache:
        return _cache['play']
    p_eps = os.path.join(ctx.ROOT, 'data', 'podcasts_episodes.json')
    p_shows = os.path.join(ctx.ROOT, 'data', 'podcasts.json')
    out = {}
    if os.path.exists(p_eps):
        apple = {s['id']: s['apple'] for s in json.load(open(p_shows, encoding='utf-8'))['shows']} if os.path.exists(p_shows) else {}
        for slug, eps in json.load(open(p_eps, encoding='utf-8')).get('creatures', {}).items():
            if slug in LIVING or slug not in ctx.by_slug:
                continue
            got = [entry(e, apple.get(e['show_id'], '')) for e in eps if e.get('audio')][:PER_CREATURE]
            if got:
                out[slug] = got
    _cache['play'] = out
    return out


def write_json(ctx):
    data = playable(ctx)
    d = os.path.join(ctx.OUT, 'data')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'podcast-play.json'), 'w', encoding='utf-8') as f:
        # podplayer.js works out the show's Apple page from u, so leave sa out to keep the file small
        json.dump({k: [{x: y for x, y in e.items() if x != 'sa'} for e in v] for k, v in data.items()}, f, separators=(',', ':'), ensure_ascii=False)
    return data


def attr(e):
    """data-pp attribute value (HTML-escaped JSON)."""
    return html.escape(json.dumps(e, separators=(',', ':'), ensure_ascii=False), quote=True)


def play_button(e, cls='pp-btn', label='Play'):
    return (f'<button type="button" class="{cls}" data-pp="{attr(e)}" aria-label="{html.escape("Play " + e["t"])}">'
            f'{PLAY_SVG}<span>{label}</span></button>')


def listen_along(ctx, hits):
    """Server-rendered "Listen along" section for a trip page.

    hits: [(km from the start, creature slug, spot name), ...] for card spots near the route, any order."""
    E = ctx.esc
    play = playable(ctx)
    first = {}
    for km, slug, name in sorted(hits, key=lambda h: h[0]):
        if slug in play and slug not in first:
            first[slug] = name
    if not first:
        return ''
    groups = ''
    n = 0
    for slug, spot in first.items():
        items = ''
        for e in play[slug][:PER_STOP]:
            meta = ' · '.join(x for x in (fmt_date(e['d']), f'{e["m"]} min' if e['m'] else '') if x)
            items += (f'<li class="pp-ep">{play_button(e, "pp-btn pp-round", "")}<span class="pp-ep-t"><b>{E(e["t"])}</b>'
                      f'<small><a href="{E(e["u"])}" rel="noopener">{E(e["s"])}</a>{" · " + meta if meta else ""}</small></span></li>')
            n += 1
        groups += (f'<li class="pp-stop"><h3><a href="{ctx.url("/podcasts/creature/" + slug + "/")}">{E(ctx.by_slug[slug]["name"])}</a></h3>'
                   f'<p class="pp-near">First spot on the road: {E(spot)}</p><ol class="pp-eps">{items}</ol></li>')
    return f'''
    <section class="pp-along" data-pp-list aria-labelledby="pp-along-h">
      <h2 id="pp-along-h">Listen along</h2>
      <p>Podcast episodes about the creatures you'll pass, in the order you'll pass them. Start it before you pull out and it keeps going with your screen off, with big buttons so you never have to type anything. Episodes stream straight from each show, so the people who make them get the listen.</p>
      <p><button type="button" class="btn pp-all" data-pp-all>{PLAY_SVG} Play all {n} in route order</button></p>
      <ol class="pp-stops">{groups}</ol>
    </section>'''

"""Podcast player helpers shared by podcasts.py (writes /data/podcast-play.json, Play buttons on creature episode
pages), z_road_trip.py ("Listen along" on trip pages), and todays_listen() for the home page (build.py) and the
app home (z_near_me.py). Not a section itself (leading underscore).

Audio is the show's own enclosure URL (data/podcasts_episodes.json "audio", filled by tools/podcast_audio.py) and is
streamed straight from the show's host by static/podplayer.js, so creators keep their download counts.
"""
import datetime, html, json, os, re

PER_CREATURE = 5      # in /data/podcast-play.json
PER_STOP = 3          # shown per creature in a "Listen along" list
# Same list as LIVING_TRADITIONS in site/build.py: info only, no playlists for them
LIVING = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
          'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}
MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
PLAY_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.1v13.8a1 1 0 0 0 1.5.86l11-6.9a1 1 0 0 0 0-1.72l-11-6.9A1 1 0 0 0 8 5.1z"/></svg>'
_cache = {}


def head(ctx):
    return (f'<meta name="ea-nl" content="{html.escape(getattr(ctx, "NEWSLETTER_API", ""))}">'
            f'<link rel="stylesheet" href="{ctx.url("/static/podplayer.css")}">'
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
            got = [dict(entry(e, apple.get(e['show_id'], '')), c=slug) for e in eps if e.get('audio')][:PER_CREATURE]  # c: creature, for share links
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


def art_thumb(ctx, slug):
    """Painted card art for a creature, the small copy first (tools/card_thumbs.py); '' when it has none."""
    for d in ('thumb', 'art'):
        if os.path.exists(os.path.join(ctx.ROOT, 'site', 'static', 'cards', d, slug + '.webp')):
            return ctx.url(f'/static/cards/{d}/{slug}.webp')
    return ''


def picks(ctx, n=9):
    """Newest playable episode per creature, newest first, each episode title once: [(entry, slug), ...]."""
    out, seen = [], set()
    for slug, lst in playable(ctx).items():
        e = max(lst, key=lambda x: x.get('d') or '')
        if e['t'] not in seen:
            seen.add(e['t'])
            out.append((e, slug))
    return sorted(out, key=lambda x: x[0].get('d') or '', reverse=True)[:n]


def todays_listen(ctx, where='home'):
    """"Today's listen": one featured episode with its creature's painted card art and a big play button, a sideways
    strip of more fresh episodes (stations on a radio dial; the one playing gets the needle), Play all and a link to
    /podcasts/. On the home page (build.py) and the app home (z_near_me.py); the page needs head(ctx).
    The featured episode rotates daily through the newest few (the site rebuilds daily), so it changes even in a week
    with no new episodes. Returns '' when nothing is playable."""
    E, U = ctx.esc, ctx.url
    lst = picks(ctx)
    if not lst:
        return ''
    k = datetime.date.today().toordinal() % len(lst)
    lst = lst[k:] + lst[:k]
    (fe, fs), rest = lst[0], lst[1:]
    mins = lambda e: f' · {e["m"]} min' if e.get('m') else ''
    # shows put em and en dashes in their titles; this block is ours, so they read as commas here
    T = lambda e: E(e['t'].replace(' \u2014 ', ', ').replace(' \u2013 ', ', ').replace('\u2014', ', ').replace('\u2013', '-'))

    def img(slug, lazy, e=None):
        a = art_thumb(ctx, slug)
        if not a:
            # no painted card for this creature yet: use the show's own cover instead of a blank square
            cover = (e or {}).get('art', '')
            if not cover:
                return '<span class="pf-noart"></span>'
            cover = re.sub(r'/\d+x\d+bb\.', '/600x600bb.' if not lazy else '/160x160bb.', cover)
            return f'<img src="{html.escape(cover)}" alt="{html.escape((e or {}).get("s", "Podcast") + (" cover art" if (e or {}).get("s", "").lower().endswith("podcast") else " podcast cover art"))}" width="160" height="160"{' loading="lazy"' if lazy else ''} decoding="async">'
        if lazy:
            return f'<img src="{a}" alt="" width="360" height="257" loading="lazy" decoding="async">'
        # the featured picture fills the card (up to ~900 px wide), so phones and big screens get the full art
        full = ctx.url(f'/static/cards/art/{slug}.webp')
        if '/thumb/' not in a:
            return f'<img src="{a}" alt="" width="1164" height="832" decoding="async">'
        return (f'<img src="{full}" srcset="{a} 360w, {full} 1164w" sizes="(min-width: 960px) 900px, 100vw" alt=""'
                f' width="1164" height="832" decoding="async">')

    stations = ''.join(
        f'<li class="pf-st">{img(s, True, e)}<span class="pf-st-t"><a href="{U("/podcasts/creature/" + s + "/")}">{E(ctx.by_slug[s]["name"])}</a>'
        f'<b>{T(e)}</b><small>{E(e["s"])}{mins(e)}</small></span>{play_button(e, "pp-btn pp-round pf-st-play", "")}</li>'
        for e, s in rest)
    hid = f'pf-h-{where}'
    return f'''<section class="pf pf-{where}" data-pp-list aria-labelledby="{hid}">
  <div class="pf-feat">
    <div class="pf-art">{img(fs, False, fe)}<h2 id="{hid}" data-pf-when>Today's listen</h2>{play_button(fe, "pp-btn pf-play", "Play")}</div>
    <div class="pf-info">
      <p class="pf-title">{T(fe)}</p>
      <p class="pf-meta"><span class="pf-eq" aria-hidden="true"><i></i><i></i><i></i><i></i></span><a href="{E(fe["u"])}" rel="noopener">{E(fe["s"])}</a>{mins(fe)}</p>
      <p class="pf-about"><a href="{U("/podcasts/creature/" + fs + "/")}">More {E(ctx.by_slug[fs]["name"])} episodes</a></p>
    </div>
  </div>
  <ol class="pf-dial" aria-label="More fresh episodes">{stations}</ol>
  <div class="pf-foot">
    <button type="button" class="btn pp-all pf-all" data-pp-all>{PLAY_SVG} Play all {len(lst)}</button>
    <a class="pf-more" href="{U("/podcasts/")}">All the podcasts</a>
    <p class="pf-note">Plays right here, streamed from each show's own feed so the show gets the listen.</p>
  </div>
</section>'''

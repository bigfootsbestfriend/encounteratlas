"""Podcast directory: /podcasts/, /podcasts/<topic>/, /podcasts/creature/<slug>/.

Data: data/podcasts.json and data/podcasts_episodes.json, written by collector/podcasts.py (weekly).
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _podplay
SHARE_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

# Mike's rule: no links to BFRO, NUFORC, MUFON or competing cryptid/encounter hubs, even as an RSS link.
BLOCKED = re.compile(r'bfro\.net|nuforc\.org|mufon\.com|cryptidcatchers?\.|cryptidatlas\.|enigmalabs\.', re.I)
from datetime import date

# Descriptions are shown as plain text, but Mike doesn't want these organisations named either: swap in neutral words.
_ORG_SUBS = [(re.compile(r'\b(?:mufon|nuforc)( investigator| field investigator)', re.I), r'UFO\1'),
             (re.compile(r'\b(?:bfro)( expeditions?| investigators?| researchers?)', re.I), r'Bigfoot\1'),
             (re.compile(r'\b(?:the )?(?:mufon|nuforc|mutual ufo network|national ufo reporting center)( \(case [\w-]+\))?', re.I), 'a UFO reporting group'),
             (re.compile(r'\b(?:the )?(?:bfro|bigfoot field researchers organi[sz]ation)', re.I), 'a Bigfoot research group')]


def scrub(t):
    for rx, rep in _ORG_SUBS:
        t = rx.sub(rep, t)
    return re.sub(r'\ba a\b', 'a', t)

# Optional per-topic <title> override ({year}, {n} = show count); other topics use the default title
TOPIC_TITLE = {'cryptids': 'Best cryptid podcasts {year}: {n} shows, ranked and updated weekly'}

# topic -> (page title noun, icon, colour class, intro, related creature categories or slugs)
TOPIC_META = {
    'bigfoot': ('Bigfoot', 'bigfoot', 'hominid',
                'Sasquatch encounters, wood knocks, field research and the people who swear they saw one. These are the shows Bigfoot fans keep coming back to.',
                ['hominid']),
    'dogman': ('Dogman', 'dogman', 'canid',
               'Upright canines in the Michigan woods, werewolf reports and the scariest campfire calls. Not for listening alone in a cabin.',
               ['canid']),
    'cryptids': ('cryptid', 'mothman', 'winged',
                 "Looking for a good cryptid podcast? These are the shows that spend real time on Mothman, lake monsters, the Jersey Devil and the rest, ranked so the best ones sit on top, and we re-check them against Apple Podcasts every week. If you're new to this, try the top three first and you'll know pretty fast which style you like.",
                 ['winged', 'aquatic', 'other', 'entity']),
    'ufo': ('UFO', 'saucer', 'ufo',
            'Sightings, abductions, whistleblowers and the UAP hearings. From weekly news roundups to deep dives on Roswell.',
            ['ufo']),
    'paranormal': ('paranormal', 'ghost', 'aquatic',
                   'Ghost stories, hauntings, high strangeness and listener-sent encounters that don\'t fit anywhere else.',
                   ['entity']),
    'military': ('military encounter', 'military', 'other',
                 'Soldiers, pilots and veterans telling what they saw on duty: UFOs on radar, things in the treeline, wartime ghosts.',
                 ['ufo-tic-tac', 'ufo-orbs', 'ufo-triangle', 'dogman', 'bigfoot']),
}
SHORT_MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def fmt_date(iso):
    try:
        y, m, d = (int(x) for x in iso[:10].split('-'))
        return f'{SHORT_MONTHS[m]} {d}, {y}'
    except (ValueError, AttributeError, IndexError):
        return ''


def days_between(a, b):
    try:
        return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days
    except (ValueError, TypeError):
        return 99999


def n_eps(n):
    """Apple caps trackCount at 1,000 and our lookup at 40 recent episodes."""
    return '1,000+' if n >= 1000 else f'{n:,}'


def n_recent(n):
    # Big numbers are estimated from posting rate, so don't pretend to precision
    return '40+' if n >= 40 else str(n)


def art(u, size):
    """Apple artwork URLs end in /600x600bb.jpg; ask for a smaller square when that's all we show."""
    return u.replace('600x600bb', f'{size}x{size}bb') if u else ''


def build(ctx):
    esc, url, icon = ctx.esc, ctx.url, ctx.icon
    p_shows = os.path.join(ctx.ROOT, 'data', 'podcasts.json')
    p_eps = os.path.join(ctx.ROOT, 'data', 'podcasts_episodes.json')
    if not os.path.exists(p_shows):
        return
    data = json.load(open(p_shows, encoding='utf-8'))
    shows = sorted(data['shows'], key=lambda s: -s['score'])
    updated = data.get('updated', '')
    topic_names = data.get('topics', {})
    eps_by = json.load(open(p_eps, encoding='utf-8')).get('creatures', {}) if os.path.exists(p_eps) else {}
    eps_by = {k: v for k, v in eps_by.items() if v and k in ctx.by_slug}
    by_topic = {t: [s for s in shows if t in s['topics']] for t in TOPIC_META}
    head = (f'<link rel="stylesheet" href="{url("/static/podcasts.css")}">')
    js = f'<script src="{url("/static/podcasts.js")}" defer></script>'

    def topic_chip(t, link=True):
        cls = f'ptag t-{t}'
        label = esc(topic_names.get(t, t))
        if link:
            return f'<a class="{cls}" href="{url("/podcasts/" + t + "/")}">{label}</a>'
        return f'<span class="{cls}">{label}</span>'

    def img(s_or_e, size, cls='', w=None):
        u = s_or_e.get('art', '')
        if not u:
            return f'<span class="pod-noart {cls}" aria-hidden="true">{icon("saucer")}</span>'
        return (f'<img class="{cls}" src="{esc(art(u, size))}" srcset="{esc(art(u, size))} 1x, {esc(art(u, min(size * 2, 600)))} 2x" '
                f'alt="" width="{w or size}" height="{w or size}" loading="lazy" decoding="async">')

    def latest_line(s):
        age = days_between(s['latest'], updated)
        fresh = ' fresh' if age <= 7 else ''
        if s.get('stale'):
            return f'<span class="pod-stale">Archive · last episode {esc(fmt_date(s["latest"]))}</span>'
        return f'<span class="pod-when{fresh}">New {esc(fmt_date(s["latest"]))}</span>'

    def links(s):
        rss = (f'<a class="pod-rss" href="{esc(s["feed"])}" rel="noopener nofollow" title="RSS feed for any podcast app">'
               f'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="19" r="2.5" fill="currentColor"/><path d="M3 11a10 10 0 0 1 10 10M3 4a17 17 0 0 1 17 17" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>RSS</a>') if s.get('feed') and not BLOCKED.search(s['feed']) else ''
        return (f'<p class="pod-links"><a class="pod-apple" href="{esc(s["apple"])}" rel="noopener">'
                f'<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.1v13.8a1 1 0 0 0 1.5.86l11-6.9a1 1 0 0 0 0-1.72l-11-6.9A1 1 0 0 0 8 5.1z"/></svg>'
                f'Apple Podcasts</a>{rss}</p>')

    def card(s):
        """Grid card for the hub directory."""
        names = f'{s["name"]} {s["publisher"]} {scrub(s.get("about", ""))[:200]}'.lower()
        tags = ''.join(topic_chip(t, False) for t in s['topics'])
        last = (f'<p class="pod-last"><span>Newest:</span> <a href="{esc(s["last_ep"]["url"])}" rel="noopener">'
                f'{esc(scrub(s["last_ep"]["title"]))}</a></p>') if s.get('last_ep') and s['last_ep'].get('title') else ''
        about = f'<p class="pod-about">{esc(scrub(s["about"]))}</p>' if s.get('about') else ''
        star = '<span class="pod-pick" title="Fan favourite">Fan favourite</span>' if s.get('notable') else ''
        return (f'<article class="pod" data-topics="{" ".join(s["topics"])}" data-names="{esc(names)}" '
                f'data-eps="{s["episodes"]}" data-latest="{esc(s["latest"])}" data-score="{s["score"]}" data-active="{s.get("recent30", 0)}">'
                f'<a class="pod-art" href="{esc(s["apple"])}" rel="noopener" tabindex="-1" aria-hidden="true">{img(s, 300)}{star}</a>'
                f'<div class="pod-body"><h3 class="pod-name"><a href="{esc(s["apple"])}" rel="noopener">{esc(s["name"])}</a></h3>'
                f'<p class="pod-pub">{esc(s["publisher"])}</p><p class="pod-tags">{tags}</p>'
                f'{about}'
                f'<p class="pod-meta"><span><strong>{n_eps(s["episodes"])}</strong> episodes</span>{latest_line(s)}'
                f'<span class="pod-genre">{esc(s["genre"])}</span></p>{last}{links(s)}</div></article>')

    def row(s, n):
        """Ranked row for topic pages."""
        tags = ''.join(topic_chip(t) for t in s['topics'])
        last = (f'<p class="pod-last"><span>Newest:</span> <a href="{esc(s["last_ep"]["url"])}" rel="noopener">'
                f'{esc(scrub(s["last_ep"]["title"]))}</a></p>') if s.get('last_ep') and s['last_ep'].get('title') else ''
        about = f'<p class="pod-about">{esc(scrub(s["about"]))}</p>' if s.get('about') else ''
        hot = f'<span class="pod-hot">{n_recent(s["recent30"])} new this month</span>' if s.get('recent30', 0) >= 4 else ''
        return (f'<li class="prow"><span class="prow-n">{n}</span><a class="prow-art" href="{esc(s["apple"])}" rel="noopener" '
                f'tabindex="-1" aria-hidden="true">{img(s, 300, "", 160)}</a><div class="prow-body">'
                f'<h3 class="pod-name"><a href="{esc(s["apple"])}" rel="noopener">{esc(s["name"])}</a></h3>'
                f'<p class="pod-pub">{esc(s["publisher"])} · {esc(s["genre"])}</p>{about}'
                f'<p class="pod-meta"><span><strong>{n_eps(s["episodes"])}</strong> episodes</span>{latest_line(s)}'
                f'{hot}</p>'
                f'<p class="pod-tags">{tags}</p>{last}{links(s)}</div></li>')

    def mini(s):
        return (f'<a class="pmini" href="{esc(s["apple"])}" rel="noopener">{img(s, 160, "", 64)}'
                f'<span><strong>{esc(s["name"])}</strong><small>{n_eps(s["episodes"])} episodes · new {esc(fmt_date(s["latest"]))}</small></span></a>')

    def creature_chip(slug):
        c = ctx.by_slug[slug]
        a = _podplay.art_thumb(ctx, slug)
        pic = f'<img class="pcrit-art" src="{a}" alt="" width="360" height="257" loading="lazy" decoding="async">' if a else ctx.badge(c, "sm")
        return (f'<a class="pcrit{" has-art" if a else ""}" href="{url("/podcasts/creature/" + slug + "/")}">{pic}'
                f'<span>{esc(c["name"])}<small>{len(eps_by[slug])} episodes</small></span></a>')

    def topic_tiles(current=None):
        out = ''
        for t, (noun, ico, col, _, _) in TOPIC_META.items():
            if not by_topic[t]:
                continue
            cur = ' aria-current="page"' if t == current else ''
            out += (f'<a class="ptile cat-{col}" href="{url("/podcasts/" + t + "/")}"{cur}>{icon(ico)}'
                    f'<span class="ptile-name">{esc(topic_names.get(t, t))}</span><span class="ptile-n">{len(by_topic[t])} shows</span></a>')
        return f'<nav class="ptiles" aria-label="Podcast topics">{out}</nav>'

    creature_order = [c['slug'] for c in ctx.creatures if c['slug'] in eps_by]
    _podplay.write_json(ctx)  # /data/podcast-play.json for the player (road trip "Listen along")
    pp_head = head + _podplay.head(ctx)

    # ---------- hub ----------
    active = sorted([s for s in shows if s.get('recent30', 0) > 0 and (s.get('notable') or s['episodes'] >= 100)], key=lambda s: (-s['recent30'], -s['score']))[:12]
    active_html = ''.join(
        f'<a class="pact" href="{esc(s["apple"])}" rel="noopener">{img(s, 300, "", 180)}'
        f'<span class="pact-n">{n_recent(s["recent30"])}<small>new</small></span>'
        f'<span class="pact-name">{esc(s["name"])}</span><span class="pact-sub">{n_recent(s["recent30"])} episode{"s" if s["recent30"] != 1 else ""} in 30 days</span></a>'
        for s in active)
    chips = ''.join(f'<button type="button" class="chip" data-filter="{t}" aria-pressed="false"><span class="dot t-{t}"></span>'
                    f'{esc(topic_names.get(t, t))} <span class="chip-n">{len(by_topic[t])}</span></button>'
                    for t in TOPIC_META if by_topic[t])
    total_eps = sum(s['episodes'] for s in shows)
    # "Play an episode now": newest playable creature episodes, one per creature, in the site's player
    play_now, seen = [], set()
    for slug, lst in _podplay.playable(ctx).items():
        if slug in _podplay.LIVING or not lst:
            continue
        e = max(lst, key=lambda x: x.get('d') or '')
        if e['t'] not in seen:
            seen.add(e['t']); play_now.append((e, slug))
    play_now = sorted(play_now, key=lambda x: x[0].get('d') or '', reverse=True)[:8]
    def pn_card(e, slug):
        a = _podplay.art_thumb(ctx, slug)
        pic = f'<img src="{a}" alt="" width="360" height="257" loading="lazy" decoding="async">' if a else '<span class="pn-noart"></span>'
        mins = f'<span class="pn-min">{e["m"]} min</span>' if e.get('m') else ''
        return (f'<li class="pn-card"><div class="pn-art">{pic}{mins}<button type="button" class="pn-share" data-pp-share aria-label="Save or share this episode">{SHARE_SVG}Save</button>{_podplay.play_button(e, "pp-btn pp-round pn-play", "")}</div>'
                f'<div class="pn-body"><a class="pn-crit" href="{url("/podcasts/creature/" + slug + "/")}">{esc(ctx.by_slug[slug]["name"])}</a>'
                f'<b class="pn-t">{esc(e["t"])}</b><small>{esc(e["s"])}</small></div></li>')
    play_html = ''.join(pn_card(e, slug) for e, slug in play_now)
    # Episode roulette: every playable creature, for the "spin" picker (podcasts.js loads /data/podcast-play.json on use)
    spin_names = {k: ctx.by_slug[k]['name'] for k in _podplay.playable(ctx) if k not in _podplay.LIVING}
    spin_art = [k for k in spin_names if _podplay.art_thumb(ctx, k)]
    spin_cfg = esc(json.dumps({'names': spin_names, 'art': spin_art, 'thumb': url('/static/cards/thumb/'),
                               'data': url('/data/podcast-play.json'), 'crit': url('/podcasts/creature/')}, separators=(',', ':')))
    body = f'''
<section class="band band-dark pod-head">
  <div class="wrap">
    <p class="crumb">Podcasts</p>
    <h1>Podcasts for the strange stuff</h1>
    <p class="lede">{len(shows)} shows about Bigfoot, Dogman, cryptids, UFOs and the paranormal, with {total_eps:,} episodes between them. We check every one each week, so dead shows drop off and new ones show up.</p>
    {topic_tiles()}
  </div>
</section>
{f"""<section class="band band-mist" aria-labelledby="pn-h">
  <div class="wrap"><div class="pp-along" data-pp-list>
    <h2 id="pn-h">Play an episode now</h2>
    <p>Fresh episodes about Mothman, Bigfoot, Dogman and the rest. They play right here (and keep going with your screen off in the app), streamed from each show's own feed so the show gets the listen.</p>
    <p><button type="button" class="btn pp-all" data-pp-all>{_podplay.PLAY_SVG} Play all {len(play_now)}</button></p>
    <ol class="pn-grid">{play_html}</ol>
  </div></div>
</section>""" if play_now else ''}
{f"""<section class="band band-dark pod-spin" aria-labelledby="spin-h" data-spin="{spin_cfg}">
  <div class="wrap spin-wrap">
    <div class="spin-intro">
      <h2 id="spin-h">Can't decide? Spin the dial</h2>
      <p>Pick how long you've got and we'll pull a random episode about one of {len(spin_names)} creatures. Don't like it? Spin again.</p>
      <div class="spin-len" role="group" aria-label="How long have you got?">
        <button type="button" class="chip" data-len="any" aria-pressed="true">Any length</button>
        <button type="button" class="chip" data-len="short" aria-pressed="false">Under 30 min</button>
        <button type="button" class="chip" data-len="mid" aria-pressed="false">30 to 60 min</button>
        <button type="button" class="chip" data-len="long" aria-pressed="false">Over an hour</button>
      </div>
      <p><button type="button" class="btn spin-go"><span class="spin-dial" aria-hidden="true"></span>Spin for an episode</button></p>
    </div>
    <div class="spin-out" data-pp-list aria-live="polite"><p class="spin-hint">Your episode shows up here.</p></div>
  </div>
</section>""" if spin_names else ''}
{f"""<section class="band band-dark pod-active-band" aria-labelledby="act-h">
  <div class="wrap">
    <h2 id="act-h"><span class="pulse" aria-hidden="true"></span>Most active this month</h2>
    <p class="muted">Shows that put out the most new episodes in the last 30 days.</p>
    <div class="pact-row">{active_html}</div>
  </div>
</section>""" if active else ''}
<div class="band band-mist"><div class="wrap">
  <h2 id="all">The full directory</h2>
  <div class="pod-tools">
    <div class="search-row light">
      <label class="visually-hidden" for="pq">Search podcasts</label>
      <input id="pq" type="search" placeholder="Search shows: skinwalker, Michigan, Ohio, abduction" autocomplete="off">
    </div>
    <label class="pod-sort">Sort <select id="psort">
      <option value="score">Recommended</option><option value="latest">Newest episode</option>
      <option value="eps">Most episodes</option><option value="active">Busiest this month</option><option value="az">A to Z</option>
    </select></label>
  </div>
  <div class="chips light" role="group" aria-label="Filter by topic">{chips}</div>
  <p class="pod-count" aria-live="polite"><span id="pcount">{len(shows)}</span> shows</p>
  <div class="pod-grid">{''.join(card(s) for s in shows)}</div>
  <p class="empty" hidden>No show matches that. Try a broader word, or clear the topic filter.</p>
  <p class="small muted">Show details come from Apple Podcasts and each show's own feed, updated {esc(fmt_date(updated))}. Every show has an RSS link you can paste into any podcast app. Know a show we missed? <a href="{url('/contact/')}">Tell us</a>.</p>
  <p class="md-listen">Run out of episodes? <a href="https://www.amazon.com/hz/audible/mlp?tag=encountersatlas-20" rel="sponsored nofollow noopener" target="_blank">Try Audible free</a> for cryptid and UFO audiobooks. <a class="md-aff" href="{url('/privacy/')}#affiliate">(affiliate link)</a></p>
</div></div>
{f"""<section class="band band-dark"><div class="wrap">
  <h2>Episodes about one creature</h2>
  <p class="lede">Only want the Mothman episodes? We pulled the best episodes about each creature from across every podcast.</p>
  <div class="pcrit-grid">{''.join(creature_chip(s) for s in creature_order)}</div>
</div></section>""" if creature_order else ''}
{js}'''
    ctx.write('/podcasts/', ctx.page('/podcasts/', 'Bigfoot, UFO and paranormal podcasts: the directory', body,
                                     f'{len(shows)} podcasts about Bigfoot, Dogman, cryptids, UFOs and the paranormal, checked weekly. '
                                     f'Filter by topic, see who posted this month, and find episodes about any creature.',
                                     head_extra=head + _podplay.head(ctx)))

    # ---------- topic pages ----------
    for t, (noun, ico, col, intro, rel) in TOPIC_META.items():
        lst = by_topic[t]
        if not lst:
            continue
        live = [s for s in lst if not s.get('stale')]
        top, rest = live[:25], live[25:] + [s for s in lst if s.get('stale')]
        rel_slugs = [s for s in creature_order if s in rel or ctx.by_slug[s]['cat'] in rel]
        rel_html = (f'<h2>Episodes about one creature</h2><div class="pcrit-grid">{"".join(creature_chip(s) for s in rel_slugs)}</div>'
                    if rel_slugs else '')
        busiest = max(live, key=lambda s: s.get('recent30', 0)) if live else None
        busy_line = (f' The busiest right now is <strong>{esc(busiest["name"])}</strong>, with {n_recent(busiest["recent30"])} new episodes in the last month.'
                     if busiest and busiest.get('recent30', 0) >= 3 else '')
        title_noun = noun if noun[0].isupper() else noun
        h1 = f'Best {title_noun} podcasts'
        rest_html = (f'<h2>More {esc(noun)} shows</h2><div class="pmini-grid">{"".join(mini(s) for s in rest)}</div>' if rest else '')
        body = f'''
<section class="band band-dark pod-head topic-head cat-{col}">
  <div class="wrap">
    <p class="crumb"><a href="{url('/podcasts/')}">Podcasts</a> / {esc(topic_names.get(t, t))}</p>
    <div class="topic-title"><span class="badge badge-md cat-{col}">{icon(ico)}</span><h1>{esc(h1)}</h1></div>
    <p class="lede">{esc(intro)}</p>
    <p class="muted">{len(lst)} shows, ranked by how much they cover {esc({'bigfoot': 'Bigfoot', 'dogman': 'Dogman', 'cryptids': 'cryptids', 'ufo': 'UFOs', 'paranormal': 'the paranormal', 'military': 'military encounters'}[t])}, how often they post and how long they've been going.{busy_line}</p>
    {topic_tiles(t)}
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <ol class="prow-list">{''.join(row(s, i + 1) for i, s in enumerate(top))}</ol>
  {rest_html}
  {rel_html}
  <p class="small muted">Updated {esc(fmt_date(updated))} from Apple Podcasts. <a href="{url('/podcasts/')}">See all {len(shows)} shows</a>.</p>
</div></div>'''
        ctx.write(f'/podcasts/{t}/', ctx.page(f'/podcasts/{t}/', TOPIC_TITLE[t].format(year=date.today().year, n=len(lst)) if t in TOPIC_TITLE else f'{h1} ({len(lst)} shows, updated weekly)', body,
                                              f'The best {noun} podcasts, ranked: {", ".join(s["name"] for s in top[:4])} and {len(lst) - 4} more, with episode counts and the latest episodes.',
                                              head_extra=head))

    # ---------- creature episode pages ----------
    def play(e, sh):
        # Play in the site's player, streamed from the show's own feed (living traditions stay info-only)
        if not e.get('audio') or slug in _podplay.LIVING:
            return ''
        return (_podplay.play_button(dict(_podplay.entry(e, sh['apple'] if sh else ''), c=slug), 'pod-play')
                + f'<button type="button" class="pp-share-inline" data-pp-share aria-label="Save or share this episode">{SHARE_SVG}Save or share</button>')

    for slug in creature_order:
        c, eps = ctx.by_slug[slug], eps_by[slug]
        show_by_id = {s['id']: s for s in shows}
        items = ''
        for e in eps:
            sh = show_by_id.get(e['show_id'])
            show_link = (f'<a href="{esc(sh["apple"])}" rel="noopener">{esc(e["show"])}</a>' if sh else esc(e['show']))
            about = f'<p class="pep-about">{esc(scrub(e["about"]))}</p>' if e.get('about') else ''
            meta = ' · '.join(x for x in [fmt_date(e['date']), f'{e["mins"]} min' if e.get('mins') else ''] if x)
            items += (f'<li class="pep"><a class="pep-art" href="{esc(e["url"])}" rel="noopener" tabindex="-1" aria-hidden="true">'
                      f'{img(e, 160, "", 96)}</a><div class="pep-body"><h3><a href="{esc(e["url"])}" rel="noopener">{esc(scrub(e["title"]))}</a></h3>'
                      f'<p class="pep-show">{show_link} <span class="muted">{esc(meta)}</span></p>'
                      f'{about}'
                      f'<p class="pod-links">{play(e, sh)}<a class="pod-apple" href="{esc(e["url"])}" rel="noopener">'
                      f'<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.1v13.8a1 1 0 0 0 1.5.86l11-6.9a1 1 0 0 0 0-1.72l-11-6.9A1 1 0 0 0 8 5.1z"/></svg>'
                      f'Listen</a></p></div></li>')
        # shows on the matching topic, for "keep listening"
        topic_for = {'hominid': 'bigfoot', 'canid': 'dogman', 'ufo': 'ufo'}.get(c['cat'], 'cryptids')
        keep = [s for s in by_topic.get(topic_for, []) if not s.get('stale')][:6]
        keep_html = (f'<h2>Shows that cover this beat</h2><div class="pmini-grid">{"".join(mini(s) for s in keep)}</div>'
                     f'<p><a href="{url("/podcasts/" + topic_for + "/")}">Best {esc(TOPIC_META[topic_for][0])} podcasts</a></p>' if keep else '')
        others = ''.join(creature_chip(s) for s in creature_order if s != slug and ctx.by_slug[s]['cat'] == c['cat'])
        aka = f'<p class="aka-line">Also called {esc(", ".join(c["aliases"][:3]))}</p>' if c['aliases'] else ''
        body = f'''
<section class="band band-dark creature-head pod-head cat-{c['cat']}">
  <div class="wrap creature-head-in">
    {ctx.badge(c, 'xl')}
    <div>
      <p class="crumb"><a href="{url('/podcasts/')}">Podcasts</a> / Episodes by creature</p>
      <h1>Podcast episodes about {esc(c['name'])}</h1>
      {aka}
      <p class="lede">The {len(eps)} best episode{'s' if len(eps) != 1 else ''} we found about {esc(c['name'])}, from {len({e['show_id'] for e in eps})} different show{'s' if len({e['show_id'] for e in eps}) != 1 else ''}. Recent and well-loved episodes first.</p>
      <p><a class="btn btn-ghost" href="{url('/creatures/' + slug + '/')}">Read the {esc(c['name'])} file</a></p>
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <ol class="pep-list" data-pp-list>{items}</ol>
  {keep_html}
  {f'<h2>More creatures like this</h2><div class="pcrit-grid light">{others}</div>' if others else ''}
  <p class="small muted">Episodes found through Apple Podcasts search, updated {esc(fmt_date(updated))}. {"Play streams the episode straight from the show's own feed, so the show gets the listen. " if slug not in _podplay.LIVING and any(e.get("audio") for e in eps) else ""}Listen opens the episode on Apple Podcasts.</p>
</div></div>'''
        ctx.write(f'/podcasts/creature/{slug}/', ctx.page(
            f'/podcasts/creature/{slug}/', f'Podcast episodes about {c["name"]}', body,
            f'The best podcast episodes about {c["name"]}' + (f' ({", ".join(c["aliases"][:2])})' if c['aliases'] else '') +
            f': {len(eps)} picks from shows like {", ".join(dict.fromkeys(e["show"] for e in eps[:3]))}.', head_extra=pp_head))

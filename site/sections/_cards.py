"""Collector cards page (/cards/) and /data/cards.json. Called from z_road_trip.py, which works out the cards.

Every card is a trading card (5:7) drawn in CSS (static/cards.css): the front has the creature on a dusk sky in its
category colour, the back has the short field notes and where to check in. static/cards.js flips them, runs the
shine on Unique cards and the reveal when a new card is collected. The back is rendered here too, so the page is
complete HTML for search engines. cards.json carries the same back data for the reveal on other pages and the
nearest-spot line.

The leading underscore keeps build.py from loading this file as a section of its own."""
import datetime, json, os, re

RANK = {'Common': ('common', '●'), 'Uncommon': ('uncommon', '◆'), 'Unique': ('unique', '★')}
LORE = re.compile(r'\b(tradition|legend|lore|belief|indigenous|sacred|tales|folklore|myth)', re.I)
YEAR = re.compile(r'\b(\d{1,2}(?:st|nd|rd|th)(?=[ -]centur)|1\d{3}s?|20\d{2}s?)\b|\((\d{3})\)')
FT = re.compile(r'(\d+(?:\.\d+)?)(?: to (\d+(?:\.\d+)?))? ?(?:ft|feet)\b')


def first_short(t):
    """'Indigenous names ... long predate the 1958 headline' -> 'Old lore; 1958'. Short text is kept as it is."""
    t = (t or '').strip()
    if len(t) <= 26:
        return t
    m = YEAR.search(t)
    if not m:
        return t
    y = m.group(1) or m.group(2) + ' AD'
    if y[-2:] in ('st', 'nd', 'rd', 'th'):
        y += ' century'
    return f'Old lore; {y}' if LORE.search(t) else y


def metric(t):
    """'7 to 9 ft' -> '2.1 to 2.7 m (7 to 9 ft)': metres first for everyone outside the US."""
    def m(v):
        x = float(v) * 0.3048
        return f'{round(x * 100)} cm' if x < 1 else f'{x:.1f}'.rstrip('0').rstrip('.') + ' m'
    def rep(g):
        a, b = g.group(1), g.group(2)
        if b:
            lo, hi = m(a), m(b)
            if lo[-2:] == hi[-2:]:
                lo = lo.rsplit(' ', 1)[0]
            return f'{lo} to {hi} ({a} to {b} ft)'
        return f'{m(a)} ({a} ft)'
    return FT.sub(rep, t or '')


def spot_list(sp):
    seen, out = set(), []
    for a, o, name in sp:
        if name not in seen:
            seen.add(name)
            out.append([a, o, name])
    return out


def build_cards(ctx, cards, hunts, checkin_km):
    E, U = ctx.esc, ctx.url
    today = datetime.date.today().isoformat()
    order = {k: i for i, k in enumerate(ctx.CATS)}
    allc = sorted(cards, key=lambda s: (order.get(cards[s]['c'], 99), cards[s]['n']))
    total = len(allc)
    live = [h for h in hunts if h['start'] <= today <= h['end'] and h['creatures']]
    in_hunt = {s for h in live for s in h['creatures']}

    info = {}
    for i, slug in enumerate(allc, 1):
        c, cr = cards[slug], ctx.by_slug[slug]
        info[slug] = {'no': i, 'n': c['n'], 'c': c['c'], 'k': ctx.CATS.get(c['c'], ('', ''))[0], 'r': c['r'], 'art': c['art'],
                      'u': U('/creatures/' + slug + '/'), 's': cr.get('summary', ''), 'first': first_short(cr.get('first')),
                      'turf': cr.get('region', ''), 'size': metric(cr.get('size', '')),
                      'hab': cr.get('habitat', ''), 'signs': (cr.get('signs') or [])[:2], 'spots': spot_list(c['spots'])}
    with open(os.path.join(ctx.OUT, 'data', 'cards.json'), 'w') as f:
        json.dump({'total': total, 'checkin_km': checkin_km, 'hunt': sorted(in_hunt), 'cards': info}, f, separators=(',', ':'), ensure_ascii=False)

    def card(slug, hunt=False):
        d, cr = info[slug], ctx.by_slug[slug]
        rk, mark = RANK[d['r']]
        no = f'#{d["no"]:03d} / {total}'
        art = (f'<img src="{d["art"]}" alt="" width="240" height="240" loading="lazy" decoding="async">' if d['art']
               else ctx.badge(cr, 'lg'))
        sp = d['spots']
        n = len(sp)
        spots = ''.join(f'<li>{E(s[2])}</li>' for s in sp[:4]) + (f'<li class="tc-moresp">and {n - 4} more</li>' if n > 4 else '')
        signs = ''.join(f'<li>{E(s)}</li>' for s in d['signs'])
        places = f'{n} real place{"s" if n != 1 else ""}'
        return f'''<li class="tc tc-{rk} cat-{d["c"]}{" tc-hunt" if hunt else ""}" data-card="{slug}" data-r="{rk}">
<div class="tc-card"><div class="tc-tilt"><div class="tc-in">
<div class="tc-face tc-front">
<div class="tc-name"><h3><span class="tc-nm">{E(d["n"])}</span></h3><span class="tc-mark" title="{d["r"]}" aria-hidden="true">{mark}</span></div>
<div class="tc-win">{art}<span class="tc-holo" aria-hidden="true"></span></div>
<div class="tc-strip"><span class="tc-kind">{E(d["k"])}</span><span class="tc-no">{no}</span></div>
<p class="tc-sum">{E(d["s"])}</p>
<p class="tc-foot"><span class="tc-r">{d["r"]}</span><span class="tc-got">{n} place{"s" if n != 1 else ""}</span></p>
<span class="tc-fx" aria-hidden="true"></span>
</div>
<div class="tc-face tc-back">
<div class="tc-bhead"><span class="tc-bn">{E(d["n"])}</span><span class="tc-bno">{no}</span></div>
<dl class="tc-stats">
<div><dt>First seen</dt><dd title="{E(cr.get("first", ""))}">{E(d["first"])}</dd></div>
<div><dt>Home turf</dt><dd>{E(d["turf"])}</dd></div>
<div><dt>Size</dt><dd>{E(d["size"])}</dd></div>
<div><dt>Habitat</dt><dd>{E(d["hab"])}</dd></div>
<div class="tc-signs"><dt>Signs</dt><dd><ul>{signs}</ul></dd></div>
</dl>
<div class="tc-where"><p class="tc-wh"><span class="tc-wh-lock">Where to find it</span><span class="tc-wh-have">Check in at {places}</span></p>
<p class="tc-near" hidden></p><ol class="tc-spots">{spots}</ol></div>
</div>
</div></div>
<button type="button" class="tc-flip" aria-pressed="false"><span class="visually-hidden">Flip the {E(d["n"])} card</span></button>
<a class="tc-more" href="{d["u"]}">Read the file</a>
</div></li>'''

    hunt_html = ''
    for h in live:
        end = datetime.date.fromisoformat(h['end']).strftime('%B %-d')
        hunt_html += (f'<section class="cc-huntbox tc-huntbox" data-hunt="{h["slug"]}"><h2>{E(h["title"])}</h2><p>{E(h["blurb"])}</p>'
                      f'<p class="cc-prog" data-of="{len(h["creatures"])}">0 of {len(h["creatures"])} collected</p>'
                      f'<ul class="tc-grid">{"".join(card(s, True) for s in h["creatures"])}</ul></section>')

    tiers = [('common', 'Common'), ('uncommon', 'Uncommon'), ('unique', 'Unique')]
    counts = {k: sum(1 for s in allc if RANK[cards[s]['r']][0] == k) for k, _ in tiers}
    tally = ''.join(f'<li class="tc-t-{k}"><span class="tc-tmark" aria-hidden="true">{RANK[lab][1]}</span> {lab} <b data-tally="{k}">0</b> of {counts[k]}</li>'
                    for k, lab in tiers)
    filters = [('all', 'All'), ('have', 'Collected'), ('unique', 'Unique')] + ([('hunt', 'Hunt')] if in_hunt else [])
    fbtn = ''.join(f'<button type="button" data-f="{k}" aria-pressed="{"true" if k == "all" else "false"}">{lab}</button>' for k, lab in filters)
    hunt_title = live[0]['title'] if live else ''
    body = f'''
<section class="band band-dark rt-hero"><div class="wrap">
  <h1>Collector cards</h1>
  <p class="lede">{total} creatures have a card, and the only way to get one is to actually go there. Stand within {checkin_km} km of a real sighting spot or a place tied to that creature, tap "I'm here", and it's yours.</p>
  <p class="rt-actions"><button type="button" class="btn" id="cc-here">I'm here</button> <a class="btn btn-ghost" href="{U('/road-trip/')}">Plan a trip</a></p>
  <p id="cc-status" class="rt-status" aria-live="polite"></p>
  <p class="cc-total" id="cc-total" hidden></p>
</div></section>
<div class="band band-dark tc-band"><div class="wrap">
  {hunt_html}
  <h2>Every card</h2>
  <p class="tc-note">Tap a card to flip it. Unique cards are the shiny ones because there's exactly one spot on the planet to get them. Uncommon cards have two or three spots and Common cards have four or more. Your collection stays on this device (no account), so don't clear your browser data if you care about it.</p>
  <ul class="tc-tally" aria-label="Your collection by rarity">{tally}</ul>
  <div class="tc-filters" role="group" aria-label="Show cards">{fbtn}<button type="button" class="tc-tiltbtn" hidden aria-pressed="false">Tilt to shine</button></div>
  <p class="tc-shown" id="tc-shown" aria-live="polite"></p>
  <ul class="tc-grid" id="tc-all">{''.join(card(s, s in in_hunt) for s in allc)}</ul>
  <p class="tc-empty" id="tc-empty" hidden>Nothing here yet. Your first card is out there somewhere, probably near a lake.</p>
</div></div>
<script type="application/json" id="cc-config">{json.dumps({"data": U("/data/roadtrip.json"), "cards": U("/data/cards.json")})}</script><script src="{U('/static/cards.js')}" defer></script>'''
    ctx.write('/cards/', ctx.page('/cards/', 'Cryptid collector cards: collect them on location', body,
              f'{total} cryptid and monster trading cards you can only collect by visiting real sighting spots and places, including {counts["unique"]} shiny Unique cards'
              f'{", plus the " + hunt_title + " set" if hunt_title else ""}.',
              head_extra=f'<link rel="stylesheet" href="{U("/static/roadtrip.css")}"><link rel="stylesheet" href="{U("/static/cards.css")}">'))
    return info

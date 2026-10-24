"""Mystery of the day: /mystery-of-the-day/. One case a day, picked from the mysteries (data/mysteries.json), the
close encounters (data/close_encounters.json) and the famous UFO cases (data/famous_cases.json), each of which has
its own write-up page. Readers vote "What do you think it was?" (vote.js, item 'm:<slug>'); today's case keeps its
explanation and results back, yesterday's shows both, and the last 14 days are listed below.

Schedule: data/motd_schedule.json holds eras {from: 'YYYY-MM-DD', order: [slugs]}. A day is the UTC day number; the
case for a day is order[(day - from) % len] of the latest era that has started. The first order is a one-off
shuffle (sorted by a hash of the slug). When the case list changes, the build adds a new era starting tomorrow:
new cases first, then the old order carrying on where it was, so past days never change. Commit that file
together with worker/src/motd_items.js (written here too); the Worker needs a deploy to accept new cases.

Left out: vanishings and deaths (Dyatlov Pass, Nahanni, Roanoke, Mary Celeste...), where a real/hoax vote would be
in poor taste, and LIVING_TRADITIONS creature art. Summaries and verdicts are the site's own text, nothing new.

The page is indexable with a stable title. The HTML shows the build day's case; static/motd.js swaps in the
right one if the visitor's UTC day differs (it fetches /data/motd.json only then) and loads the vote counts.
"""
import datetime, hashlib, json, os

API = os.environ.get('EA_API', 'https://api.encounteratlas.com').rstrip('/')
SITEKEY = os.environ.get('TURNSTILE_SITEKEY', '1x00000000000000000000AA')
PATH = '/mystery-of-the-day/'
START = '2026-10-24'          # first day on the schedule (launch day)
ARCHIVE = 14
MON = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
SKIP = {'dyatlov-pass', 'nahanni-headless-valley'}  # plus every mystery of type 'vanishing'
LIVING = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
          'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}  # = build.py LIVING_TRADITIONS
KINDS = {'my': ('Mystery', '/mysteries/'), 'ce': ('Close encounter', '/encounters/'), 'uf': ('UFO case', '/ufo/cases/')}
STATUS = {'unexplained': 'Unexplained', 'disputed': 'Disputed', 'solved': 'Mostly solved', 'legend': 'Legend',
          'explained': 'Explained', 'hoax': 'Hoax'}
POSTER_SKY = {'hominid': ('#E3A649', '#B5532F'), 'canid': ('#3B4C6B', '#1B2A3A'), 'winged': ('#3B4C6B', '#1B2A3A'),
              'aquatic': ('#E8B04A', '#C8693A'), 'entity': ('#3B4C6B', '#1B2A3A'), 'ufo': ('#2E3E5C', '#141E2E'),
              'fae': ('#C97B9A', '#4A2E4F'), 'other': ('#E3A649', '#B5532F')}
EPOCH = datetime.date(1970, 1, 1)


def dnum(d):
    return (d - EPOCH).days


def ddate(n):
    return EPOCH + datetime.timedelta(days=n)


def dateline(d):
    p = d.split('-')
    if len(p) == 3:
        return f'{MON[int(p[1])]} {int(p[2])}, {p[0]}'
    if len(p) == 2:
        return f'{MON[int(p[1])]} {p[0]}'
    return p[0]


def shuffled(slugs):
    return sorted(slugs, key=lambda s: hashlib.sha256(('ea-motd|' + s).encode()).hexdigest())


def load(ctx, fn):
    p = os.path.join(ctx.ROOT, 'data', fn)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []


def gather(ctx):
    """Every eligible case as a small dict (the same shape goes into /data/motd.json for the browser)."""
    photos = load(ctx, 'mystery_photos.json') or {}
    out = {}
    for kind, fn in (('my', 'mysteries.json'), ('ce', 'close_encounters.json'), ('uf', 'famous_cases.json')):
        for x in load(ctx, fn):
            if x['slug'] in SKIP or x.get('type') == 'vanishing' or x['slug'] in out:
                continue
            art = None
            if kind == 'my' and photos.get(x['slug']):
                art = {'img': photos[x['slug']][0]['src']}
            else:
                crs = [s for s in x.get('creatures', []) if s in ctx.by_slug and s not in LIVING and ctx.by_slug[s].get('art')]
                if not crs and kind == 'ce':
                    crs = ['grey-aliens'] if ctx.by_slug.get('grey-aliens', {}).get('art') else []
                if crs:
                    c = ctx.by_slug[crs[0]]
                    art = {'art': c['art'], 'cat': c['cat']}
            nd = lambda t: (t or '').replace('\u2013', '-').replace('\u2014', ', ')  # no en/em dashes in this page's copy
            out[x['slug']] = {'k': kind, 'n': nd(x['name']), 'd': dateline(x['date']), 'p': nd(x['place']), 's': nd(x['summary']),
                              'st': x['status'], 'sn': nd(x.get('status_note')), 'u': KINDS[kind][1] + x['slug'] + '/', 'a': art}
    return out


def schedule(ctx, slugs, today):
    """Load data/motd_schedule.json, add an era starting tomorrow if the case list changed, save it."""
    path = os.path.join(ctx.ROOT, 'data', 'motd_schedule.json')
    sched = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'eras': []}
    eras = sched['eras']
    want = set(slugs)
    tomorrow = today + 1
    if not eras:
        eras.append({'from': START, 'order': shuffled(want)})
    elif set(eras[-1]['order']) != want:
        if dnum(datetime.date.fromisoformat(eras[-1]['from'])) >= tomorrow and len(eras) > 1:
            eras.pop()  # an era that hasn't started yet: rebuild it from the one before
        last = eras[-1]
        lf = dnum(datetime.date.fromisoformat(last['from']))
        k = (tomorrow - lf) % len(last['order']) if tomorrow > lf else 0
        rot = last['order'][k:] + last['order'][:k]
        order = shuffled(want - set(last['order'])) + [s for s in rot if s in want]
        if set(order) != set(last['order']):
            eras.append({'from': ddate(tomorrow).isoformat(), 'order': order})
        print(f'motd: case list changed, new era from {ddate(tomorrow)}: commit data/motd_schedule.json and '
              'worker/src/motd_items.js, then deploy the Worker')
    text = json.dumps(sched, indent=1, ensure_ascii=False) + '\n'
    if not os.path.exists(path) or open(path, encoding='utf-8').read() != text:
        open(path, 'w', encoding='utf-8').write(text)
    eras_n = [{'from': dnum(datetime.date.fromisoformat(e['from'])), 'order': e['order']} for e in eras]
    wtext = ('// Written by site/sections/motd.py from data/motd_schedule.json. Do not edit by hand.\n'
             '// from = UTC day number (Unix ms / 86400000). Deploy the Worker after this changes.\n'
             'export const MOTD = ' + json.dumps({'eras': eras_n}, separators=(',', ':')) + ';\n')
    wpath = os.path.join(ctx.ROOT, 'worker', 'src', 'motd_items.js')
    if os.path.isdir(os.path.dirname(wpath)) and (not os.path.exists(wpath) or open(wpath, encoding='utf-8').read() != wtext):
        open(wpath, 'w', encoding='utf-8').write(wtext)
    return eras_n


def pick(eras, day):
    era = None
    for e in eras:
        if e['from'] <= day:
            era = e
    if not era or not era['order']:
        return None
    return era['order'][(day - era['from']) % len(era['order'])]


def art_html(ctx, a, cls, idp):
    """Poster frame with the creature silhouette (same as the creature pages), the mystery's photo, or a plain mark."""
    u = ctx.url
    if a and a.get('img'):
        return f'<span class="{cls} motd-photo"><img src="{u(a["img"])}" alt="" width="320" height="320" loading="lazy"></span>'
    if a and a.get('art'):
        sa, sb = POSTER_SKY.get(a['cat'], POSTER_SKY['other'])
        sid = 'motd-' + idp
        wet = a['cat'] == 'aquatic'
        ground = ('<rect y="160" width="200" height="40" fill="#2B4A55"/>' if wet else
                  '<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="#1E3A2F"/>')
        return (f'<span class="{cls}" aria-hidden="true"><svg viewBox="0 0 200 200"><defs><linearGradient id="{sid}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{sa}"/><stop offset="1" stop-color="{sb}"/></linearGradient>'
                f'<clipPath id="c{sid}"><rect x="6" y="6" width="188" height="188" rx="10"/></clipPath></defs>'
                f'<g clip-path="url(#c{sid})"><rect width="200" height="200" fill="url(#{sid})"/><circle cx="150" cy="52" r="24" fill="#F3E3B8" opacity=".9"/>'
                f'<path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="#5E4A3A" opacity=".5"/>{ground}'
                f'<image href="{u("/static/" + a["art"] + ".svg")}" x="22" y="{34 if wet else 26}" width="160" height="160"/></g>'
                f'<rect x="6" y="6" width="188" height="188" rx="10" fill="none" stroke="#F3E3B8" stroke-width="4"/></svg></span>')
    return f'<span class="{cls} motd-blank" aria-hidden="true">?</span>'


def build(ctx):
    e, u = ctx.esc, ctx.url
    cases = gather(ctx)
    if not cases:
        return
    today = dnum(datetime.datetime.now(datetime.timezone.utc).date())
    eras = schedule(ctx, list(cases), today)

    os.makedirs(os.path.join(ctx.OUT, 'data'), exist_ok=True)
    with open(os.path.join(ctx.OUT, 'data', 'motd.json'), 'w', encoding='utf-8') as f:
        json.dump({'eras': eras, 'cases': cases}, f, separators=(',', ':'), ensure_ascii=False)

    def kind_pill(c):
        return f'<span class="motd-kind k-{c["k"]}">{KINDS[c["k"]][0]}</span>'

    def status_pill(c):
        return f'<span class="motd-st st-{c["st"]}">{STATUS.get(c["st"], c["st"].title())}</span>'

    t_slug = pick(eras, today)
    y_slug = pick(eras, today - 1)
    t = cases.get(t_slug)
    y = cases.get(y_slug)

    today_html = ''
    if t:
        today_html = f'''<article class="motd-card motd-today" id="motd-today" data-slug="{t_slug}">
  {art_html(ctx, t['a'], 'motd-art', 't')}
  <div class="motd-txt">
    <p class="motd-meta">{kind_pill(t)} <span data-f="d">{e(t['d'])}</span></p>
    <p class="motd-place" data-f="p">{e(t['p'])}</p>
    <h2 data-f="n">{e(t['n'])}</h2>
    <p class="motd-sum" data-f="s">{e(t['s'])}</p>
  </div>
  <div class="motd-vote" data-motd-vote="m:{t_slug}">
    <p class="vote-h"><strong>What do you think it was?</strong></p>
    <p class="motd-noscript">Voting needs JavaScript and a free account. You sign in with just your email (we send you a link, no password), and it's one vote per person so nobody can stuff the box.</p>
  </div>
  <p class="motd-key"><b>Real</b> means you think something truly unexplained happened. <b>Hoax</b> means somebody made it up. <b>Misidentified</b> means it was something ordinary that fooled people.</p>
  <p class="motd-spoil">Can't wait until tomorrow? <a data-f="u" href="{u(t['u'])}">Read the full write-up</a> (spoilers, obviously).</p>
</article>'''

    yest_html = ''
    if y:
        yest_html = f'''<section class="motd-yest" id="motd-yest" data-slug="{y_slug}" aria-labelledby="motd-yh">
  <h2 id="motd-yh">Yesterday's case, revealed</h2>
  <div class="motd-card motd-small">
    {art_html(ctx, y['a'], 'motd-art motd-art-sm', 'y')}
    <div class="motd-txt">
      <p class="motd-meta">{kind_pill(y)} <span data-f="d">{e(y['d'])}</span></p>
    <p class="motd-place" data-f="p">{e(y['p'])}</p>
      <h3 data-f="n">{e(y['n'])}</h3>
      <p class="motd-sum" data-f="s">{e(y['s'])}</p>
    </div>
    <div class="motd-verdict">
      <h4>What the evidence says</h4>
      <p>{status_pill(y)} <span data-f="sn">{e(y['sn'])}</span></p>
      <h4>How readers voted</h4>
      <div class="motd-results" data-motd-results="m:{y_slug}" aria-live="polite"><p class="motd-wait">Vote results load here once 10 people have voted.</p></div>
      <p class="motd-more"><a class="btn btn-sm" data-f="u" href="{u(y['u'])}">The full write-up, with what the evidence says</a></p>
    </div>
  </div>
</section>'''

    rows = []
    for i in range(1, ARCHIVE + 1):
        d = today - i
        s = pick(eras, d)
        c = cases.get(s)
        if not c:
            continue
        dd = ddate(d)
        rows.append(f'<li data-slug="{s}"><span class="motd-day">{MON[dd.month][:3]} {dd.day}</span>'
                    f'<a href="{u(c["u"])}">{e(c["n"])}</a><span class="motd-arc-meta">{kind_pill(c)}{status_pill(c)}'
                    f'<span class="motd-arc-vote" data-motd-arc="m:{s}"></span></span></li>')
    archive = (f'<section class="motd-arc" aria-labelledby="motd-ah"><h2 id="motd-ah">The last {ARCHIVE} days</h2>'
               f'<ol class="motd-list" id="motd-list">{"".join(rows)}</ol></section>') if rows else ''

    n_my = sum(1 for c in cases.values() if c['k'] == 'my')
    n_ce = sum(1 for c in cases.values() if c['k'] == 'ce')
    n_uf = sum(1 for c in cases.values() if c['k'] == 'uf')
    cfg = json.dumps({'api': API, 'base': ctx.BASE, 'sitekey': SITEKEY}, separators=(',', ':')).replace('</', '<\\/')
    head = (f'<link rel="stylesheet" href="{u("/static/report.css")}">'
            f'<link rel="stylesheet" href="{u("/static/motd.css")}">'
            '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" async defer></script>'
            f'<script src="{u("/static/vote.js")}" defer></script>'
            f'<script src="{u("/static/motd.js")}" defer></script>')
    body = f'''
<section class="band band-dark motd-head"><div class="wrap">
  <p class="crumb"><a href="{u('/mysteries/')}">Mysteries</a> / Mystery of the day</p>
  <h1>Mystery of the day</h1>
  <p class="lede">One strange case a day, picked from the {len(cases)} mysteries, close encounters and famous UFO cases we've written up. Read it, decide what you think it was, then come back tomorrow to see how everyone voted and what the evidence actually says.</p>
  <p class="motd-switch" id="motd-switch">A new case goes up at midnight UTC every day.</p>
</div></section>
<div class="band band-mist motd-body" id="motd" data-day="{today}" data-json="{u('/data/motd.json')}" data-base="{e(ctx.BASE)}"><div class="wrap">
  <p class="motd-date" id="motd-date">{e(ddate(today).strftime('%A, %B %-d, %Y'))} (UTC)</p>
  {today_html}
  {yest_html}
  {archive}
  <aside class="motd-how">
    <h2>How this works</h2>
    <p>Every day at midnight UTC the next case comes up from a shuffled list of {n_my} mysteries, {n_ce} close encounters and {n_uf} famous UFO cases, so you won't see the same one again for {len(cases)} days. The summary is the same one on the case's own page and I don't add anything to it. The verdict stays hidden on the day so you get to make up your own mind first.</p>
    <p>Voting is free but you need an account, which is just your email (we send a sign-in link, no password). One vote per person keeps it fair, newer accounts count a bit less, and results only show once at least 10 people have voted. It's what readers think, not a verdict. I left out the cases where people died or went missing, since voting "hoax" on those didn't sit right with me.</p>
    <p>Want more? Browse all the <a href="{u('/mysteries/')}">mysteries</a>, <a href="{u('/encounters/')}">close encounters</a> and <a href="{u('/ufo/cases/')}">famous UFO cases</a>, or try <a href="{u('/on-this-day/')}">on this day</a>.</p>
  </aside>
  <script type="application/json" id="ea-config">{cfg}</script>
</div></div>'''
    ctx.write(PATH, ctx.page(PATH, 'Mystery of the day: one strange case a day, and you decide what it was', body,
                             'A new unexplained case every day from the Encounter Atlas files: UFO sightings, close encounters and '
                             'mysteries from around the world. Vote on what you think it was and see the verdict tomorrow.',
                             body_class='motd', head_extra=head))

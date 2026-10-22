"""Encounter reports: the /report/ form (replaces the placeholder page build.py writes) and the /reports/
pages (recent reports, one report via ?id=, your account via ?me=1, sign-in links via ?signin=).

Static report pages (Mike, 2026-10-22): every approved report also gets /reports/<pid>/, built from the Worker's
PUBLIC API (/api/reports list + /api/reports/<pid>), so nothing beyond what that API shows can reach the HTML.
Thin ones (THIN_STORY_CHARS, no usable place or date) are noindex,follow and so stay out of the sitemap.
A report approved since the last build has no page yet: 404.html sends /reports/<pid>/ to /reports/?id=<pid>,
which renders it in the browser; /reports/?id= sends readers on to the static page once it exists (vote.js).

Everything dynamic comes from the Worker in worker/ (see worker/DEPLOY.md).
Build-time settings (environment variables):
  EA_API             Worker origin. Default https://api.encounteratlas.com
  TURNSTILE_SITEKEY  public Turnstile site key. The default is Cloudflare's always-pass TEST key: replace it
                     with the real widget's key before launch (DEPLOY.md), or every real submission fails.
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.request

API = os.environ.get('EA_API', 'https://api.encounteratlas.com').rstrip('/')
SITEKEY = os.environ.get('TURNSTILE_SITEKEY', '1x00000000000000000000AA')
MAPLIBRE = '4.7.1'

# A reader report is "thin" (noindex,follow, not in the sitemap) when its story is shorter than this, or it has no
# usable place name or date. Substantial reports are indexable and go to IndexNow through the sitemap diff.
THIN_STORY_CHARS = 600
# Same list as the Worker's LIVING_TRADITIONS (worker/src/index.js) and build.py: these reports are only mapped to a
# ~100 km cell, so their pages name the region, never the place the reader typed.
LIVING_TRADITIONS = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
                     'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}
# Competitor groups never appear on the site (the Worker blocks them on submit; this is the build-time backstop).
BLOCKED = re.compile(r'bfro|nuforc|mufon|enigma\s*labs|enigmalabs|cryptid\s*catchers|cryptidcatchers|cryptid\s*atlas|cryptidatlas', re.I)
# A street address ("Main St 12", "Улица ..., 64", "64 Elm Road") is too precise for a public page title.
ADDRESS = re.compile(r'(^\s*\d+[\w/-]*\s+\S)|(,\s*\d+[\w/-]*\s*$)|(\s\d+[a-zа-я]?\d*\s*$)', re.I)


def _head(ctx, extra_js=''):
    v = ctx.url
    return (f'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/{MAPLIBRE}/maplibre-gl.min.css">'
            f'<link rel="stylesheet" href="{v("/static/report.css")}">'
            f'<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/{MAPLIBRE}/maplibre-gl.min.js" defer></script>'
            f'<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" async defer></script>'
            f'<script src="{v("/static/vote.js")}" defer></script>{extra_js}')


def _config(ctx):
    cfg = {'api': API, 'base': ctx.BASE, 'sitekey': SITEKEY}
    meta = {c['slug']: {'n': c['name'], 'c': c['cat'], 'i': c.get('art') or 'icons/' + c['icon']} for c in ctx.creatures}
    cats = {k: v[0] for k, v in ctx.CATS.items()}
    # json.dumps output is safe inside <script type="application/json"> once "</" is escaped.
    j = lambda o: json.dumps(o, separators=(',', ':')).replace('</', '<\\/')
    return (f'<script type="application/json" id="ea-config">{j(cfg)}</script>'
            f'<script type="application/json" id="ea-creatures">{j({"creatures": meta, "cats": cats})}</script>')


def _picker(ctx):
    esc = ctx.esc
    groups = ''
    for k, (label, _) in ctx.CATS.items():
        cs = sorted((c for c in ctx.creatures if c['cat'] == k), key=lambda c: c['name'])
        if not cs:
            continue
        opts = ''.join(
            f'<label class="pick" data-names="{esc((c["name"] + " " + " ".join(c["aliases"])).lower())}">'
            f'<input type="radio" name="creature" value="{c["slug"]}" required>'
            f'{ctx.badge(c, "sm")}<span class="pick-name">{esc(c["name"])}</span></label>' for c in cs)
        groups += f'<div class="pick-group" data-group="{k}"><p class="pick-h"><span class="dot cat-{k}"></span>{esc(label)}</p><div class="pick-grid">{opts}</div></div>'
    other = (f'<div class="pick-group"><p class="pick-h">Not on the list</p><div class="pick-grid">'
             f'<label class="pick pick-other" data-names="other something else lights unknown"><input type="radio" name="creature" value="other">'
             f'<span class="badge badge-sm cat-other"><span class="q" aria-hidden="true">?</span></span><span class="pick-name">Something else</span></label></div></div>')
    return groups + other


def build(ctx):
    # Until the Worker is deployed (EA_API set in the build), keep build.py's "opens soon" /report/ page.
    if 'EA_API' not in os.environ:
        return
    esc, url = ctx.esc, ctx.url
    tips = '''<ul class="signs">
    <li>Date, time and how long it lasted</li>
    <li>Where you were, and where it was from you</li>
    <li>Size, shape, colour and how it moved</li>
    <li>Sounds and smells</li>
    <li>Weather and light: moon, clouds, headlights</li>
    <li>Who else saw it</li>
  </ul>'''
    form = f'''
<section class="band band-dark rep-head">
  <div class="wrap">
    <p class="crumb"><a href="{url('/reports/')}">Encounters</a> / Report</p>
    <h1 id="rf-title">Report an encounter</h1>
    <p class="lede">Saw something you can't explain? Tell us what happened. A moderator reads every report before it goes on the map.</p>
    <p class="rep-who" data-who></p>
  </div>
</section>
<div class="band band-mist rep-band"><div class="wrap rep-grid">
<form id="report-form" class="rep-form" novalidate>
  <p class="draft-note" data-draft-banner hidden><span>We brought back the report you started on this device.</span> <button type="button" class="linkish" data-draft-clear>Start over</button></p>
  <p class="edit-note" data-edit-banner hidden></p>

  <fieldset class="step" id="step-what">
    <legend><span class="n">1</span>What did you see?</legend>
    <label class="visually-hidden" for="pick-q">Search</label>
    <input id="pick-q" class="pick-search" type="search" placeholder="Search: Sasquatch, orbs, lake monster..." autocomplete="off">
    <div class="picker" role="radiogroup" aria-label="Creature or phenomenon">{_picker(ctx)}</div>
    <div class="field" data-other hidden>
      <label for="other_what">What was it, in a few words?</label>
      <input id="other_what" name="other_what" maxlength="80" placeholder="e.g. glowing green lights over the lake">
    </div>
    <p class="err" data-err="creature"></p><p class="err" data-err="other_what"></p>
  </fieldset>

  <fieldset class="step" id="step-when">
    <legend><span class="n">2</span>When?</legend>
    <div class="row2">
      <div class="field"><label for="seen_date">Date</label><input id="seen_date" name="seen_date" type="date" required></div>
      <div class="field"><label for="seen_time">Time <span class="opt">(if you know)</span></label><input id="seen_time" name="seen_time" type="time"></div>
    </div>
    <label class="check"><input type="checkbox" name="date_approx"> I'm not sure of the exact date</label>
    <p class="err" data-err="seen_date"></p><p class="err" data-err="seen_time"></p>
  </fieldset>

  <fieldset class="step" id="step-where">
    <legend><span class="n">3</span>Where?</legend>
    <div class="loc-actions">
      <button type="button" class="btn" data-gps>Use my location</button>
      <span class="or">or tap the map, or search a place</span>
    </div>
    <div class="place-row">
      <label class="visually-hidden" for="place">Place name</label>
      <input id="place" name="place" maxlength="120" placeholder="Nearest town, park or road" autocomplete="off">
      <button type="button" class="btn btn-quiet" data-find>Find</button>
    </div>
    <ul class="place-results" data-place-results hidden></ul>
    <div class="rep-map" id="rep-map" aria-label="Map: tap to set where it happened"></div>
    <p class="loc-status" data-loc-status>No spot set yet.</p>
    <p class="privacy"><strong>Your exact spot stays private.</strong> The public map only shows an area about 5 km across, and only moderators see the pin. The place name you type is public, so keep it general on private land. <a href="{ctx.url('/privacy/')}">How we handle your information</a>.</p>
    <input type="hidden" name="lat"><input type="hidden" name="lon"><input type="hidden" name="loc_source" value="map">
    <p class="err" data-err="location"></p>
  </fieldset>

  <fieldset class="step" id="step-story">
    <legend><span class="n">4</span>What happened?</legend>
    <div class="field">
      <label for="story">Tell it the way you'd tell a friend</label>
      <textarea id="story" name="story" rows="8" maxlength="6000" required placeholder="What you were doing, what you saw, how it moved, what happened next."></textarea>
      <p class="hint"><span data-count>0</span> characters. A few sentences at least.</p>
      <p class="err" data-err="story"></p>
    </div>
    <div class="row2">
      <div class="field"><label for="duration">How long did it last?</label><input id="duration" name="duration" maxlength="80" placeholder="e.g. about 20 seconds"></div>
      <div class="field"><label for="witnesses">How many people saw it?</label><input id="witnesses" name="witnesses" type="number" min="1" max="999" value="1" inputmode="numeric"></div>
    </div>
    <div class="row2">
      <div class="field"><label for="sounds">Sounds</label><textarea id="sounds" name="sounds" rows="2" maxlength="600" placeholder="Knocks, howls, humming, nothing at all"></textarea></div>
      <div class="field"><label for="smells">Smells</label><textarea id="smells" name="smells" rows="2" maxlength="600" placeholder="Skunk, wet dog, sulphur, none"></textarea></div>
    </div>
  </fieldset>

  <fieldset class="step" id="step-media">
    <legend><span class="n">5</span>Photo and video links <span class="opt">(optional)</span></legend>
    <p class="hint">We don't host photos or videos here. To share one, upload it to a free photo or video service first, then paste the link below.</p>
    <div class="field">
      <label>Photo links <span class="opt">(up to 5)</span></label>
      <div data-links></div>
      <button type="button" class="linkish" data-add-link>+ Add another photo link</button>
      <details class="host-help"><summary>Where can I put my photos?</summary>
        <p>Any of these free services gives you a link you can paste here:</p>
        <ul>
          <li><a href="https://imgur.com/upload" target="_blank" rel="noopener nofollow">Imgur</a>: no account needed. Upload, then copy the link.</li>
          <li><a href="https://postimages.org/" target="_blank" rel="noopener nofollow">Postimages</a>: no account needed.</li>
          <li><a href="https://www.flickr.com/" target="_blank" rel="noopener nofollow">Flickr</a>: free account, keeps the full-quality original.</li>
          <li>Google Photos, iCloud Photos, Dropbox or OneDrive: open the photo, choose <em>Share</em> and <em>Copy link</em> (make sure anyone with the link can view it).</li>
          <li>Instagram, Facebook or X: post it publicly, then copy the post link.</li>
        </ul>
        <p>Phone photos can carry your GPS location. Imgur removes it, but other services and cloud drives may not. A screenshot of the photo is an easy way to strip it. You can delete the photo at the host whenever you like.</p>
      </details>
      <p class="hint">We show photo links as buttons that open the photo on that site, not on our pages.</p>
      <p class="err" data-err="links"></p>
    </div>
    <div class="field">
      <label>Video links <span class="opt">(YouTube, TikTok or Vimeo)</span></label>
      <div data-videos></div>
      <button type="button" class="linkish" data-add-video>+ Add another link</button>
      <p class="hint">Upload the video to YouTube, TikTok or Vimeo first, then paste the link here.</p>
      <p class="err" data-err="videos"></p>
    </div>
  </fieldset>

  <fieldset class="step" id="step-you">
    <legend><span class="n">6</span>About you</legend>
    <label class="check"><input type="checkbox" name="anonymous" checked> Stay anonymous on the site</label>
    <div class="field" data-name-field hidden><label for="display_name">Show my name as</label><input id="display_name" name="display_name" maxlength="40" autocomplete="nickname"></div>
    <div class="field" data-email-field>
      <label for="email">Email <span class="opt">(optional, never shown)</span></label>
      <input id="email" name="email" type="email" maxlength="254" autocomplete="email" inputmode="email" placeholder="you@example.com">
      <p class="hint">We'll email you a link to follow and edit your report. No newsletter, no passwords.</p>
      <p class="err" data-err="email"></p>
    </div>
    <div class="hp" aria-hidden="true"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
  </fieldset>

  <div class="send">
    <div class="ts-slot" data-ts></div>
    <button type="submit" class="btn btn-big" data-submit>Send my report</button>
    <p class="form-msg" data-form-msg role="status" aria-live="polite"></p>
    <p class="draft-status" data-draft-status>Your report saves on this device as you type, so it's safe to finish later.</p>
  </div>
</form>

<section class="rep-done" data-done hidden tabindex="-1">
  <h2>Thanks. Your report is in.</h2>
  <p data-done-msg>A moderator will read it soon. Once it's approved it appears on the map and people can weigh in.</p>
  <p class="done-actions"><a class="btn" href="{url('/reports/')}">See recent encounters</a> <a class="btn btn-quiet" href="{url('/report/')}">Report another</a></p>
</section>

<aside class="rep-aside">
  <h2>Write it down while it's fresh</h2>
  {tips}
  <p>Photograph tracks with something for scale, like a boot or a phone.</p>
  <h2>What to bring next time</h2>
  <p>A trail camera, a red-light headlamp and an audio recorder catch most of what people miss. See <a href="{url('/gear/')}">field gear for investigators</a>.</p>
  <h2>What happens next</h2>
  <p>A moderator checks every report. Once it's live, anyone with an account can vote <strong>Real</strong>, <strong>Hoax</strong> or <strong>Misidentified</strong>. Votes are community opinion, not a verdict.</p>
</aside>
</div></div>
<noscript><div class="wrap"><p class="lede">The report form needs JavaScript turned on.</p></div></noscript>
{_config(ctx)}'''
    ctx.write('/report/', ctx.page('/report/', 'Report an encounter', form,
                                   'Report a Bigfoot, Dogman, UFO or other strange encounter. Your exact location stays private.',
                                   body_class='reporting', head_extra=_head(ctx, f'<script src="{url("/static/skycore.js")}" defer></script><script src="{url("/static/report.js")}" defer></script>')))

    # Static pages first, so the /reports/ list below can carry the same cards in its HTML (no-JS readers and crawlers);
    # vote.js swaps them for the live, filterable list.
    shaped = build_report_pages(ctx)
    static_cards = ''.join(card_html(ctx, R, S, f'rl{i}') for i, (R, S) in enumerate(shaped))
    first = (f'<div class="list-bar"><h2>Latest reports</h2></div><div class="rep-cards">{static_cards}</div>' if static_cards
             else '<p class="loading">Loading reports...</p>')
    shell = f'''
<div id="ea-reports" data-view="list">
<section class="band band-dark rep-head">
  <div class="wrap">
    <h1>Recent encounters</h1>
    <p class="lede">What people say they saw, checked by a moderator and pinned to within about 5 km. Read them, then vote: real, hoax or misidentified.</p>
    <p class="lede-story"><a href="{url('/stories/')}">Prefer a longer read? Witness stories: first-hand accounts retold in full</a></p>
    <div class="map-actions"><a class="btn" href="{url('/report/')}">Report an encounter</a><a class="btn btn-ghost" href="{url('/reports/?me=1')}" data-acct>Your reports</a></div>
  </div>
</section>
<div class="band band-mist"><div class="wrap">{first}</div></div>
</div>
<noscript><div class="wrap"><p class="lede">Reports load with JavaScript. Turn it on to read them.</p></div></noscript>
{_config(ctx)}'''
    ctx.write('/reports/', ctx.page('/reports/', 'Encounter reports: Real or hoax?', shell,
                                    'Recent Bigfoot, Dogman, UFO and cryptid encounter reports from witnesses, with community Real or Hoax votes.',
                                    body_class='reports', head_extra=_head(ctx)))


# ---------------- static report pages ----------------

def _get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={'User-Agent': 'encounteratlas-build/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # network blip in CI: try again, then give up (pages fall back to /reports/?id=)
            err = e
            time.sleep(2 * (i + 1))
    raise err


def fetch_reports():
    """Approved reports, newest first, exactly as the public API shows them. [] if the API can't be reached."""
    out, before = [], None
    try:
        while True:
            d = _get('/api/reports?limit=50' + (f'&before={before}' if before else ''))
            for x in d.get('reports', []):
                if re.fullmatch(r'[a-z0-9]{10}', x.get('id', '')):
                    full = _get('/api/reports/' + x['id']).get('report')
                    if full:
                        full['approved_at'] = full.get('approved_at') or x.get('approved_at')
                        out.append(full)
            before = d.get('next')
            if not before or len(out) > 5000:
                break
    except Exception as e:
        print(f'reports: public API not reachable ({e!r}); static report pages skipped this build', file=sys.stderr)
        return []
    return out


POSTER_SKY = {'hominid': ('#E3A649', '#B5532F'), 'canid': ('#3B4C6B', '#1B2A3A'), 'winged': ('#3B4C6B', '#1B2A3A'), 'aquatic': ('#E8B04A', '#C8693A'),
              'entity': ('#3B4C6B', '#1B2A3A'), 'ufo': ('#2E3E5C', '#141E2E'), 'fae': ('#C97B9A', '#4A2E4F'), 'other': ('#3B4C6B', '#1B2A3A')}


def _poster(ctx, c, sid, cls='rposter'):
    """Same park-poster frame vote.js draws for reader reports; "Something else" gets the unknown shape."""
    cat = c['cat'] if c else 'other'
    art = c['art'] if c and c.get('art') else 'art/unknown-shape'
    a, b = POSTER_SKY.get(cat, POSTER_SKY['other'])
    wet = cat == 'aquatic'
    ground = ('<rect y="160" width="200" height="40" fill="#2B4A55"/>' if wet else
              '<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="#1E3A2F"/>')
    return (f'<span class="{cls}" aria-hidden="true"><svg viewBox="0 0 200 200"><defs><linearGradient id="{sid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>'
            f'<clipPath id="c{sid}"><rect x="6" y="6" width="188" height="188" rx="10"/></clipPath></defs><g clip-path="url(#c{sid})">'
            f'<rect width="200" height="200" fill="url(#{sid})"/><circle cx="150" cy="52" r="24" fill="#F3E3B8" opacity=".9"/>'
            f'<path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="#5E4A3A" opacity=".5"/>{ground}'
            f'<image href="{ctx.url("/static/" + art + ".svg")}" x="22" y="{34 if wet else 26}" width="160" height="160"/></g>'
            f'<rect x="6" y="6" width="188" height="188" rx="10" fill="none" stroke="#F3E3B8" stroke-width="4"/></svg></span>')


def place_name(p):
    """Readers often type places in lower case ("boya lake"): capitalise each word unless they used capitals (vote.js placeName)."""
    p = ' '.join(str(p or '').split())
    return re.sub(r'(^|[\s-])(\w)', lambda m: m.group(1) + m.group(2).upper(), p) if p and p == p.lower() else p


def _short(t, n=70):
    t = ' '.join(str(t or 'Something strange').split())
    t = t[:1].upper() + t[1:]
    return t if len(t) <= n else re.sub(r'\s+\S*$', '', t[:n]) + '…'


def _date(d, t='', approx=False):
    try:
        x = datetime.date.fromisoformat(d)
    except (TypeError, ValueError):
        return ''
    if approx:
        return f'Around {x:%B} {x.year}'
    s = f'{x:%B} {x.day}, {x.year}'
    if t and re.fullmatch(r'\d\d:\d\d', t):
        hh, mm = map(int, t.split(':'))
        s += f', {(hh % 12) or 12}:{mm:02d} {"AM" if hh < 12 else "PM"}'
    return s


def _region(ctx, lat, lon):
    """(name, hub path or None) of the state/province/country the public point falls in."""
    A = getattr(ctx, 'areas', None)
    if A is None or lat is None:
        return '', None
    cc, a1 = A.where(float(lat), float(lon))
    if not cc:
        return '', None
    countries = getattr(ctx, '_countries', None)
    if countries is None:
        cp = os.path.join(ctx.ROOT, 'data', 'countries.json')
        countries = ctx._countries = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else {}
    country = (countries.get(cc) or [cc])[0]
    if cc == 'US':
        country = 'USA'
    hub = (getattr(ctx, 'regions', {}) or {}).get(f'{cc}.{a1}') if a1 else None
    a1n = (A.a1_name.get(f'{cc}.{a1}') or '').rstrip("'") if a1 else ''
    if hub:
        return f'{hub[1]}, {country}', hub[0]
    return (f'{a1n}, {country}' if a1n else country), None


def shape(ctx, R):
    """Everything a report page and card need, from the public API fields only."""
    c = ctx.by_slug.get(R.get('creature'))
    region_only = R.get('creature') in LIVING_TRADITIONS
    typed = place_name(R.get('place'))
    usable = bool(typed) and not region_only and not ADDRESS.search(typed)
    region, hub = _region(ctx, R.get('lat'), R.get('lon'))
    what = c['name'] if c else _short(R.get('other_what') or 'Something strange', 48)
    if usable:
        lower = typed[:1].lower() + typed[1:]
        title = f'{what} {lower}' if re.match(r'(near|outside|by|at|in|around|off|on|above|over)\s', typed, re.I) else f'{what} near {typed}'
        where = typed
    elif region:
        title, where = f'{what} in {region.split(",")[0]}', region
    else:
        title, where = f'{what} encounter', ''
    story = str(R.get('story') or '').strip()
    reasons = []
    if len(story) < THIN_STORY_CHARS:
        reasons.append('short story')
    if not usable:
        reasons.append('no usable place')
    if not R.get('seen_date'):
        reasons.append('no date')
    if BLOCKED.search(' '.join(str(R.get(k) or '') for k in ('story', 'sounds', 'smells', 'other_what', 'place', 'duration'))):
        reasons.append('names a competitor group')
    return {'c': c, 'what': what, 'title': title, 'where': where, 'region': region, 'hub': hub, 'region_only': region_only,
            'story': story, 'thin': reasons, 'path': f'/reports/{R["id"]}/'}


def card_html(ctx, R, S, sid):
    e = ctx.esc
    c = S['c']
    cat = c['cat'] if c else 'other'
    kind = c['name'] if c else 'Something else'
    snip = S['story'] if len(S['story']) <= 220 else re.sub(r'\s+\S*$', '', S['story'][:210]) + '…'
    head = _short(R.get('other_what'), 70) if not c else (S['where'] or 'Place not named')
    sub = f'<span class="rc-date">{e(S["where"])}</span>' if not c and S['where'] else ''
    return (f'<a class="rcard" href="{ctx.url(S["path"])}"><div class="rc-img rc-noimg cat-{cat}">{_poster(ctx, c, sid)}</div>'
            f'<span class="rc-body"><span class="rc-kind"><span class="dot cat-{cat}"></span>{e(kind)}</span>'
            f'<span class="rc-title">{e(head)}</span>{sub}<span class="rc-date">{e(_date(R.get("seen_date"), "", R.get("date_approx")))}</span>'
            f'<span class="rc-snip">{e(snip)}</span></span></a>')


def report_page(ctx, R, S, others):
    e, u = ctx.esc, ctx.url
    c, pid = S['c'], R['id']
    cat = c['cat'] if c else 'other'
    when = _date(R.get('seen_date'), R.get('seen_time'), R.get('date_approx'))
    paras = ''.join(f'<p>{e(p.strip())}</p>' for p in re.split(r'\n+', S['story']) if p.strip())
    extra = ''
    if R.get('sounds'):
        extra += f'<h2>Sounds</h2><p>{e(R["sounds"])}</p>'
    if R.get('smells'):
        extra += f'<h2>Smells</h2><p>{e(R["smells"])}</p>'
    links = [l for l in (R.get('links') or []) if str(l.get('url', '')).startswith('https://') and not BLOCKED.search(l.get('url', ''))]
    if links:
        extra += (f'<h2>{"Photos (links)" if len(links) > 1 else "Photo (link)"}</h2><ul class="plinks">'
                  + ''.join(f'<li><a class="btn btn-quiet" href="{e(l["url"])}" rel="noopener nofollow ugc noreferrer">View photo on {e(l.get("host") or "another site")}</a></li>' for l in links)
                  + '</ul><p class="small">Photos are hosted by the witness on another site. We don\'t check or store them, and they may change or be removed.</p>')
    vids = R.get('videos') or []
    if vids:
        extra += f'<h2>{"Videos" if len(vids) > 1 else "Video"}</h2>'
        for v in vids:
            name = {'youtube': 'YouTube', 'tiktok': 'TikTok', 'vimeo': 'Vimeo'}.get(v.get('provider'), 'the web')
            if v.get('provider') == 'youtube' and re.fullmatch(r'[A-Za-z0-9_-]{11}', v.get('id', '')):
                box = (f'<div class="vid-box"><a class="yt" href="{e(v["url"])}" rel="noopener nofollow ugc" aria-label="Play video on YouTube">'
                       f'<img src="https://i.ytimg.com/vi/{v["id"]}/hqdefault.jpg" alt="" loading="lazy"><span class="yt-play" aria-hidden="true"></span></a>'
                       f'<a class="vid-link" href="{e(v["url"])}" rel="noopener nofollow ugc">Watch on YouTube</a></div>')
            else:
                box = f'<a class="vid-card" href="{e(v["url"])}" rel="noopener nofollow ugc"><span class="yt-play" aria-hidden="true"></span>Watch the video on {name}</a>'
            extra += f'<div class="vid">{box}<div data-vote-item="{e(v["item"])}" data-vote-label="This video: real or hoax?" data-vote-compact></div></div>'

    if S['region_only']:
        where_txt = (f'{S["region"]}. ' if S['region'] else '') + 'This is part of a living tradition, so we only map it to the region, about 100 km across.'
        km, zoom = 50, 6
    else:
        where_txt = (f'{S["where"]}. ' if S['where'] else '') + 'Shown within about 5 km.'
        km, zoom = 3, 9.5
    facts = [('What', f'<a href="{u("/creatures/" + c["slug"] + "/")}">{e(c["name"])}</a>' if c else e(_short(R.get('other_what'), 120))),
             ('When', e(when)), ('Where', e(where_txt)), ('How long', e(R.get('duration') or '')),
             ('Witnesses', e(str(R.get('witnesses') or ''))), ('Reported by', e(R.get('name') or 'Anonymous')),
             ('Added', e(_date(datetime.datetime.utcfromtimestamp(R['approved_at']).date().isoformat())) if R.get('approved_at') else '')]
    dl = ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in facts if v)
    lat, lon = R.get('lat'), R.get('lon')
    at = f'{lat:.2f},{lon:.2f},{6 if S["region_only"] else 8}' if lat is not None else ''
    explore = []
    if S['hub']:
        explore.append(f'<li><a href="{u(S["hub"])}">Everything strange in {e(S["region"].split(",")[0])}</a></li>')
    if at:
        explore.append(f'<li><a href="{u("/map/?at=" + at)}">Other sightings in this area, on the map</a></li>')
    explore.append(f'<li><a href="{u("/near-me/")}">Sightings near you</a></li>')
    if c:
        explore.append(f'<li><a href="{u("/creatures/" + c["slug"] + "/")}">All about {e(c["name"])}</a></li>')
        explore.append(f'<li><a href="{u("/reports/?creature=" + c["slug"])}">Every {e(c["name"])} reader report</a></li>')
    more = ''
    if others:
        more = (f'<h2>More reader reports</h2><div class="rep-cards">'
                + ''.join(card_html(ctx, o, os_, f'rs{pid}{i}') for i, (o, os_) in enumerate(others)) + '</div>'
                f'<p><a class="btn btn-quiet" href="{u("/reports/")}">See all reader reports</a></p>')
    crumb_c = f' / <a href="{u("/creatures/" + c["slug"] + "/")}">{e(c["name"])}</a>' if c else ''
    report_href = u('/report/?creature=' + c['slug']) if c else u('/report/')
    seen_icon = ctx.crit_icon(c) if c else ''
    body = f'''
<section class="band band-dark rep-head"><div class="wrap rep-detail-head">
  <div class="creature-head-in">{_poster(ctx, c, 'rsky' + pid, 'rposter rposter-lg')}
    <div><p class="crumb"><a href="{u('/reports/')}">Encounters</a>{crumb_c}</p>
      <h1>{e(S['title'])}</h1>
      <p class="lede">{e(when)}</p></div></div>
</div></section>
<div class="band band-mist"><div class="wrap">
  <div class="creature-body rep-body" data-report="{pid}">
    <article class="prose rep-story">
      <div data-owner-slot></div>
      {paras}
      {extra}
      <h2 id="vote">Real or hoax?</h2>
      <div data-vote-item="r:{pid}" data-vote-label="Your verdict on this encounter"></div>
      <p class="small">A reader sent this in and a moderator checked it before it went up. We can't verify it, and we don't claim it's true or false.
      Is this your report? <a href="{u('/reports/?me=1')}">Sign in to edit it</a>, or <a href="{u('/contact/?about=report:' + pid)}">tell us</a> if something's wrong.</p>
    </article>
    <aside class="facts">
      <div class="mini-map" data-rep-map="{lat},{lon},{km},{zoom}" role="img" aria-label="Map of the rough area"></div>
      <dl>{dl}</dl>
      <p class="more"><a href="{report_href}">Seen something too? Report it</a></p>
    </aside>
  </div>
  <h2>Explore around this report</h2>
  <ul class="also-links">{''.join(explore)}</ul>
  <section class="seen-box cat-{cat}">{seen_icon}<div>
    <h2>Had an experience like this?</h2>
    <p>Tell us what happened. Every report is read by a person before it goes on the map, and your exact spot stays private.</p>
    <p class="seen-actions"><a class="btn" href="{report_href}">Report an encounter</a>
    <a class="btn btn-ghost" href="{u('/stories/')}">Read witness stories</a></p>
  </div></section>
  {more}
</div></div>
{_config(ctx)}'''
    desc = re.sub(r'\s+', ' ', S['story'])
    desc = desc if len(desc) <= 155 else re.sub(r'\s+\S*$', '', desc[:150]) + '…'
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': S['title'][:110], 'description': desc,
          'url': ctx.SITE_URL + S['path'], 'isPartOf': {'@type': 'WebSite', 'name': 'Encounter Atlas', 'url': ctx.SITE_URL + '/'},
          'publisher': {'@type': 'Organization', 'name': 'Encounter Atlas', 'url': ctx.SITE_URL + '/'}}
    if R.get('approved_at'):
        ld['datePublished'] = datetime.datetime.utcfromtimestamp(R['approved_at']).strftime('%Y-%m-%dT%H:%M:%SZ')
    if R.get('name'):
        ld['author'] = {'@type': 'Person', 'name': R['name']}
    if S['where']:
        ld['contentLocation'] = {'@type': 'Place', 'name': S['where']}
    head = (_head(ctx, f'<script src="{u("/static/report_page.js")}" defer></script>')
            + '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>')
    return ctx.page(S['path'], S['title'], body, desc, body_class='reports report-page', head_extra=head, noindex=bool(S['thin']))


def build_report_pages(ctx):
    reports = fetch_reports()
    shaped = [(R, shape(ctx, R)) for R in reports]
    for i, (R, S) in enumerate(shaped):
        # Related: same creature first, then the newest others; indexable ones before thin ones.
        pool = [x for x in shaped if x[0]['id'] != R['id']]
        pool.sort(key=lambda x: (x[0].get('creature') != R.get('creature'), bool(x[1]['thin'])))
        ctx.write(S['path'], report_page(ctx, R, S, pool[:3]))
    ctx.report_where = {R['id']: S['where'] for R, S in shaped}  # z_near_me.py's static cards use the same coarse place
    n_thin = sum(1 for _, S in shaped if S['thin'])
    for R, S in shaped:
        if S['thin']:
            print(f'reports: {R["id"]} noindex ({", ".join(S["thin"])})', file=sys.stderr)
    print(f'reports: {len(shaped)} static report pages, {len(shaped) - n_thin} indexable, {n_thin} noindex', file=sys.stderr)
    # Search entries for indexable reports, like the other sections add theirs.
    sp = os.path.join(ctx.OUT, 'data', 'search.json')
    if os.path.exists(sp):
        items = json.load(open(sp, encoding='utf-8'))
        items += [{'t': S['title'], 'a': 'reader report ' + (S['c']['name'] if S['c'] else ''), 'k': 'Reader report',
                   'u': ctx.url(S['path']), 'i': 'clipboard', 'c': S['c']['cat'] if S['c'] else 'other'} for R, S in shaped if not S['thin']]
        json.dump(items, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    return shaped

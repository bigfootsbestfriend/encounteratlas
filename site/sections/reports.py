"""Encounter reports: the /report/ form (replaces the placeholder page build.py writes) and the /reports/
pages (recent reports, one report via ?id=, your account via ?me=1, sign-in links via ?signin=).

Everything dynamic comes from the Worker in worker/ (see worker/DEPLOY.md). Pages are JS-rendered for now.
Build-time settings (environment variables):
  EA_API             Worker origin. Default https://api.encounteratlas.com
  TURNSTILE_SITEKEY  public Turnstile site key. The default is Cloudflare's always-pass TEST key: replace it
                     with the real widget's key before launch (DEPLOY.md), or every real submission fails.
"""
import json
import os

API = os.environ.get('EA_API', 'https://api.encounteratlas.com').rstrip('/')
SITEKEY = os.environ.get('TURNSTILE_SITEKEY', '1x00000000000000000000AA')
MAPLIBRE = '4.7.1'


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
                                   body_class='reporting', head_extra=_head(ctx, f'<script src="{url("/static/report.js")}" defer></script>')))

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
<div class="band band-mist"><div class="wrap"><p class="loading">Loading reports...</p></div></div>
</div>
<noscript><div class="wrap"><p class="lede">Reports load with JavaScript. Turn it on to read them.</p></div></noscript>
{_config(ctx)}'''
    ctx.write('/reports/', ctx.page('/reports/', 'Encounter reports: Real or hoax?', shell,
                                    'Recent Bigfoot, Dogman, UFO and cryptid encounter reports from witnesses, with community Real or Hoax votes.',
                                    body_class='reports', head_extra=_head(ctx)))

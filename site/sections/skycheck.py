"""/tools/was-it-a-planet/: what bright things were in the sky at a given time and place.

Everything is worked out in the browser (static/skycheck.js) with astronomy-engine (MIT) for the Sun, Moon, planets and
the brightest stars, and satellite.js (MIT) with a Celestrak orbit for the International Space Station on recent dates.
The page itself is full HTML: the explanation of the usual suspects reads fine without JavaScript.
Data: OUT/data/cities.json (tools/make_cities.py, GeoNames CC BY 4.0) for the place picker.
"""
import os, shutil

SUSPECTS = [
    ('Venus', 'e-planet', 'The brightest thing in the sky after the Sun and Moon. Low in the west after sunset or the east before dawn, '
              'steady and white, it can look like a landing light that never lands. It is the most common "UFO" of all.'),
    ('Jupiter', 'e-planet', 'Bright, steady and cream-coloured, often high in the sky all night. Through binoculars you can see up to four tiny moons beside it.'),
    ('Sirius and other bright stars', 'e-planet', 'Low on the horizon, a bright star twinkles hard and flashes red, green and blue. People film Sirius as a "colour-changing craft" every winter.'),
    ('The Moon', 'e-planet', 'A thin crescent low near the horizon, orange and half-hidden by cloud, can look nothing like the Moon.'),
    ('The International Space Station', 'e-satellite', 'A bright, steady light gliding across the sky in a few minutes with no blinking, then fading out in mid-air as it enters Earth\'s shadow.'),
    ('Starlink trains', 'e-starlink', 'A straight line of evenly spaced lights moving together, seen in the days after a launch. One of the most reported "fleets" since 2019.'),
    ('Planes and drones', 'e-drone', 'Landing lights pointed at you look like a still, bright light for minutes. Look for blinking red and green, and listen.'),
    ('Sky lanterns', 'e-lantern', 'Orange, flickering lights drifting slowly with the wind, often in a group after a wedding or party, then winking out one by one.'),
]


def build(ctx):
    E, U = ctx.esc, ctx.url
    src = os.path.join(ctx.ROOT, 'data', 'cities.json')
    if os.path.exists(src):
        os.makedirs(os.path.join(ctx.OUT, 'data'), exist_ok=True)
        shutil.copy(src, os.path.join(ctx.OUT, 'data', 'cities.json'))
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    dir_btns = ''.join(f'<button type="button" class="sk-dir" data-az="{i * 45}" aria-pressed="false">{d}</button>' for i, d in enumerate(dirs))
    sus = ''.join(f'<li><span class="sk-sico">{ctx.icon(ic)}</span><span><b>{E(n)}</b>{E(t)}</span></li>' for n, ic, t in SUSPECTS)
    head = (f'<link rel="stylesheet" href="{U("/static/tools.css")}"><link rel="stylesheet" href="{U("/static/skycheck.css")}">'
            '<script src="https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/astronomy.browser.min.js" defer></script>'
            '<script src="https://cdn.jsdelivr.net/npm/satellite.js@6.0.2/dist/satellite.min.js" defer></script>'
            f'<script src="{U("/static/skycheck.js")}" defer></script>')
    body = f'''
<section class="band band-dark tool-head">
  <div class="wrap">
    <p class="crumb"><a href="{U('/tools/')}">Tools</a> / Was it a planet?</p>
    <h1>Was it a planet?</h1>
    <p class="lede">Saw a bright light you couldn't explain? Tell us when and where, and which way you were looking. We'll show what was in that part of the sky:
    planets, the Moon, the brightest stars and, for recent nights, the Space Station.</p>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <form class="sk-form" data-cities="{U('/data/cities.json')}" data-base="{U('')}" onsubmit="return false">
    <div class="sk-row">
      <label>When did you see it?<input type="datetime-local" id="sk-when" required></label>
      <label class="sk-place">Where were you?<input type="text" id="sk-place" list="sk-cities" placeholder="Town or city" autocomplete="off">
        <datalist id="sk-cities"></datalist></label>
      <button type="button" class="btn btn-sm" id="sk-me">Use my location</button>
    </div>
    <fieldset class="sk-row"><legend>Which way were you looking? (optional)</legend><div class="sk-dirs">{dir_btns}</div></fieldset>
    <fieldset class="sk-row"><legend>How high was it? (optional)</legend><div class="sk-dirs sk-alt">
      <button type="button" class="sk-h" data-h="low" aria-pressed="false">Low, near the horizon</button>
      <button type="button" class="sk-h" data-h="mid" aria-pressed="false">Halfway up</button>
      <button type="button" class="sk-h" data-h="high" aria-pressed="false">High overhead</button></div></fieldset>
    <p class="sk-note">Times are on your device's clock ({'<span id="sk-tz">your time zone</span>'}). Your location never leaves your browser.</p>
    <button type="button" class="btn" id="sk-go">Check the sky</button>
  </form>
  <div class="sk-out" aria-live="polite" hidden>
    <h2 id="sk-h2">The sky at that moment</h2>
    <p id="sk-sum"></p>
    <div class="sk-wrap"><svg id="sk-dome" viewBox="-110 -110 220 220" role="img" aria-label="Sky map: the centre is straight overhead, the edge is the horizon"></svg>
    <ol id="sk-list" class="sk-list"></ol></div>
    <p class="small muted">Planet and star positions: astronomy-engine. Space Station orbit: Celestrak. Fast-moving things like planes, drones and lanterns can't be checked this way.</p>
    <p class="sk-next"><a class="btn" href="{U('/report/')}">Still can't explain it? Report it</a> <a class="btn btn-ghost-l" href="{U('/guides/skywatching/')}">Skywatching guide</a></p>
  </div>
  <noscript><p class="callout">This checker needs JavaScript. The list below covers the usual suspects.</p></noscript>
  <h2>The usual suspects</h2>
  <p>Most lights reported as UFOs turn out to be one of these. If yours matched none of them, it is worth <a href="{U('/report/')}">reporting</a>.</p>
  <ul class="sk-sus">{sus}</ul>
  <p>Want to rule things out on the spot? See the <a href="{U('/guides/skywatching/')}">skywatching guide</a>, the
  <a href="{U('/tools/what-did-i-see/')}">What did I see?</a> quiz, or browse <a href="{U('/ufo/canada/')}">Canadian sightings</a> and how investigators rated them.</p>
</div></div>'''
    ctx.write('/tools/was-it-a-planet/', ctx.page('/tools/was-it-a-planet/', 'Was it a planet? Check what was in the sky when you saw a UFO', body,
                                                  'Enter the time, place and direction of a strange light to see which planets, bright stars, the Moon or the Space Station were there.',
                                                  body_class='tools', head_extra=head))

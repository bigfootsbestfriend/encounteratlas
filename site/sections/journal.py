"""/journal/: a field journal for outings (stakeouts, hikes, skywatching nights), including the nights nothing happened.

Everything is stored on the visitor's device (IndexedDB, falling back to localStorage) by static/journal.js and is never
sent to us. The only outside call is Open-Meteo (free, no key) for the weather at the entry's time and place, with the
coordinates rounded to 0.01 degrees first. The moon phase is worked out in the browser.

The page is full HTML at load: the form, the "why log empty nights" piece in Mike's voice and the checklist all read fine
without JavaScript. journal.js only reads the saved entries and wires up the controls.
Place picker: OUT/data/cities.json (copied there by skycheck.py), the same town list /near-me/ uses.
"""
import json

LOOKING = [('ufo', 'UFOs'), ('creature', 'A creature'), ('out', 'Just out there')]
HAPPENED = [('nothing', 'Nothing'), ('heard', 'Heard something'), ('saw', 'Saw something')]
CONDITIONS = [(1, 'Rough'), (2, 'Poor'), (3, 'OK'), (4, 'Good'), (5, 'Perfect')]

CHECKLIST = [
    'The date, when you got there and how long you stayed',
    'Where you were, close enough that you could find the spot again',
    'The weather (cloud, wind, temperature, rain). The journal fills this in when you have a signal',
    'The moon. The journal works that one out for you too',
    'How many people were with you, and whether anyone had a dog along',
    'What you went out for',
    'Anything you heard, saw or smelled, even if it was probably a deer',
    'Anything that could explain it: planes, campfires, traffic, a train, other people in the bush',
    'How good the conditions were for spotting anything at all',
]


def build(ctx):
    E, U = ctx.esc, ctx.url

    def chips(name, opts, checked=None, legend='', cls=''):
        b = ''.join(f'<label class="jn-chip{(" jn-" + str(v)) if cls else ""}"><input type="radio" name="{name}" value="{v}"'
                    f'{" checked" if v == checked else ""}><span>{E(t)}</span></label>' for v, t in opts)
        return f'<fieldset class="jn-set"><legend>{E(legend)}</legend><div class="jn-chips">{b}</div></fieldset>'

    checklist = ''.join(f'<li>{E(x)}</li>' for x in CHECKLIST)
    cfg = json.dumps({'report': U('/report/'), 'cities': U('/data/cities.json')}, separators=(',', ':')).replace('</', '<\\/')

    body = f'''
<section class="band band-dark jn-head" data-area="journal-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/tools/')}">Tools</a> / Field journal</p>
    <h1>Field journal</h1>
    <p class="lede">A log for every night you go out looking, whether it's a stakeout, a hike or a night of skywatching, and yes, that includes the ones where nothing happened.
    It fills in the weather and the moon for you, and everything stays on your phone or computer. We never see it.</p>
  </div>
</section>

<section class="jn-tool" data-area="journal-form" aria-labelledby="jn-form-h">
  <div class="wrap">
    <form id="jn-form" class="jn-form" novalidate>
      <h2 id="jn-form-h">Log an outing</h2>
      <p class="jn-editing" id="jn-editing" hidden>Editing an entry. <button type="button" class="linkish" id="jn-cancel">Cancel</button></p>
      <div class="jn-row2">
        <div class="jn-field"><label for="jn-when">When did you head out?</label>
          <input type="datetime-local" id="jn-when" name="when" required></div>
        <div class="jn-field"><label for="jn-hours">How long were you out? <span class="opt">(hours)</span></label>
          <input type="number" id="jn-hours" name="hours" min="0" max="72" step="0.25" inputmode="decimal" placeholder="e.g. 2.5"></div>
      </div>
      <div class="jn-field">
        <label for="jn-place">Where were you?</label>
        <div class="jn-place-row">
          <input type="text" id="jn-place" name="place" list="jn-cities" maxlength="120" autocomplete="off" placeholder="Lake, trail, town or road">
          <datalist id="jn-cities"></datalist>
          <button type="button" class="btn btn-ghost jn-locate" id="jn-locate">Use my location</button>
        </div>
        <p class="jn-hint" id="jn-loc" aria-live="polite">Type a place, or use your location (rounded to about 1 km) so the journal can look up the weather.</p>
      </div>
      <div class="jn-field jn-narrow"><label for="jn-with">How many people were with you? <span class="opt">(0 if it was just you)</span></label>
        <input type="number" id="jn-with" name="with" min="0" max="99" step="1" value="0" inputmode="numeric"></div>
      {chips('looking', LOOKING, 'out', 'What were you looking for?')}
      {chips('happened', HAPPENED, 'nothing', 'What happened?', cls='h')}
      {chips('cond', CONDITIONS, 3, 'How good were conditions for spotting anything?')}
      <div class="jn-field"><label for="jn-notes">Notes</label>
        <textarea id="jn-notes" name="notes" rows="4" maxlength="4000" placeholder="What you did, where you sat, what you heard, what it probably was"></textarea></div>
      <div class="jn-sky" id="jn-sky" aria-live="polite">
        <p class="jn-moon" id="jn-moon"></p>
        <p class="jn-wx" id="jn-wx">Weather fills in here once there's a place and a time, if you have a signal.</p>
        <button type="button" class="linkish" id="jn-wx-btn" hidden>Try the weather again</button>
      </div>
      <div class="jn-send">
        <button type="submit" class="btn btn-big" id="jn-save">Save to my journal</button>
        <p class="jn-msg" id="jn-msg" role="status" aria-live="polite"></p>
      </div>
    </form>
  </div>
</section>

<section class="band band-mist jn-list-band" data-area="journal-list" aria-labelledby="jn-list-h">
  <div class="wrap">
    <h2 id="jn-list-h">Your journal</h2>
    <dl class="jn-stats" id="jn-stats">
      <div><dt>Nights out</dt><dd data-s="nights">0</dd></div>
      <div><dt>Hours</dt><dd data-s="hours">0</dd></div>
      <div><dt>Heard something</dt><dd data-s="heard">0</dd></div>
      <div><dt>Sightings</dt><dd data-s="saw">0</dd></div>
    </dl>
    <div class="jn-tools">
      <button type="button" class="btn btn-ghost-l btn-sm" id="jn-units" aria-pressed="false">Show &deg;F and mph</button>
      <button type="button" class="btn btn-ghost-l btn-sm" id="jn-csv">Export CSV</button>
      <button type="button" class="btn btn-ghost-l btn-sm" id="jn-json">Export JSON</button>
      <label class="btn btn-ghost-l btn-sm jn-import">Import JSON<input type="file" id="jn-file" accept=".json,application/json" class="visually-hidden"></label>
    </div>
    <p class="jn-msg" id="jn-list-msg" role="status" aria-live="polite"></p>
    <ol class="jn-entries" id="jn-entries" aria-label="Journal entries, newest first"></ol>
    <p class="jn-empty" id="jn-empty">Nothing logged yet on this device. Your first entry shows up here.</p>
    <noscript><p class="jn-empty">The journal needs JavaScript turned on to save entries. The checklist below works fine on paper.</p></noscript>
  </div>
</section>

<section class="band band-dark" data-area="journal-why">
  <div class="wrap jn-why">
    <div class="prose">
      <h2>Why write down the nights where nothing happened?</h2>
      <p>Here's the thing. If you only write down the nights something weird happened, your notes are going to make it look like something weird
      happens every time you go out. It doesn't. Most nights you sit in the dark, feed the mosquitoes and drive home.</p>
      <p>Those empty nights are what make the good ones mean anything. Say you've been out to the same lake 30 times and you heard knocks twice.
      That's a very different story than "I heard knocks at the lake" and anybody you tell is going to take you a lot more seriously if you can
      show them the other 28 nights too.</p>
      <p>It helps you as well. After a season of logging you can actually see when things happened (what time, what the moon was doing, what the
      weather was like) instead of going on memory, and memory is pretty bad at that stuff. Quick, what was the cloud cover three Saturdays ago?
      Exactly.</p>
      <p>Side note: this works the same way for skywatchers. A light you can't explain on a clear, moonless night counts for a lot more when you've got
      a pile of nights at the same spot where all you saw was planes and Starlink.</p>
    </div>
    <div class="jn-check">
      <h2>What to write down</h2>
      <ul class="signs">{checklist}</ul>
      <p>Write it the same night if you can. By the next morning a ten-second noise has a way of turning into a minute.</p>
    </div>
  </div>
</section>

<section class="band band-mist" data-area="journal-privacy">
  <div class="wrap prose">
    <h2>Your journal stays on your device</h2>
    <p>Everything you log here is saved in your browser on this phone or computer. Nothing gets sent to us and there's no account to make.
    The only thing that ever leaves your device is a weather lookup, and that's just the rough spot (rounded to about 1 km) and the date going to
    <a href="https://open-meteo.com/">Open-Meteo</a>, a free weather service. If you type a place that isn't in our town list, the name you typed goes
    to Open-Meteo's place search too, so it can find the spot. Your notes never do. The moon phase is worked out right on your device.</p>
    <p>The flip side is that if you clear your browser data or lose your phone, the journal goes with it. Hit <b>Export JSON</b> now and then
    and keep the file somewhere safe. You can bring it back (or move it to another device) with <b>Import JSON</b>. The CSV opens in any spreadsheet.</p>
    <p>If a night does turn into something, tap <b>Turn this into a report</b> on that entry and the <a href="{U('/report/')}">report form</a>
    opens with the place already filled in. A moderator reads every report before it goes on the map. Want to know whether that bright light was
    just Venus? Try <a href="{U('/tools/was-it-a-planet/')}">Was it a planet?</a> first.</p>
  </div>
</section>
<script type="application/json" id="jn-config">{cfg}</script>'''

    head = (f'<link rel="stylesheet" href="{U("/static/journal.css")}">'
            f'<script src="{U("/static/journal.js")}" defer></script>')
    ctx.write('/journal/', ctx.page('/journal/', 'Field journal for cryptid and UFO outings', body,
                                    'Log every stakeout, hike and skywatching night, even the empty ones. Weather and moon phase fill in for you, '
                                    'and it all stays on your device. Export to CSV or JSON.',
                                    body_class='journal', head_extra=head, viewport_fit=True, article={'published': '2026-10-24'}))

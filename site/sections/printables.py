"""Printables: /printables/after-an-encounter/, a two-page record sheet for anyone who has just had a sighting.

Plain HTML that prints cleanly (site-wide print CSS adds the Encounter Atlas header and footer). Linked from the
report page, every creature page's "Seen the ...?" box and the guides hub.
"""

FIELDS_1 = [
    ('When', ['Date', 'Time it started', 'How long it lasted']),
    ('Where', ['Place name or nearest town', 'GPS or what3words (phone maps: press and hold to drop a pin)', 'Terrain: woods, field, water, road, sky, home']),
    ('Conditions', ['Weather and light (moon, clouds, headlights, torch)', 'What you were doing just before']),
]
QUESTIONS = [
    'Describe what you saw, in order. Start with the very first thing that caught your attention.',
    'Size and shape, compared with something nearby (a door, a car, a tree, your hand at arm\'s length).',
    'Colour, surface, eyes or lights. Did anything glow or reflect?',
    'How did it move? How did it leave, and which way did it go?',
    'Sounds, smells, or anything you felt (cold, pressure, a sense of being watched).',
]


def build(ctx):
    e, u = ctx.esc, ctx.url
    lines = lambda n: '<span class="pr-lines">' + '<i></i>' * n + '</span>'
    grid = {'When': ' grid3', 'Conditions': ' grid2'}
    p1 = ''.join(f'<fieldset class="pr-set{grid.get(h, "")}"><legend>{e(h)}</legend>' + ''.join(f'<label>{e(x)}{lines(1)}</label>' for x in xs) + '</fieldset>' for h, xs in FIELDS_1)
    qs = ''.join(f'<div class="pr-q"><p>{i}. {e(q)}</p>{lines(4 if i == 1 else 2)}</div>' for i, q in enumerate(QUESTIONS, 1))
    body = f'''
<section class="band band-dark pr-head"><div class="wrap">
  <p class="crumb"><a href="{u('/guides/')}">Field guides</a> / Printables</p>
  <h1>After an encounter: your record sheet</h1>
  <p class="lede">Memory changes fast, especially after you talk it over or read other people's reports. Print this, keep it in the glovebox or your pack, and fill it in before you tell anyone. Then send it to us when you're ready.</p>
  <p class="pr-actions"><button type="button" class="btn" onclick="window.print()">Print the record sheet</button>
  <a class="btn btn-ghost" href="{u('/report/')}">Report it online instead</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
<article class="pr-sheet">
  <header class="pr-title"><h2>Encounter record sheet</h2><p>Fill this in as soon as you can, before you look anything up. Short notes are fine. Guesses are fine if you mark them as guesses.</p></header>
  {p1}
  <div class="pr-qs">{qs}</div>
  <div class="pr-page2">
    <div class="pr-q"><p>6. Sketch it. Add a person or a tree for scale and an arrow for the direction it went.</p><div class="pr-sketch"></div></div>
    <fieldset class="pr-set"><legend>Evidence</legend>
      <label>Photos or video taken (file names, times; keep the originals)<span class="pr-lines"><i></i><i></i></span></label>
      <label>Tracks, hair, marks or damage (measure, photograph with something for scale, don't move it)<span class="pr-lines"><i></i><i></i></span></label>
    </fieldset>
    <fieldset class="pr-set"><legend>Other witnesses</legend>
      <label>Who else saw or heard it, and how to reach them<span class="pr-lines"><i></i><i></i></span></label>
    </fieldset>
    <div class="pr-q"><p>7. What else could it have been? Write down anything you ruled out, and why.</p><span class="pr-lines"><i></i><i></i><i></i></span></div>
    <div class="pr-q"><p>8. How you felt then, and how you feel now.</p><span class="pr-lines"><i></i><i></i></span></div>
    <div class="pr-check"><p><b>Before you go back:</b></p>
      <ul><li>Tell someone where you're going and when to expect you</li><li>Same time of day, same weather if you can</li>
      <li>Note what's normal there: animals, lights, traffic, aircraft</li><li>Never approach anything that seems dangerous</li></ul></div>
    <div class="pr-send"><img src="{u('/static/qr-report.svg')}" alt="" width="96" height="96">
      <p><b>Send it to Encounter Atlas</b> Scan the code or go to encounteratlas.com/report. You can stay anonymous, and every report is read by a person before it goes on the map.</p></div>
    <p class="pr-sign">Written by ____________________________ &nbsp; on (date) ______________</p>
  </div>
</article>
</div></div>'''
    head = f'<link rel="stylesheet" href="{u("/static/printables.css")}">'
    ctx.write('/printables/after-an-encounter/', ctx.page('/printables/after-an-encounter/', 'Encounter record sheet: a printable for after a sighting', body,
              'A free printable record sheet for anyone who has just seen something strange: when, where, what it looked like, a sketch box and evidence notes.',
              body_class='printables', head_extra=head))

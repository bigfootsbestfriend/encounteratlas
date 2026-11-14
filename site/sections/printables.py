"""Printables: /printables/ hub, /printables/after-an-encounter/ (a two-page record sheet for anyone who has just had a
sighting), /printables/silhouettes/ and /printables/coloring-pages/ (files made by tools/make_printables.py from
data/printables.json and committed under site/static/printables/, because CI has no rsvg-convert).

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
    downloads(ctx)
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


SHORT_NAME = {'thylacine': 'Thylacine', 'grey-aliens': 'Grey alien'}


def downloads(ctx):
    import json, os
    e, u = ctx.esc, ctx.url
    cfg = json.load(open(os.path.join(ctx.ROOT, 'data', 'printables.json'), encoding='utf-8'))
    name = lambda s: SHORT_NAME.get(s) or ctx.by_slug[s]['name']
    head = f'<link rel="stylesheet" href="{u("/static/printables.css")}">'
    for key in ('silhouettes', 'coloring'):
        assert len(cfg[key]) % 2 == 0, f'printables {key}: keep the count even'
        for s in cfg[key]:  # the build has no rsvg-convert, so a missing file means tools/make_printables.py wasn't run
            f = f'silhouettes/{s}.png' if key == 'silhouettes' else f'coloring/{s}.pdf'
            assert os.path.exists(os.path.join(ctx.ROOT, 'site', 'static', 'printables', f)), f'run tools/make_printables.py ({f})'

    cards = ''.join(
        f'<div class="pd-card"><img src="{u("/static/art/" + s + ".svg")}" alt="{e(name(s))} silhouette" width="200" height="200" loading="lazy">'
        f'<b><a href="{u("/creatures/" + s + "/")}">{e(name(s))}</a></b>'
        f'<span class="pd-dl"><a href="{u("/static/art/" + s + ".svg")}" download="{s}-silhouette.svg">SVG</a>'
        f'<a href="{u("/static/printables/silhouettes/" + s + ".png")}" download="{s}-silhouette.png">PNG</a></span></div>' for s in cfg['silhouettes'])
    n = len(cfg['silhouettes'])
    body = f'''
<section class="band band-dark pr-head"><div class="wrap">
  <p class="crumb"><a href="{u('/printables/')}">Printables</a> / Silhouettes</p>
  <h1>Free cryptid silhouettes: Bigfoot, Mothman and {n - 2} more</h1>
  <p class="lede">These are the creature shapes we use all over this site, and you can have them. Every one comes as an SVG (the one you want for a Cricut, a laser cutter or vinyl decals, since it scales to any size) and as a big PNG with a see-through background.</p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <div class="pd-grid">{cards}</div>
  <div class="prose pd-note">
    <h2>What you can do with them</h2>
    <p>Use them for your own crafts, school projects, decals, stencils, pumpkin carving or a shirt you make for yourself. You don't have to credit us (a link back is nice if you post what you made). Please don't sell the files themselves or upload them to a clip-art site.</p>
    <p>The Bigfoot, Dogman, Loch Ness Monster, Jersey Devil and Yeti shapes come from a free pack by Logos By Nick, which allows personal and commercial use. We drew the rest for Encounter Atlas.</p>
    <p>Want something to colour in? There are <a href="{u('/printables/coloring-pages/')}">outline versions you can print</a> too.</p>
  </div>
</div></div>'''
    ctx.write('/printables/silhouettes/', ctx.page('/printables/silhouettes/', f'Free cryptid silhouettes (SVG and PNG): Bigfoot, Mothman, Nessie and {n - 3} more', body,
              f'{n} free cryptid and UFO silhouettes to download as SVG or transparent PNG, including Bigfoot, Mothman, the Loch Ness Monster, the Jersey Devil and a flying saucer.',
              body_class='printables', head_extra=head))

    allpdf = u('/static/printables/coloring/encounter-atlas-coloring-pages.pdf')
    cards = ''.join(
        f'<div class="pd-card pd-sheet"><img src="{u("/static/printables/coloring/" + s + ".svg")}" alt="{e(name(s))} colouring page" width="200" height="200" loading="lazy">'
        f'<b>{e(name(s))}</b><span class="pd-dl"><a href="{u("/static/printables/coloring/" + s + ".pdf")}" download="{s}-coloring-page.pdf">Print (PDF)</a>'
        f'<a href="{u("/creatures/" + s + "/")}">Who is it?</a></span></div>' for s in cfg['coloring'])
    n = len(cfg['coloring'])
    body = f'''
<section class="band band-dark pr-head"><div class="wrap">
  <p class="crumb"><a href="{u('/printables/')}">Printables</a> / Colouring pages</p>
  <h1>Cryptid colouring pages: Bigfoot, Mothman and friends</h1>
  <p class="lede">{n} free colouring pages (or coloring pages, if you spell it the American way) to print at home. Each one is a big, simple outline on a single letter-size page, so it works for little kids with fat markers and for anybody who wants to draw in their own fur, scales and glowing red eyes.</p>
  <p class="pr-actions"><a class="btn" href="{allpdf}" download>Download all {n} in one PDF</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <div class="pd-grid">{cards}</div>
  <div class="prose pd-note">
    <h2>Printing tips</h2>
    <p>The pages are US letter size and print fine on A4 if you pick "fit to page" in the print box. They're plain outlines with nothing filled in, so add a forest, a lake or a startled camper around them (the Hodag looks great in green, for what it's worth).</p>
    <p>They're free for home, classrooms, libraries and scout nights, and you can print as many copies as you need. Teachers might also like the <a href="{u('/printables/judge-a-ufo-report/')}">UFO evidence worksheet</a>. If you want the solid shapes for cutting or decals, grab the <a href="{u('/printables/silhouettes/')}">silhouettes</a>.</p>
  </div>
</div></div>'''
    ctx.write('/printables/coloring-pages/', ctx.page('/printables/coloring-pages/', 'Free cryptid colouring pages to print: Bigfoot, Mothman, Nessie (coloring pages)', body,
              f'{n} free printable cryptid colouring pages (coloring pages) as PDFs: Bigfoot, Mothman, the Loch Ness Monster, the Jersey Devil, a Yeti, a grey alien and a flying saucer.',
              body_class='printables', head_extra=head))

    hub = [('/printables/coloring-pages/', 'footprint', 'Colouring pages', f'{n} big outline pages to print, from Bigfoot to a flying saucer.'),
           ('/printables/silhouettes/', 'hominid', 'Silhouettes', f'{len(cfg["silhouettes"])} creature shapes as SVG and PNG for crafts, decals and stencils.'),
           ('/printables/after-an-encounter/', 'clipboard', 'Encounter record sheet', 'Two pages to fill in right after a sighting, before the details fade.'),
           ('/printables/judge-a-ufo-report/', 'saucer', 'Be the investigator', 'A classroom worksheet on judging the evidence in a UFO report.')]
    cards = ''.join(f'<a class="pd-hub" href="{u(p)}">{ctx.icon(ic, "ico")}<span><b>{e(t)}</b><small>{e(d)}</small></span></a>' for p, ic, t, d in hub)
    body = f'''
<section class="band band-dark pr-head"><div class="wrap">
  <p class="crumb">Printables</p>
  <h1>Free cryptid and UFO printables</h1>
  <p class="lede">Everything here is free to print or download. There's stuff for kids, for crafters and for anybody who has just seen something strange and wants to get it on paper.</p>
</div></section>
<div class="band band-mist"><div class="wrap"><div class="pd-hubs">{cards}</div></div></div>'''
    ctx.write('/printables/', ctx.page('/printables/', 'Free cryptid and UFO printables: colouring pages, silhouettes, worksheets', body,
              'Free cryptid and UFO printables: colouring pages, SVG and PNG silhouettes, an encounter record sheet and a classroom UFO evidence worksheet.',
              body_class='printables', head_extra=head))

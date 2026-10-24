"""Field guides: /guides/ hub plus one page per guide.

Metadata lives in data/guides.json, the body of each guide in data/guides/<slug>.html.
Fragments can use a few placeholders, resolved here:
  {{url:/path/}}     site URL (adds the GitHub Pages base path)
  {{guide:slug}}     URL of another guide
  {{icon:name}}      inline hand-drawn icon from site/static/icons
Every <h2 id="..."> becomes an entry in the page's table of contents (data-toc="..." gives a shorter label).
Every <li class="ck"> becomes a tickable checklist item that remembers its state in the browser.
A <div class="g-checklist" id="..."> gets a "Print this list" button that prints only that list.
"""
import json, os, re, urllib.parse

SCRIPT = '''<script>
(function () {
  var key = 'ea-guide:' + location.pathname + ':';
  document.querySelectorAll('.g-checklist input[type=checkbox]').forEach(function (b) {
    try { b.checked = localStorage.getItem(key + b.id) === '1'; } catch (e) {}
    b.addEventListener('change', function () {
      try { b.checked ? localStorage.setItem(key + b.id, '1') : localStorage.removeItem(key + b.id); } catch (e) {}
    });
  });
  document.addEventListener('click', function (e) {
    var p = e.target.closest('[data-print]'), c = e.target.closest('[data-clear]');
    if (p) {
      var t = document.getElementById(p.getAttribute('data-print'));
      if (!t) return;
      t.classList.add('print-target'); document.body.classList.add('print-one');
      window.print();
      setTimeout(function () { t.classList.remove('print-target'); document.body.classList.remove('print-one'); }, 500);
    }
    if (c) {
      document.getElementById(c.getAttribute('data-clear')).querySelectorAll('input[type=checkbox]').forEach(function (b) {
        b.checked = false; try { localStorage.removeItem(key + b.id); } catch (e) {}
      });
    }
  });
})();
</script>'''


def build(ctx):
    root = ctx.ROOT
    guides = json.load(open(os.path.join(root, 'data', 'guides.json')))
    by_slug = {g['slug']: g for g in guides}
    head = f'<link rel="stylesheet" href="{ctx.url("/static/guides.css")}">'

    def gurl(slug):
        return ctx.url(f'/guides/{slug}/')

    def render(src, slug):
        src = re.sub(r'\{\{url:([^}]+)\}\}', lambda m: ctx.url(m.group(1)), src)
        src = re.sub(r'\{\{guide:([^}]+)\}\}', lambda m: gurl(m.group(1)), src)
        src = re.sub(r'\{\{icon:([a-z0-9-]+)\}\}', lambda m: ctx.icon(m.group(1), 'ico ico-inline'), src)
        src = re.sub(r'\{\{diagram:([a-z0-9-]+)\}\}', lambda m: open(os.path.join(ctx.ROOT, 'data', 'guides', 'diagrams', m.group(1) + '.svg'), encoding='utf-8').read(), src)
        n = [0]

        def ck(m):
            n[0] += 1
            i = f'ck-{n[0]}'
            return f'<li><label for="{i}"><input type="checkbox" id="{i}"><span>{m.group(1)}</span></label></li>'
        src = re.sub(r'<li class="ck">(.*?)</li>', ck, src, flags=re.S)

        def cl(m):
            cid, title = m.group(1), m.group(2)
            return (f'<div class="g-checklist" id="{cid}"><div class="g-cl-head"><h3>{title}</h3>'
                    f'<div class="g-cl-tools"><button type="button" class="g-tool" data-print="{cid}">Print this list</button>'
                    f'<button type="button" class="g-tool g-tool-quiet" data-clear="{cid}">Clear ticks</button></div></div>')
        src = re.sub(r'<div class="g-checklist" id="([^"]+)" data-title="([^"]+)">', cl, src)
        return src

    def words(html_src):
        txt = re.sub(r'<svg.*?</svg>', ' ', html_src, flags=re.S)
        txt = re.sub(r'<[^>]+>', ' ', txt)
        return len(re.findall(r"[A-Za-z0-9'’]+", txt))

    def toc(html_src):
        items = []
        for m in re.finditer(r'<h2 id="([^"]+)"([^>]*)>(.*?)</h2>', html_src, flags=re.S):
            short = re.search(r'data-toc="([^"]+)"', m.group(2))
            label = short.group(1) if short else re.sub(r'<[^>]+>', '', m.group(3))
            items.append(f'<li><a href="#{m.group(1)}">{label}</a></li>')
        return ''.join(items)

    def card(g, big=False):
        return (f'<a class="g-card{" g-card-big" if big else ""} tone-{g["tone"]}" href="{gurl(g["slug"])}">'
                f'<span class="g-card-ico">{ctx.icon(g["icon"])}</span>'
                f'<span class="g-card-txt"><span class="g-card-kick">{ctx.esc(g["kicker"])}</span>'
                f'<span class="g-card-h">{ctx.esc(g["short"])}</span>'
                f'<span class="g-card-p">{ctx.esc(g["blurb"])}</span>'
                f'<span class="g-card-meta">{g["_mins"]} min read{" · printable checklist" if g.get("printable") else ""}</span></span></a>')

    stats = []
    for g in guides:
        src = open(os.path.join(root, 'data', 'guides', g['slug'] + '.html'), encoding='utf-8').read()
        g['_src'] = src
        g['_words'] = words(src)
        g['_mins'] = max(2, round(g['_words'] / 230))
        stats.append((g['slug'], g['_words']))

    GEAR_LINKS = {  # (guide, section id) -> (gear section, what it covers)
        ('bigfoot-expedition', 'gear'): ('', 'every item on this list, with why it matters'),
        ('bigfoot-expedition', 'cameras'): ('trail-cameras', 'trail cameras, security boxes and batteries'),
        ('bigfoot-expedition', 'audio'): ('audio', 'recorders and parabolic mics'),
        ('bigfoot-expedition', 'night'): ('night-vision', 'thermal and night vision'),
        ('bigfoot-expedition', 'safety'): ('camping', 'first aid, bear spray and satellite messengers'),
        ('casting-tracks', 'materials'): ('casting', 'dental stone, plaster and scale rulers'),
        ('casting-tracks', 'kit'): ('casting', 'the casting kit'),
        ('dogman-and-night-encounters', 'document'): ('night-vision', 'thermal and night vision'),
        ('dogman-and-night-encounters', 'safety'): ('camping', 'safety gear'),
        ('skywatching', 'tools'): ('skywatching', 'planispheres, astronomy binoculars and telescopes'),
        ('skywatching', 'camera'): ('skywatching', 'tripods for night shots'),
        ('trail-cameras', 'choose'): ('trail-cameras', 'trail cameras worth buying'),
        ('trail-cameras', 'power'): ('trail-cameras', 'lithium batteries and high-endurance cards'),
        ('trail-cameras', 'theft'): ('trail-cameras', 'security boxes and cable locks'),
        ('how-to-report', 'evidence'): ('audio', 'recorders and cameras'),
    }

    def gear_links(html_src, slug):
        # Add a short "Gear for this" line at the end of each matching section (just before the next <h2>, or the end).
        heads = [(m.start(), m.group(1)) for m in re.finditer(r'<h2 id="([^"]+)"', html_src)]
        for k, (pos, sid) in reversed(list(enumerate(heads))):
            if (slug, sid) not in GEAR_LINKS:
                continue
            anchor, what = GEAR_LINKS[(slug, sid)]
            end = heads[k + 1][0] if k + 1 < len(heads) else len(html_src)
            link = (f'<p class="g-gearlink">{ctx.icon("q-pin", "ico ico-inline")} Gear for this: '
                    f'<a href="{ctx.url("/gear/")}{"#" + anchor if anchor else ""}">{ctx.esc(what)}</a></p>\n')
            html_src = html_src[:end] + link + html_src[end:]
        return html_src

    # Inline Amazon links on the first mention of each piece of gear (outside links, headings and diagrams), plus a
    # "Recommended gear" box above each guide's first checklist. Tagged search links; static/amz.js handles Canada.
    AMZ = lambda q: 'https://www.amazon.com/s?' + urllib.parse.urlencode({'k': q, 'tag': 'encountersatlas-20'})
    SPON = 'rel="sponsored nofollow noopener" target="_blank"'
    GEAR_TERMS = [
        (r'cellular (?:trail )?cameras?', 'cellular trail camera'), (r'trail cam(?:era)?s?', 'trail camera'),
        (r'red[- ]light headlamps?|headlamps?|head ?torch(?:es)?', 'red light headlamp'),
        (r'dental stone', 'dental stone casting'), (r'plaster of Paris', 'plaster of paris'),
        (r'parabolic (?:mic|microphone)s?', 'parabolic microphone'),
        (r'(?:digital |handheld )?(?:audio |voice )recorders?', 'handheld digital audio recorder'),
        (r'bear spray', 'bear spray'), (r'thermal (?:scope|imager|monocular|camera)s?', 'thermal monocular'),
        (r'night[- ]vision (?:scope|monocular|device|camera)s?', 'digital night vision monocular'),
        (r'binoculars', '10x42 binoculars'), (r'satellite messengers?|inReach', 'satellite messenger'),
        (r'first[- ]aid kits?', 'hiking first aid kit'), (r'(?<!phone )(?<!phone\'s )compass(?!es\b)', 'baseplate compass'),
        (r'tripods?', 'phone tripod'), (r'lithium (?:AA )?batteries', 'lithium aa batteries'),
        (r'(?:SD|memory) cards?', 'high endurance sd card'), (r'security box(?:es)?|lock ?box(?:es)?', 'trail camera security box'),
        (r'cable locks?', 'python cable lock'), (r'tape measures?', 'tape measure'), (r'planisphere', 'planisphere'),
        (r'two-way radios?|walkie-talkies?', 'two way radios'), (r'hand ?warmers', 'hand warmers'),
        (r'GPS units?|handheld GPS', 'handheld gps'), (r'power banks?|battery packs?', 'power bank'),
        (r'nitrile gloves', 'nitrile gloves'), (r'tweezers', 'tweezers'),
    ]
    SKIP = {'a', 'h1', 'h2', 'h3', 'svg', 'title', 'figcaption', 'button', 'th'}

    def amazon_links(html_src):
        used, depth, out = set(), {}, []
        for part in re.split(r'(<[^>]+>)', html_src):
            if part.startswith('<'):
                m = re.match(r'<(/?)([a-zA-Z0-9]+)', part)
                if m and m.group(2).lower() in SKIP and not part.endswith('/>'):
                    k = m.group(2).lower()
                    depth[k] = depth.get(k, 0) + (-1 if m.group(1) else 1)
                out.append(part)
                continue
            if any(v > 0 for v in depth.values()) or not part.strip():
                out.append(part)
                continue
            for pat, q in GEAR_TERMS:
                if q in used:
                    continue
                mm = re.search(r'\b(' + pat + r')\b', part, flags=re.I)
                if mm:
                    used.add(q)
                    part = part[:mm.start()] + f'<a class="g-amz" href="{ctx.esc(AMZ(q))}" {SPON}>{mm.group(1)}</a>' + part[mm.end():]
            out.append(part)
        return ''.join(out)

    REC = {
        'bigfoot-expedition': [('No-glow trail camera', 'no glow trail camera', 'Watches the spot for weeks without flashing.'),
                               ('Red-light headlamp', 'red light headlamp', 'Keeps your night vision.'),
                               ('Handheld audio recorder', 'handheld digital audio recorder', 'Captures knocks and calls all night.'),
                               ('Thermal monocular', 'thermal monocular', 'Sees body heat in total darkness.'),
                               ('Two-way radios', 'two way radios', 'Check-ins where phones have no signal.'),
                               ('Bear spray', 'bear spray', 'The safety item that actually gets used.'),
                               ('Satellite messenger', 'satellite messenger', 'SOS and texts with no cell service.'),
                               ('Dental stone', 'dental stone casting', 'For casting any track you find.')],
        'skywatching': [('Astronomy binoculars', '15x70 astronomy binoculars', 'Turns a dot into a shape.'),
                        ('Planisphere', 'planisphere', 'Rules out bright stars and planets.'),
                        ('Phone tripod with remote', 'phone tripod bluetooth remote', 'Steady long exposures.'),
                        ('Red flashlight', 'red flashlight astronomy', 'Read notes without losing dark eyes.'),
                        ('Zero-gravity chair', 'zero gravity chair', 'Hours of looking up without a sore neck.'),
                        ('Hand warmers', 'hand warmers', 'Clear nights are cold nights.')],
        'dogman-and-night-encounters': [('Red-light headlamp', 'red light headlamp', 'See your feet, not just the dark.'),
                                        ('Thermal monocular', 'thermal monocular', 'Tells a deer from something else.'),
                                        ('Handheld audio recorder', 'handheld digital audio recorder', 'Proof of what you heard.'),
                                        ('Bear spray', 'bear spray', 'Works on anything with a nose.'),
                                        ('Two-way radios', 'two way radios', 'Stay in touch at night.'),
                                        ('Satellite messenger', 'satellite messenger', 'For when it goes wrong.')],
        'trail-cameras': [('No-glow trail camera', 'no glow trail camera', 'Invisible flash at night.'),
                          ('Cellular trail camera', 'cellular trail camera', 'Photos straight to your phone.'),
                          ('Security box', 'trail camera security box', 'Stops bears and thieves.'),
                          ('Python cable lock', 'python cable lock', 'Locks the box to the tree.'),
                          ('Lithium AA batteries', 'lithium aa batteries', 'Months of power, even in the cold.'),
                          ('High-endurance SD cards', 'high endurance sd card 32gb', 'Built for constant writing.'),
                          ('SD card reader for phones', 'sd card reader for phone', 'Check photos in the field.')],
        'casting-tracks': [('Dental stone', 'dental stone casting', 'Harder and sharper than plaster.'),
                           ('Photo scale ruler', 'forensic photo scale ruler', 'A scale in every photo.'),
                           ('Tape measure', 'tape measure', 'For step, stride and straddle.'),
                           ('Heavy zip bags', 'gallon freezer bags heavy duty', 'Mix the stone right in the bag.'),
                           ('Aluminium flashing', 'aluminum flashing roll', 'Makes a quick dam ring.'),
                           ('Folding trowel', 'folding trowel', 'Lift the cast from underneath.')],
        'how-to-report': [('Handheld audio recorder', 'handheld digital audio recorder', 'Record your account while it is fresh.'),
                          ('Photo scale ruler', 'forensic photo scale ruler', 'Makes photos measurable.'),
                          ('Tape measure', 'tape measure', 'Distances and sizes in real numbers.'),
                          ('All-weather notebook', 'rite in the rain notebook', 'Writes in rain and cold.'),
                          ('Handheld GPS', 'handheld gps', 'An exact spot, even off-grid.')],
    }

    def rec_box(html_src, slug):
        items = REC.get(slug)
        m = re.search(r'<[a-z]+[^>]*class="g-checklist', html_src)
        if not items or not m:
            return html_src
        lis = ''.join(f'<li><a href="{ctx.esc(AMZ(q))}" {SPON}>{ctx.esc(n)}</a><span>{ctx.esc(w)}</span></li>' for n, q, w in items)
        box = (f'<aside class="g-rec"><p class="g-rec-h">Recommended gear <a class="md-aff" href="{ctx.url("/privacy/")}#affiliate">(affiliate links)</a></p>'
               f'<ul>{lis}</ul><p class="g-rec-all"><a href="{ctx.url("/gear/")}">All field gear</a></p></aside>\n')
        return html_src[:m.start()] + box + html_src[m.start():]

    for g in guides:
        body_html = rec_box(amazon_links(gear_links(render(g['_src'], g['slug']), g['slug'])), g['slug'])
        rel = ''.join(card(by_slug[s]) for s in g.get('related', []) if s in by_slug)
        crits = ''.join(ctx.creature_card(ctx.by_slug[s]) for s in g.get('creatures', []) if s in ctx.by_slug)
        printable = ('<span class="g-chip">Printable checklists</span>' if g.get('printable') else '')
        body = f'''
<section class="band band-dark g-hero tone-{g['tone']}">
  <div class="wrap g-hero-in">
    <span class="g-hero-ico">{ctx.icon(g['icon'])}</span>
    <div>
      <p class="crumb"><a href="{ctx.url('/guides/')}">Field guides</a> / {ctx.esc(g['kicker'])}</p>
      <h1>{ctx.esc(g['title'])}</h1>
      <p class="lede">{ctx.esc(g['lede'])}</p>
      <p class="g-meta"><span class="g-chip">{g['_mins']} min read</span>{printable}</p>
    </div>
  </div>
</section>
<div class="band band-mist g-main"><div class="wrap g-layout">
  <nav class="g-toc" aria-label="On this page"><p class="g-toc-h">On this page</p><ol>{toc(body_html)}</ol>
    <p class="g-toc-foot"><a href="{ctx.url('/report/')}">Report an encounter</a></p></nav>
  <article class="prose g-body">
{body_html}
  </article>
</div></div>
<div class="band band-dark g-more"><div class="wrap">
  <h2>More field guides</h2>
  <div class="g-grid">{rel}</div>
  {f'<h2>Who you might be looking for</h2><div class="crit-grid">{crits}</div>' if crits else ''}
</div></div>
{SCRIPT if 'g-checklist' in body_html else ''}'''
        path = f'/guides/{g["slug"]}/'
        ctx.write(path, ctx.page(path, g['seo'], body, g['desc'], body_class='guide', head_extra=head, article={'updated': g.get('updated_iso')}))

    flagship = guides[0]
    rest = ''.join(card(g) for g in guides[1:])
    kits = ''.join(f'<li><a href="{gurl(g["slug"])}#{k["id"]}">{ctx.esc(k["name"])}</a> <span class="muted">{ctx.esc(g["short"])}</span></li>'
                   for g in guides for k in g.get('kits', []))
    body = f'''
<section class="band band-dark g-hub-head">
  <div class="wrap g-hub-in">
    <div class="g-hub-icons" aria-hidden="true">{''.join(f'<span class="tone-{t}">{ctx.icon(i)}</span>' for i, t in [('footprint', 'other'), ('trailcam', 'entity'), ('eyeshine', 'canid'), ('telescope', 'ufo'), ('recorder', 'hominid'), ('clipboard', 'winged')])}</div>
    <p class="crumb">Field guides</p>
    <h1>Field guides for the curious</h1>
    <p class="lede">How to go looking, safely and properly: the gear, the settings, the ways to rule out the ordinary, and how to bring back evidence that holds up. Written for people who actually go out there.</p>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  {card(flagship, big=True)}
  <div class="g-grid">{rest}
    <a class="g-card g-card-cta" href="{ctx.url('/report/')}"><span class="g-card-txt"><span class="g-card-kick">Back from the woods?</span>
      <span class="g-card-h">Report an encounter</span><span class="g-card-p">Tell us what you saw or heard, and put it on the map.</span>
      <span class="g-card-go">Report it &rarr;</span></span></a>
  </div>
  <div class="g-hub-split">
    <section>
      <h2>Printable kits</h2>
      <p>Tick them off on your phone (your ticks are remembered on this device) or print them for the truck.</p>
      <p><a class="btn" href="{ctx.url('/printables/after-an-encounter/')}">Encounter record sheet</a> For right after a sighting: what to write down before you forget.</p>
      <ul class="g-kits">{kits}</ul>
    </section>
    <section class="g-rules-card">
      <h2>Five rules for every trip</h2>
      <ol class="g-steps g-steps-sm">
        <li><strong>Tell someone your plan</strong> and when to raise the alarm.</li>
        <li><strong>Know whose land it is</strong> and check the rules for it.</li>
        <li><strong>Know if it's hunting season.</strong> Wear blaze orange if it is.</li>
        <li><strong>Leave no trace</strong> and never harass wildlife or people.</li>
        <li><strong>Write it down right away,</strong> before you talk it over or read other reports.</li>
      </ol>
    </section>
  </div>
</div></div>'''
    ctx.write('/guides/', ctx.page('/guides/', 'Field guides: Bigfoot expeditions, skywatching, trail cams and more', body,
                                   'Practical field guides for Bigfoot research, UFO skywatching, night encounters, trail cameras, casting tracks and reporting what you saw.',
                                   body_class='guide', head_extra=head))
    import sys
    print('guides: ' + ', '.join(f'{s} {w}w' for s, w in stats), file=sys.stderr)

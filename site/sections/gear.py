"""Field gear hub (/gear/): what to pack, by job, with a one-line reason for each item.

Links are Amazon searches (always the current models) with the Associates tag; static/amz.js sends Canadian visitors
to amazon.ca at click time. Books and documentaries come from data/media.json (checked by tools/verify_media.py).
Section ids are linked from the guides (guides.py GEAR_LINKS), the creature pages, places and the report page.
"""
import json, os, urllib.parse

TAG = 'encountersatlas-20'

SECTIONS = [
    ('trail-cameras', 'trailcam', 'Trail cameras', 'Your eyes in the woods while you sleep. Most of the best cryptid photos people send in come from these.', [
        ('No-glow trail camera', 'no glow trail camera', "Invisible infrared flash, so animals (and thieves) don't see it fire."),
        ('Cellular trail camera', 'cellular trail camera', 'Sends each photo to your phone, so you know the moment something walks by.'),
        ('Security box and cable lock', 'trail camera security box cable lock', 'Bears chew cameras and people steal them. A steel box stops both.'),
        ('High-endurance SD cards', 'high endurance sd card 32gb', 'Built for constant rewriting; cheap cards fail in the cold.'),
        ('Lithium AA batteries', 'lithium aa batteries', 'Last months longer than alkalines and keep working below freezing.'),
    ]),
    ('night-vision', 'eyeshine', 'Night vision and thermal', 'Most encounters happen after dark. These let you see what made the noise.', [
        ('Thermal monocular', 'thermal monocular', 'Shows body heat through total darkness and brush: the single most useful night tool.'),
        ('Digital night vision monocular', 'digital night vision monocular', 'Cheaper than thermal and records video, but needs its infrared light.'),
        ('Red-light headlamp', 'red light headlamp', "Keeps your night vision and doesn't light up the whole hillside."),
    ]),
    ('audio', 'recorder', 'Audio recorders', 'Howls, knocks and whoops are the most common evidence. A phone mic misses most of it.', [
        ('Handheld digital audio recorder', 'handheld digital audio recorder', 'Records clean, timestamped sound all night on one set of batteries.'),
        ('Parabolic microphone', 'parabolic microphone', 'Pulls in distant calls and wood knocks from across a valley.'),
        ('Furry wind muff', 'microphone windscreen deadcat', 'Wind noise ruins more night recordings than anything else.'),
    ]),
    ('casting', 'footprint', 'Track casting', 'A good cast of a print is evidence you can hand to a scientist. Our casting guide shows how.', [
        ('Dental stone', 'dental stone casting', 'Harder and more detailed than plaster of Paris; what trackers prefer.'),
        ('Plaster of Paris', 'plaster of paris', 'Fine for a first try and easy to find.'),
        ('Photo scale ruler', 'forensic photo scale ruler', 'Put a scale in every track photo, or the size can never be checked.'),
        ('Folding trowel', 'folding trowel', 'To lift a cast cleanly once it has set.'),
    ]),
    ('binoculars', 'telescope', 'Binoculars', 'For a hump on the lake, a shape on the ridge or a light that might be a plane.', [
        ('10x42 binoculars', '10x42 binoculars', 'The all-round size: bright enough for dusk, light enough to carry all day.'),
        ('Waterproof binoculars', 'waterproof binoculars', 'For lake and sea watching from a boat or a wet shoreline.'),
        ('Image-stabilised binoculars', 'image stabilized binoculars', 'Rock-steady views of a distant light or a moving shape.'),
    ]),
    ('skywatching', 'q-sky', 'Skywatching', 'Most UFO reports turn out to be planets, satellites or planes. These help you rule them out fast.', [
        ('Planisphere', 'planisphere', "Tells you which bright 'star' is really Venus or Jupiter."),
        ('Astronomy binoculars', '15x70 astronomy binoculars', 'Big lenses for faint lights; pair with a tripod adapter.'),
        ('Beginner Dobsonian telescope', 'dobsonian telescope beginner', 'Best value for seeing more of the sky, and for ruling out planets and satellites.'),
        ('Phone tripod with remote', 'phone tripod bluetooth remote', 'Long night exposures without the shake.'),
    ]),
    ('camping', 'woods', 'Camping and safety', 'Nobody finds anything if they get lost or hurt. Pack these before anything else.', [
        ('Hiking first aid kit', 'hiking first aid kit', 'Sprains and cuts are far more likely than monsters.'),
        ('Bear spray', 'bear spray', 'Essential in bear country; practise with the holster before you need it.'),
        ('Satellite messenger', 'satellite messenger', "Texts and SOS where there's no cell signal."),
        ('Baseplate compass', 'baseplate compass', 'Works when your phone battery dies.'),
        ('Emergency bivvy', 'emergency bivvy', 'Weighs almost nothing and can save a night out gone wrong.'),
    ]),
]
APPS = [('Stellarium', 'https://stellarium.org/', 'free planetarium: what is that bright light?'),
        ('Heavens-Above', 'https://www.heavens-above.com/', 'satellite and Starlink pass times'),
        ('Flightradar24', 'https://www.flightradar24.com/', 'planes overhead right now')]


def amz(q, index=''):
    return 'https://www.amazon.com/s?' + urllib.parse.urlencode({'k': q, **({'i': index} if index else {}), 'tag': TAG})


SPONSORED = 'rel="sponsored nofollow noopener" target="_blank"'


def build(ctx):
    E, U = ctx.esc, ctx.url
    p = os.path.join(ctx.ROOT, 'data', 'media.json')
    media = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'books': [], 'docs': []}
    toc = ''.join(f'<a class="md-chip" href="#{sid}">{E(t)}</a>' for sid, _, t, _, _ in SECTIONS) + '<a class="md-chip" href="#reading">Books and documentaries</a>'
    secs = ''
    for i, (sid, ico, title, why, items) in enumerate(SECTIONS):
        cards = ''.join(f'<a class="md-book tone-{(i + j) % 5}" href="{E(amz(q))}" {SPONSORED}><span class="md-spine" aria-hidden="true"></span>'
                        f'<span class="md-txt"><b>{E(n)}</b><small>{E(w)}</small><span class="md-go">See options on Amazon</span></span></a>'
                        for j, (n, q, w) in enumerate(items))
        extra = ''
        if sid == 'skywatching':
            extra = ('<p class="gr-apps"><b>Free apps:</b> ' + ' · '.join(f'<a href="{u}" rel="noopener nofollow" target="_blank">{E(n)}</a> ({E(d)})' for n, u, d in APPS)
                     + f'. See the <a href="{U("/guides/skywatching/")}#tools">skywatching guide</a> for how to use them.</p>')
        secs += (f'<section class="gr-sec" id="{sid}"><h2><span class="gr-ico">{ctx.icon(ico)}</span>{E(title)}</h2><p class="gr-why">{E(why)}</p>'
                 f'<div class="md-grid">{cards}</div>{extra}</section>')
    pick = lambda tags: [b for b in media['books'] if any(t in b['for'] for t in tags)]
    seen, books = set(), []
    for b in pick(['@general']) + pick(['@hominid']) + pick(['@lake', '@sea']) + pick(['@ufo']):
        if b['title'] not in seen:
            seen.add(b['title'])
            books.append(b)
    bcards = ''.join(f'<a class="md-book tone-{j % 5}" href="{E(amz(b["title"] + " " + b["author"].split(",")[0], "stripbooks"))}" {SPONSORED}>'
                     f'<span class="md-spine" aria-hidden="true"></span><span class="md-txt"><b>{E(b["title"])}</b><small>{E(b["author"].split(",")[0])}</small>'
                     f'<span class="md-go">Find it on Amazon</span></span></a>' for j, b in enumerate(books[:9]))
    dcards = ''.join(f'<div class="md-doc"><span class="md-ico">{ctx.icon("ufo-film")}</span><span class="md-txt"><b>{E(d["title"])}</b><small>{d["year"]} · {E(d["blurb"])}</small>'
                     f'<span class="md-links"><a href="{E(amz(d["title"] + " " + str(d["year"]), "instant-video"))}" {SPONSORED}>Watch on Amazon</a>'
                     f'<a href="https://www.justwatch.com/us/search?q={urllib.parse.quote(d["title"])}" rel="noopener nofollow" target="_blank">Where to stream</a></span></span></div>'
                     for d in media['docs'])
    body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{U('/guides/')}">Field guides</a> / Gear</p>
  <h1>Field gear for investigators</h1>
  <p class="lede">What to pack for a night in the woods, a lake watch or a skywatch, and why each thing earns its place. Read the
  <a href="{U('/guides/')}">field guides</a> for how to use it.</p>
</div></section>
<div class="band band-mist md-band gr-page"><div class="wrap">
  <nav class="md-chips gr-toc" aria-label="Gear sections">{toc}</nav>
  {secs}
  <section class="gr-sec" id="reading"><h2><span class="gr-ico">{ctx.icon('folder')}</span>Books and documentaries</h2>
    <p class="gr-why">The best general reads, sceptical and believing. Every creature page also lists books about that creature.</p>
    <div class="md-grid">{bcards}</div>
    <h3>Documentaries</h3><div class="md-grid">{dcards}</div></section>
  <p class="md-disc">As an Amazon Associate we earn from qualifying purchases. Gear links go to Amazon searches so you see current models and prices;
  we don't take payment to list anything. <a href="{U('/privacy/')}#affiliate">More about our links</a>.</p>
</div></div>'''
    ctx.write('/gear/', ctx.page('/gear/', 'Field gear for cryptid and UFO investigators', body,
                                 'Trail cameras, thermal and night vision, audio recorders, track casting, binoculars, skywatching and safety gear '
                                 'for Bigfoot, cryptid and UFO investigators, with the reason each one is worth packing.'))

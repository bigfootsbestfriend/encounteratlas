"""Press and researchers (/press/): what Encounter Atlas covers, the numbers, how each dataset is sourced, how to cite it,
free-to-use charts, and the contact form preset to "Press". Numbers are counted from data/ at build time.
Charts in site/static/img/charts/ are our own work under CC BY-SA 4.0 (the same files go to Wikimedia Commons).
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sources
from contact import _form, _head

CHARTS = [('Project_Blue_Book_UFO_sightings_by_year_1947-1969.svg', 'UFO sightings reported to the US Air Force each year, 1947 to 1969',
           'From the Air Force\'s own fact sheet: 12,618 sightings, 701 left unidentified.'),
          ('Official_UFO_programmes_by_country.svg', 'Official UFO programmes by country, 1946 to today',
           'Every government programme on our programmes page, as a timeline.')]


def build(ctx):
    U, E = ctx.url, ctx.esc

    def n(name):
        p = os.path.join(ctx.ROOT, 'data', name)
        return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []

    rel = n('ufo_releases.json')
    rec = n('on_the_record.json') or {'hearings': [], 'people': []}
    progs = n('ufo_programs.json')
    canada = n('ufo_cases_canada.json')
    stats = [(len(rel), 'official UFO releases', f'from {len({r["country"] for r in rel})} countries', '/ufo/releases/'),
             (len(rec['hearings']), 'public UFO hearings', f'{len(rec["people"])} people who testified', '/ufo/hearings/'),
             (len(ctx.bluebook), 'Project Blue Book files', 'mapped from the National Archives', '/ufo/blue-book/'),
             (len(canada), 'Canadian sightings', 'from the Canadian UFO Survey', '/ufo/canada/'),
             (len(ctx.creatures), 'creatures', 'with folklore, sightings and sources', '/creatures/')]
    if progs:
        stats.insert(1, (len(progs), 'government UFO programmes', f'in {len({p["country"] for p in progs})} countries', '/ufo/programs/'))
    tiles = ''.join(f'<li><a href="{U(p)}"><b>{v:,}</b><span>{E(a)}</span><small>{E(b)}</small></a></li>' for v, a, b, p in stats)
    def size(f):
        head = open(os.path.join(ctx.ROOT, 'site', 'static', 'img', 'charts', f), encoding='utf-8').read(400)
        return re.search(r'width="(\d+)" height="(\d+)"', head).groups()

    charts = ''.join(
        f'<figure class="press-chart"><a href="{U("/static/img/charts/" + f)}"><img src="{U("/static/img/charts/" + f)}" alt="{E(t)}" loading="lazy" width="{size(f)[0]}" height="{size(f)[1]}"></a>'
        f'<figcaption><b>{E(t)}.</b> {E(c)} <a href="{U("/static/img/charts/" + f)}" download>Download SVG</a></figcaption></figure>'
        for f, t, c in CHARTS if os.path.exists(os.path.join(ctx.ROOT, 'site', 'static', 'img', 'charts', f)))
    body = f'''
<section class="band band-dark"><div class="wrap"><p class="crumb"><a href="{U('/about/')}">About</a> / Press</p>
<h1>Press and researchers</h1>
<p class="lede">Writing about UFOs, government files or cryptids? Everything here is free to read, link and quote, and every official record links back to its source.</p></div></section>
<div class="band band-mist"><div class="wrap">
<ul class="press-stats">{tiles}</ul>
<div class="prose">
<h2>What Encounter Atlas is</h2>
<p>A free, independent site that puts strange sightings and the official paper trail in one place: a world map of reports, the governments' own UFO files, the hearings, and the folklore behind 245 creatures. It's built and run by <a href="{U('/author/mike-johnston/')}">Mike Johnston</a> in Alberta, Canada. We don't claim sightings are real and we don't claim they aren't. We show the record and where it came from.</p>
<h2>Pages people cite</h2>
<ul>
<li><a href="{U('/ufo/releases/')}">Every official UFO release, on one timeline</a>: {len(rel)} government releases, each linked to the original with an archived copy.</li>
{f'<li><a href="{U("/ufo/programs/")}">Government UFO programmes worldwide</a>: who investigated, when, and what they concluded.</li>' if progs else ''}
<li><a href="{U('/ufo/hearings/')}">UFO hearings since 1966</a>: quotes checked word for word against the official transcripts.</li>
<li><a href="{U('/ufo/blue-book/')}">Project Blue Book files, mapped</a>: {len(ctx.bluebook):,} Air Force case files from the National Archives.</li>
<li><a href="{U('/ufo/countries/')}">UFO files by country</a>: how each government has handled reports.</li>
</ul>
<h2>How we source things</h2>
<ul>
<li>Official records come from the government that published them (National Archives in the US, UK and Canada, GovInfo, the air forces and agencies themselves). Summaries are our own words.</li>
<li>Quotes from hearings are copied word for word from the published transcripts and written statements.</li>
<li>Reader reports are what witnesses tell us. They're moderated for spam and privacy, not verified, and exact locations are blurred.</li>
<li>Full source list: <a href="{U('/about/')}">About and sources</a>. Each list page has an "About this list" box with the date its links were last checked.</li>
</ul>
<h2>Citing us</h2>
<p>Please link the specific page you used. A citation that works anywhere:</p>
<p class="press-cite">Johnston, Mike. "Page title." Encounter Atlas. Accessed (date). https://encounteratlas.com/page/</p>
<p>For anything from a government file, cite the original record too. Our pages link it.</p>
{f'<h2>Charts you can use</h2><p>Our own charts, free to reuse under <a href="https://creativecommons.org/licenses/by-sa/4.0/" rel="license noopener">CC BY-SA 4.0</a>. Credit "Encounter Atlas".</p>{charts}' if charts else ''}
<h2>Get in touch</h2>
<p>Interviews, data questions, corrections or a source we missed: use the form or email <a href="mailto:hello@encounteratlas.com">hello@encounteratlas.com</a>.</p>
</div>
<div class="narrow">{_form(ctx, 'press')}</div>
</div></div>'''
    css = (f'<link rel="stylesheet" href="{U("/static/sources.css")}">' + _head(ctx))
    ctx.write('/press/', ctx.page('/press/', 'Press and researchers', body,
                                  'Facts, figures, sourcing and free charts for journalists and researchers writing about UFO files, hearings and cryptids.',
                                  head_extra=css))

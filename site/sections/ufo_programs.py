"""Government UFO programmes worldwide (/ufo/programs/), from data/ufo_programs.json.

One hub page, not one page per programme (most would be thin). Grouped by country, with a timeline strip drawn in
plain HTML/CSS (full list in the HTML, no JS needed). Every programme links its official sources, each with an
archived copy where the Internet Archive has one (data/source_archive.json, tools/archive_links.py).
Entries are hand-checked: what_it_did / conclusion are our own words; sources are official first.
Fields: slug, name, aka, country, agency, start, end (null = still running), status (active|closed), did, found,
sources [{name, url}], release (slug in ufo_releases.json or null), note (optional caveat shown in italics).
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sources

ORDER = ['us', 'ca', 'gb', 'fr', 'es', 'it', 'be', 'dk', 'se', 'su', 'br', 'cl', 'ar', 'pe', 'uy', 'mx', 'au', 'nz', 'jp']
NAMES = {'us': 'United States', 'ca': 'Canada', 'gb': 'United Kingdom', 'fr': 'France', 'es': 'Spain', 'it': 'Italy',
         'be': 'Belgium', 'dk': 'Denmark', 'se': 'Sweden', 'su': 'Soviet Union and Russia', 'br': 'Brazil', 'cl': 'Chile',
         'ar': 'Argentina', 'pe': 'Peru', 'uy': 'Uruguay', 'mx': 'Mexico', 'au': 'Australia', 'nz': 'New Zealand', 'jp': 'Japan',
         'ru': 'Russia', 'de': 'Germany', 'pt': 'Portugal', 'ie': 'Ireland', 'cn': 'China', 'in': 'India', 'kr': 'South Korea'}
Y0 = 1945


def build(ctx):
    p = os.path.join(ctx.ROOT, 'data', 'ufo_programs.json')
    if not os.path.exists(p):
        return
    E, U = ctx.esc, ctx.url
    progs = json.load(open(p, encoding='utf-8'))
    now = datetime.date.today().year
    span = now + 1 - Y0
    by_cc = {}
    for g in progs:
        by_cc.setdefault(g['country'], []).append(g)
    ccs = sorted(by_cc, key=lambda c: (ORDER.index(c) if c in ORDER else 99, NAMES.get(c, c)))
    for c in ccs:
        by_cc[c].sort(key=lambda g: (str(g['start']), g['name']))
    active = [g for g in progs if g['status'] == 'active']

    def years(g):
        if g['status'] == 'unclear':
            return f'{g["start"]} to ?'
        if not g.get('end'):
            return f'{g["start"]} to today'
        return str(g['start']) if g['end'] == g['start'] else f'{g["start"]} to {g["end"]}'

    def chip(g):
        return {'active': '<span class="pg-st pg-on">Still running</span>',
                'unclear': f'<span class="pg-st pg-unc">No news since {g["end"]}</span>'}.get(g['status'], '<span class="pg-st">Closed</span>')

    def bar(g):
        s = int(str(g['start'])[:4])
        e = int(str(g['end'])[:4]) if g.get('end') else now
        left = (s - Y0) / span * 100
        width = max((e - s + 1) / span * 100, 0.9)
        return (f'<li><a href="#{g["slug"]}"><span class="pg-bl">{E(g.get("short") or g["name"])}</span>'
                f'<span class="pg-track"><span class="pg-bar{ {"active": " pg-bar-on", "unclear": " pg-bar-unc"}.get(g["status"], "")}" '
                f'style="left:{left:.2f}%;width:{width:.2f}%" title="{E(g["name"])}: {E(years(g))}"></span></span></a></li>')

    ticks = ''.join(f'<span style="left:{(y - Y0) / span * 100:.2f}%">{y}</span>' for y in range(1950, now + 1, 10))
    strip = ''.join(f'<li class="pg-cc"><b>{E(NAMES.get(c, c.upper()))}</b><ol>{"".join(bar(g) for g in by_cc[c])}</ol></li>' for c in ccs)

    def card(g):
        src = ''.join(f'<li>{_sources.src_link(ctx, s["url"], s["name"])}</li>' for s in g['sources'])
        rel = (f'<p class="pg-rel"><a href="{U("/ufo/releases/" + g["release"] + "/")}">Its files in our official releases list</a></p>'
               if g.get('release') else '')
        aka = f'<p class="pg-aka">{E(g["aka"])}</p>' if g.get('aka') else ''
        note = f'<p class="pg-note"><em>{E(g["note"])}</em></p>' if g.get('note') else ''
        return (f'<article class="pg-card" id="{g["slug"]}"><header><p class="pg-meta"><span class="pg-yrs">{E(years(g))}</span>{chip(g)}</p>'
                f'<h3>{E(g["name"])}</h3>{aka}<p class="pg-agency">{E(g["agency"])}</p></header>'
                f'<p>{E(g["did"])}</p><p><b>What it found:</b> {E(g["found"])}</p>{note}'
                f'<h4>Sources</h4><ul class="pg-src">{src}</ul>{rel}</article>')

    sections = ''.join(
        f'<section class="pg-country" id="c-{c}"><h2>{E(NAMES.get(c, c.upper()))} <span class="muted">({len(by_cc[c])})</span></h2>'
        f'<div class="pg-grid">{"".join(card(g) for g in by_cc[c])}</div></section>' for c in ccs)
    jump = ''.join(f'<a class="chip" href="#c-{c}">{E(NAMES.get(c, c.upper()))}</a>' for c in ccs)
    first = min(int(str(g['start'])[:4]) for g in progs)
    method = ('<p><b>What counts:</b> a programme, office, study or standing procedure set up by a government, military or state '
              'agency to collect or investigate UFO or UAP reports. Private groups are left out, even when former officials run them, '
              'and so are claims about secret programmes nobody has confirmed.</p>'
              '<p><b>How we wrote it:</b> we read the official records and summed them up in our own words. Sources are the '
              'governments\' own pages and documents first; where those are thin, one news or academic source fills the gap.</p>')
    body = f'''
<section class="band band-dark ua-hero"><div class="wrap">
  <p class="crumb"><a href="{U('/ufo/')}">UFOs</a> / Government programmes</p>
  <h1>Every government UFO programme, country by country</h1>
  <p class="lede">Since {first}, at least {len(progs)} official programmes in {len(ccs)} countries have collected or studied UFO reports. Some lasted a few months; France's has been running since 1977. Here's who ran each one, what they did and what they concluded, with the official records linked.</p>
  <ul class="ua-stats"><li><b>{len(progs)}</b> programmes</li><li><b>{len(ccs)}</b> countries</li><li><b>{len(active)}</b> still running</li><li><b>{first}</b> earliest</li></ul>
</div></section>
<div class="band band-mist"><div class="wrap">
  <h2>On one timeline</h2>
  <div class="pg-tl" aria-label="Programme timeline"><div class="pg-ticks">{ticks}</div><ol class="pg-strip">{strip}</ol>
  <p class="pg-key"><span class="pg-bar pg-bar-on"></span> still running <span class="pg-bar"></span> closed <span class="pg-bar pg-bar-unc"></span> status unknown</p></div>
  <nav class="chips pg-jump" aria-label="Jump to a country">{jump}</nav>
  {sections}
  <p>See also: <a href="{U('/ufo/releases/')}">every official UFO release</a>, <a href="{U('/ufo/hearings/')}">UFO hearings</a> and <a href="{U('/ufo/countries/')}">UFO files by country</a>.</p>
  {_sources.about_box(ctx, '/ufo/programs/', 'Every government UFO programme, country by country', method)}
</div></div>'''
    css = (f'<link rel="stylesheet" href="{U("/static/ufo_archive.css")}"><link rel="stylesheet" href="{U("/static/sources.css")}">'
           f'<link rel="stylesheet" href="{U("/static/programs.css")}">')
    ctx.write('/ufo/programs/', ctx.page('/ufo/programs/', 'Government UFO programmes worldwide: who investigated and what they found', body,
                                         f'{len(progs)} official UFO and UAP programmes in {len(ccs)} countries since {first}, from Project Blue Book to AARO, '
                                         'GEIPAN and Sky Canada, with dates, findings and official sources.',
                                         head_extra=css, article={'published': '2026-10-24'}))

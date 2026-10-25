"""Builds the Encounter Atlas static site into _site/ (stdlib only).

Inputs: data/creatures.json (hand-written), data/bluebook.json (collector/bluebook.py),
data/military.json (hand-written). Output: plain HTML pages + a few JSON/GeoJSON files.
"""
import hashlib, datetime, html, json, os, re, shutil, sys, urllib.parse
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.environ.get('OUT_DIR') or os.path.join(ROOT, '_site')
STATIC = os.path.join(ROOT, 'site', 'static')
PUBLISHED = '2026-10-13'  # launch day: creature pages without their own "updated" date show this
_MON = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def md_links(t):
    """Escape text, then turn [words](/site/path/) into internal links (hand-written creature sections only)."""
    return re.sub(r'\[([^\]]+)\]\((/[^)\s]*)\)', lambda m: f'<a href="{url(m.group(2))}">{m.group(1)}</a>', esc(t))


# Self-hosted fonts (site/static/fonts, OFL): @font-face inlined so text never waits on a third-party stylesheet, and the
# two fonts the first screen uses are preloaded. Regenerate fonts.css + woff2 files if weights change.
def font_head():
    return (f'<link rel="preload" href="{url("/static/fonts/publicsans-ijwRs572Xtc6ZYQws9YVwnNGfJ4.woff2")}" as="font" type="font/woff2" crossorigin>'
            f'<link rel="preload" href="{url("/static/fonts/zillaslab-dFa5ZfeM_74wlPZtksIFYoEf6HOpWw.woff2")}" as="font" type="font/woff2" crossorigin>'
            '<style>' + re.sub(r'/\*.*?\*/\s*', '', open(os.path.join(STATIC, 'fonts', 'fonts.css')).read(), flags=re.S)
            .replace('url(/static/', f'url({BASE}/static/').replace('\n', '') + '</style>')


ARTICLES = []  # every page built with article=..., for the author page and sitemap <lastmod>
# RSS feeds (2026-10-25): Google Discover's Follow button reads the feeds linked from each page's <head>; Telegram,
# Discord and feed readers use them too. Every indexable page with a known date goes in FEED; section feeds by path prefix.
FEED = []
FEED_SECTIONS = [('/creatures/', 'Creatures'), ('/reports/', 'Reader reports'), ('/stories/', 'Witness stories'),
                 ('/ufo/', 'UFOs and official files'), ('/encounters/', 'Close encounters'), ('/mysteries/', 'Mysteries')]
AUTHOR = {'name': 'Mike Johnston', 'path': '/author/mike-johnston/', 'image': '/static/img/mike-johnston.png'}


def byline_html(a):
    pub, upd = a.get('published') or PUBLISHED, a.get('updated')
    when = f'Updated {nice_date(upd)}' if upd and upd != pub else f'Published {nice_date(pub)}'
    return f'<p class="byline">{a.get("verb", "By")} <a href="{url(AUTHOR["path"])}" rel="author">{AUTHOR["name"]}</a> · {when}</p>'


def with_byline(body, a):
    b = byline_html(a)
    m = re.search(r'<p class="lede">.*?</p>', body, re.S) or re.search(r'</h1>', body)
    return body[:m.end()] + '\n      ' + b + body[m.end():] if m else b + body


def article_ld(path, title, desc, og_image, a):
    o = {'@context': 'https://schema.org', '@type': 'Article', 'headline': title[:110], 'description': desc,
         'mainEntityOfPage': SITE_URL + path, 'datePublished': a.get('published') or PUBLISHED,
         'dateModified': a.get('updated') or a.get('published') or PUBLISHED,
         'author': {'@type': 'Person', 'name': AUTHOR['name'], 'url': SITE_URL + AUTHOR['path']},
         'publisher': {'@type': 'Organization', 'name': 'Encounter Atlas', 'url': SITE_URL + '/', 'logo': {'@type': 'ImageObject', 'url': SITE_URL + '/static/app-512.png'}}}
    o['image'] = SITE_URL + (og_image or '/static/og.png')
    return o


def author_page():
    """/author/mike-johnston/: who writes and reviews the site, how it's researched, and everything credited to him."""
    groups = [('/creatures/', 'Creatures'), ('/mysteries/', 'Mysteries'), ('/encounters/', 'Close encounters'), ('/ufo/cases/', 'Famous UFO cases'),
              ('/ufo/hearings/', 'UFO hearings'), ('/ufo/people/', 'People on the record'), ('/ufo/releases/', 'Official UFO releases'),
              ('/compare/', 'Comparisons'), ('/guides/', 'Field guides'), ('/stories/', 'Witness stories (retold)')]
    arts = [a for a in ARTICLES if not a['noindex']]
    recent = sorted(arts, key=lambda a: (a['date'], a['title']), reverse=True)[:12]
    rec = ''.join(f'<li><span class="yr">{esc(nice_date(a["date"]))}</span><span><a href="{url(a["path"])}">{esc(a["title"])}</a></span></li>' for a in recent)
    cnt = ''.join(f'<li><a href="{url(p)}">{esc(n)}</a> <span class="muted">{sum(1 for a in arts if a["path"].startswith(p) and a["path"] != p)}</span></li>'
                  for p, n in groups if any(a['path'].startswith(p) for a in arts))
    path = AUTHOR['path']
    body = f'''
<section class="band band-dark"><div class="wrap author-head">
  <picture><source srcset="{url('/static/img/mike-johnston.webp')}" type="image/webp"><img class="author-photo" src="{url(AUTHOR['image'])}" alt="Mike Johnston" width="160" height="160"></picture>
  <div>
    <p class="crumb"><a href="{url('/about/')}">About</a> / Author</p>
    <h1>Mike Johnston</h1>
    <p class="lede">Founder and editor of Encounter Atlas. Canadian web developer with a long-running interest in Bigfoot, lake monsters and UFOs.</p>
    {social_row('social owner-social')}
  </div>
</div></section>
<div class="band band-mist"><div class="wrap prose">
  <h2>About me</h2>
  <p>I've had a long-running interest in Sasquatch, lake monsters like Ogopogo, and lights in the sky. I built Encounter Atlas because the information was scattered across old forums, dead links and books that are hard to find. I wanted one place where you can see where things were reported, read what people actually said, and check the original sources yourself.</p>
  <p>By day I build websites. Here I write and review the creature pages, case write-ups, guides and the official records sections, and I read every reader report before it goes on the map.</p>
  <h2>How I research and write</h2>
  <ul>
    <li><strong>Original sources first.</strong> Government archives (Project Blue Book, the National Archives, Library and Archives Canada), congressional transcripts, old newspapers and published witness accounts. Every page links to where the facts came from.</li>
    <li><strong>Reports are not proof.</strong> A sighting on this site means someone said they saw something. I say what was reported, what investigators found and which explanations hold up, and I let you decide.</li>
    <li><strong>Witnesses get credit.</strong> Stories are retold in my own words and credited to the person who told them, with a link to the original where there is one.</li>
    <li><strong>Corrections are welcome.</strong> If something is wrong or out of date, <a href="{url('/contact/')}">tell me</a> and I will fix it and update the date on the page.</li>
  </ul>
  <h2>Recently updated</h2>
  <ol class="timeline cases">{rec}</ol>
  <h2>Everything I've written</h2>
  <ul class="author-counts">{cnt}</ul>
</div></div>'''
    person = {'@type': 'Person', '@id': SITE_URL + path + '#person', 'name': 'Mike Johnston', 'url': SITE_URL + path, 'image': SITE_URL + AUTHOR['image'],
              'jobTitle': 'Founder and editor', 'nationality': 'Canadian', 'knowsAbout': ['Cryptozoology', 'Bigfoot', 'Lake monsters', 'UFOs', 'Project Blue Book'],
              'worksFor': {'@type': 'Organization', 'name': 'Encounter Atlas', 'url': SITE_URL + '/', 'sameAs': [u for _, u, _, _ in SOCIAL]}}
    ld = [{'@context': 'https://schema.org', '@type': 'ProfilePage', 'url': SITE_URL + path, 'mainEntity': person}]
    write(path, page(path, 'Mike Johnston, founder and editor', body,
                     'Mike Johnston writes and reviews Encounter Atlas: who he is, how the site is researched, and everything he has written about cryptids, UFOs and mysteries.',
                     ld=ld, head_extra='<style>.author-head{display:flex;gap:1.6rem;align-items:center}.author-photo{border-radius:50%;border:4px solid var(--lantern);width:160px;height:160px}'
                     '.author-counts{columns:2;max-width:40rem}@media(max-width:600px){.author-head{flex-direction:column;align-items:flex-start}.author-photo{width:110px;height:110px}.author-counts{columns:1}}</style>'))


def nice_date(d):
    y, m, dd = map(int, d.split('-'))
    return f'{_MON[m - 1]} {dd}, {y}'
SITE_URL = os.environ.get('SITE_URL', 'https://encounteratlas.com').rstrip('/')
BASE = os.environ.get('BASE_PATH', '').rstrip('/')  # '/encounteratlas' on the GitHub Pages preview
INDEXNOW_KEY = '929458a6bce349d1b445a459836d80fe'
NEWSLETTER_API = 'https://newsletter.crossplayguide.workers.dev'  # shared Worker (repo: newsletter); sites.json key 'encounteratlas'
LAUNCHED = True  # launched 2026-10-13 (Mike: "launch the site")
CF_BEACON = os.environ.get('CF_BEACON', '')
CLARITY_ID = os.environ.get('CLARITY_ID', '')  # Microsoft Clarity project (free heatmaps + session replays); set in deploy.yml
GA_ID = os.environ.get('GA_ID', '')
CLICKY_ID = os.environ.get('CLICKY_ID', '')  # Clicky site ID; set in deploy.yml  # GA4 measurement ID; set in deploy.yml, empty for local and preview builds

CATS = {
    'hominid': ('Hairy hominids', 'Upright, ape-like giants of the woods and mountains'),
    'canid': ('Dogmen and beasts', 'Upright canines, werewolves and livestock killers'),
    'winged': ('Winged things', 'Red-eyed fliers and impossible birds'),
    'aquatic': ('Lake and sea monsters', 'Long necks, humps and serpents in deep water'),
    'entity': ('Strange visitors', 'Small grey beings, frogmen and things from the sky'),
    'fae': ('Fairies and little people', 'Fae, pixies, hidden folk and little people from every continent'),
    'other': ('Odd creatures', 'Desert worms, Alpine lizards and other one-offs'),
    'ufo': ('UFOs and UAP', 'Saucers, triangles, orbs and what the military tracked'),
}
MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']
US_STATES = {}


def esc(s):
    return html.escape(str(s), quote=True)


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


_VER = {}


def url(path):
    # CSS and JS get a content-hash query so browsers and the service worker (cache-first for /static/)
    # fetch a changed file at once instead of serving yesterday's copy.
    if path.startswith('/static/') and path.endswith(('.css', '.js')):
        if path not in _VER:
            f = os.path.join(STATIC, path[len('/static/'):])
            _VER[path] = hashlib.md5(open(f, 'rb').read()).hexdigest()[:8] if os.path.exists(f) else ''
        if _VER[path]:
            return f'{BASE}{path}?v={_VER[path]}'
    return BASE + path


ICON_ART = json.load(open(os.path.join(ROOT, 'data', 'icon_art.json'))) if os.path.exists(os.path.join(ROOT, 'data', 'icon_art.json')) else {}


def tile_icon(name):
    """Tile icon with the silhouette scaled to a shared optical size (equal bounding-box area, never past the box)."""
    tag = icon(name)
    if name not in ICON_ART:
        return tag
    d = ' '.join(re.findall(r' d="([^"]+)"', open(os.path.join(STATIC, 'art', ICON_ART[name] + '.svg')).read()))
    n = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', d)]
    x0, x1, y0, y1 = min(n[0::2]), max(n[0::2]), min(n[1::2]), max(n[1::2])
    w, h = x1 - x0, y1 - y0
    k = min(560 / (w * h) ** .5, 790 / max(w, h))  # scale vs the 800 viewBox
    pos = lambda c: (.5 - c / 800 * k) / (1 - k) * 100 if abs(1 - k) > .01 else 50
    return tag.replace('" aria-hidden', f';--ms:{k * 100:.1f}%;--mx:{pos((x0 + x1) / 2):.1f}%;--my:{pos((y0 + y1) / 2):.1f}%" aria-hidden', 1)


def icon(name, cls='ico'):
    if name in ICON_ART:  # creature names draw the poster silhouette as a mask, so it takes the surrounding colour
        src = url('/static/art/' + ICON_ART[name] + '.svg')
        return f'<span class="{cls} art-ico" style="--m:url({src})" aria-hidden="true"></span>'
    svg = open(os.path.join(STATIC, 'icons', name + '.svg')).read().strip()
    return svg.replace('<svg ', f'<svg class="{cls}" aria-hidden="true" focusable="false" ', 1)


_CE = None


def story_url(creature_slug, year):
    """The full write-up for a famous case, if one exists (a close-encounters case page with that creature and year)."""
    global _CE
    if _CE is None:
        fp = os.path.join(ROOT, 'data', 'close_encounters.json')
        _CE = {}
        for x in (json.load(open(fp)) if os.path.exists(fp) else []):
            years = {x['year']} | ({1955, 1972} if x['slug'].startswith('loveland') else set())
            for cr in x.get('creatures', []):
                for y in years:
                    _CE.setdefault((cr, y), url('/encounters/' + x['slug'] + '/'))
                _CE.setdefault((cr, 'first'), (url('/encounters/' + x['slug'] + '/'), x['name']))
    return _CE.get((creature_slug, year), '')


def crit_icon(c, cls='ico'):
    """A creature's own poster silhouette as a colour-taking mask; falls back to its shared icon."""
    if c.get('art'):
        src = url('/static/' + c['art'] + '.svg')
        return f'<span class="{cls} art-ico" style="--m:url({src})" aria-hidden="true"></span>'
    return icon(c['icon'], cls)


_EXT_A = re.compile(r'<a\b(?![^>]*\btarget=)([^>]*\bhref="https?://(?!(?:www\.)?encounteratlas\.com)[^"]*"[^>]*)>')


def external_new_tab(html_text):
    """Every link to another site opens in a new tab, so readers keep their place here."""
    def fix(m):
        attrs = m.group(1)
        if 'rel="' in attrs:
            attrs = re.sub(r'rel="([^"]*)"', lambda r: 'rel="' + ' '.join(dict.fromkeys(r.group(1).split() + ['noopener'])) + '"', attrs)
        else:
            attrs += ' rel="noopener"'
        return f'<a{attrs} target="_blank">'
    return _EXT_A.sub(fix, html_text)


def write(path, text):
    full = os.path.join(OUT, path.lstrip('/'))
    if full.endswith('/'):
        full += 'index.html'
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(external_new_tab(text) if full.endswith('.html') else text)


EA_API = os.environ.get('EA_API', '').rstrip('/')  # report Worker; empty until it's deployed
MAP_API = f' data-api="{EA_API}"' if EA_API else ''
UFO_MENU = [('/ufo/', 'UFO sightings'), ('/ufo/cases/', 'Famous cases worldwide'), ('/ufo/canada/', 'Canada sightings map'), ('/ufo/greece/', 'Greece close encounters'), ('/ufo/blue-book/', 'Air Force Blue Book files'),
            ('/ufo/releases/', 'Official releases'), ('/ufo/hearings/', 'Hearings and testimony'), ('/ufo/programs/', 'Government programmes'), ('/ufo/countries/', 'UFO files by country'), ('/military/', 'Military encounters')]
STORY_MENU = ([('/reports/', 'Reader reports')] if EA_API else []) + [('/stories/', 'Witness stories'), ('/stories/campfire/', 'Campfire stories'), ('/encounters/', 'Close encounters'), ('/report/', 'Report an encounter')]
EXPLORE_MENU = [('/near-me/', 'Sightings near me'), ('/road-trip/', 'Road trip planner'), ('/cards/', 'Collector cards'), ('/tools/skywatch/', "Tonight's skywatch"), ('/journal/', 'Field journal'), ('/mystery-of-the-day/', 'Mystery of the day'), ('/mysteries/', 'Mysteries'), ('/history/', 'Old newspaper stories'), ('/on-this-day/', 'On this day'), ('/compare/', 'Creature comparisons'),
                ('/us/', 'By state or province'), ('/places/', 'Places to visit')]
RES_MENU = [('/guides/', 'Field guides'), ('/gear/', 'Field gear'), ('/books/', 'Books'), ('/tools/', 'Tools'), ('/podcasts/', 'Podcasts'), ('/newsletter/', 'Weekly email')]
# Six top-level items (Mike, 2026-10-18: the eight-item menu wrapped into three rows on phones). Under 960px the
# same groups open from one Menu button instead (mobile_menu()).
NAV = [('/map/', 'Map'), ('/creatures/', 'Creatures'), ('UFOs', UFO_MENU), ('Stories', STORY_MENU), ('Explore', EXPLORE_MENU), ('More', RES_MENU)]


def mobile_menu(path):
    """The phone menu: one <details> panel with every group, big tap targets. Works without JS."""
    cur = lambda q: ' aria-current="page"' if path == q or (q != '/' and path.startswith(q)) else ''
    top = ''.join(f'<a class="mm-big" href="{url(q)}"{cur(q)}>{esc(n)}</a>' for q, n in NAV if not isinstance(n, list))
    groups = ''.join(f'<div class="mm-group"><p class="mm-h">{esc(p)}</p>' + ''.join(f'<a href="{url(q)}"{cur(q)}>{esc(m)}</a>' for q, m in n) + '</div>'
                     for p, n in NAV if isinstance(n, list))
    return (f'<details class="mm" data-area="mobile-menu"><summary aria-label="Menu"><svg viewBox="0 0 20 14" width="20" height="14" aria-hidden="true">'
            '<path d="M1 1h18M1 7h18M1 13h18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg><span>Menu</span></summary>'
            f'<div class="mm-panel"><div class="mm-top">{top}</div><div class="mm-groups">{groups}</div></div></details>')


def nav_html(path):
    """Top nav; a (label, [links]) entry becomes a dropdown (<details>, so it works without JS)."""
    out = ''
    for p, n in NAV:
        if isinstance(n, list):
            on = any(path.startswith(q) for q, _ in n)
            links = ''.join(f'<a href="{url(q)}"{" aria-current=page" if path.startswith(q) and not any(path.startswith(r) and len(r) > len(q) for r, _ in n) else ""}>{esc(m)}</a>' for q, m in n)
            out += (f'<details class="nav-dd{" on" if on else ""}"><summary>{esc(p)}<svg viewBox="0 0 10 6" width="10" height="6" aria-hidden="true">'
                    f'<path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></summary><div class="dd-menu">{links}</div></details>')
        else:
            out += f'<a href="{url(p)}"{" aria-current=page" if path.startswith(p) else ""}>{esc(n)}</a>'
    return out


# Official social accounts: (name, url, svg path, viewBox). Add a row when Mike opens an account; nothing is shown for ones that don't exist.
SOCIAL = [
    ('Bluesky', 'https://bsky.app/profile/encounteratlas.com', '0 0 600 530',
     'm135.72 44.03c66.496 49.921 138.02 151.14 164.28 205.46 26.262-54.316 97.782-155.54 164.28-205.46 47.98-36.021 125.72-63.892 125.72 24.795 0 17.712-10.155 148.79-16.111 170.07-20.703 73.984-96.144 92.854-163.25 81.433 117.3 19.964 147.14 86.092 82.697 152.22-122.39 125.59-175.91-31.511-189.63-71.766-2.514-7.3797-3.6904-10.832-3.7077-7.8964-.0174-2.9357-1.1937.51669-3.7077 7.8964-13.714 40.255-67.233 197.36-189.63 71.766-64.444-66.128-34.605-132.26 82.697-152.22-67.108 11.421-142.55-7.4491-163.25-81.433-5.9562-21.282-16.111-152.36-16.111-170.07 0-88.687 77.742-60.816 125.72-24.795z'),
    ('Facebook', 'https://www.facebook.com/61595246615673/', '0 0 24 24', 'M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z'),
]


def ga_tag():
    """Analytics, live site only (never on a BASE_PATH preview): GA4 + usage events (static/track.js), and the
    Cloudflare beacon when CF_BEACON is set. window.eaTrack(name, params) sends a named event from any page script."""
    if BASE:
        return ''
    out = ''
    if GA_ID:
        out += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>'
                "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                # app_mode (GA4 custom dimension): twa = the Play Store app, pwa = installed from the browser, web = a tab.
                # Remembered per session, since only the app's first page carries ?source=twa / ?source=pwa. Only our own package's
                # referrer counts: links opened from the Reddit app also arrive as android-app://com.reddit.frontpage.
                "var eaMode=(function(){try{var q=new URLSearchParams(location.search).get('source'),s=sessionStorage;"
                "if(q==='twa'||document.referrer.indexOf('android-app://com.encounteratlas.app')===0)s.setItem('ea-mode','twa');"
                "else if(q==='pwa'||q==='app')s.setItem('ea-mode','pwa');"
                "return s.getItem('ea-mode')||(matchMedia('(display-mode: standalone)').matches||navigator.standalone?'pwa':'web');}catch(e){return 'web';}})();"
                f"gtag('js',new Date());gtag('set',{{app_mode:eaMode}});gtag('config','{GA_ID}',{{app_mode:eaMode}});"
                "window.eaTrack=function(n,p){try{gtag('event',n,Object.assign({page_type:location.pathname.split('/')[1]||'home'},p||{}));}catch(e){}};</script>"
                f'<script src="{url("/static/track.js")}" defer></script>')
    if CLARITY_ID:
        out += ('<script>addEventListener("load",function(){setTimeout(function(){(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};'
                't=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);'
                f'}})(window,document,"clarity","script","{CLARITY_ID}");}},3000);}});</script>')
    if CLICKY_ID:
        out += f'<script async data-id="{CLICKY_ID}" src="https://static.getclicky.com/js"></script>'
    if CF_BEACON:
        out += (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                f'data-cf-beacon=\'{{"token": "{CF_BEACON}"}}\'></script>')
    return out


def social_row(cls='social'):
    """Icon links to the official accounts (footer and About page)."""
    if not SOCIAL:
        return ''
    links = ''.join(f'<a href="{u}" rel="me noopener" aria-label="Encounter Atlas on {n}" title="{n}" data-net="{n.lower()}">'
                    f'<svg viewBox="{vb}" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="{d}"/></svg></a>' for n, u, vb, d in SOCIAL)
    return f'<p class="{cls}">{links}</p>'


def ld_json(path, title, body, extra=None):
    """Structured data: BreadcrumbList from the page's own crumb line, WebSite on the home page, plus any extra objects."""
    out = list(extra or [])
    if path == '/':
        out.append({'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'Encounter Atlas', 'url': SITE_URL + '/'})
        out.append({'@context': 'https://schema.org', '@type': 'Organization', 'name': 'Encounter Atlas', 'url': SITE_URL + '/',
                    'logo': SITE_URL + '/static/app-512.png', 'sameAs': [u for _, u, _, _ in SOCIAL]})
    if path == '/about/':
        out.append({'@context': 'https://schema.org', '@type': 'AboutPage', 'url': SITE_URL + '/about/', 'mainEntity': {
            '@type': 'Person', 'name': 'Mike Johnston', 'image': SITE_URL + '/static/img/mike-johnston.png', 'nationality': 'Canadian',
            'jobTitle': 'Founder', 'worksFor': {'@type': 'Organization', 'name': 'Encounter Atlas', 'url': SITE_URL + '/', 'sameAs': [u for _, u, _, _ in SOCIAL]}}})
    m = re.search(r'<p class="crumb">(.*?)</p>', body, re.S)
    if m:
        items = [(html.unescape(re.sub(r'<[^>]+>', '', t)).strip(), h) for h, t in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', m.group(1))]
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S)
        last = html.unescape(re.sub(r'<[^>]+>', '', h1.group(1))).strip() if h1 else title  # the page itself
        crumbs = [(n, h) for n, h in items if n and h != url(path)] + [(last, path)]
        if len(crumbs) >= 2:
            abs_ = lambda h: SITE_URL + (h[len(BASE):] if BASE and h.startswith(BASE) else h)
            out.append({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': abs_(h)} for i, (n, h) in enumerate(crumbs)]})
    return ''.join('<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False).replace('</', '<\\/') + '</script>' for o in out)


# Weekly email bar above the header on every page but the full-screen map. Closing it hides it for 14 days
# (static/signup.js); the inline script removes it before paint for people who closed it or already signed up.
HELLO = f'''<div class="hello" id="hello" role="region" aria-label="Weekly email">
  <form class="hello-in" action="{NEWSLETTER_API}/subscribe" method="post" data-nl>
    <p class="hello-txt"><b>Strange news, once a week.</b> <span>Monsters from the old newspapers, a creature of the week and new reader reports.</span></p>
    <input type="hidden" name="site" value="encounteratlas"><input class="visually-hidden" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
    <label for="hello-email" class="visually-hidden">Email address</label>
    <input id="hello-email" name="email" type="email" required placeholder="you@example.com" autocomplete="email">
    <button type="submit" class="btn btn-sm">Sign me up</button>
  </form>
  <button type="button" class="hello-x" aria-label="Close">&times;</button>
</div>
<script>try{{const s=localStorage;if(s.getItem('ea-subbed')||Date.now()-(+s.getItem('ea-hello')||0)<12096e5)document.getElementById('hello').remove();}}catch(e){{}}</script>'''


def page(path, title, body, desc='', body_class='', head_extra='', canonical=True, og_image='', noindex=False, viewport_fit=False, ld=None, article=None):
    # article={'published': 'YYYY-MM-DD', 'updated': 'YYYY-MM-DD' or None, 'verb': 'By'|'Retold by'}: pages we wrote get Mike's
    # byline (after the lede, else after the h1), Article structured data and og:type article. See AUTHOR.
    if article is not None:
        ARTICLES.append({'path': path, 'title': title, 'desc': desc, 'date': article.get('updated') or article.get('published') or PUBLISHED, 'noindex': noindex})
        body = with_byline(body, article)
        ld = (ld or []) + [article_ld(path, title, desc, og_image, article)]
    # Brand suffix only when it still fits in Google's ~60-70 character title space
    full_title = title if title.startswith('Encounter Atlas') or len(title) > 50 else f'{title} | Encounter Atlas'
    nav = nav_html(path)
    # noindex=True for thin template pages (useful to visitors, not worth Google's index): kept out of the sitemap too.
    robots = '<meta name="robots" content="noindex">' if not LAUNCHED else ('<meta name="robots" content="noindex,follow">' if noindex else
                                                                            '<meta name="robots" content="max-image-preview:large">')
    m = re.search(r'"datePublished":\s*"(\d{4}-\d\d-\d\d)', head_extra + json.dumps(ld or []))
    fdate = (article.get('updated') or article.get('published') or PUBLISHED) if article is not None else (m.group(1) if m else None)
    if fdate and not noindex and canonical:
        FEED.append({'path': path, 'title': title, 'desc': desc, 'image': og_image or '/static/og.png', 'date': fdate})
    sec = next(((p, n) for p, n in FEED_SECTIONS if path.startswith(p)), None)
    feeds = (f'<link rel="alternate" type="application/rss+xml" title="Encounter Atlas" href="{SITE_URL}/feed.xml">'
             + (f'<link rel="alternate" type="application/rss+xml" title="Encounter Atlas: {sec[1]}" href="{SITE_URL}{sec[0]}feed.xml">' if sec else ''))
    beacon = ga_tag()
    canon = f'<link rel="canonical" href="{SITE_URL}{path}">' if canonical else ''
    head_extra = re.sub(r'<link rel="stylesheet" href="(https://cdnjs\.cloudflare\.com/ajax/libs/maplibre-gl/[^"]+\.css)">',
                        r"""<link rel="preload" href="\1" as="style" onload="this.onload=null;this.rel='stylesheet'"><noscript><link rel="stylesheet" href="\1"></noscript>""", head_extra)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1{", viewport-fit=cover" if viewport_fit else ""}">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}{canon}
<meta name="theme-color" content="#13261F">
<link rel="icon" href="{url('/static/favicon.svg')}" type="image/svg+xml">
<link rel="manifest" href="{url('/manifest.webmanifest')}">
<link rel="apple-touch-icon" href="{url('/static/apple-touch-icon.png')}">
{feeds}
<meta property="og:type" content="{'article' if ld and any(o.get('@type') == 'Article' for o in ld) else 'website'}">
<meta property="og:site_name" content="Encounter Atlas">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE_URL}{path}">
<meta property="og:image" content="{SITE_URL}{og_image or '/static/og.png'}">
<meta name="twitter:card" content="summary_large_image">
{font_head()}
<link rel="stylesheet" href="{url('/static/site.css')}">
{head_extra}
{ld_json(path, title, body, ld)}
{beacon}
</head>
<body class="{body_class}">
<a class="skip" href="#main">Skip to content</a>
<div class="print-brand" aria-hidden="true"><img src="{url('/static/logo-mark.svg')}" alt="" width="44" height="44"><div><b>Encounter Atlas</b><span>Cryptids, UFOs and close encounters, mapped</span></div><span class="pb-url">encounteratlas.com</span></div>
<div class="print-foot" aria-hidden="true">Printed from encounteratlas.com{esc(path)} · Free to print and share · Report what you saw at encounteratlas.com/report</div>
{'' if path in ('/map/', '/near-me/') else HELLO}
<header class="top">
  <a class="brand" href="{url('/')}"><img class="mark" src="{url('/static/logo-mark.svg')}" alt="" width="42" height="42">Encounter Atlas</a>
  <nav class="nav" aria-label="Main" data-area="main-menu">{nav}</nav>
  <a class="search-btn" href="{url('/search/')}" aria-label="Search the site"{' aria-current="page"' if path == '/search/' else ''}><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg></a>
  <a class="report-btn" href="{url('/report/')}"{' aria-current="page"' if path.startswith('/report/') else ''}><span class="rb-dot" aria-hidden="true"></span><span class="rb-long">Report an encounter</span><span class="rb-short" aria-hidden="true">Report</span></a>
  {mobile_menu(path)}
</header>
<main id="main">
{body}
</main>
<footer class="foot">
  <div class="foot-in">
    <p class="foot-brand"><img class="mark" src="{url('/static/logo-mark.svg')}" alt="" width="42" height="42">Encounter Atlas</p>
    <p>Sightings, creatures and official files, mapped. Reports are what witnesses say they saw. We don't claim they're real, and we don't claim they're not.</p>
    <p class="foot-links"><a href="{url('/about/')}">About and sources</a><a href="{url('/creatures/')}">Creature index</a><a href="{url('/compare/')}">Comparisons</a><a href="{url('/ufo/')}">UFO sightings</a><a href="{url('/encounters/')}">Close encounters</a><a href="{url('/stories/')}">Witness stories</a><a href="{url('/mysteries/')}">Mysteries</a><a href="{url('/on-this-day/')}">On this day</a><a href="{url('/report/')}">Report an encounter</a><a href="{url('/gear/')}">Gear</a><a href="{url('/contact/')}">Contact us</a><a href="{url('/newsletter/')}">Weekly email</a><a href="{url('/feed.xml')}">RSS feed</a><a href="{url('/datasets/')}">Open data</a><a href="{url('/advertise/')}">Advertise with us</a><a href="{url('/privacy/')}">Privacy policy</a></p>
    {social_row('social foot-social')}
    <p class="small">As an Amazon Associate we earn from qualifying purchases. <a href="{url('/privacy/')}#affiliate">About our affiliate links</a>.</p>
    <p class="small">Air Force case files: US National Archives, Record Group 341. Canadian sightings: the Canadian UFO Survey, Ufology Research. Place data: GeoNames (CC BY 4.0). Map: OpenFreeMap, OpenMapTiles, OpenStreetMap contributors.</p>
  </div>
</footer>
<script src="{url('/static/amz.js')}" defer></script>
<script src="{url('/static/signup.js')}" defer></script>
<script>if ('serviceWorker' in navigator) navigator.serviceWorker.register('{url('/sw.js')}');</script>
<script>document.addEventListener('click',e=>{{const a=e.target.closest&&e.target.closest('a[href]');if(a&&/^https?:/.test(a.href)&&!/(^|[.])encounteratlas[.]com$/.test(a.hostname)&&a.host!==location.host&&!a.target){{a.target='_blank';a.rel=((a.rel||'')+' noopener').trim();}}}},true);</script>
<script>(function(){{const dd=[...document.querySelectorAll('.nav-dd, .mm')];dd.forEach(d=>d.addEventListener('toggle',()=>{{if(d.open)dd.forEach(o=>{{if(o!==d)o.open=false;}});}}));document.addEventListener('click',e=>{{dd.forEach(d=>{{if(d.open&&!d.contains(e.target))d.open=false;}});}});document.addEventListener('keydown',e=>{{if(e.key==='Escape')dd.forEach(d=>{{if(d.open){{d.open=false;d.querySelector('summary').focus();}}}});}});}})();</script>
</body>
</html>
'''


def signup_box(uid, title='Strange news, once a week', text=None):
    """Weekly email signup (single opt-in). The newsletter Worker sends people back to /newsletter/#confirmed.
    A dark card with three creature silhouettes, what's in each email, and a short email field (signup.js tracks it)."""
    text = text or 'One short email every Thursday, free, for cryptid and UFO fans everywhere.'
    # A dusk banner across the top of the card: creature silhouettes on the ridge, Nessie in the lake, a saucer overhead
    a = lambda n, c: f'<img class="{c}" src="{url("/static/art/" + n + ".svg")}" alt="" width="80" height="80" loading="lazy">'
    art = (a('ufo-saucer', 'sb-ufo') + a('mothman', 'sb-moth') + a('bigfoot', 'sb-big') + a('dogman', 'sb-dog') + a('loch-ness-monster', 'sb-ness')
           + '<svg class="sb-land" viewBox="0 0 800 60" preserveAspectRatio="none"><path d="M0 34 C90 14 170 12 260 26 S420 44 520 30 L560 32 L800 32 L800 60 L0 60Z" fill="#13261F"/>'
           '<path d="M560 36 L800 36 L800 60 L560 60Z" fill="#1E4A4F"/><path d="M590 44 h60 M690 50 h70" stroke="#F2B33D" stroke-opacity=".35" stroke-width="2"/></svg>')
    return f'''<section class="signup" id="signup-{uid}">
<div class="su-banner" aria-hidden="true">{art}</div>
<div class="su-main"><h2>{esc(title)}</h2>
<p class="su-lede">{esc(text)}</p>
<ul class="su-list"><li><b>From the old newspapers</b> monster and airship stories printed this week, 100+ years ago</li>
<li><b>Creature of the week</b> one cryptid, its best cases and where it is seen</li>
<li><b>New reader reports</b> fresh sightings sent in from around the world</li></ul>
<form action="{NEWSLETTER_API}/subscribe" method="post" data-nl><input type="hidden" name="site" value="encounteratlas">
<input class="visually-hidden" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
<label for="email-{uid}" class="visually-hidden">Email address</label>
<input id="email-{uid}" name="email" type="email" required placeholder="Your email address" autocomplete="email">
<button type="submit" class="btn">Send me the weekly email</button></form>
<p class="su-fine">No spam, never shared. Unsubscribe in one click.</p></div></section>'''


# How the "Seen ...?" box names a creature. Proper names take no article ("Seen Bigfoot?"), kinds of animal
# take a/an ("Seen a chupacabra?"), plurals take none, and named one-off monsters keep "the" (the default).
PROPER_NAMES = {'bigfoot', 'kussie', 'momo', 'mothman', 'owlman', 'ogopogo', 'champ', 'bessie', 'cadborosaurus', 'chessie',
                'memphre', 'igopogo', 'manipogo', 'nahuelito', 'morag', 'morgawr', 'selma', 'mussie', 'old-ned', 'sharlie',
                'ponik', 'cressie', 'issie', 'old-yellow-top', 'tahoe-tessie', 'storsjoodjuret', 'goatman', 'black-shuck',
                'altamaha-ha', 'indrid-cold', 'gef', 'trunko', 'mugwump', 'batsquatch'}
KIND_NAMES = {'yeti', 'yowie', 'skunk-ape', 'dogman', 'chupacabra', 'thunderbird', 'sea-serpent', 'almas', 'yeren',
              'orang-pendek', 'kongamato', 'mokele-mbembe', 'tsuchinoko', 'mapinguari', 'ahool', 'ropen', 'nandi-bear', 'mngwa',
              'tatzelwurm', 'mongolian-death-worm', 'queensland-tiger', 'lusca', 'barmanou', 'mande-barung', 'nittaewo',
              'chuchuna', 'amomongo', 'orang-mawas', 'agogwe', 'dingonek', 'mbielu-mbielu-mbielu', 'emela-ntouka', 'lukwata',
              'minhocao', 'mono-grande', 'waitoreke', 'ningen', 'dobhar-chu', 'grassman', 'sheepsquatch', 'hibagon',
              'shunka-warakin', 'ozark-howler', 'globster'}
PLURAL_NAMES = {'black-eyed-children', 'shadow-people', 'grey-aliens', 'nordic-aliens', 'men-in-black', 'reptilians',
                'thylacine', 'melon-heads', 'fresno-nightcrawlers'}


def a_an(word):
    return 'an' if word[:1].lower() in 'aeiou' else 'a'


def seen_question(c):
    n, sl = c['name'], c['slug']
    if sl == 'thylacine':  # named "Thylacine sightings"
        return 'Seen a thylacine?'
    if sl in PLURAL_NAMES:
        return f'Seen {n if sl in ("nordic-aliens", "men-in-black") else n[0].lower() + n[1:]}?'
    if sl in PROPER_NAMES:
        return f'Seen {n}?'
    if sl in KIND_NAMES:
        n = n.lower() if sl == 'sea-serpent' else n
        return f'Seen {a_an(n)} {n}?'
    return f'Seen the {n[4:] if n.startswith("The ") else n}?'


def badge(c, size='md'):
    if c.get('art'):
        px = 168 if size == 'xl' else 64
        return (f'<span class="badge badge-{size} art cat-{c["cat"]}"><img src="{url("/static/" + c["art"] + ".svg")}" alt="" '
                f'width="{px}" height="{px}" loading="lazy"></span>')
    return (f'<span class="badge badge-{size} cat-{c["cat"]}">{icon(c["icon"])}</span>')


def mini(c):
    """Small creature mark for chips: the silhouette if we have one, else the old icon."""
    if c.get('art'):
        return f'<span class="mini art cat-{c["cat"]}"><img src="{url("/static/" + c["art"] + ".svg")}" alt="" width="26" height="26" loading="lazy"></span>'
    return icon(c['icon'])


POSTER_SKY = {'hominid': ('#E3A649', '#B5532F'), 'canid': ('#3B4C6B', '#1B2A3A'), 'winged': ('#3B4C6B', '#1B2A3A'),
              'aquatic': ('#E8B04A', '#C8693A'), 'entity': ('#3B4C6B', '#1B2A3A'), 'ufo': ('#2E3E5C', '#141E2E'), 'fae': ('#C97B9A', '#4A2E4F'), 'other': ('#E3A649', '#B5532F')}


def poster(c):
    """Park-poster frame for a creature page: dusk sky, ridgeline, pines, and the silhouette in front."""
    a, b = POSTER_SKY.get(c['cat'], POSTER_SKY['other'])
    sid = 'sky-' + c['slug']
    ground = ('<rect y="160" width="200" height="40" fill="#2B4A55"/>' if c['cat'] == 'aquatic' else
              '<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="#1E3A2F"/>')
    return (f'<svg class="poster" viewBox="0 0 200 200" role="img" aria-label="Illustration of the {esc(c["name"][4:] if c["name"].startswith("The ") else c["name"])}: {esc(c["summary"].rstrip("."))}">'
            f'<defs><linearGradient id="{sid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>'
            f'<clipPath id="c{sid}"><rect x="6" y="6" width="188" height="188" rx="10"/></clipPath></defs>'
            f'<g clip-path="url(#c{sid})"><rect width="200" height="200" fill="url(#{sid})"/><circle cx="150" cy="52" r="24" fill="#F3E3B8" opacity=".9"/>'
            f'<path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="#5E4A3A" opacity=".5"/>{ground}'
            f'<image href="{url("/static/" + c["art"] + ".svg")}" x="22" y="{34 if c["cat"] == "aquatic" else 26}" width="160" height="160"/></g>'
            f'<rect x="6" y="6" width="188" height="188" rx="10" fill="none" stroke="#F3E3B8" stroke-width="4"/></svg>')


def creature_card(c, sort=None):
    """sort: on the creature index, a dict of sort keys (n sightings, loc, size, first and last year) shown as a meta line."""
    aka = f'<span class="aka">aka {esc(", ".join(c["aliases"][:2]))}</span>' if c['aliases'] else ''
    data = meta = ''
    if sort:
        data = ''.join(f' data-{k}="{esc(str(v))}"' for k, v in sort.items() if k != 'place')
        n = sort['n']
        meta = (f'<span class="crit-meta"><span class="cm-n">{f"{n} sighting" + ("s" if n != 1 else "") + " on file" if n else "No sightings on file yet"}</span>'
                f'<span class="cm-loc">{esc(sort["place"])}</span></span>')
    return (f'<a class="crit" href="{url("/creatures/" + c["slug"] + "/")}" data-cat="{c["cat"]}"{data} '
            f'data-names="{esc((c["name"] + " " + " ".join(c["aliases"]) + " " + c["region"]).lower())}">'
            f'{badge(c)}<span class="crit-txt"><span class="crit-name">{esc(c["name"])}</span>{aka}'
            f'<span class="crit-sum">{esc(c["summary"])}</span>{meta}</span></a>')


def build_creatures(creatures, by_slug):
    groups = defaultdict(list)
    for c in creatures:
        groups[c['cat']].append(c)
    chips = ''.join(f'<button type="button" class="chip" data-filter="{k}" aria-pressed="false">'
                    f'<span class="dot cat-{k}"></span>{esc(v[0])}</button>' for k, v in CATS.items() if groups[k])
    # Sort keys for the index. "Sightings on file" = famous cases + close encounters + historic newspaper reports
    # (reader reports join once the Worker is live).
    def jload(f):
        fp = os.path.join(ROOT, 'data', f)
        return json.load(open(fp, encoding='utf-8')) if os.path.exists(fp) else []
    countries = jload('countries.json') or {}
    sizes = (jload('sizes.json') or {}).get('sizes', {}) if isinstance(jload('sizes.json'), dict) else {}
    hist = Counter(x.get('creature') for x in jload('historic.json') if x.get('creature'))
    close_n = Counter(s for x in jload('close_encounters.json') for s in x.get('creatures', []))
    WHERE = [('ca', 'Canada'), ('us', 'United States'), ('latam', 'Mexico, Central and South America'), ('eu', 'Europe'),
             ('af', 'Africa'), ('as', 'Asia'), ('oc', 'Australia and the Pacific'), ('world', 'Worldwide')]

    def where(cc):  # filter key for the "Where" menu
        if cc in ('CA', 'US'):
            return cc.lower()
        cont = (countries.get(cc) or ['', ''])[1]
        return {'EU': 'eu', 'AF': 'af', 'AS': 'as', 'OC': 'oc', 'SA': 'latam', 'NA': 'latam'}.get(cont, 'world')
    keys = {}
    for c in creatures:
        yrs = [f['year'] for f in c['famous'] if isinstance(f.get('year'), int)]
        m = re.search(r'\b(1[0-9]{3}|20[0-9]{2})', c.get('first') or '')
        first = min(yrs + ([int(m.group(1))] if m else [])) if (yrs or m) else 9999
        cc = c['cc'][0] if c['cc'] else ''
        cname = (countries.get(cc) or [cc])[0] if cc else 'Worldwide'
        keys[c['slug']] = {'n': len(c['famous']) + close_n[c['slug']] + hist[c['slug']], 'first': first,
                           'last': max(yrs) if yrs else 0, 'size': (sizes.get(c['slug']) or {}).get('draw', 0),
                           'w': ' '.join(sorted({where(x) for x in c['cc']})) or 'world',
                           'loc': (cname + ' ' + c['region']).lower(), 'place': c['region'] if cname in c['region'] or cname == 'Worldwide' else f'{c["region"]}, {cname}'}
    wn = Counter(w for k in keys.values() for w in k['w'].split())
    where_opts = ''.join(f'<option value="{k}">{esc(lab)} ({wn[k]})</option>' for k, lab in WHERE if wn[k])
    sections = ''
    for k, (label, blurb) in CATS.items():
        if not groups[k]:
            continue
        cards = ''.join(creature_card(c, keys[c['slug']]) for c in sorted(groups[k], key=lambda c: (-keys[c['slug']]['n'], c['name'])))
        sections += (f'<section class="cat-group" data-group="{k}"><h2 class="cat-h"><span class="dot cat-{k}"></span>'
                     f'{esc(label)}</h2><p class="cat-blurb">{esc(blurb)}</p><div class="crit-grid">{cards}</div></section>')
    body = f'''
<section class="band band-dark index-head">
  <div class="wrap">
    <h1>Creature index</h1>
    <p class="lede">{len(creatures)} creatures and phenomena, from Bigfoot to the Navy's Tic Tac. Search by any name: Sasquatch, Nessie, goat-sucker. Mixing two up? <a href="{url('/compare/')}">See the comparisons</a>.</p>
    <div class="search-row">
      <label class="visually-hidden" for="q">Search creatures</label>
      <input id="q" type="search" placeholder="Search by name, nickname or place" autocomplete="off">
    </div>
    <div class="chips" role="group" aria-label="Filter by type">{chips}</div>
    <div class="sort-row"><label for="where">Where</label>
      <select id="where"><option value="">Anywhere ({len(creatures)})</option>{where_opts}</select></div>
    <div class="sort-row"><label for="sort">Sort each group by</label>
      <select id="sort">
        <option value="most">Most sightings</option><option value="fewest">Fewest sightings</option>
        <option value="recent">Most recent sighting</option><option value="oldest">Oldest first record</option>
        <option value="loc">Location (country, then region)</option><option value="size">Biggest first</option>
        <option value="az">Name, A to Z</option>
      </select>
      <span class="sort-note">Sightings on file: famous cases, close encounters and historic newspaper reports.</span></div>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  {sections}
  <p class="empty" hidden>No creature by that name yet. <a href="{url('/report/')}">Tell us about it</a> and we'll add it.</p>
</div></div>
<script src="{url('/static/index.js')}" defer></script>'''
    write('/creatures/', page('/creatures/', 'Creature index: cryptids, monsters and UFO types', body,
                              'Searchable index of cryptids and UFO types with alternative names, famous cases and what witnesses report.'))

    def load(name):
        fp = os.path.join(ROOT, 'data', name)
        return json.load(open(fp)) if os.path.exists(fp) else []
    places = load('places.json')
    guides = load('guides.json')
    fam_geo = Counter(f['creature'] for f in load('famous_geo.json'))
    close_enc = load('close_encounters.json')
    historic = load('historic.json')
    CAT_GUIDES = {'hominid': ['bigfoot-expedition', 'casting-tracks', 'trail-cameras'], 'canid': ['dogman-and-night-encounters', 'trail-cameras'],
                  'ufo': ['skywatching'], 'winged': ['dogman-and-night-encounters'], 'aquatic': [], 'entity': ['dogman-and-night-encounters'], 'fae': [], 'other': []}
    PLACE_KIND = {'museum': 'Museum', 'festival': 'Festival', 'attraction': 'Roadside stop', 'expedition': 'Tour'}

    def extras(c):
        """Map, places, guides and the contribution panel: the 'what next' part of each creature page."""
        out = ''
        n = fam_geo.get(c['slug'], 0)
        np = sum(c['slug'] in (x.get('creatures') or []) for x in places)
        if n or np:  # no card when there is nothing of this creature's own to pin
            what = [f'{n} famous case{"s" if n != 1 else ""}'] if n else []
            what += [f'{np} place{"s" if np != 1 else ""} to visit'] if np else []
            out += (f'<a class="next-card next-map cat-{c["cat"]}" href="{url("/map/?creature=" + c["slug"])}">{crit_icon(c)}'
                    f'<span><b>See {esc(c["name"])} on the map</b><small>{" and ".join(what)} pinned'
                    f'{", plus reader reports" if EA_API else ""}</small></span></a>')
        ce = [x for x in close_enc if c['slug'] in x.get('creatures', [])][:5]
        if ce:
            items = ''.join(f'<li><a href="{url("/encounters/" + x["slug"] + "/")}">{esc(x["name"])}</a><small>{esc(x["place"])}, {x["year"]}</small></li>' for x in ce)
            out += f'<div class="next-block"><h3>Close encounters</h3><ul class="next-list">{items}</ul></div>'
        hs = sorted((x for x in historic if x.get('creature') == c['slug']), key=lambda x: x['date'])
        if hs:  # old newspaper reports (site/sections/historic.py); cards there have id="h-<id>"
            HPAGE = {'airship': 'airships-1896-1897', 'airship-1909': 'phantom-airships-1909', 'wild-man': 'wild-men', 'sea-serpent': 'sea-serpents',
                     'jersey-devil': 'jersey-devil-1909', 'giant-bird': 'giant-birds', 'phantom-light': 'phantom-lights', 'creature': 'strange-creatures'}
            pick = hs if len(hs) <= 6 else hs[:3] + hs[-3:]  # oldest and newest
            items = ''.join(f'<li><a href="{url("/history/" + HPAGE.get(x["k"], "") + "/")}#h-{esc(x["id"])}">{esc(x["title"])}</a>'
                            f'<small>{esc(x["town"] or x["place"])}, {x["date"][:4]}</small></li>' for x in pick)
            more = (f'<p class="next-more"><a href="{url("/history/" + HPAGE.get(hs[0]["k"], "") + "/")}">{len(hs)} reports in all: see the history pages</a></p>'
                    if len(hs) > 6 else '')
            out += f'<div class="next-block"><h3>In old newspapers</h3><ul class="next-list">{items}</ul>{more}</div>'
        pl = [x for x in places if c['slug'] in (x.get('creatures') or [])]
        if pl:
            # Every linked place, so each place page gets a link back from its creature; past eight they sit in a
            # <details> (still plain links in the HTML) so long lists like Bigfoot's don't swamp the page
            li = lambda x: (f'<li><a href="{url("/places/" + x["slug"] + "/")}">{esc(x["name"])}</a>'
                            f'<small>{esc(PLACE_KIND.get(x["type"], "Place"))}{", " + esc(x["city"]) if x.get("city") else ""}'
                            f'{", " + esc(x["region"]) if x.get("region") else ""}</small></li>')
            items = ''.join(li(x) for x in pl[:8])
            more = (f'<details class="next-more-places"><summary>{len(pl) - 8} more place{"s" if len(pl) - 8 != 1 else ""} to visit</summary>'
                    f'<ul class="next-list">{"".join(li(x) for x in pl[8:])}</ul></details>' if len(pl) > 8 else '')
            out += f'<div class="next-block"><h3>Go see it</h3><ul class="next-list">{items}</ul>{more}</div>'
        return out

    def guide_band(c):
        """Field guides for this creature, as a full-width band of cards (more prominent than the old sidebar list)."""
        gs = [g for g in guides if c['slug'] in (g.get('creatures') or [])]
        gs += [g for g in guides if g['slug'] in CAT_GUIDES.get(c['cat'], []) and g not in gs]
        if len(gs) < 3:
            gs += [g for g in guides if g['slug'] == 'how-to-report' and g not in gs]
        gs = gs[:3]
        if not gs:
            return ''
        cards = ''.join(f'<a class="cg-card" href="{url("/guides/" + g["slug"] + "/")}"><span class="cg-ico tone-{g.get("tone", "other")}">{icon(g["icon"])}</span>'
                        f'<span><span class="cg-kick">{esc(g.get("kicker") or "Field guide")}</span><b>{esc(g.get("short") or g["title"])}</b>'
                        f'<small>{esc(g.get("blurb") or "")}</small><span class="cg-go">Read the guide{" · printable checklist" if g.get("printable") else ""}</span></span></a>' for g in gs)
        return (f'<section class="band band-dark cg-band" id="guides"><div class="wrap"><h2>{"Out where the stories are told?" if kind(c) == "folklore" else "Watching the skies?" if kind(c) == "ufo" else "Going looking for the " + esc(c["name"]) + "?"}</h2>'
                f'<p class="lede-dark">Our field guides cover where to go, what to bring and how to come back with evidence that holds up.</p>'
                f'<div class="cg-grid">{cards}</div><p class="cg-all"><a href="{url("/guides/")}">All field guides</a></p></div></section>')

    # Books, documentaries and gear (Amazon Associates). Every book/documentary is checked to exist first
    # (tools/verify_media.py -> data/media.json). Living traditions get no shopping at all.
    MEDIA = load('media.json') or {'books': [], 'docs': []}
    for _d in MEDIA['docs']:
        _b = re.sub(r'^\d{4} ', '', _d['blurb'])
        _d['blurb'] = _b[:1].upper() + _b[1:]
    CANDS = {(b['t'], b['a']): b for b in (load('media_candidates.json') or {}).get('books', [])}
    GROUPS = {'hominid': ['@hominid'], 'aquatic': ['@lake', '@sea'], 'ufo': ['@ufo'], 'entity': ['@ufo'], 'fae': ['@fae']}
    GEAR = {
        'ufo': [('Astronomy binoculars', 'astronomy binoculars', 'binoculars'), ('Planisphere star finder', 'planisphere star chart', 'stars'),
                ('Phone tripod for night shots', 'phone tripod night sky', 'tripod'), ('Red-light headlamp', 'red light headlamp astronomy', 'lamp')],
        'aquatic': [('Waterproof binoculars', 'waterproof binoculars', 'binoculars'), ('Waterproof action camera', 'waterproof action camera', 'camera'),
                    ('Phone telephoto lens', 'phone telephoto lens', 'camera'), ('Dry bag', 'dry bag', 'pack')],
        'woods': [('Trail camera', 'trail camera', 'camera'), ('Thermal monocular', 'thermal monocular', 'binoculars'),
                  ('Track casting plaster', 'plaster casting kit animal tracks', 'track'), ('Digital audio recorder', 'digital audio recorder', 'mic')],
    }
    AMZ_TAG = 'encountersatlas-20'
    AUDIBLE = 'https://www.amazon.com/hz/audible/mlp?tag=' + AMZ_TAG  # Audible free-trial page (Associates bounty)

    def amz(q, index=''):
        return ('https://www.amazon.com/s?' + urllib.parse.urlencode({'k': q, **({'i': index} if index else {}), 'tag': AMZ_TAG}))

    def media_band(c):
        sl = c['slug']
        if sl in LIVING_TRADITIONS:
            return ''
        groups = GROUPS.get(c['cat'], [])
        spec = [b for b in MEDIA['books'] if sl in b['for']][:6]
        general = []
        if len(spec) < 3:
            general = [b for b in MEDIA['books'] if any(g in b['for'] for g in groups) and b not in spec]
            general += [b for b in MEDIA['books'] if '@general' in b['for'] and b not in spec and b not in general]
            general = general[:max(0, 3 - len(spec))]
        docs = [d for d in MEDIA['docs'] if sl in d['for']]
        docs += [d for d in MEDIA['docs'] if any(g in d['for'] for g in groups) and d not in docs]
        docs = docs[:3]

        def book_card(b, i):
            cand = next((v for (bt, ba), v in CANDS.items() if v['for'] == b['for'] and ba.lower() in b['author'].lower()), None)
            title = cand['t'] if cand else b['title']
            author = b['author'].split(',')[0] if ', ' not in b['author'] or b['author'].count(',') > 1 else b['author']
            if re.match(r'^[A-Z][a-z]+, [A-Z]', author):  # "Owen, David" -> "David Owen"
                author = ' '.join(reversed(author.split(', ', 1)))
            href = amz(f'{title} {author.split(",")[0]}', 'stripbooks')
            return (f'<a class="md-book tone-{i % 5}" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">'
                    f'<span class="md-spine" aria-hidden="true"></span><span class="md-txt"><b>{esc(title)}</b><small>{esc(author)}</small>'
                    f'<span class="md-go">Find it on Amazon</span></span></a>')
        out = ''
        if spec or general:
            out += f'<h3>Books about the {esc(c["name"])}</h3><div class="md-grid">{"".join(book_card(b, i) for i, b in enumerate(spec))}</div>' if spec else ''
            if general:
                out += (f'<h3>{"More good reads" if spec else "General books on " + ("UFOs" if c["cat"] in ("ufo", "entity") else "fairy lore" if c["cat"] == "fae" else "cryptids")}</h3>'
                        f'{"" if spec else "<p class=md-note>No book is devoted to this one yet, so here are the best general guides.</p>"}'
                        f'<div class="md-grid">{"".join(book_card(b, i + len(spec)) for i, b in enumerate(general))}</div>')
        if spec or general:
            out += (f'<p class="md-listen">Prefer to listen? <a href="{AUDIBLE}" rel="sponsored nofollow noopener" target="_blank">Try Audible free</a> '
                    f'and hear cryptid and UFO books on the drive to the trailhead.</p>')
        if docs:
            cards = ''.join(f'<div class="md-doc"><span class="md-ico">{icon("ufo-film")}</span><span class="md-txt"><b>{esc(d["title"])}</b>'
                            f'<small>{d["year"]} · {esc(d["blurb"])}</small>'
                            f'<span class="md-links"><a href="{esc(amz(d["title"] + " " + str(d["year"]), "instant-video"))}" rel="sponsored nofollow noopener" target="_blank">Watch on Amazon</a>'
                            f'<a href="https://www.justwatch.com/us/search?q={urllib.parse.quote(d["title"])}" rel="noopener nofollow" target="_blank">Where to stream</a>'
                            f'<a href="{esc(d["wiki"])}" rel="noopener" target="_blank">About it</a></span></span></div>' for d in docs)
            out += f'<h3>Watch</h3><div class="md-grid">{cards}</div>'
        if kind(c) not in ('single', 'folklore'):
            gear = GEAR['ufo' if c['cat'] in ('ufo', 'entity') else 'aquatic' if c['cat'] == 'aquatic' else 'woods']
            chips = ''.join(f'<a class="md-chip" href="{esc(amz(q))}" rel="sponsored nofollow noopener" target="_blank">{esc(n)}</a>' for n, q, _ in gear)
            out += (f'<h3>Gear for the field</h3><div class="md-chips">{chips}'
                    f'<a class="md-chip md-merch" href="{esc(amz(("UFO" if c["cat"] == "ufo" else c["name"]) + " shirt"))}" rel="sponsored nofollow noopener" target="_blank">'
                    f'{esc("UFO" if c["cat"] == "ufo" else c["name"])} shirts and gifts</a><a class="md-chip" href="{url("/gear/")}">All field gear</a></div>')
        elif kind(c) == 'folklore' and c['cat'] == 'fae':
            out += (f'<h3>Shop</h3><div class="md-chips"><a class="md-chip md-merch" href="{esc(amz(c["name"] + " gifts"))}" rel="sponsored nofollow noopener" target="_blank">'
                    f'{esc(c["name"])} gifts and decor</a></div>')
        if not out:
            return ''
        return (f'<section class="band band-mist md-band" id="books"><div class="wrap"><h2>Read, watch and gear up <a class="md-aff" href="{url("/privacy/")}#affiliate">(affiliate links)</a></h2>{out}'
                f'</div></section>')

    COUNTRIES = load('countries.json') or {}
    if isinstance(COUNTRIES, list):
        COUNTRIES = {}
    famous_details = {}
    for fn in ('famous_details_a.json', 'famous_details_b.json'):
        d = load(fn)
        if isinstance(d, dict):
            famous_details.update(d)
    famous_details.update(STORY_DETAILS)

    KINDS = load('creature_kinds.json') or {}
    # Folklore hybrid (Mike approved 2026-10-12): stories first, then modern claimed sightings, and both
    # actions in the box. Living traditions get a respect note, and their reports are shown at region precision only (enforced by the Worker's LIVING_TRADITIONS; keep both lists in sync).
    FOLK_HYBRID = True
    LIVING_TRADITIONS = {'skinwalker', 'menk', 'wendigo', 'kushtaka', 'pukwudgie', 'menehune', 'yunwi-tsunsdi', 'mannegishi',
                         'makiawisug', 'nimerigar', 'tokoloshe', 'mami-wata', 'inkanyamba', 'alux', 'mamlambo'}

    def kind(c):
        """cryptid (still reported), single (one exhibit, hoax or incident), folklore (a told tradition) or ufo."""
        return 'ufo' if c['cat'] == 'ufo' else KINDS.get(c['slug'], 'cryptid')

    def seen_box(c):
        k, n, sl = kind(c), esc(c['name']), c['slug']
        extra = ''
        if k == 'single':
            h, p = f'Know more about the {n}?', ('Found an old article, a photo or a mistake on this page? Send it in. '
                                                 'Every note is read by a person, and we credit sources.')
            acts = f'<a class="btn" href="{url("/report/?about=" + sl)}">Add a detail or correction</a>'
        elif k == 'folklore' and FOLK_HYBRID:
            h = 'Seen something, or heard a local story?'
            p = ('Tell us what happened, or share a story passed down in your family or community. '
                 'Every report is read by a person, and you can stay anonymous.')
            if sl in LIVING_TRADITIONS:
                p += (' This is part of a living tradition. Please write respectfully, and we only map reports '
                      'to the nearest region, never an exact spot.')
            acts = (f'<a class="btn" href="{url("/report/?creature=" + sl)}">Report an encounter</a>\n        '
                    f'<a class="btn btn-ghost" href="{url("/report/?story=" + sl)}">Share a story</a>')
        elif k == 'folklore':
            h, p = 'Heard a local story, or had an experience?', ('Stories passed down in families and communities matter. '
                                                                   'Share yours in your own words, and you can stay anonymous.')
            acts = f'<a class="btn" href="{url("/report/?creature=" + sl)}">Share your story</a>'
        else:
            h = 'Seen one?' if k == 'ufo' else seen_question(c)
            p = 'Tell us what happened. Every report is read by a person before it goes on the map, and you can stay anonymous.'
            label = 'Report a sighting' if k == 'ufo' or sl == 'thylacine' else 'Report an encounter' if sl in PLURAL_NAMES else f'Report {a_an(n)} {n} encounter'
            acts = f'<a class="btn" href="{url("/report/?creature=" + sl)}">{label}</a>'
            if os.path.exists(os.path.join(ROOT, 'data', 'identify.json')):
                acts += f'\n        <a class="btn btn-ghost" href="{url("/tools/what-did-i-see/")}">Not sure what it was?</a>'
            extra = f'<p class="seen-print"><a href="{url("/printables/after-an-encounter/")}">Print a record sheet</a> to fill in while it\'s fresh.</p>'
        return (f'<section class="seen-box cat-{c["cat"]}" aria-labelledby="seen-{sl}">\n      {crit_icon(c)}\n      <div>\n'
                f'        <h2 id="seen-{sl}">{h}</h2>\n        <p>{p}</p>\n        <p class="seen-actions">{acts}</p>\n        {extra}\n      </div>\n    </section>')

    _cp = os.path.join(ROOT, 'data', 'compare.json')
    COMPARE = json.load(open(_cp, encoding='utf-8')) if os.path.exists(_cp) else []

    def related_groups(c):
        """Two labelled groups: similar creatures (same kind) and others reported in the same country or continent."""
        cur = [by_slug[s] for s in c['related'] if s in by_slug]
        cc = set(c['cc'])
        conts = {COUNTRIES.get(x, ['', ''])[1] for x in cc} - {''}
        def near(o):
            return 2 if cc & set(o['cc']) else (1 if conts & {COUNTRIES.get(x, ['', ''])[1] for x in o['cc']} else 0)
        same = [o for o in creatures if o['cat'] == c['cat'] and o['slug'] != c['slug']]
        similar = [o for o in cur if o['cat'] == c['cat']]
        similar += sorted((o for o in same if o not in similar), key=lambda o: (-near(o), o['name']))
        similar = similar[:6]
        others = [o for o in creatures if o['slug'] != c['slug'] and o not in similar and near(o)]
        others.sort(key=lambda o: (-(o in cur), -near(o), o['name']))
        nearby = others[:6]
        if cc and any(near(o) == 2 for o in nearby):
            where = ', '.join(COUNTRIES.get(x, [x])[0] for x in sorted(cc)[:3])
        else:
            names = {'NA': 'North America', 'SA': 'South America', 'EU': 'Europe', 'AF': 'Africa', 'AS': 'Asia', 'OC': 'Oceania', 'AN': 'Antarctica'}
            where = ', '.join(names.get(x, x) for x in sorted(conts)) or 'the same part of the world'
        out = ''
        cmps = [x for x in COMPARE if c['slug'] in (x['a'], x['b']) and x['a'] in by_slug and x['b'] in by_slug]
        if cmps:
            out += ('<h2 class="rel-h">Often confused with</h2><p class="rel-why">Side-by-side guides: how to tell which one you saw.</p><ul class="cmp-links">'
                    + ''.join(f'<li><a href="{url("/compare/" + x["a"] + "-vs-" + x["b"] + "/")}">{esc(by_slug[x["a"]]["name"])} vs {esc(by_slug[x["b"]]["name"])}</a></li>' for x in cmps)
                    + '</ul>')
        if similar:
            out += (f'<h2 class="rel-h">Similar creatures</h2><p class="rel-why">Other {esc(CATS[c["cat"]][0].lower())} from around the world.</p>'
                    f'<div class="crit-grid">{"".join(creature_card(o) for o in similar)}</div>')
        if nearby:
            out += (f'<h2 class="rel-h">Also from {esc(where)}</h2><p class="rel-why">Different creatures from the same part of the world.</p>'
                    f'<div class="crit-grid">{"".join(creature_card(o) for o in nearby)}</div>')
        return f'<div class="wrap rel-wrap">{out}</div>' if out else ''

    WITNESS = {}
    for st in load('witness_stories.json'):
        WITNESS.setdefault(st['creature'], []).append(st)

    def witness_section(c):
        sts = sorted(WITNESS.get(c['slug'], []), key=lambda x: -x['year'])
        if not sts:
            return ''
        cards = ''.join(f'<a class="ws-card" href="{url("/stories/" + x["id"] + "/")}"><b>{esc(x["title"])}</b>'
                        f'<span class="ws-meta">{esc(x["place"])} · {esc(x["when"])}</span><span class="ws-dek">{esc(x["dek"])}</span>'
                        f'<span class="ws-go">Read the story · {max(1, round(sum(len(p.split()) for p in x["body"]) / 230))} min</span></a>'
                        for x in sts[:6])
        more = (f'<p class="ws-more"><a class="btn btn-quiet" href="{url("/stories/?c=" + c["slug"])}">Read all {len(sts)} {esc(c["name"])} stories</a></p>'
                if len(sts) > 6 else '')
        return (f'<h2 id="witness">Witness stories</h2><p class="ws-intro">First-hand accounts people have shared publicly, '
                f'retold in full and credited to them. <a href="{url("/stories/")}">All witness stories</a></p>'
                f'<div class="ws-grid">{cards}</div>{more}')

    def papers_section(c):
        ps = sorted(c.get('papers', []), key=lambda x: x['year'])
        if not ps:
            return ''
        items = ''.join(f'<li><span class="yr">{x["year"]}</span><span><strong>{esc(x["name"])}</strong><br><span class="muted">{esc(x["place"])}</span>'
                        f'<p class="case-sum">{esc(x["summary"])}</p><p class="case-links"><a class="case-src" href="{esc(x["source_url"])}" rel="noopener">'
                        f'Source: {esc(x["source_title"])}</a></p></span></li>' for x in ps)
        return f'<h2 id="papers">In the old newspapers</h2><ol class="timeline">{items}</ol>'

    def case_item(c, f):
        d = famous_details.get(c['slug'] + '|' + f['name']) or {}
        story = story_url(c['slug'], f['year'])
        extra = ''
        if d.get('summary'):
            extra += f'<p class="case-sum">{esc(d["summary"])}</p>'
        links = []
        if story:
            links.append(f'<a class="full-story" href="{story}">Read the full story</a>')
        if d.get('source_url'):
            links.append(f'<a class="case-src" href="{esc(d["source_url"])}" rel="noopener">Source: {esc(d.get("source_title") or "read more")}</a>')
        if links:
            extra += f'<p class="case-links">{"".join(links)}</p>'
        return (f'<li><span class="yr">{f["year"]}</span><span><strong>{esc(f["name"])}</strong>'
                f'<br><span class="muted">{esc(f["place"])}</span>{extra}</span></li>')

    def extra_sections(c):
        """Hand-written longer sections for priority pages: data/creatures.json "sections": [{"h": heading, "p": [paragraphs]}]."""
        return ''.join(f'<h2>{esc(x["h"])}</h2>' + ''.join(f'<p>{md_links(t)}</p>' for t in x['p']) for x in c.get('sections', []))

    def faq_section(c):
        """Short answers to what people actually search (Search Console), as question headings: "faq": [{"q", "a"}]."""
        if not c.get('faq'):
            return ''
        return ('<h2 id="questions">Questions people ask</h2>'
                + ''.join(f'<h3>{esc(x["q"])}</h3><p>{md_links(x["a"])}</p>' for x in c['faq']))

    for c in creatures:
        aka = (f'<p class="aka-line">Also called {esc(", ".join(c["aliases"]))}</p>' if c['aliases'] else '')
        facts = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in
                        [('Where', c['region']), ('Size', c['size']), ('Setting' if kind(c) == 'single' else 'Habitat', c['habitat']),
                         ({'single': 'When', 'folklore': 'Earliest record'}.get(kind(c), 'First reported'), c['first'])] if v)
        body_p = ''.join(f'<p>{esc(p)}</p>' for p in c['body'])
        signs = ''.join(f'<li>{esc(s)}</li>' for s in c['signs'])
        fam = sorted(c['famous'], key=lambda f: f['year'])
        modern = ''
        if kind(c) == 'folklore' and FOLK_HYBRID:
            yr = lambda f: f['year'] if isinstance(f['year'], int) else 0
            modern = ''.join(case_item(c, f) for f in fam if yr(f) >= 1900)
            fam = [f for f in fam if yr(f) < 1900]
        cases = ''.join(case_item(c, f) for f in fam)
        first_story = story_url(c['slug'], 'first')
        rel = ''.join(creature_card(by_slug[s]) for s in c['related'] if s in by_slug)
        wiki = f'https://en.wikipedia.org/wiki/{c["wiki"].replace(" ", "_")}' if c.get('wiki') else ''
        ufo_note = ''
        if c['cat'] == 'ufo':
            ufo_note = (f'<p class="callout">{icon("folder", "ico ico-inline")} Browse 10,622 US Air Force Project Blue Book '
                        f'case files on the <a href="{url("/map/")}">map</a> or <a href="{url("/ufo/blue-book/")}">by state</a>.</p>')
        gb, mb = (guide_band(c) if kind(c) != 'single' else ''), media_band(c)
        jumps = [('#witness', 'Witness stories') if WITNESS.get(c['slug']) else None, ('#cases', 'Timeline' if kind(c) == 'single' else 'Famous cases') if cases else None, ('#modern', 'Modern reports') if modern else None, ('#papers', 'Old newspapers') if c.get('papers') else None,
                 ('#questions', 'Questions') if c.get('faq') else None, ('#facts', 'Facts'), ('#guides', 'Field guides') if gb else None, ('#books', 'Books and gear') if mb else None, ('#related', 'Similar creatures')]
        jump = '<nav class="jump" aria-label="On this page">' + ''.join(f'<a href="{h}">{t}</a>' for h, t in filter(None, jumps)) + '</nav>'
        nws = len(WITNESS.get(c['slug'], []))
        reads = (f'<a href="{url("/stories/?c=" + c["slug"])}">{"Read " + str(nws) + " witness " + ("story" if nws == 1 else "stories") if nws else "Read witness stories"}</a>')
        if EA_API:
            # Filled in by creature.js once this creature has approved reader reports.
            reads += f'<a href="{url("/reports/?creature=" + c["slug"])}" data-rr-link hidden>Reader reports</a>'
        reads = f'<p class="crit-reads">{reads}</p>'
        rr_sec = (f'<section id="reader" class="rr-sec" data-rr="{c["slug"]}" data-api="{EA_API}" hidden><h2>Reader reports</h2>'
                  f'<p class="ws-intro">Encounters sent in by our readers and checked by a moderator.</p><div class="rr-list"></div>'
                  f'<p><a href="{url("/reports/?creature=" + c["slug"])}">All {esc(c["name"])} reports</a></p></section>') if EA_API else ''
        body = f'''
<section class="band band-dark creature-head cat-{c['cat']}">
  <div class="wrap creature-head-in">
    {poster(c) if c.get('art') else badge(c, 'xl')}
    <div>
      <p class="crumb"><a href="{url('/creatures/')}">Creature index</a> / {esc(CATS[c['cat']][0])}</p>
      <h1>{esc(c['name'])}</h1>
      {aka}
      <p class="lede">{esc(c['summary'])}</p>
      {f'<p class="lede-story"><a href="{first_story[0]}">Read the full story: {esc(first_story[1])}</a></p>' if first_story else ''}
      {jump}
      {reads}
    </div>
  </div>
</section>
<div class="band band-mist"><div class="wrap creature-body">
  <article class="prose">
    {'<h2>The story</h2>' if kind(c) == 'single' else ''}
    {body_p}
    {extra_sections(c)}
    {ufo_note}
    <h2>{ {'single': 'What was shown or claimed', 'folklore': 'What the stories say'}.get(kind(c), 'What witnesses report') }</h2>
    <ul class="signs">{signs}</ul>
    {witness_section(c)}
    {rr_sec}
    {f'<h2 id="cases">{"Timeline" if kind(c) == "single" else "Famous cases"}</h2><ol class="timeline">{cases}</ol>' if cases else ''}
    {f'<h2 id="modern">Modern reports</h2><ol class="timeline">{modern}</ol>' if modern else ''}
    {papers_section(c)}
    {faq_section(c)}
    {seen_box(c)}
  </article>
  <aside class="side">
    <div class="facts" id="facts">
      <dl>{facts}</dl>
      {f'<p class="more"><a href="{wiki}" rel="noopener">Read more on Wikipedia</a></p>' if wiki else ''}
    </div>
    {extras(c)}
  </aside>
</div>
</div>
{gb}
{mb}
<div class="band band-mist" id="related">{related_groups(c)}</div>
<div class="band band-mist nl-band"><div class="wrap">{signup_box('c', 'Get strange news, once a week', 'New ' + c['name'] + ' and cryptid reports, a creature of the week and what the old newspapers said this week. One short email on Thursdays, unsubscribe in one click.')}</div></div>'''
        title = c.get('seo_title') or (f'{c["name"]}: ' + {'single': 'the story, facts and other names', 'folklore': 'stories, facts and other names'}.get(kind(c), 'sightings, facts and other names'))
        desc = c.get('seo_desc') or (f'{c["summary"]} Also called {", ".join(c["aliases"][:4])}.' if c['aliases'] else c['summary'])
        og = f'/static/og/creatures/{c["slug"]}.jpg'
        og = og if os.path.exists(os.path.join(STATIC, 'og', 'creatures', c['slug'] + '.jpg')) else ''
        write(f'/creatures/{c["slug"]}/', page(f'/creatures/{c["slug"]}/', title, body, desc, og_image=og, article={'updated': c.get('updated')},
                                               head_extra=f'<script src="{url("/static/creature.js")}" defer></script>' if EA_API else ''))


def case_line(b):
    when = f'{MONTHS[b["month"]]} {b["year"]}' if b.get('month') and b.get('year') else (str(b['year']) if b.get('year') else 'Date unknown')
    place = b['place'] or b['region'] or 'Unknown place'
    scan = f' <a class="muted" href="{esc(b["img"])}" rel="noopener">first page</a>' if b.get('img') else ''
    return (f'<li><span class="yr">{esc(when)}</span><span><a href="https://catalog.archives.gov/id/{b["id"]}" rel="noopener">'
            f'{esc(place)}</a>{scan}</span></li>')


def region_slug(b):
    if b['cc'] == 'US' and b['a1']:
        return 'us-' + slugify(b['region'])
    if b['cc']:
        return slugify(b.get('country') or b['region'] or b['cc'])
    return 'unknown'


def build_ufo(bluebook, BY_SLUG):
    by_region = defaultdict(list)
    for b in bluebook:
        by_region[region_slug(b)].append(b)
    names = {}
    for k, v in by_region.items():
        b = v[0]
        names[k] = (b['region'] if b['cc'] == 'US' else b.get('country') or b['region']) if b['cc'] else 'Place unclear or at sea'
    years = Counter(b['year'] for b in bluebook if b.get('year'))
    ymax = max(years.values())
    bars = ''
    for y in range(1947, 1970):
        n = years.get(y, 0)
        h = round(100 * n / ymax)
        bars += (f'<div class="bar" style="--h:{h}%" title="{y}: {n:,} cases"><span class="bar-n">{n:,}</span>'
                 f'<span class="bar-y">{"&#8217;" + str(y)[2:] if y % 2 else "&#8217;" + str(y)[2:]}</span></div>')
    us = sorted((k for k in by_region if k.startswith('us-')), key=lambda k: names[k])
    other = sorted((k for k in by_region if not k.startswith('us-') and k != 'unknown'), key=lambda k: -len(by_region[k]))
    def links(keys):
        return ''.join(f'<li><a href="{url("/ufo/blue-book/" + k + "/")}">{esc(names[k])}</a> <span class="muted">{len(by_region[k]):,}</span></li>' for k in keys)
    top = Counter({names[k]: len(by_region[k]) for k in us}).most_common(1)[0]
    body = f'''
<section class="band band-dark">
  <div class="wrap">
    <p class="crumb"><a href="{url('/ufo/')}">UFOs</a> / Air Force files</p>
    <h1>Project Blue Book: the Air Force UFO files</h1>
    <p class="lede">From 1947 to 1969 the US Air Force investigated {len(bluebook):,} UFO reports. Every case folder is now public at the National Archives. We've put them on a map and sorted them by state and country.</p>
    <nav class="tiles ufo-more" aria-label="More official UFO files">
      <a class="tile" href="{url('/ufo/releases/')}">{icon('folder')}<span>Every official release, 13 countries</span></a>
      <a class="tile" href="{url('/ufo/files/pursue/')}">{icon('military')}<span>The Pentagon's 2026 files</span></a>
      <a class="tile" href="{url('/ufo/files/faa/')}">{icon('saucer')}<span>FAA pilot reports, 2007 to 2024</span></a>
      <a class="tile" href="{url('/ufo/canada/')}">{icon('saucer')}<span>Canada sightings, 1989 to today</span></a>
      <a class="tile" href="{url('/ufo/countries/')}">{icon('ufo-globe') if os.path.exists(os.path.join(STATIC, 'icons', 'ufo-globe.svg')) else icon('saucer')}<span>UFO files by country</span></a>
      <a class="tile" href="{url('/encounters/')}">{icon('entity')}<span>Close encounters with beings</span></a>
      <a class="tile" href="{url('/ufo/cases/')}">{icon('saucer')}<span>Famous cases worldwide</span></a>
    </nav>
    <p><a class="btn" href="{url('/map/')}">Open the map</a></p>
  </div>
</section>
<div class="band band-mist"><div class="wrap">
  <h2>Cases by year</h2>
  <p>{max(years, key=years.get)} was the busiest year, with {ymax:,} reports. The big spikes match famous flaps: the Washington, DC sightings of 1952, the Levelland wave of 1957 and the Michigan “swamp gas” reports of 1966.</p>
  <div class="bars" role="img" aria-label="Bar chart of Blue Book cases per year, 1947 to 1969">{bars}</div>
  <h2>United States</h2>
  <p>{esc(top[0])} has the most case folders ({top[1]:,}).</p>
  <ul class="cols">{links(us)}</ul>
  <h2>Rest of the world</h2>
  <p>Air Force personnel overseas and allied militaries also sent in reports.</p>
  <ul class="cols">{links(other)}</ul>
  <p class="small">{len(by_region.get('unknown', [])):,} folders have no readable place (marked “[Blank]” or “[Illegible]” on the original). <a href="{url('/ufo/blue-book/unknown/')}">See them here</a>.</p>
  <h2>About these files</h2>
  <p>Each link opens the case folder in the National Archives catalog, where you can read the scanned pages: witness forms, teletype messages, sketches and the Air Force's conclusion. Names of witnesses were blacked out before release. Most cases were explained as aircraft, balloons, stars or planets. 701 stayed “unidentified”.</p>
</div></div>'''
    write('/ufo/blue-book/', page('/ufo/blue-book/', 'Project Blue Book UFO files by state, year and map', body,
                        f'All {len(bluebook):,} US Air Force Project Blue Book UFO case files (1947-1969), mapped and listed by state and country.'))
    # "Also in <place>": the rest of the site for the same state or country (creatures, places, newspapers, FAA, Canada)
    sys.path.insert(0, os.path.join(ROOT, 'collector'))
    from geo import Areas
    areas = Areas()
    ld = lambda f: json.load(open(os.path.join(ROOT, 'data', f), encoding='utf-8')) if os.path.exists(os.path.join(ROOT, 'data', f)) else []
    fam_at = defaultdict(list)
    for f in ld('famous_geo.json'):
        if f['creature'] in BY_SLUG:
            cc, a1 = areas.where(f['lat'], f['lon'])
            fam_at[(cc, a1)].append(f)
            fam_at[(cc, None)].append(f)
    place_regions = Counter(x['region'] for x in ld('places.json') if x.get('region'))
    hist_states = Counter(h['state'] for h in ld('historic.json') if h.get('state'))
    faa_states = Counter(r['region'] for r in ld('ufo_cases_faa.json') if r.get('region') and r.get('cc') == 'US')

    def also(k, sample):
        cc, a1, nm = sample['cc'], (sample.get('a1') if sample['cc'] == 'US' else None), names[k]
        if not cc:
            return ''
        fam = fam_at.get((cc, a1), [])
        crit = list(dict.fromkeys(f['creature'] for f in fam))[:8]
        links = []
        if cc == 'US' and place_regions.get(nm):
            links.append((url('/places/' + slugify(nm) + '/'), f'{place_regions[nm]} place{"s" if place_regions[nm] != 1 else ""} to visit in {nm}'))
        if cc == 'US' and hist_states.get(nm, 0) >= 5:  # historic.py makes a state page from 5 reports
            links.append((url('/history/' + slugify(nm) + '/'), f'{hist_states[nm]} old newspaper report{"s" if hist_states[nm] != 1 else ""} from {nm}'))
        if cc == 'US' and faa_states.get(nm):
            links.append((url('/ufo/files/faa/' + slugify(nm) + '/'), f'{faa_states[nm]} FAA pilot report{"s" if faa_states[nm] != 1 else ""} over {nm}'))
        if cc == 'CA':
            links += [(url('/ufo/canada/'), 'Canadian UFO sightings since 1989, by province and town'), (url('/canada/'), 'Creatures and places in Canada')]
        if cc == 'US':
            links.append((url('/us/'), 'Creatures, famous cases and places, state by state'))
        if not crit and not links:
            return ''
        out = f'<h2>Also in {esc(nm)}</h2>'
        if links:
            out += '<ul class="also-links">' + ''.join(f'<li><a href="{u}">{esc(t)}</a></li>' for u, t in links) + '</ul>'
        if crit:
            out += (f'<h3>Creatures with famous cases in {esc(nm)}</h3><div class="crit-grid">'
                    + ''.join(creature_card(BY_SLUG[sl]) for sl in crit) + '</div>')
        return out

    os.makedirs(os.path.join(OUT, 'data', 'bb'), exist_ok=True)
    bb_head = (f'<link rel="stylesheet" href="{url("/static/ufo_canada.css")}">'
               '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
               '<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
               f'<script src="{url("/static/ufo_canada.js")}" defer></script>')

    def bb_extras(k, cases, nm):
        """Map of the files pinned to a town, a by-year chart and the places with the most files."""
        pts = [b for b in cases if b.get('lat') is not None and b['precision'] not in ('region', 'country')]
        out = ''
        if len(pts) >= 3:
            feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(b['lon'], 4), round(b['lat'], 4)]},
                      'properties': {'t': b['place'] or nm, 'w': (f'{b["year"]}-{b["month"]:02d}' if b.get('month') else str(b['year'] or '')),
                                     'e': 'bb', 'a': 0, 'u': f'https://catalog.archives.gov/id/{b["id"]}', 'lk': 'open the file'}} for b in pts]
            with open(os.path.join(OUT, 'data', 'bb', k + '.geojson'), 'w') as f:
                json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'))
            xs, ys = sorted(b['lon'] for b in pts), sorted(b['lat'] for b in pts)
            lo, hi = len(xs) // 50, len(xs) - 1 - len(xs) // 50
            bounds = f'{xs[lo] - .5:.2f},{ys[lo] - .4:.2f},{xs[hi] + .5:.2f},{ys[hi] + .4:.2f}'
            out += (f'<div class="cu-map" data-geojson="{url("/data/bb/" + k + ".geojson")}" data-bounds="{bounds}" data-cluster="{1 if len(pts) > 150 else 0}" '
                    f'data-towns="0" role="region" aria-label="Map of Air Force UFO files in {esc(nm)}"></div>'
                    f'<p class="small muted">{len(pts):,} of {len(cases):,} files are pinned to a town; tap a dot to open the file.</p>')
        ys_ = Counter(b['year'] for b in cases if b.get('year'))
        if sum(ys_.values()) >= 10:
            mx = max(ys_.values())
            out += ('<h2>Files by year</h2><div class="bars" role="img" aria-label="Bar chart of files per year">' +
                    ''.join(f'<div class="bar" style="--h:{round(100 * ys_.get(y, 0) / mx)}%" title="{y}: {ys_.get(y, 0)} files"><span class="bar-n">{ys_.get(y, 0)}</span>'
                            f'<span class="bar-y">&#8217;{str(y)[2:]}</span></div>' for y in range(1947, 1970)) + '</div>')
        towns = Counter(b['place'] for b in pts if b.get('place'))
        if len(towns) >= 5:
            out += ('<h2>Places with the most files</h2><ul class="cols">' +
                    ''.join(f'<li>{esc(t)} <span class="muted">{n}</span></li>' for t, n in towns.most_common(24)) + '</ul>')
        return out + '<h2>Every file</h2>'

    # US city pages: any town with CITY_MIN or more files pinned to it gets its own page under its state.
    CITY_MIN = 8
    CITY_INDEX_MIN = 15  # smaller town pages stay up for visitors but are noindexed (Google's scaled-content rules)
    places_all = json.load(open(os.path.join(ROOT, 'data', 'places.json')))
    places_all = places_all if isinstance(places_all, list) else places_all.get('places', [])
    city_pages = {}
    for k, cases in by_region.items():
        if not k.startswith('us-'):
            continue
        cnt = Counter(b['place'] for b in cases if b.get('precision') == 'place' and b.get('place') and b.get('lat') is not None)
        city_pages[k] = sorted(((pl, slugify(pl), n) for pl, n in cnt.items() if n >= CITY_MIN and slugify(pl)), key=lambda x: -x[2])

    def km(a, b, c, d):
        import math
        p1, p2 = math.radians(a), math.radians(c)
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
        return 6371 * 2 * math.asin(math.sqrt(h))

    CITY_NOTES = {
        ('us-ohio', 'dayton'): 'Dayton has more files than anywhere else for a simple reason: Project Blue Book was run from '
                               'Wright-Patterson Air Force Base, just outside the city. Local sightings were easy to report in person, '
                               'and the base itself logged reports from its own staff.',
        ('us-ohio', 'kettering'): 'Kettering sits next to Dayton and Wright-Patterson Air Force Base, where Project Blue Book had its office.',
        ('us-new-mexico', 'albuquerque'): 'Albuquerque is home to Kirtland Air Force Base and the Sandia nuclear weapons labs, '
                                          'and New Mexico\'s test ranges kept the skies busy with rockets, balloons and jets through the Blue Book years.',
        ('us-district-of-columbia', 'washington'): 'In July 1952 radar operators at Washington National Airport and Andrews Air Force Base tracked unknown '
                                                    'targets over the capital on two weekends running, and jets were scrambled to chase them. '
                                                    'The "Washington flap" made front pages around the world.',
    }

    def file_years(cases):
        """Files grouped by year as small month links (a city page would otherwise repeat the town name hundreds of times)."""
        by = defaultdict(list)
        for b in cases:
            by[b.get('year')].append(b)
        out = ''
        for y in sorted(by, key=lambda v: (v is None, v or 0)):
            fs = sorted(by[y], key=lambda b: b.get('month') or 13)
            links = ''.join(f'<a href="https://catalog.archives.gov/id/{b["id"]}" rel="noopener">{MONTHS[b["month"]][:3] if b.get("month") else "File"}</a>' for b in fs)
            out += f'<div class="fy"><h3>{y or "Date unknown"} <span class="muted">{len(fs)} file{"s" if len(fs) != 1 else ""}</span></h3><p class="fchips">{links}</p></div>'
        return out

    def city_page(k, nm, pl, sl, cases):
        cases = sorted(cases, key=lambda b: (b['year'] is None, b['year'] or 0, b['month'] or 0))
        ys = Counter(b['year'] for b in cases if b.get('year'))
        peak = f' The busiest year was {max(ys, key=ys.get)}, with {max(ys.values())} files.' if ys else ''
        span = f' The files run from {min(ys)} to {max(ys)}.' if len(ys) > 1 else ''
        lat = sum(b['lat'] for b in cases) / len(cases)
        lon = sum(b['lon'] for b in cases) / len(cases)
        note = CITY_NOTES.get((k, sl), '')
        chart = ''
        if sum(ys.values()) >= 8:
            mx = max(ys.values())
            chart = ('<h2>Files by year</h2><div class="bars" role="img" aria-label="Bar chart of files per year">' +
                     ''.join(f'<div class="bar" style="--h:{round(100 * ys.get(y, 0) / mx)}%" title="{y}: {ys.get(y, 0)} files"><span class="bar-n">{ys.get(y, 0)}</span>'
                             f'<span class="bar-y">&#8217;{str(y)[2:]}</span></div>' for y in range(1947, 1970)) + '</div>')
        months = Counter(b['month'] for b in cases if b.get('month'))
        busiest_m = f' Most were filed in {MONTHS[max(months, key=months.get)]}.' if len(months) >= 3 else ''
        near = sorted(((km(lat, lon, x['lat'], x['lon']), x) for x in places_all if x.get('lat') is not None and x.get('lon') is not None), key=lambda t: t[0])
        near = [(d, x) for d, x in near if d <= 150][:6]
        near_html = ('<h2>Strange places to visit nearby</h2><ul class="also-links">' +
                     ''.join(f'<li><a href="{url("/places/" + x["slug"] + "/")}">{esc(x["name"])}</a> <span class="muted">{esc(x.get("city") or "")}, about {round(d)} km away</span></li>' for d, x in near)
                     + '</ul>') if near else ''
        others = [(p2, s2, n2) for p2, s2, n2 in city_pages[k] if s2 != sl][:12]
        others_html = ('<h2>Other towns in ' + esc(nm) + ' with Air Force files</h2><ul class="cols">' +
                       ''.join(f'<li><a href="{url(f"/ufo/blue-book/{k}/{s2}/")}">{esc(p2)}</a> <span class="muted">{n2}</span></li>' for p2, s2, n2 in others) + '</ul>') if others else ''
        body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/ufo/')}">UFOs</a> / <a href="{url('/ufo/blue-book/')}">Project Blue Book</a> / <a href="{url(f'/ufo/blue-book/{k}/')}">{esc(nm)}</a></p>
  <h1>UFO sightings in {esc(pl)}, {esc(nm)}: Air Force files</h1>
  <p class="lede">{len(cases)} US Air Force Project Blue Book case files name {esc(pl)}.{span}{peak}{busiest_m}</p>
  <p><a class="btn" href="{url('/map/?type=ufo')}">See them on the map</a> <a class="btn btn-ghost" href="{url('/report/')}">Seen something here? Report it</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
  {f'<p class="lede-note">{esc(note)}</p>' if note else ''}
  {chart}
  <h2>Every file from {esc(pl)}</h2>
  <div class="file-years">{file_years(cases)}</div>
  <p class="small">Each link opens the original scanned folder at the US National Archives (Record Group 341). Blue Book closed in 1969, so there are no files after that year.</p>
  {near_html}
  {others_html}
  <p><a href="{url(f'/ufo/blue-book/{k}/')}">All {esc(nm)} files</a> · <a href="{url('/ufo/')}">UFO sightings hub</a> · <a href="{url('/reports/')}">Recent reader reports</a></p>
</div></div>'''
        write(f'/ufo/blue-book/{k}/{sl}/', page(f'/ufo/blue-book/{k}/{sl}/', f'UFO sightings in {pl}, {nm}: {len(cases)} Air Force files',
                                                body, f'{len(cases)} Project Blue Book UFO files from {pl}, {nm} (1947 to 1969), with dates and links to the scanned originals.',
                                                noindex=len(cases) < CITY_INDEX_MIN and (k, sl) not in CITY_NOTES))

    for k, cases in by_region.items():
        cases = sorted(cases, key=lambda b: (b['year'] is None, b['year'] or 0, b['month'] or 0))  # undated files last
        nm = names[k] if k != 'unknown' else 'Place unclear or unreadable'
        ys = Counter(b['year'] for b in cases if b.get('year'))
        peak = f' The busiest year was {max(ys, key=ys.get)}, with {max(ys.values())} reports.' if ys else ''
        items = ''.join(case_line(b) for b in cases)
        cps = city_pages.get(k, [])
        city_links = ('<h2>Towns with their own page</h2><ul class="cols">' +
                      ''.join(f'<li><a href="{url(f"/ufo/blue-book/{k}/{s2}/")}">{esc(p2)}</a> <span class="muted">{n2}</span></li>' for p2, s2, n2 in cps) + '</ul>') if cps else ''
        for p2, s2, n2 in cps:
            city_page(k, nm, p2, s2, [b for b in cases if b.get('precision') == 'place' and b.get('place') == p2 and b.get('lat') is not None])
        body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/ufo/')}">UFOs</a> / <a href="{url('/ufo/blue-book/')}">Project Blue Book</a></p>
  <h1>UFO sightings in {esc(nm)}: Air Force files</h1>
  <p class="lede">{len(cases):,} Project Blue Book case {'file' if len(cases) == 1 else 'files'} from {esc(nm)}, 1947 to 1969.{peak}</p>
  <p><a class="btn" href="{url('/map/')}">See them on the map</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
  {city_links}
  {bb_extras(k, cases, nm) if k != 'unknown' else ''}
  <ol class="timeline cases">{items}</ol>
  <p class="small">Links open the original folder at the US National Archives.</p>
  {also(k, cases[0]) if k != 'unknown' else ''}
</div></div>'''
        write(f'/ufo/blue-book/{k}/', page(f'/ufo/blue-book/{k}/', f'UFO sightings in {nm}: {len(cases):,} Air Force Blue Book files',
                                           body, f'{len(cases):,} US Air Force Project Blue Book UFO case files from {nm}, with dates, places and links to the scanned originals.',
                                           head_extra=bb_head))


def build_map_data(bluebook):
    """GeoJSON for the map. Files pinned to a place go in bluebook.geojson. Files that only name a state, province or
    country are never drawn as a pin: they go in bluebook_approx.geojson as one faded "about N files somewhere in X"
    ring per area, at a point inside it, linking to that area's list."""
    feats, approx = [], {}
    for b in bluebook:
        if b.get('lat') is None:
            continue
        if b['precision'] in ('region', 'country'):
            key = (b['cc'], b['a1'] if b['precision'] == 'region' else None)
            a = approx.setdefault(key, {'lat': b['lat'], 'lon': b['lon'], 'n': 0, 'k': region_slug(b),
                                        'name': b['region'] if b['precision'] == 'region' else (b.get('country') or b['region'])})
            a['n'] += 1
            continue
        when = f'{MONTHS[b["month"]][:3]} {b["year"]}' if b.get('month') and b.get('year') else (b.get('year') or '')
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(b['lon'], 3), round(b['lat'], 3)]},
                      'properties': {'id': b['id'], 't': (b['place'] or b['region'] or '')[:60], 'r': b['region'] or '',
                                     'w': str(when), 'y': b.get('year') or 0, 'a': 0}})
    os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
    with open(os.path.join(OUT, 'data', 'bluebook.geojson'), 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'))
    # Small per-month lists for the home page's "This month in the Air Force files" box, so it never pulls the
    # whole 1.3 MB map file just to show eight rows
    os.makedirs(os.path.join(OUT, 'data', 'bluebook-month'), exist_ok=True)
    for i, m in enumerate(MONTHS[1:], 1):
        rows = [[p['id'], p['t'], p['r'], p['w'], p['y']] for p in (x['properties'] for x in feats) if p['w'].startswith(m[:3] + ' ')]
        with open(os.path.join(OUT, 'data', 'bluebook-month', f'{i:02d}.json'), 'w') as f:
            json.dump(rows, f, separators=(',', ':'))
    ap = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(a['lon'], 3), round(a['lat'], 3)]},
           'properties': {'n': a['n'], 't': a['name'], 'u': url(f'/ufo/blue-book/{a["k"]}/')}}
          for a in sorted(approx.values(), key=lambda a: -a['n'])]
    with open(os.path.join(OUT, 'data', 'bluebook_approx.geojson'), 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': ap}, f, separators=(',', ':'))
    return len(feats)


def build_layer_data(creatures, military):
    """Small GeoJSON layers for the map: famous creature cases and military encounters."""
    by_slug = {c['slug']: c for c in creatures}
    fam_path = os.path.join(ROOT, 'data', 'famous_geo.json')
    famous = json.load(open(fam_path)) if os.path.exists(fam_path) else []
    feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [f['lon'], f['lat']]},
              'properties': {'s': f['creature'], 'n': by_slug[f['creature']]['name'], 'c': f['cat'], 'i': by_slug[f['creature']].get('art') or by_slug[f['creature']]['icon'],
                             't': f['name'], 'y': f['year'], 'p': f['place'], 'u': story_url(f['creature'], f['year'])}}
             for f in famous if f['creature'] in by_slug]
    with open(os.path.join(OUT, 'data', 'famous.geojson'), 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': feats}, fh, separators=(',', ':'))
    mil = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [m['lon'], m['lat']]},
            'properties': {'t': m['name'], 'y': m['date'][:4], 'p': m['place'], 'b': m['branch']}}
           for m in military if 'lat' in m]
    with open(os.path.join(OUT, 'data', 'military.geojson'), 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': mil}, fh, separators=(',', ':'))


def build_military(military):
    items = ''
    for m in sorted(military, key=lambda m: m['date']):
        src = ''.join(f'<a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}</a>' for s in m.get('sources', []))
        items += (f'<li class="mil"><span class="yr">{esc(m["date"][:4])}</span><div><h3>{esc(m["name"])}</h3>'
                  f'<p class="muted">{esc(m["place"])} · {esc(m["branch"])}</p><p>{esc(m["summary"])}</p>'
                  f'{f"<p class=src>Sources: {src}</p>" if src else ""}</div></li>')
    body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/ufo/')}">UFOs</a> / Military</p>
  <h1>Military encounters</h1>
  <p class="lede">Pilots, radar operators and soldiers have reported some of the strangest things on record, and the military has kept files on them since the 1940s.</p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <p>The Air Force's own Project Blue Book alone holds {10622:,} case files. <a href="{url('/ufo/blue-book/')}">Browse them by state</a>. Below are the military cases people still talk about.</p>
  <ol class="timeline mil-list">{items}</ol>
</div></div>'''
    write('/military/', page('/military/', 'Military UFO and creature encounters', body,
                             'The most famous military UFO and UAP encounters, from WWII foo fighters to the Navy Tic Tac, with official sources.', article={}))


TILES = [('hominid', 'yeti', 'Bigfoot and hairy giants'), ('canid', 'dogman', 'Dogmen and beasts'),
         ('winged', 'mothman', 'Winged things'), ('aquatic', 'lake', 'Lake monsters'),
         ('entity', 'entity', 'Strange visitors'), ('fae', 'fairy', 'Fairies and little people'), ('ufo', 'saucer', 'UFOs and UAP')]
MAP_HEAD = None


def map_head(lazy=False):
    if lazy:
        # Home page: the map is below the fold, so MapLibre (about 200 KB of JS) and map.js only load when the map comes
        # within ~800px of the screen or someone touches its controls. Keeps the first screen fast.
        return (f'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
                '<script>(function(){var done=0;function go(){if(done)return;done=1;var a=document.createElement("script");'
                'a.src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js";a.onload=function(){var b=document.createElement("script");'
                f'b.src="{url("/static/map.js")}";document.head.appendChild(b);}};document.head.appendChild(a);}}'
                'addEventListener("DOMContentLoaded",function(){var m=document.getElementById("map");if(!m)return;var blk=m.closest("section")||m;'
                '["pointerdown","focusin","keydown"].forEach(function(t){blk.addEventListener(t,go,{once:true});});'
                'if("IntersectionObserver"in window){new IntersectionObserver(function(es,o){if(es.some(function(e){return e.isIntersecting})){o.disconnect();go();}},'
                '{rootMargin:"800px 0px"}).observe(m);}else go();});})();</script>')
    return (f'<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css">'
            f'<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js" defer></script>'
            f'<script src="{url("/static/map.js")}" defer></script>')


def filter_bar(creatures, famous_slugs):
    """Type chips, then category chips and a creature search; picking a category (or typing) shows that group's
    creature chips, wrapped onto lines rather than one long sideways row. map.js wires them up."""
    types = [('all', 'Everything'), ('cryptid', 'Cryptids'), ('ufo', 'UFOs'), ('military', 'Military'), ('places', 'Places to visit'), ('events', 'Events and gatherings')]
    tchips = ''.join(f'<button type="button" class="tchip" data-type="{k}" aria-pressed="{str(k == "all").lower()}">{esc(v)}</button>'
                     for k, v in types)
    crit = [c for c in creatures if c['slug'] in famous_slugs]
    order = {k: i for i, k in enumerate(CATS)}
    crit.sort(key=lambda c: (order[c['cat']], c['name']))
    counts = Counter(c['cat'] for c in crit)
    rep = {cat: ic for cat, ic, _ in TILES}
    catchips = ''.join(f'<button type="button" class="catchip cat-{k}" data-cat="{k}" aria-pressed="false">{icon(rep.get(k, "worm"))}'
                       f'<span>{esc(CATS[k][0])}</span><small>{counts[k]}</small></button>' for k in CATS if counts.get(k))
    cchips = ''.join(f'<button type="button" class="cchip cat-{c["cat"]}" data-creature="{c["slug"]}" data-cat="{c["cat"]}" '
                     f'data-names="{esc((c["name"] + " " + " ".join(c["aliases"])).lower())}" aria-pressed="false" hidden>'
                     f'{mini(c)}<span>{esc(c["name"])}</span></button>' for c in crit)
    return (f'<div class="filters" aria-label="Filter the map"><div class="tchips" role="group" aria-label="Encounter type">{tchips}</div>'
            f'<div class="cfind"><div class="catchips" role="group" aria-label="Creature type">{catchips}</div>'
            f'<input type="search" class="cfind-in" placeholder="Find a creature" aria-label="Find a creature on the map" autocomplete="off"></div>'
            f'<div class="cchips" role="group" aria-label="Creature" hidden>{cchips}</div><p class="cfind-none" hidden>No creature by that name has a pin yet.</p></div>')


def build_search_index(creatures, bluebook, military):
    """Small JSON index for the home search box: creatures (with aliases), UFO file regions, military cases."""
    items = [{'t': c['name'], 'a': ' '.join(c['aliases']), 'k': CATS[c['cat']][0], 'u': url('/creatures/' + c['slug'] + '/'), 'i': c.get('art') or c['icon'], 'c': c['cat']}
             for c in creatures]
    regions = Counter()
    names = {}
    for b in bluebook:
        k = region_slug(b)
        if k != 'unknown':
            regions[k] += 1
            names[k] = b['region']
    items += [{'t': f'UFO files: {names[k]}', 'a': names[k], 'k': f'{n:,} Air Force files', 'u': url('/ufo/blue-book/' + k + '/'), 'i': 'folder', 'c': 'ufo'}
              for k, n in regions.items()]
    ce_path = os.path.join(ROOT, 'data', 'close_encounters.json')
    for x in (json.load(open(ce_path)) if os.path.exists(ce_path) else []):
        items.append({'t': x['name'], 'a': x['place'] + ' ' + ' '.join(x.get('creatures', [])), 'k': f'Close encounter, {x["year"]}',
                      'u': url('/encounters/' + x['slug'] + '/'), 'i': 'art/' + (x['creatures'] or ['grey-aliens'])[0], 'c': 'entity'})
    items += [{'t': m['name'], 'a': m['place'], 'k': 'Military encounter, ' + m['date'][:4], 'u': url('/military/'), 'i': 'military', 'c': 'ufo'}
              for m in military]
    with open(os.path.join(OUT, 'data', 'search.json'), 'w') as f:
        json.dump(items, f, separators=(',', ':'))


def build_home(creatures, n_points, bluebook, military):
    fam_path = os.path.join(ROOT, 'data', 'famous_geo.json')
    famous_slugs = {f['creature'] for f in json.load(open(fam_path))} if os.path.exists(fam_path) else set()
    cu_path = os.path.join(ROOT, 'data', 'ufo_cases_canada.json')
    n_canada = len(json.load(open(cu_path))) if os.path.exists(cu_path) else 0
    # "This month in old newspapers": built server-side (the site rebuilds daily), five reports from this month, spread over the years.
    hp = os.path.join(ROOT, 'data', 'historic.json')
    hist = json.load(open(hp, encoding='utf-8')) if os.path.exists(hp) else []
    mon = datetime.date.today().month
    this_m = sorted((x for x in hist if x['date'][5:7] == f'{mon:02d}'), key=lambda x: x['date'])
    if len(this_m) > 5:
        this_m = [this_m[round(i * (len(this_m) - 1) / 4)] for i in range(5)]
    HPAGE = {'airship': 'airships-1896-1897', 'airship-1909': 'phantom-airships-1909', 'wild-man': 'wild-men', 'sea-serpent': 'sea-serpents',
             'jersey-devil': 'jersey-devil-1909', 'giant-bird': 'giant-birds', 'phantom-light': 'phantom-lights', 'creature': 'strange-creatures'}
    news_html = ''.join(f'<li><span class="yr">{x["date"][:4]}</span><span><a href="{url("/history/" + HPAGE.get(x["k"], "") + "/")}#h-{esc(x["id"])}">'
                        f'<strong>{esc(x["title"])}</strong></a><br><span class="muted">{esc(x["place"])}</span></span></li>' for x in this_m)
    n_myst = len(json.load(open(os.path.join(ROOT, 'data', 'mysteries.json')))) if os.path.exists(os.path.join(ROOT, 'data', 'mysteries.json')) else 0
    n_places = len(json.load(open(os.path.join(ROOT, 'data', 'places.json')))) if os.path.exists(os.path.join(ROOT, 'data', 'places.json')) else 0
    explore = [('/history/', 'newspaper', f'{len(hist)} reports in old newspapers'), ('/mysteries/', 'q-unsure', f'{n_myst} unsolved mysteries'),
               ('/places/', 'museum', f'{n_places} places to visit'), ('/tools/was-it-a-planet/', 'e-planet', 'Was it a planet?'),
               ('/tools/what-did-i-see/', 'q-sky', 'What did I see? quiz'), ('/tools/size-comparison/', 'footprint', 'How big is it?'),
               ('/guides/', 'expedition', 'Field guides'), ('/podcasts/', 'recorder', 'Podcasts')]
    explore_html = ''.join(f'<a class="tile" href="{url(u)}">{icon(i)}<span>{esc(t)}</span></a>' for u, i, t in explore
                           if os.path.exists(os.path.join(STATIC, 'icons', i + '.svg')))
    featured = [c for c in creatures if c['slug'] in ('bigfoot', 'dogman', 'mothman', 'loch-ness-monster', 'chupacabra',
                                                       'ufo-tic-tac', 'jersey-devil', 'flatwoods-monster', 'fairies')]
    cards = ''.join(creature_card(c) for c in featured)
    tiles = ''.join(f'<a class="tile cat-{cat}" href="{url("/map/?cat=" + cat)}">{tile_icon(ic)}<span>{esc(label)}</span></a>'
                    for cat, ic, label in TILES)
    tiles += f'<a class="tile tile-mil" href="{url("/map/?type=military")}">{tile_icon("military")}<span>Military encounters</span></a>'
    build_search_index(creatures, bluebook, military)
    body = f'''
<section class="home-hero">
  <div class="wrap">
    <h1>Every strange thing, on one map</h1>
    <p class="lede">Bigfoot, Dogman, lake monsters, UFOs and what the military saw. {len(creatures)} creatures, {len(bluebook):,} Air Force files, {n_canada:,} Canadian sightings, and reports from readers like you.</p>
    <div class="search" data-index="{url('/data/search.json')}">
      <label class="visually-hidden" for="home-q">Search</label>
      <input id="home-q" type="search" placeholder="Search: Sasquatch, Ohio, Roswell..." autocomplete="off">
      <ul class="search-results" hidden></ul>
    </div>
    <p class="home-where">Or browse where you live: <a href="{url('/us/')}">US states</a> · <a href="{url('/canada/')}">Canada</a> · <a href="{url('/on-this-day/')}" data-otd-today>What happened on this day</a></p>
    <nav class="tiles" aria-label="Browse by type">{tiles}</nav>
  </div>
</section>
{f'''<section class="new-reports" data-api="{EA_API}" data-base="{url('')}" data-index="{url('/data/search.json')}" aria-labelledby="nr-h" hidden>
  <div class="wrap">
    <div class="nr-head"><div><p class="nr-pill"><span class="nr-dot" aria-hidden="true"></span><span data-nr-count>New from readers</span></p>
      <h2 id="nr-h">Latest reader reports</h2></div>
      <p class="nr-actions"><a class="btn btn-sm" href="{url('/reports/')}">See all reports</a> <a class="btn btn-sm btn-ghost" href="{url('/report/')}">Report yours</a></p></div>
    <div class="nr-list"></div>
  </div>
</section>''' if EA_API else ''}
<div class="band band-mist nl-band home-nl"><div class="wrap">{signup_box('home')}</div></div>
<section class="map-block" aria-label="Encounter map">
  <div class="wrap">
    <div class="map-block-head">
      <h2>The encounter map</h2>
      <div class="map-block-actions"><button type="button" class="btn btn-sm" data-locate>Use my location</button>
      <a class="btn btn-sm btn-ghost" href="{url('/map/')}">Full screen</a></div>
    </div>
    {filter_bar(creatures, famous_slugs)}
  </div>
  <div class="map-frame"><div id="map" class="map" data-base="{BASE}"{MAP_API}></div></div>
</section>
<div class="band band-mist"><div class="wrap">
  <div class="near" hidden>
    <h2>Near you</h2>
    <ol class="timeline near-list"></ol>
  </div>
  <div class="this-month">
    <h2>This month in the Air Force files</h2>
    <p class="lede-dark">UFO reports the Air Force logged in <span class="month-name">this month</span>, 1947 to 1969.</p>
    <ol class="timeline cases month-list"><li><span class="yr"></span><span>Loading...</span></li></ol>
  </div>
  <h2>Meet the locals</h2>
  <p class="lede-dark">Every creature has its other names, what witnesses report and the cases that made it famous.</p>
  <div class="crit-grid home-crits">{cards}</div>
  <p><a href="{url('/creatures/')}">See all {len(creatures)} creatures</a></p>
  {f"""<h2>This month in old newspapers</h2>
  <p class="lede-dark">Sea serpents, wild men and phantom airships reported in {MONTHS[mon]}, from American papers printed before 1927.</p>
  <ol class="timeline cases">{news_html}</ol>
  <p><a href="{url('/history/')}">All {len(hist)} old newspaper reports</a></p>""" if news_html else ''}
  <h2>Keep exploring</h2>
  <nav class="tiles home-explore" aria-label="More to explore">{explore_html}</nav>
</div></div>
<div class="band band-dark"><div class="wrap split split-3">
  <div>
    {icon('folder', 'ico ico-lg')}
    <h2>The Air Force kept files</h2>
    <p>Project Blue Book collected {len(bluebook):,} UFO reports between 1947 and 1969. Find the ones from your state, read the original scans, and see where they cluster.</p>
    <p><a class="btn" href="{url('/ufo/blue-book/')}">Open the Air Force files</a></p>
  </div>
  <div>
    {icon('ufo-globe', 'ico ico-lg')}
    <h2>Canada's UFO sightings</h2>
    <p>{n_canada:,} reports from every province and territory since 1989, from the Canadian UFO Survey. See your town's sightings and the ones nobody could explain.</p>
    <p><a class="btn" href="{url('/ufo/canada/')}">Open the Canada map</a></p>
    <p><a href="{url('/canada/')}">Sasquatch, lake monsters and more in Canada</a></p>
  </div>
  <div>
    {icon('military', 'ico ico-lg')}
    <h2>Military encounters</h2>
    <p>Foo fighters over Germany, radar returns over the White House, a Tic Tac off San Diego. The cases pilots and soldiers reported.</p>
    <p><a class="btn" href="{url('/military/')}">Read the cases</a></p>
  </div>
</div></div>
<script src="{url('/static/home.js')}" defer></script>'''
    write('/', page('/', 'Encounter Atlas: Bigfoot, UFO and cryptid sightings mapped', body,
                    'A map of Bigfoot, Dogman, UFO and cryptid encounters, a searchable creature index, and the US Air Force Project Blue Book files.',
                    body_class='home', head_extra=map_head(lazy=True)))
    write('/search/', page('/search/', 'Search', f'''
<section class="band band-dark search-page"><div class="wrap">
  <h1>Search Encounter Atlas</h1>
  <div class="search search-big" data-index="{url('/data/search.json')}" data-limit="40">
    <label class="visually-hidden" for="home-q">Search</label>
    <input id="home-q" type="search" placeholder="Creature, town, state, province, case..." autocomplete="off" autofocus>
    <ul class="search-results" hidden></ul>
  </div>
  <p class="search-tips">Try a creature (Mothman, Ogopogo), a place (Ohio, Edmonton, Lake Champlain) or a case (Roswell, Falcon Lake).</p>
  <nav class="tiles" aria-label="Browse by type">{tiles}</nav>
</div></section>
<script src="{url('/static/home.js')}" defer></script>''', 'Search creatures, places, UFO files and encounters on Encounter Atlas.'))
    write('/map/', page('/map/', 'Encounter map', f'''
<section class="map-full" aria-label="Encounter map">
  <div class="map-full-bar">
    <div class="mf-head"><h1>Encounter map</h1><p>Air Force UFO files, famous creature cases, military encounters and places you can visit. Every pin is a real file or case, so tap one and read it.</p></div>
    <button type="button" class="mf-toggle" aria-expanded="false" aria-controls="mf-panel"><svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M2 4h12M4.5 8h7M7 12h2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><span>Filters</span><span class="mf-now">Everything</span></button>
    <button type="button" class="btn btn-sm" data-locate>Near me</button>
  </div>
  <div class="map-frame full">
    <div id="mf-panel" class="mf-panel" hidden>{filter_bar(creatures, famous_slugs)}<button type="button" class="btn btn-sm mf-done">Show the map</button></div>
    <div id="map" class="map" data-base="{BASE}"{MAP_API}></div>
    <a class="map-exit" href="{url('/')}" hidden><svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>Exit full map</a></div>
</section>''', 'Map of Bigfoot, Dogman, UFO and cryptid encounters, military cases and every US Air Force Project Blue Book file.',
                        body_class='mapper', head_extra=map_head()))


def build_static_pages():
    write('/report/', page('/report/', 'Report an encounter', f'''
<section class="band band-dark"><div class="wrap">
  <h1>Report an encounter</h1>
  <p class="lede">Saw something you can't explain? The report form is being built now and opens soon, with links to your photos and videos and a pin on the map.</p>
</div></section>
<div class="band band-mist"><div class="wrap prose">
  <p><a class="btn" href="{url('/printables/after-an-encounter/')}">Print the encounter record sheet</a></p>
  <h2>What to write down now, while it's fresh</h2>
  <ul class="signs">
    <li>Date, time and how long it lasted</li>
    <li>Exactly where you were, and where it was from you</li>
    <li>Size, shape, colour and how it moved</li>
    <li>Sounds and smells</li>
    <li>Weather and light: moon, clouds, headlights</li>
    <li>Who else saw it</li>
  </ul>
  <p>Take photos of tracks with something for scale, like a boot or a phone. Don't post your exact location publicly if it's private land.</p>
  <h2>What to bring next time</h2>
  <p>A trail camera, a red-light headlamp and an audio recorder catch most of what people miss. See <a href="{url('/gear/')}">field gear for investigators</a>.</p>
</div></div>''', 'Report a Bigfoot, Dogman, UFO or other strange encounter.'))
    write('/privacy/', page('/privacy/', 'Privacy', f'''
<section class="band band-dark"><div class="wrap"><h1>Privacy</h1>
<p class="lede">What we keep when you use Encounter Atlas or send us a report, who can see it, and how to get it removed. Short version: your exact location, your email address and your IP address are never made public.</p></div></section>
<div class="band band-mist"><div class="wrap prose">
<p class="small">Last updated: October 24, 2026.</p>

<h2>Just reading the site</h2>
<ul>
<li><strong>No ads and no account needed.</strong> You can read every page and use the map and tools without signing up.</li>
<li id="analytics"><strong>Analytics:</strong> we use Google Analytics to count visits and see which pages and tools people use, so we know what to improve. It sets cookies and collects things like your approximate location, your device and browser, the pages you view and the buttons, filters and map choices you use. It never gets your name, your email address, or what you type into a report or message. Search words you type into the site's search boxes are counted so we can see what people look for. You can opt out with <a href="https://tools.google.com/dlpage/gaoptout">Google's opt-out add-on</a> or by blocking cookies, and the site works the same either way. See <a href="https://policies.google.com/technologies/partner-sites">how Google uses this data</a>. We also use Clicky to see how visitors move through the site. Like Google Analytics it sets cookies and sees the same kind of information, never your name, email or what you type into a form (<a href="https://clicky.com/terms/privacy">Clicky's privacy policy</a>). Blocking cookies opts you out of both.</li>
<li><strong>Things your browser remembers, not us:</strong> your sort choice on the creature index, your last place on Near me, a draft of a report you haven't sent yet, your saved road trips, the collector cards you've checked in, and your field journal notes (all stored only on your device, and never sent to us unless you turn a journal note into a report). Clearing your browser data removes them.</li>
<li><strong>Other services the pages load:</strong> map tiles from OpenFreeMap, fonts from Google Fonts and code libraries from cdnjs and jsDelivr. The <a href="{url('/tools/was-it-a-planet/')}">Was it a planet?</a> tool also fetches the Space Station's orbit from Celestrak; the place you enter stays in your browser. The <a href="{url('/road-trip/')}">road trip planner</a> sends the start and end towns you type to Open-Meteo's place search and the route points to the OpenStreetMap routing service (routing.openstreetmap.de). <a href="{url('/tools/skywatch/')}">Tonight's skywatch</a> sends a point rounded to about 1 km to Open-Meteo for the cloud forecast. The "Conditions that night" panel on reader reports asks Open-Meteo for the weather at the report's public map point. Like any website, these see your IP address when they send the file. Witness videos only load from YouTube (in its privacy-enhanced mode) when you press play.</li>
</ul>

<h2>Sending a report</h2>
<p>When you report an encounter we keep what you type and choose: the date and time, what you saw, the story, sounds, smells, how many people were there, links to any photos and videos, and where it happened.</p>
<ul>
<li><strong>Your exact location is private.</strong> Only our moderators see the exact spot. The public map shows the report on a grid of about 5 km (3 miles), never the exact point, so nobody can find your home or a private spot from it.</li>
<li><strong>We don't take photo or video uploads.</strong> You can link to pictures and videos you've posted elsewhere (Imgur, Flickr, YouTube and so on). Those files stay on that service, under its rules. Some services keep the GPS location inside a photo, so check before you share a link.</li>
<li><strong>Your name is optional.</strong> Reports are anonymous unless you choose to show a display name.</li>
<li><strong>Every report is checked by a person</strong> before it appears on the site, and we can turn down reports that break our rules.</li>
<li><strong>Spam protection:</strong> forms use Cloudflare Turnstile to check you're not a bot, and we store a scrambled one-way code made from your IP address (not the address itself) to spot floods of fake reports or votes.</li>
</ul>

<h2 id="location">Your location, only when you ask</h2>
<ul>
<li><strong>Near me and the app</strong> only ask for your location when you tap "Use my location". The phone rounds it to about 1 km before it's used, and we don't save it: it's only used to fetch the reports around that point. Picking a town instead uses a list built into the site, with no outside service.</li>
<li><strong>On the report form</strong>, "Use my location" also rounds the point to about 1 km on your phone before it's sent. It's stored with the report like a spot you tap on the map (see above: only moderators see it, the public sees about 5 km).</li>
<li><strong>We never track your location in the background.</strong> The app has no background location at all.</li>
<li>Your last searched place and filters are remembered in your browser so the app reopens where you left off. "Forget this place" or clearing your browser data removes them.</li>
<li>A report you write with no signal is kept in your browser until you're back online, then sent the normal way.</li>
</ul>

<h2 id="alerts">Sighting alerts (notifications)</h2>
<ul>
<li>If you turn on alerts, we store your browser's push address and keys (from Google, Mozilla, Apple or Microsoft, depending on your device), the place you saved rounded to about 1 km, your radius, which kinds of report you want and whether you use km or miles. We also note when we last sent you an alert, to keep it to three a day.</li>
<li>That place is the only location we keep for alerts. It doesn't change unless you move your alerts.</li>
<li>Alerts go through your browser maker's push service, which delivers the message but can't read it (it's encrypted).</li>
<li>Turn them off with "Turn off alerts" on the <a href="{url('/near-me/')}">Near me</a> page, or by blocking notifications for this site. Either way we stop sending, and dead push addresses are switched off automatically.</li>
<li>Push addresses are never sold or shared, and no account or email is needed.</li>
</ul>

<h2>Accounts and voting</h2>
<ul>
<li>Signing in uses a one-time link sent to your email. We keep your email address and, if you choose one, a display name. There's no password for us to lose.</li>
<li>Your email is never shown on the site, never sold and never added to a mailing list. We only use it to sign you in and, if we need to, to contact you about one of your reports.</li>
<li>When you vote "real or hoax", we keep the vote, the account that cast it and the scrambled IP code, so each account counts once and vote-stuffing can be caught. Results are shown as totals, never as who voted what.</li>
</ul>

<h2>Who can see what</h2>
<ul>
<li><strong>Everyone:</strong> approved reports (story, date, approximate area, photo and video links, display name if you chose one) and vote totals.</li>
<li><strong>Our moderators only:</strong> the exact location, your email address and the scrambled IP code, to check reports and stop abuse.</li>
<li><strong>Service providers that run the site for us:</strong> Cloudflare (hosting for reports, alerts and the database), Resend (sends the sign-in emails and passes contact-form messages to our inbox), GitHub (hosts the public pages), and Google Analytics and Clicky (visitor statistics; see above). They process data only to provide those services.</li>
<li>We don't sell or rent anyone's information, and we don't share it with advertisers or other sighting organisations.</li>
</ul>

<h2 id="newsletter">Weekly email</h2>
<p>If you sign up for the <a href="{url('/newsletter/')}">weekly email</a>, we store your email address with <a href="https://resend.com/legal/privacy-policy">Resend</a>, the service that sends it, and use it only for that email. We ask you to confirm by clicking a link first. Every email has a one-click unsubscribe link, and we never sell or share the list. Signing up is separate from a reporting account: an account alone never puts you on the list.</p>

<h2>Removing your report or account</h2>
<ul>
<li>If you sent a report while signed in, you can edit or withdraw it yourself from the report page. Withdrawing removes it from the site straight away.</li>
<li>To remove a report sent without an account, delete your account, or ask what we hold about you, email <a href="mailto:hello@encounteratlas.com">hello@encounteratlas.com</a>. We reply within 30 days.</li>
<li>Sign-ins expire after 90 days on a device, and you can sign out at any time.</li>
</ul>

<h2 id="affiliate">Affiliate links</h2>
<p>Some links on creature pages (books, documentaries, gear and shirts) go to Amazon.com. As an Amazon Associate we earn from qualifying purchases. It costs you nothing extra, and it never decides what we write: books are listed because they're about the creature, not because of a deal. These links are marked as sponsored for search engines.</p>
<p>When you click one, Amazon may set its own cookies to credit the sale to us. That happens on Amazon's site, under <a href="https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ" rel="noopener">Amazon's privacy notice</a>. We don't get your name, address or what else you buy, only order totals.</p>
<h2>Children</h2>
<p>Encounter Atlas is meant for adults and teens. If you're under 13, please ask a parent or guardian to send a report for you.</p>

<h2>Changes</h2>
<p>If we change how we handle your information, we'll update this page and the date at the top.</p>
<p>See also: <a href="{url('/about/')}">About and sources</a>.</p>
</div></div>''', 'What Encounter Atlas keeps when you read the site or send a report, who can see it, and how to have it removed.'))
    write('/404.html', page('/404.html', 'Page not found', f'''
<section class="band band-dark"><div class="wrap"><h1>Nothing out here</h1>
<p class="lede">That page doesn't exist, or it wandered off into the woods. Try a search, or pick a trail below.</p>
<form class="nf-search" action="{url('/search/')}" method="get" role="search">
  <label for="nf-q" class="visually-hidden">Search the site</label>
  <input id="nf-q" name="q" type="search" placeholder="Bigfoot, Ogopogo, Roswell..." autocomplete="off">
  <button class="btn" type="submit">Search</button>
</form>
<p class="md-chips"><a class="md-chip" href="{url('/')}">Home</a><a class="md-chip" href="{url('/map/')}">Map</a><a class="md-chip" href="{url('/creatures/')}">Creatures</a>
<a class="md-chip" href="{url('/ufo/')}">UFOs</a><a class="md-chip" href="{url('/places/')}">Places to visit</a><a class="md-chip" href="{url('/report/')}">Report an encounter</a></p>
<script>(function () {{
  // A reader report approved since the last build has no static page yet (site/sections/reports.py):
  // show it from the API at /reports/?id= instead, keeping ?source= and #vote. static=0 stops a redirect loop.
  var m = location.pathname.match(/[/]reports[/]([a-z0-9]{{10}})[/]?$/);
  if (m) {{
    var q = new URLSearchParams(location.search); q.set('id', m[1]); q.set('static', '0');
    location.replace('{url('/reports/')}?' + q.toString() + location.hash); return;
  }}
  // guess search words from the missing address: /creatures/ogopogoo/ -> "ogopogoo"
  var w = location.pathname.split('/').filter(Boolean).pop() || '';
  w = decodeURIComponent(w).replace(/\.html?$/, '').replace(/[-_]+/g, ' ').trim();
  if (w && w.length < 60) document.getElementById('nf-q').value = w;
}})();</script></div></section>''', canonical=False))


def merge_stories(creatures):
    """data/creature_stories.json adds researched stories (old newspapers, books, news reports) to each creature's
    case timeline: {slug: [{name, year, place, summary, source_title, source_url}]}. Written by hand, in our own words."""
    p = os.path.join(ROOT, 'data', 'creature_stories.json')
    if not os.path.exists(p):
        return
    by = {c['slug']: c for c in creatures}
    for slug, stories in json.load(open(p, encoding='utf-8')).items():
        c = by.get(slug)
        if not c:
            print('creature_stories: unknown slug', slug, file=sys.stderr)
            continue
        have = {f['name'] for f in c['famous']}
        for st in stories:
            if st.get('kind') == 'newspaper':  # shown in their own "In the old newspapers" list, not the case timeline
                c.setdefault('papers', []).append(st)
            elif st['name'] not in have:
                c['famous'].append({'name': st['name'], 'year': st['year'], 'place': st['place']})
                STORY_DETAILS[slug + '|' + st['name']] = {k: st[k] for k in ('summary', 'source_title', 'source_url') if st.get(k)}


STORY_DETAILS = {}


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(STATIC, os.path.join(OUT, 'static'))
    creatures = json.load(open(os.path.join(ROOT, 'data', 'creatures.json')))
    by_slug = {c['slug']: c for c in creatures}
    merge_stories(creatures)
    for c in creatures:  # park-poster silhouettes (site/static/art/<slug>.svg) replace the old icons where we have them
        if os.path.exists(os.path.join(STATIC, 'art', c['slug'] + '.svg')):
            c['art'] = 'art/' + c['slug']
    bad = [(c['slug'], r) for c in creatures for r in c['related'] if r not in by_slug]
    if bad:
        print('unknown related slugs:', bad, file=sys.stderr)
    bluebook = json.load(open(os.path.join(ROOT, 'data', 'bluebook.json')))
    mil_path = os.path.join(ROOT, 'data', 'military.json')
    military = json.load(open(mil_path)) if os.path.exists(mil_path) else []
    n_points = build_map_data(bluebook)
    build_layer_data(creatures, military)
    build_home(creatures, n_points, bluebook, military)
    build_creatures(creatures, by_slug)
    build_ufo(bluebook, by_slug)
    build_military(military)
    build_static_pages()
    # Each site/sections/*.py module owns one part of the site (places, podcasts, ...) and exposes
    # build(ctx). ctx gives it the shared helpers and loaded data, so sections never edit this file.
    import importlib.util, types
    ctx = types.SimpleNamespace(ROOT=ROOT, OUT=OUT, STATIC=STATIC, SITE_URL=SITE_URL, BASE=BASE, page=page, write=write,
                                url=url, esc=esc, icon=icon, crit_icon=crit_icon, slugify=slugify, badge=badge, creature_card=creature_card,
                                social_row=social_row, signup_box=signup_box, NEWSLETTER_API=NEWSLETTER_API, creatures=creatures, by_slug=by_slug, bluebook=bluebook, military=military, CATS=CATS, MONTHS=MONTHS)
    sec_dir = os.path.join(ROOT, 'site', 'sections')
    for fn in sorted(os.listdir(sec_dir)) if os.path.isdir(sec_dir) else []:
        if fn.endswith('.py') and not fn.startswith('_'):
            spec = importlib.util.spec_from_file_location('sec_' + fn[:-3], os.path.join(sec_dir, fn))
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                mod.build(ctx)
            except Exception as e:  # SKIP_BROKEN_SECTIONS=1 for local previews while a section is half-built
                if not os.environ.get('SKIP_BROKEN_SECTIONS'):
                    raise
                print(f'warning: section {fn} skipped: {e!r}', file=sys.stderr)
    author_page()
    write_feeds()
    with open(os.path.join(OUT, 'manifest.webmanifest'), 'w') as f:
        # The app (installed PWA, later the Play Store TWA) opens on /near-me/. id stays fixed so installs survive start_url changes.
        json.dump({'id': BASE + '/near-me/', 'name': 'Encounter Atlas', 'short_name': 'Encounters', 'start_url': BASE + '/near-me/?source=pwa',
                   'scope': BASE + '/', 'display': 'standalone', 'orientation': 'any',
                   'background_color': '#13261F', 'theme_color': '#13261F', 'lang': 'en', 'categories': ['entertainment', 'lifestyle', 'travel'],
                   'description': 'See and report Bigfoot, Dogman, UFO and cryptid sightings near you, anywhere in the world.',
                   'icons': [{'src': BASE + '/static/app-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
                             {'src': BASE + '/static/app-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
                             {'src': BASE + '/static/app-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
                             {'src': BASE + '/static/favicon.svg', 'sizes': 'any', 'type': 'image/svg+xml'}],
                   'shortcuts': [{'name': 'Report an encounter', 'short_name': 'Report', 'url': BASE + '/report/?source=pwa',
                                  'icons': [{'src': BASE + '/static/app-192.png', 'sizes': '192x192', 'type': 'image/png'}]},
                                 {'name': 'Road trip planner', 'short_name': 'Road trip', 'url': BASE + '/road-trip/?source=pwa',
                                  'icons': [{'src': BASE + '/static/app-192.png', 'sizes': '192x192', 'type': 'image/png'}]},
                                 {'name': "Tonight's skywatch", 'short_name': 'Skywatch', 'url': BASE + '/tools/skywatch/?source=pwa',
                                  'icons': [{'src': BASE + '/static/app-192.png', 'sizes': '192x192', 'type': 'image/png'}]},
                                 {'name': 'Full encounter map', 'short_name': 'Map', 'url': BASE + '/map/?source=pwa',
                                  'icons': [{'src': BASE + '/static/app-192.png', 'sizes': '192x192', 'type': 'image/png'}]}]}, f)
    shutil.copy(os.path.join(ROOT, 'site', 'sw.js'), os.path.join(OUT, 'sw.js'))
    if BASE == '':
        open(os.path.join(OUT, 'CNAME'), 'w').write(SITE_URL.split('//')[1] + '\n')
    pages = []
    for d, _, files in os.walk(OUT):
        for fn in files:
            if fn == 'index.html' and 'content="noindex' not in open(os.path.join(d, fn), encoding='utf-8').read(3000):
                pages.append('/' + os.path.relpath(d, OUT).replace('.', '').strip('/') + '/')
    pages = sorted(p.replace('//', '/') for p in pages)
    with open(os.path.join(OUT, 'sitemap.xml'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        lastmod = {a['path']: a['date'] for a in ARTICLES}
        f.writelines(f'<url><loc>{SITE_URL}{p}</loc>' + (f'<lastmod>{lastmod[p]}</lastmod>' if p in lastmod else '') + '</url>\n' for p in pages)
        f.write('</urlset>\n')
    # IndexNow (Bing, Yandex, Seznam, Naver): the key file proves we own the site when we ping changed URLs.
    open(os.path.join(OUT, INDEXNOW_KEY + '.txt'), 'w').write(INDEXNOW_KEY)
    # Android app (Play Store Trusted Web Activity, package com.encounteratlas.app): proves the app and the site belong
    # together so it opens full screen with no browser bar. First fingerprint = our upload key (sideloaded test APKs);
    # add Play Console's app-signing key fingerprint once the app is uploaded there.
    os.makedirs(os.path.join(OUT, '.well-known'), exist_ok=True)
    with open(os.path.join(OUT, '.well-known', 'assetlinks.json'), 'w') as f:
        json.dump([{'relation': ['delegate_permission/common.handle_all_urls'],
                    'target': {'namespace': 'android_app', 'package_name': 'com.encounteratlas.app',
                               'sha256_cert_fingerprints': APP_FINGERPRINTS}}], f)
    # Crawlers that only collect pages for AI training and never send visitors (Mike, 2026-10-25). Search and
    # answer bots that cite and link back (ChatGPT-User, OAI-SearchBot, PerplexityBot, Googlebot) stay allowed.
    training_bots = ['GPTBot', 'ClaudeBot', 'Google-Extended', 'Applebot-Extended', 'CCBot', 'meta-externalagent',
                     'Bytespider', 'cohere-training-data-crawler']
    with open(os.path.join(OUT, 'robots.txt'), 'w') as f:
        f.write(''.join(f'User-agent: {b}\n' for b in training_bots) + 'Disallow: /\n\n'
                f'User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n')
    print(f'built {len(pages)} pages, {n_points:,} map points', file=sys.stderr)


def write_feeds():
    """/feed.xml (everything, plus the What's new notes) and one RSS 2.0 feed per FEED_SECTIONS prefix, newest first."""
    from email.utils import format_datetime
    def rfc(d):
        return format_datetime(datetime.datetime.fromisoformat(d[:10]).replace(hour=12, tzinfo=datetime.timezone.utc))
    def item(x):
        img = SITE_URL + x['image'] if x['image'].startswith('/') else x['image']
        typ = 'image/png' if img.endswith('.png') else 'image/jpeg'
        link = SITE_URL + x['path']
        return (f'<item><title>{esc(x["title"])}</title><link>{esc(link)}</link><guid isPermaLink="{"false" if x.get("guid") else "true"}">'
                f'{esc(x.get("guid") or link)}</guid><pubDate>{rfc(x["date"])}</pubDate><description>{esc(x["desc"])}</description>'
                f'<enclosure url="{esc(img)}" length="0" type="{typ}"/><media:content url="{esc(img)}" medium="image" type="{typ}"/></item>\n')
    def feed(path, title, desc, items):
        items = sorted(items, key=lambda x: (x['date'], x['path']), reverse=True)[:50]
        os.makedirs(os.path.dirname(os.path.join(OUT, path.strip('/'))), exist_ok=True)
        with open(os.path.join(OUT, path.strip('/')), 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
                    'xmlns:media="http://search.yahoo.com/mrss/">\n<channel>\n'
                    f'<title>{esc(title)}</title><link>{SITE_URL}{path.rsplit("feed.xml", 1)[0]}</link><description>{esc(desc)}</description>'
                    f'<language>en</language><atom:link href="{SITE_URL}{path}" rel="self" type="application/rss+xml"/>'
                    f'<image><url>{SITE_URL}/static/app-192.png</url><title>{esc(title)}</title><link>{SITE_URL}/</link></image>\n'
                    + (f'<lastBuildDate>{rfc(items[0]["date"])}</lastBuildDate>\n' if items else '')
                    + ''.join(item(x) for x in items) + '</channel>\n</rss>\n')
    seen = {}
    for x in FEED:
        seen[x['path']] = x  # last build of a path wins
    pages = list(seen.values())
    news = []
    for n in json.load(open(os.path.join(ROOT, 'data', 'whats_new.json'))):
        hit = seen.get(n['path'], {})
        news.append({'path': n['path'], 'title': 'New on Encounter Atlas: ' + n['title'], 'desc': n['note'], 'date': n['date'],
                     'image': hit.get('image', '/static/og.png'), 'guid': f'{SITE_URL}/whats-new/{n["date"]}/{slugify(n["title"])}'})
    feed('/feed.xml', 'Encounter Atlas', 'New sightings, creatures, witness stories and official UFO files from Encounter Atlas.', pages + news)
    for prefix, name in FEED_SECTIONS:
        feed(prefix + 'feed.xml', f'Encounter Atlas: {name}', f'The newest {name.lower()} on Encounter Atlas.',
             [x for x in pages if x['path'].startswith(prefix) and x['path'] != prefix])


APP_FINGERPRINTS = [
    'E2:3A:78:F1:C2:82:AB:8D:C8:3E:3D:30:90:50:F2:D8:B4:53:E9:8F:93:36:54:5A:74:9A:3E:F5:47:76:19:BC',  # upload key
]


if __name__ == '__main__':
    main()

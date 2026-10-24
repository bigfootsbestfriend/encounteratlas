"""On the record: UFO hearings held by lawmakers and the people who testified, from data/on_the_record.json.

/ufo/hearings/ is a timeline hub with one page per hearing; /ufo/people/ groups everyone who testified, with one page each.
Summaries are our own words. Quotes are short, word for word from US congressional transcripts and written testimony
(US federal records, public domain), checked against the files in data/raw/hearings/. Every page links the official record.
Hearings with "page": false get a hub card that points to their /ufo/releases/ page instead. Short profiles are noindexed.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sources

MON = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
SIDES = {'witness': ('Witnesses', 'Pilots, sailors and security staff who saw something themselves', '#E07A4F'),
         'whistleblower': ('Whistleblowers', 'Former insiders who say information is being held back', '#A99CF0'),
         'official': ('Officials', 'People who spoke for the government or ran its UFO offices', '#6FA8DC'),
         'scientist': ('Scientists', 'Researchers asked to give Congress their expert view', '#7FC8A9'),
         'journalist': ('Journalists', 'Reporters who have followed the story for years', '#F2B33D')}
ONE = {'witness': 'Witness', 'whistleblower': 'Whistleblower', 'official': 'Official', 'scientist': 'Scientist', 'journalist': 'Journalist'}
SRC = {'transcript': 'Hearing transcript', 'written': 'Written testimony'}
FLAG = {'us': 'United States', 'mx': 'Mexico'}


def build(ctx):
    path = os.path.join(ctx.ROOT, 'data', 'on_the_record.json')
    if not os.path.exists(path):
        return
    d = json.load(open(path, encoding='utf-8'))
    R(ctx, d).run()


def dateline(d):
    y, m, dd = d.split('-')
    return f'{MON[int(m)]} {int(dd)}, {y}'


def initials(name):
    w = [x for x in name.replace('.', ' ').split() if x[0].isupper() and x not in ('Jr',)]
    return (w[0][0] + w[-1][0]) if len(w) > 1 else w[0][:2]


class R:
    def __init__(self, ctx, d):
        self.c, self.u, self.e = ctx, ctx.url, ctx.esc
        self.hearings = sorted(d['hearings'], key=lambda h: h['date'])
        self.people = d['people']
        self.h_by = {h['slug']: h for h in self.hearings}
        self.p_by = {p['slug']: p for p in self.people}
        for h in self.hearings:
            for s in h.get('witnesses', []):
                assert s in self.p_by, s
            for q in h.get('quotes', []):
                assert q['who'] in self.p_by, q['who']
        for p in self.people:
            p['quotes'] = [(h, q) for h in self.hearings for q in h.get('quotes', []) if q['who'] == p['slug']]
            p['hearings'] = [s for s in p['hearings'] if s in self.h_by]
        self.head = (f'<link rel="stylesheet" href="{self.u("/static/encounters.css")}">'
                     f'<link rel="stylesheet" href="{self.u("/static/onrecord.css")}">'
                     f'<link rel="stylesheet" href="{self.u("/static/sources.css")}">')

    def run(self):
        self.hub()
        for h in self.hearings:
            if h.get('page', True):
                self.hearing(h)
        self.people_hub()
        for p in self.people:
            self.person(p)

    # --- links and small parts ------------------------------------------------------------------
    def hurl(self, h):
        if h.get('page', True):
            return self.u('/ufo/hearings/' + h['slug'] + '/')
        return self.u('/ufo/releases/' + h['release'] + '/')

    def purl(self, p):
        return self.u('/ufo/people/' + p['slug'] + '/')

    def avatar(self, p, size=''):
        return (f'<span class="or-av {size}" style="--t:{SIDES[p["side"]][2]}" aria-hidden="true">{self.e(initials(p["name"]))}</span>')

    def chip(self, p):
        return f'<a class="or-chip" href="{self.purl(p)}" style="--t:{SIDES[p["side"]][2]}">{self.e(p["name"])}</a>'

    def quote(self, h, q, show_who=True, show_hearing=False):
        e, p = self.e, self.p_by[q['who']]
        who = f'<a href="{self.purl(p)}">{e(p["name"])}</a>' if show_who else ''
        where = f'<a href="{self.hurl(h)}">{e(h["short"])}</a>' if show_hearing else ''
        bits = ', '.join(x for x in (who, where, SRC[q['src']]) if x)
        note = f' <span class="or-qnote">({e(q["note"])})</span>' if q.get('note') else ''
        return (f'<figure class="or-q" style="--t:{SIDES[p["side"]][2]}"><blockquote><p>{e(q["q"])}</p></blockquote>'
                f'<figcaption>{bits}{note}</figcaption></figure>')

    def ext_list(self, links):
        return ''.join(f'<li><a href="{self.e(l["url"])}" rel="noopener">{self.e(l["name"])}</a>{_sources.arch_link(self.c, l["url"])}</li>' for l in links)

    # --- /ufo/hearings/ ----------------------------------------------------------------------------
    def hcard(self, h):
        e = self.e
        ppl = ''.join(self.chip(self.p_by[s]) for s in h.get('witnesses', []))
        return (f'<li class="or-h"><span class="or-yr">{h["date"][:4]}</span><div class="or-hcard">'
                f'<p class="ce-meta">{e(dateline(h["date"]))} · {e(FLAG.get(h["country"], ""))}</p>'
                f'<h3><a href="{self.hurl(h)}">{e(h["title"])}</a></h3>'
                f'<p class="or-body">{e(h["body"])}</p><p>{e(h["summary"])}</p>'
                f'{f"<p class=or-who><b>Testified:</b> {ppl}</p>" if ppl else ""}</div></li>')

    def hub(self):
        c, e = self.c, self.e
        n, y0 = len(self.hearings), self.hearings[0]['date'][:4]
        quotes = [(h, q) for h in self.hearings for q in h.get('quotes', [])][::-1][:4]
        qs = ''.join(self.quote(h, q, show_hearing=True) for h, q in quotes)
        body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/ufo/')}">UFOs</a> / On the record</p>
  <h1>UFO hearings: what was said under oath</h1>
  <p class="lede">{n} times since {y0}, lawmakers have held public hearings on UFOs. Here is who testified, what they said and what changed afterwards, with links to the official transcripts.</p>
  <p class="or-tabs"><a class="btn" href="{self.u('/ufo/people/')}">Everyone who testified ({len(self.people)})</a> <a class="btn btn-ghost" href="{self.u('/ufo/releases/')}">All official releases</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
  <h2>In their own words</h2>
  <div class="or-qgrid">{qs}</div>
  <h2>Every hearing, oldest first</h2>
  <ol class="or-tl">{''.join(self.hcard(h) for h in self.hearings)}</ol>
  {_sources.about_box(c, '/ufo/hearings/', 'UFO hearings in Congress: every public hearing since 1966', '<p>We read the official transcripts and written statements and summed them up in our own words. Quotes are short and copied word for word from US congressional records, which are public domain; each page links the original so you can read the whole thing. Testimony is what people told lawmakers, not a finding of fact, so we note where the Pentagon or AARO disputes a claim. Private briefings and so-called citizen hearings are left out because they were not held by a legislature.</p>')}
</div></div>'''
        c.write('/ufo/hearings/', c.page('/ufo/hearings/', 'UFO hearings in Congress: every public hearing since 1966', body,
                                         f'All {n} public UFO and UAP hearings held by lawmakers since {y0}: who testified, key quotes from the '
                                         'official transcripts, and what happened next.', body_class='encounters onrecord', head_extra=self.head))

    def hearing(self, h):
        c, e = self.c, self.e
        paras = ''.join(f'<p>{e(t)}</p>' for t in h['text'])
        qs = ''.join(self.quote(h, q) for q in h.get('quotes', []))
        ppl = ''.join(self.pcard(self.p_by[s]) for s in h.get('witnesses', []))
        rel = f'<p><a href="{self.u("/ufo/releases/" + h["release"] + "/")}">This hearing in our official releases list</a></p>' if h.get('release') else ''
        mil = f'<p>The encounter it describes is also in <a href="{self.u("/military/")}">military encounters</a> ({e(h["military"])}).</p>' if h.get('military') else ''
        pages = [x for x in self.hearings if x.get('page', True)]
        i = pages.index(h)
        prev, nxt = (pages[i - 1] if i else None), (pages[i + 1] if i + 1 < len(pages) else None)
        pn = ''.join(f'<a class="ce-pn {k}" href="{self.hurl(y)}"><small>{lab}</small>{e(y["title"])}</a>'
                     for k, lab, y in (('prev', 'Earlier hearing', prev), ('next', 'Later hearing', nxt)) if y)
        body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/ufo/hearings/')}">UFO hearings</a> / {h['date'][:4]}</p>
  <h1>{e(h['title'])}</h1>
  <p class="ce-when">{e(dateline(h['date']))} · {e(h['body'])}</p>
  <p class="lede">{e(h['summary'])}</p>
</div></section>
<div class="band band-mist"><div class="wrap ce-body">
  <article class="prose">{paras}{qs}{mil}</article>
  <aside class="ce-side">
    <div class="ce-facts">
      <p><b>Date</b>{e(dateline(h['date']))}</p>
      <p><b>Held by</b>{e(h['body'])}</p>
      {f'<p><b>Chair</b>{e(h["chair"])}</p>' if h.get('chair') else ''}
      <p><b>Testified</b>{len(h.get('witnesses', []))} {'person' if len(h.get('witnesses', [])) == 1 else 'people'}</p>
      {f'<p><b>What came next</b>{e(h["outcome"])}</p>' if h.get('outcome') else ''}
    </div>
  </aside>
</div></div>
<div class="band ce-more"><div class="wrap">
  <h2>Who testified</h2>
  <div class="or-pgrid">{ppl}</div>
  <h2>Read the official record</h2><ul class="ce-src">{self.ext_list(h['links'])}</ul>
  {rel}
  <nav class="ce-pns" aria-label="More hearings">{pn}</nav>
  <p><a href="{self.u('/ufo/hearings/')}">All {len(self.hearings)} hearings</a></p>
</div></div>'''
        c.write('/ufo/hearings/' + h['slug'] + '/', c.page('/ufo/hearings/' + h['slug'] + '/', f'{h["title"]} ({h["date"][:4]})', body,
                                                           h['summary'], body_class='encounters onrecord', head_extra=self.head,
                                                           article={'published': '2026-10-23', 'updated': h.get('updated')}))

    # --- /ufo/people/ ------------------------------------------------------------------------------
    def pcard(self, p):
        e = self.e
        yrs = ', '.join(dict.fromkeys(self.h_by[s]['date'][:4] for s in p['hearings']))
        return (f'<article class="or-pcard"><a href="{self.purl(p)}">{self.avatar(p)}<span>'
                f'<span class="ce-name">{e(p["name"])}</span><span class="ce-meta">{e(p["role"])}</span>'
                f'<span class="or-side" style="--t:{SIDES[p["side"]][2]}">{ONE[p["side"]]} · {yrs}</span></span></a></article>')

    def people_hub(self):
        c, e = self.c, self.e
        groups = ''
        for k, (name, sub, col) in SIDES.items():
            ps = sorted((p for p in self.people if p['side'] == k), key=lambda p: (self.h_by[p['hearings'][0]]['date'], p['name']))
            if ps:
                groups += (f'<section class="or-group" style="--t:{col}"><h2><i class="or-dot" aria-hidden="true"></i>{name} <span>{len(ps)}</span></h2>'
                           f'<p class="my-gsub">{e(sub)}</p><div class="or-pgrid">{"".join(self.pcard(p) for p in ps)}</div></section>')
        body = f'''
<section class="band band-dark ce-head"><div class="wrap">
  <p class="crumb"><a href="{self.u('/ufo/hearings/')}">UFO hearings</a> / People</p>
  <h1>Who has testified about UFOs</h1>
  <p class="lede">{len(self.people)} pilots, sailors, scientists, officials, whistleblowers and reporters who have spoken to lawmakers about UFOs, from J. Allen Hynek in 1966 to the Navy and Air Force veterans of 2025.</p>
</div></section>
<div class="band band-mist"><div class="wrap">
  {groups}
  <aside class="ce-note"><h2>About these profiles</h2><p>Each profile covers what the person did and what they told lawmakers, in our words, with short quotes from the official record. Being listed here is not an endorsement of anyone's claims, and where officials dispute what was said, we say so.</p></aside>
</div></div>'''
        c.write('/ufo/people/', c.page('/ufo/people/', 'People who testified to Congress about UFOs', body,
                                       f'{len(self.people)} people who have testified at UFO and UAP hearings: pilots, whistleblowers, '
                                       'scientists and officials, with what they said on the record.', body_class='encounters onrecord', head_extra=self.head))

    def person(self, p):
        c, e = self.c, self.e
        paras = ''.join(f'<p>{e(t)}</p>' for t in p['text'])
        qs = ''.join(self.quote(h, q, show_who=False, show_hearing=True) for h, q in p['quotes'])
        hs = ''.join(f'<li><span class="yr">{h["date"][:4]}</span><span><a href="{self.hurl(h)}">{e(h["title"])}</a></span></li>'
                     for h in (self.h_by[s] for s in p['hearings']))
        others = []
        for s in p['hearings']:
            others += [self.p_by[w] for w in self.h_by[s].get('witnesses', []) if w != p['slug'] and self.p_by[w] not in others]
        alongside = ''.join(self.chip(o) for o in others)
        thin = len(p['text']) < 2 and not p['quotes']
        body = f'''
<section class="band band-dark ce-head"><div class="wrap or-phero">
  {self.avatar(p, 'or-av-lg')}
  <div>
    <p class="crumb"><a href="{self.u('/ufo/people/')}">People</a> / {SIDES[p['side']][0]}</p>
    <h1>{e(p['name'])}</h1>
    <p class="ce-when">{e(p['role'])}{(' · ' + e(p['years'])) if p.get('years') else ''}</p>
  </div>
</div></section>
<div class="band band-mist"><div class="wrap">
  <article class="prose">{paras}{f'<h2>On the record</h2>{qs}' if qs else ''}
    <h2>Hearings</h2><ol class="timeline">{hs}</ol>
    {f'<h2>Testified alongside</h2><p class="or-who">{alongside}</p>' if alongside else ''}
    <p><a href="{self.u('/ufo/people/')}">Everyone who has testified</a></p>
  </article>
</div></div>'''
        c.write('/ufo/people/' + p['slug'] + '/', c.page('/ufo/people/' + p['slug'] + '/', f'{p["name"]}: UFO hearing testimony', body,
                                                         f'{p["name"]}, {p["role"]}: ' + p['text'][0][:120].rsplit(' ', 1)[0] + '...',
                                                         body_class='encounters onrecord', head_extra=self.head, noindex=thin,
                                                         article={'published': '2026-10-23', 'updated': p.get('updated')}))

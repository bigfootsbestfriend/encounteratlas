"""On this day: /on-this-day/ (calendar) and one page per calendar day, /on-this-day/<month>-<day>/.

Each day collects everything we have with an exact date: old-newspaper monster and airship stories (historic.json,
including the dates of the papers that ran them), military encounters, mysteries and close encounters, plus the
Canadian UFO Survey sightings logged on that date since 1989 (count, busiest year and the strangest few) and a link to
that month's Air Force files.
"""
import importlib.util, json, os
from collections import Counter, defaultdict

MON = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
DAYS_IN = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
CU_TYPE = {'nl': 'Night lights', 'nd': 'Night disc', 'dd': 'Daylight disc', 'ph': 'Physical traces', 'c1': 'Close encounter',
           'c2': 'Close encounter with traces', 'c3': 'Close encounter with beings',
           'c4': 'Contact or abduction claim', 'rd': 'Radar', 'ux': 'Unusual'}


def full(d):
    d = str(d or '')
    return d if len(d) == 10 and d[4] == '-' and d[7] == '-' else ''


def clip(t, n=280):
    """Whole sentences up to about n characters; falls back to a word cut with an ellipsis."""
    if len(t) <= n:
        return t
    cut = t[:n]
    end = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    return cut[:end + 1] if end > 80 else cut.rsplit(' ', 1)[0] + '\u2026'


def build(ctx):
    R = ctx.ROOT
    esc, url = ctx.esc, ctx.url
    load = lambda f: json.load(open(os.path.join(R, 'data', f), encoding='utf-8')) if os.path.exists(os.path.join(R, 'data', f)) else []
    spec = importlib.util.spec_from_file_location('hist_topics', os.path.join(R, 'site', 'sections', 'historic.py'))
    hmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hmod)
    topics = getattr(hmod, 'TOPICS', {})

    ev = defaultdict(list)   # 'MM-DD' -> [(year, kind, title, where, url, note)]
    for x in load('historic.json'):
        dates = [full(x.get('date'))] + [full(p.get('date')) for p in (x.get('papers') or []) if isinstance(p, dict)]
        d = next((v for v in dates if v), '')
        if not d:
            continue
        t = topics.get(x.get('k'))
        u = url(f'/history/{t[0]}/#h-{x["id"]}') if t else url('/history/')
        where = ', '.join(v for v in (x.get('town'), x.get('state')) if v)
        ev[d[5:]].append((int(d[:4]), 'In the old newspapers', x['title'], where, u, x.get('summary', '')))
    for x in load('military.json'):
        d = full(x.get('date'))
        if d:
            ev[d[5:]].append((int(d[:4]), 'Military encounter', x['name'], x.get('place', ''), url('/military/'), x.get('summary', '')))
    for x in load('mysteries.json'):
        d = full(x.get('date'))
        if d:
            ev[d[5:]].append((int(d[:4]), 'Mystery', x['name'], x.get('place', ''), url(f'/mysteries/{x["slug"]}/'), x.get('summary', '')))
    for x in load('close_encounters.json'):
        d = full(x.get('date'))
        if d:
            ev[d[5:]].append((int(d[:4]), 'Close encounter', x['name'], x.get('place', ''), url(f'/encounters/{x["slug"]}/'), x.get('summary', '')))

    for x in load('famous_cases.json'):
        d = full(x.get('date'))
        if d:
            ev[d[5:]].append((int(d[:4]), 'Famous UFO case', x['name'], x.get('place', ''), url(f'/ufo/cases/{x["slug"]}/'), x.get('summary', '')))

    cu = defaultdict(list)
    for x in load('ufo_cases_canada.json'):
        d = full(x.get('date'))
        if d:
            cu[d[5:]].append(x)
    bb_month = Counter(b['month'] for b in ctx.bluebook if b.get('month'))

    def key(m, d):
        return f'{m:02d}-{d:02d}'

    def path(m, d):
        return f'/on-this-day/{MON[m].lower()}-{d}/'

    head = f'<link rel="stylesheet" href="{url("/static/onthisday.css")}">'
    for m in range(1, 13):
        for d in range(1, DAYS_IN[m] + 1):
            k, name = key(m, d), f'{MON[m]} {d}'
            items = sorted(ev.get(k, []), key=lambda t: t[0])
            cases = cu.get(k, [])
            evs = ''.join(
                f'<li><span class="otd-yr">{y}</span><div><span class="otd-kind">{esc(kind)}</span>'
                f'<h3><a href="{u}">{esc(t)}</a></h3>{f"<p class=otd-where>{esc(w)}</p>" if w else ""}'
                f'{f"<p>{esc(clip(n))}</p>" if n else ""}</div></li>'
                for y, kind, t, w, u, n in items)
            cu_html = ''
            if cases:
                ys = Counter(c['date'][:4] for c in cases)
                top = max(ys, key=ys.get)
                odd = sorted((c for c in cases if c.get('type') in ('c1', 'c2', 'c3', 'c4', 'ph', 'dd')),
                             key=lambda c: (not c.get('note'), -(c.get('strange') or 0), c['date']))[:6]
                provs = Counter(c.get('prov') for c in cases if c.get('prov')).most_common(3)
                cu_html = (f'<section class="otd-cu"><h2>Canadian UFO sightings on {name}</h2>'
                           f'<p>The Canadian UFO Survey logged <strong>{len(cases)}</strong> sighting{"s" if len(cases) != 1 else ""} on {name} between 1989 and today'
                           f'{f", most in {top} ({ys[top]})" if len(ys) > 1 else ""}. '
                           + ('Most came from ' + ', '.join(f'<a href="{url("/ufo/canada/" + ctx.slugify(p) + "/")}">{esc(p)}</a>' for p, _ in provs) + '.' if provs else '')
                           + '</p>')
                if odd:
                    cu_html += ('<h3>The strangest ones</h3><ul class="otd-cases">' + ''.join(
                        f'<li><b>{c["date"][:4]}</b> · {esc(c.get("place") or "")}{", " + esc(c["prov"]) if c.get("prov") else ""} · '
                        f'<span class="muted">{esc(CU_TYPE.get(c.get("type"), "Sighting"))}{", " + str(c["wit"]) + " witnesses" if (c.get("wit") or 0) > 1 else ""}</span>'
                        f'{"<br><span class=otd-note>" + esc(c["note"]) + "</span>" if c.get("note") else ""}</li>' for c in odd) + '</ul>')
                cu_html += f'<p class="small">Source: the Canadian UFO Survey, Ufology Research. <a href="{url("/ufo/canada/")}">Explore every Canadian sighting</a>.</p></section>'
            bb = bb_month.get(m, 0)
            bb_html = (f'<p class="otd-bb">The US Air Force opened <strong>{bb:,}</strong> Project Blue Book files for sightings in {MON[m]}, 1947 to 1969. '
                       f'<a href="{url("/ufo/blue-book/")}">Browse the Air Force files</a>.</p>') if bb else ''
            prev_m, prev_d = (m, d - 1) if d > 1 else ((m - 2) % 12 + 1, DAYS_IN[(m - 2) % 12 + 1])
            next_m, next_d = (m, d + 1) if d < DAYS_IN[m] else (m % 12 + 1, 1)
            n_ev = len(items)
            lede = (f'{n_ev} strange event{"s" if n_ev != 1 else ""} from history happened on {name}' if n_ev
                    else f'What happened on {name} in the world of UFOs, monsters and mysteries')
            lede += f', plus {len(cases)} Canadian UFO sightings.' if cases else '.'
            body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{url('/on-this-day/')}">On this day</a></p>
  <h1>{name} in strange history</h1>
  <p class="lede">{lede}</p>
  <p class="otd-nav"><a class="btn btn-sm btn-ghost" href="{url(path(prev_m, prev_d))}">&larr; {MON[prev_m]} {prev_d}</a>
    <a class="btn btn-sm btn-ghost" href="{url(path(next_m, next_d))}">{MON[next_m]} {next_d} &rarr;</a></p>
</div></section>
<div class="band band-mist"><div class="wrap otd-body">
  {f'<ol class="otd-list">{evs}</ol>' if evs else f'<p>No famous case or old newspaper story we know of is dated {name}. Yet. Seen something on this date? <a href="{url("/report/")}">Report it</a>.</p>'}
  {cu_html}
  {bb_html}
  <p><a class="btn" href="{url('/on-this-day/')}">Pick another day</a> <a class="btn btn-quiet" href="{url('/report/')}">Report an encounter</a></p>
</div></div>'''
            desc = (f'UFO sightings, monster reports and mysteries that happened on {name}: ' +
                    '; '.join(f'{t} ({y})' for y, _, t, _, _, _ in items[:3]) if items else
                    f'UFO sightings and strange events on {name}, including {len(cases)} Canadian UFO reports.')
            ctx.write(path(m, d), ctx.page(path(m, d), f'{name} in strange history: UFOs, monsters and mysteries', body, desc[:300], head_extra=head))

    months = ''
    for m in range(1, 13):
        cells = ''.join(f'<a href="{url(path(m, d))}" data-md="{key(m, d)}" class="{"has" if ev.get(key(m, d)) else ""}" '
                        f'title="{MON[m]} {d}: {len(ev.get(key(m, d), []))} events">{d}</a>' for d in range(1, DAYS_IN[m] + 1))
        months += f'<section class="otd-month"><h2>{MON[m]}</h2><div class="otd-days">{cells}</div></section>'
    body = f'''
<section class="band band-dark"><div class="wrap">
  <h1>On this day in strange history</h1>
  <p class="lede">Pick a date to see the UFO sightings, monster reports, mysteries and military encounters that happened on it. Bold days have a famous case or an old newspaper story.</p>
  <p><a class="btn" id="otd-today" href="{url('/on-this-day/')}">See today</a></p>
</div></section>
<div class="band band-mist"><div class="wrap"><div class="otd-cal">{months}</div></div></div>
<script>
(() => {{
  const t = new Date(), M = {json.dumps([x.lower() for x in MON])};
  const a = document.getElementById('otd-today');
  a.href = '{url('/on-this-day/')}' + M[t.getMonth() + 1] + '-' + t.getDate() + '/';
  a.textContent = 'See today: ' + t.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric' }});
  const md = String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0');
  const c = document.querySelector('[data-md="' + md + '"]'); if (c) c.classList.add('today');
}})();
</script>'''
    ctx.write('/on-this-day/', ctx.page('/on-this-day/', 'On this day in strange history: UFOs, monsters and mysteries by date', body,
                                        'Every day of the year: the UFO sightings, monster reports, mysteries and military encounters that happened on that date.',
                                        head_extra=head))

"""Weekly email: /newsletter/ (signup and confirm page) and /newsletter.json (this week's content).

The shared newsletter Worker (repo bigfootsbestfriend/newsletter, site key 'encounteratlas') handles signups and
double opt-in; its weekly job reads /newsletter.json each Thursday and saves a Resend broadcast for Mike to send.
"""
import datetime, json, os, urllib.request

STATES = {
    'check': "Almost done: check your inbox for a confirmation email and click the button in it.",
    'invalid': "That email address doesn't look right. Please try again.",
    'confirming': 'Confirming your subscription…',
    'confirmed': "You're subscribed. The next weekly email lands on Thursday.",
    'expired': "That confirmation link has expired. Sign up again below and we'll send a new one.",
    'error': 'Something went wrong on our side. Please try again in a few minutes.',
}
MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December']


def nice(d):
    y, m, day = (int(x) for x in d.split('-'))
    return f'{MONTHS[m]} {day}, {y}'


def this_week(dates, start):
    """True if any full YYYY-MM-DD date falls on the 7 days from start (any year)."""
    days = {(start + datetime.timedelta(days=i)).strftime('%m-%d') for i in range(7)}
    return next((d for d in dates if len(d) == 10 and d[5:] in days), None)


def build(ctx):
    e, u = ctx.esc, ctx.url
    states = ''.join(f'<p class="lede nl-state" data-state="{k}" hidden><strong>{e(v)}</strong></p>' for k, v in STATES.items())
    script = f'''<script>
(() => {{
  const show = s => {{
    document.querySelectorAll('[data-state]').forEach(p => p.hidden = p.dataset.state !== s);
    const form = document.querySelector('.signup');
    if (form) form.style.display = ['check', 'confirming', 'confirmed'].includes(s) ? 'none' : '';
  }};
  const t = new URLSearchParams(location.search).get('confirm');
  if (t) {{
    show('confirming');
    history.replaceState(null, '', location.pathname);
    fetch({json.dumps(ctx.NEWSLETTER_API + '/confirm')}, {{method: 'POST', headers: {{'content-type': 'application/json'}}, body: JSON.stringify({{t}})}})
      .then(r => r.json()).then(d => show(d.state === 'invalid' ? 'expired' : d.state)).catch(() => show('error'));
  }} else if (location.hash) show(location.hash.slice(1));
}})();
</script>'''
    body = f'''
<section class="band band-dark"><div class="wrap">
  <h1>The Encounter Atlas weekly email</h1>
  {states}
  <p class="lede">One short email every Thursday with the strange stories worth your time.</p>
</div></section>
<div class="band band-mist"><div class="wrap prose">
  <ul class="signs">
    <li><strong>This week in the old newspapers:</strong> wild men, sea serpents and mystery airships reported this same week, a century or more ago, with links to the original pages.</li>
    <li><strong>Creature of the week:</strong> one cryptid, its story and where people say they've seen it.</li>
    <li><strong>New reader reports:</strong> the latest encounters sent in by readers and checked by a person.</li>
  </ul>
  {ctx.signup_box('page', 'Sign up', 'Free. No spam, and we never share your address. Unsubscribe in one click from any email.')}
  <p class="small">How we handle your address: see the <a href="{u('/privacy/')}#newsletter">privacy policy</a>.</p>
</div></div>
{script}'''
    ctx.write('/newsletter/', ctx.page('/newsletter/', 'The Encounter Atlas weekly email', body,
                                       'A free weekly email: old-newspaper monster stories from this week in history, a creature of the week and new reader reports.'))
    with open(os.path.join(ctx.OUT, 'newsletter.json'), 'w') as f:
        json.dump(content(ctx), f, indent=1)


def content(ctx):
    S = ctx.SITE_URL
    today = datetime.date.today()
    # weekly.py runs Thursday morning: cover that Thursday through the next Wednesday.
    start = today + datetime.timedelta(days=(3 - today.weekday()) % 7)
    sections = []

    hist = json.load(open(os.path.join(ctx.ROOT, 'data', 'historic.json')))
    old = []
    for x in hist:
        d = this_week([x['date']] + [p.get('date', '') for p in x.get('papers', [])], start)
        if d:
            where = ', '.join(v for v in (x.get('town'), x.get('state')) if v)
            old.append((d, {'title': x['title'], 'url': f'{S}/history/#h-{x["id"]}', 'note': nice(d) + (f' · {where}' if where else '')}))
    for fn, path in (('mysteries.json', '/mysteries/{slug}/'), ('military.json', '/military/')):
        for x in json.load(open(os.path.join(ctx.ROOT, 'data', fn))):
            d = this_week([x.get('date') or ''], start)
            if d:
                old.append((d, {'title': x['name'], 'url': S + path.format(**x), 'note': nice(d) + ' · ' + x['place']}))
    old.sort(key=lambda t: (t[0][5:], t[0]))
    if old:
        sections.append({'title': 'This week in strange history', 'items': [i for _, i in old[:8]]})

    # Creature of the week: a fresh one each week, in a fixed shuffled order so neighbours aren't alike.
    cs = sorted(ctx.creatures, key=lambda c: hash_slug(c['slug']))
    c = cs[start.isocalendar()[1] % len(cs)]
    sections.append({'title': 'Creature of the week', 'items': [
        {'title': c['name'], 'url': f'{S}/creatures/{c["slug"]}/', 'note': c['summary']}]})

    reports = []
    try:
        api = os.environ.get('EA_API', 'https://api.encounteratlas.com').rstrip('/')
        req = urllib.request.Request(api + '/api/reports?limit=20', headers={'user-agent': 'EncounterAtlasBuild/1.0 (+https://encounteratlas.com)'})
        with urllib.request.urlopen(req, timeout=15) as r:
            since = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
            for x in json.load(r).get('reports', []):
                if (x.get('approved_at') or 0) >= since:
                    what = x.get('creature_name') or x.get('other_what') or 'Something strange'
                    reports.append({'title': f'{what} near {x["place"]}' if x.get('place') else what,
                                    'url': f'{S}/reports/?id={x["id"]}', 'note': x.get('snippet') or ''})
    except Exception as err:
        print(f'newsletter: reader reports skipped: {err!r}')
    if reports:
        sections.append({'title': 'New reader reports', 'items': reports[:6]})
    sections.append({'title': 'Seen something?', 'items': [
        {'title': 'Report an encounter', 'url': f'{S}/report/', 'note': 'Every report is read by a person. Your exact location stays private.'}]})

    lead = old[0][1]['title'] if old else None
    return {'site': 'encounteratlas', 'date': start.isoformat(),
            'subject': f'This week in strange history: {lead}' if lead else f'Creature of the week: {c["name"]}',
            'intro': 'Here are the strange stories from this week in history, a creature to read up on, and what readers sent in.',
            'sections': sections}


def hash_slug(s):
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) % 1000003
    return h

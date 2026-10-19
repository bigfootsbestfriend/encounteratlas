"""Weekly email: /newsletter/ (signup and confirm page) and /newsletter.json (this week's content).

The shared newsletter Worker (repo bigfootsbestfriend/newsletter, site key 'encounteratlas') handles signups (single
opt-in) and sends /newsletter/welcome.json as the welcome email; its weekly job reads /newsletter.json each Thursday and
saves a Resend broadcast for Mike to send. The book of the week links to /books/, never to Amazon (no affiliate links in email).
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
    os.makedirs(os.path.join(ctx.OUT, 'newsletter'), exist_ok=True)
    with open(os.path.join(ctx.OUT, 'newsletter', 'welcome.json'), 'w') as f:
        json.dump(welcome(ctx), f, indent=1)


def week_start(today=None):
    """weekly.py runs Thursday morning: an issue covers that Thursday through the next Wednesday."""
    today = today or datetime.date.today()
    return today + datetime.timedelta(days=(3 - today.weekday()) % 7)


def week_creature(ctx, start):
    """A fresh creature each week, in a fixed shuffled order so neighbours aren't alike."""
    cs = sorted(ctx.creatures, key=lambda c: hash_slug(c['slug']))
    return cs[start.isocalendar()[1] % len(cs)]


def week_book(ctx, start=None):
    """(book, why) for this week: a book about the creature of the week if we have one, else the next in a fixed rotation."""
    start = start or week_start()
    p = os.path.join(ctx.ROOT, 'data', 'media.json')
    # Only books with an Open Library cover (data/media.json 'cover', checked 2026-10-18), so the email shows the cover.
    books = [b for b in json.load(open(p, encoding='utf-8'))['books'] if b.get('isbn10') and b.get('cover')] if os.path.exists(p) else []
    if not books:
        return None, ''
    c = week_creature(ctx, start)
    match = [b for b in books if c['slug'] in b['for']]
    if match:
        return match[start.isocalendar()[1] % len(match)], f'Goes with this week\'s creature: read more about the {c["name"]} in this one.'
    books.sort(key=lambda b: hash_slug(b['isbn10']))
    b = books[(start.isocalendar()[0] * 53 + start.isocalendar()[1]) % len(books)]
    about = [ctx.by_slug[t]['name'] for t in b['for'] if t in ctx.by_slug][:2]
    return b, (f'This week\'s pick from our bookshelf, on {" and ".join(about)}.' if about else 'This week\'s pick from our bookshelf.')


def content(ctx):
    S = ctx.SITE_URL
    start = week_start()
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

    c = week_creature(ctx, start)
    sections.append({'title': 'Creature of the week', 'items': [
        {'title': c['name'], 'url': f'{S}/creatures/{c["slug"]}/', 'note': c['summary']}]})
    b, why = week_book(ctx, start)
    if b:
        sections.append({'title': 'Book of the week', 'items': [
            {'title': b['title'], 'url': f'{S}/books/#b-{b["isbn10"]}', 'image': f'https://covers.openlibrary.org/b/isbn/{b["isbn10"]}-M.jpg',
             'note': f'{b["author"].split(",")[0]}{", " + str(b["year"]) if b.get("year") else ""}. {why}'}]})

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


def welcome(ctx):
    """The welcome email the newsletter Worker sends right after signup: {subject, html, text}. Email-safe HTML (tables,
    inline styles, PNG images only) in the site's colours: spruce, lantern gold and lichen."""
    S = ctx.SITE_URL
    img = lambda n: f'{S}/static/email/{n}.png'
    font = "font-family:Georgia,'Times New Roman',serif"
    body = "font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
    gets = [('bigfoot', 'This week in the old newspapers', 'Wild men, sea serpents and phantom airships printed this same week, 100+ years ago.'),
            ('loch-ness-monster', 'Creature of the week', 'One cryptid from around the world, its best cases and where people say they see it.'),
            ('ufo-saucer', 'New reader reports and a book of the week', 'Fresh sightings sent in by readers, plus one good book to read next.')]
    rows = ''.join(f'''<tr><td width="64" style="padding:10px 14px 10px 0;vertical-align:top"><img src="{img(a)}" width="56" height="56" alt="" style="display:block"></td>
<td style="padding:10px 0;vertical-align:top;{body}"><div style="font-weight:700;color:#F3F1DA;font-size:16px">{t}</div><div style="color:#C9D3A4;font-size:15px;line-height:1.45">{d}</div></td></tr>''' for a, t, d in gets)
    start = [(f'{S}/map/', 'The encounter map', 'Every sighting, creature and Air Force file near you.'),
             (f'{S}/ufo/cases/', 'Famous UFO cases worldwide', 'From Nuremberg 1561 to Shag Harbour and the Kaikōura lights.'),
             (f'{S}/on-this-day/', 'What happened on this day', 'Pick any date and see the strange history that happened on it.'),
             (f'{S}/stories/', 'Witness stories', 'First-hand accounts, told in the witnesses\' own words.')]
    links = ''.join(f'''<tr><td style="padding:12px 0;border-bottom:1px solid #E4EBE6;{body}"><a href="{u}" style="color:#13261F;font-weight:700;font-size:16px;text-decoration:none">{t} &rarr;</a>
<div style="color:#4D6157;font-size:14px;line-height:1.45">{d}</div></td></tr>''' for u, t, d in start)
    html = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Welcome to Encounter Atlas</title></head>
<body style="margin:0;padding:0;background:#E4EBE6">
<div style="display:none;max-height:0;overflow:hidden">Your first strange stories land Thursday. Here's where to start.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#E4EBE6"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:580px">
<tr><td style="background:#13261F;border-radius:16px 16px 0 0;padding:22px 26px;border-bottom:4px solid #F2B33D">
  <table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="padding-right:12px"><img src="{img('logo')}" width="44" height="44" alt="" style="display:block;border-radius:8px"></td>
  <td style="{font};font-size:24px;font-weight:700;color:#F3F1DA">Encounter Atlas</td></tr></table></td></tr>
<tr><td style="background:#13261F;padding:8px 26px 26px">
  <h1 style="{font};font-size:30px;line-height:1.2;color:#FFD27A;margin:0 0 12px">You're in. Welcome to the strange side.</h1>
  <p style="{body};font-size:17px;line-height:1.55;color:#F3F1DA;margin:0 0 18px">Thanks for signing up. Every Thursday you'll get one short email with the best of what's strange, from Bigfoot in the Pacific Northwest to lake monsters in Scotland and lights over the Nullarbor.</p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>
</td></tr>
<tr><td style="background:#ffffff;padding:24px 26px">
  <h2 style="{font};font-size:22px;color:#13261F;margin:0 0 4px">While you wait, start here</h2>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{links}</table>
</td></tr>
<tr><td style="background:#F6F0E2;padding:24px 26px;border-radius:0 0 16px 16px">
  <h2 style="{font};font-size:22px;color:#13261F;margin:0 0 8px">One question for you</h2>
  <p style="{body};font-size:16px;line-height:1.55;color:#15241E;margin:0 0 16px">What's the strangest thing you've ever seen? Hit reply and tell us. We read every reply. If you'd like it on the map, you can also send it in as a report; your exact location always stays private.</p>
  <a href="{S}/report/" style="display:inline-block;background:#F2B33D;color:#13261F;{body};font-weight:700;font-size:16px;padding:13px 22px;border-radius:999px;text-decoration:none">Report an encounter</a>
</td></tr>
<tr><td style="padding:18px 10px;text-align:center;{body};font-size:13px;line-height:1.5;color:#4D6157">
  You're getting this because you signed up at <a href="{S}/" style="color:#4D6157">encounteratlas.com</a>. Every weekly email has a one-click unsubscribe link.<br>Didn't sign up? Just reply and we'll take you off the list.</td></tr>
</table></td></tr></table></body></html>'''
    text = ("You're in. Welcome to Encounter Atlas.\n\nEvery Thursday you'll get one short email:\n"
            + ''.join(f'- {t}: {d}\n' for _, t, d in gets)
            + '\nWhile you wait, start here:\n' + ''.join(f'- {t}: {u}\n' for u, t, _ in start)
            + f"\nOne question: what's the strangest thing you've ever seen? Hit reply and tell us.\nReport an encounter: {S}/report/\n\n"
            "Didn't sign up? Reply and we'll take you off the list.")
    return {'subject': "You're in: welcome to Encounter Atlas", 'html': html, 'text': text}

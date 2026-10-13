"""Contact (/contact/), Advertise with us (/advertise/) and About (/about/, with a short "Get in touch with Mike" form).

All three share one form (_form); compact=True drops the topic picker for the About page.

The form posts to the reports Worker (/api/contact), which emails hello@ with reply-to set to the sender and stores nothing.
Until the Worker is live (EA_API unset in the build) the pages show the email address instead of the form.
"""
import json
import os

EMAIL = 'hello@encounteratlas.com'
TOPICS = [('general', 'General question'), ('advertise', 'Advertising or sponsorship'), ('correction', 'Correction or source'),
          ('takedown', 'Takedown or privacy request'), ('press', 'Press')]


def _form(ctx, topic, compact=False):
    api = os.environ.get('EA_API', '').rstrip('/')
    if not api:
        return (f'<div class="step"><p>Email us at <a href="mailto:{EMAIL}">{EMAIL}</a>. '
                'A contact form is coming soon.</p></div>')
    if compact:
        return f'''<form class="rep-form contact-form compact" novalidate>
  <fieldset class="step">
    <input type="hidden" name="topic" value="{topic}">
    <div class="row2">
      <div class="field"><label for="c-name">Your name <span class="hint">(optional)</span></label><input id="c-name" name="name" maxlength="100" autocomplete="name"></div>
      <div class="field"><label for="c-email">Your email</label><input id="c-email" name="email" type="email" maxlength="254" autocomplete="email" required></div>
    </div>
    <div class="field"><label for="c-msg">Message</label><textarea id="c-msg" name="message" rows="4" maxlength="5000" required></textarea></div>
    <div class="hp" aria-hidden="true"><label>Leave this empty <input name="website" tabindex="-1" autocomplete="off"></label></div>
    <div class="ts-slot"></div>
    <p><button class="btn" type="submit">Send to Mike</button></p>
    <p class="c-msg" role="status" aria-live="polite"></p>
  </fieldset>
</form>'''
    opts = ''.join(f'<option value="{k}"{" selected" if k == topic else ""}>{ctx.esc(v)}</option>' for k, v in TOPICS)
    return f'''<form class="rep-form contact-form" novalidate>
  <fieldset class="step">
    <div class="row2">
      <div class="field"><label for="c-name">Your name <span class="hint">(optional)</span></label><input id="c-name" name="name" maxlength="100" autocomplete="name"></div>
      <div class="field"><label for="c-email">Your email</label><input id="c-email" name="email" type="email" maxlength="254" autocomplete="email" required></div>
    </div>
    <div class="field"><label for="c-topic">What's it about?</label><select id="c-topic" name="topic">{opts}</select></div>
    <div class="field"><label for="c-msg">Message</label><textarea id="c-msg" name="message" rows="7" maxlength="5000" required></textarea>
      <p class="hint">Sending a sighting? Use the <a href="{ctx.url('/report/')}">report form</a> instead, so it can go on the map.</p></div>
    <div class="hp" aria-hidden="true"><label>Leave this empty <input name="website" tabindex="-1" autocomplete="off"></label></div>
    <div class="ts-slot"></div>
    <p><button class="btn" type="submit">Send message</button></p>
    <p class="c-msg" role="status" aria-live="polite"></p>
  </fieldset>
</form>'''


def _head(ctx):
    api = os.environ.get('EA_API', '').rstrip('/')
    css = f'<link rel="stylesheet" href="{ctx.url("/static/report.css")}">'
    if not api:
        return css
    cfg = json.dumps({'api': api, 'base': ctx.BASE, 'sitekey': os.environ.get('TURNSTILE_SITEKEY', '1x00000000000000000000AA')}).replace('</', '<\\/')
    return (css + f'<script type="application/json" id="ea-config">{cfg}</script>'
            '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" async defer></script>'
            f'<script src="{ctx.url("/static/vote.js")}" defer></script><script src="{ctx.url("/static/contact.js")}" defer></script>')


def build(ctx):
    U = ctx.url
    ctx.write('/contact/', ctx.page('/contact/', 'Contact us', f'''
<section class="band band-dark"><div class="wrap"><h1>Contact us</h1>
<p class="lede">Questions, corrections, a source we should add, or a report you want taken down. We read everything.</p></div></section>
<div class="band band-mist"><div class="wrap narrow">
{_form(ctx, 'general')}
<p class="small">We only use your email to reply. See our <a href="{U('/privacy/')}">privacy policy</a>.</p>
</div></div>''', 'Contact Encounter Atlas: questions, corrections, takedown requests and press.', head_extra=_head(ctx)))

    ctx.write('/advertise/', ctx.page('/advertise/', 'Advertise with us', f'''
<section class="band band-dark"><div class="wrap"><h1>Advertise with us</h1>
<p class="lede">Reach people who spend their evenings reading about Bigfoot, lake monsters and lights in the sky.</p></div></section>
<div class="band band-mist"><div class="wrap narrow prose">
<h2>Who reads Encounter Atlas</h2>
<p>Cryptid fans, UFO watchers, campers, hunters and hikers, true-mystery readers and podcast listeners. They come for the map, the creature pages,
the official UFO files and the close-encounter stories, and they send in sightings of their own.</p>
<h2>What we offer</h2>
<ul>
<li><strong>Sponsored creature or topic pages:</strong> one sponsor on a page such as Bigfoot, Mothman or UFO sightings.</li>
<li><strong>Podcasts, books and documentaries:</strong> featured spots in our podcast and reading lists.</li>
<li><strong>Gear and merch:</strong> trail cameras, night vision, camping gear and cryptid apparel that fit our field guides.</li>
<li><strong>Events and festivals:</strong> cryptid festivals, ghost walks and museum exhibits, shown on the map and on the place pages.</li>
</ul>
<h2>Our rules</h2>
<ul>
<li>Every paid placement is clearly labelled.</li>
<li>Sponsors never change what we write, and reports are never paid for or removed for a sponsor.</li>
<li>We don't sell or share reader data, and we don't run pop-ups.</li>
</ul>
<p>Tell us what you have in mind and we'll send current traffic numbers and rates.</p>
</div>
<div class="wrap narrow">{_form(ctx, 'advertise')}</div></div>''',
        'Advertise on Encounter Atlas: sponsored creature pages, podcast and book features, gear and events for cryptid and UFO fans.', head_extra=_head(ctx)))

    ctx.write('/about/', ctx.page('/about/', 'About and sources', f'''
<section class="band band-dark"><div class="wrap"><h1>About Encounter Atlas</h1>
<p class="lede">One place for strange sightings: creatures, UFOs and the official files, mapped and searchable.</p></div></section>
<div class="band band-mist"><div class="wrap prose">
<div class="owner-card">
  <picture><source srcset="{U('/static/img/mike-johnston.webp')}" type="image/webp"><img src="{U('/static/img/mike-johnston.png')}" alt="Mike Johnston" width="160" height="160"></picture>
  <div><h2>Who's behind it</h2>
  <p>Encounter Atlas is built and run by <strong>Mike Johnston</strong>, a Canadian web developer with a long-running interest in Bigfoot, lake monsters and UFOs.</p></div>
</div>
<section class="owner-contact" aria-labelledby="reach-mike"><h2 id="reach-mike">Get in touch with Mike</h2>
{_form(ctx, 'general', compact=True)}
<p class="small">Your email is only used to reply. See our <a href="{U('/privacy/')}">privacy policy</a>.</p></section>
<h2>Sources</h2>
<ul>
<li><strong>Project Blue Book case files</strong>, US Air Force, 1947 to 1969. US National Archives, Record Group 341, microfilm T1206. US federal records, no copyright in the United States. Places were matched automatically from the folder titles; dots marked “approximate” are placed at the state or country, not the exact spot.</li>
<li><strong>Canadian UFO sightings, 1989 to 2025</strong>: the Canadian UFO Survey, compiled each year by Ufology Research (Winnipeg) from reports to police, airports, the military, researchers and UFO groups. We left out reports the survey received from online UFO reporting sites. Ratings (explained, unexplained...) are the survey's; notes are lightly tidied. Places were matched to towns with GeoNames.</li>
<li><strong>Place names</strong>: GeoNames, licensed CC BY 4.0.</li>
<li><strong>Map tiles</strong>: OpenFreeMap, built on OpenMapTiles and OpenStreetMap data.</li>
<li><strong>Creature entries</strong> are written by us from published accounts. Each links to further reading.</li>
</ul>
<h2>Our stance</h2>
<p>We collect reports and evidence and let you decide. A report on this site means someone said they saw something, not that it's proven.</p>
</div></div>''', 'Who runs Encounter Atlas, how to reach Mike, and the sources behind the site.', head_extra=_head(ctx)))

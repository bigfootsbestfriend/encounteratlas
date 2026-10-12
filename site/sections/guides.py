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
import json, os, re

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

    for g in guides:
        body_html = render(g['_src'], g['slug'])
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
      <p class="g-meta"><span class="g-chip">{g['_mins']} min read</span>{printable}<span class="g-chip">Updated {ctx.esc(g.get('updated', 'October 2026'))}</span></p>
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
        ctx.write(path, ctx.page(path, g['seo'], body, g['desc'], body_class='guide', head_extra=head))

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

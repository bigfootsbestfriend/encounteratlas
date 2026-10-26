"""Books: /books/, every verified book in data/media.json with its cover (Open Library) and an Amazon link.

The weekly email's book of the week links here (/books/#b-<isbn10>), never straight to Amazon: Amazon's Associates
rules don't allow affiliate links in emails, so the affiliate link lives on this page. The pick itself comes from
newsletter.week_book() so the email and this page always agree.
"""
import importlib.util, json, os

TAG = 'encountersatlas-20'
SPONSORED = 'rel="sponsored nofollow noopener" target="_blank"'
GROUPS = [('General reads', ['@general', '@us']), ('Bigfoot and hairy giants', ['@hominid', 'bigfoot', 'yeti', 'yowie', 'almas', 'yeren', 'skunk-ape', 'orang-pendek', 'fouke-monster', 'honey-island-swamp-monster', 'momo']),
          ('Dogmen and beasts', ['dogman', 'beast-of-bray-road', 'wolfman-of-defiance', 'shunka-warakin', 'chupacabra', 'beast-of-gevaudan', 'jersey-devil', 'nandi-bear', 'thylacine']),
          ('Lake and sea monsters', ['@lake', '@sea', 'loch-ness-monster', 'sea-serpent', 'kraken', 'ogopogo', 'champ', 'morag', 'cadborosaurus', 'mokele-mbembe', 'globster', 'stellers-sea-ape']),
          ('UFOs, aliens and visitors', ['@ufo', 'alien-abduction', 'grey-aliens', 'men-in-black', 'flatwoods-monster', 'ufo-saucer', 'ufo-tic-tac', 'ufo-triangle', 'ufo-crash', 'mystery-airships', 'mothman', 'indrid-cold']),
          ('Fairies, merfolk and folklore', ['@fae', 'fairies', 'pixies', 'leprechaun', 'selkie', 'merrow', 'kappa', 'ningyo', 'mermaid'])]


def cover(b, size='M'):
    return f'https://covers.openlibrary.org/b/isbn/{b["isbn10"]}-{size}.jpg'


def amazon(b):
    return f'https://www.amazon.com/dp/{b["isbn10"]}?tag={TAG}'


def build(ctx):
    E, U = ctx.esc, ctx.url
    p = os.path.join(ctx.ROOT, 'data', 'media.json')
    if not os.path.exists(p):
        return
    books = [b for b in json.load(open(p, encoding='utf-8'))['books'] if b.get('isbn10')]
    spec = importlib.util.spec_from_file_location('nl_sec', os.path.join(ctx.ROOT, 'site', 'sections', 'newsletter.py'))
    nl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nl)
    wk, why = nl.week_book(ctx)

    def card(b, big=False):
        tags = [ctx.by_slug[t]['name'] for t in b['for'] if t in ctx.by_slug][:3]
        return (f'<article class="bk-card{" bk-big" if big else ""}" id="{"" if big else "b-" + b["isbn10"]}">'
                + (f'<a href="{amazon(b)}" {SPONSORED} class="bk-cover"><img src="{cover(b, "L" if big else "M")}" alt="Cover of {E(b["title"])}" loading="lazy" width="{150 if big else 96}" height="{225 if big else 144}"></a>'
                 if b.get('cover') else f'<a href="{amazon(b)}" {SPONSORED} class="bk-cover bk-nocover tone-{sum(map(ord, b["isbn10"])) % 5}" aria-hidden="true" tabindex="-1"><span>{E(b["title"][:60])}</span></a>')
                + f'<div class="bk-txt">{"<p class=bk-kick>Book of the week</p>" if big else ""}<h3>{E(b["title"])}</h3><p class="bk-by">{E(b["author"])}{(" · " + str(b["year"])) if b.get("year") else ""}</p>'
                + (f'<p class="bk-why">{E(why)}</p>' if big else '')
                + (f'<p class="bk-tags">{E(", ".join(tags))}</p>' if tags else '')
                + f'<a class="btn btn-sm" href="{amazon(b)}" {SPONSORED}>Find it on Amazon</a></div></article>')

    seen, secs = set(), ''
    for title, tags in GROUPS:
        group = [b for b in books if b['isbn10'] not in seen and any(t in b['for'] for t in tags)]
        seen.update(b['isbn10'] for b in group)
        if group:
            secs += f'<section class="bk-sec"><h2>{E(title)}</h2><div class="bk-grid">{"".join(card(b) for b in group)}</div></section>'
    rest = [b for b in books if b['isbn10'] not in seen]
    if rest:
        secs += f'<section class="bk-sec"><h2>More strange reads</h2><div class="bk-grid">{"".join(card(b) for b in rest)}</div></section>'
    body = f'''
<section class="band band-dark"><div class="wrap">
  <p class="crumb"><a href="{U('/gear/')}">Gear</a> / Books</p>
  <h1>Books about cryptids, UFOs and the unexplained</h1>
  <p class="lede">{len(books)} books we've checked exist and are worth a look, sceptical and believing, from Bigfoot field guides to the UFO files. Each week the email picks one. Rather listen? Here are the <a href="{U('/podcasts/cryptids/')}">best cryptid podcasts</a>, ranked every week.</p>
  <p class="gr-aff"><a class="md-aff" href="{U('/privacy/')}#affiliate">As an Amazon Associate we earn from qualifying purchases.</a></p>
</div></section>
<div class="band band-mist"><div class="wrap">
  {card(wk, True) if wk else ''}
  {secs}
  <p class="small">Covers from Open Library. Prices and editions vary by country; Amazon sends you to your local store where it can.</p>
</div></div>'''
    ctx.write('/books/', ctx.page('/books/', 'Books about cryptids, UFOs and the unexplained', body,
                                  f'{len(books)} books on Bigfoot, lake monsters, UFOs, aliens and fairies, plus the Encounter Atlas book of the week.',
                                  head_extra=f'<link rel="stylesheet" href="{U("/static/books.css")}">'))

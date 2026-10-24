"""Shared bits for pages built to be cited (official releases, hearings): archived copies of every official link
(data/source_archive.json, refreshed by tools/archive_links.py) and an "About this list / cite this page" box.
Files starting with _ are not run as sections; import with sys.path as on_record.py and ufo_archive.py do.
"""
import datetime, json, os

_DATA = None
MON = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def data(root):
    global _DATA
    if _DATA is None:
        p = os.path.join(root, 'data', 'source_archive.json')
        _DATA = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'checked': '', 'links': {}}
    return _DATA


def nice_date(d):
    y, m, dd = d.split('-')
    return f'{int(dd)} {MON[int(m)]} {y}'


def archived(root, url):
    return (data(root)['links'].get(url) or {}).get('archive')


def arch_link(ctx, url):
    """' · Archived copy' after an official link, when the Internet Archive has a working capture."""
    a = archived(ctx.ROOT, url)
    return (f' <a class="src-arch" href="{ctx.esc(a)}" rel="noopener" title="Saved copy at the Internet Archive, in case the official page moves">'
            f'Archived copy</a>') if a else ''


def about_box(ctx, path, title, method):
    """How the list was built, when the links were last checked, how to report errors, and a ready-made citation."""
    e = ctx.esc
    checked = data(ctx.ROOT).get('checked') or datetime.date.today().isoformat()
    cite = (f'Johnston, Mike. "{title}." Encounter Atlas. Links checked {nice_date(checked)}. '
            f'{ctx.SITE_URL}{path}')
    return f'''<aside class="src-about" id="about-this-list">
  <h2>About this list</h2>
  {method}
  <p><b>Links last checked:</b> <time datetime="{checked}">{nice_date(checked)}</time>. Some government sites block automatic checks, so every official link also has an archived copy from the Internet Archive where one exists.</p>
  <p><b>Spotted a mistake or a dead link?</b> Email <a href="mailto:hello@encounteratlas.com">hello@encounteratlas.com</a> and we will fix it.</p>
  <div class="src-cite"><h3>Cite this page</h3><p id="src-cite-text">{e(cite)}</p>
  <button type="button" class="btn btn-ghost-l btn-sm" onclick="navigator.clipboard&&navigator.clipboard.writeText(document.getElementById('src-cite-text').textContent).then(()=>{{this.textContent='Copied'}})">Copy citation</button></div>
</aside>'''

"""Open data (/datasets/, 2026-10-25): free downloads of the tables we've cleaned up, so researchers, data journalists
and dataset lists (awesome-public-datasets, Kaggle, Hugging Face, Zenodo, Google Dataset Search) can use and cite them.

Only public records and our own compilations go here, never reader reports. Files are rebuilt every deploy into
/datasets/files/. data/dataset_mirrors.json holds the Hugging Face / Kaggle / Zenodo links once each copy is live
(tools/publish_datasets.py uploads them); a mirror is only shown after it exists.
"""
import csv, io, json, os

FILES = '/datasets/files/'
LICENCE = 'https://creativecommons.org/licenses/by/4.0/'

BB_COLS = [('nara_id', 'National Archives catalog ID of the case file (naId)'),
           ('title', 'Folder title as typed on the file: place, state or country, month and year'),
           ('place', 'Place part of the title'),
           ('country_code', 'ISO 3166-1 alpha-2 country we matched the place to (blank if unknown)'),
           ('admin1', 'State or province code we matched (GeoNames admin1, blank if unknown)'),
           ('year', 'Year from the title'),
           ('month', 'Month number from the title (blank if the title has none)'),
           ('lat', 'Latitude of the matched place (WGS84)'),
           ('lon', 'Longitude of the matched place (WGS84)'),
           ('location_precision', 'place = town matched, region = state/province centre, country = country centre, coords = coordinates in the title, none = not mapped'),
           ('pages', 'Number of scanned pages in the file'),
           ('nara_url', 'The file in the National Archives catalog'),
           ('first_page_image', 'First scanned page, hosted by the National Archives')]
PROG_COLS = [('slug', 'Our ID'), ('name', 'Programme name'), ('aka', 'Other names'), ('country', 'Country code (lowercase ISO alpha-2)'),
             ('agency', 'Agency that ran it'), ('start', 'Start year'), ('end', 'End year (blank if active or unknown)'),
             ('status', 'active, closed or unclear'), ('did', 'What it did, in our words'), ('found', 'What it concluded, in our words'),
             ('sources', 'Official and press sources, "name <url>" separated by " | "')]


def _csv(cols, rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    w.writerow([c for c, _ in cols])
    for r in rows:
        w.writerow(['' if r.get(c) is None else r.get(c) for c, _ in cols])
    return out.getvalue()


def build(ctx):
    U, E = ctx.url, ctx.esc
    root = ctx.ROOT
    def load(name, default):
        p = os.path.join(root, 'data', name)
        return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default
    mirrors = load('dataset_mirrors.json', {})

    bb = [{'nara_id': x['id'], 'title': x['title'], 'place': x['place'], 'country_code': x.get('cc') or '', 'admin1': x.get('a1') or '',
           'year': x.get('year'), 'month': x.get('month'), 'lat': x.get('lat'), 'lon': x.get('lon'), 'location_precision': x.get('precision'),
           'pages': x.get('pages'), 'nara_url': f'https://catalog.archives.gov/id/{x["id"]}', 'first_page_image': x.get('img') or ''}
          for x in sorted(ctx.bluebook, key=lambda x: (x.get('year') or 0, x.get('month') or 0, x['id']))]
    progs = [dict(p, sources=' | '.join(f'{s["name"]} <{s["url"]}>' for s in p.get('sources', []))) for p in load('ufo_programs.json', [])]
    rel = [{k: r.get(k) for k in ('slug', 'title', 'country', 'agency', 'date', 'period', 'type', 'summary', 'url', 'links')}
           for r in load('ufo_releases.json', [])]
    ctx.write(FILES + 'project-blue-book-case-files.csv', _csv(BB_COLS, bb))
    ctx.write(FILES + 'project-blue-book-case-files.json', json.dumps(bb, ensure_ascii=False))
    ctx.write(FILES + 'government-ufo-programmes.csv', _csv(PROG_COLS, progs))
    ctx.write(FILES + 'government-ufo-programmes.json', json.dumps(load('ufo_programs.json', []), ensure_ascii=False, indent=1))
    ctx.write(FILES + 'official-ufo-releases.json', json.dumps(rel, ensure_ascii=False, indent=1))

    years = [x['year'] for x in bb if x['year']]
    mapped = sum(1 for x in bb if x['lat'] is not None)
    sets = [
        {'key': 'bluebook', 'name': 'Project Blue Book case files, geocoded',
         'desc': (f'All {len(bb):,} case files in the US National Archives\' "Sanitized Version of Project Blue Book Case Files" (series 597821), '
                  f'with the place, month and year pulled out of each folder title and {mapped:,} of them matched to map coordinates. '
                  'Each row links to the file and its first scanned page at the National Archives.'),
         'page': '/ufo/blue-book/', 'cols': BB_COLS, 'files': ['project-blue-book-case-files.csv', 'project-blue-book-case-files.json'],
         'temporal': f'{min(years)}/{max(years)}', 'keywords': ['UFO', 'Project Blue Book', 'US Air Force', 'National Archives', 'UAP', 'geocoded'],
         'source': 'US National Archives, Record Group 341, series 597821 (US federal record, public domain). Places matched with GeoNames (CC BY 4.0).'},
        {'key': 'programmes', 'name': 'Government UFO programmes worldwide',
         'desc': (f'{len(progs)} official UFO and UAP investigation programmes from {len({p["country"] for p in progs})} countries, 1946 to today: '
                  'who ran each one, when, what it did and what it concluded, with official sources.'),
         'page': '/ufo/programs/', 'cols': PROG_COLS, 'files': ['government-ufo-programmes.csv', 'government-ufo-programmes.json'],
         'temporal': '1946/..', 'keywords': ['UFO', 'UAP', 'government', 'AARO', 'GEIPAN', 'investigations'],
         'source': 'Compiled by Encounter Atlas from government publications; every row lists its sources.'},
        {'key': 'releases', 'name': 'Official UFO file releases',
         'desc': f'{len(rel)} government releases of UFO and UAP records from {len({r["country"] for r in rel})} countries, with dates, agencies, what was released and links to the originals.',
         'page': '/ufo/releases/', 'cols': None, 'files': ['official-ufo-releases.json'],
         'temporal': None, 'keywords': ['UFO', 'UAP', 'declassified', 'government records'],
         'source': 'Compiled by Encounter Atlas; each entry links to the publishing government.'},
    ]

    ld, cards = [], []
    for s in sets:
        m = mirrors.get(s['key'], {})
        dist = [{'@type': 'DataDownload', 'encodingFormat': 'text/csv' if f.endswith('.csv') else 'application/json',
                 'contentUrl': ctx.SITE_URL + FILES + f} for f in s['files']]
        d = {'@context': 'https://schema.org', '@type': 'Dataset', 'name': s['name'], 'description': s['desc'],
             'url': f'{ctx.SITE_URL}/datasets/#{s["key"]}', 'license': LICENCE, 'isAccessibleForFree': True, 'keywords': s['keywords'],
             'creator': {'@type': 'Organization', 'name': 'Encounter Atlas', 'url': ctx.SITE_URL + '/'}, 'distribution': dist,
             'sameAs': [v for k, v in m.items() if k in ('huggingface', 'kaggle', 'zenodo')]}
        if s['temporal']:
            d['temporalCoverage'] = s['temporal']
        if m.get('doi'):
            d['identifier'] = 'https://doi.org/' + m['doi']
        ld.append(d)
        dl = ''.join(f'<a class="btn{"" if i == 0 else " btn-ghost"}" href="{U(FILES + f)}" download>{f.rsplit(".", 1)[1].upper()}</a>' for i, f in enumerate(s['files']))
        also = ' · '.join(f'<a href="{E(m[k])}">{n}</a>' for k, n in (('huggingface', 'Hugging Face'), ('kaggle', 'Kaggle'), ('zenodo', 'Zenodo')) if m.get(k))
        cols = ('<details><summary>Columns</summary><dl class="ds-cols">' + ''.join(f'<dt><code>{c}</code></dt><dd>{E(t)}</dd>' for c, t in s['cols']) + '</dl></details>') if s['cols'] else ''
        cards.append(f'''<section class="ds-card" id="{s["key"]}"><h2>{E(s["name"])}</h2><p>{E(s["desc"])}</p>
<p class="ds-dl">{dl} <a href="{U(s["page"])}">See it on the site</a></p>
{f'<p class="small">Also on {also}.{" DOI: <a href=" + chr(34) + "https://doi.org/" + E(m["doi"]) + chr(34) + ">" + E(m["doi"]) + "</a>" if m.get("doi") else ""}</p>' if also else ''}
<p class="small"><b>Source:</b> {E(s["source"])}</p>{cols}</section>''')

    body = f'''
<section class="band band-dark"><div class="wrap"><p class="crumb"><a href="{U('/press/')}">Press and researchers</a> / Open data</p>
<h1>Open data: UFO files you can download</h1>
<p class="lede">The tables behind our maps and timelines, free to download, analyse and republish. CSV and JSON, rebuilt every time the site updates.</p></div></section>
<div class="band band-mist"><div class="wrap"><div class="prose">
{''.join(cards)}
<h2>Licence and credit</h2>
<p>Our cleaning, matching and write-ups are free to use under <a href="{LICENCE}" rel="license noopener">CC BY 4.0</a>. Credit "Encounter Atlas (encounteratlas.com)" and link this page. The underlying US government records are public domain.</p>
<p class="press-cite">Encounter Atlas. "Dataset name." Encounter Atlas open data, accessed (date). https://encounteratlas.com/datasets/</p>
<h2>What's not here</h2>
<p>Reader reports stay on the site only. People send them to us, not to the public domain, and we blur their locations on purpose.</p>
<p>Found a mistake or a better match for a place? <a href="{U('/contact/?about=data')}">Tell us</a> and we'll fix it for everyone.</p>
</div></div></div>'''
    head = ('<style>.ds-card{background:var(--paper,#fff);border-radius:14px;padding:18px 20px;margin:0 0 22px;box-shadow:0 1px 3px rgba(0,0,0,.08)}'
            '.ds-card h2{margin-top:0}.ds-card .btn-ghost{color:#13261F;border-color:#13261F}.ds-dl{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.ds-cols dt{margin-top:8px}.ds-cols dd{margin:2px 0 0 0}'
            '.press-cite{font-family:ui-monospace,monospace;font-size:.9em;background:rgba(0,0,0,.05);padding:10px 12px;border-radius:8px;overflow-wrap:anywhere}</style>')
    ctx.write('/datasets/', ctx.page('/datasets/', 'Open data: UFO files you can download', body,
                                     'Free CSV and JSON downloads: every Project Blue Book case file geocoded, government UFO programmes worldwide, and official UFO file releases.',
                                     head_extra=head, ld=ld))

#!/usr/bin/env python3
"""Mirror the /datasets/ files to Hugging Face, Kaggle and Zenodo (2026-10-25).

Each mirror carries a data card that credits and links encounteratlas.com/datasets/. Files are taken from the LIVE site,
so run this only after a deploy. Links to each copy go in data/dataset_mirrors.json (commit it so /datasets/ shows them).

  ~/.local/share/ea-data-venv/bin/python tools/publish_datasets.py [hf] [kaggle] [zenodo] [--refresh]

hf/kaggle: create on first run, new version on later runs (--refresh is the nightly path: re-upload only when the
file changed). zenodo: one published record per dataset (DOI); later runs make a new version only when the CSV
changed, since every Zenodo version is permanent.
Keys: ~/.config/kitchen-magpie/huggingface.env, kaggle.env, zenodo.env.
"""
import hashlib, json, os, sys, tempfile, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
MIRRORS = os.path.join(ROOT, 'data', 'dataset_mirrors.json')
SITE = 'https://encounteratlas.com'
CFG = os.path.expanduser('~/.config/kitchen-magpie/')


def env(name, key):
    return dict(l.strip().split('=', 1) for l in open(CFG + name) if '=' in l)[key]


SETS = {
    'bluebook': {
        'slug': 'project-blue-book-case-files', 'title': 'Project Blue Book UFO Case Files (Geocoded)',
        'subtitle': 'All 10,622 US Air Force Blue Book case files from the National Archives, with places mapped',
        'files': ['project-blue-book-case-files.csv', 'project-blue-book-case-files.json'],
        'tags': ['ufo', 'uap', 'project-blue-book', 'us-air-force', 'national-archives', 'geospatial', 'history'],
        'about': """Project Blue Book was the US Air Force's study of UFO reports from 1952 to 1969 (following Projects Sign and Grudge).
The US National Archives holds its case files as the series "Sanitized Version of Project Blue Book Case Files" (naId 597821),
but the catalog only gives each file a typed folder title such as "Fort Worth, Texas, July 1952".

This table turns those titles into data: place, state or country, year and month, matched to coordinates with GeoNames.
Every row links to the file in the National Archives catalog and to its first scanned page.""",
        'notes': """- One row per case FILE in the National Archives series, not per sighting. The Air Force's own total of 12,618 sightings
  counts differently (some files hold several reports, some reports have no file in this series).
- `location_precision` says how good the map point is: `place` (town matched), `coords` (coordinates in the title),
  `region` (state or province centre), `country` (country centre) or `none` (not mapped). Use `place`/`coords` for maps.
- A few folder titles are blank or illegible in the original ([BLANK], [ILLEGIBLE]); they're kept as typed.
- Years outside 1947 to 1969 are older reports the Air Force filed with Blue Book.""",
        'source': 'US National Archives, Record Group 341 (Records of Headquarters US Air Force), series 597821. US federal records, public domain. Place matching uses GeoNames (CC BY 4.0).',
        'page': '/ufo/blue-book/', 'kaggle_subtitle': 'All 10,622 USAF Blue Book case files from the US National Archives, mapped', 'kaggle_keywords': ['history', 'geospatial analysis', 'aviation', 'government']},
    'programmes': {
        'slug': 'government-ufo-programmes', 'title': 'Government UFO Programmes Worldwide',
        'subtitle': 'Official UFO and UAP investigation programmes in 18 countries since 1946, with sources',
        'files': ['government-ufo-programmes.csv', 'government-ufo-programmes.json'],
        'tags': ['ufo', 'uap', 'government', 'history', 'aaro', 'geipan'],
        'about': """Every official UFO/UAP investigation programme we could source: who ran it, start and end years, status, what it did and
what it concluded, with links to the government publications. From Project Sign (1948) to AARO and France's GEIPAN.""",
        'notes': """- `did` and `found` are short summaries in our own words; follow `sources` for the originals.
- `end` is blank for programmes still running or whose end is not documented (`status` = active or unclear).""",
        'source': 'Compiled by Encounter Atlas from government publications; each row lists its sources.',
        'page': '/ufo/programs/', 'kaggle_subtitle': 'Official UFO/UAP investigation programmes in 18 countries, 1946 to today', 'kaggle_keywords': ['history', 'government']},
}


def card(key, s, fmt):
    url = f'{SITE}/datasets/#{key}'
    body = f"""# {s['title']}

{s['subtitle']}.

**Home page, documentation and the always-current copy: [encounteratlas.com/datasets]({url})**
See the data on a map: [{SITE}{s['page']}]({SITE}{s['page']})

## About

{s['about']}

## Notes

{s['notes']}

## Source and licence

{s['source']}

Our cleaning, matching and summaries are released under CC BY 4.0. Please credit **Encounter Atlas (encounteratlas.com)**
and link {SITE}/datasets/.

```
Encounter Atlas. "{s['title']}." Encounter Atlas open data. {SITE}/datasets/
```

Corrections and better place matches are welcome: {SITE}/contact/?about=data
"""
    if fmt == 'hf':
        return ('---\nlicense: cc-by-4.0\nlanguage:\n- en\npretty_name: ' + json.dumps(s['title']) + '\ntags:\n'
                + ''.join(f'- {t}\n' for t in s['tags']) + 'size_categories:\n- ' + ('10K<n<100K' if key == 'bluebook' else 'n<1K')
                + f'\nconfigs:\n- config_name: default\n  data_files: {s["files"][0]}\n---\n\n' + body)
    return body


def fetch(tmp, s):
    for f in s['files']:
        with urllib.request.urlopen(urllib.request.Request(f'{SITE}/datasets/files/{f}', headers={'User-Agent': 'ea-datasets/1.0'}), timeout=120) as r:
            open(os.path.join(tmp, f), 'wb').write(r.read())
    return hashlib.sha256(open(os.path.join(tmp, s['files'][0]), 'rb').read()).hexdigest()


def hf(key, s, tmp, m):
    from huggingface_hub import HfApi
    api = HfApi(token=env('huggingface.env', 'HF_TOKEN'))
    repo = f'encounteratlas/{s["slug"]}'
    api.create_repo(repo, repo_type='dataset', exist_ok=True)
    open(os.path.join(tmp, 'README.md'), 'w').write(card(key, s, 'hf'))
    api.upload_folder(repo_id=repo, repo_type='dataset', folder_path=tmp, allow_patterns=s['files'] + ['README.md'],
                      commit_message='Update from encounteratlas.com/datasets/')
    m['huggingface'] = f'https://huggingface.co/datasets/{repo}'


def kaggle(key, s, tmp, m):
    os.environ['KAGGLE_API_TOKEN'] = env('kaggle.env', 'KAGGLE_API_TOKEN')
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    ref = f'encounteratlas/{s["slug"]}'
    meta = {'title': s['title'][:50], 'subtitle': s['kaggle_subtitle'],
            'id': ref, 'licenses': [{'name': 'CC-BY-4.0'}], 'keywords': s['kaggle_keywords'],
            'description': card(key, s, 'kaggle')}
    json.dump(meta, open(os.path.join(tmp, 'dataset-metadata.json'), 'w'))
    exists = any(d.ref == ref for d in api.dataset_list(user='encounteratlas'))
    if exists:
        api.dataset_create_version(tmp, 'Update from encounteratlas.com/datasets/', quiet=True, dir_mode='skip')
    else:
        api.dataset_create_new(tmp, public=True, quiet=True, dir_mode='skip')
    m['kaggle'] = f'https://www.kaggle.com/datasets/{ref}'


def zenodo(key, s, tmp, m, digest):
    tok = env('zenodo.env', 'ZENODO_TOKEN')
    api = 'https://zenodo.org/api/deposit/depositions'
    def call(url, data=None, method=None, ctype='application/json'):
        req = urllib.request.Request(url + ('&' if '?' in url else '?') + 'access_token=' + tok, data, {'Content-Type': ctype}, method=method)
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r) if r.status != 204 else None
    if m.get('zenodo_sha') == digest:
        return
    if m.get('zenodo_id'):   # new version of the existing record
        d = call(f'{api}/{m["zenodo_id"]}/actions/newversion', b'', 'POST')
        d = call(d['links']['latest_draft'])
        for f in d.get('files', []):
            call(f'{api}/{d["id"]}/files/{f["id"]}', method='DELETE')
    else:
        d = call(api, b'{}', 'POST')
    for f in s['files']:
        call(f'{d["links"]["bucket"]}/{f}', open(os.path.join(tmp, f), 'rb').read(), 'PUT', 'application/octet-stream')
    import datetime
    meta = {'metadata': {'title': s['title'], 'upload_type': 'dataset', 'description': card(key, s, 'zenodo').replace('\n\n', '<br><br>'),
                         'creators': [{'name': 'Johnston, Mike', 'affiliation': 'Encounter Atlas'}], 'access_right': 'open',
                         'license': 'cc-by-4.0', 'keywords': s['tags'], 'publication_date': datetime.date.today().isoformat(),
                         'related_identifiers': [{'identifier': f'{SITE}/datasets/', 'relation': 'isSupplementTo', 'resource_type': 'dataset'}]}}
    call(f'{api}/{d["id"]}', json.dumps(meta).encode(), 'PUT')
    pub = call(f'{api}/{d["id"]}/actions/publish', b'', 'POST')
    m.update({'zenodo_id': m.get('zenodo_id') or pub['id'], 'zenodo': pub['links']['html'] if 'html' in pub['links'] else f'https://zenodo.org/records/{pub["id"]}',
              'doi': pub.get('conceptdoi') or pub['doi'], 'zenodo_sha': digest})


def main():
    want = [a for a in sys.argv[1:] if not a.startswith('--')] or ['hf', 'kaggle', 'zenodo']
    refresh = '--refresh' in sys.argv
    mirrors = json.load(open(MIRRORS)) if os.path.exists(MIRRORS) else {}
    for key, s in SETS.items():
        m = mirrors.setdefault(key, {})
        with tempfile.TemporaryDirectory() as tmp:
            digest = fetch(tmp, s)
            changed = m.get('sha') != digest
            for target in want:
                if refresh and not changed and target != 'zenodo':
                    continue
                if target == 'hf':
                    hf(key, s, tmp, m)
                elif target == 'kaggle':
                    kaggle(key, s, tmp, m)
                elif target == 'zenodo':
                    zenodo(key, s, tmp, m, digest)
                print(f'{key}: {target} ok', file=sys.stderr)
            m['sha'] = digest
    json.dump(mirrors, open(MIRRORS, 'w'), indent=2)
    open(MIRRORS, 'a').write('\n')


if __name__ == '__main__':
    main()

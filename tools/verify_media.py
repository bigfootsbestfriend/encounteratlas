"""Verify the books and documentaries in data/media_candidates.json before they go on the site.

Books: Open Library search (title + author surname). Kept only when the title matches and the author is listed, and an
ISBN-10 is found (Amazon's /dp/<ISBN-10> page for a print book). Documentaries: the Wikipedia article must exist and
describe a film or series. Writes data/media.json; prints what was dropped so nothing invented slips through.
  python3 tools/verify_media.py
"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
UA = {'User-Agent': 'EncounterAtlas/1.0 (+https://encounteratlas.com; hello@encounteratlas.com)'}


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s)).strip()


def book(b):
    main_t = re.split(r'[:?!]', b['t'])[0].strip()
    q = urllib.parse.urlencode({'title': main_t, 'author': b['a'], 'fields': 'title,subtitle,author_name,isbn,first_publish_year,key,language',
                                'limit': 10})
    d = get('https://openlibrary.org/search.json?' + q)
    if not d:
        return None, 'no response'
    want = norm(main_t)
    for doc in d.get('docs', []):
        full = norm(doc.get('title', '') + ' ' + (doc.get('subtitle') or ''))
        if not (full.startswith(want) or want.startswith(norm(doc.get('title', '')))):
            continue
        if not any(norm(b['a']) in norm(a) for a in doc.get('author_name', [])):
            continue
        isbn10 = [i for i in doc.get('isbn', []) if len(i) == 10 and i[0] in '01']  # English-language groups
        if not isbn10:
            continue
        # Prefer the ISBN-10 Amazon most likely lists: newest-looking numbers are not knowable here, so take the
        # most common prefix group and the first one (Open Library lists editions roughly by popularity).
        return {'title': doc['title'] + (': ' + doc['subtitle'] if doc.get('subtitle') and ':' not in b['t'] else ''),
                'author': ', '.join(a for a in doc['author_name'][:2] if '(' not in a), 'year': doc.get('first_publish_year'),
                'isbn10': isbn10[0], 'ol': 'https://openlibrary.org' + doc['key']}, None
    return None, f'no match ({len(d.get("docs", []))} results)'


def doc(x):
    d = get('https://en.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(x['wiki'].replace(' ', '_')))
    if not d or d.get('type') != 'standard':
        return None, 'no article'
    text = (d.get('description') or '') + ' ' + (d.get('extract') or '')[:400]
    if not re.search(r'documentar|docuseries|docudrama|television series|reality|film', text, re.I):
        return None, 'not a film or series: ' + (d.get('description') or '')
    return {'title': x['t'], 'year': x['y'], 'wiki': d['content_urls']['desktop']['page'], 'blurb': (d.get('description') or '')}, None


def main():
    c = json.load(open(os.path.join(ROOT, 'data', 'media_candidates.json'), encoding='utf-8'))
    out, dropped = {'books': [], 'docs': []}, []
    for b in c['books']:
        r, why = book(b)
        if r:
            out['books'].append({**r, 'for': b['for']})
        else:
            dropped.append(('book', b['t'], b['a'], why))
        time.sleep(0.4)
    for x in c['docs']:
        r, why = doc(x)
        if r:
            out['docs'].append({**r, 'for': x['for']})
        else:
            dropped.append(('doc', x['t'], x['wiki'], why))
        time.sleep(0.2)
    json.dump(out, open(os.path.join(ROOT, 'data', 'media.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'kept {len(out["books"])} books, {len(out["docs"])} documentaries', file=sys.stderr)
    for d in dropped:
        print('DROPPED', *d, file=sys.stderr)


if __name__ == '__main__':
    main()

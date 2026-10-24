"""Archived copies for every official source link on the releases, hearings and programmes pages (data/source_archive.json).

For each URL: the latest Internet Archive capture that returned 200, plus today's live status. Government sites
(aaro.mil, senate.gov, defense.gov...) block scripts with 403, so a 403 here is normal; the archive capture shows the
page works for readers. The pages show "Archived copy" next to each official link, so citations survive link rot.
Run: python3 tools/archive_links.py   (several minutes; Wayback rate-limits, so it paces itself; reuses captures already found unless --refresh)
"""
import datetime, json, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'source_archive.json')
UA = {'User-Agent': 'EncounterAtlas link checker (hello@encounteratlas.com)'}
BROWSER = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36'}


def source_urls():
    urls = []
    for r in json.load(open(os.path.join(ROOT, 'data', 'ufo_releases.json'))):
        urls += [r['url']] + [l['url'] for l in r.get('links', [])]
    for h in json.load(open(os.path.join(ROOT, 'data', 'on_the_record.json')))['hearings']:
        urls += [l['url'] for l in h.get('links', [])]
    for g in json.load(open(os.path.join(ROOT, 'data', 'ufo_programs.json'))):
        urls += [s['url'] for s in g['sources']]
    return [u for u in dict.fromkeys(urls) if not u.startswith('https://web.archive.org/')]


def seeded():
    """Captures researchers already confirmed by hand (the "archive" field in ufo_programs.json sources)."""
    return {s['url']: s['archive'] for g in json.load(open(os.path.join(ROOT, 'data', 'ufo_programs.json')))
            for s in g['sources'] if s.get('archive')}


def live(u):
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=BROWSER), timeout=30).status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def capture(u):
    q = 'https://web.archive.org/cdx/search/cdx?' + urllib.parse.urlencode(
        {'url': u, 'output': 'json', 'filter': 'statuscode:200', 'limit': '-1', 'fl': 'timestamp,original'})
    for _ in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=60))
            return f'https://web.archive.org/web/{d[-1][0]}/{d[-1][1]}' if len(d) > 1 else None
        except Exception:
            time.sleep(8)
    return False  # archive unreachable: keep what we had


if __name__ == '__main__':
    old = json.load(open(OUT)) if os.path.exists(OUT) else {'links': {}}
    refresh = '--refresh' in sys.argv
    links = {}
    for u in source_urls():
        prev = old['links'].get(u) or ({'archive': seeded()[u]} if u in seeded() else {})
        a = prev.get('archive') if prev.get('archive') and not refresh else capture(u)
        if a is False:
            a = prev.get('archive')
        links[u] = {'status': live(u), 'archive': a}
        print(links[u]['status'], 'ARCH' if a else 'none', u[:100], flush=True)
        time.sleep(1.5 if prev.get('archive') else 8)
    json.dump({'checked': datetime.date.today().isoformat(), 'links': links}, open(OUT, 'w'), indent=1)
    print(sum(1 for v in links.values() if v['archive']), 'of', len(links), 'archived')

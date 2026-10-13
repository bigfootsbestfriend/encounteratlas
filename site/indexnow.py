#!/usr/bin/env python3
"""Tell IndexNow (Bing, Yandex and others) about pages that changed in this build.

  indexnow.py diff   compare each sitemap page in _site with the live copy; print the URLs that differ (new pages too)
  indexnow.py ping   read URLs on stdin and submit them, 10,000 per request

The deploy workflow runs `diff` in the build job (the live site is still the old version) and `ping` after the deploy succeeds.
Both do nothing on a BASE_PATH preview build or before launch. The key comes from INDEXNOW_KEY in site/build.py,
which also writes /<key>.txt.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / '_site'
SRC = (HERE / 'build.py').read_text()
KEY = re.search(r"^INDEXNOW_KEY = '([0-9a-f]+)'", SRC, re.M).group(1)
LAUNCHED = re.search(r'^LAUNCHED = True', SRC, re.M) is not None
SITE_URL = os.environ.get('SITE_URL', 'https://encounteratlas.com').rstrip('/')
ACTIVE = LAUNCHED and not os.environ.get('BASE_PATH', '').strip('/')
UA = {'User-Agent': 'encounteratlas-indexnow/1.0'}
BATCH = 10000


def norm(html):
    # Ignore cache-busting query strings on static assets, which can change between builds.
    return hashlib.sha1(re.sub(r'\?v=[0-9A-Za-z]+', '', html).encode()).hexdigest()


def changed(u):
    local = OUT / u[len(SITE_URL):].lstrip('/') / 'index.html'
    if not local.exists():
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20) as r:
            live = r.read().decode('utf-8', 'replace')
    except Exception:
        live = ''  # new page (404) or a fetch error: report it
    return u if norm(live) != norm(local.read_text()) else None


def diff():
    if not ACTIVE:
        return
    urls = re.findall(r'<loc>([^<]+)</loc>', (OUT / 'sitemap.xml').read_text())
    with ThreadPoolExecutor(12) as pool:
        for u in pool.map(changed, urls):
            if u:
                print(u)


def ping():
    urls = list(dict.fromkeys(l.strip() for l in sys.stdin if l.strip().startswith(SITE_URL + '/')))
    if not urls or not ACTIVE:
        print('IndexNow: nothing to submit')
        return
    host = SITE_URL.split('//', 1)[1]
    for i in range(0, len(urls), BATCH):
        part = urls[i:i + BATCH]
        body = json.dumps({'host': host, 'key': KEY, 'keyLocation': f'{SITE_URL}/{KEY}.txt', 'urlList': part}).encode()
        req = urllib.request.Request('https://api.indexnow.org/indexnow', data=body,
                                     headers={'Content-Type': 'application/json; charset=utf-8', **UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f'IndexNow {r.status}: {len(part)} URLs')


if __name__ == '__main__':
    {'diff': diff, 'ping': ping}[sys.argv[1]]()

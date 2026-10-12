"""PURSUE (Presidential Unsealing and Reporting System for UAP Encounters) -> data/ufo_cases_pursue.json.

Since May 8, 2026 the US Department of War has posted declassified UAP records at https://www.war.gov/ufo/
in tranches. The page is driven by one CSV, /Portals/1/Interactive/2026/UFO/uap-data.csv, listing every
file with its release date, agency, incident date, incident location, description and download link.
US federal records, so public domain: we copy the listing and link every item to its war.gov or DVIDS file.

war.gov's CDN refuses scripted downloads (HTTP 403), so this script reads a copy saved from a browser:
open https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv in a browser and save it as
data/raw/pursue/uap-data.csv, then run this script. (Fetching it inside a headless Chromium page that
has first loaded war.gov/ufo/ also works.)
"""
import csv, json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ufo_geo  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'data', 'raw', 'pursue', 'uap-data.csv')
OUT = os.path.join(ROOT, 'data', 'ufo_cases_pursue.json')
KIND = {'PDF': 'document', 'VID': 'video', 'IMG': 'image', 'AUD': 'audio'}
MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                       'september', 'october', 'november', 'december'], 1)}


def us_date(s):
    """'9/18/26' -> '2026-09-18'; two-digit years up to 26 are 20xx, the rest 19xx."""
    m = re.match(r'^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$', s or '')
    if not m:
        return ''
    y = int(m.group(3))
    if y < 100:
        y += 2000 if y <= 26 else 1900
    return f'{y:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}'


def incident(s):
    """Returns (sortable date 'YYYY[-MM[-DD]]', label as published)."""
    s = (s or '').strip()
    if s in ('', 'N/A'):
        return '', ''
    d = us_date(s)
    if d:
        return d, s
    m = re.search(r'([A-Za-z]+),?\s+(\d{4})', s)
    if m and m.group(1).lower() in MONTHS:
        return f'{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}', s
    m = re.search(r'(1[89]\d\d|20\d\d)', s)
    return (m.group(1), s) if m else ('', s)


def link(row):
    kind = row['Type'].strip()
    vid = row['DVIDS Video ID'].strip()
    if kind == 'VID' and vid:
        return f'https://www.dvidshub.net/video/{vid}'
    if kind == 'AUD' and vid:
        return f'https://www.dvidshub.net/audio/{vid}'
    return row['PDF | Image Link'].strip() or 'https://www.war.gov/ufo/'


def main():
    if not os.path.exists(SRC):
        sys.exit(__doc__)
    rows = [r for r in csv.DictReader(open(SRC, encoding='utf-8-sig')) if r.get('Title', '').strip()]
    out, stats = [], Counter()
    for r in rows:
        when, when_label = incident(r['Incident Date'])
        loc = re.sub(r'\s+', ' ', r['Incident Location'].replace('\xa0', ' ')).strip()
        if loc == 'Georgia' and 'Tbilisi' in r['Title']:
            loc = 'Tbilisi, Georgia'  # the country, not the US state
        geo = ufo_geo.geocode(loc) if loc else None
        stats[geo[2] if geo else 'none'] += 1
        title = r['Title'].strip()
        m = re.match(r'^([A-Z]{2,5}-UAP-[A-Z]{0,3}\d+[A-Z]?),\s*(.*)$', title)
        out.append({
            'id': m.group(1) if m else title, 'title': m.group(2) if m else title,
            'kind': KIND.get(r['Type'].strip(), 'document'), 'agency': r['Agency'].strip(),
            'release': us_date(r['Release Date']), 'date': when, 'date_label': when_label, 'loc': loc if loc != 'N/A' else '',
            'desc': re.sub(r'\s+', ' ', r['Description Blurb']).strip(), 'url': link(r),
            'thumb': r['Modal Image'].strip(), 'alt': r['Image Alt Text'].strip(),
            'redacted': r['Redaction'].strip().upper() == 'TRUE', 'featured': r['Featured'].strip().upper() == 'YES',
            'lat': round(geo[0], 4) if geo else None, 'lon': round(geo[1], 4) if geo else None,
            'precision': geo[2] if geo else 'none', 'cc': geo[3] if geo else None, 'region': geo[4] if geo else '',
        })
    releases = sorted({o['release'] for o in out})
    for o in out:
        o['tranche'] = releases.index(o['release']) + 1
    out.sort(key=lambda o: (o['release'], o['id']))
    json.dump(out, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
    print(len(out), 'PURSUE records,', len(releases), 'tranches', dict(stats), file=sys.stderr)


if __name__ == '__main__':
    main()

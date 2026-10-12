"""Shared place matching for the UFO archive collectors (stdlib only).

Reuses the GeoNames tables that collector/bluebook.py loads (cities1000 plus the full US and Canada
files, CC BY 4.0). geocode() takes free text such as "Braymer, Missouri", "Detroit, MI",
"Budapest, Hungary", "Texas" or "Arabian Gulf" and returns (lat, lon, precision, cc, region).
Precision is 'place' (a town), 'region' (state or province centre), 'country' (country centre)
or 'area' (a sea or broad region placed by hand). None when the text names no place on Earth.
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bluebook  # noqa: E402  (same folder; only its helpers are used)

norm = bluebook.norm

# Broad areas named in the files. Points are rough centres, flagged 'area' so the map shows them as approximate.
AREAS = {
    'western united states': (39.5, -115.5, 'US'), 'westen united states': (39.5, -115.5, 'US'),
    'eastern united states': (37.5, -79.0, 'US'), 'northeastern united states': (42.5, -73.5, 'US'),
    'northeastern u s': (42.5, -73.5, 'US'), 'southeastern united states': (32.5, -84.0, 'US'),
    'southern united states': (32.0, -92.0, 'US'), 'midwestern united states': (41.5, -90.0, 'US'),
    'united states': (39.8, -98.6, 'US'), 'middle east': (29.5, 45.0, None), 'arabian gulf': (27.0, 51.5, None),
    'persian gulf': (27.0, 51.5, None), 'gulf of oman': (24.5, 58.5, None), 'strait of hormuz': (26.6, 56.3, None),
    'arabian sea': (15.0, 64.0, None), 'gulf of aden': (12.5, 47.5, None), 'aegean sea': (38.5, 25.0, None),
    'mediterranean sea': (35.0, 18.0, None), 'yellow sea': (35.5, 123.5, None), 'east china sea': (29.5, 125.5, None),
    'south china sea': (13.0, 114.0, None), 'pacific ocean': (22.0, -150.0, None), 'atlantic ocean': (30.0, -45.0, None),
    'north atlantic ocean': (45.0, -35.0, None), 'caribbean sea': (15.0, -75.0, None), 'gulf of america': (25.5, -90.0, None),
    'gulf of mexico': (25.5, -90.0, None), 'ussr': (55.75, 37.62, 'RU'),
}
OVERRIDES = {  # names the generic rules would get wrong
    'tbilisi georgia': (41.6941, 44.8337, 'GE', 'Georgia'),
    'washington virginia': (39.1157, -77.5636, 'US', 'Virginia'),  # FAA Washington Center sits in Leesburg
    'cockburn town turks and caicos islands': (21.4612, -71.1419, 'TC', 'Turks and Caicos Islands'),
}
NOT_PLACES = {'', 'n a', 'na', 'various', 'unknown', 'moon', 'low earth orbit', 'cislunar space', 'pacific time zone',
              'north america', 'centcom', 'africom', 'eucom', 'northcom', 'indopacom', 'indo pacom', 'southcom'}
STATE_ABBR = {'mi': 'michigan', 'ma': 'massachusetts', 'tx': 'texas', 'fl': 'florida', 'nj': 'new jersey'}

_G = None


def tables():
    global _G
    if _G is None:
        countries, country_names, admin1, us_abbr, by_place, centres = bluebook.load_geonames()
        country_names.update({'ussr': 'RU', 'united states': 'US', 'u s': 'US', 'usa': 'US'})
        _G = dict(countries=countries, country_names=country_names, admin1=admin1, us_abbr=us_abbr,
                  by_place=by_place, centres=centres)
    return _G


def _region(text):
    """'Missouri' / 'MO' / 'Washington State' -> (cc, admin1 code, name) or None."""
    g = tables()
    r = norm(text).replace(' state', '').strip()
    r = STATE_ABBR.get(r, r)
    r = g['us_abbr'].get(r, r)
    r = bluebook.US_ABBR.get(r, r)
    return g['admin1'].get(r)


def _town(name, cc, a1=''):
    g = tables()
    for cand in bluebook.place_candidates(name):
        for key in ((cc, a1, cand), (cc, a1, cand + '#full'), (cc, '', cand)):
            hits = g['by_place'].get(key)
            if hits:
                pop, lat, lon, _ = max(hits)
                return lat, lon
    return None


def geocode(text):
    g = tables()
    t = re.sub(r',\s*(U\.?S\.?A?\.?|United States)$', '', (text or '').strip(), flags=re.I).strip()
    key = norm(t)
    if key in NOT_PLACES or '|' in t or ';' in t:
        return None
    if key in OVERRIDES:
        lat, lon, cc, region = OVERRIDES[key]
        return lat, lon, 'place', cc, region
    if key in AREAS:
        lat, lon, cc = AREAS[key]
        return lat, lon, 'area', cc, t
    parts = [p.strip() for p in t.split(',') if p.strip()]
    if len(parts) == 1:
        reg = _region(parts[0])
        if reg:
            cc, a1, name = reg
            lat, lon = g['centres'][(cc, a1)]
            return lat, lon, 'region', cc, name
        cc = g['country_names'].get(key)
        if cc and (cc, '') in g['centres']:
            lat, lon = g['centres'][(cc, '')]
            return lat, lon, 'country', cc, g['countries'].get(cc, t)
        if key in ('washington d c', 'washington dc'):
            return 38.895, -77.036, 'place', 'US', 'District of Columbia'
        return None
    place, region = ', '.join(parts[:-1]), parts[-1]
    if norm(place) == 'washington' and norm(region) in ('d c', 'dc'):
        return 38.895, -77.036, 'place', 'US', 'District of Columbia'
    if norm(place).startswith('cape kennedy') or norm(place).startswith('cape canaveral'):
        return 28.396, -80.605, 'place', 'US', 'Florida'
    reg = _region(region)
    if reg:
        cc, a1, name = reg
        if len(parts) == 2 and _region(place) and norm(place) != norm(region):  # "Montana, Utah": two states
            return None
        hit = _town(place, cc, a1)
        if hit:
            return hit[0], hit[1], 'place', cc, name
        lat, lon = g['centres'][(cc, a1)]
        return lat, lon, 'region', cc, name
    cc = g['country_names'].get(norm(region))
    if cc:
        hit = _town(place, cc)
        if hit:
            return hit[0], hit[1], 'place', cc, g['countries'].get(cc, region)
        if (cc, '') in g['centres']:
            lat, lon = g['centres'][(cc, '')]
            return lat, lon, 'country', cc, g['countries'].get(cc, region)
    return None

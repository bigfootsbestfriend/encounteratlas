"""Merge new creature batches (data/<name>_new.json + data/<name>_overrides.json) into creatures.json and
famous_overrides.json. Skips slugs that already exist. usage: python3 tools/merge_new.py fae sweep"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: os.path.join(ROOT, 'data', f)
FIELDS = ['slug', 'name', 'aliases', 'cat', 'icon', 'region', 'cc', 'first', 'summary', 'body', 'signs', 'size', 'habitat',
          'famous', 'related', 'wiki']
CATS = {'hominid', 'canid', 'winged', 'aquatic', 'entity', 'other', 'ufo', 'fae'}
cs = json.load(open(D('creatures.json')))
have = {c['slug'] for c in cs}
ovr = json.load(open(D('famous_overrides.json')))
added = []
for batch in sys.argv[1:]:
    for c in json.load(open(D(batch + '_new.json'))):
        if c['slug'] in have:
            print('skip existing', c['slug']); continue
        miss = [f for f in FIELDS if f not in c]
        if miss or c['cat'] not in CATS:
            print('BAD', c.get('slug'), miss, c.get('cat')); continue
        cs.append({f: c[f] for f in FIELDS}); have.add(c['slug']); added.append(c['slug'])
    if os.path.exists(D(batch + '_overrides.json')):
        ovr.update(json.load(open(D(batch + '_overrides.json'))))
for c in cs:  # drop dangling related links
    c['related'] = [r for r in c['related'] if r in have and r != c['slug']]
json.dump(cs, open(D('creatures.json'), 'w'), indent=1, ensure_ascii=False)
json.dump(dict(sorted(ovr.items())), open(D('famous_overrides.json'), 'w'), indent=1, ensure_ascii=False)
print(f'added {len(added)}: {" ".join(added)}; total {len(cs)}')

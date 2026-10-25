"""Scheduled rewrites (Mike, 2026-10-25): witness stories retold in the storytelling style go live in batches of about
20 a day, with no manual step. data/story_rewrites.json holds {"witness": {id: {"release": "YYYY-MM-DD", "body": [...]}}}.
The daily 09:17 UTC build swaps in every rewrite whose release date has arrived; data/witness_stories.json keeps the
original report wording untouched. Every loader of witness_stories.json goes through apply_witness()."""
import datetime, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    p = os.path.join(ROOT, 'data', 'story_rewrites.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def released(kind, today=None):
    today = today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    return {k: v for k, v in _load().get(kind, {}).items() if v.get('release', '9999') <= today}


def apply_witness(stories):
    live = released('witness')
    for st in stories:
        r = live.get(st.get('id'))
        if r:
            st['body'] = r['body']
            st['retold'] = r['release']
    return stories

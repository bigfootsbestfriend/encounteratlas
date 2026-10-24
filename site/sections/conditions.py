"""Data for the "Conditions that night" panel on reader report pages (static/conditions.js; the panel's HTML is in
reports.py). Writes OUT/data/showers.json from skywatch.py's SHOWERS so there's still only one meteor shower table.
"""
import importlib.util
import json
import os


def build(ctx):
    spec = importlib.util.spec_from_file_location('sec_skywatch_showers', os.path.join(os.path.dirname(__file__), 'skywatch.py'))
    sky = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sky)
    rows = [{'n': s[1], 's': s[2], 'p': s[3], 'e': s[4], 'z': s[5]} for s in sky.SHOWERS]
    os.makedirs(os.path.join(ctx.OUT, 'data'), exist_ok=True)
    with open(os.path.join(ctx.OUT, 'data', 'showers.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, separators=(',', ':'))

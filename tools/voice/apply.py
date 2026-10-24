"""Merge a hand-written rewrite (tools/voice/<slug>.json) into data/creatures.json after linting it against
Mike's voice rules (MIKE-VOICE.md). Usage: python3 tools/voice/apply.py <slug> [--dry]"""
import json, re, sys, datetime
BANNED = r"\b(delve|tapestry|testament|intriguing|enigmatic|captivating|compelling|remarkabl\w*|notabl\w*|striking\w*|eerie|eerily|unsettling|haunting|chilling|lingering|enduring|shrouded|moreover|furthermore|in conclusion|worth noting|remains unclear|speaks to|underscore\w*|a reminder that|converge\w*|genuinely|the teller)\b"
def lint(texts):
    bad = []
    for t in texts:
        if '—' in t or '–' in t: bad.append(('dash', t[:80]))
        for m in re.finditer(BANNED, t, re.I): bad.append(('word ' + m.group(0), t[:80]))
        for m in re.finditer(r'[a-z]: [a-z]', t):
            if not re.search(r'(Side note|Here\'s the thing): ', t[max(0, m.start() - 15):m.end()]): bad.append(('colon', t[max(0, m.start() - 40):m.end() + 30]))
        if re.search(r"\bisn't (just )?\w+[^.]*, it's\b|\bnot just\b[^.]*\bbut\b|That gap between", t): bad.append(('contrast frame', t[:80]))
        if re.search(r'bfro|nuforc|mufon', t, re.I): bad.append(('banned source', t[:80]))
    return bad
slug = sys.argv[1]
new = json.load(open(f'tools/voice/{slug}.json'))
texts = [p for s in new.get('sections', []) for p in s['p']] + [f['a'] for f in new.get('faq', [])] + new.get('body', []) + [new.get('summary', ''), new.get('seo_desc', '')]
bad = lint(texts)
for b in bad: print('LINT', *b)
words = sum(len(t.split()) for t in texts)
print(slug, 'words', words, 'lint issues', len(bad))
if bad or '--dry' in sys.argv: sys.exit(1 if bad else 0)
C = json.load(open('data/creatures.json'))
for c in C:
    if c['slug'] == slug:
        c.update(new); c['updated'] = datetime.date.today().isoformat()
json.dump(C, open('data/creatures.json', 'w'), ensure_ascii=False, indent=1)
print('applied')

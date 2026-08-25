#!/usr/bin/env python3
"""Rebuild the archive + search indexes from editions/*.html. Idempotent; run from repo root.
Outputs:
  editions/index.json              — list of editions (date, day, stories)
  editions/search-index.json       — light per-story metadata (title, summary, zone, id, date)
  editions/search-body-YYYY-MM.json — full lesson text per story, sharded by month (lazy-loaded)
"""
import re, json, glob, html as H, datetime, os
from collections import defaultdict

def txt(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', H.unescape(s)).strip()

editions, entries = [], []
shards = defaultdict(dict)
for path in sorted(glob.glob('editions/????-??-??.html')):
    date = os.path.basename(path)[:-5]
    doc = open(path, encoding='utf-8').read()
    zones = re.findall(r'<section class="zone">(.*?)</section>', doc, re.S)
    n_stories = 0
    for z in zones:
        zh = re.search(r'<div class="zone-head">(.*?)</div>', z, re.S)
        zone = txt(re.sub(r'<span.*?</span>', '', zh.group(1), flags=re.S)) if zh else ''
        if 'Concept Library' in zone: continue
        for m in re.finditer(r'<div class="card[^"]*" data-deep="([^"]+)">(.*?)(?=<div class="card|\Z)', z, re.S):
            did, body = m.group(1), m.group(2)
            h2 = re.search(r'<h2>(.*?)</h2>', body, re.S)
            st = re.search(r'<div class="story">(.*?)</div>', body, re.S)
            sl = re.search(r'<div class="srcline">(.*?)</div>', body, re.S)
            wy = re.search(r'<div class="why">(.*?)</div>', body, re.S)
            imp = 1 if 'card imp' in m.group(0)[:40] else 0
            mod = re.search(r'<div class="overlay" id="'+re.escape(did)+r'">(.*?)(?=\n*\s*(?:<div class="overlay"|<script>))', doc, re.S)
            deep = re.sub(r'^Close\s*\S*\s*', '', txt(mod.group(1))) if mod else ''
            n_stories += 1
            entries.append({'d': date, 'z': zone, 'id': did, 'imp': imp,
                            't': txt(h2.group(1)) if h2 else '',
                            's': (txt(st.group(1)) if st else '') + (' ' + txt(wy.group(1)) if wy else ''),
                            'src': txt(sl.group(1)) if sl else ''})
            shards[date[:7]][date+'|'+did] = deep
    wd = datetime.date.fromisoformat(date).strftime('%a')
    editions.append({'date': date, 'day': wd, 'stories': n_stories})

editions.sort(key=lambda e: e['date'], reverse=True)
entries.sort(key=lambda e: e['d'], reverse=True)
months = sorted(shards.keys(), reverse=True)
json.dump({'editions': editions}, open('editions/index.json','w'), ensure_ascii=False)
json.dump({'v': 2, 'built': datetime.date.today().isoformat(), 'months': months, 'entries': entries},
          open('editions/search-index.json','w'), ensure_ascii=False)
# remove stale shards, write current ones
for old in glob.glob('editions/search-body-*.json'):
    if os.path.basename(old)[12:-5] not in shards: os.remove(old)
for mo, data in shards.items():
    json.dump(data, open(f'editions/search-body-{mo}.json','w'), ensure_ascii=False)
print('editions:', len(editions), '| entries:', len(entries), '| months:', months,
      '| light index:', os.path.getsize('editions/search-index.json'), 'bytes',
      '| shards:', {mo: os.path.getsize(f'editions/search-body-{mo}.json') for mo in months})

#!/usr/bin/env python3
"""Rebuild the archive + search indexes AND the Land School all-classes page. Idempotent; run from repo root.
Outputs:
  editions/index.json               — list of editions (date, day, stories)
  editions/search-index.json        — light per-story metadata + light school-class metadata
  editions/search-body-YYYY-MM.json — full lesson text per news story, sharded by month (lazy-loaded)
  editions/search-school.json       — full text of all 37 Land School classes (lazy-loaded)
  school.html                       — the Land School library: all 37 classes on one page (reuses index.html's <style>)
"""
import re, json, glob, html as H, datetime, os
from collections import defaultdict

def txt(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', H.unescape(s)).strip()

# ---------- news editions ----------
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

# ---------- Land School: light entries + full-text shard + library page ----------
school_light, school_bodies = [], {}
CAT_ORDER = ['Buying','Selling','Records','Rules','Tax','Safety','NRI','Developers','Market']
lessons, tg_guides, tg_tabs = [], [], []
if os.path.exists('learn/tg-guides.json'):
    gdata = json.load(open('learn/tg-guides.json'))
    tg_guides = gdata['guides']
    tg_tabs = gdata.get('tabOrder', [])
    for g in tg_guides:
        school_light.append({'id': g['id'], 't': g['title'], 's': g['summary'], 'cat': 'TG Guides · '+g['category']})
        school_bodies[g['id']] = txt(g['html'])
if os.path.exists('learn/lessons.json'):
    data = json.load(open('learn/lessons.json'))
    lessons = data['lessons'] if isinstance(data, dict) else data
    for l in lessons:
        school_light.append({'id': 'ls-'+l['id'], 't': l['title'], 's': l['summary'], 'cat': l['category']})
        school_bodies['ls-'+l['id']] = txt(l['html'])

    # school.html — reuse the live paper's <style> so design stays in sync
    idx = open('index.html', encoding='utf-8').read()
    style = re.search(r'<style>.*?</style>', idx, re.S).group(0)
    fonts = re.search(r'<link rel="stylesheet" href="https://fonts[^>]+>', idx)
    cats = defaultdict(list)
    for l in lessons: cats[l['category']].append(l)
    order = [c for c in CAT_ORDER if c in cats] + [c for c in sorted(cats) if c not in CAT_ORDER]
    body_zones, modals = '', ''
    for c in order:
        cards = ''
        for l in cats[c]:
            lid = 'ls-'+l['id']
            cards += ('<div class="card mini" data-deep="'+lid+'">\n'
              '<h2>\U0001F393 '+l['title']+'</h2>\n'
              '<div class="srcline">Land School · topic: '+l['category']+' · source &amp; further reading: <a href="'+l['srcUrl']+'" target="_blank" rel="noopener">1acre.in</a></div>\n'
              '<div class="story">'+l['summary']+'</div>\n'
              '<div class="deepbar"><span>Evergreen class — part of the 37-class course</span><button class="deep-btn" data-open="'+lid+'">Open class ▸</button></div>\n'
              '</div>\n')
            modals += ('<div class="overlay" id="'+lid+'">\n<div class="sheet">\n'
              '<button class="close" data-close>Close ✕</button>\n'
              '<h2>\U0001F393 '+l['title']+'</h2>\n'
              '<div class="srcline">Land School — an original Deccan Ledger lesson · source &amp; further reading: <a href="'+l['srcUrl']+'" target="_blank" rel="noopener">'+l['srcTitle']+' — 1acre.in</a></div>\n'
              +l['html']+'\n</div>\n</div>\n')
        body_zones += ('<section class="zone">\n<div class="zone-head">'+c+
          ' <span class="count">'+str(len(cats[c]))+(' class' if len(cats[c])==1 else ' classes')+'</span></div>\n'+cards+'</section>\n')

    # --- Telangana land document guides section (tabbed) ---
    tg_section, tg_modals = '', ''
    if tg_guides:
        gcats = defaultdict(list)
        for g in tg_guides: gcats[g['category']].append(g)
        tabs = [c for c in tg_tabs if c in gcats] + [c for c in sorted(gcats) if c not in tg_tabs]
        chips = '<button class="chip active" data-tgtab="__all">All guides</button>'
        for c in tabs:
            chips += '<button class="chip" data-tgtab="'+c+'">'+c+' ('+str(len(gcats[c]))+')</button>'
        tg_section = ('<div class="schoolhead" id="tg-guides" style="margin-top:44px;">'
          '<h1 style="font-size:29px;">Telangana land document guides</h1>'
          '<p>The complete set of '+str(len(tg_guides))+' Telangana-specific guides — every state document, portal and check, from the Pahani to the registration slot — written by The Deccan Ledger on 1acre.in\u2019s guide library, in our own words, each crediting and linking its source. Pick a tab to browse by stage.</p>'
          '<div class="chips" style="display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px;">'+chips+'</div></div>\n')
        for c in tabs:
            cards = ''
            for g in gcats[c]:
                cards += ('<div class="card mini" data-deep="'+g['id']+'">\n'
                  '<h2>\U0001F4D1 '+g['title']+'</h2>\n'
                  '<div class="srcline">TG guide · '+g['category']+' · source &amp; further reading: <a href="'+g['srcUrl']+'" target="_blank" rel="noopener">1acre.in</a></div>\n'
                  '<div class="story">'+g['summary']+'</div>\n'
                  '<div class="deepbar"><span>Telangana land document guide</span><button class="deep-btn" data-open="'+g['id']+'">Open guide ▸</button></div>\n'
                  '</div>\n')
                tg_modals += ('<div class="overlay" id="'+g['id']+'">\n<div class="sheet">\n'
                  '<button class="close" data-close>Close ✕</button>\n'
                  '<h2>\U0001F4D1 '+g['title']+'</h2>\n'
                  '<div class="srcline">Telangana land document guide — an original Deccan Ledger lesson · source &amp; further reading: <a href="'+g['srcUrl']+'" target="_blank" rel="noopener">'+g['srcTitle']+' — 1acre.in</a></div>\n'
                  +g['html']+'\n</div>\n</div>\n')
            tg_section += ('<section class="zone tgg" data-tgcat="'+c+'">\n<div class="zone-head">'+c+
              ' <span class="count">'+str(len(gcats[c]))+(' guide' if len(gcats[c])==1 else ' guides')+'</span></div>\n'+cards+'</section>\n')

    school_page = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
      '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
      '<meta name="robots" content="noindex">\n<title>Land School — The Deccan Ledger</title>\n'
      +(fonts.group(0)+'\n' if fonts else '')+style+'\n'
      '<style>.schoolbar{position:sticky;top:0;z-index:120;background:#161512;color:#f6f3ec;font-family:Inter,-apple-system,sans-serif;font-size:14px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;gap:10px;}.schoolbar a{color:#e8c469;text-decoration:none;font-weight:600;white-space:nowrap;}.schoolhead{max-width:740px;margin:26px auto 6px;padding:0 18px;}.schoolhead h1{font-family:var(--serif);font-size:34px;margin:0 0 6px;}.schoolhead p{color:var(--muted);font-size:14.5px;line-height:1.55;margin:0 0 8px;}</style>\n'
      '</head>\n<body>\n'
      '<div class="schoolbar"><span>\U0001F393 Land School · all '+str(len(lessons))+' classes</span><a href="index.html">‹ Today’s paper</a></div>\n'
      '<div class="schoolhead"><h1>Land School</h1><p>The complete 37-class course on land — written by The Deccan Ledger on the topics of 1acre.in’s research library, in our own words, every class crediting and linking its source. Two classes appear in the daily paper on rotation; this page holds them all. Tap any class to open it.</p></div>\n'
      '<main class="wrap">\n'+body_zones+tg_section+'</main>\n'+modals+tg_modals+
      '<script>(function(){\n'
      'function openM(id){var m=document.getElementById(id);if(!m)return;document.querySelectorAll(".overlay.open").forEach(function(o){o.classList.remove("open");});m.classList.add("open");document.body.style.overflow="hidden";m.scrollTop=0;}\n'
      'function closeAll(){document.querySelectorAll(".overlay.open").forEach(function(m){m.classList.remove("open");});document.body.style.overflow="";}\n'
      'document.querySelectorAll(".card[data-deep]").forEach(function(c){c.addEventListener("click",function(e){if(e.target.closest("a")||e.target.closest(".deep-btn"))return;openM(c.getAttribute("data-deep"));});});\n'
      'document.querySelectorAll("[data-open]").forEach(function(b){b.addEventListener("click",function(e){e.stopPropagation();openM(b.getAttribute("data-open"));});});\n'
      'document.querySelectorAll("[data-close]").forEach(function(b){b.addEventListener("click",closeAll);});\n'
      'document.querySelectorAll(".overlay").forEach(function(o){o.addEventListener("click",function(e){if(e.target===o)closeAll();});});\n'
      'document.addEventListener("keydown",function(e){if(e.key==="Escape")closeAll();});\n'
      'try{var t=localStorage.getItem("ddl-theme");if(t&&t!=="system")document.documentElement.dataset.theme=t;}catch(e){}\n'
      'var tgChips=document.querySelectorAll("[data-tgtab]");\n'
      'function tgShow(tab){document.querySelectorAll("section.tgg").forEach(function(z){z.style.display=(tab==="__all"||z.getAttribute("data-tgcat")===tab)?"":"none";});tgChips.forEach(function(c){c.classList.toggle("active",c.getAttribute("data-tgtab")===tab);});}\n'
      'tgChips.forEach(function(c){c.addEventListener("click",function(){tgShow(c.getAttribute("data-tgtab"));});});\n'
      'var h=decodeURIComponent(location.hash.slice(1)||"");if(h)setTimeout(function(){openM(h);},100);\n'
      '})();</script>\n</body>\n</html>\n')
    open('school.html','w',encoding='utf-8').write(school_page)

# ---------- write indexes ----------
json.dump({'editions': editions}, open('editions/index.json','w'), ensure_ascii=False)
json.dump({'v': 3, 'built': datetime.date.today().isoformat(), 'months': months,
           'entries': entries, 'school': school_light},
          open('editions/search-index.json','w'), ensure_ascii=False)
for old in glob.glob('editions/search-body-*.json'):
    if os.path.basename(old)[12:-5] not in shards: os.remove(old)
for mo, data in shards.items():
    json.dump(data, open(f'editions/search-body-{mo}.json','w'), ensure_ascii=False)
json.dump(school_bodies, open('editions/search-school.json','w'), ensure_ascii=False)
print('editions:', len(editions), '| news entries:', len(entries), '| school classes:', len(school_light),
      '| months:', months,
      '| light index:', os.path.getsize('editions/search-index.json'), 'B',
      '| school shard:', os.path.getsize('editions/search-school.json'), 'B',
      '| school.html:', os.path.getsize('school.html') if lessons else 0, 'B')

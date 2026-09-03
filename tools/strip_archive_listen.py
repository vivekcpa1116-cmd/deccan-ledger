#!/usr/bin/env python3
"""Voice belongs to TODAY'S paper only (Vivek, 2 Sep 2026).
Archived editions get a small script that removes every listen control.
Run from the repo root; safe to re-run."""
import glob, os, re

STRIP = ('<script>(function(){function go(){'
         "['.listen-btn','#btn-listen-all','.player','#rs-voicewrap'].forEach(function(sel){"
         'document.querySelectorAll(sel).forEach(function(el){ el.remove(); });});'
         'try{ if(window.speechSynthesis) speechSynthesis.cancel(); }catch(e){}}'
         'if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",function(){setTimeout(go,60);});'
         ' else setTimeout(go,60);})();</script>')

MARK = 'ddl-no-listen'
done = 0
for p in sorted(glob.glob('editions/????-??-??.html')):
    s = open(p, encoding='utf-8').read()
    if MARK in s:
        continue
    if 'listen-btn' not in s:
        continue  # older editions built before the listen feature
    s = s.replace('</body>', '<!-- ' + MARK + ' -->' + STRIP + '\n</body>', 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('stripped listen from', os.path.basename(p))
    done += 1
print('done:', done, 'archived edition(s) updated')

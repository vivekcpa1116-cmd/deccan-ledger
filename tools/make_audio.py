#!/usr/bin/env python3
"""Studio voice for TODAY'S paper only.

Reads index.html, turns each story card into a short spoken track with OpenAI's
text-to-speech, uploads the MP3s to a GitHub release (so they never enter git
history and the repo stays small), and writes audio/manifest.json so the app
plays the recorded voice instead of the phone's built-in one.

Only ONE day of audio is kept: yesterday's release is deleted every run.

Needs:  OPENAI_API_KEY  in the environment, and the gh CLI logged in.
Usage:  python3 tools/make_audio.py            (voice: standard tts-1)
        python3 tools/make_audio.py --hd       (higher fidelity, 2x cost)
        python3 tools/make_audio.py --dry-run  (show cost, generate nothing)
"""
import os, re, sys, json, html, subprocess, tempfile, datetime, urllib.request

REPO      = 'vivekcpa1116-cmd/deccan-ledger'
GH        = '/Users/vivek/deccan-ledger-site/bin/gh'
VOICE     = os.environ.get('DDL_VOICE', 'onyx')   # onyx = calm male news read
MODEL     = 'tts-1'
RATE_USD  = 15.0 / 1_000_000                      # tts-1: $15 per 1M characters
INR       = 88.0

if '--hd' in sys.argv:
    MODEL, RATE_USD = 'tts-1-hd', 30.0 / 1_000_000
DRY = '--dry-run' in sys.argv


def txt(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def spoken(raw):
    """Tidy the text so it reads naturally aloud."""
    t = txt(raw)
    t = re.sub(r'✓\s*READ', '', t)
    t = re.sub(r'[\U0001F000-\U0001FAFF\u2190-\u2BFF\uFE0F]', ' ', t)  # emoji/symbols read badly
    t = t.replace('₹', 'rupees ').replace('&', ' and ')
    t = re.sub(r'\bsq\s?yd\b', 'square yards', t, flags=re.I)
    t = re.sub(r'\bsq\s?ft\b', 'square feet', t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def collect(doc):
    """One track per story card, in the order they appear in the paper."""
    items = []
    for zone in re.findall(r'<section class="zone">(.*?)</section>', doc, re.S):
        zh = re.search(r'<div class="zone-head">(.*?)</div>', zone, re.S)
        zname = txt(re.sub(r'<span.*?</span>', '', zh.group(1), flags=re.S)) if zh else ''
        if 'Concept Library' in zname:
            continue
        for m in re.finditer(r'<div class="card[^"]*" data-deep="([^"]+)">(.*?)(?=<div class="card|\Z)', zone, re.S):
            cid, body = m.group(1), m.group(2)
            h2 = re.search(r'<h2>(.*?)</h2>', body, re.S)
            st = re.search(r'<div class="story">(.*?)</div>', body, re.S)
            wy = re.search(r'<div class="why">(.*?)</div>', body, re.S)
            title = spoken(h2.group(1)) if h2 else 'Story'
            parts = [title]
            if st: parts.append(spoken(st.group(1)))
            if wy: parts.append(spoken(wy.group(1)))
            text = '. '.join(p for p in parts if p)
            if len(text) > 40:
                items.append({'id': cid, 'title': title[:90], 'zone': zname, 'text': text})
    return items


def speak(text, path, key):
    req = urllib.request.Request(
        'https://api.openai.com/v1/audio/speech',
        data=json.dumps({'model': MODEL, 'voice': VOICE, 'input': text[:4000]}).encode(),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r, open(path, 'wb') as f:
        f.write(r.read())


def gh(*args, **kw):
    return subprocess.run([GH] + list(args), capture_output=True, text=True, **kw)


def main():
    doc = open('index.html', encoding='utf-8').read()
    dm = re.search(r'<div class="date">([^&<]+)', doc)
    date_label = dm.group(1).strip().rstrip('&middot;').strip() if dm else ''
    today = datetime.date.today().isoformat()

    items = collect(doc)
    chars = sum(len(i['text']) for i in items)
    usd = chars * RATE_USD
    print(f'{len(items)} tracks · {chars:,} characters · {MODEL} · '
          f'${usd:.2f} (about rupees {usd*INR:.0f}) · voice {VOICE}')
    if DRY:
        for i in items:
            print(f"   {i['id']:26} {len(i['text']):>5} chars  {i['title'][:52]}")
        return

    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        sys.exit('OPENAI_API_KEY is not set — cannot generate audio.')

    tag = 'audio-' + today
    tmp = tempfile.mkdtemp(prefix='ddl-audio-')
    manifest = {'date': today, 'dateLabel': date_label, 'model': MODEL,
                'voice': VOICE, 'items': []}

    for n, it in enumerate(items, 1):
        fn = f"{it['id']}.mp3"
        path = os.path.join(tmp, fn)
        print(f'  [{n}/{len(items)}] {it["id"]} …', flush=True)
        speak(it['text'], path, key)
        manifest['items'].append({
            'id': it['id'], 'title': it['title'], 'zone': it['zone'],
            'file': fn, 'bytes': os.path.getsize(path)})

    # publish the files as release assets (they never enter git history)
    gh('release', 'delete', tag, '--yes', '--cleanup-tag')
    r = gh('release', 'create', tag, '--repo', REPO, '--title',
           f'Audio · {date_label or today}', '--notes',
           'Spoken edition. Replaced daily; only one day is kept.')
    if r.returncode != 0 and 'already exists' not in (r.stderr or ''):
        sys.exit('could not create release: ' + (r.stderr or r.stdout))
    files = [os.path.join(tmp, i['file']) for i in manifest['items']]
    up = gh('release', 'upload', tag, *files, '--repo', REPO, '--clobber')
    if up.returncode != 0:
        sys.exit('upload failed: ' + (up.stderr or up.stdout))

    manifest['base'] = f'https://github.com/{REPO}/releases/download/{tag}/'
    os.makedirs('audio', exist_ok=True)
    json.dump(manifest, open('audio/manifest.json', 'w'), ensure_ascii=False, indent=1)

    # keep ONE day: remove every older audio release
    ls = gh('release', 'list', '--repo', REPO, '--limit', '40')
    for line in (ls.stdout or '').splitlines():
        t = line.split('\t')[0].strip()
        if t.startswith('audio-') and t != tag:
            gh('release', 'delete', t, '--yes', '--cleanup-tag', '--repo', REPO)
            print('  removed old audio release', t)

    total = sum(i['bytes'] for i in manifest['items'])
    print(f'done · {len(manifest["items"])} tracks · {total/1e6:.1f} MB hosted '
          f'· cost about rupees {usd*INR:.0f} · manifest written')


if __name__ == '__main__':
    main()

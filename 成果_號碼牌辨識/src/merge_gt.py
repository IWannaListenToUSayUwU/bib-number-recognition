"""合併雙標結果：兩人皆 sure 且號碼相同 → 直接採用；其餘列為待裁定。"""
import json, glob, os, sys, re
which = sys.argv[1] if len(sys.argv) > 1 else 'dev'
out = {}
for fa in sorted(glob.glob(f'work/labels/{which}/*_A.json')):
    clip = os.path.basename(fa)[:-7]
    fb = fa.replace('_A.json', '_B.json')
    A = json.load(open(fa))['runners']
    B = json.load(open(fb))['runners'] if os.path.exists(fb) else None
    sa = {r['bib'] for r in A if r['status'] == 'sure'}
    if B is None:
        out[clip] = {'agreed_sure': sorted(sa), 'only_A': [], 'only_B': [], 'single': True}
        continue
    sb = {r['bib'] for r in B if r['status'] == 'sure'}
    allb = lambda R: {r['bib']: r['status'] for r in R}
    ab, bb = allb(A), allb(B)
    out[clip] = {'agreed_sure': sorted(sa & sb),
                 'only_A': sorted((b, bb.get(b, '-')) for b in sa - sb),
                 'only_B': sorted((b, ab.get(b, '-')) for b in sb - sa), 'single': False}
for c, d in out.items():
    print(c, 'agree', len(d['agreed_sure']), d['agreed_sure'], '| A-only', d['only_A'], '| B-only', d['only_B'], '(single)' if d['single'] else '')

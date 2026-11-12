"""產生最終標準答案：sure 集合（含時間範圍）+ partial 樣式（用於不懲罰）。裁定結果寫在 ADJ。"""
import json, glob, os, sys
which = sys.argv[1]
ADJ = json.load(open(f'work/adjudication_{which}.json')) if os.path.exists(f'work/adjudication_{which}.json') else {}
gt = {}
for fa in sorted(glob.glob(f'work/labels/{which}/*_A.json')):
    clip = os.path.basename(fa)[:-7]
    files = [fa] + ([fa.replace('_A', '_B')] if os.path.exists(fa.replace('_A', '_B')) else [])
    L = [json.load(open(f)) for f in files]
    runs = {}
    for d in L:
        for r in d['runners']:
            runs.setdefault(r['bib'], []).append(r)
    sure_sets = [{r['bib'] for r in d['runners'] if r['status'] == 'sure'} for d in L]
    agreed = set.intersection(*sure_sets)
    adj = ADJ.get(clip, {})
    for b, verdict in adj.items():
        if verdict == 'sure': agreed.add(b)
        else: agreed.discard(b)
    sure = []
    for b in sorted(agreed):
        rs = runs[b]
        sure.append({'bib': b, 't0': min(r['t_first'] for r in rs), 't1': max(r['t_last'] for r in rs)})
    partial = []
    for d in L:
        for r in d['runners']:
            if r['bib'] not in agreed and r['bib'] != '?':
                partial.append({'pat': r['bib'], 't0': r['t_first'], 't1': r['t_last']})
    unread = max(sum(r['status'] == 'unreadable' for r in d['runners']) for d in L)
    nobib = max(d.get('no_bib_runners', 0) for d in L)
    gt[clip] = {'sure': sure, 'partial': partial, 'n_unreadable': unread, 'n_nobib': nobib, 'n_annotators': len(L)}
json.dump(gt, open(f'work/gt_{which}.json', 'w'), indent=1)
for c, g in gt.items():
    print(c, 'sure', len(g['sure']), 'partial', len(g['partial']), 'unread', g['n_unreadable'], 'nobib', g['n_nobib'], 'annot', g['n_annotators'])

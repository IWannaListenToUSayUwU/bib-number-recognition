import json, sys, os, collections
sys.path.insert(0, 'src')
from r3_common import pool, ed, norm
from aggregate2 import aggregate2
from evaluate import score_clip, summarize
cfg = json.load(open('work/FROZEN_CONFIG_v2.json'))['aggregate']
P = pool(); res = {}; FN = collections.Counter(); FP = collections.Counter(); ex = collections.defaultdict(list)
for k, d in P.items():
    preds = aggregate2(d['rows'], **cfg)
    pr = [(p['bib'], p['t'], p['score']) for p in preds]
    r = score_clip(pr, d['gt']); res[k] = r
    g = d['gt']
    for b in r['fn']:
        s = [x for x in g['sure'] if x['bib'] == b][0]
        win = [x for x in d['rows'] if s['t0'] - 2 <= x['t'] <= s['t1'] + 2]
        exact = [x for x in win if norm(x['txt']) == b]
        near = [x for x in win if norm(x['txt']) and ed(norm(x['txt']), b) == 1]
        if exact and max(x['sc'] for x in exact) >= 0.8: cat = 'A 有讀到(高信心)但沒輸出'
        elif exact: cat = 'B 有讀到但信心<0.8'
        elif near: cat = 'C 只讀到差一位的'
        elif any(norm(x['txt']) for x in win): cat = 'D 窗內只有其他數字'
        else: cat = 'E 窗內完全沒讀到數字'
        FN[cat] += 1; ex[cat].append((k[1], b))
    for b, t in r['fps']:
        sure_near = [x for x in g['sure'] if x['t0'] - 4 <= t <= x['t1'] + 4]
        part_near = [x for x in g['partial'] if x['t0'] - 4 <= t <= x['t1'] + 4]
        if any(x['bib'] == b for x in g['sure']): cat = 'a 重複輸出(同號碼已算過或時間不符)'
        elif any(ed(x['bib'], b) == 1 for x in sure_near): cat = 'b 與附近正確號碼差一位'
        elif any(len(x['pat']) != len(b) and x['pat'].replace('?', '') and all(ch in b for ch in x['pat'].replace('?', '')) for x in part_near) or any(ed(x['pat'].replace('?', ''), b) <= 1 for x in part_near if x['pat'] != '?'): cat = 'c 與附近 partial 相近'
        else: cat = 'd 其他(背景文字/路人/幻覺)'
        FP[cat] += 1; ex[cat].append((k[1], b, t))
print('BASELINE v2 on pool:', summarize(res))
for s in ['dev', 'test', 'test2']: print(' ', s, summarize({k: v for k, v in res.items() if k[0] == s}))
for v in ['v1', 'v2', 'v3']: print(' ', v, summarize({k: r for k, r in res.items() if k[1].startswith(v)}))
print('\nFN:'); [print(f'  {n:3d} {c}  e.g. {ex[c][:6]}') for c, n in sorted(FN.items())]
print('FP:'); [print(f'  {n:3d} {c}  e.g. {ex[c][:8]}') for c, n in sorted(FP.items())]
json.dump({'FN': FN, 'FP': FP, 'examples': ex}, open('r3/taxonomy.json', 'w'), ensure_ascii=False, indent=1)

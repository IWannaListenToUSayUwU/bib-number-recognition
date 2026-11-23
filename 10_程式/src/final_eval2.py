"""第二輪最終評估（test2，凍結設定 v2）。含/不含 v2_540 兩組；片段層級 bootstrap。"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(__file__))
from aggregate2 import load4, aggregate2
from evaluate import score_clip
cfg = json.load(open('work/FROZEN_CONFIG_v2.json'))['aggregate']
which = sys.argv[1] if len(sys.argv) > 1 else 'test2'; raw = sys.argv[2] if len(sys.argv) > 2 else 'work/raw4'
gt = json.load(open(f'work/gt_{which}.json'))
per, preds = {}, {}
for c in gt:
    rows, _ = load4(f'{raw}/{which}/{c}.jsonl')
    P = aggregate2(rows, **cfg)
    preds[c] = [(p['bib'], p['t'], p['score']) for p in P]
    per[c] = score_clip(preds[c], gt[c])
def agg(keys, strict=False):
    tp = sum(per[k]['tp'] for k in keys); fp = sum(per[k]['fp'] + (per[k]['ign'] if strict else 0) for k in keys); n = sum(per[k]['n'] for k in keys)
    P = tp / (tp + fp) if tp + fp else 0; R = tp / n if n else 0
    return dict(TP=tp, FP=fp, N=n, P=round(P, 3), R=round(R, 3), F1=round(2 * P * R / (P + R), 3) if P + R else 0)
def cboot(keys, B=10000, seed=0):
    rnd = random.Random(seed); out = {'P': [], 'R': [], 'F1': []}
    for _ in range(B):
        s = agg([rnd.choice(keys) for _ in keys])
        if s['N'] and s['TP'] + s['FP']:
            for k in out: out[k].append(s[k])
    return {k: (round(sorted(v)[int(.025 * len(v))], 3), round(sorted(v)[int(.975 * len(v))], 3)) for k, v in out.items()}
res = {'per_clip': {c: {k: per[c][k] for k in ['tp', 'fp', 'ign', 'n', 'fn', 'fps']} for c in per}}
groups = {'ALL': list(gt), 'ALL_excl_v2_540': [c for c in gt if c != 'v2_540']} | {v: [c for c in gt if c.startswith(v)] for v in ['v1', 'v2', 'v3']}
for g, keys in groups.items():
    res[g] = {'lenient': agg(keys), 'strict': agg(keys, True), 'clip_bootstrap_CI95': cboot(keys) if len(keys) > 2 else None}
    print(g, json.dumps(res[g], ensure_ascii=False))
for c in per: print(c, res['per_clip'][c])
json.dump(res, open(f'work/final_eval_{which}_v2.json', 'w'), ensure_ascii=False, indent=1)
json.dump(preds, open(f'work/final_preds_{which}_v2.json', 'w'), indent=1)

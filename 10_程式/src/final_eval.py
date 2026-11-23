"""最終評估（test 集，凍結設定）。只在標準答案定稿後執行一次。"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(__file__))
from bench3 import load
from aggregate import aggregate
from evaluate import score_clip
cfg = json.load(open('work/FROZEN_CONFIG.json'))['aggregate']
which = sys.argv[1] if len(sys.argv) > 1 else 'test'
raw = sys.argv[2] if len(sys.argv) > 2 else 'raw8'
gt = json.load(open(f'work/gt_{which}.json'))
per, preds_all = {}, {}
for c, g in gt.items():
    preds = aggregate(load(f'work/{raw}/{which}/{c}.jsonl'), **cfg)
    preds_all[c] = preds
    per[c] = score_clip(preds, g)
def agg(keys, strict=False):
    tp = sum(per[k]['tp'] for k in keys); fp = sum(per[k]['fp'] + (per[k]['ign'] if strict else 0) for k in keys)
    n = sum(per[k]['n'] for k in keys)
    vis = sum(per[k]['n'] + len({p['pat'] for p in gt[k]['partial']}) + gt[k]['n_unreadable'] for k in keys)
    P = tp / (tp + fp) if tp + fp else 0; R = tp / n if n else 0
    return dict(TP=tp, FP=fp, N_sure=n, P=round(P, 3), R=round(R, 3), F1=round(2 * P * R / (P + R), 3) if P + R else 0,
                R_vs_all_visible_bibs=round(tp / vis, 3) if vis else 0, N_visible=vis)
def boot(keys, B=5000, seed=0):
    rnd = random.Random(seed)
    gi = [1] * sum(per[k]['tp'] for k in keys) + [0] * sum(len(per[k]['fn']) for k in keys)
    pi = [1] * sum(per[k]['tp'] for k in keys) + [0] * sum(per[k]['fp'] for k in keys)
    def ci(v):
        if not v: return (0, 0)
        s = sorted(sum(rnd.choice(v) for _ in v) / len(v) for _ in range(B)); return (round(s[int(.025 * B)], 3), round(s[int(.975 * B)], 3))
    return dict(R_CI95=ci(gi), P_CI95=ci(pi))
out = {'per_clip': {c: {k: per[c][k] for k in ['tp', 'fp', 'ign', 'n', 'fn', 'fps']} for c in per}}
groups = {'ALL': list(gt)} | {v: [c for c in gt if c.startswith(v)] for v in ['v1', 'v2', 'v3']}
for gname, keys in groups.items():
    out[gname] = {'lenient': agg(keys), 'strict': agg(keys, strict=True), **boot(keys)}
    print(gname, json.dumps(out[gname], ensure_ascii=False))
for c in per:
    print(c, {k: per[c][k] for k in ['tp', 'fp', 'ign', 'n', 'fn', 'fps']})
json.dump(out, open(f'work/final_eval_{which}.json', 'w'), ensure_ascii=False, indent=1)
json.dump({c: p for c, p in preds_all.items()}, open(f'work/final_preds_{which}.json', 'w'), indent=1)

"""test3 一次評估：v2（aggregate2）vs v3（候選驗證器），同一份抽取，成對比較；片段層級 bootstrap 估 F1 差距。"""
import sys, json, random
sys.path.insert(0, 'src')
from r3_common import load_rows
from aggregate2 import aggregate2
from r3_final import predict_clip
from evaluate import score_clip, summarize
gt = json.load(open('work/gt_test3.json')); cfg2 = json.load(open('work/FROZEN_CONFIG_v2.json'))['aggregate']; J = json.load(open('r3/verifier_v3.json'))
R = {'v2': {}, 'v3': {}}; preds = {'v2': {}, 'v3': {}}
for c, g in gt.items():
    rows, persons = load_rows(f'work/raw4/test3/{c}.jsonl')
    p2 = [(p['bib'], p['t'], p['score']) for p in aggregate2(rows, **cfg2)]
    p3 = predict_clip(dict(rows=rows, persons=persons), J)
    preds['v2'][c], preds['v3'][c] = p2, p3
    R['v2'][c], R['v3'][c] = score_clip(p2, g), score_clip(p3, g)
out = {}
for v in ['v2', 'v3']:
    out[v] = {'ALL': summarize(R[v]), **{vid: summarize({c: r for c, r in R[v].items() if c.startswith(vid)}) for vid in ['v1', 'v2', 'v3']},
              'strict': summarize({c: dict(r, fp=r['fp'] + r['ign']) for c, r in R[v].items()})}
    print(v, json.dumps(out[v], ensure_ascii=False))
clips = list(gt); rnd = random.Random(0); d = []
for _ in range(10000):
    s = [rnd.choice(clips) for _ in clips]
    a = summarize({i: R['v2'][c] for i, c in enumerate(s)})['F1']; b = summarize({i: R['v3'][c] for i, c in enumerate(s)})['F1']; d.append(b - a)
d.sort(); out['F1_diff_v3_minus_v2'] = dict(point=round(out['v3']['ALL']['F1'] - out['v2']['ALL']['F1'], 3), CI95=(round(d[250], 3), round(d[9750], 3)), P_v3_better=round(sum(x > 0 for x in d) / len(d), 3))
print('F1 diff', out['F1_diff_v3_minus_v2'])
for c in clips: print(c, 'v2', {k: R['v2'][c][k] for k in ['tp', 'fp', 'n']}, '| v3', {k: R['v3'][c][k] for k in ['tp', 'fp', 'n']}, 'v3 fps', R['v3'][c]['fps'][:6])
out['per_clip'] = {v: {c: {k: R[v][c][k] for k in ['tp', 'fp', 'ign', 'n', 'fn', 'fps']} for c in clips} for v in R}
json.dump(out, open('r3/final_eval_test3.json', 'w'), ensure_ascii=False, indent=1); json.dump(preds, open('r3/final_preds_test3.json', 'w'), indent=1)

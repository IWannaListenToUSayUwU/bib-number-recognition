"""依活動度分層，固定種子抽 dev/test 片段。test 先抽、先鎖定；看過的 probe 時段只能進 dev。"""
import json, random
random.seed(20261111)
a = json.load(open('work/activity.json'))
CLIP = {'v1': 60, 'v2': 30, 'v3': 60}          # v2 人潮極密，片段縮短以控制標註量
PROBE = {'v1': [630, 1470], 'v2': [150, 270], 'v3': [1230, 1950]}
GAP = 120                                       # dev/test 之間至少隔 2 分鐘
out = {}
for v, rows in a.items():
    L = CLIP[v]; dur = rows[-1][0]
    wins = []
    for s in range(0, int(dur) - L, L):
        near = [r[2] for r in rows if s <= r[0] < s + L]
        wins.append((s, sum(near) / max(1, len(near))))
    vals = sorted(w[1] for w in wins)
    q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    strat = lambda x: 'low' if x < q1 else ('mid' if x < q2 else 'high')
    far = lambda s, pts: all(abs(s - p) >= GAP + L and abs(s + L - p) >= GAP for p in pts)
    test, dev = [], []
    for st in ['low', 'mid', 'high']:
        cand = [w for w in wins if strat(w[1]) == st and far(w[0], PROBE[v]) and far(w[0], [t[0] for t in test])]
        test.append(random.choice(cand))
    for st in ['low', 'mid', 'high']:
        cand = [w for w in wins if strat(w[1]) == st and far(w[0], [t[0] for t in test]) and far(w[0], [d[0] for d in dev])]
        dev.append(random.choice(cand))
    out[v] = {'clip_len': L,
              'test': [{'start': s, 'end': s + L, 'stratum': strat(x)} for s, x in test],
              'dev': [{'start': s, 'end': s + L, 'stratum': strat(x)} for s, x in dev]}
json.dump(out, open('work/split.json', 'w'), indent=1)
for v in out:
    print(v, 'TEST', [(c['start'], c['stratum']) for c in out[v]['test']], 'DEV', [(c['start'], c['stratum']) for c in out[v]['dev']])

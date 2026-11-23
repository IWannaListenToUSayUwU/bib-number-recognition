"""第二輪：新抽 test2（避開所有已用片段 ±120 秒），固定種子，抽出即鎖定。"""
import json, random
random.seed(20261112)
a = json.load(open('work/activity.json')); old = json.load(open('work/split.json'))
CLIP = {'v1': 60, 'v2': 30, 'v3': 60}; GAPS = {'v1': 120, 'v2': 30, 'v3': 120}
PROBE = {'v1': [630, 1470], 'v2': [150, 270], 'v3': [1230, 1950]}
out = {}
for v, rows in a.items():
    L = CLIP[v]; dur = rows[-1][0]
    used = [c['start'] for k in ['dev', 'test'] for c in old[v][k]]
    wins = []
    for s in range(0, int(dur) - L, L):
        near = [r[2] for r in rows if s <= r[0] < s + L]
        wins.append((s, sum(near) / max(1, len(near))))
    vals = sorted(w[1] for w in wins); q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    strat = lambda x: 'low' if x < q1 else ('mid' if x < q2 else 'high')
    far = lambda s, pts: all(abs(s - p) >= GAPS[v] + L for p in pts)
    picks = []
    for st in ['mid', 'high']:     # 低活動度片段幾乎沒有可讀號碼，第二輪只抽中、高兩層
        cand = [w for w in wins if strat(w[1]) == st and far(w[0], used + PROBE[v] + [p[0] for p in picks])]
        if not cand:   # 該層沒有符合間隔的片段時，放寬為「不重疊且間隔 >= 30 秒」，並記錄
            cand = [w for w in wins if strat(w[1]) == st and all(abs(w[0] - q) >= 30 + L for q in used + PROBE[v] + [p[0] for p in picks])]
            print('relaxed gap:', v, st)
        picks.append(random.choice(cand))
    out[v] = {'clip_len': L, 'test2': [{'start': s, 'end': s + L, 'stratum': strat(x)} for s, x in picks]}
json.dump(out, open('work/split2.json', 'w'), indent=1)
print({v: [(c['start'], c['stratum']) for c in out[v]['test2']] for v in out})

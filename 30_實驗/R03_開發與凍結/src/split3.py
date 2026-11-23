"""第三輪：新抽 test3。避開所有已用片段（dev/test/test2）與 probe 畫面，間隔 >=30 秒；固定種子，抽出即鎖定。"""
import json, random
random.seed(20261116)
a = json.load(open('work/activity.json')); s1 = json.load(open('work/split.json')); s2 = json.load(open('work/split2.json'))
CLIP = {'v1': 60, 'v2': 30, 'v3': 60}; NPICK = {'v1': 2, 'v2': 2, 'v3': 3}; GAP = 30
PROBE = {'v1': [630, 1470, 855], 'v2': [150, 270, 225, 626], 'v3': [1230, 1950, 1460, 2500]}
out = {}
for v, rows in a.items():
    L = CLIP[v]; dur = rows[-1][0]
    used = [(c['start'], c['end']) for k in ['dev', 'test'] for c in s1[v][k]] + [(c['start'], c['end']) for c in s2[v]['test2']]
    used += [(p, p) for p in PROBE[v]]
    ok = lambda s, U: all(s + L + GAP <= u0 or s >= u1 + GAP for u0, u1 in U)
    wins = []
    for s in range(0, int(dur) - L, 30):
        near = [r[2] for r in rows if s <= r[0] < s + L]
        wins.append((s, sum(near) / max(1, len(near))))
    vals = sorted(w[1] for w in wins); med = vals[len(vals) // 2]
    picks = []
    for _ in range(NPICK[v]):
        cand = [w for w in wins if w[1] >= med and ok(w[0], used + [(p, p + L) for p, _ in picks])]
        picks.append(random.choice(cand))
    out[v] = {'clip_len': L, 'test3': [{'start': s, 'end': s + L, 'activity': round(x, 2)} for s, x in sorted(picks)]}
json.dump(out, open('work/split3.json', 'w'), indent=1)
print({v: [(c['start'], c['activity']) for c in out[v]['test3']] for v in out})

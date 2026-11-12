"""評分：預測 [(bib, t, conf)] 對照標準答案。
TP：號碼完全相同且時間落在 [t0-2, t1+2]。同一 GT 只算一次，重複預測算 FP。
寬鬆模式：與 partial 樣式相容（? 視為萬用字元、位數相同）且時間重疊的預測不計 FP。"""
import json, re

def compat(pat, b, wild='?'):
    if pat == '?': return False
    return len(pat) == len(b) and all(p == wild or p == c for p, c in zip(pat, b))

def score_clip(preds, g, tol=2.0):
    matched = set(); tp = fp = ign = 0; fps = []
    for b, t, *_ in sorted(preds, key=lambda x: -(x[2] if len(x) > 2 else 0)):
        hit = None
        for i, s in enumerate(g['sure']):
            if s['bib'] == b and s['t0'] - tol <= t <= s['t1'] + tol:
                hit = i; break
        if hit is not None and hit not in matched:
            matched.add(hit); tp += 1
        elif hit is None and any(compat(p['pat'], b) and p['t0'] - tol <= t <= p['t1'] + tol for p in g['partial']):
            ign += 1
        else:
            fp += 1; fps.append((b, round(t, 1)))
    fn = [s['bib'] for i, s in enumerate(g['sure']) if i not in matched]
    return dict(tp=tp, fp=fp, ign=ign, n=len(g['sure']), fn=fn, fps=fps)

def summarize(res):
    tp = sum(r['tp'] for r in res.values()); fp = sum(r['fp'] for r in res.values()); n = sum(r['n'] for r in res.values())
    P = tp / (tp + fp) if tp + fp else 0; R = tp / n if n else 0
    return dict(TP=tp, FP=fp, N=n, P=round(P, 3), R=round(R, 3), F1=round(2 * P * R / (P + R), 3) if P + R else 0)

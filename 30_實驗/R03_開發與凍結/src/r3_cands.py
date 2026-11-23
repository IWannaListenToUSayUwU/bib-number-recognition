"""候選號碼表：每個 (軌跡, 號碼) 一列，附特徵與標籤（TP/FP/IGN）。供規則設計與交叉驗證。"""
import json, sys, collections, numpy as np
sys.path.insert(0, 'src')
from r3_common import pool, ed, norm
from evaluate import compat

def candidates(d, min_conf=0.5, minlen=1, maxlen=5):
    rows = d['rows']; per = collections.defaultdict(list)
    for p in d['persons']: per[p['tid']].append(p)
    g = collections.defaultdict(list)
    for r in rows:
        s = norm(r['txt'])
        if not s or r['sc'] < min_conf or not (minlen <= len(s) <= maxlen): continue
        key = r['tid'] if r['tid'] >= 0 else ('f', r['t'], tuple(r['bbox']))
        g[key].append((s, r))
    out = []
    for key, v in g.items():
        tot = sum(r['sc'] for _, r in v)
        strs = collections.defaultdict(list)
        for s, r in v: strs[s].append(r)
        pp = sorted(per.get(key, []), key=lambda p: p['t']) if not isinstance(key, tuple) else []
        if len(pp) >= 2:
            a, b = pp[0]['pbox'], pp[-1]['pbox']; h = np.median([p['pbox'][3] - p['pbox'][1] for p in pp])
            disp = np.hypot((a[0] + a[2] - b[0] - b[2]) / 2, (a[1] + a[3] - b[1] - b[3]) / 2) / h
            cx = [(p['pbox'][0] + p['pbox'][2]) / 2 for p in pp]; cy = [(p['pbox'][1] + p['pbox'][3]) / 2 for p in pp]
            rng = np.hypot(max(cx) - min(cx), max(cy) - min(cy)) / h
            grow = (b[3] - b[1]) / max(1, a[3] - a[1]); dur = pp[-1]['t'] - pp[0]['t']
        else:
            disp = rng = 0.0; grow = 1.0; dur = 0.0
        for s, rs in strs.items():
            relx = np.median([((r['bbox'][0] + r['bbox'][2]) / 2 - (r['pbox'][0] + r['pbox'][2]) / 2) / max(1, r['pbox'][2] - r['pbox'][0]) for r in rs])
            rely = np.median([((r['bbox'][1] + r['bbox'][3]) / 2 - r['pbox'][1]) / max(1, r['ph']) for r in rs])
            tx = [(r['bbox'][0] + r['bbox'][2]) / 2 for r in rs]; ty = [(r['bbox'][1] + r['bbox'][3]) / 2 for r in rs]
            best = max(rs, key=lambda r: r['sc'] * r['bh'])
            out.append(dict(key=key, bib=s, n=len(rs), sumc=sum(r['sc'] for r in rs), maxc=max(r['sc'] for r in rs),
                            nhi=sum(r['sc'] >= 0.9 for r in rs), bh=max(r['bh'] for r in rs), bhrel=float(np.median([r['bh'] / max(1, r['ph']) for r in rs])),
                            frac=sum(r['sc'] for r in rs) / tot, L=len(s), relx=float(relx), rely=float(rely),
                            disp=float(disp), rng=float(rng), grow=float(grow), dur=float(dur), ntrk=len(pp),
                            tspan=max(r['t'] for r in rs) - min(r['t'] for r in rs), txtrng=float(np.hypot(max(tx) - min(tx), max(ty) - min(ty))),
                            t=best['t'], t0=min(r['t'] for r in rs), t1=max(r['t'] for r in rs), wtot=tot,
                            others={k: len(x) for k, x in strs.items() if k != s}))
    return out

def label(c, gt, tol=2.0):
    for s in gt['sure']:
        if s['bib'] == c['bib'] and s['t0'] - tol <= c['t'] <= s['t1'] + tol: return 'TP'
    for p in gt['partial']:
        if compat(p['pat'], c['bib']) and p['t0'] - tol <= c['t'] <= p['t1'] + tol: return 'IGN'
    return 'FP'

if __name__ == '__main__':
    P = pool(); T = []
    for k, d in P.items():
        for c in candidates(d):
            c['set'], c['clip'], c['vid'] = k[0], k[1], d['vid']; c['y'] = label(c, d['gt']); T.append(c)
    import pandas as pd
    df = pd.DataFrame(T); df.to_pickle('r3/cands.pkl')
    print(len(df), df.y.value_counts().to_dict())
    pd.set_option('display.width', 250)
    feats = ['n', 'sumc', 'maxc', 'nhi', 'bh', 'bhrel', 'frac', 'L', 'relx', 'rely', 'disp', 'rng', 'grow', 'dur', 'txtrng']
    print(df[df.y != 'IGN'].groupby('y')[feats].quantile([.1, .5, .9]).T.round(2))
    print(df.groupby(['vid', 'y']).size().unstack(fill_value=0))
    print(df[df.y != 'IGN'].groupby(['L', 'y']).size().unstack(fill_value=0))

"""候選驗證器：用候選特徵判斷「這個讀數是不是真的號碼牌號碼」。留一支影片交叉驗證（LOVO）＋留一片段（LOCO）。"""
import sys, json, collections, numpy as np, pandas as pd
sys.path.insert(0, 'src')
from r3_common import pool, ed
from evaluate import score_clip, summarize
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

F = ['n', 'sumc', 'maxc', 'nhi', 'bh', 'bhrel', 'frac', 'L', 'relx_abs', 'rely', 'disp', 'grow_log', 'dur_log', 'txtrng_log', 'n_log']
def feats(df):
    df = df.copy()
    df['relx_abs'] = (df.relx - 0.1).abs(); df['grow_log'] = np.log(df.grow.clip(0.2, 10)); df['dur_log'] = np.log1p(df.dur)
    df['txtrng_log'] = np.log1p(df.txtrng); df['n_log'] = np.log(df.n)
    return df

def resolve(cs, thr, merge_gap=4.0, sub_gap=3.0, ed_merge=True):
    """cs: 單一片段的候選（含 p）。回傳 [(bib,t,score)]"""
    acc = [c for c in cs if c['p'] >= thr]
    bytrk = collections.defaultdict(list)
    for c in acc: bytrk[str(c['key'])].append(c)
    keep = []
    for k, v in bytrk.items():
        v = sorted(v, key=lambda c: -c['p']); out = []
        for c in v:   # 同軌跡內：與已保留者為子字串或只差一位 → 視為同一個號碼的誤讀，丟掉
            if any((c['bib'] in o['bib'] or o['bib'] in c['bib'] or (ed_merge and len(c['bib']) == len(o['bib']) and ed(c['bib'], o['bib']) <= 1)) for o in out): continue
            out.append(c)
        keep += out
    keep.sort(key=lambda c: (c['bib'], c['t0'])); merged = []
    for c in keep:
        if merged and merged[-1]['bib'] == c['bib'] and c['t0'] - merged[-1]['t1'] <= merge_gap:
            m = merged[-1]; best = m if m['p'] >= c['p'] else c
            merged[-1] = dict(bib=m['bib'], t=best['t'], p=max(m['p'], c['p']), t0=min(m['t0'], c['t0']), t1=max(m['t1'], c['t1']), key=m['key'])
        else: merged.append(dict(bib=c['bib'], t=c['t'], p=c['p'], t0=c['t0'], t1=c['t1'], key=c['key']))
    final = [c for c in merged if not any(len(o['bib']) > len(c['bib']) and c['bib'] in o['bib'] and abs(o['t'] - c['t']) <= sub_gap and o['p'] >= 0.5 * c['p'] for o in merged)]
    return [(c['bib'], c['t'], c['p']) for c in final]

def e2e(df, P, thr, **kw):
    res = {}
    for (s, c), d in P.items():
        cs = df[(df['set'] == s) & (df['clip'] == c)].to_dict('records')
        res[(s, c)] = score_clip(resolve(cs, thr, **kw), d['gt'])
    return res

def model(kind):
    if kind == 'lr': return make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000, class_weight='balanced'))
    return GradientBoostingClassifier(n_estimators=120, max_depth=2, learning_rate=0.08, subsample=0.8, random_state=0)

if __name__ == '__main__':
    P = pool(); df = feats(pd.read_pickle('r3/cands.pkl')); df = df[df.L.between(2, 4)].reset_index(drop=True)
    tr = df.y != 'IGN'
    for kind in ['lr', 'gb']:
        for cv, grp in [('LOVO', df['vid']), ('LOCO', df['clip'])]:
            df['p'] = np.nan
            for g in grp.unique():
                m = model(kind).fit(df.loc[tr & (grp != g), F], (df.loc[tr & (grp != g), 'y'] == 'TP').astype(int))
                df.loc[grp == g, 'p'] = m.predict_proba(df.loc[grp == g, F])[:, 1]
            best = None
            for thr in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
                s = summarize(e2e(df, P, thr)); 
                if best is None or s['F1'] > best[1]['F1']: best = (thr, s)
                print(f'{kind} {cv} thr={thr}', s)
            res = e2e(df, P, best[0])
            print('  best', best, {v: summarize({k: r for k, r in res.items() if k[1].startswith(v)}) for v in ['v1', 'v2', 'v3']})
        if kind == 'lr':
            m = model('lr').fit(df.loc[tr, F], (df.loc[tr, 'y'] == 'TP').astype(int))
            print('  LR coef', dict(zip(F, m[-1].coef_[0].round(2))))

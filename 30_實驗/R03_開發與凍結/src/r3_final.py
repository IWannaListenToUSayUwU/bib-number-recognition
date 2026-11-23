"""第三輪最終版：以開發池（dev+test+test2）訓練候選驗證器（邏輯迴歸），權重存成 JSON（部署時不需 sklearn）。"""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, 'src')
from r3_verifier import F, feats, resolve, model
from r3_cands import candidates

def train(out='r3/verifier_v3.json'):
    df = feats(pd.read_pickle('r3/cands.pkl')); df = df[df.L.between(2, 4)]
    tr = df[df.y != 'IGN']
    m = model('lr').fit(tr[F], (tr.y == 'TP').astype(int))
    sc, lr = m[0], m[-1]
    J = dict(features=F, mean=sc.mean_.tolist(), scale=sc.scale_.tolist(), coef=lr.coef_[0].tolist(), intercept=float(lr.intercept_[0]),
             threshold=0.7, minlen=2, maxlen=4, min_conf=0.5, trained_on='dev+test+test2 (148 sure bibs, %d candidates)' % len(tr))
    json.dump(J, open(out, 'w'), indent=1); return J

def predict_clip(d, J):
    """d: dict(rows, persons) → [(bib, t, p)]"""
    cs = [c for c in candidates(d, min_conf=J['min_conf']) if J['minlen'] <= c['L'] <= J['maxlen']]
    if not cs: return []
    df = feats(pd.DataFrame(cs))
    X = (df[J['features']].values - np.array(J['mean'])) / np.array(J['scale'])
    df['p'] = 1 / (1 + np.exp(-(X @ np.array(J['coef']) + J['intercept'])))
    return resolve(df.to_dict('records'), J['threshold'])

if __name__ == '__main__':
    J = train(); print('trained', J['trained_on'], 'thr', J['threshold'])

"""第三輪共用：把三組已標註資料（dev/test/test2）合成開發池，統一讀取快取。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from aggregate2 import norm
SETS = {'dev': 'work/raw4/dev', 'test2': 'work/raw4/test2', 'test': 'work/raw8/test'}

def load_rows(path):
    """回傳 (text rows, person rows)。text row: t,tid,bbox,bh,txt,sc,pbox,ph；person row: t,tid,pbox"""
    rows, persons = [], []
    for l in open(path):
        r = json.loads(l)
        persons.append(dict(t=r['t'], tid=r['tid'], pbox=r['pbox']))
        for txt, sc, bb in (r.get('texts') or []):
            rows.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc, pbox=r['pbox'], ph=r['pbox'][3] - r['pbox'][1]))
    return rows, persons

def pool():
    """{(set,clip): dict(gt=, rows=, persons=, vid=)}"""
    P = {}
    for s, d in SETS.items():
        gt = json.load(open(f'work/gt_{s}.json'))
        for c, g in gt.items():
            p = f'{d}/{c}.jsonl'
            if not os.path.exists(p): continue
            rows, persons = load_rows(p)
            P[(s, c)] = dict(gt=g, rows=rows, persons=persons, vid=c.split('_')[0])
    return P

def ed(a, b):
    if a == b: return 0
    la, lb = len(a), len(b)
    d = list(range(lb + 1))
    for i in range(1, la + 1):
        p = d[:]; d[0] = i
        for j in range(1, lb + 1):
            d[j] = min(p[j] + 1, d[j - 1] + 1, p[j - 1] + (a[i - 1] != b[j - 1]))
    return d[lb]

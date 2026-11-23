"""第二輪 dev 比較：同一份 raw4 快取上，比較 (a) 不切軌跡 vs 切軌跡 (b) 固定位置過濾 開/關 (c) 門檻。"""
import sys, os, json, itertools
sys.path.insert(0, os.path.dirname(__file__))
from aggregate2 import load4, aggregate2
from evaluate import score_clip, summarize
which = sys.argv[1] if len(sys.argv) > 1 else 'dev'; raw = sys.argv[2] if len(sys.argv) > 2 else 'work/raw4'
gt = json.load(open(f'work/gt_{which}.json'))
clips = [c for c in gt if os.path.exists(f'{raw}/{which}/{c}.jsonl.done')]
data = {}
for c in clips:
    rows, _ = load4(f'{raw}/{which}/{c}.jsonl')
    raw_rows = [dict(r) for r in rows]
    tid2raw = {}
    for l in open(f'{raw}/{which}/{c}.jsonl'):
        j = json.loads(l); tid2raw[j['tid']] = j['rawtid']
    for r in raw_rows: r['tid'] = tid2raw.get(r['tid'], r['tid'])
    data[c] = {'split': rows, 'nosplit': raw_rows}
def run(mode, **kw):
    res = {c: score_clip([(p['bib'], p['t'], p['score']) for p in aggregate2(data[c][mode], **kw)], gt[c]) for c in clips}
    return summarize(res), res
print('clips', clips)
for mode, st in itertools.product(['nosplit', 'split'], [False, True]):
    s, res = run(mode, static=st)
    print(f'{mode:8s} static={st!s:5}', s)
for mc, ms in itertools.product([0.7, 0.8, 0.9], [0.5, 0.9, 1.5]):
    s, _ = run('split', static=True, min_conf=mc, min_score=ms)
    print(f'split static conf>={mc} score>={ms}', s)
s, res = run('split', static=True)
for c, r in res.items(): print(c, {k: r[k] for k in ['tp', 'fp', 'n', 'fn', 'fps']})

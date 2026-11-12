"""raw3 快取的評估：把每段文字轉成通用讀數格式後聚合。"""
import sys, os, json, itertools
sys.path.insert(0, os.path.dirname(__file__))
from aggregate import aggregate
from evaluate import score_clip, summarize
def load(path):
    out = []
    for l in open(path):
        r = json.loads(l)
        for txt, sc, bb in r['texts']:
            out.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, rap=(txt, sc), src='torso', ph=r['ph']))
    return out
if __name__ == '__main__':
    which = sys.argv[1]
    gt = json.load(open(f'work/gt_{which}.json'))
    clips = [c for c in gt if os.path.exists(f'work/raw3/{which}/{c}.jsonl.done')]
    rows = {c: load(f'work/raw3/{which}/{c}.jsonl') for c in clips}
    print('clips', clips)
    for mc, mv, ut, ml in itertools.product([0.5, 0.7, 0.85, 0.95], [1, 2], [True, False], [2, 3]):
        res = {c: score_clip(aggregate(rows[c], reader='rap', min_conf=mc, min_votes=mv, use_track=ut, minlen=ml, maxlen=4), gt[c]) for c in clips}
        print(f'conf>={mc} votes>={mv} track={ut!s:5} minlen={ml}', summarize(res))
    res = {c: score_clip(aggregate(rows[c], reader='rap', min_conf=0.85), gt[c]) for c in clips}
    for c, r in res.items():
        print(c, {k: r[k] for k in ['tp', 'fp', 'n', 'fn', 'fps']})

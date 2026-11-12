"""在快取上比較各種組合。用法：python src/bench.py dev [clip_prefix]"""
import sys, os, json, itertools, glob
sys.path.insert(0, os.path.dirname(__file__))
from aggregate import aggregate
from evaluate import score_clip, summarize
which = sys.argv[1]; raw = sys.argv[2] if len(sys.argv) > 2 else 'raw2'
gt = json.load(open(f'work/gt_{which}.json'))
clips = [c for c in gt if os.path.exists(f'work/{raw}/{which}/{c}.jsonl.done')]
rows = {c: [json.loads(l) for l in open(f'work/{raw}/{which}/{c}.jsonl')] for c in clips}
def run(**kw):
    res = {c: score_clip(aggregate(rows[c], **kw), gt[c]) for c in clips}
    return summarize(res), res
if __name__ == '__main__':
    print('clips:', clips)
    SRC = {'all': None, 'rbnr_full': {'rbnr_full'}, 'rbnr_torso': {'rbnr_torso'}, 'white': {'white'}, 'rbnr*': {'rbnr_full', 'rbnr_torso'}}
    for (sn, sv), reader in itertools.product(SRC.items(), ['rap', 'ez', 'svhn', 'rap+ez', 'rap+ez+svhn']):
        for mc in [0.3, 0.6]:
            s, _ = run(reader=reader, srcs=sv, min_conf=mc)
            print(f'{sn:10s} {reader:12s} conf>={mc}  {s}')

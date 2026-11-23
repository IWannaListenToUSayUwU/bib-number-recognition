"""文字行裁切快取：依現有快取的文字框，從影片重新裁出每個文字行（加邊界），供辨識器變體離線比較。"""
import sys, os, json, cv2, collections
sys.path.insert(0, 'src')
from frames import iter_frames
from r3_common import SETS
def build(setname, clip, rawdir, outdir, fps=8, mx=0.15, my=0.30):
    os.makedirs(outdir, exist_ok=True)
    vid, start = clip.split('_'); start = int(start)
    L = {'v1': 60, 'v2': 30, 'v3': 60}[vid]
    byt = collections.defaultdict(list); n = 0
    for li, l in enumerate(open(f'{rawdir}/{clip}.jsonl')):
        r = json.loads(l)
        for ti, (txt, sc, bb) in enumerate(r.get('texts') or []):
            byt[round(r['t'], 3)].append(dict(id=f'{li}_{ti}', t=r['t'], tid=r['tid'], pbox=r['pbox'], bbox=bb, txt=txt, sc=sc))
    idx = []
    for t, f in iter_frames(vid, start, start + L, fps=fps):
        for it in byt.get(round(t, 3), []):
            x1, y1, x2, y2 = it['bbox']; w, h = x2 - x1, y2 - y1
            X1 = max(0, int(x1 - mx * w)); X2 = min(f.shape[1], int(x2 + mx * w)); Y1 = max(0, int(y1 - my * h)); Y2 = min(f.shape[0], int(y2 + my * h))
            c = f[Y1:Y2, X1:X2]
            if c.size == 0: continue
            cv2.imwrite(f'{outdir}/{it["id"]}.png', c); it['crop'] = [X1, Y1, X2, Y2]; idx.append(it); n += 1
    json.dump(idx, open(f'{outdir}/index.json', 'w'))
    tot = sum(len(v) for v in byt.values())
    print(setname, clip, f'{n}/{tot} crops', flush=True)
if __name__ == '__main__':
    which = sys.argv[1:] or list(SETS)
    for s in which:
        d = SETS.get(s, f'work/raw4/{s}')
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.jsonl') and os.path.exists(f'{d}/{fn}.done'):
                clip = fn[:-6]
                if not os.path.exists(f'r3/crops/{s}/{clip}/index.json'): build(s, clip, d, f'r3/crops/{s}/{clip}')

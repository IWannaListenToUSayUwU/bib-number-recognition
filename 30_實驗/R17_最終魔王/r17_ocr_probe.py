r"""R17 事前量測：OCR 前處理（抗逆光／反光）有沒有用？不跑完整流程，只在「答案已知」的軀幹圖上比較。
答案：開發段的過線事件，用 offsets.json 換成槍聲時間後，±1 秒內「只有一位」官方完賽者 → 這個事件的真實號碼就是他。
取那條軌跡人框高度 ≥ min_ph 的格子（最多 per_track 張，平均分布），用和 extract9 相同的軀幹裁切，對每種前處理各 OCR 一次。
用法：python 30_實驗/R17_最終魔王/r17_ocr_probe.py <標籤> [--gpu] [--per 6] [--minph 90]
輸出：out/<標籤>/ocr_probe.json（每種前處理：單張讀對率、軌跡至少讀對一次的比例、讀出錯號碼率）"""
import sys, os, json, csv, glob, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
ORT126 = r'C:\Users\ShiLaCow\bibread_ortgpu\ort126'
GPU = '--gpu' in sys.argv
if GPU: sys.path.insert(0, ORT126)
import torch  # noqa
import cv2, numpy as np  # noqa
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src'))
from extract9 import preprocess  # noqa
from rapidocr_onnxruntime import RapidOCR  # noqa
VIDEO = os.path.join(ROOT, '00_原始素材', '最終魔王', '2026 10 04 2026新屋魚米之鄉馬拉松終點 GP020205.mp4')
D = re.compile(r'\d+')
VARIANTS = [None, 'clahe', 'gamma', 'clahe_up', 'lowdet', 'lowdet_up']   # lowdet＝文字偵測門檻降低（det_thresh 0.3→0.2、det_box_thresh 0.5→0.3）


def arg(k, d):
    return type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d


def main():
    tag = [a for a in sys.argv[1:] if not a.startswith('--') and not a.replace('.', '').isdigit()][0]
    per, minph = arg('--per', 6), arg('--minph', 90)
    offs = json.load(open(os.path.join(HERE, 'offsets.json'), encoding='utf-8'))['offsets']
    off_rows = []
    for race in offs:
        for r in json.load(open(os.path.join(HERE, '官方成績', f'官方_{race}.json'), encoding='utf-8'))['rows']:
            off_rows.append((r['t'] - offs[race]['offset'], r['bib']))
    items = []
    src = json.load(open(os.path.join(HERE, 'out', tag, 'run_info.json'), encoding='utf-8')).get('replay_of', tag)
    for d in sorted(glob.glob(os.path.join(HERE, 'out', tag, 'seg_*'))):
        rows = [json.loads(l) for l in open(os.path.join(HERE, 'out', src, os.path.basename(d), 'raw.jsonl'), encoding='utf-8')]
        by = {}
        for r in rows: by.setdefault(r['tid'], []).append(r)
        for e in csv.DictReader(open(os.path.join(d, 'events.csv'), encoding='utf-8')):
            t = float(e['t_cross']); c = [b for tt, b in off_rows if abs(tt - t) <= 1.0]
            if len(c) != 1: continue
            tr = [r for r in by.get(int(e['vid']), []) if r['ph'] >= minph]
            if not tr: continue
            pick = [tr[int(i)] for i in np.linspace(0, len(tr) - 1, min(per, len(tr)))]
            items.append(dict(seg=os.path.basename(d), t=t, truth=c[0], sys_bib=e['bib'], frames=[(r['t'], r['pbox']) for r in pick]))
    print('有唯一答案、且有近距離畫面的過線事件：', len(items), flush=True)
    gk = {f'{m}_use_cuda': True for m in ('det', 'cls', 'rec')} if GPU else {}
    ocr = RapidOCR(**gk); ocr_low = RapidOCR(**gk, det_thresh=0.2, det_box_thresh=0.3)
    cap = cv2.VideoCapture(VIDEO)
    res = {str(v): dict(crops=0, ok=0, wrong=0, tracks_ok=0) for v in VARIANTS}
    detail = []
    for it in items:
        tok = {str(v): False for v in VARIANTS}
        for t, (x1, y1, x2, y2) in it['frames']:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read()
            if not ok: continue
            h = y2 - y1; w = x2 - x1
            cx1 = max(0, x1 - int(.08 * w)); cx2 = min(f.shape[1], x2 + int(.08 * w))
            cy1 = max(0, y1 + int(.22 * h)); cy2 = min(f.shape[0], y1 + int(.72 * h))
            crop = f[cy1:cy2, cx1:cx2]
            if crop.size == 0: continue
            for v in VARIANTS:
                eng = ocr_low if v and v.startswith('lowdet') else ocr
                pv = {'lowdet': None, 'lowdet_up': 'clahe_up'}.get(v, v)
                img, _ = preprocess(crop, pv); out, _ = eng(img, use_cls=False)
                digs = [max(D.findall(x[1].replace(' ', '')), key=len) for x in (out or []) if D.findall(x[1].replace(' ', '')) and float(x[2]) >= 0.5]
                long5 = [x for x in digs if len(x) >= 4]
                k = str(v); res[k]['crops'] += 1
                if it['truth'] in digs: res[k]['ok'] += 1; tok[k] = True
                elif any(len(x) == 5 for x in long5): res[k]['wrong'] += 1
        for k in tok: res[k]['tracks_ok'] += tok[k]
        detail.append(dict(it, ok=tok))
    n = len(items)
    for k, r in res.items():
        r['crop_ok_rate'] = round(r['ok'] / r['crops'], 3) if r['crops'] else None
        r['crop_wrong5_rate'] = round(r['wrong'] / r['crops'], 3) if r['crops'] else None
        r['track_ok_rate'] = round(r['tracks_ok'] / n, 3) if n else None
        print(f"{k:9s} 單張讀對 {r['ok']}/{r['crops']} = {r['crop_ok_rate']}｜讀出錯的 5 碼 {r['crop_wrong5_rate']}｜軌跡至少對一次 {r['tracks_ok']}/{n} = {r['track_ok_rate']}", flush=True)
    sys_ok = sum(1 for it in items if it['sys_bib'] == it['truth'])
    print(f'（對照）系統這些事件最後輸出正確號碼：{sys_ok}/{n}')
    json.dump(dict(tag=tag, gpu=GPU, per=per, minph=minph, n_events=n, system_correct=sys_ok, variants=res, detail=detail),
              open(os.path.join(HERE, 'out', tag, 'ocr_probe.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

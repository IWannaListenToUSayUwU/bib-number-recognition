"""逐格抽取 v4（第二輪）：OCR 行為與 extract3 相同，另外加入「編號轉移偵測」。
每條 ByteTrack 軌跡持續追蹤軀幹顏色直方圖與位置；顏色突變或位置瞬間跳動 → 切成新的虛擬軌跡（vid），
並重置提早停止計數，讓換上來的人重新被辨識。每位人物每格都記錄一列（未做 OCR 時 texts=None）。"""
import sys, os, json, time, re, cv2, numpy as np
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR
D = re.compile(r'\d+')

def torso_hist(crop):
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [16, 4], [0, 180, 0, 256]).flatten()
    return h / (h.sum() + 1e-9)

def bhatt(a, b):
    return float(np.sqrt(max(0.0, 1 - np.sum(np.sqrt(a * b)))))

MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')

def process(frame_iter, fps=8, imgsz=960, min_h=100, top=0.22, bot=0.72, early_stop=3, hist_thr=0.45, jump_thr=0.8, stats=None):
    det = YOLO(os.path.join(MODELS, 'yolo11s.pt'))
    nt = int(os.environ.get('BIB_OCR_THREADS', '0'))   # 平行執行時限制每個行程的 OCR 執行緒（只影響速度，不影響結果邏輯）
    kw = {f'{m}_{k}': nt for m in ('det', 'cls', 'rec') for k in ('intra_op_num_threads',)} if nt > 0 else {}
    if nt > 0:
        kw.update({f'{m}_inter_op_num_threads': 1 for m in ('det', 'cls', 'rec')})
    ocr = RapidOCR(**kw)
    nf = 0; nocr = 0; nsplit = 0
    good = defaultdict(Counter)
    state = {}          # tid -> dict(vid, hist, box, t)
    nextv = defaultdict(int)
    for t, f in frame_iter:
        nf += 1
        r = det.track(f, classes=[0], conf=0.2, imgsz=imgsz, persist=True, tracker='bytetrack.yaml', verbose=False)[0]
        if r.boxes is None or len(r.boxes) == 0:
            continue
        ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [-1] * len(r.boxes)
        for tid, b in zip(ids, r.boxes.xyxy.tolist()):
            x1, y1, x2, y2 = map(int, b); h = y2 - y1; w = x2 - x1
            if h < min_h:
                continue
            cx1 = max(0, x1 - int(.08 * w)); cx2 = min(f.shape[1], x2 + int(.08 * w))
            cy1 = max(0, y1 + int(top * h)); cy2 = min(f.shape[0], y1 + int(bot * h))
            crop = f[cy1:cy2, cx1:cx2]
            if crop.size == 0 or crop.shape[0] < 10:
                continue
            hist = torso_hist(crop)
            # --- 編號轉移偵測 ---
            st = state.get(tid)
            split = False
            if st is not None and tid >= 0:
                d = bhatt(hist, st['hist'])
                pcx, pcy = (st['box'][0] + st['box'][2]) / 2, (st['box'][1] + st['box'][3]) / 2
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                gap_frames = max(1, round((t - st['t']) * fps))
                jump = np.hypot(cx - pcx, cy - pcy) / max(w, st['box'][2] - st['box'][0]) / gap_frames
                if d > hist_thr or jump > jump_thr:
                    split = True
            if st is None or split:
                if split:
                    nsplit += 1
                nextv[tid] += 1
                v = tid * 1000 + nextv[tid] if tid >= 0 else -1
                state[tid] = dict(vid=v, hist=hist, box=(x1, y1, x2, y2), t=t)
            else:
                st['hist'] = 0.8 * st['hist'] + 0.2 * hist; st['box'] = (x1, y1, x2, y2); st['t'] = t
            v = state[tid]['vid']
            texts = None
            if not (v >= 0 and good[v] and good[v].most_common(1)[0][1] >= early_stop):
                res, _ = ocr(crop, use_cls=False); nocr += 1
                texts = []
                for box, txt, sc in res or []:
                    xs = [p[0] for p in box]; ys = [p[1] for p in box]
                    texts.append([txt, round(float(sc), 3), [int(cx1 + min(xs)), int(cy1 + min(ys)), int(cx1 + max(xs)), int(cy1 + max(ys))]])
                    d_ = D.findall(txt.replace(' ', ''))
                    if d_ and float(sc) >= 0.9 and v >= 0:
                        good[v][max(d_, key=len)] += 1
            yield dict(t=round(t, 3), tid=v, rawtid=tid, pbox=[x1, y1, x2, y2], ph=h, split=split, texts=texts)
        if stats is not None:
            stats.update(frames=nf, ocr=nocr, splits=nsplit)

def run(vid, s, e, out, fps=8, **kw):
    t0 = time.time(); st = {}
    with open(out, 'w') as fo:
        for row in process(iter_frames(vid, s, e, fps=fps), fps=fps, stats=st, **kw):
            fo.write(json.dumps(row) + '\n')
    print(vid, s, st, f'{time.time() - t0:.0f}s', flush=True)

if __name__ == '__main__':
    # 用法：python extract4.py OUTDIR vid:start:end [vid:start:end ...]
    outdir = sys.argv[1]; os.makedirs(outdir, exist_ok=True)
    for spec in sys.argv[2:]:
        v, a, b = spec.split(':')
        o = f'{outdir}/{v}_{a}.jsonl'
        if os.path.exists(o + '.done'):
            continue
        run(v, float(a), float(b), o); open(o + '.done', 'w').close()

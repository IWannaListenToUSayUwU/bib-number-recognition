"""逐格抽取 v5（方法 3：不提早停止，改挑最清晰的幾張）。
人物偵測、ByteTrack、編號轉移偵測與 extract4 相同。差別：
- 不再逐格 OCR；每條（虛擬）軌跡暫存每格的軀幹裁切，計算品質分數
  品質 = (框高 / 該軌跡最大框高) × (清晰度 / 該軌跡最大清晰度)，清晰度 = 縮到高 128 後的拉普拉斯變異數
- 軌跡消失超過 gap 秒（或影片結束）時，依品質挑前 top_k 張（彼此至少相隔 min_sep 秒）做 OCR
- 每張 OCR 結果記錄品質排名 rank（0 = 最好），之後可離線模擬只用前 K 張
輸出格式與 extract4 相容：人物列（texts=None）＋ OCR 列（texts=[...]，附 rank、q）。"""
import sys, os, json, time, re, cv2, numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR
from extract4 import torso_hist, bhatt, MODELS

def sharpness(crop):
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    s = 128 / g.shape[0]
    g = cv2.resize(g, (max(8, int(g.shape[1] * s)), 128), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())

def process(frame_iter, fps=8, imgsz=960, min_h=100, top=0.22, bot=0.72, hist_thr=0.45, jump_thr=0.8,
            top_k=12, min_sep=0.25, gap=1.0, select='quality', stats=None, **_ignored):
    det = YOLO(os.path.join(MODELS, 'yolo11s.pt'))
    nt = int(os.environ.get('BIB_OCR_THREADS', '0'))
    kw = {f'{m}_intra_op_num_threads': nt for m in ('det', 'cls', 'rec')} if nt > 0 else {}
    ocr = RapidOCR(**kw)
    state = {}; nextv = defaultdict(int)
    buf = defaultdict(list)       # vid -> [(t, crop, (cx1,cy1), h, sharp, pbox)]
    last_seen = {}
    nf = nocr = nsplit = 0

    def flush(v):
        nonlocal nocr
        items = buf.pop(v, []); last_seen.pop(v, None)
        if not items: return []
        mh = max(x[3] for x in items); ms = max(x[4] for x in items) or 1.0
        if select == 'bins':
            # 依時間平均切成 top_k 段，每段挑清晰度最高的一張（只在相近時間內比較清晰度）
            items = sorted(items, key=lambda x: x[0]); n = len(items); chosen = []
            for b in range(min(top_k, n)):
                seg = items[b * n // min(top_k, n):(b + 1) * n // min(top_k, n)]
                if seg:
                    x = max(seg, key=lambda z: z[4]); chosen.append((x[4] / ms, x))
            chosen.sort(key=lambda c: -c[0])
        else:
            scored = sorted(((x[3] / mh) * (x[4] / ms), x) for x in items)[::-1]
            chosen = []
            for q, x in scored:
                if all(abs(x[0] - c[1][0]) >= min_sep - 1e-6 for c in chosen):
                    chosen.append((q, x))
                if len(chosen) >= top_k: break
        out = []
        for rank, (q, (t, crop, (cx1, cy1), h, sh, pbox)) in enumerate(chosen):
            res, _ = ocr(crop, use_cls=False); nocr += 1
            texts = []
            for box, txt, sc in res or []:
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                texts.append([txt, round(float(sc), 3), [int(cx1 + min(xs)), int(cy1 + min(ys)), int(cx1 + max(xs)), int(cy1 + max(ys))]])
            out.append(dict(t=round(t, 3), tid=v, pbox=pbox, ph=h, texts=texts, rank=rank, q=round(q, 4)))
        return out

    for t, f in frame_iter:
        nf += 1
        r = det.track(f, classes=[0], conf=0.2, imgsz=imgsz, persist=True, tracker='bytetrack.yaml', verbose=False)[0]
        ids = r.boxes.id.int().tolist() if (r.boxes is not None and r.boxes.id is not None) else ([-1] * len(r.boxes) if r.boxes is not None else [])
        boxes = r.boxes.xyxy.tolist() if r.boxes is not None else []
        for tid, b in zip(ids, boxes):
            x1, y1, x2, y2 = map(int, b); h = y2 - y1; w = x2 - x1
            if h < min_h: continue
            cx1 = max(0, x1 - int(.08 * w)); cx2 = min(f.shape[1], x2 + int(.08 * w))
            cy1 = max(0, y1 + int(top * h)); cy2 = min(f.shape[0], y1 + int(bot * h))
            crop = f[cy1:cy2, cx1:cx2]
            if crop.size == 0 or crop.shape[0] < 10: continue
            hist = torso_hist(crop); st = state.get(tid); split = False
            if st is not None and tid >= 0:
                d = bhatt(hist, st['hist'])
                pcx, pcy = (st['box'][0] + st['box'][2]) / 2, (st['box'][1] + st['box'][3]) / 2
                gapf = max(1, round((t - st['t']) * fps))
                jump = np.hypot((x1 + x2) / 2 - pcx, (y1 + y2) / 2 - pcy) / max(w, st['box'][2] - st['box'][0]) / gapf
                split = bool(d > hist_thr or jump > jump_thr)
            if st is None or split:
                if split:
                    nsplit += 1
                    for row in flush(st['vid']): yield row
                nextv[tid] += 1
                v = tid * 1000 + nextv[tid] if tid >= 0 else -1
                state[tid] = dict(vid=v, hist=hist, box=(x1, y1, x2, y2), t=t)
            else:
                st['hist'] = 0.8 * st['hist'] + 0.2 * hist; st['box'] = (x1, y1, x2, y2); st['t'] = t
            v = state[tid]['vid']
            yield dict(t=round(t, 3), tid=v, rawtid=tid, pbox=[x1, y1, x2, y2], ph=h, split=split, texts=None)
            if v < 0:
                continue
            buf[v].append((t, crop.copy(), (cx1, cy1), h, sharpness(crop), [x1, y1, x2, y2])); last_seen[v] = t
            if len(buf[v]) > 120:   # 記憶體保護：只留品質（框高）最大的 120 張
                buf[v].sort(key=lambda x: -x[3]); buf[v] = buf[v][:120]
        for v in [v for v, ls in last_seen.items() if t - ls > gap]:
            for row in flush(v): yield row
        if stats is not None: stats.update(frames=nf, ocr=nocr, splits=nsplit)
    for v in list(buf):
        for row in flush(v): yield row
    if stats is not None: stats.update(frames=nf, ocr=nocr, splits=nsplit)

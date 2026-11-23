"""逐格抽取 v2：人物+追蹤 → 三種號碼牌定位 → 三種辨識器。全部寫入快取供離線比較。"""
import sys, os, json, time, cv2, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
from bibdet import bib_detector, digit_detector, read_digits
from whitepatch import white_patches
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR
import easyocr

def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1]); x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x2 - x1) * max(0, y2 - y1)
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)

def run(vid, s, e, out, fps=5, imgsz=960, min_h=80):
    det = YOLO('models/yolo11s.pt'); bd = bib_detector(); dd = digit_detector()
    ocr = RapidOCR(det_limit_side_len=416, det_limit_type='max')
    ez = easyocr.Reader(['en'], gpu=False, verbose=False, model_storage_directory='models/easyocr')
    fo = open(out, 'w'); t0 = time.time(); nf = 0
    for t, f in iter_frames(vid, s, e, fps=fps):
        nf += 1
        r = det.track(f, classes=[0], conf=0.2, imgsz=imgsz, persist=True, tracker='bytetrack.yaml', verbose=False)[0]
        ff = [(x, y, x + w, y + h, sc) for (x, y, w, h), sc, _ in bd(f, conf=0.2, size=960)]   # RBNR 全畫面
        if r.boxes is None or len(r.boxes) == 0:
            continue
        ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [-1] * len(r.boxes)
        cands = []   # (src, tid, pbox, bibbox_in_frame, score)
        for tid, b in zip(ids, r.boxes.xyxy.tolist()):
            x1, y1, x2, y2 = map(int, b); h = y2 - y1; w = x2 - x1
            if h < min_h:
                continue
            cx1 = max(0, x1 - int(.1 * w)); cx2 = min(f.shape[1], x2 + int(.1 * w))
            cy1 = max(0, y1 + int(.08 * h)); cy2 = min(f.shape[0], y1 + int(.75 * h))
            crop = f[cy1:cy2, cx1:cx2]
            if crop.size == 0:
                continue
            sc = 416 / max(crop.shape[:2]); up = cv2.resize(crop, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
            for (bx, by, bw, bh), bs, _ in bd(up, conf=0.2, size=416):
                cands.append(('rbnr_torso', tid, [x1, y1, x2, y2], [cx1 + bx / sc, cy1 + by / sc, cx1 + (bx + bw) / sc, cy1 + (by + bh) / sc], bs))
            for (bx, by, bw, bh), ws in white_patches(up):
                cands.append(('white', tid, [x1, y1, x2, y2], [cx1 + bx / sc, cy1 + by / sc, cx1 + (bx + bw) / sc, cy1 + (by + bh) / sc], ws))
            for fx1, fy1, fx2, fy2, fs in ff:   # 全畫面偵測結果，中心落在此人上半身才歸給他
                mx, my = (fx1 + fx2) / 2, (fy1 + fy2) / 2
                if cx1 <= mx <= cx2 and cy1 <= my <= cy2:
                    cands.append(('rbnr_full', tid, [x1, y1, x2, y2], [fx1, fy1, fx2, fy2], fs))
        for src, tid, pb, bb, bs in cands:
            X1, Y1, X2, Y2 = bb; ow, oh = X2 - X1, Y2 - Y1; p = 0.12
            X1 = int(max(0, X1 - p * ow)); Y1 = int(max(0, Y1 - p * oh)); X2 = int(min(f.shape[1], X2 + p * ow)); Y2 = int(min(f.shape[0], Y2 + p * oh))
            bc = f[Y1:Y2, X1:X2]
            if bc.size == 0 or bc.shape[0] < 6 or bc.shape[1] < 6:
                continue
            k = 64 / bc.shape[0]; bc2 = cv2.resize(bc, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
            rr, _ = ocr(bc2, use_det=False, use_cls=False, use_rec=True)
            rap = (rr[0][0], float(rr[0][1])) if rr else ('', 0.0)
            ezr = ez.recognize(cv2.cvtColor(bc2, cv2.COLOR_BGR2GRAY), allowlist='0123456789', detail=1)
            ezo = (ezr[0][1], float(ezr[0][2])) if ezr else ('', 0.0)
            sv, svc = read_digits(dd, bc2)
            fo.write(json.dumps(dict(t=round(t, 3), tid=tid, src=src, pbox=pb, bbox=[X1, Y1, X2, Y2], bconf=round(float(bs), 3),
                                     bw=X2 - X1, bh=Y2 - Y1, rap=rap, ez=ezo, svhn=(sv or '', round(svc, 3)))) + '\n')
        fo.flush()
    fo.close()
    print(vid, s, f'{nf} frames {time.time() - t0:.0f}s', flush=True)

if __name__ == '__main__':
    split = json.load(open('work/split.json'))
    which = sys.argv[1]; vids = sys.argv[2].split(','); fps = float(sys.argv[3]) if len(sys.argv) > 3 else 5
    os.makedirs(f'work/raw2/{which}', exist_ok=True)
    for v in vids:
        for c in split[v][which]:
            o = f'work/raw2/{which}/{v}_{c["start"]}.jsonl'
            if os.path.exists(o + '.done'):
                continue
            run(v, c['start'], c['end'], o, fps=fps); open(o + '.done', 'w').close()

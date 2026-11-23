"""逐格抽取原始讀數（快取）：人物偵測+追蹤 → 上半身放大 → 號碼牌偵測 → 多種辨識器。
輸出 JSONL：每格每人一筆，含 track id、人物框、號碼牌框、各辨識器讀數與信心。"""
import sys, os, json, time, cv2, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
from bibdet import bib_detector, digit_detector, read_digits
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR

def run(vid, s, e, out, fps=5, person_model='models/yolo11s.pt', imgsz=960, min_h=80):
    det = YOLO(person_model); bd = bib_detector(); dd = digit_detector(); ocr = RapidOCR()
    fo = open(out, 'w'); t_start = time.time(); nf = 0
    for t, f in iter_frames(vid, s, e, fps=fps):
        nf += 1
        r = det.track(f, classes=[0], conf=0.2, imgsz=imgsz, persist=True, tracker='bytetrack.yaml', verbose=False)[0]
        if r.boxes is None or len(r.boxes) == 0:
            continue
        ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [-1] * len(r.boxes)
        for tid, b, pc in zip(ids, r.boxes.xyxy.tolist(), r.boxes.conf.tolist()):
            x1, y1, x2, y2 = map(int, b); h = y2 - y1; w = x2 - x1
            if h < min_h:
                continue
            # 上半身（頭下到大腿），左右各放寬 10%
            cx1 = max(0, x1 - int(.1 * w)); cx2 = min(f.shape[1], x2 + int(.1 * w))
            cy1 = max(0, y1 + int(.08 * h)); cy2 = min(f.shape[0], y1 + int(.75 * h))
            crop = f[cy1:cy2, cx1:cx2]
            if crop.size == 0:
                continue
            sc = 416 / max(crop.shape[:2])
            up = cv2.resize(crop, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC if sc > 1 else cv2.INTER_AREA)
            bibs = bd(up, conf=0.2, size=416)
            for (bx, by, bw, bh), bs, _ in bibs:
                # 回到原圖座標，從原圖重裁（避免二次插值），放大到高 64
                ox1 = cx1 + bx / sc; oy1 = cy1 + by / sc; ow = bw / sc; oh = bh / sc
                p = 0.12
                X1 = int(max(0, ox1 - p * ow)); Y1 = int(max(0, oy1 - p * oh))
                X2 = int(min(f.shape[1], ox1 + ow * (1 + p))); Y2 = int(min(f.shape[0], oy1 + oh * (1 + p)))
                bc = f[Y1:Y2, X1:X2]
                if bc.size == 0 or bc.shape[0] < 6:
                    continue
                k = 64 / bc.shape[0]
                bc2 = cv2.resize(bc, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
                rr, _ = ocr(bc2, use_det=False, use_cls=False, use_rec=True)
                rap = (rr[0][0], float(rr[0][1])) if rr else ('', 0.0)
                rd, _ = ocr(bc2)   # det+rec 版本：可切出號碼牌內的數字行
                rapd = [(x[1], float(x[2])) for x in (rd or [])]
                sv, svc = read_digits(dd, bc2)
                rec = dict(t=round(t, 3), tid=tid, pbox=[x1, y1, x2, y2], pconf=round(pc, 3),
                           bbox=[X1, Y1, X2, Y2], bconf=round(bs, 3), bw=X2 - X1, bh=Y2 - Y1,
                           rap=rap, rapd=rapd, svhn=(sv or '', round(svc, 3)))
                fo.write(json.dumps(rec) + '\n')
    fo.close()
    print(vid, s, f'{nf} frames {time.time() - t_start:.0f}s', flush=True)

if __name__ == '__main__':
    split = json.load(open('work/split.json'))
    which = sys.argv[1]; vids = sys.argv[2].split(','); fps = float(sys.argv[3]) if len(sys.argv) > 3 else 5
    os.makedirs(f'work/raw/{which}', exist_ok=True)
    for v in vids:
        for c in split[v][which]:
            run(v, c['start'], c['end'], f'work/raw/{which}/{v}_{c["start"]}.jsonl', fps=fps)

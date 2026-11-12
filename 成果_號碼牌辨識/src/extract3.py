"""逐格抽取 v3：人物+追蹤 → 軀幹裁切（避開頭部）→ RapidOCR 預設偵測+辨識（放大至短邊 736）。
加速：只處理框高 >= min_h 的人；同一軌跡已有 3 次一致的高信心讀數就跳過。"""
import sys, os, json, time, re, cv2
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR
D = re.compile(r'\d+')

def run(vid, s, e, out, fps=4, imgsz=960, min_h=100, top=0.22, bot=0.72, early_stop=3):
    det = YOLO('models/yolo11s.pt'); ocr = RapidOCR()
    fo = open(out, 'w'); t0 = time.time(); nf = 0; nocr = 0
    good = defaultdict(Counter)
    for t, f in iter_frames(vid, s, e, fps=fps):
        nf += 1
        r = det.track(f, classes=[0], conf=0.2, imgsz=imgsz, persist=True, tracker='bytetrack.yaml', verbose=False)[0]
        if r.boxes is None or len(r.boxes) == 0:
            continue
        ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [-1] * len(r.boxes)
        for tid, b in zip(ids, r.boxes.xyxy.tolist()):
            x1, y1, x2, y2 = map(int, b); h = y2 - y1; w = x2 - x1
            if h < min_h:
                continue
            if tid >= 0 and good[tid] and good[tid].most_common(1)[0][1] >= early_stop:
                continue
            cx1 = max(0, x1 - int(.08 * w)); cx2 = min(f.shape[1], x2 + int(.08 * w))
            cy1 = max(0, y1 + int(top * h)); cy2 = min(f.shape[0], y1 + int(bot * h))
            crop = f[cy1:cy2, cx1:cx2]
            if crop.size == 0 or crop.shape[0] < 10:
                continue
            res, _ = ocr(crop, use_cls=False); nocr += 1
            texts = []
            for box, txt, sc in res or []:
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                texts.append([txt, round(float(sc), 3), [int(cx1 + min(xs)), int(cy1 + min(ys)), int(cx1 + max(xs)), int(cy1 + max(ys))]])
                d = D.findall(txt.replace(' ', ''))
                if d and float(sc) >= 0.9 and tid >= 0:
                    good[tid][max(d, key=len)] += 1
            fo.write(json.dumps(dict(t=round(t, 3), tid=tid, pbox=[x1, y1, x2, y2], ph=h, texts=texts)) + '\n')
        fo.flush()
    fo.close()
    print(vid, s, f'{nf} frames, {nocr} ocr calls, {time.time() - t0:.0f}s', flush=True)

if __name__ == '__main__':
    split = json.load(open('work/split.json'))
    which = sys.argv[1]; vids = sys.argv[2].split(','); fps = float(sys.argv[3]) if len(sys.argv) > 3 else 4
    os.makedirs(f'work/raw3/{which}', exist_ok=True)
    for v in vids:
        for c in split[v][which]:
            o = f'work/raw3/{which}/{v}_{c["start"]}.jsonl'
            if os.path.exists(o + '.done'):
                continue
            run(v, c['start'], c['end'], o, fps=fps); open(o + '.done', 'w').close()

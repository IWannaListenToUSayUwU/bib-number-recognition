"""只在 GT 號碼出現的時間窗內比較 OCR 變體（dev 集）。
指標：hit_any = 該號碼在窗內被讀到過（任何信心）；hit85 = 信心>=0.85 讀到；noise = 窗內非 GT 的 2~4 位數字讀數數量。"""
import sys, os, json, re, time, cv2, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR
import easyocr
D = re.compile(r'\d+')
MASK = {'v2': [(110, 555, 345, 680), (935, 565, 1195, 675)], 'v3': [(30, 25, 300, 115), (100, 655, 1180, 715)], 'v1': []}

def norm(t):
    m = D.findall(t.replace(' ', '')); return max(m, key=len) if m else ''

def clahe(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB); l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

V = {
 'V0_default': dict(kw={}, pre=None, up=1.0),
 'V1_lowthr': dict(kw=dict(det_box_thresh=0.3, det_thresh=0.2, det_unclip_ratio=2.0), pre=None, up=1.0),
 'V2_lowthr_clahe': dict(kw=dict(det_box_thresh=0.3, det_thresh=0.2, det_unclip_ratio=2.0), pre=clahe, up=1.0),
 'V3_lowthr_1024': dict(kw=dict(det_box_thresh=0.3, det_thresh=0.2, det_unclip_ratio=2.0, det_limit_side_len=1024), pre=None, up=1.0),
 'V4_easyocr': dict(easy=True),
}
def main():
    gt = json.load(open('work/gt_dev.json')); split = json.load(open('work/split.json'))
    det = YOLO('models/yolo11s.pt')
    eng = {k: (RapidOCR(**v['kw']) if not v.get('easy') else easyocr.Reader(['en'], gpu=False, verbose=False, model_storage_directory='models/easyocr')) for k, v in V.items()}
    stats = {k: dict(hit_any=0, hit85=0, n=0, noise=0, sec=0.0) for k in V}
    per = []
    for clip, g in gt.items():
        vid = clip.split('_')[0]
        for s in g['sure']:
            reads = {k: [] for k in V}
            for t, f in iter_frames(vid, s['t0'] - 0.5, s['t1'] + 0.5, fps=4):
                f = f.copy()
                for x1, y1, x2, y2 in MASK[vid]:
                    f[y1:y2, x1:x2] = 127
                r = det.predict(f, classes=[0], conf=0.2, imgsz=960, verbose=False)[0]
                for b in r.boxes.xyxy.tolist():
                    x1, y1, x2, y2 = map(int, b); h = y2 - y1; w = x2 - x1
                    if h < 100: continue
                    crop = f[max(0, y1 + int(.22 * h)):y1 + int(.72 * h), max(0, x1 - int(.08 * w)):x2 + int(.08 * w)]
                    if crop.size == 0: continue
                    for k, v in V.items():
                        t0 = time.time()
                        if v.get('easy'):
                            res = eng[k].readtext(cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), allowlist='0123456789')
                            out = [(txt, float(sc)) for _, txt, sc in res]
                        else:
                            im = v['pre'](crop) if v['pre'] else crop
                            res, _ = eng[k](im, use_cls=False)
                            out = [(txt, float(sc)) for _, txt, sc in (res or [])]
                        stats[k]['sec'] += time.time() - t0
                        reads[k] += [(norm(a), c) for a, c in out]
            for k in V:
                st = stats[k]; st['n'] += 1
                ok = [c for a, c in reads[k] if a == s['bib']]
                st['hit_any'] += bool(ok); st['hit85'] += any(c >= 0.85 for c in ok)
                st['noise'] += sum(1 for a, c in reads[k] if 2 <= len(a) <= 4 and a != s['bib'] and c >= 0.85)
            per.append((clip, s['bib'], {k: max([c for a, c in reads[k] if a == s['bib']] or [0]) for k in V}))
            print(clip, s['bib'], {k: round(x, 2) for k, x in per[-1][2].items()}, flush=True)
    print('\nSUMMARY')
    for k, st in stats.items():
        print(k, f"hit_any {st['hit_any']}/{st['n']}  hit85 {st['hit85']}/{st['n']}  noise85 {st['noise']}  ocr_sec {st['sec']:.0f}")
main()

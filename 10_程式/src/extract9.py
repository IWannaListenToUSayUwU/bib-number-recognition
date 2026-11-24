"""逐格抽取 v9（2026-11-24，R17 最終魔王）＝extract8 加兩個選項（全部關閉時輸出和 extract8 逐位元相同）：
  ocr_min_h：人框高度 ≥ min_h 就追蹤、輸出（過線要用），但 ≥ ocr_min_h 才做 OCR（None＝同 min_h）。
             低解析度影片在計時線附近的人只有 60～70 像素，min_h=100 會讓過線完全偵測不到。
  prep：OCR 前的影像前處理（抗逆光／反光）：None｜'clahe'（亮度通道局部對比等化）｜'gamma'（暗部提亮）｜'clahe_up'（clahe＋放大 2 倍）
以下為 extract8 原說明：
逐格抽取 v8（2026-11-23，三層設定用）＝extract7，但「這一格要不要做 OCR」交給 ocrgate.OcrGate：
  static_s／static_p：不動的人不讀（同 extract7）
  zone_line／zone_up／zone_down：只讀線附近（新增；計時線和範圍來自機位層 config/camera/*.json）
其他選項（bottom_ext、ocr_every、ocr_det_side、ocr_unclip、es_len）和 extract7 相同、預設關閉。
所有選項都關閉時，輸出和 extract4 逐位元相同（偵測、追蹤、換人切分都不看 OCR 結果）。
以下為 extract7 原說明：
逐格抽取 v7（R13 E2）＝extract4 加一個選項 bottom_ext：人框貼到畫面底部（下半身被切掉）時，OCR 的裁切範圍延伸到畫面底，
避免切掉腰部的號碼布。顏色直方圖（換人偵測）仍用原本的裁切，所以 bottom_ext=False 時輸出和 extract4 完全相同。
提速選項（R13 E3，預設關閉）：static_s>0 時，同一個人（ByteTrack 編號）過去 static_s 秒內人框中心移動不到 static_p×人框高度 → 這一格不做 OCR；
ocr_every=K>1 時，同一條虛擬軌跡每 K 格才做一次 OCR。
ocr_det_side（R13 E5）：RapidOCR 文字偵測的輸入短邊（預設 None＝RapidOCR 預設 736；320 時 OCR 約快 2.5 倍）。
ocr_unclip（R13 E5c）：文字框外擴比例（預設 None＝RapidOCR 預設 1.6）。
es_len（R13 E6）：提早停止只算這個長度的數字讀數（號碼 5 碼 → 被截斷的 4 碼讀數不會讓 OCR 提早停止）；預設 None＝原行為。
所有選項都關閉時，輸出和 extract4 逐位元相同。
以下為 extract4 原說明：逐格抽取 v4（第二輪）：OCR 行為與 extract3 相同，另外加入「編號轉移偵測」。
每條 ByteTrack 軌跡持續追蹤軀幹顏色直方圖與位置；顏色突變或位置瞬間跳動 → 切成新的虛擬軌跡（vid），
並重置提早停止計數，讓換上來的人重新被辨識。每位人物每格都記錄一列（未做 OCR 時 texts=None）。"""
import sys, os, json, time, re, cv2, numpy as np
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR
from ocrgate import OcrGate
D = re.compile(r'\d+')

def torso_hist(crop):
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [16, 4], [0, 180, 0, 256]).flatten()
    return h / (h.sum() + 1e-9)

_CLAHE = None
def preprocess(img, prep):
    """回傳 (OCR 用的影像, 放大倍率)。prep=None 時原樣回傳（和 extract8 相同）。"""
    global _CLAHE
    if not prep: return img, 1.0
    if _CLAHE is None: _CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    if prep in ('clahe', 'clahe_up'):
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB); lab[:, :, 0] = _CLAHE.apply(lab[:, :, 0]); out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        if prep == 'clahe_up': return cv2.resize(out, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), 2.0
        return out, 1.0
    if prep == 'gamma':
        lut = (np.power(np.arange(256) / 255.0, 0.6) * 255).astype(np.uint8); return cv2.LUT(img, lut), 1.0
    raise ValueError(f'未知的 prep：{prep}')

def bhatt(a, b):
    return float(np.sqrt(max(0.0, 1 - np.sum(np.sqrt(a * b)))))

MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')

def process(frame_iter, fps=8, imgsz=960, min_h=100, top=0.22, bot=0.72, early_stop=3, hist_thr=0.45, jump_thr=0.8, bottom_ext=False, static_s=0.0, static_p=0.1, ocr_every=1, ocr_det_side=None, ocr_unclip=None, es_len=None,
            zone_line=None, zone_up=None, zone_down=None, stats=None, ocr_min_h=None, prep=None):
    det = YOLO(os.path.join(MODELS, 'yolo11s.pt'))
    nt = int(os.environ.get('BIB_OCR_THREADS', '0'))   # 平行執行時限制每個行程的 OCR 執行緒（只影響速度，不影響結果邏輯）
    kw = {f'{m}_{k}': nt for m in ('det', 'cls', 'rec') for k in ('intra_op_num_threads',)} if nt > 0 else {}
    if nt > 0:
        kw.update({f'{m}_inter_op_num_threads': 1 for m in ('det', 'cls', 'rec')})
    if ocr_det_side:
        kw['det_limit_side_len'] = int(ocr_det_side)
    if ocr_unclip:
        kw['det_unclip_ratio'] = float(ocr_unclip)
    ocr = RapidOCR(**kw)
    nf = 0; nocr = 0; nsplit = 0; nsmall = 0
    good = defaultdict(Counter)
    state = {}          # tid -> dict(vid, hist, box, t)
    nextv = defaultdict(int)
    gate = OcrGate(static_s, static_p, zone_line, zone_up, zone_down)
    nseen = defaultdict(int)    # vid -> 出現格數（每 K 格 OCR 用）
    nstatic = 0
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
            ocy2 = cy2
            if bottom_ext and y2 >= f.shape[0] - 2:      # 人框被畫面底部切掉 → OCR 範圍延伸到畫面底
                ocy2 = f.shape[0]
            ocrop = f[cy1:ocy2, cx1:cx2]
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
            skip = gate.active and not gate.allow(t, tid, (x1, y1, x2, y2))
            if ocr_every > 1:
                k_ = nseen[v]; nseen[v] += 1
                if k_ % ocr_every: skip = True
            if ocr_min_h and h < ocr_min_h: skip = True; nsmall += 1
            elif skip: nstatic += 1
            if not skip and not (v >= 0 and good[v] and good[v].most_common(1)[0][1] >= early_stop):
                img_, sc_ = preprocess(ocrop, prep)
                res, _ = ocr(img_, use_cls=False); nocr += 1
                texts = []
                for box, txt, sc in res or []:
                    xs = [p[0] / sc_ for p in box]; ys = [p[1] / sc_ for p in box]
                    texts.append([txt, round(float(sc), 3), [int(cx1 + min(xs)), int(cy1 + min(ys)), int(cx1 + max(xs)), int(cy1 + max(ys))]])
                    d_ = D.findall(txt.replace(' ', ''))
                    if d_ and float(sc) >= 0.9 and v >= 0 and (not es_len or len(max(d_, key=len)) == es_len):
                        good[v][max(d_, key=len)] += 1
            yield dict(t=round(t, 3), tid=v, rawtid=tid, pbox=[x1, y1, x2, y2], ph=h, split=split, texts=texts)
        if stats is not None:
            stats.update(frames=nf, ocr=nocr, splits=nsplit, **({'small': nsmall} if ocr_min_h else {}), **({'skipped': nstatic, 'skip_static': gate.n_static, 'skip_zone': gate.n_zone} if (gate.active or ocr_every > 1) else {}))

def run(vid, s, e, out, fps=8, **kw):
    t0 = time.time(); st = {}
    with open(out, 'w') as fo:
        for row in process(iter_frames(vid, s, e, fps=fps), fps=fps, stats=st, **kw):
            fo.write(json.dumps(row) + '\n')
    print(vid, s, st, f'{time.time() - t0:.0f}s', flush=True)

if __name__ == '__main__':
    # 用法：python extract8.py OUTDIR vid:start:end [vid:start:end ...]
    outdir = sys.argv[1]; os.makedirs(outdir, exist_ok=True)
    for spec in sys.argv[2:]:
        v, a, b = spec.split(':')
        o = f'{outdir}/{v}_{a}.jsonl'
        if os.path.exists(o + '.done'):
            continue
        run(v, float(a), float(b), o); open(o + '.done', 'w').close()

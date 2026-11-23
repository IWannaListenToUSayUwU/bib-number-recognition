"""逐格抽取 v6（第八輪：調嚴換人偵測）。OCR 與挑圖完全沿用 extract5（select='bins'），只改「何時切開軌跡」。
舊做法（extract4/5）：整塊軀幹的 色相×飽和度 直方圖，單一幀跟軌跡平均比，距離 > 0.45 才切。
  實測（C、D 兩片，相鄰兩個不同的人當作換人）只抓到約 30% 的換人。
新做法：
  1. 特徵改用 feat6：上衣左右兩側＋褲子，兩條分開算（避開號碼布與背景），HSV 加亮度格
  2. 不看單一幀，而是看「最近 win 幀的平均」跟「之前的軌跡外觀」比，距離 > win_thr 就切
     （平均掉單幀雜訊，同一人很少超過門檻；實測換人約可抓到 50–70%，同一人誤切約 1%）
  3. 切點：視窗中第一個單幀距離 > single_lo 的幀（沒有的話就是視窗第一幀），之後的幀全歸新的人
  4. 位置瞬移（jump_thr）照舊立即切
為了能把切點往回放，每條軌跡會延遲 win 幀才確定歸屬（只延遲輸出，不影響結果）。"""
import sys, os, cv2, numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR
from extract4 import MODELS
from extract5 import sharpness
from feat6 import stripe_feats, bhatt

def _dist(fa, fb, mode):
    s = bhatt(fa[0], fb[0]) if fa[0] is not None and fb[0] is not None else None
    o = bhatt(fa[1], fb[1]) if fa[1] is not None and fb[1] is not None else None
    if s is None and o is None: return 0.0
    if s is None or o is None: return s if o is None else o
    return s if mode == 'shirt' else (s + o) / 2

def _mean(feats):
    out = []
    for j in range(2):
        xs = [f[j] for f in feats if f[j] is not None]
        out.append(np.mean(xs, 0) if xs else None)
    return tuple(out)

def _ema(ref, new, a):
    return tuple(r if n is None else n if r is None else (1 - a) * r + a * n for r, n in zip(ref, new))

def process(frame_iter, fps=8, imgsz=960, min_h=100, top=0.22, bot=0.72, jump_thr=0.8,
            top_k=12, min_sep=0.25, gap=1.0, select='bins',
            win=3, win_thr=0.42, single_lo=0.30, ref_alpha=0.3, dist_mode='mean',
            stats=None, **_ignored):
    det = YOLO(os.path.join(MODELS, 'yolo11s.pt'))
    nt = int(os.environ.get('BIB_OCR_THREADS', '0'))
    kw = {f'{m}_intra_op_num_threads': nt for m in ('det', 'cls', 'rec')} if nt > 0 else {}
    ocr = RapidOCR(**kw)
    state = {}; nextv = defaultdict(int)
    buf = defaultdict(list)       # vid -> [(t, crop, (cx1,cy1), h, sharp, pbox)]
    last_seen = {}
    cnt = dict(nf=0, nocr=0, nsplit=0, nsplit_app=0, nsplit_jump=0)

    def flush(v):
        items = buf.pop(v, []); last_seen.pop(v, None)
        if not items: return []
        mh = max(x[3] for x in items); ms = max(x[4] for x in items) or 1.0
        if select == 'bins':
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
            res, _ = ocr(crop, use_cls=False); cnt['nocr'] += 1
            texts = []
            for box, txt, sc in res or []:
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                texts.append([txt, round(float(sc), 3), [int(cx1 + min(xs)), int(cy1 + min(ys)), int(cx1 + max(xs)), int(cy1 + max(ys))]])
            out.append(dict(t=round(t, 3), tid=v, pbox=pbox, ph=h, texts=texts, rank=rank, q=round(q, 4)))
        return out

    def new_vid(tid):
        nextv[tid] += 1
        return tid * 1000 + nextv[tid]

    def commit(st, item, split=False):
        """把一幀確定歸給 st['vid']，回傳人物列。"""
        t, crop, cxy, h, sh, pbox, feat, rawtid = item
        v = st['vid']
        buf[v].append((t, crop, cxy, h, sh, pbox)); last_seen[v] = t
        if len(buf[v]) > 120:
            buf[v].sort(key=lambda x: -x[3]); buf[v] = buf[v][:120]
        st['ref'] = feat if st['ref'] is None else _ema(st['ref'], feat, ref_alpha)
        return dict(t=round(t, 3), tid=v, rawtid=rawtid, pbox=pbox, ph=h, split=split, texts=None)

    def drain(st):
        rows = [commit(st, it) for it in st['pend']]; st['pend'] = []
        return rows

    for t, f in frame_iter:
        cnt['nf'] += 1
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
            if tid < 0:
                yield dict(t=round(t, 3), tid=-1, rawtid=tid, pbox=[x1, y1, x2, y2], ph=h, split=False, texts=None)
                continue
            feat = stripe_feats(f, (x1, y1, x2, y2))
            item = (t, crop.copy(), (cx1, cy1), h, sharpness(crop), [x1, y1, x2, y2], feat, tid)
            st = state.get(tid)
            if st is None:
                st = state[tid] = dict(vid=new_vid(tid), ref=None, box=(x1, y1, x2, y2), t=t, pend=[])
                yield commit(st, item); continue
            # 1) 位置瞬移：立即切
            pcx, pcy = (st['box'][0] + st['box'][2]) / 2, (st['box'][1] + st['box'][3]) / 2
            gapf = max(1, round((t - st['t']) * fps))
            jump = np.hypot((x1 + x2) / 2 - pcx, (y1 + y2) / 2 - pcy) / max(w, st['box'][2] - st['box'][0]) / gapf
            st['box'] = (x1, y1, x2, y2); st['t'] = t
            if jump > jump_thr:
                for row in drain(st): yield row
                for row in flush(st['vid']): yield row
                st['vid'] = new_vid(tid); st['ref'] = None
                cnt['nsplit'] += 1; cnt['nsplit_jump'] += 1
                yield commit(st, item, split=True); continue
            # 2) 外觀：延遲 win 幀，用視窗平均判斷
            st['pend'].append(item)
            if len(st['pend']) < win: continue
            feats = [it[6] for it in st['pend']]
            if st['ref'] is not None and _dist(_mean(feats), st['ref'], dist_mode) > win_thr:
                ds = [_dist(fe, st['ref'], dist_mode) for fe in feats]
                cut = next((i for i, d in enumerate(ds) if d > single_lo), 0)
                old_items, new_items = st['pend'][:cut], st['pend'][cut:]
                st['pend'] = old_items
                for row in drain(st): yield row
                for row in flush(st['vid']): yield row
                st['vid'] = new_vid(tid); st['ref'] = _mean([it[6] for it in new_items])
                cnt['nsplit'] += 1; cnt['nsplit_app'] += 1
                for i, it in enumerate(new_items):
                    yield commit(st, it, split=(i == 0))
            else:
                yield commit(st, st['pend'].pop(0))
        # 消失的軌跡：先把延遲中的幀歸位，再看要不要做 OCR
        for tid, st in state.items():
            if st['pend'] and t - st['t'] > gap:
                for row in drain(st): yield row
        for v in [v for v, ls in last_seen.items() if t - ls > gap]:
            for row in flush(v): yield row
        if stats is not None: stats.update(frames=cnt['nf'], ocr=cnt['nocr'], splits=cnt['nsplit'],
                                           splits_app=cnt['nsplit_app'], splits_jump=cnt['nsplit_jump'])
    for st in state.values():
        for row in drain(st): yield row
    for v in list(buf):
        for row in flush(v): yield row
    if stats is not None: stats.update(frames=cnt['nf'], ocr=cnt['nocr'], splits=cnt['nsplit'],
                                       splits_app=cnt['nsplit_app'], splits_jump=cnt['nsplit_jump'])

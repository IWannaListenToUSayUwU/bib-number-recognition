r"""R13 OCR 探針（只用調整集，離線，CPU）：同一批人框，換不同的裁切／前處理，直接比 RapidOCR 讀對號碼的比例。
用來在花 GPU 時間整段重跑之前，先看哪一種改法值得試。必須用 bibread 環境的 python 跑（RapidOCR 版本要和正式流程相同）：
  %USERPROFILE%\anaconda3\envs\bibread\python.exe 30_實驗/R13_新機位讀號碼/r13_ocr_probe.py <調整集片段> [每人最多幾格=10] [raw 路徑]
做法：
  1. 用 v2.2 的過線事件，把官方名單上的跑者對到「唯一」的過線事件（槍聲時間差 ≤ 1 秒內只有一個事件），取得這個人的軌跡；
     號碼的答案＝官方號碼（只當答案用，不給 OCR 看）。
  2. 每人沿整條軌跡平均取 N 格，對每種裁切跑一次 OCR（use_cls=False，和正式流程相同）。
  3. 比較：讀到正確 5 碼的格數比例、至少讀對 1 次／3 次的人數；分畫面左半（靠近線）和右半。
輸出：診斷\OCR探針_<片段>.json"""
import json, os, sys, time
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path  # noqa: E402
from rapidocr_onnxruntime import RapidOCR  # noqa: E402

VARIANTS = {
    'base':       dict(top=0.22, bot=0.72),                 # v2.2 現行
    'top10':      dict(top=0.10, bot=0.72),                 # 上緣放高
    'top10_b60':  dict(top=0.10, bot=0.60),                 # 上緣放高、下緣收短（比較小的裁切）
    'base_up2':   dict(top=0.22, bot=0.72, scale=2.0),      # 放大 2 倍
    'base_sharp': dict(top=0.22, bot=0.72, sharp=True),     # 銳化
    'clahe':      dict(top=0.22, bot=0.72, enh='clahe'),    # 局部對比增強（L 通道）
    'gamma2':     dict(top=0.22, bot=0.72, enh='gamma2'),   # 調暗（gamma 2）：過曝畫面的淡灰數字變深
    'stretch':    dict(top=0.22, bot=0.72, enh='stretch'),  # 每張裁切把亮度 1%～99% 拉到 0～255
    'clahe_up2':  dict(top=0.22, bot=0.72, enh='clahe', scale=2.0),
}
# OCR 參數版本（裁切都用 base）：RapidOCR 預設 det limit_type=min、limit_side_len=736（小裁切會被放大到短邊 736）、thresh 0.3、box_thresh 0.5
OCRV = {
    'ocr_lowthr':  dict(det_thresh=0.2, det_box_thresh=0.35),
    'ocr_max960':  dict(det_limit_type='max', det_limit_side_len=960),      # 不放大
    'ocr_min320':  dict(det_limit_type='min', det_limit_side_len=320),      # 只放大到短邊 320
    'ocr_min320_low': dict(det_limit_type='min', det_limit_side_len=320, det_thresh=0.2, det_box_thresh=0.35),
    'ocr_unclip2': dict(det_unclip_ratio=2.0),
}
for k in OCRV: VARIANTS[k] = dict(top=0.22, bot=0.72, ocr=k)
VARIANTS['adapt'] = dict(top=0.22, bot=0.72, enh='adapt')              # 自適應二值化（淡灰數字 → 黑字白底）
VARIANTS['gray_clahe_up3'] = dict(top=0.22, bot=0.72, enh='grayclahe', scale=3.0)
VARIANTS['stack5'] = dict(top=0.22, bot=0.72, stack=5)                  # 前後 5 格對齊（平移）後平均
VARIANTS['stack5_clahe'] = dict(top=0.22, bot=0.72, stack=5, enh='clahe')
VARIANTS['stack5_up2'] = dict(top=0.22, bot=0.72, stack=5, scale=2.0)
ONLY = os.environ.get('PROBE_ONLY')   # 只跑部分版本（逗號分隔）
if ONLY: VARIANTS = {k: v for k, v in VARIANTS.items() if k in ONLY.split(',')}


def crop(f, pbox, top, bot, scale=1.0, sharp=False, enh=None, ocr=None, stack=0, nb=None):
    H, W = f.shape[:2]; x1, y1, x2, y2 = pbox; h = y2 - y1; w = x2 - x1
    cx1 = max(0, x1 - int(.08 * w)); cx2 = min(W, x2 + int(.08 * w)); cy1 = max(0, y1 + int(top * h)); cy2 = min(H, y1 + int(bot * h))
    c = f[cy1:cy2, cx1:cx2]
    if c.size == 0: return None
    if stack and nb:
        ref = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32); acc = c.astype(np.float32); n = 1
        for g in nb:   # 鄰近格：在稍大的範圍內找最佳平移，再裁同樣大小
            pad = 24; X1 = max(0, cx1 - pad); Y1 = max(0, cy1 - pad); big = g[Y1:min(H, cy2 + pad), X1:min(W, cx2 + pad)]
            if big.shape[0] < c.shape[0] or big.shape[1] < c.shape[1]: continue
            r = cv2.matchTemplate(cv2.cvtColor(big, cv2.COLOR_BGR2GRAY).astype(np.float32), ref, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(r)
            if mx < 0.5: continue
            acc += big[loc[1]:loc[1] + c.shape[0], loc[0]:loc[0] + c.shape[1]].astype(np.float32); n += 1
        c = (acc / n).astype(np.uint8)
    if enh == 'clahe':
        lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB); lab[..., 0] = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4)).apply(lab[..., 0])
        c = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    elif enh == 'adapt':
        g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY); g = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8)
        c = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    elif enh == 'grayclahe':
        g = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4)).apply(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)); c = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    elif enh == 'gamma2':
        c = (255.0 * (c / 255.0) ** 2.0).astype(np.uint8)
    elif enh == 'stretch':
        lo, hi = np.percentile(c, (1, 99)); c = np.clip((c.astype(np.float32) - lo) * 255.0 / max(1.0, hi - lo), 0, 255).astype(np.uint8)
    if scale != 1.0: c = cv2.resize(c, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if sharp:
        b = cv2.GaussianBlur(c, (0, 0), 2.0); c = cv2.addWeighted(c, 1.6, b, -0.6, 0)
    return c


def main():
    clip = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    rp = sys.argv[3] if len(sys.argv) > 3 else raw_path('FROZEN_CONFIG_v2_2', clip)
    recs = [json.loads(l) for l in open(rp, encoding='utf-8')]
    ev = L.crossing_events(rp, clip); t0 = L.clock_at_t0(clip)
    offl = {r['bib']: L.sec(r['time']) for r in L.official()['rows'] if t0 + 1 <= L.sec(r['time']) <= t0 + 59}
    pairs = []
    for b, x in offl.items():
        c = [e for e in ev if abs(t0 + e['t_cross'] - x - 0.3) <= 1.0]
        if len(c) == 1: pairs.append((b, c[0]))
    nt = int(os.environ.get('BIB_OCR_THREADS', '4'))
    kw = {f'{m}_intra_op_num_threads': nt for m in ('det', 'cls', 'rec')}; kw.update({f'{m}_inter_op_num_threads': 1 for m in ('det', 'cls', 'rec')})
    ocr = RapidOCR(**kw)
    ocrs = {k: RapidOCR(**kw, **OCRV[k]) for k in {p.get('ocr') for p in VARIANTS.values()} if k}
    cap = cv2.VideoCapture(os.path.join(L.ROOT, '20_測試基準', 'clips', clip + '.mp4'))
    res = {v: dict(frames=0, exact=0, exact_left=0, frames_left=0, digits=0, per_bib={}) for v in VARIANTS}
    t_start = time.time(); nfr = 0
    for b, e in pairs:
        tr = sorted((r for r in recs if r.get('rawtid') == e['rawtid']), key=lambda r: r['t'])
        picks = [tr[int(i)] for i in np.linspace(0, len(tr) - 1, min(N, len(tr)))] if tr else []   # 沿整條軌跡平均取 N 格
        for r in picks:
            fi = int(round(r['t'] * 30)); need_nb = any(p.get('stack') for p in VARIANTS.values())
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, fi - 2) if need_nb else fi)
            fr = [cap.read()[1] for _ in range(5 if need_nb else 1)]
            f = fr[min(2, fi)] if need_nb else fr[0]
            if f is None: continue
            nb = [g for j, g in enumerate(fr) if g is not None and g is not f] if need_nb else None
            nfr += 1; left = (r['pbox'][0] + r['pbox'][2]) / 2 < 960
            for v, p in VARIANTS.items():
                c = crop(f, r['pbox'], **p, nb=nb)
                if c is None: continue
                out, _ = (ocrs[p['ocr']] if p.get('ocr') else ocr)(c, use_cls=False)
                reads = [L.norm(t) for _, t, s in (out or []) if float(s) >= 0.8]
                hit = b in reads; R = res[v]
                R['frames'] += 1; R['exact'] += hit; R['digits'] += any(len(x) >= 3 for x in reads)
                R['frames_left'] += left; R['exact_left'] += hit and left
                R['per_bib'][b] = R['per_bib'].get(b, 0) + hit
    print(f'{clip}: 對到 {len(pairs)} 位官方跑者、{nfr} 格；OCR 花 {time.time() - t_start:.0f} 秒')
    for v, R in res.items():
        pb = R['per_bib']; n1 = sum(1 for x in pb.values() if x >= 1); n3 = sum(1 for x in pb.values() if x >= 3)
        R.update(people=len(pb), people_ge1=n1, people_ge3=n3)
        print(f"  {v:11s} 讀對的格 {R['exact']}/{R['frames']}（左半 {R['exact_left']}/{R['frames_left']}）｜有 3 碼以上數字 {R['digits']}｜"
              f"至少讀對 1 次的人 {n1}/{len(pb)}、3 次 {n3}")
    os.makedirs(os.path.join(HERE, '診斷'), exist_ok=True)
    json.dump(dict(clip=clip, pairs=len(pairs), frames=nfr, variants=VARIANTS, results=res),
              open(os.path.join(HERE, '診斷', f'OCR探針_{clip}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

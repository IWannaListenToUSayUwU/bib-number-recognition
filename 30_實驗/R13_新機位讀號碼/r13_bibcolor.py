r"""R13 號碼布顏色檢查：2022 臺北馬 1 開頭的號碼（10000–11783）看起來是藍紫底白字、0 開頭是白底深字。
如果顏色能穩定區分，就能解決「01183 還是 11183」這種開頭一碼的歧義（主辦單位事先知道各號碼區段的顏色，算比賽設定資訊）。
做法：取「讀數＝正確號碼」的 OCR 文字框（正確號碼：調整集用官方名單＋時間對得上的事件；C、D 用人工 sure），量文字框內偏藍像素的比例
（HSV：H 95–140〔OpenCV 0–180〕、S ≥ 60、V ≥ 40；預設只量文字框內部，BC_PAD=1 時往外多取 1/3 字高），比較 0 開頭和 1 開頭的分布。只用調整集＋C、D。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_bibcolor.py　輸出：診斷\號碼布顏色.json"""
import json, os, sys
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path, TUNE, GUARD  # noqa: E402


def blue_frac(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return float(((h >= 95) & (h <= 140) & (s >= 60) & (v >= 40)).mean())


def truth_reads(c):
    """回傳 [(t, bbox, bib)]：讀數剛好等於這個人正確號碼的 OCR 文字框。"""
    rp = raw_path('FROZEN_CONFIG_v2_2', c); recs = [json.loads(l) for l in open(rp, encoding='utf-8')]
    out = []
    if c.startswith('tpe2t_'):
        ev = L.crossing_events(rp, c); t0 = L.clock_at_t0(c)
        offl = {r['bib']: L.sec(r['time']) for r in L.official()['rows'] if t0 - 5 <= L.sec(r['time']) <= t0 + 65}
        good = {e['vid']: e['bib'] for e in ev if e['bib'] in offl and abs(offl[e['bib']] - t0 - e['t_cross']) <= 2}
    else:
        g = json.load(open(os.path.join(L.ROOT, '20_測試基準', 'gt_crossing', c + '.json'), encoding='utf-8'))['events']
        sure = {x['bib'] for x in g if x['status'] == 'sure'}
        good = None
    for r in recs:
        for txt, sc, bb in (r['texts'] or []):
            s = L.norm(txt)
            if len(s) != 5: continue
            if good is not None and good.get(r['tid']) == s: out.append((r['t'], bb, s))
            if good is None and s in sure: out.append((r['t'], bb, s))
    return out


def main():
    res = {}
    for c in TUNE + GUARD:
        p = raw_path('FROZEN_CONFIG_v2_2', c)
        if not os.path.exists(p): continue
        tr = truth_reads(c); cap = cv2.VideoCapture(os.path.join(L.ROOT, '20_測試基準', 'clips', c + '.mp4'))
        for t, bb, b in tr:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * 30))); ok, f = cap.read()
            if not ok: continue
            x1, y1, x2, y2 = bb; PAD = int(os.environ.get('BC_PAD', '0'))   # 0＝只量文字框內部
            pad = max(2, (y2 - y1) // 3) if PAD else 0
            crop = f[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]
            if crop.size == 0: continue
            res.setdefault(b, []).append(dict(clip=c, t=t, blue=round(blue_frac(crop), 3)))
    per = {b: float(np.median([x['blue'] for x in v])) for b, v in res.items()}
    z = sorted(v for b, v in per.items() if b[0] == '0'); o = sorted(v for b, v in per.items() if b[0] == '1')
    print(f'0 開頭 {len(z)} 個號碼：藍色比例中位數 {np.median(z) if z else None:.3f}，最大 {max(z) if z else None}；分位 {np.percentile(z, [50, 90, 95, 100]).round(3) if z else None}')
    print(f'1 開頭 {len(o)} 個號碼：藍色比例中位數 {np.median(o) if o else None}，最小 {min(o) if o else None}；全部 {[round(x, 3) for x in o]}')
    json.dump(dict(per_bib=per, reads=res), open(os.path.join(HERE, '診斷', '號碼布顏色.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

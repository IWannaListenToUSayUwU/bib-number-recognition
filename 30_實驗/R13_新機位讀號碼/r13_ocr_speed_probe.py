r"""R13 OCR 速度探針（C、D，人工答案 v1；離線、CPU）：RapidOCR 的文字偵測預設把每張裁切放大到短邊 736 像素（det limit_type=min），
這是 OCR 最花時間的地方。比較不同偵測輸入大小的「讀對率」和「每次 OCR 時間」，看能不能在不掉準確度下提速。
必須用 bibread 環境的 python 跑：
  %USERPROFILE%\anaconda3\envs\bibread\python.exe 30_實驗/R13_新機位讀號碼/r13_ocr_speed_probe.py [每人格數=6] [人數上限=40]
做法：v2.2 過線事件和人工答案（score_v2 的配對）配起來，取人工 sure 號碼的人；沿軌跡平均取 N 格（只取過線前 3 秒內，OCR 真正會用到的那段）；
每格對每種設定各跑一次（設定輪流跑，讓背景負載對各設定公平）。計時用 time.perf_counter。
輸出：診斷\OCR速度探針_CD.json"""
import json, os, sys, time
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path  # noqa: E402
from rapidocr_onnxruntime import RapidOCR  # noqa: E402

CFGS = {'min736(預設)': {}, 'min480': dict(det_limit_side_len=480), 'min320': dict(det_limit_side_len=320),
        'max480': dict(det_limit_type='max', det_limit_side_len=480), 'max320': dict(det_limit_type='max', det_limit_side_len=320)}


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 6; LIM = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    nt = int(os.environ.get('BIB_OCR_THREADS', '4'))
    kw = {f'{m}_intra_op_num_threads': nt for m in ('det', 'cls', 'rec')}; kw.update({f'{m}_inter_op_num_threads': 1 for m in ('det', 'cls', 'rec')})
    ocrs = {k: RapidOCR(**kw, **v) for k, v in CFGS.items()}
    res = {k: dict(frames=0, exact=0, sec=0.0, per_bib={}) for k in CFGS}
    people = []
    for c in ('tpe_C_600', 'tpe_D_1800'):
        rp = raw_path('FROZEN_CONFIG_v2_2', c); recs = [json.loads(l) for l in open(rp, encoding='utf-8')]
        ev = L.crossing_events(rp, c)
        g = json.load(open(os.path.join(L.ROOT, '20_測試基準', 'gt_crossing', c + '.json'), encoding='utf-8'))['events']
        sys_ev = [dict(t=float(e['t_cross']), bib=e['bib'], u=float(e['u'])) for e in ev]
        ms, _ = L.score_v2.match(sorted(sys_ev, key=lambda s: s['t']), g)
        evs = sorted(ev, key=lambda e: float(e['t_cross']))
        for i, j in ms.items():
            if g[j]['status'] != 'sure': continue
            e = evs[i]; tr = sorted((r for r in recs if r.get('rawtid') == e['rawtid'] and e['t_cross'] - 3 <= r['t'] <= e['t_cross']), key=lambda r: r['t'])
            if tr: people.append((c, g[j]['bib'], tr))
    people = people[::max(1, len(people) // LIM)][:LIM]
    caps = {c: cv2.VideoCapture(os.path.join(L.ROOT, '20_測試基準', 'clips', c + '.mp4')) for c in ('tpe_C_600', 'tpe_D_1800')}
    for c, b, tr in people:
        for r in [tr[int(i)] for i in np.linspace(0, len(tr) - 1, min(N, len(tr)))]:
            cap = caps[c]; cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(r['t'] * 30))); ok, f = cap.read()
            if not ok: continue
            H, W = f.shape[:2]; x1, y1, x2, y2 = r['pbox']; h = y2 - y1; w = x2 - x1
            cr = f[max(0, y1 + int(.22 * h)):min(H, y1 + int(.72 * h)), max(0, x1 - int(.08 * w)):min(W, x2 + int(.08 * w))]
            if cr.size == 0: continue
            for k, o in ocrs.items():
                t0 = time.perf_counter(); out, _ = o(cr, use_cls=False); dt = time.perf_counter() - t0
                hit = b in [L.norm(t) for _, t, s in (out or []) if float(s) >= 0.8]
                R = res[k]; R['frames'] += 1; R['exact'] += hit; R['sec'] += dt; R['per_bib'][b] = R['per_bib'].get(b, 0) + hit
    print(f'C、D：{len(people)} 位人工 sure 跑者')
    for k, R in res.items():
        pb = R['per_bib']; R.update(people_ge1=sum(1 for x in pb.values() if x >= 1), people_ge3=sum(1 for x in pb.values() if x >= 3),
                                     ms_per_call=round(1000 * R['sec'] / max(1, R['frames']), 1))
        print(f"  {k:12s} 讀對 {R['exact']}/{R['frames']}（{R['exact'] / max(1, R['frames']):.2f}）｜至少讀對 1 次的人 {R['people_ge1']}/{len(pb)}、3 次 {R['people_ge3']}｜每次 {R['ms_per_call']} 毫秒")
    json.dump(dict(cfgs=CFGS, people=len(people), results=res), open(os.path.join(HERE, '診斷', 'OCR速度探針_CD.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

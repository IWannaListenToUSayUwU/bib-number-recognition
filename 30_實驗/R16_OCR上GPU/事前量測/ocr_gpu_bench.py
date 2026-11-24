"""OCR CPU vs GPU 小測試。
  python ocr_gpu_bench.py crops            → 從 tpe_C_600 切軀幹圖（同 extract8 的裁切），存 crops.npz
  python ocr_gpu_bench.py run <mode>       → mode = cpu131 | cpu126 | gpu126 | gpu126h ，讀 crops 兩輪、記時間和讀數
  python ocr_gpu_bench.py compare          → 比較各 mode 的讀數
"""
import sys, os, time, json
ROOT = r"Z:\雲科專題"; HERE = os.path.dirname(os.path.abspath(__file__))
ORT126 = r"C:\Users\ShiLaCow\bibread_ortgpu\ort126"
mode = sys.argv[2] if len(sys.argv) > 2 else ''
if '126' in mode:
    sys.path.insert(0, ORT126)
import torch  # noqa: E402  先載入 torch 的 CUDA／cuDNN DLL，GPU 版 ORT 才找得到
import numpy as np, cv2  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src'))
NPZ = os.path.join(HERE, 'crops.npz')


def make_crops():
    from ultralytics import YOLO
    from videoio import probe, frames
    vp = os.path.join(ROOT, '20_測試基準', 'clips', 'tpe_C_600.mp4'); W, H, dur = probe(vp)
    det = YOLO(os.path.join(ROOT, '10_程式', 'models', 'yolo11s.pt'))
    crops = []; n = 0
    for t, f in frames(vp, 0.0, dur, 16, W, H):
        n += 1
        if n % 8: continue                       # 每 0.5 秒取一格
        r = det(f, classes=[0], conf=0.2, imgsz=960, verbose=False)[0]
        for b in r.boxes.xyxy.tolist():
            x1, y1, x2, y2 = map(int, b); h = y2 - y1; w = x2 - x1
            if h < 100: continue
            cx1 = max(0, x1 - int(.08 * w)); cx2 = min(f.shape[1], x2 + int(.08 * w))
            cy1 = max(0, y1 + int(.22 * h)); cy2 = min(f.shape[0], y1 + int(.72 * h))
            c = f[cy1:cy2, cx1:cx2]
            if c.size and c.shape[0] >= 10: crops.append(c.copy())
    np.savez_compressed(NPZ, *crops)
    print(f'{len(crops)} crops from {n} frames (dur {dur:.1f}s)')


def run(mode):
    import onnxruntime as ort
    print('ort', ort.__version__, ort.__file__.split('site-packages')[-1][:60], ort.get_available_providers(), flush=True)
    if mode == 'gpu126h':                           # cuDNN 演算法搜尋改 HEURISTIC（輸入大小一直變時，EXHAUSTIVE 每種大小都要重找）
        from rapidocr_onnxruntime.utils import infer_engine as ie
        orig = ie.OrtInferSession._get_ep_list
        def patched(self):
            L = orig(self)
            return [(n, dict(o, cudnn_conv_algo_search='HEURISTIC') if n == 'CUDAExecutionProvider' else o) for n, o in L]
        ie.OrtInferSession._get_ep_list = patched
    from rapidocr_onnxruntime import RapidOCR
    gpu = mode.startswith('gpu')
    kw = {f'{m}_use_cuda': gpu for m in ('det', 'cls', 'rec')}
    if not gpu:   # 和正式流程一樣：BIB_OCR_THREADS=8
        kw.update({f'{m}_intra_op_num_threads': 8 for m in ('det', 'cls', 'rec')}); kw.update({f'{m}_inter_op_num_threads': 1 for m in ('det', 'cls', 'rec')})
    ocr = RapidOCR(**kw)
    print('providers det/rec:', ocr.text_det.infer.session.get_providers()[0], ocr.text_rec.session.session.get_providers()[0] if hasattr(ocr.text_rec, 'session') else '?', flush=True)
    z = np.load(NPZ); crops = [z[k] for k in z.files]
    out = {}
    NR = int(os.environ.get('BENCH_ROUNDS', '2')); stage = [0.0, 0.0, 0.0]
    for rnd in range(1, NR + 1):
        texts = []; t0 = time.time(); per = []
        for c in crops:
            a = time.time(); res, el_ = ocr(c, use_cls=False); per.append(time.time() - a)
            if rnd == NR and el_: stage[0] += el_[0] or 0; stage[2] += el_[2] or 0
            texts.append([[x[1], round(float(x[2]), 3)] for x in (res or [])])
        el = time.time() - t0
        out[f'round{rnd}'] = dict(sec=round(el, 2), ms_per_crop=round(1000 * el / len(crops), 2), first50_ms=round(1000 * sum(per[:50]) / 50, 1),
                                 last_half_ms=round(1000 * sum(per[len(per) // 2:]) / (len(per) - len(per) // 2), 2))
        print(mode, f'round{rnd}', out[f'round{rnd}'], flush=True)
        if rnd == NR:
            out['texts'] = texts
            out['stage_ms'] = dict(det=round(1000 * stage[0] / len(crops), 1), rec=round(1000 * stage[2] / len(crops), 1), total=out[f'round{rnd}']['ms_per_crop'])
            print('stage_ms', out['stage_ms'], flush=True)
    out['n'] = len(crops); out['ort'] = ort.__version__
    json.dump(out, open(os.path.join(HERE, f'bench_{mode}.json'), 'w', encoding='utf-8'), ensure_ascii=False)


def compare():
    R = {m: json.load(open(os.path.join(HERE, f'bench_{m}.json'), encoding='utf-8')) for m in ('cpu131', 'cpu126', 'gpu126', 'gpu126h') if os.path.exists(os.path.join(HERE, f'bench_{m}.json'))}
    base = R['cpu131']['texts']
    for m, r in R.items():
        same_txt = sum(1 for a, b in zip(base, r['texts']) if [x[0] for x in a] == [x[0] for x in b])
        same_all = sum(1 for a, b in zip(base, r['texts']) if a == b)
        dsc = [abs(x[1] - y[1]) for a, b in zip(base, r['texts']) if [x[0] for x in a] == [x[0] for x in b] for x, y in zip(a, b)]
        print(f"{m:8s} ort {r['ort']:7s} n={r['n']}  r1 {r['round1']['ms_per_crop']:7.2f} ms/張  stage {r.get('stage_ms')}  "
              f"文字相同 {same_txt}/{r['n']}  文字＋分數相同 {same_all}/{r['n']}  分數差最大 {max(dsc) if dsc else 0:.3f}")
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(base, r['texts'])) if [x[0] for x in a] != [x[0] for x in b]]
        for i, a, b in diffs[:6]: print('    ', i, a, '→', b)


if __name__ == '__main__':
    {'crops': make_crops, 'run': lambda: run(mode), 'compare': compare}[sys.argv[1]]()

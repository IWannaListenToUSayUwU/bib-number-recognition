"""整支影片平行處理（Windows / Linux 皆可）：
把影片切成 N 段（段與段重疊 3 秒）分給 N 個工作行程，人物偵測自動使用 GPU（若有 CUDA），OCR 用 CPU。
全部讀數合併後一次定案（跨段的同一號碼會被時間合併），輸出 CSV，可選擇輸出只標定案結果的影片。

用法：python run_parallel.py 影片.mp4 --outdir 輸出資料夾 [--workers N] [--start 秒] [--end 秒] [--no-video]
"""
import argparse, csv, json, os, sys, time, multiprocessing as mp
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
CFG = json.load(open(os.path.join(HERE, '..', 'work', 'FROZEN_CONFIG_v2.json'), encoding='utf-8'))

def log(msg, path=None):
    line = time.strftime('%H:%M:%S ') + msg
    print(line, flush=True)
    if path:
        with open(path, 'a', encoding='utf-8') as f: f.write(line + '\n')

def worker(args):
    idx, video, t0, t1, out, logpath, nthreads = args
    for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        os.environ[k] = str(nthreads)
    os.environ['BIB_OCR_THREADS'] = str(nthreads)
    import cv2; cv2.setNumThreads(1)
    import torch
    from videoio import probe, frames
    from extract4 import process
    torch.set_num_threads(1)
    W, H, _ = probe(video); fps = CFG['extract']['fps']
    ex = {k: v for k, v in CFG['extract'].items() if k in ('imgsz', 'min_h', 'top', 'bot', 'early_stop', 'hist_thr', 'jump_thr')}
    st = {}; tstart = time.time(); last = tstart
    with open(out, 'w', encoding='utf-8') as fo:
        for r in process(frames(video, t0, t1, fps, W, H), fps=fps, stats=st, **ex):
            if r['tid'] >= 0: r['tid'] = r['tid'] + (idx + 1) * 10 ** 9      # 各段軌跡編號不重複
            fo.write(json.dumps(r) + '\n')
            if time.time() - last > 60:
                last = time.time(); log(f'  第 {idx + 1} 段：{r["t"]:.0f}/{t1:.0f}s', logpath)
    log(f'  第 {idx + 1} 段完成（{t0:.0f}-{t1:.0f}s，{time.time() - tstart:.0f} 秒）', logpath)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('--outdir', required=True)
    ap.add_argument('--workers', type=int, default=0); ap.add_argument('--start', type=float, default=0)
    ap.add_argument('--end', type=float); ap.add_argument('--no-video', action='store_true')
    a = ap.parse_args()
    import cv2, torch
    from videoio import probe, frames
    from aggregate2 import aggregate2
    os.makedirs(a.outdir, exist_ok=True)
    name = os.path.splitext(os.path.basename(a.video))[0][:40]
    logpath = os.path.join(a.outdir, 'log.txt')
    W, H, dur = probe(a.video); t1 = min(a.end or dur, dur)
    ncpu = os.cpu_count() or 2
    nw = a.workers or max(1, min(6, ncpu // 3))
    nthreads = max(1, ncpu // nw)
    gpu = torch.cuda.is_available()
    log(f'開始：{name}  長度 {t1 - a.start:.0f}s  工作行程 {nw}×{nthreads}執行緒  GPU={"是 " + torch.cuda.get_device_name(0) if gpu else "否"}', logpath)
    seg = (t1 - a.start) / nw; jobs = []
    for i in range(nw):
        s = a.start + i * seg; e = min(t1, s + seg + 3.0)
        jobs.append((i, a.video, s, e, os.path.join(a.outdir, f'_raw_{name}_{i}.jsonl'), logpath, nthreads))
    tstart = time.time()
    with mp.get_context('spawn').Pool(nw) as pool:
        outs = pool.map(worker, jobs)
    rows, boxes = [], defaultdict(list)
    for o in outs:
        for l in open(o, encoding='utf-8'):
            r = json.loads(l); boxes[r['tid']].append((r['t'], r['pbox']))
            for txt, sc, bb in (r.get('texts') or []):
                rows.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc))
    preds = aggregate2(rows, **CFG['aggregate'])
    csvp = os.path.join(a.outdir, f'{name}.csv')
    with open(csvp, 'w', newline='', encoding='utf-8-sig') as fo:
        wr = csv.writer(fo); wr.writerow(['bib', 'time_s', 'time_hms', 'first_s', 'last_s', 'score'])
        for p in sorted(preds, key=lambda x: x['t']):
            t = p['t']
            wr.writerow([p['bib'], f'{t:.2f}', time.strftime('%H:%M:%S', time.gmtime(t)), f'{p["t0"]:.2f}', f'{p["t1"]:.2f}', f'{p["score"]:.3f}'])
    el = time.time() - tstart
    log(f'辨識完成：{len(preds)} 個號碼，耗時 {el:.0f} 秒（影片長度的 {el / max(1, t1 - a.start):.2f} 倍）→ {csvp}', logpath)
    if not a.no_video:
        fps = CFG['extract']['fps']; label = {}
        for p in preds:
            for tid in p['tids']:
                if isinstance(tid, int): label[tid] = (p['bib'], p['t0'] - 1, p['t1'] + 1)
        at = defaultdict(list)
        for tid, lst in boxes.items():
            for t, b in lst: at[round(t, 3)].append((tid, b))
        vp = os.path.join(a.outdir, f'{name}_標註.mp4')
        vw = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
        for t, f in frames(a.video, a.start, t1, fps, W, H):
            g = f.copy()
            for tid, (x1, y1, x2, y2) in at.get(round(t, 3), []):
                L = label.get(tid)
                if L and L[1] <= t <= L[2]:
                    cv2.rectangle(g, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(g, L[0], (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5)
                    cv2.putText(g, L[0], (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
                else:
                    cv2.rectangle(g, (x1, y1), (x2, y2), (160, 160, 160), 1)
            cv2.putText(g, time.strftime('%H:%M:%S', time.gmtime(t)), (10, H - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            vw.write(g)
        vw.release(); log(f'標註影片 → {vp}', logpath)
    for o in outs:
        try: os.remove(o)
        except OSError: pass

if __name__ == '__main__':
    mp.freeze_support(); main()

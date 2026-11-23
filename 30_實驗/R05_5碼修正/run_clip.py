"""第五輪：用第二版 v2.1 設定（FROZEN_CONFIG_v2_1.json，只把 aggregate.maxlen 由 4 改為 5）跑單一片段（Windows / Linux 皆可）。
沿用第四輪 run_clip.py，只改讀取的設定檔（v2 → v2_1）、加一行 maxlen 檢查，以及本說明；輸出位置一樣是本資料夾的 out\\<片段名>\\。
只 import 既有模組（..\\成果_號碼牌辨識\\src 的 videoio、extract4、aggregate2），不修改它們。
用法：python run_clip.py clips\\tpe_C_xxx.mp4
輸出：out\\<片段名>\\raw.jsonl、result.csv、<片段名>_標註.mp4、DONE.txt；進度寫進 out\\log.txt
YOLO 會自動使用 CUDA（若可用）；OCR 執行緒數由環境變數 BIB_OCR_THREADS 控制（預設 8）。
"""
import csv, json, os, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.normpath(os.path.join(HERE, '..', '成果_號碼牌辨識'))
sys.path.insert(0, os.path.join(SYS, 'src'))
CFG = json.load(open(os.path.join(SYS, 'work', 'FROZEN_CONFIG_v2_1.json'), encoding='utf-8'))
assert CFG['aggregate']['maxlen'] == 5, 'FROZEN_CONFIG_v2_1.json 的 maxlen 應為 5'
os.environ.setdefault('BIB_OCR_THREADS', '8')
OUTROOT = os.path.join(HERE, 'out')
LOGP = os.path.join(OUTROOT, 'log.txt')


def log(msg):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOGP, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def main():
    video = os.path.abspath(sys.argv[1])
    name = os.path.splitext(os.path.basename(video))[0]
    outdir = os.path.join(OUTROOT, name)
    os.makedirs(outdir, exist_ok=True)
    import cv2, torch
    from videoio import probe, frames
    from extract4 import process
    from aggregate2 import aggregate2
    W, H, dur = probe(video)
    E = CFG['extract']; fps = E['fps']
    ex = {k: E[k] for k in ('imgsz', 'min_h', 'top', 'bot', 'early_stop', 'hist_thr', 'jump_thr')}
    gpu = torch.cuda.is_available()
    log(f'[{name}] 開始 {W}x{H} 長度 {dur:.2f}s  GPU={"是 " + torch.cuda.get_device_name(0) if gpu else "否"}  '
        f'OCR執行緒={os.environ["BIB_OCR_THREADS"]}  fps={fps} {ex}')
    t0w = time.time(); last = t0w; st = {}
    rawp = os.path.join(outdir, 'raw.jsonl')
    with open(rawp, 'w', encoding='utf-8') as fo:
        for r in process(frames(video, 0.0, dur, fps, W, H), fps=fps, stats=st, **ex):
            fo.write(json.dumps(r) + '\n')
            if time.time() - last > 60:
                last = time.time(); log(f'[{name}]   進度 {r["t"]:.1f}/{dur:.0f}s {st}')
    t_ext = time.time() - t0w
    log(f'[{name}] 抽取完成 {st} 耗時 {t_ext:.0f}s')
    # 讀回 raw，組成 aggregate2 的輸入（與 src/run_parallel.py、aggregate2.load4 相同）
    rows, boxes = [], defaultdict(list)
    for l in open(rawp, encoding='utf-8'):
        r = json.loads(l); boxes[r['tid']].append((r['t'], r['pbox']))
        for txt, sc, bb in (r.get('texts') or []):
            rows.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc))
    preds = aggregate2(rows, **CFG['aggregate'])
    with open(os.path.join(outdir, 'result.csv'), 'w', newline='', encoding='utf-8') as fo:
        wr = csv.writer(fo); wr.writerow(['bib', 'time_s', 'first_s', 'last_s', 'score', 'tids'])
        for p in sorted(preds, key=lambda x: x['t']):
            tids = ';'.join(str(x) for x in sorted(p['tids'], key=str))
            wr.writerow([p['bib'], f'{p["t"]:.3f}', f'{p["t0"]:.3f}', f'{p["t1"]:.3f}', f'{p["score"]:.3f}', tids])
    log(f'[{name}] 定案 {len(preds)} 個號碼 → result.csv')
    # 標註影片：照抄 src/run_parallel.py 的疊字邏輯
    label = {}
    for p in preds:
        for tid in p['tids']:
            if isinstance(tid, int): label[tid] = (p['bib'], p['t0'] - 1, p['t1'] + 1)
    at = defaultdict(list)
    for tid, lst in boxes.items():
        for t, b in lst: at[round(t, 3)].append((tid, b))
    vp = os.path.join(outdir, f'{name}_標註.mp4')
    vw = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
    for t, f in frames(video, 0.0, dur, fps, W, H):
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
    vw.release()
    log(f'[{name}] 標註影片完成；總耗時 {time.time() - t0w:.0f}s（抽取 {t_ext:.0f}s）')
    open(os.path.join(outdir, 'DONE.txt'), 'w').close()


if __name__ == '__main__':
    main()

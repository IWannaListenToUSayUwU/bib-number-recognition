"""馬拉松號碼牌辨識系統（命令列，第二版）。

用法：
  python bibread.py 影片.mp4 --out 結果.csv [--annotated 標註影片.mp4] [--start 秒] [--end 秒] [--fps 8]

流程：
  第一階段（辨識）：每秒取 fps 格 → YOLO11s 偵測人物 + ByteTrack 追蹤 → 編號轉移偵測（軀幹顏色/位置突變即切成新的人）
                   → 軀幹裁切 → RapidOCR（PP-OCRv4）→ 只留 2~4 位數字
  第二階段（定案）：同一人加權投票 → 子字串併入較長號碼 → 固定位置文字（車牌、看板）剔除 → 相同號碼相近時間合併
  第三階段（選用）：重新播放影片，只把「定案的號碼」畫在對應的人與時間上，影片與 CSV 完全一致
"""
import argparse, csv, json, os, subprocess, sys, time
from collections import defaultdict
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract4 import process          # noqa: E402
from aggregate2 import aggregate2     # noqa: E402

CFG_PATH = os.path.join(HERE, '..', 'work', 'FROZEN_CONFIG_v2.json')


from videoio import probe, frames  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('--out', required=True)
    ap.add_argument('--annotated'); ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float)
    ap.add_argument('--fps', type=float)
    a = ap.parse_args()
    cfg = json.load(open(CFG_PATH)) if os.path.exists(CFG_PATH) else {'extract': {}, 'aggregate': {}}
    ex = {k: v for k, v in cfg['extract'].items() if k in ('imgsz', 'min_h', 'top', 'bot', 'early_stop', 'hist_thr', 'jump_thr')}
    ag = cfg['aggregate']
    fps = a.fps or cfg['extract'].get('fps', 8)
    W, H, dur = probe(a.video)
    t1 = min(a.end or dur, dur)
    tstart = time.time()

    # 第一階段：辨識
    rows, boxes = [], defaultdict(list)
    n = 0
    for r in process(frames(a.video, a.start, t1, fps, W, H), fps=fps, **ex):
        boxes[r['tid']].append((r['t'], r['pbox']))
        for txt, sc, bb in (r.get('texts') or []):
            rows.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc))
        n += 1
        if n % 2000 == 0:
            print(f'  {r["t"]:.0f}s / {t1:.0f}s（已 {time.time() - tstart:.0f} 秒）', flush=True)

    # 第二階段：定案
    preds = aggregate2(rows, **ag)
    with open(a.out, 'w', newline='', encoding='utf-8-sig') as fo:
        wr = csv.writer(fo); wr.writerow(['bib', 'time_s', 'time_hms', 'first_s', 'last_s', 'score'])
        for p in sorted(preds, key=lambda x: x['t']):
            t = p['t']
            wr.writerow([p['bib'], f'{t:.2f}', time.strftime('%H:%M:%S', time.gmtime(t)) + f'.{int((t % 1) * 10)}',
                         f'{p["t0"]:.2f}', f'{p["t1"]:.2f}', f'{p["score"]:.3f}'])
    print(f'完成辨識：{len(preds)} 個號碼，耗時 {time.time() - tstart:.0f} 秒 → {a.out}')

    # 第三階段：只畫定案結果
    if a.annotated:
        label = {}   # tid -> (bib, t0, t1)
        for p in preds:
            for tid in p['tids']:
                if isinstance(tid, int):
                    label[tid] = (p['bib'], p['t0'], p['t1'])
        at = defaultdict(list)
        for tid, lst in boxes.items():
            for t, b in lst:
                at[t].append((tid, b))
        vw = cv2.VideoWriter(a.annotated, cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
        for t, f in frames(a.video, a.start, t1, fps, W, H):
            g = f.copy()
            for tid, (x1, y1, x2, y2) in at.get(t, []):
                lab = label.get(tid)
                if lab and lab[1] - 1.0 <= t <= lab[2] + 1.0:
                    cv2.rectangle(g, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(g, lab[0], (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5)
                    cv2.putText(g, lab[0], (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
                else:
                    cv2.rectangle(g, (x1, y1), (x2, y2), (160, 160, 160), 1)
            cv2.putText(g, f'{t:.1f}s', (10, H - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            vw.write(g)
        vw.release()
        print(f'標註影片 → {a.annotated}')


if __name__ == '__main__':
    main()

"""產生人工標註素材（與受測系統的 OCR 完全無關，只用人物追蹤來整理畫面）。
輸出：每條軌跡一張「跑者卡」（3 個最大時刻的上半身原解析度放大 2 倍），
以及每秒 1 張的全景縮圖（畫出軌跡編號，供檢查漏網跑者）。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
from ultralytics import YOLO

def run(vid, s, e, outdir, fps=10, min_h=110):
    os.makedirs(outdir, exist_ok=True)
    m = YOLO('models/yolo11s.pt')
    tracks = {}          # id -> list of (t, box, area)
    frames = {}
    sheet = []
    for t, f in iter_frames(vid, s, e, fps=fps):
        r = m.track(f, classes=[0], conf=0.25, imgsz=960, persist=True, tracker='bytetrack.yaml', verbose=False)[0]
        if r.boxes.id is None:
            ids, boxes = [], []
        else:
            ids = r.boxes.id.int().tolist(); boxes = r.boxes.xyxy.tolist()
        key = round(t, 2)
        for i, b in zip(ids, boxes):
            h = b[3] - b[1]
            tracks.setdefault(i, []).append((key, b, h))
        frames[key] = f
        # 只保留可能用到的影格：保留每條軌跡目前最大的 3 張即可，記憶體控制
        if len(frames) > 400:
            keep = set()
            for tr in tracks.values():
                for x in sorted(tr, key=lambda z: -z[2])[:3]:
                    keep.add(x[0])
            for k in list(frames):
                if k not in keep and k < key - 2:
                    frames.pop(k)
        if abs((t - s) - round(t - s)) < 0.5 / fps:
            g = f.copy()
            for i, b in zip(ids, boxes):
                if b[3] - b[1] >= min_h:
                    cv2.rectangle(g, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (0, 255, 0), 2)
                    cv2.putText(g, str(i), (int(b[0]), int(b[1]) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(g, f'{t:.0f}s', (10, 700), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            sheet.append(cv2.resize(g, (640, 360)))
    # 全景圖：每張 2x2 = 1280x720
    for k in range(0, len(sheet), 4):
        grp = sheet[k:k + 4] + [np.zeros((360, 640, 3), np.uint8)] * (4 - len(sheet[k:k + 4]))
        cv2.imwrite(f'{outdir}/overview_{k // 4:02d}.jpg', np.vstack([np.hstack(grp[:2]), np.hstack(grp[2:])]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    # 跑者卡
    meta = []
    for i, tr in sorted(tracks.items()):
        if max(x[2] for x in tr) < min_h:
            continue
        best = []
        for x in sorted(tr, key=lambda z: -z[2]):
            if x[0] in frames and all(abs(x[0] - y[0]) >= 0.3 for y in best):
                best.append(x)
            if len(best) == 3:
                break
        crops = []
        for t, b, h in best:
            x1, y1, x2, y2 = map(int, b); bh = y2 - y1; bw = x2 - x1
            c = frames[t][max(0, y1 + int(0.1 * bh)):y1 + int(0.7 * bh), max(0, x1 - int(0.1 * bw)):x2 + int(0.1 * bw)]
            c = cv2.resize(c, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            c = cv2.resize(c, (int(c.shape[1] * 360 / c.shape[0]), 360))
            crops.append(c)
        card = np.hstack(crops)
        cv2.putText(card, f'track {i}', (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imwrite(f'{outdir}/card_{i:04d}.jpg', card, [cv2.IMWRITE_JPEG_QUALITY, 92])
        meta.append({'track': i, 't_first': tr[0][0], 't_last': tr[-1][0], 't_best': best[0][0], 'max_h': round(max(x[2] for x in tr))})
    json.dump(meta, open(f'{outdir}/tracks.json', 'w'), indent=1)
    print(vid, s, len(meta), 'cards', len(sheet), 'overview frames')

if __name__ == '__main__':
    split = json.load(open('work/split.json'))
    which = sys.argv[1]     # dev / test
    vids = sys.argv[2:] or ['v1', 'v2', 'v3']
    for v in vids:
        for c in split[v][which]:
            run(v, c['start'], c['end'], f'work/gt/{which}/{v}_{c["start"]}')

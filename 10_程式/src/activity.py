"""每 5 秒偵測一次人，統計近鏡頭人數（框高 >= 180px，即號碼牌大致可讀的距離）。"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames, DURATION
from ultralytics import YOLO
m = YOLO('models/yolo11n.pt')
out = {}
for vid in ['v1', 'v2', 'v3']:
    rows = []
    for t, f in iter_frames(vid, 0, DURATION[vid], fps=0.2):
        r = m.predict(f, classes=[0], conf=0.3, imgsz=640, verbose=False)[0]
        hs = [float(b[3] - b[1]) for b in r.boxes.xyxy.tolist()]
        rows.append([round(t, 1), len(hs), sum(h >= 180 for h in hs)])
    out[vid] = rows
    print(vid, len(rows), flush=True)
json.dump(out, open('work/activity.json', 'w'))

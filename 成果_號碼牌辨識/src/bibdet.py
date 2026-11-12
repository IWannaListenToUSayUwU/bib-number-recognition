"""ericBayless/bib-detector 的 YOLOv4-tiny 號碼牌偵測器與 SVHN 數字偵測器（OpenCV DNN, CPU）。"""
import cv2, numpy as np, os
M = os.path.join(os.path.dirname(__file__), '..', 'models', 'eb')

class Darknet:
    def __init__(self, cfg, w, size=416, letterbox=True):
        self.letterbox = letterbox
        self.net = cv2.dnn.readNetFromDarknet(cfg, w)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.ln = self.net.getUnconnectedOutLayersNames()
        self.size = size
    def __call__(self, img, conf=0.3, nms=0.4, size=None):
        s = size or self.size
        h0, w0 = img.shape[:2]
        if self.letterbox and h0 != w0:   # 補邊成正方形，避免拉伸變形
            m = max(h0, w0)
            pad = np.full((m, m, 3), 114, np.uint8); pad[:h0, :w0] = img; img = pad
        H, W = img.shape[:2]
        blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (s, s), swapRB=True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.ln)
        boxes, scores, cls = [], [], []
        for o in outs:
            for d in o:
                sc = d[5:]; c = int(np.argmax(sc)); p = float(sc[c]) * float(d[4]) if False else float(sc[c])
                if p < conf:
                    continue
                cx, cy, w, h = d[0] * W, d[1] * H, d[2] * W, d[3] * H
                boxes.append([int(cx - w / 2), int(cy - h / 2), int(w), int(h)]); scores.append(p); cls.append(c)
        idx = cv2.dnn.NMSBoxes(boxes, scores, conf, nms)
        idx = np.array(idx).flatten() if len(idx) else []
        return [(boxes[i], scores[i], cls[i]) for i in idx]

def bib_detector():
    return Darknet(f'{M}/RBNR2_custom-yolov4-tiny-detector.cfg', f'{M}/RBNR2_custom-yolov4-tiny-detector_best.weights')

def digit_detector():
    return Darknet(f'{M}/SVHN3_custom-yolov4-tiny-detector.cfg', f'{M}/SVHN3_custom-yolov4-tiny-detector_best.weights')

def read_digits(dd, crop, conf=0.3):
    """SVHN 數字偵測 → 由左到右排序組成號碼。"""
    r = dd(crop, conf=conf)
    if not r:
        return None, 0.0
    r = sorted(r, key=lambda x: x[0][0])
    return ''.join(str(c) for _, _, c in r), float(np.mean([s for _, s, _ in r]))

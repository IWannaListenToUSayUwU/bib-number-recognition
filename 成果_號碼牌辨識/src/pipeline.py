"""辨識管線元件。"""
import re, cv2, numpy as np

DIGITS = re.compile(r'\d+')

def torso_crops(frame, boxes, min_h=90, up_to=None):
    """由人物框裁出軀幹區（框高 10%~65%），回傳 (crop, box_in_frame)。"""
    out = []
    H, W = frame.shape[:2]
    for b in boxes:
        x1, y1, x2, y2 = b
        h = y2 - y1; w = x2 - x1
        if h < min_h:
            continue
        cx1 = int(max(0, x1 - 0.05 * w)); cx2 = int(min(W, x2 + 0.05 * w))
        cy1 = int(max(0, y1 + 0.10 * h)); cy2 = int(min(H, y1 + 0.65 * h))
        c = frame[cy1:cy2, cx1:cx2]
        if c.size == 0:
            continue
        if up_to:   # 放大到固定寬度
            s = up_to / c.shape[1]
            if s > 1:
                c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        out.append((c, (cx1, cy1, cx2, cy2)))
    return out

def digits_only(txt):
    """取出最長的連續數字串；回傳 None 表示沒有。"""
    m = DIGITS.findall(txt.replace(' ', ''))
    if not m:
        return None
    return max(m, key=len)

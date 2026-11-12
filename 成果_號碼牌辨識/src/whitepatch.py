"""啟發式號碼牌定位：上半身裡「亮、低飽和、近矩形」的區塊。"""
import cv2, numpy as np

def white_patches(crop, max_n=2):
    h, w = crop.shape[:2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    V = hsv[..., 2].astype(np.float32); S = hsv[..., 1].astype(np.float32)
    thr = max(110, np.percentile(V, 88))           # 相對亮度門檻，適應逆光/陰天
    m = ((V >= thr) & (S <= 100)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))   # 填掉黑色數字造成的洞
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = st[i]
        if bw < 0.15 * w or bw > 0.85 * w or bh < 0.08 * h or bh > 0.5 * h:
            continue
        ar = bw / bh
        fill = area / (bw * bh)
        if not (0.6 <= ar <= 3.0) or fill < 0.5:
            continue
        # 必須內含暗色筆畫（數字），否則多半是白衣服
        roi = crop[y:y + bh, x:x + bw]
        g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        dark = (g < np.percentile(g, 90) * 0.6).mean()
        if dark < 0.04:
            continue
        out.append(((x, y, bw, bh), fill * min(1, dark * 5)))
    return sorted(out, key=lambda z: -z[1])[:max_n]

"""第八輪：衣服外觀特徵（調嚴換人偵測用）。
依 re-ID 文獻的做法：
- 身體分水平條紋（上衣、褲子）分開比，任一條變了就算換人
- 上衣只取左右兩側（避開正中間每個人都一樣的白色號碼布），寬度內縮避開背景
- HSV 直方圖加入亮度：有顏色的像素用 色相12 × 飽和度2 格；
  低飽和/很暗的像素（白、灰、黑）改依亮度分 6 格，讓白衣、灰衣、黑衣分得開"""
import cv2, numpy as np

SHIRT = (0.18, 0.48)      # 上衣：人物框高度 18%–48%
SHORTS = (0.52, 0.68)     # 褲子：52%–68%

def _hist(px_hsv):
    if px_hsv.size == 0:
        return None
    h = px_hsv[:, 0].astype(np.int32); s = px_hsv[:, 1].astype(np.int32); v = px_hsv[:, 2].astype(np.int32)
    chrom = (s >= 50) & (v >= 50)
    hb = np.minimum(h[chrom] * 12 // 180, 11); sb = (s[chrom] >= 150).astype(np.int32)
    c = np.bincount(hb * 2 + sb, minlength=24)
    a = np.bincount(np.minimum(v[~chrom] * 6 // 256, 5), minlength=6)
    out = np.concatenate([c, a]).astype(np.float64)
    return out / (out.sum() + 1e-9)

def stripe_feats(frame, box):
    """回傳 (上衣直方圖, 褲子直方圖)；某條太小則為 None。"""
    x1, y1, x2, y2 = box; w = x2 - x1; h = y2 - y1
    H, W = frame.shape[:2]
    def region(r0, r1, cols):
        ya, yb = max(0, int(y1 + r0 * h)), min(H, int(y1 + r1 * h))
        parts = []
        for c0, c1 in cols:
            xa, xb = max(0, int(x1 + c0 * w)), min(W, int(x1 + c1 * w))
            if yb - ya >= 4 and xb - xa >= 3:
                parts.append(frame[ya:yb, xa:xb].reshape(-1, 3))
        if not parts:
            return None
        px = np.concatenate(parts).reshape(-1, 1, 3)
        return _hist(cv2.cvtColor(px, cv2.COLOR_BGR2HSV).reshape(-1, 3))
    shirt = region(*SHIRT, [(0.15, 0.38), (0.62, 0.85)])
    shorts = region(*SHORTS, [(0.20, 0.80)])
    return shirt, shorts

def bhatt(a, b):
    return float(np.sqrt(max(0.0, 1 - np.sum(np.sqrt(a * b)))))

def feat_dist(fa, fb):
    """兩組條紋特徵的距離 = 各條 Bhattacharyya 距離的最大值（任一條變了就算變）。"""
    ds = [bhatt(a, b) for a, b in zip(fa, fb) if a is not None and b is not None]
    return max(ds) if ds else 0.0

def feat_mix(ref, new, alpha):
    return tuple((r if n is None else n if r is None else (1 - alpha) * r + alpha * n) for r, n in zip(ref, new))

r"""R12：量畫面是否穩定（鏡頭有沒有移動、變焦、剪接），用來挑「機位固定」的片段。
做法：每隔 step 秒取一格，用上半部（終點拱門、看台這些不動的背景）找 ORB 特徵點，
和前一個取樣格求相似變換（平移＋縮放＋旋轉）；也和固定參考格比，看整段是否同一個構圖。
用法：python 30_實驗/R12_第二機位/r12_stability.py [step=10] [t0=0] [t1=片長] [參考秒數=4000]
輸出：30_實驗/R12_第二機位/總覽/穩定度_<step>s_<t0>-<t1>.csv"""
import csv, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r12_overview import grab, SRC, OUT  # noqa: E402
import subprocess

ORB = cv2.ORB_create(3000); BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def feat(f):
    g = cv2.cvtColor(cv2.resize(f, (960, 540), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    mask = np.zeros_like(g); mask[:250, :] = 255  # 上半部：拱門、計時鐘、看台
    return ORB.detectAndCompute(g, mask)


def rel(a, b):
    """b 相對 a 的相似變換：回傳 (dx, dy, scale, 內點數)；以 1920 寬的像素為單位。"""
    if a[1] is None or b[1] is None: return None
    m = BF.match(a[1], b[1])
    if len(m) < 20: return None
    p = np.float32([a[0][x.queryIdx].pt for x in m]); q = np.float32([b[0][x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(p, q, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if M is None: return None
    s = float(np.hypot(M[0, 0], M[1, 0]))
    # 畫面中心點被移到哪裡（換回 1920 寬）
    c = np.array([480, 270, 1.0]); d = M @ c - c[:2]
    return round(float(d[0]) * 2, 1), round(float(d[1]) * 2, 1), round(s, 4), int(inl.sum())


def main():
    a = sys.argv[1:]
    step = float(a[0]) if len(a) > 0 else 10.0; t0 = float(a[1]) if len(a) > 1 else 0.0
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', SRC],
                               capture_output=True, text=True).stdout)
    t1 = float(a[2]) if len(a) > 2 else dur - 1; tref = float(a[3]) if len(a) > 3 else 4000.0
    ref = feat(grab(tref)[0]); prev = None; rows = []
    for t in np.arange(t0, t1, step):
        f = feat(grab(t)[0]); r1 = rel(prev, f) if prev is not None else None; r2 = rel(ref, f)
        rows.append(dict(t=round(float(t), 2), d_prev_x=r1[0] if r1 else '', d_prev_y=r1[1] if r1 else '', s_prev=r1[2] if r1 else '',
                         inl_prev=r1[3] if r1 else '', d_ref_x=r2[0] if r2 else '', d_ref_y=r2[1] if r2 else '',
                         s_ref=r2[2] if r2 else '', inl_ref=r2[3] if r2 else ''))
        prev = f
    p = os.path.join(OUT, f'穩定度_{step:g}s_{t0:g}-{t1:g}.csv')
    with open(p, 'w', encoding='utf-8-sig', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(p, len(rows))


if __name__ == '__main__':
    main()

"""逐格標註素材（不依賴任何偵測/追蹤器，避免標準答案與系統共享盲點）。
每秒 2 格，裁出「號碼牌可能可讀」的區域並放大，左上角印全域時間。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from frames import iter_frames
# (x1,y1,x2,y2, 放大倍率, 每張圖疊幾格)
ZONE = {'v1': (250, 150, 1280, 600, 1.3, 2),
        'v2': (200, 120, 1280, 720, 1.25, 1),
        'v3': (380, 150, 1280, 620, 1.5, 2)}
def run(vid, s, e, outdir, fps=2):
    os.makedirs(outdir, exist_ok=True)
    x1, y1, x2, y2, sc, per = ZONE[vid]
    buf, n = [], 0
    for t, f in iter_frames(vid, s, e, fps=fps):
        c = cv2.resize(f[y1:y2, x1:x2], None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
        cv2.rectangle(c, (0, 0), (150, 40), (0, 0, 0), -1)
        cv2.putText(c, f'{t:.1f}s', (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        buf.append(c)
        if len(buf) == per:
            cv2.imwrite(f'{outdir}/f_{n:03d}.jpg', np.vstack(buf), [cv2.IMWRITE_JPEG_QUALITY, 93]); n += 1; buf = []
    if buf:
        cv2.imwrite(f'{outdir}/f_{n:03d}.jpg', np.vstack(buf), [cv2.IMWRITE_JPEG_QUALITY, 93]); n += 1
    print(vid, s, n, 'images', flush=True)
if __name__ == '__main__':
    split = json.load(open('work/split.json'))
    for which in ['dev', 'test']:
        for v in ['v1', 'v2', 'v3']:
            for c in split[v][which]:
                run(v, c['start'], c['end'], f'work/gtf/{which}/{v}_{c["start"]}')

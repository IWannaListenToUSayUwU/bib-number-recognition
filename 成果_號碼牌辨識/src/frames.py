"""影片來源抽象：把 v3 的三段切片拼回全域時間軸，統一用 ffmpeg 讀影格。"""
import subprocess, json, numpy as np, os

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
VIDEOS = {
    'v1': [('v1.mp4', 0.0)],
    'v2': [('v2.mp4', 0.0)],
    'v3': [('v3_part0.mp4', 0.0), ('v3_part1.mp4', 1200.0), ('v3_part2.mp4', 2400.0)],
}
DURATION = {'v1': 1700.4, 'v2': 1078.7, 'v3': 3535.7}
FPS = {'v1': 30000 / 1001, 'v2': 30000 / 1001, 'v3': 25.0}
W, H = 1280, 720


def _locate(vid, t):
    """全域秒數 -> (檔案, 檔內偏移)。v3 切片保留原時間戳 (start_time=1200...)，所以用 -ss 全域時間即可。"""
    parts = VIDEOS[vid]
    for fn, off in reversed(parts):
        if t >= off:
            return os.path.join(DATA, fn), off
    return os.path.join(DATA, parts[0][0]), 0.0


def iter_frames(vid, t0, t1, fps=None, scale=None):
    """產生 (全域時間, BGR 影格)。fps=None 表示原始每一格。不跨切片邊界時最有效率。"""
    t = t0
    while t < t1:
        path, off = _locate(vid, t)
        # 切片檔案的結束點
        nxt = [o for _, o in VIDEOS[vid] if o > off]
        seg_end = min(t1, nxt[0] if nxt else 1e9)
        w, h = (W, H) if scale is None else scale
        vf = []
        if fps:
            vf.append(f'fps={fps}')
        if scale:
            vf.append(f'scale={w}:{h}')
        # 切片保留了原始時間戳，-ss 用檔內相對時間 (t - off)
        cmd = ['ffmpeg', '-v', 'error', '-ss', f'{t - off:.3f}', '-i', path, '-t', f'{seg_end - t:.3f}']
        if vf:
            cmd += ['-vf', ','.join(vf)]
        cmd += ['-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        step = 1.0 / (fps or FPS[vid])
        i = 0
        try:
            while True:
                buf = p.stdout.read(w * h * 3)
                if len(buf) < w * h * 3:
                    break
                yield t + i * step, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
                i += 1
        finally:
            p.kill(); p.wait()
        t = seg_end


def grab(vid, t):
    for _, f in iter_frames(vid, t, t + 0.5, fps=None):
        return f

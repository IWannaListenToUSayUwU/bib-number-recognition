"""跨平台影片讀取：優先用系統 ffmpeg，沒有就用 imageio-ffmpeg 內附的執行檔；尺寸/長度用 OpenCV 取得（不需 ffprobe）。"""
import os, shutil, subprocess, numpy as np, cv2

def ffmpeg_exe():
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def probe(path):
    cap = cv2.VideoCapture(path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30; n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return W, H, (n / fps if n > 0 else 0.0)

def frames(path, t0, t1, fps, W, H):
    cmd = [ffmpeg_exe(), '-v', 'error', '-ss', f'{t0:.3f}', '-i', path, '-t', f'{t1 - t0:.3f}',
           '-vf', f'fps={fps}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=flags)
    i = 0
    try:
        while True:
            buf = p.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            yield round(t0 + i / fps, 3), np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            i += 1
    finally:
        p.kill(); p.wait()

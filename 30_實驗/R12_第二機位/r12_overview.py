r"""R12 第二機位：整支影片的總覽（只讀原始影片，不改它）。
用法（在專案根目錄）：python 30_實驗/R12_第二機位/r12_overview.py [間隔秒數，預設 60]
輸出：30_實驗/R12_第二機位/總覽/總覽_<n>.jpg（每張 5×5 格，左上角是原片時間）、重複格檢查.txt"""
import os, subprocess, sys
import cv2, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, '總覽')
SRC = os.path.join(ROOT, '00_原始素材', '【賽事精華】 台北馬最完整全馬終點衝線時刻  快找找看你在哪裡 ! [15_48-1_54_49].mp4')


def grab(t, n=1):
    """用 ffmpeg 取 t 秒起的 n 格（快速定位），回傳 BGR 陣列清單。"""
    p = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', SRC, '-frames:v', str(n),
                        '-f', 'image2pipe', '-vcodec', 'bmp', '-'], capture_output=True, check=True).stdout
    out = []; i = 0
    while i < len(p):
        size = int.from_bytes(p[i + 2:i + 6], 'little'); out.append(cv2.imdecode(np.frombuffer(p[i:i + size], np.uint8), 1)); i += size
    return out


def main():
    step = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    os.makedirs(OUT, exist_ok=True)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', SRC],
                               capture_output=True, text=True).stdout)
    ts = list(np.arange(0, dur - 1, step)); tiles = []
    for t in ts:
        f = grab(t)[0]; f = cv2.resize(f, (384, 216), interpolation=cv2.INTER_AREA)
        m, s = divmod(int(t), 60)
        cv2.putText(f, f'{m}:{s:02d} ({int(t)}s)', (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(f, f'{m}:{s:02d} ({int(t)}s)', (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        tiles.append(f)
    for k in range(0, len(tiles), 25):
        grp = tiles[k:k + 25] + [np.zeros_like(tiles[0])] * (25 - len(tiles[k:k + 25]))
        sheet = np.vstack([np.hstack(grp[r * 5:(r + 1) * 5]) for r in range(5)])
        cv2.imencode('.jpg', sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(os.path.join(OUT, f'總覽_{k // 25 + 1}.jpg'))
    # 每秒 60 格是不是真的 60 格：取幾個時間點連續 12 格，看相鄰格是否完全相同
    lines = []
    for t in (300, dur / 2, dur - 300):
        fr = grab(t, 12); d = [float(np.abs(fr[i].astype(int) - fr[i - 1].astype(int)).mean()) for i in range(1, len(fr))]
        lines.append(f't={t:.0f}s 相鄰格平均差：' + ' '.join(f'{x:.2f}' for x in d))
    open(os.path.join(OUT, '重複格檢查.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(f'{len(ts)} 張 → {OUT}'); print('\n'.join(lines))


if __name__ == '__main__':
    main()

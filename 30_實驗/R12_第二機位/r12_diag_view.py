r"""R12 診斷圖：把正式流程的人框（綠）和 OCR 實際裁切範圍（人框高度 22%～72%，黃）畫在原始畫面上，讀到的文字標在旁邊。
用法：python 30_實驗/R12_第二機位/r12_diag_view.py <片段> <秒數> [<秒數> ...]
輸出：診斷\框_<片段>_<秒數>.jpg（只分析、不改參數）"""
import json, os, sys, subprocess
import cv2, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
TOP, BOT, MIN_H = 0.22, 0.72, 100   # FROZEN_CONFIG_v2_2 的 extract_args（run_info.json）


def frame(clip, t):
    p = os.path.join(ROOT, '20_測試基準', 'clips', clip + '.mp4')
    b = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', p, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'bmp', '-'],
                       capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)


def main():
    clip = sys.argv[1]; ts = [float(x) for x in sys.argv[2:]]
    recs = [json.loads(l) for l in open(os.path.join(HERE, 'out', 'FROZEN_CONFIG_v2_2', clip, 'raw.jsonl'), encoding='utf-8')]
    for t in ts:
        tt = min({r['t'] for r in recs}, key=lambda x: abs(x - t))
        f = frame(clip, tt)
        for r in recs:
            if r['t'] != tt: continue
            x1, y1, x2, y2 = r['pbox']; h = y2 - y1
            cv2.rectangle(f, (x1, y1), (x2, y2), (0, 255, 0), 2)
            if h >= MIN_H:
                cv2.rectangle(f, (x1, y1 + int(TOP * h)), (x2, y1 + int(BOT * h)), (0, 220, 255), 2)
            txt = ' '.join(x[0] for x in (r['texts'] or []) if x[0].isascii())
            cv2.putText(f, f"{r['tid']} {txt}"[:30], (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            for x in (r['texts'] or []):
                bx = x[2]; cv2.rectangle(f, (bx[0], bx[1]), (bx[2], bx[3]), (255, 0, 255), 2)
        o = os.path.join(HERE, '診斷', f'框_{clip}_{t:g}.jpg')
        cv2.imencode('.jpg', f, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(o); print(o, tt)


if __name__ == '__main__':
    main()

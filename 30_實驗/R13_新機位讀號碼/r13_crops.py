r"""R13 診斷圖：官方名單上的跑者，沿著跑動路徑每 0.5 秒取一張「OCR 實際看到的裁切」（人框高度 22%～72%、左右各加 8%），
標上人框中心 x、人框是否貼底、OCR 讀到的字。用來判斷號碼在線附近是「看得清但 OCR 讀不出」還是「本來就看不清」。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_crops.py <調整集片段> [人數=8] [raw 路徑（預設：基準跑完的 raw）]
輸出：30_實驗/R13_新機位讀號碼/診斷/裁切_<片段>.jpg（只分析、不改參數；只用調整集）"""
import json, os, subprocess, sys
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path  # noqa: E402
TH = 150   # 每張縮圖高度


def frame(clip, t):
    p = os.path.join(L.ROOT, '20_測試基準', 'clips', clip + '.mp4')
    b = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', p, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'bmp', '-'], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)


def main():
    clip = sys.argv[1]; k = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rp = sys.argv[3] if len(sys.argv) > 3 else raw_path('FROZEN_CONFIG_v2_2', clip)
    recs = [json.loads(l) for l in open(rp, encoding='utf-8')]
    ev = L.crossing_events(rp, clip); t0 = L.clock_at_t0(clip)
    offl = {r['bib']: L.sec(r['time']) for r in L.official()['rows'] if t0 + 3 <= L.sec(r['time']) <= t0 + 57}
    # 官方跑者 ↔ 過線事件：時間差 ≤ 1 秒、最接近的那一個（只是為了找到這個人的軌跡；號碼不看系統讀的）
    pairs = []
    for b, x in sorted(offl.items(), key=lambda z: z[1]):
        c = [e for e in ev if abs(t0 + e['t_cross'] - x - 0.3) <= 1.0]
        if len(c) == 1: pairs.append((b, c[0]))
    step = max(1, len(pairs) // k); pairs = pairs[::step][:k]
    rows = []
    for b, e in pairs:
        tr = sorted((r for r in recs if r.get('rawtid') == e['rawtid']), key=lambda r: r['t'])
        if not tr: continue
        picks = []; last = -9
        for r in tr:
            if r['t'] - last >= 0.5: picks.append(r); last = r['t']
        tiles = []
        for r in picks[:14]:
            f = frame(clip, r['t']); H, W = f.shape[:2]
            x1, y1, x2, y2 = r['pbox']; h = y2 - y1; w = x2 - x1
            cx1 = max(0, x1 - int(.08 * w)); cx2 = min(W, x2 + int(.08 * w)); cy1 = max(0, y1 + int(.22 * h)); cy2 = min(H, y1 + int(.72 * h))
            cr = f[cy1:cy2, cx1:cx2]
            if cr.size == 0: continue
            s = TH / cr.shape[0]; cr = cv2.resize(cr, (max(1, int(cr.shape[1] * s)), TH))
            txt = ' '.join(t[0] for t in (r['texts'] or []) if t[0].isascii())[:14] if r['texts'] is not None else '(no OCR)'
            lab = f"x{(x1 + x2) // 2} h{h}{' BOT' if y2 >= H - 2 else ''} t{r['t']:.1f}"
            pad = np.full((36, cr.shape[1], 3), 255, np.uint8)
            cv2.putText(pad, lab, (2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
            cv2.putText(pad, txt, (2, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 200), 1)
            tiles.append(np.vstack([pad, cr]))
        if not tiles: continue
        head = np.full((TH + 36, 120, 3), 230, np.uint8)
        cv2.putText(head, b, (4, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.putText(head, f"cross {e['t_cross']:.1f}s", (4, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        cv2.putText(head, f"sys: {e['bib'] or '-'}", (4, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 200), 1)
        rows.append(np.hstack([head] + tiles))
    Wm = max(r.shape[1] for r in rows)
    img = np.vstack([np.hstack([r, np.full((r.shape[0], Wm - r.shape[1], 3), 255, np.uint8)]) for r in rows])
    o = os.path.join(HERE, '診斷', f'裁切_{clip}.jpg'); os.makedirs(os.path.dirname(o), exist_ok=True)
    cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(o); print(o, img.shape, len(rows))


if __name__ == '__main__':
    main()

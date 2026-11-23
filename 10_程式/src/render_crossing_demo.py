r"""過線計時 demo 影片（2026-11-23）：把「號碼＋過線時間」畫在片段上。不需要 GPU（用已經跑好的 raw.jsonl＋過線事件）。
畫面內容：計時線（黃）、追蹤中的人（灰框）、過線的人（綠框＋號碼＋過線時間，過線後顯示 3 秒）、右上角「最近過線」名單。
過線事件用三層設定算（settings.for_clip ＋ bibrules.events），所以號碼規則、計時線都和正式流程相同。
用法（在專案根目錄）：
  python 10_程式/src/render_crossing_demo.py <全域設定> <片段> <raw.jsonl> <輸出.mp4> [--gun 片段第 0 秒的槍聲時間（秒）] [--title 標題]
輸出：<輸出.mp4>（H.264、縮成 1280 寬）與同名 .csv（過線事件：片段秒數、槍聲時間、號碼）"""
import argparse, csv, json, os, subprocess, sys
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings, bibrules  # noqa: E402

FONT = next((p for p in (r'C:\Windows\Fonts\msjhbd.ttc', r'C:\Windows\Fonts\msjh.ttc', r'C:\Windows\Fonts\NotoSansTC-VF.ttf') if os.path.exists(p)), None)


def hms(s):
    s = max(0.0, s); h = int(s // 3600); m = int(s % 3600 // 60); x = s % 60
    return f'{h}:{m:02d}:{x:04.1f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('global_name'); ap.add_argument('clip'); ap.add_argument('raw'); ap.add_argument('out')
    ap.add_argument('--gun', type=float, default=None); ap.add_argument('--title', default='')
    a = ap.parse_args()
    S = settings.for_clip(a.global_name, a.clip)
    vp = os.path.join(settings.ROOT, '20_測試基準', 'clips', a.clip + '.mp4')
    ev = bibrules.events(a.raw, S, video_path=vp)
    ev = sorted(ev, key=lambda e: e['t_cross'])
    tlabel = (lambda t: hms(a.gun + t)) if a.gun is not None else (lambda t: f'片段 {t:5.2f} 秒')
    with open(os.path.splitext(a.out)[0] + '.csv', 'w', newline='', encoding='utf-8-sig') as fo:
        w = csv.writer(fo); w.writerow(['過線（片段秒數）', '槍聲時間' if a.gun is not None else '', '號碼（空白＝讀不出）', '定案方式'])
        for e in ev: w.writerow([f"{e['t_cross']:.3f}", hms(a.gun + e['t_cross']) if a.gun is not None else '', e['bib'], e.get('decided_by', '')])
    # raw：每個取樣時間 → 這一格的人框
    frames = {}
    for l in open(a.raw, encoding='utf-8'):
        r = json.loads(l); frames.setdefault(r['t'], []).append(r)
    ts = sorted(frames)
    crossed = {e['rawtid']: e for e in ev}
    L = S['camera']['line']; p1, p2 = tuple(map(int, L['p1'])), tuple(map(int, L['p2']))
    cap = cv2.VideoCapture(vp); fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tmp = a.out + '.tmp.mp4'
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
    fBig = ImageFont.truetype(FONT, 30); fMid = ImageFont.truetype(FONT, 24); fSm = ImageFont.truetype(FONT, 20)
    fi = 0; k = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        t = fi / fps; fi += 1
        while k + 1 < len(ts) and ts[k + 1] <= t + 1e-6: k += 1
        recs = frames.get(ts[k], []) if ts and ts[k] <= t + 1e-6 and t - ts[k] < 0.2 else []
        cv2.line(f, p1, p2, (0, 215, 255), 4)
        labels = []
        for r in recs:
            x1, y1, x2, y2 = r['pbox']; e = crossed.get(r.get('rawtid'))
            if e is not None and e['t_cross'] <= t <= e['t_cross'] + 3.0:
                cv2.rectangle(f, (x1, y1), (x2, y2), (60, 220, 60), 5)
                labels.append((x1, y1, e))
            else:
                cv2.rectangle(f, (x1, y1), (x2, y2), (235, 235, 235), 2)
        img = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(img, 'RGBA')
        for x1, y1, e in labels:
            txt = (e['bib'] or '讀不出') + '  ' + tlabel(e['t_cross'])
            tw = d.textlength(txt, font=fMid); y = max(0, y1 - 34)
            d.rectangle([x1, y, x1 + tw + 12, y + 32], fill=(0, 0, 0, 170)); d.text((x1 + 6, y + 2), txt, font=fMid, fill=(120, 255, 120))
        # 右上角：最近過線
        done = [e for e in ev if e['t_cross'] <= t][-8:]
        pw, ph = 380, 52 + 30 * max(1, len(done)); px = W - pw - 16
        d.rectangle([px, 16, px + pw, 16 + ph], fill=(0, 0, 0, 160))
        d.text((px + 12, 22), f'最近過線（共 {sum(1 for e in ev if e["t_cross"] <= t)} 人）', font=fMid, fill=(255, 255, 255))
        for i, e in enumerate(reversed(done)):
            d.text((px + 12, 56 + 30 * i), f"{(e['bib'] or '讀不出'):>6s}   {tlabel(e['t_cross'])}", font=fSm, fill=(120, 255, 120) if e['bib'] else (200, 200, 200))
        if a.title:
            tw = d.textlength(a.title, font=fBig); d.rectangle([16, H - 60, 16 + tw + 20, H - 14], fill=(0, 0, 0, 160)); d.text((26, H - 56), a.title, font=fBig, fill=(255, 255, 255))
        vw.write(cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR))
    vw.release(); cap.release()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-vf', 'scale=1280:-2', '-c:v', 'libx264', '-crf', '28', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.out], check=True)
    os.remove(tmp)
    print(a.out, f'{fi} 格；過線事件 {len(ev)}（有號碼 {sum(1 for e in ev if e["bib"])}）；定案規則 {S["mode"]}')


if __name__ == '__main__':
    main()

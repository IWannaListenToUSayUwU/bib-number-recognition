r"""R13 自動對時試作（研究流程 第 7 節 #11）：用 RapidOCR 讀畫面上的 CITIZEN 計時鐘，自動算出「片段時間 → 槍聲時間」的位移，和 R12 手動量的值比較。
做法：每 0.5 秒取一格，裁時鐘區域（1920×1080 畫面的 y 170–290、x 990–1270），OCR 後解析成 H:MM:SS。
  某格讀到整秒 S（時鐘顯示 S，表示槍聲時間在 [S, S+1)）→ 位移 off ∈ [S − t, S + 1 − t)。
  先用眾數（S − t 取整）排除讀錯的格（例：秒數個位壞掉一段，0 看起來像 9），再把剩下的區間取交集，取中點。
必須用 bibread 環境的 python（RapidOCR）：
  %USERPROFILE%\anaconda3\envs\bibread\python.exe 30_實驗/R13_新機位讀號碼/r13_clock_auto.py
輸出：診斷\自動對時.json"""
import json, os, re, sys
from collections import Counter
import cv2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from rapidocr_onnxruntime import RapidOCR  # noqa: E402
CLIPS = ['tpe2t_2700', 'tpe2t_3600', 'tpe2t_4800', 'tpe2t_5700']


def parse(texts):
    s = re.sub(r'[^0-9]', '', ''.join(texts))
    if len(s) == 5:                      # H MM SS
        h, m, x = int(s[0]), int(s[1:3]), int(s[3:5])
        if m < 60 and x < 60: return h * 3600 + m * 60 + x
    return None


def main():
    nt = int(os.environ.get('BIB_OCR_THREADS', '4'))
    ocr = RapidOCR(det_intra_op_num_threads=nt, rec_intra_op_num_threads=nt, cls_intra_op_num_threads=nt)
    res = {}
    for c in CLIPS:
        cap = cv2.VideoCapture(os.path.join(L.ROOT, '20_測試基準', 'clips', c + '.mp4')); samples = []; fi = -1
        while True:
            ok, f = cap.read(); fi += 1
            if not ok: break
            if fi % 15: continue                       # 每 0.5 秒
            t = fi / 30.0; out, _ = ocr(f[170:290, 990:1270], use_cls=False)
            S = parse([x[1] for x in (out or [])])
            samples.append((t, S, ''.join(x[1] for x in (out or []))))
        ok_s = [(t, S) for t, S, _ in samples if S is not None]
        mode = Counter(int(S - t) for t, S in ok_s).most_common(1)[0][0] if ok_s else None
        good = [(t, S) for t, S in ok_s if mode is not None and int(S - t) in (mode - 1, mode, mode + 1)]
        lo = max((S - t for t, S in good), default=None); hi = min((S + 1 - t for t, S in good), default=None)
        # 交集為空（少數讀錯）時退回用中位數
        est = (lo + hi) / 2 if lo is not None and hi is not None and lo < hi else None
        manual = L.clock_at_t0(c)
        res[c] = dict(samples=len(samples), parsed=len(ok_s), consistent=len(good), interval=[lo, hi], estimate=est, manual=manual,
                      error=round(est - manual, 3) if est is not None else None, examples=[s[2] for s in samples[:5]])
        print(f"{c}: 取樣 {len(samples)}、解析成功 {len(ok_s)}、一致 {len(good)}；自動 {est} vs 手動 {manual} → 差 {res[c]['error']} 秒；例 {res[c]['examples']}")
    json.dump(res, open(os.path.join(HERE, '診斷', '自動對時.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

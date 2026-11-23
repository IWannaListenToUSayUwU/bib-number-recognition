r"""R13：比較各設定的抽取時間與 OCR 次數（stats.json）。v2.2 的 C、D 用 R12 正式流程那次（同一台電腦、同樣一次只跑一個）。
注意：使用者常開遊戲、或 Claude 同時跑 CPU 分析時，時間數字不完全可比；這裡只比同一段片段在不同設定下的倍數。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_speed_compare.py [設定名 ...]（預設 R13_E5_det320 R13_FULL_ocr R13_E2_bottomext）"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from r13_e1 import SUBDIR, TUNE, GUARD  # noqa: E402
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def stats(src, c):
    if src == 'FROZEN_CONFIG_v2_2':
        d = os.path.join(ROOT, '30_實驗', 'R12_第二機位', 'out', src, c) if c in GUARD else os.path.join(HERE, 'out', src, c)
    else:
        d = os.path.join(HERE, SUBDIR.get(src, 'out'), src, c)
    p = os.path.join(d, 'stats.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(os.path.join(d, 'DONE.txt')) and os.path.exists(p) else None


def main():
    srcs = sys.argv[1:] or ['R13_E5_det320', 'R13_FULL_ocr', 'R13_E2_bottomext']
    for c in GUARD + TUNE:
        b = stats('FROZEN_CONFIG_v2_2', c)
        if not b: continue
        line = f"{c:11s} v2.2 {b['extract_sec']:5d} 秒、OCR {b['stats']['ocr']:5d}"
        for s in srcs:
            x = stats(s, c)
            if x: line += f" ｜ {s} {x['extract_sec']:5d} 秒（×{x['extract_sec'] / b['extract_sec']:.2f}）、OCR {x['stats']['ocr']:5d}"
        print(line + f"｜即時倍數（v2.2）{b['extract_sec'] / 60:.1f}")


if __name__ == '__main__':
    main()

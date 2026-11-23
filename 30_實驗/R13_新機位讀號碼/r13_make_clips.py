r"""R13：從第二機位原片剪出調整集（tune）片段到 20_測試基準\clips，剪法和 R12 r12_make_clips.py 完全相同（fps=30、crf 16、無聲）。
選段規則（事前寫死，見 計畫.md ②）：2700、3600、4800、5700 秒起各 60 秒。已存在的不覆寫。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_make_clips.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '30_實驗', 'R12_第二機位'))
import r12_make_clips as M  # noqa: E402
M.SEGS = [('tpe2t_2700', 2700), ('tpe2t_3600', 3600), ('tpe2t_4800', 4800), ('tpe2t_5700', 5700)]
M.HERE = HERE  # 片段資訊.json 寫到 R13
if __name__ == '__main__':
    M.main()

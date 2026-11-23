r"""用官方完賽名單檢查舊基準 20_測試基準\gt（A～D 段，舊 AI 標註，score.py 用）的 sure 號碼（研究流程 第 7 節 #3）。只產生清單，不改答案。
每段用 sure 號碼估「官方時間 − 最後出現時間」的中位數，容忍 3 個 MAD（至少 20 秒）。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_oldgt_check.py　輸出：診斷\舊答案_官方名單核對.json"""
import json, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
off = {r['bib']: L.sec(r['time']) for r in L.official()['rows']}
out = {}
for c in ['tpe_A_300', 'tpe_B_1200', 'tpe_C_600', 'tpe_D_1800']:
    p = os.path.join(L.ROOT, '20_測試基準', 'gt', c + '.json')
    if not os.path.exists(p): continue
    g = json.load(open(p, encoding='utf-8')); sure = g['sure']
    d = [off[s['bib']] - s['t1'] for s in sure if s['bib'] in off]
    m = statistics.median(d); mad = statistics.median(abs(x - m) for x in d); tol = max(20.0, 3 * 1.4826 * mad)
    notin = [s['bib'] for s in sure if s['bib'] not in off]
    far = [(s['bib'], round(off[s['bib']] - s['t1'] - m)) for s in sure if s['bib'] in off and abs(off[s['bib']] - s['t1'] - m) > tol]
    out[c] = dict(n_sure=len(sure), in_list=len(d), offset_median=round(m, 1), mad=round(mad, 1), tol=round(tol, 1), not_in_list=notin, time_far=far,
                  suspicious=len(notin) + len(far))
    print(c, json.dumps(out[c], ensure_ascii=False))
os.makedirs(os.path.join(HERE, '診斷'), exist_ok=True)
json.dump(out, open(os.path.join(HERE, '診斷', '舊答案_官方名單核對.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

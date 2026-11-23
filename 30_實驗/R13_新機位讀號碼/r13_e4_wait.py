r"""R13 E4：過線後等幾秒才定案號碼（decide_after，v2.2＝3 秒）——離線掃描。等越短延遲越低（即時運算），但可能還沒讀到號碼。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_e4_wait.py [號碼名單模式=v22]
片段：調整集（官方成績）＋C、D（人工答案 v1）。不跑檢查集。輸出：E4\等待秒數掃描_<模式>.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path, TUNE, GUARD  # noqa: E402


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'v22'; reg = L.registry(); res = {}
    for w in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0):
        f = n = gf = gn = bad = gw = 0; lat = []
        for c in TUNE + GUARD:
            p = raw_path('FROZEN_CONFIG_v2_2', c)
            if not os.path.exists(p): continue
            ev = L.crossing_events(p, c, mode, reg, wait=w); lat += [e['latency'] for e in ev if e['bib']]
            if c in TUNE:
                x = L.official_eval(c, ev); f += x['found']; n += x['official_in_clip']; bad += x['time_mismatch'] + x['not_in_list']
            else:
                x = L.gt_eval(c, ev); gf += x['full']; gn += x['n_gt']; gw += x['wrong']
        lat.sort(); med = lat[len(lat) // 2] if lat else None
        res[w] = dict(tune_found=f, tune_n=n, tune_wrong=bad, guard_full=gf, guard_n=gn, guard_wrong=gw, latency_median=med)
        print(f'等 {w} 秒：調整集 {f}/{n}（錯誤輸出 {bad}）｜C+D {gf}/{gn}（錯誤輸出 {gw}）｜有號碼事件的延遲中位數 {med} 秒')
    os.makedirs(os.path.join(HERE, 'E4'), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, 'E4', f'等待秒數掃描_{mode}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

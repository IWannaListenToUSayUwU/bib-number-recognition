r"""R13 E1：號碼名單＋5 碼規則（離線，不用 GPU）。用 v2.2 的 raw.jsonl 重算過線事件，只改「定案」那一步。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_e1.py [raw 來源設定名，預設 FROZEN_CONFIG_v2_2]
片段：調整集（tpe2t_*，官方成績評分）＋ C、D（人工答案 v1，score_v2）。**檢查集 tpe2_A/B/C 不跑**（計畫.md ②）。
輸出：30_實驗/R13_新機位讀號碼/E1/<raw 來源>/<模式>/<片段>/events.csv、E1/<raw 來源>/E1結果.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402

TUNE = ['tpe2t_2700', 'tpe2t_3600', 'tpe2t_4800', 'tpe2t_5700']
GUARD = ['tpe_C_600', 'tpe_D_1800']
MODES = ['v22', 'len5', 'post', 'post_noz', 'post_uq', 'pre', 'pre_noz', 'pre_keep', 'cons', 'cons_color']


SUBDIR = {'R13_E2_bottomext': os.path.join('E2', 'out'), 'R13_E3_static': os.path.join('E3', 'out'), 'R13_FULL_ocr': os.path.join('FULL', 'out'), 'R13_E5_det320': os.path.join('E5', 'out'), 'R13_E5b_det480': os.path.join('E5b', 'out'), 'R13_E5c_det320u2': os.path.join('E5c', 'out'), 'R13_E6_det320_es5': os.path.join('E6', 'out')}   # 每個實驗一個子資料夾


def raw_path(src, c):
    """回傳跑完的 raw.jsonl 路徑（要有 DONE.txt，避免讀到還在寫的檔）；沒有就回傳一個不存在的路徑。
    C、D 在 v2.2 時用 R12 正式流程的 raw（和 R06 逐位元相同）；其他設定要那個實驗自己跑過 C、D。"""
    d = os.path.join(HERE, SUBDIR.get(src, 'out'), src, c)
    if not c.startswith('tpe2t_') and src == 'FROZEN_CONFIG_v2_2':
        d = os.path.join(L.ROOT, '30_實驗', 'R12_第二機位', 'out', 'FROZEN_CONFIG_v2_2', c)
    return os.path.join(d, 'raw.jsonl') if os.path.exists(os.path.join(d, 'DONE.txt')) else os.path.join(d, '_not_done_')


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'FROZEN_CONFIG_v2_2'
    reg = L.registry(); res = {}
    for m in MODES:
        r = dict(tune={}, guard={})
        for c in TUNE + GUARD:
            p = raw_path(src, c)
            if not os.path.exists(p): continue
            ev = L.crossing_events(p, c, m, reg)
            L.write_events(ev, os.path.join(HERE, 'E1', src, m, c, 'events.csv'))
            if c in TUNE: x = L.official_eval(c, ev); x.pop('deltas'); r['tune'][c] = x
            else: r['guard'][c] = L.gt_eval(c, ev)
        T = r['tune']; G = r['guard']
        f = sum(x['found'] for x in T.values()); n = sum(x['official_in_clip'] for x in T.values())
        ok = sum(x['consistent'] for x in T.values()); bad = sum(x['time_mismatch'] + x['not_in_list'] for x in T.values())
        gf = sum(x['full'] for x in G.values()); gn = sum(x['n_gt'] for x in G.values()); gw = sum(x['wrong'] for x in G.values())
        r['summary'] = dict(tune_found=f, tune_n=n, tune_found_rate=round(f / n, 3) if n else None, tune_ci95=L.wilson(f, n) if n else None,
                            tune_consistent=ok, tune_wrong_out=bad, per_clip_found={c: x['found'] for c, x in T.items()},
                            guard_full=gf, guard_n=gn, guard_rate=round(gf / gn, 3) if gn else None, guard_wrong=gw)
        res[m] = r; s = r['summary']
        print(f"{m:8s} 調整集 找到 {f}/{n}＝{s['tune_found_rate']}  一致 {ok} 錯誤輸出 {bad}  各段 {list(s['per_clip_found'].values())}"
              f" ｜ C+D {gf}/{gn}＝{s['guard_rate']} 錯誤輸出 {gw}")
    os.makedirs(os.path.join(HERE, 'E1', src), exist_ok=True)
    json.dump(dict(raw_source=src, registry_n=len(reg), results=res, rules=L.__doc__), open(os.path.join(HERE, 'E1', src, 'E1結果.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

r"""R13 穩健度：號碼名單用的是「完賽者」（7,813 人），真實的報名名單更大（含沒出賽、沒完賽的號碼）。
在名單中隨機加入 15%／30% 不在完賽名單、但在號碼範圍內（00001–11783）的假號碼，重算 cons_color（定案方法），看調整集找到人數和錯誤輸出的變化。
只用調整集（不再看檢查集）。用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_registry_sensitivity.py"""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path, TUNE  # noqa: E402


def main():
    base = L.registry(); pool = [f'{i:05d}' for i in range(1, 11784) if f'{i:05d}' not in base]; out = {}
    for extra in (0.0, 0.15, 0.30):
        for seed in ((0,) if extra == 0 else (1, 2, 3)):
            random.seed(seed); reg = set(base) | set(random.sample(pool, min(len(pool), int(len(base) * extra))))
            L._subidx.clear()
            f = n = bad = 0
            for c in TUNE:
                ev = L.crossing_events(raw_path('FROZEN_CONFIG_v2_2', c), c, 'cons_color', reg)
                x = L.official_eval(c, ev); f += x['found']; n += x['official_in_clip']; bad += x['time_mismatch'] + x['not_in_list']
            out[f'{extra}_{seed}'] = dict(extra=extra, seed=seed, registry=len(reg), found=f, n=n, wrong=bad)
            print(f'名單 +{extra:.0%}（{len(reg)} 個，seed {seed}）：調整集找到 {f}/{n}、錯誤輸出 {bad}', flush=True)
    json.dump(out, open(os.path.join(HERE, '診斷', '號碼名單大小_穩健度.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

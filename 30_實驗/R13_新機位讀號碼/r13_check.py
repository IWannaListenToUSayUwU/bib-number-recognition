r"""R13 檢查集評估（只在方法定案後跑一次）：tpe2_A/B/C 用 R12 凍結的 v2.2 raw（sha 見 檢查集_v2.2凍結sha.json），
比較 v2.2 和定案的號碼名單模式（離線規則，不需要 GPU）。官方對照規則和 R12、調整集相同。
為了避免先看結果再選方法，必須先有 `方法定案.json`（寫明定案的模式、時間、依據），這支程式才會跑。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_check.py
輸出：30_實驗/R13_新機位讀號碼/檢查集結果.json、檢查集\<模式>\<片段>\events.csv"""
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
CHECK = ['tpe2_A_3000', 'tpe2_B_4200', 'tpe2_C_5400']


def main():
    dp = os.path.join(HERE, '方法定案.json')
    if not os.path.exists(dp): sys.exit('[停止] 還沒有 方法定案.json：方法定案前不准看檢查集')
    dec = json.load(open(dp, encoding='utf-8')); modes = ['v22'] + [m for m in dec['modes'] if m != 'v22']; wait = dec.get('decide_after', L.WAIT)
    frozen = json.load(open(os.path.join(HERE, '檢查集_v2.2凍結sha.json'), encoding='utf-8'))
    for f, h in frozen.items():
        p = os.path.join(L.ROOT, f)
        if f.endswith('raw.jsonl') and hashlib.sha256(open(p, 'rb').read()).hexdigest() != h: sys.exit(f'[停止] {f} 和凍結時不同')
    reg = L.registry(); res = {}
    for m in modes:
        f = n = ok = bad = 0; per = {}
        for c in CHECK:
            rp = os.path.join(L.ROOT, '30_實驗', 'R12_第二機位', 'out', 'FROZEN_CONFIG_v2_2', c, 'raw.jsonl')
            ev = L.crossing_events(rp, c, m, reg, wait=wait if m != 'v22' else L.WAIT)
            L.write_events(ev, os.path.join(HERE, '檢查集', m, c, 'events.csv'))
            x = L.official_eval(c, ev); x.pop('deltas'); per[c] = x
            f += x['found']; n += x['official_in_clip']; ok += x['consistent']; bad += x['time_mismatch'] + x['not_in_list']
        res[m] = dict(found=f, n=n, rate=round(f / n, 3), ci95=L.wilson(f, n), consistent=ok, wrong_out=bad, per_clip=per)
        print(f"{m:9s} 檢查集 官方名單找到 {f}/{n}＝{res[m]['rate']} {res[m]['ci95']}｜一致 {ok}｜錯誤輸出 {bad}｜各段 {[per[c]['found'] for c in CHECK]}")
    json.dump(dict(decision=dec, results=res), open(os.path.join(HERE, '檢查集結果.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

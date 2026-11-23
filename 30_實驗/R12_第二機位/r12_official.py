r"""R12：用官方成績（運動筆記即時成績，推定為槍聲時間）對照系統的過線結果。這不是正確答案，是獨立的旁證。
用法（在專案根目錄）：python 30_實驗/R12_第二機位/r12_official.py [結果資料夾，預設 30_實驗/R12_第二機位/out_crossing]
規則（計畫.md「官方成績對照」，看結果前寫死）：
  系統事件的槍聲時間 = 片段開頭的時鐘（時鐘對照.json）＋ t_cross
  官方一致：號碼在官方名單，且 |官方時間 − 系統槍聲時間| ≤ 2 秒
  時間不符：號碼在名單、但差 > 2 秒；不在名單：號碼不在這段時間的官方名單（多半是讀錯）
  官方名單找到率：官方時間落在片段第 1～59 秒的人，系統有輸出同號碼且官方一致的比例
輸出：<結果資料夾>/官方對照.json、官方對照_逐筆.csv"""
import csv, json, math, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, '20_測試基準'))
from score_v2 import wilson  # noqa: E402
TOL = 2.0


def sec(s):
    h, m, x = map(int, s.split(':')); return h * 3600 + m * 60 + x


def main():
    root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, 'out_crossing')
    off = json.load(open(os.path.join(HERE, '官方成績', '官方成績_片段時間窗.json'), encoding='utf-8'))['clips']
    res = {}; rows_out = []; T = dict(ok=0, out=0, cov=0, n_off=0, d=[])
    for c, o in off.items():
        p = os.path.join(root, c, 'events.csv')
        if not os.path.exists(p): continue
        t0 = o['clock_at_t0']; offl = {}
        for r in o['rows']: offl.setdefault(r['bib'], []).append(sec(r['time']))
        ev = list(csv.DictReader(open(p, encoding='utf-8')))
        cnt = dict(consistent=0, time_mismatch=0, not_in_list=0, unknown=0); found = set(); d = []
        for e in ev:
            b = e['bib']; g = t0 + float(e['t_cross'])
            if not b: k = 'unknown'; dd = None
            elif b in offl:
                dd = min((x - g for x in offl[b]), key=abs)
                k = 'consistent' if abs(dd) <= TOL else 'time_mismatch'
                if k == 'consistent': found.add(b); d.append(dd)
            else: k = 'not_in_list'; dd = None
            cnt[k] += 1
            rows_out.append(dict(clip=c, t_cross=e['t_cross'], gun_sys=round(g, 2), bib=b, guess=e.get('guess', ''), result=k,
                                 official_minus_sys=round(dd, 2) if dd is not None else ''))
        inside = [b for b, ts in offl.items() if any(t0 + 1 <= x <= t0 + 59 for x in ts)]
        cov = sum(1 for b in inside if b in found)
        out_bibs = cnt['consistent'] + cnt['time_mismatch'] + cnt['not_in_list']
        res[c] = dict(events=len(ev), official_in_clip=len(inside), **cnt,
                      consistent_share=dict(k=cnt['consistent'], n=out_bibs, value=round(cnt['consistent'] / out_bibs, 3) if out_bibs else None, ci95=wilson(cnt['consistent'], out_bibs)),
                      official_found=dict(k=cov, n=len(inside), value=round(cov / len(inside), 3) if inside else None, ci95=wilson(cov, len(inside))),
                      delta_official_minus_sys=dict(n=len(d), median=round(sorted(d)[len(d) // 2], 2) if d else None,
                                                    mean=round(sum(d) / len(d), 2) if d else None))
        T['ok'] += cnt['consistent']; T['out'] += out_bibs; T['cov'] += cov; T['n_off'] += len(inside); T['d'] += d
        print(f"{c}: 事件 {len(ev)}（官方這 60 秒 {len(inside)} 人）；輸出號碼 {out_bibs}：官方一致 {cnt['consistent']}、時間不符 {cnt['time_mismatch']}、"
              f"不在名單 {cnt['not_in_list']}；未知 {cnt['unknown']}；官方名單找到 {cov}/{len(inside)}；官方−系統 中位數 {res[c]['delta_official_minus_sys']['median']} 秒")
    if T['out']:
        d = sorted(T['d'])
        res['total'] = dict(consistent_share=dict(k=T['ok'], n=T['out'], value=round(T['ok'] / T['out'], 3), ci95=wilson(T['ok'], T['out'])),
                            official_found=dict(k=T['cov'], n=T['n_off'], value=round(T['cov'] / T['n_off'], 3), ci95=wilson(T['cov'], T['n_off'])),
                            delta_median=d[len(d) // 2] if d else None, delta_mean=round(sum(d) / len(d), 2) if d else None,
                            delta_within_1s=round(sum(abs(x) <= 1 for x in d) / len(d), 3) if d else None)
        print('合計', json.dumps(res['total'], ensure_ascii=False))
    res['rules'] = __doc__
    json.dump(res, open(os.path.join(root, '官方對照.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if rows_out:
        with open(os.path.join(root, '官方對照_逐筆.csv'), 'w', newline='', encoding='utf-8-sig') as fo:
            w = csv.DictWriter(fo, list(rows_out[0])); w.writeheader(); w.writerows(rows_out)


if __name__ == '__main__':
    main()

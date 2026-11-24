r"""R17 評分：用官方成績（10K＋21K 的號碼＋槍聲時間）評 r17_run.py 的過線事件。畫面沒有時鐘 →
「片段秒數 → 槍聲時間」的差（每個組別一個常數）用讀到的號碼估計；估好後存 offsets.json 凍結，之後所有評分共用。
用法：python 30_實驗/R17_最終魔王/r17_eval.py <標籤> [--fit-offset]
指標（和 R13 官方名單評分同精神）：
  應過線人數：官方完賽者中，槍聲時間換算後落在已處理時段內的人（3K 不在名單，不算）
  找到率＝號碼對、時間差 ≤ 2 秒（一對一）÷ 應過線人數
  輸出號碼正確率＝輸出的號碼（不含重複）在官方名單、且時間差 ≤ 2 秒 ÷ 輸出號碼數；錯誤輸出＝其餘（讀錯或時間對不上）
  過線事件數 ÷ 應過線人數（偵測量的參考，不是一對一）"""
import csv, json, os, sys, glob, math
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
OFF = os.path.join(HERE, 'offsets.json'); TOL = 2.0


def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def official():
    o = {}
    for race in ('10K', '21K'):
        for r in json.load(open(os.path.join(HERE, '官方成績', f'官方_{race}.json'), encoding='utf-8'))['rows']:
            o[r['bib']] = (race, r['t'])
    return o


def load(tag):
    info = json.load(open(os.path.join(HERE, 'out', tag, 'run_info.json'), encoding='utf-8'))
    ev, segs = [], []
    for d in sorted(glob.glob(os.path.join(HERE, 'out', tag, 'seg_*'))):
        if not os.path.exists(os.path.join(d, 'DONE.txt')): continue
        segs.append(tuple(json.load(open(os.path.join(d, 'stats.json')))['seg']))
        for r in csv.DictReader(open(os.path.join(d, 'events.csv'), encoding='utf-8')):
            r['t_cross'] = float(r['t_cross']); r['dup'] = r['dup'] == 'True'; ev.append(r)
    return info, ev, segs


def fit_offsets(ev, O):
    res = {}
    for race in ('10K', '21K'):
        d = [O[e['bib']][1] - e['t_cross'] for e in ev if e['bib'] and not e['dup'] and O.get(e['bib'], ('',))[0] == race]
        if len(d) < 3: continue
        best = max(d, key=lambda x: sum(1 for y in d if abs(y - x) <= 1.5))
        near = sorted(y for y in d if abs(y - best) <= 2.0)
        res[race] = dict(offset=round(near[len(near) // 2], 2), support=len(near), n_candidates=len(d))
    return res


def evaluate(tag, fit=False):
    O = official(); info, ev, segs = load(tag)
    if fit or not os.path.exists(OFF):
        offs = fit_offsets(ev, O); json.dump(dict(offsets=offs, fitted_from=tag), open(OFF, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('估計時間差（存 offsets.json）：', offs)
    offs = json.load(open(OFF, encoding='utf-8'))['offsets']
    inseg = lambda t: any(a <= t < b for a, b in segs)
    expected = {b: t - offs[r]['offset'] for b, (r, t) in O.items() if r in offs and inseg(t - offs[r]['offset'])}
    out_bibs = [e for e in ev if e['bib'] and not e['dup']]
    # 一對一：每個輸出號碼對到應過線的同號碼、時間差 ≤ TOL
    used = set(); good = []; terr = []
    for e in sorted(out_bibs, key=lambda e: e['t_cross']):
        b = e['bib']
        if b in expected and b not in used and abs(e['t_cross'] - expected[b]) <= TOL:
            used.add(b); good.append(e); terr.append(e['t_cross'] - expected[b])
    in_list = sum(1 for e in out_bibs if e['bib'] in O)
    n_exp = len(expected); k = len(good); no = len(out_bibs)
    terr.sort()
    r = dict(tag=tag, segments=segs, offsets=offs, n_expected=n_exp, n_events=len(ev), n_out_bib=no,
             found=dict(k=k, n=n_exp, value=round(k / n_exp, 3) if n_exp else None, ci95=wilson(k, n_exp)),
             out_correct=dict(k=k, n=no, value=round(k / no, 3) if no else None, ci95=wilson(k, no)),
             out_in_list=dict(k=in_list, n=no), wrong_out=no - k,
             events_per_expected=round(len(ev) / n_exp, 2) if n_exp else None,
             time_err=dict(median=round(terr[len(terr) // 2], 2) if terr else None, abs_med=round(sorted(abs(x) for x in terr)[len(terr) // 2], 2) if terr else None))
    per = []
    for a, b in segs:
        ne = sum(1 for t in expected.values() if a <= t < b); kk = sum(1 for e in good if a <= e['t_cross'] < b)
        evs = [e for e in ev if a <= e['t_cross'] < b]; ob = sum(1 for e in out_bibs if a <= e['t_cross'] < b)
        per.append(dict(seg=[a, b], expected=ne, events=len(evs), out_bib=ob, found=kk))
    r['per_segment'] = per
    json.dump(r, open(os.path.join(HERE, 'out', tag, 'eval.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"[{tag}] 應過線 {n_exp} 人｜過線事件 {len(ev)}｜輸出號碼 {no}（在名單 {in_list}）｜找到 {k} → 找到率 {r['found']['value']} {r['found']['ci95']}｜"
          f"輸出正確率 {r['out_correct']['value']}｜錯誤輸出 {no - k}｜時間差中位數 {r['time_err']['median']}")
    for p in per: print('   ', p)
    return r


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    for t in a: evaluate(t, fit='--fit-offset' in sys.argv)

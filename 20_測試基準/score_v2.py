r"""20_測試基準 過線評分程式 score_v2（規則見 30_實驗\R11_過線正確答案\計畫.md「評分規則」，寫於標註之前）。
用法：python score_v2.py <結果資料夾> [片段 ...] [--gt <正確答案資料夾>] [--gtver <版本>]
  <結果資料夾>\<片段>\events.csv：過線事件（10_程式\src\crossing.py 的輸出欄位：t_cross, bib, u, latency …）
  正確答案預設在 20_測試基準\gt_crossing\<片段>.json（--gt 只給測試用）。
  --gtver v1_1：改用 <片段>.v1_1.json（修正版正確答案），結果另存 score_v2.v1_1.json，不覆蓋 v1 的 score_v2.json（2026-11-23 加，評分規則不變）。
規則摘要：
  配對：系統事件與正確答案一對一，|Δt| ≤ 1.0 秒且 |Δu| ≤ 0.3，依 |Δt|+|Δu| 由小到大貪婪配對。
  主要指標 = 配對成功、號碼相同（正確答案為 sure）、|Δt| ≤ 0.5 秒、不是重複輸出 的數量 ÷ 全部過線跑者數。
  重複：同一個號碼第二次以後的輸出都算錯。與 partial 相容、或配到 unreadable/nobib 跑者的號碼：不算對也不算錯。
  比例都附 95% Wilson 區間。
輸出：螢幕 + <結果資料夾>\score_v2.json"""
import csv, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MATCH_DT, MATCH_DU, OK_DT = 1.0, 0.3, 0.5


def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def ratio(k, n): return dict(k=k, n=n, value=round(k / n, 3) if n else None, ci95=wilson(k, n))


def compat(pat, b):
    return pat not in ('', '?') and len(pat) == len(b) and all(p == '?' or p == c for p, c in zip(pat, b))


def pct(xs, q):
    if not xs: return None
    xs = sorted(xs); return round(xs[min(len(xs) - 1, int(math.ceil(q * len(xs))) - 1)], 3)


def match(sys_ev, gt):
    pairs = []
    for i, s in enumerate(sys_ev):
        for j, g in enumerate(gt):
            dt = abs(s['t'] - g['t']); du = abs(s['u'] - g['u'])
            if dt <= MATCH_DT and du <= MATCH_DU: pairs.append((dt + du, i, j))
    pairs.sort(); ms, mg = {}, {}
    for _, i, j in pairs:
        if i not in ms and j not in mg: ms[i] = j; mg[j] = i
    return ms, mg


def score_clip(sys_ev, gt):
    sys_ev = sorted(sys_ev, key=lambda s: s['t']); ms, mg = match(sys_ev, gt)
    seen = set(); res = []
    for i, s in enumerate(sys_ev):
        b = s['bib']; j = ms.get(i); g = gt[j] if j is not None else None
        if not b: r = 'unknown'
        elif b in seen: r = 'dup'
        elif g is None: r = 'wrong_nocross'
        elif g['status'] == 'sure': r = 'correct' if b == g['bib'] else 'wrong_bib'
        elif g['status'] == 'partial': r = 'ignore' if compat(g['bib'], b) else 'wrong_bib'
        else: r = 'ignore'
        if b: seen.add(b)
        res.append(dict(r=r, j=j, dt=(s['t'] - g['t']) if g else None))
    n_all = len(gt); n_sure = sum(g['status'] == 'sure' for g in gt)
    corr = [x for x in res if x['r'] == 'correct']
    full = [x for x in corr if abs(x['dt']) <= OK_DT]
    wrong = [x for x in res if x['r'] in ('dup', 'wrong_nocross', 'wrong_bib')]
    absdt = [abs(x['dt']) for x in corr]
    unk = [x for x in res if x['r'] == 'unknown']
    lat = [s['latency'] for s in sys_ev if s['latency'] is not None]
    return dict(
        n_gt=n_all, n_gt_sure=n_sure, n_sys=len(sys_ev),
        main_bib_and_time=ratio(len(full), n_all), ceiling_sure_share=ratio(n_sure, n_all),
        detection=ratio(len(mg), n_all), false_crossings=len(sys_ev) - len(ms),
        sure_bib_correct=ratio(len(corr), n_sure),
        bib_output_error=ratio(len(wrong), len(corr) + len(wrong)),
        wrong_breakdown=dict(wrong_bib=sum(x['r'] == 'wrong_bib' for x in res), dup=sum(x['r'] == 'dup' for x in res),
                             no_crossing=sum(x['r'] == 'wrong_nocross' for x in res), ignored=sum(x['r'] == 'ignore' for x in res)),
        time_error=dict(n=len(corr), median_abs=pct(absdt, 0.5), p95_abs=pct(absdt, 0.95),
                        mean_signed=round(sum(x['dt'] for x in corr) / len(corr), 3) if corr else None,
                        within_0_2=ratio(sum(a <= 0.2 for a in absdt), len(corr)), within_0_5=ratio(sum(a <= 0.5 for a in absdt), len(corr))),
        unknown=dict(n=len(unk), matched_unreadable_or_nobib=sum(1 for x in unk if x['j'] is not None and gt[x['j']]['status'] in ('unreadable', 'nobib'))),
        latency=dict(median=pct(lat, 0.5), max=max(lat) if lat else None),
        _raw=dict(full=len(full), corr=len(corr), wrong=len(wrong), matched_gt=len(mg), absdt=absdt, signed=[x['dt'] for x in corr], lat=lat, unk=len(unk)))


def load_sys(p):
    out = []
    for r in csv.DictReader(open(p, encoding='utf-8-sig')):
        out.append(dict(t=float(r['t_cross']), bib=(r.get('bib') or '').strip(), u=float(r['u']),
                        latency=float(r['latency']) if r.get('latency') not in (None, '') else None))
    return out


def main():
    args = sys.argv[1:]; gtdir = os.path.join(HERE, 'gt_crossing')
    if '--gt' in args: k = args.index('--gt'); gtdir = args[k + 1]; del args[k:k + 2]
    gtver = None
    if '--gtver' in args: k = args.index('--gtver'); gtver = args[k + 1]; del args[k:k + 2]
    root = os.path.abspath(args[0])
    clips = args[1:] or sorted(d for d in os.listdir(root) if os.path.exists(os.path.join(root, d, 'events.csv')))
    per = {}; T = dict(full=0, corr=0, wrong=0, matched_gt=0, n_gt=0, n_sure=0, n_sys=0, false=0, unk=0, absdt=[], signed=[], lat=[])
    for c in clips:
        gp = os.path.join(gtdir, c + (f'.{gtver}' if gtver else '') + '.json')
        if not os.path.exists(gp): print(f'[略過] {c}：沒有過線正確答案 {gp}'); continue
        g = json.load(open(gp, encoding='utf-8'))
        s = score_clip(load_sys(os.path.join(root, c, 'events.csv')), g['events']); raw = s.pop('_raw'); per[c] = s
        for k in ('full', 'corr', 'wrong', 'matched_gt', 'unk'): T[k] += raw[k]
        T['n_gt'] += s['n_gt']; T['n_sure'] += s['n_gt_sure']; T['n_sys'] += s['n_sys']; T['false'] += s['false_crossings']
        T['absdt'] += raw['absdt']; T['signed'] += raw['signed']; T['lat'] += raw['lat']
        print(f"{c:12s} 號碼與時間都對 {s['main_bib_and_time']['value']}（{s['main_bib_and_time']['k']}/{s['n_gt']}）"
              f" 偵測率 {s['detection']['value']} 誤報過線 {s['false_crossings']} sure號碼正確 {s['sure_bib_correct']['value']}"
              f" 輸出號碼錯誤率 {s['bib_output_error']['value']} 時間誤差中位 {s['time_error']['median_abs']}s 偏差 {s['time_error']['mean_signed']}s")
    if not per: return
    tot = dict(clips=list(per), n_gt=T['n_gt'], n_gt_sure=T['n_sure'], n_sys=T['n_sys'],
               main_bib_and_time=ratio(T['full'], T['n_gt']), ceiling_sure_share=ratio(T['n_sure'], T['n_gt']),
               detection=ratio(T['matched_gt'], T['n_gt']), false_crossings=T['false'],
               sure_bib_correct=ratio(T['corr'], T['n_sure']), bib_output_error=ratio(T['wrong'], T['corr'] + T['wrong']),
               time_error=dict(n=T['corr'], median_abs=pct(T['absdt'], 0.5), p95_abs=pct(T['absdt'], 0.95),
                               mean_signed=round(sum(T['signed']) / len(T['signed']), 3) if T['signed'] else None,
                               within_0_2=ratio(sum(a <= 0.2 for a in T['absdt']), T['corr']), within_0_5=ratio(sum(a <= 0.5 for a in T['absdt']), T['corr'])),
               unknown_events=T['unk'], latency=dict(median=pct(T['lat'], 0.5), max=max(T['lat']) if T['lat'] else None))
    m = tot['main_bib_and_time']
    print(f"{'合計':10s} 號碼與時間都對 {m['value']} {m['ci95']}（{m['k']}/{tot['n_gt']}，理論上限 {tot['ceiling_sure_share']['value']}）"
          f" 偵測率 {tot['detection']['value']} sure號碼正確 {tot['sure_bib_correct']['value']} 輸出號碼錯誤率 {tot['bib_output_error']['value']}")
    try: gtname = os.path.relpath(gtdir, HERE)
    except ValueError: gtname = os.path.abspath(gtdir)   # 不同磁碟（只有測試時會發生）
    json.dump(dict(total=tot, per_clip=per, scorer='20_測試基準/score_v2.py', gt_dir=gtname, gt_version=gtver or 'v1',
                   rules=dict(match_dt=MATCH_DT, match_du=MATCH_DU, ok_dt=OK_DT)),
              open(os.path.join(root, f'score_v2.{gtver}.json' if gtver else 'score_v2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

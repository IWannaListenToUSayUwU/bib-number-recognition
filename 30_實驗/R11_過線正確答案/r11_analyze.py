r"""R11 分析：用正式 score_v2 的配對規則，列出 16 格／8 格每一筆錯誤，並比較人工過線答案和舊 AI 答案。
用法（在專案根目錄）：python 30_實驗/R11_過線正確答案/r11_analyze.py
輸出：30_實驗/R11_過線正確答案/分析/
  逐筆_<src>.csv        每一位過線跑者（正確答案）＋配到的系統事件＋判定；沒配到人的系統事件也列出
  新舊答案比較.csv      人工答案 vs 舊 AI 答案（20_測試基準/gt/）的號碼差異
  分析摘要.json
只讀檔案，不改正確答案、不改評分程式。"""
import csv, json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, '分析')
sys.path.insert(0, os.path.join(ROOT, '20_測試基準'))
import score_v2 as S  # noqa: E402
CLIPS = ['tpe_C_600', 'tpe_D_1800']


def load_gt(clip):
    return json.load(open(os.path.join(ROOT, '20_測試基準', 'gt_crossing', clip + '.json'), encoding='utf-8'))['events']


def per_event(src):
    rows = []
    for clip in CLIPS:
        gt = load_gt(clip)
        sys_ev = sorted(S.load_sys(os.path.join(HERE, 'out', src, clip, 'events.csv')), key=lambda s: s['t'])
        ms, mg = S.match(sys_ev, gt)
        seen = set(); res = {}
        for i, s in enumerate(sys_ev):  # 與 score_v2.score_clip 相同的判定順序
            b = s['bib']; j = ms.get(i); g = gt[j] if j is not None else None
            if not b: r = 'unknown'
            elif b in seen: r = 'dup'
            elif g is None: r = 'wrong_nocross'
            elif g['status'] == 'sure': r = 'correct' if b == g['bib'] else 'wrong_bib'
            elif g['status'] == 'partial': r = 'ignore' if S.compat(g['bib'], b) else 'wrong_bib'
            else: r = 'ignore'
            if b: seen.add(b)
            res[i] = r
        for j, g in enumerate(gt):
            i = mg.get(j); s = sys_ev[i] if i is not None else None
            r = res[i] if i is not None else 'missed'
            ok = r == 'correct' and abs(s['t'] - g['t']) <= S.OK_DT
            rows.append(dict(clip=clip, t_gt=g['t'], u_gt=g['u'], gt_bib=g['bib'], status=g['status'],
                             t_sys=round(s['t'], 3) if s else '', sys_bib=s['bib'] if s else '',
                             dt=round(s['t'] - g['t'], 3) if s else '', result=r, main_ok=ok))
        for i, s in enumerate(sys_ev):
            if i not in ms:
                rows.append(dict(clip=clip, t_gt='', u_gt='', gt_bib='', status='（沒有人過線）', t_sys=round(s['t'], 3),
                                 sys_bib=s['bib'], dt='', result=res[i], main_ok=False))
    return rows


def old_vs_new():
    rows = []
    for clip in CLIPS:
        old = json.load(open(os.path.join(ROOT, '20_測試基準', 'gt', clip + '.json'), encoding='utf-8'))
        old_sure = {x['bib'] for x in old['sure']}
        old_partial = {x['pat'] for x in old.get('partial', [])}
        gt = load_gt(clip)
        new_sure = {g['bib'] for g in gt if g['status'] == 'sure'}
        new_part = [g['bib'] for g in gt if g['status'] == 'partial']
        for b in sorted(old_sure | new_sure):
            if b in old_sure and b in new_sure: continue
            if b in new_sure:
                why = '人工 sure、舊答案沒有' + ('（舊答案列為 partial）' if any(S.compat(p, b) for p in old_partial) else '')
            else:
                comp = [p for p in new_part if S.compat(p, b)]
                why = ('舊答案 sure、人工只寫 partial：' + '/'.join(comp)) if comp else '舊答案 sure、人工答案沒有（沒過線，或號碼不同）'
            rows.append(dict(clip=clip, bib=b, diff=why))
    return rows


def write_csv(p, rows):
    with open(p, 'w', encoding='utf-8-sig', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def main():
    os.makedirs(OUT, exist_ok=True); summ = {}
    for src in ['16fps', '8fps']:
        rows = per_event(src); write_csv(os.path.join(OUT, f'逐筆_{src}.csv'), rows)
        cnt = {}
        for r in rows: cnt[r['result']] = cnt.get(r['result'], 0) + 1
        errs = [r for r in rows if r['result'] in ('wrong_bib', 'dup', 'wrong_nocross')]
        summ[src] = dict(result_counts=cnt, errors=errs if src == '16fps' else len(errs))
    ov = old_vs_new(); write_csv(os.path.join(OUT, '新舊答案比較.csv'), ov)
    summ['old_vs_new'] = ov
    json.dump(summ, open(os.path.join(OUT, '分析摘要.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

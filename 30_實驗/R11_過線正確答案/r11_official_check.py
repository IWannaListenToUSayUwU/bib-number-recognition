r"""用 2022 臺北馬全馬官方完賽名單（R13 抓的，號碼＋時間）檢查 R11 人工答案 v1（C、D 段，轉角機位）。只產生核對清單，不改答案。
轉角機位畫面上沒有比賽時鐘，所以先用「人工 sure 號碼」估計每段的時間差：官方時間 − 片段過線時間 ≈ 固定值＋轉角到終點的跑步時間。
檢查項目：
  1. sure 號碼不在完賽名單（可能看錯，或沒晶片／沒完賽）
  2. sure 號碼的時間差離中位數太遠（> 容忍值，可能看成別人的號碼）
  3. partial（有 ?）：名單中符合樣式、時間也對得上的號碼有幾個（只給使用者參考，不自動填）
  4. 舊 AI 答案有、人工答案沒有的 sure 號碼：名單中時間對不對得上（對得上 → 可能真的有這個人經過、人工漏標）
用法（在專案根目錄）：python 30_實驗/R11_過線正確答案/r11_official_check.py
輸出：30_實驗/R11_過線正確答案/分析/官方名單核對.json、官方名單核對.csv"""
import csv, json, os, re, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OFF = os.path.join(ROOT, '30_實驗', 'R13_新機位讀號碼', '官方成績', '官方完賽名單_全馬.json')
CLIPS = ['tpe_C_600', 'tpe_D_1800']


def sec(s):
    h, m, x = map(int, s.split(':')); return h * 3600 + m * 60 + x


def main():
    off = {r['bib']: sec(r['time']) for r in json.load(open(OFF, encoding='utf-8'))['rows']}
    cmp_rows = list(csv.DictReader(open(os.path.join(HERE, '分析', '新舊答案比較.csv'), encoding='utf-8-sig')))
    out = {}; rows = []
    for c in CLIPS:
        g = json.load(open(os.path.join(ROOT, '20_測試基準', 'gt_crossing', c + '.json'), encoding='utf-8'))
        old = json.load(open(os.path.join(ROOT, '20_測試基準', 'gt', c + '.json'), encoding='utf-8'))
        sure = [e for e in g['events'] if e['status'] == 'sure']
        d = [off[e['bib']] - e['t'] for e in sure if e['bib'] in off]
        m = statistics.median(d); dev = sorted(abs(x - m) for x in d)
        tol = max(20.0, 3 * dev[len(dev) // 2] * 1.4826)          # 3 個 MAD（至少 20 秒）
        res = dict(n_sure=len(sure), sure_in_list=len(d), offset_median=round(m, 1), mad=round(dev[len(dev) // 2], 1), tol=round(tol, 1))
        for e in sure:
            if e['bib'] not in off:
                rows.append(dict(clip=c, t=e['t'], bib=e['bib'], status='sure', check='不在完賽名單', detail=''))
            elif abs(off[e['bib']] - e['t'] - m) > tol:
                rows.append(dict(clip=c, t=e['t'], bib=e['bib'], status='sure', check='時間對不上', detail=f"官方−片段 {off[e['bib']] - e['t'] - m:+.0f} 秒（相對中位數）"))
        for e in g['events']:
            if e['status'] != 'partial': continue
            pat = re.compile('^' + e['bib'].replace('?', r'\d') + '$')
            cand = sorted((b for b in off if pat.match(b) and abs(off[b] - e['t'] - m) <= tol), key=lambda b: abs(off[b] - e['t'] - m))
            rows.append(dict(clip=c, t=e['t'], bib=e['bib'], status='partial', check=f'名單中符合且時間對得上：{len(cand)} 個',
                             detail=' '.join(f"{b}({off[b] - e['t'] - m:+.0f}s)" for b in cand[:5])))
        miss = [r['bib'] for r in cmp_rows if r['clip'] == c and r['diff'].startswith('舊答案 sure、人工答案沒有')]
        for b in miss:
            o = [s for s in old['sure'] if s['bib'] == b]
            t1 = o[0]['t1'] if o else None
            if b not in off: chk, det = '舊 AI sure、人工沒有：不在完賽名單', ''
            elif t1 is None: chk, det = '舊 AI sure、人工沒有：在名單', ''
            else:
                x = off[b] - t1 - m
                chk = '舊 AI sure、人工沒有：時間對得上（可能人工漏標）' if abs(x) <= tol + 5 else '舊 AI sure、人工沒有：時間對不上'
                det = f'舊答案最後出現 {t1:.1f}s；官方−片段 {x:+.0f} 秒（相對中位數）'
            rows.append(dict(clip=c, t=t1, bib=b, status='old_ai_sure', check=chk, detail=det))
        out[c] = res
        print(c, res)
    for r in rows: print(f"  {r['clip']} {r['t']} {r['bib']:6s} {r['check']} {r['detail']}")
    json.dump(dict(summary=out, rows=rows, source=OFF, note='只供人工核對；不自動修改答案。'),
              open(os.path.join(HERE, '分析', '官方名單核對.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, '分析', '官方名單核對.csv'), 'w', newline='', encoding='utf-8-sig') as fo:
        w = csv.DictWriter(fo, list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == '__main__':
    main()

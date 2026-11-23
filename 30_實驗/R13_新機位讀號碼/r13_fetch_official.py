r"""R13：抓 2022 臺北馬拉松全馬「全部完賽者」的號碼＋時間（運動筆記即時成績，推定為槍聲時間；R12 已用時鐘驗證）。
只存號碼、時間、頁碼，不存姓名、組別。每頁間隔 0.6 秒（robots.txt 允許）。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_fetch_official.py
輸出：30_實驗/R13_新機位讀號碼/官方成績/官方完賽名單_全馬.json
號碼：網站是 6 碼（例 007701），號碼布印 5 碼 → 開頭的 0 去掉一個（07701）；6 碼且不以 0 開頭的（例 999998）原樣保留並標記。"""
import json, os, re, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://bravelog.tw/contest/rank/2022121801?page={}'
PAT = re.compile(r'<span class="border-right pr-1">(\d{6})</span>\s*<span class="border-right px-1">(\w+)</span>[\s\S]*?<div class="time">\s*<span>\s*([\d:]+)\s*</span>')


def get(p):
    req = urllib.request.Request(URL.format(p), headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    for k in range(4):
        try:
            return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
        except Exception as e:
            time.sleep(3 * (k + 1)); err = e
    raise err


def main():
    rows = []; p = 1
    while True:
        r = PAT.findall(get(p))
        if not r: break
        for bib6, cat, t in r:
            rows.append(dict(bib=bib6[1:] if bib6.startswith('0') else bib6, bib6=bib6, cat=cat, time=t, page=p))
        p += 1; time.sleep(0.6)
        if p % 50 == 0: print('page', p, len(rows), flush=True)
    bibs = [r['bib'] for r in rows]
    out = dict(source='https://bravelog.tw/contest/rank/2022121801（運動筆記即時成績；網站註明正式成績以主辦單位公告為準）',
               race='2022 臺北馬拉松 全馬（2022-12-18 06:30 起跑）', fetched=time.strftime('%Y-%m-%d %H:%M'),
               pages=p - 1, n=len(rows), n_unique_bib=len(set(bibs)), cats=sorted({r['cat'] for r in rows}),
               odd_bibs=sorted({b for b in bibs if len(b) != 5}),
               time_basis='推定為槍聲時間（R12：07701 畫面時鐘 4:02:20 ＝官方 04:02:20；24 筆一致事件時間差全在 1 秒內）',
               note='只存號碼與時間（不存姓名、組別以外的個資）。', rows=[{k: r[k] for k in ('bib', 'time', 'page')} for r in rows])
    json.dump(out, open(os.path.join(HERE, '官方成績', '官方完賽名單_全馬.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('done', out['pages'], out['n'], out['n_unique_bib'], out['odd_bibs'][:10])


if __name__ == '__main__':
    main()

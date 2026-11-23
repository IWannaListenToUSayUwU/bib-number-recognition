r"""R12 診斷（只分析、不改任何參數）：新機位為什麼讀到號碼的比例低？
用法（在專案根目錄）：python 30_實驗/R12_第二機位/r12_diag.py
對每段片段統計 raw.jsonl（正式流程 v2.2、16 格）：
  1. OCR 讀到的文字中，純數字 3～6 碼的數量、5 碼的數量、文字框高度中位數
  2. 官方名單（tpe2）：官方時間在片段第 1～59 秒的號碼，raw 裡有沒有出現過
     （完整 5 碼／只少開頭的 0／只有其中 4 碼連續／完全沒讀到），以及系統最後有沒有定案
輸出：診斷\讀號碼診斷.json"""
import json, os, re, sys, csv
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'out', 'FROZEN_CONFIG_v2_2', '{}', 'raw.jsonl')
CLIPS = ['tpe2_A_3000', 'tpe2_B_4200', 'tpe2_C_5400', 'tpe_C_600', 'tpe_D_1800']
DIG = re.compile(r'^\d{3,6}$')


def sec(s):
    h, m, x = map(int, s.split(':')); return h * 3600 + m * 60 + x


def main():
    off = json.load(open(os.path.join(HERE, '官方成績', '官方成績_片段時間窗.json'), encoding='utf-8'))['clips']
    out = {}
    for c in CLIPS:
        recs = [json.loads(l) for l in open(RAW.format(c), encoding='utf-8')]
        texts = [t for r in recs for t in (r['texts'] or [])]
        dig = [t for t in texts if DIG.match(t[0])]
        five = [t for t in dig if len(t[0]) == 5]
        hs = sorted(t[2][3] - t[2][1] for t in dig) or [0]
        phs = sorted(r['ph'] for r in recs)
        tracks = len({r['tid'] for r in recs})
        reads = Counter(t[0] for t in dig)
        cut = sum(1 for r in recs if r['pbox'][3] >= 1075)  # 人框貼到畫面底部（下半身被切掉）
        d = dict(records=len(recs), tracks=tracks, ocr_texts=len(texts), digit_3to6=len(dig), digit_5=len(five),
                 digit_text_h_median=hs[len(hs) // 2], person_h_median=phs[len(phs) // 2],
                 pbox_touch_bottom_share=round(cut / len(recs), 3),
                 records_with_any_digit=round(sum(1 for r in recs if any(DIG.match(t[0]) for t in (r['texts'] or []))) / len(recs), 3))
        if c in off:
            o = off[c]; t0 = o['clock_at_t0']
            inside = sorted({r['bib'] for r in o['rows'] if t0 + 1 <= sec(r['time']) <= t0 + 59})
            ev = {e['bib'] for e in csv.DictReader(open(os.path.join(HERE, 'out_crossing', c, 'events.csv'), encoding='utf-8')) if e['bib']}
            k = Counter()
            per = {}
            for b in inside:
                if b in reads: s = 'exact'
                elif b.startswith('0') and b[1:] in reads: s = 'lost_leading_0'
                elif any(b[i:i + 4] in reads for i in range(2)): s = 'partial_4'
                else: s = 'never'
                k[s] += 1; per[b] = dict(raw=s, raw_reads=reads.get(b, 0), decided=b in ev)
            d['official'] = dict(n=len(inside), raw_status=dict(k), decided=sum(1 for b in inside if b in ev),
                                 exact_in_raw_but_not_decided=sum(1 for b in inside if per[b]['raw'] == 'exact' and not per[b]['decided']))
            d['official_per_bib'] = per
        out[c] = d
        print(c, json.dumps({x: y for x, y in d.items() if x != 'official_per_bib'}, ensure_ascii=False))
    os.makedirs(os.path.join(HERE, '診斷'), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, '診斷', '讀號碼診斷.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

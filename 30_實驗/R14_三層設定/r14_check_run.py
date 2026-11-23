r"""R14 GPU 驗證跑完後的檢查（不需要 GPU）。
  (1) GLOBAL_v2_2 的 tpe_C_600：raw.jsonl 和 R12 v2.2 逐位元相同？events.csv 和 R12 out_crossing 相同？
  (2) GLOBAL_v3_0：raw 的 OCR（texts）和「完整 OCR 重播 static2＋zone500」逐筆相同？score_v2（C、D）和官方對照（tpe2t_2700）＝R13 模擬（C 32、D 59、tpe2t_2700 11）？
      抽取時間和 v2.2（C 692、D 740 秒，R12 乾淨計時）比。
用法（在專案根目錄）：python 30_實驗/R14_三層設定/r14_check_run.py"""
import csv, hashlib, json, os, sys, re
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src')); sys.path.insert(0, os.path.join(ROOT, '30_實驗', 'R13_新機位讀號碼'))
import settings  # noqa: E402
from ocrgate import OcrGate  # noqa: E402
import r13_lib as L  # noqa: E402
OUT = os.path.join(HERE, 'out'); R12 = os.path.join(ROOT, '30_實驗', 'R12_第二機位'); R13 = os.path.join(ROOT, '30_實驗', 'R13_新機位讀號碼')
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
D = re.compile(r'\d+')


def replay(c):
    S = settings.for_clip('GLOBAL_v3_0', c); kw = settings.extract_kwargs(S)
    gate = OcrGate(kw['static_s'], kw['static_p'], kw.get('zone_line'), kw.get('zone_up'), kw.get('zone_down')); good = defaultdict(Counter); out = []
    for l in open(os.path.join(R13, 'FULL', 'out', 'R13_FULL_ocr', c, 'raw.jsonl'), encoding='utf-8'):
        r = json.loads(l); v = r['tid']
        allow = gate.allow(r['t'], r.get('rawtid', v), r['pbox']) and not (v >= 0 and good[v] and good[v].most_common(1)[0][1] >= 3)
        t = r['texts'] if allow else None
        for txt, sc, bb in (t or []):
            d_ = D.findall(txt.replace(' ', ''))
            if d_ and float(sc) > 0.9 and v >= 0: good[v][max(d_, key=len)] += 1
        out.append(t)
    return out


def main():
    res = {}
    p = os.path.join(OUT, 'GLOBAL_v2_2', 'tpe_C_600')
    if os.path.exists(os.path.join(p, 'DONE.txt')):
        a = sha(os.path.join(p, 'raw.jsonl')) == sha(os.path.join(R12, 'out', 'FROZEN_CONFIG_v2_2', 'tpe_C_600', 'raw.jsonl'))
        e1 = [(r['t_cross'], r['bib']) for r in csv.DictReader(open(os.path.join(p, 'events.csv'), encoding='utf-8'))]
        e0 = [(r['t_cross'], r['bib']) for r in csv.DictReader(open(os.path.join(R12, 'out_crossing', 'tpe_C_600', 'events.csv'), encoding='utf-8'))]
        res['v22_C'] = dict(raw_identical=a, events_identical=e1 == e0, extract_sec=json.load(open(os.path.join(p, 'stats.json')))['extract_sec'])
        print('(1) GLOBAL_v2_2 tpe_C_600：raw 和 v2.2 逐位元相同', a, '｜events 相同', e1 == e0)
    base = {'tpe_C_600': 692, 'tpe_D_1800': 740}
    for c in ('tpe_C_600', 'tpe_D_1800', 'tpe2t_2700'):
        p = os.path.join(OUT, 'GLOBAL_v3_0', c)
        if not os.path.exists(os.path.join(p, 'DONE.txt')): print(f'[略過] {c}：GLOBAL_v3_0 還沒跑完'); continue
        recs = [json.loads(l) for l in open(os.path.join(p, 'raw.jsonl'), encoding='utf-8')]
        rp = replay(c); nd = sum(1 for r, t in zip(recs, rp) if r['texts'] != t)
        st = json.load(open(os.path.join(p, 'stats.json')))
        ev = [dict(r, t_cross=float(r['t_cross']), u=float(r['u'])) for r in csv.DictReader(open(os.path.join(p, 'events.csv'), encoding='utf-8'))]
        sc = L.official_eval(c, ev)['found'] if c.startswith('tpe2t') else L.gt_eval(c, ev)['full']
        res[c] = dict(records=len(recs), replay_len=len(rp), texts_diff=nd, ocr=st['stats']['ocr'], extract_sec=st['extract_sec'],
                      base_sec=base.get(c), score=sc)
        print(f"(2) {c}：OCR {st['stats']['ocr']} 次、和重播不同 {nd} 筆（共 {len(recs)}）｜抽取 {st['extract_sec']} 秒（v2.2 {base.get(c, '—')}）｜cons_color {sc}")
    json.dump(res, open(os.path.join(HERE, 'GPU驗證結果.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

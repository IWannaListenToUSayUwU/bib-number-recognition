r"""R14 離線驗證（不需要 GPU）：三層設定與新模組（settings、ocrgate、bibrules、extract8）是否正確。
  1. 每個片段都能合併三層設定；列出實際的定案模式、能不能算過線、抽取參數
  2. GLOBAL_v2_2 ＋ bibrules.events 在 R12 的 v2.2 raw 上 → 過線事件和 R12 out_crossing 逐筆相同（C、D）
  3. GLOBAL_v3_0 的定案規則在 v2.2 raw 上 → 和 R13 cons_color 的數字相同（調整集 75/251、C+D 91/122、檢查集 36/160）
  4. ocrgate.OcrGate 重播 R13 的完整 OCR raw → OCR 次數和 R13 r13_policy_sim 的 static2＋zone500 相同（C 2228、D 2798、tpe2t_2700 4016）
用法（在專案根目錄）：python 30_實驗/R14_三層設定/r14_verify.py　輸出：30_實驗/R14_三層設定/驗證結果.json"""
import csv, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src')); sys.path.insert(0, os.path.join(ROOT, '30_實驗', 'R13_新機位讀號碼'))
import settings, bibrules  # noqa: E402
from ocrgate import OcrGate  # noqa: E402
import r13_lib as L  # noqa: E402   官方對照、score_v2 評分沿用 R13 的函式
R12 = os.path.join(ROOT, '30_實驗', 'R12_第二機位'); R13 = os.path.join(ROOT, '30_實驗', 'R13_新機位讀號碼')
CLIPS = ['tpe_A_300', 'tpe_B_1200', 'tpe_C_600', 'tpe_D_1800', 'tpe2_A_3000', 'tpe2_B_4200', 'tpe2_C_5400', 'tpe2t_2700', 'tpe2t_3600', 'tpe2t_4800', 'tpe2t_5700']
TUNE = CLIPS[7:]; CHECK = CLIPS[4:7]; GUARD = ['tpe_C_600', 'tpe_D_1800']


def raw_v22(c):
    if c in GUARD or c in CHECK: return os.path.join(R12, 'out', 'FROZEN_CONFIG_v2_2', c, 'raw.jsonl')
    return os.path.join(R13, 'out', 'FROZEN_CONFIG_v2_2', c, 'raw.jsonl')


def video(c): return os.path.join(ROOT, '20_測試基準', 'clips', c + '.mp4')


def main():
    out = {}
    print('== 1. 合併三層設定')
    for g in ('GLOBAL_v2_2', 'GLOBAL_v3_0'):
        for c in CLIPS:
            S = settings.for_clip(g, c); kw = settings.extract_kwargs(S)
            out.setdefault('merge', {}).setdefault(g, {})[c] = dict(mode=S['mode'], can_cross=S['can_cross'], camera=S['camera_name'],
                                                                     zone='zone_line' in kw, static_s=kw.get('static_s'))
        print(g, {c: (v['mode'], v['can_cross'], v['zone']) for c, v in out['merge'][g].items()})
    print('== 2. GLOBAL_v2_2 重現 R12 過線事件（C、D）')
    for c in GUARD:
        S = settings.for_clip('GLOBAL_v2_2', c); ev = bibrules.events(raw_v22(c), S)
        old = list(csv.DictReader(open(os.path.join(R12, 'out_crossing', c, 'events.csv'), encoding='utf-8')))
        same = [(str(e['t_cross']), e['bib']) for e in ev] == [(o['t_cross'], o['bib']) for o in old]
        out.setdefault('reproduce_v22', {})[c] = same; print(c, len(ev), '和 R12 逐筆相同：', same)
    print('== 3. GLOBAL_v3_0 定案規則重現 R13 cons_color')
    tot = {}
    for c in TUNE + GUARD + CHECK:
        S = settings.for_clip('GLOBAL_v3_0', c)
        ev = bibrules.events(raw_v22(c), S, video_path=video(c))
        if c in GUARD: x = L.gt_eval(c, ev); k = ('guard', x['full'], x['n_gt'])
        else: x = L.official_eval(c, ev); k = ('tune' if c in TUNE else 'check', x['found'], x['official_in_clip'])
        a = tot.setdefault(k[0], [0, 0]); a[0] += k[1]; a[1] += k[2]
    out['v30_decision'] = {k: f'{a}/{b}' for k, (a, b) in tot.items()}
    print('調整集', out['v30_decision']['tune'], '（R13：75/251）｜C+D', out['v30_decision']['guard'], '（R13：91/122）｜檢查集', out['v30_decision']['check'], '（R13：36/160）')
    print('== 4. OcrGate 重播完整 OCR（static 2 秒、0.1×人高；線上游 500／下游 150 像素）')
    D = __import__('re').compile(r'\d+')
    from collections import Counter, defaultdict
    for c in ('tpe_C_600', 'tpe_D_1800', 'tpe2t_2700'):
        S = settings.for_clip('GLOBAL_v3_0', c); kw = settings.extract_kwargs(S)
        gate = OcrGate(kw['static_s'], kw['static_p'], kw.get('zone_line'), kw.get('zone_up'), kw.get('zone_down'))
        good = defaultdict(Counter); n = 0
        for l in open(os.path.join(R13, 'FULL', 'out', 'R13_FULL_ocr', c, 'raw.jsonl'), encoding='utf-8'):
            r = json.loads(l); v = r['tid']
            allow = gate.allow(r['t'], r.get('rawtid', v), r['pbox']) and not (v >= 0 and good[v] and good[v].most_common(1)[0][1] >= 3)
            if allow and r['texts'] is not None:
                n += 1
                for txt, sc, bb in r['texts']:
                    d_ = D.findall(txt.replace(' ', ''))
                    if d_ and float(sc) > 0.9 and v >= 0: good[v][max(d_, key=len)] += 1
        out.setdefault('gate_replay', {})[c] = n; print(c, 'OCR', n)
    exp = {'tpe_C_600': 2228, 'tpe_D_1800': 2798, 'tpe2t_2700': 4016}
    out['gate_replay_matches_r13'] = all(out['gate_replay'][c] == v for c, v in exp.items())
    print('和 R13 r13_policy_sim 相同：', out['gate_replay_matches_r13'], exp)
    json.dump(out, open(os.path.join(HERE, '驗證結果.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

r"""R13 提速策略的精確重現（離線）：用「完整 OCR」的 raw（R13_FULL_ocr：每格都 OCR、不提早停止）重播各種 OCR 策略。
為什麼是精確的：偵測、追蹤、換人切分都不看 OCR 結果；同一格同一個裁切的 OCR 結果是固定的。所以「某一格要不要 OCR」換成任何規則，
都只是把完整紀錄中那一格的 texts 保留或拿掉（texts=None）。先用 early_stop=3 重播，必須和 v2.2 的 raw 逐筆相同（驗證模擬器）。
策略參數：
  es       讀到同一號碼幾次（信心 ≥ 0.9）就停止 OCR（v2.2＝3）
  static   不動的人不 OCR：(秒數 S, 人高比例 P)，例 (2.0, 0.1)
  every    同一條虛擬軌跡每 K 格才 OCR
  zone     只在腳的位置離線 [上游 up 像素, 下游 down 像素] 內才 OCR（線＝該片段的計時線）
  good_len 提早停止只算這個長度的讀數（號碼是 5 碼 → 被截斷的 4 碼讀數不會讓 OCR 提早停止）
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_policy_sim.py
輸出：30_實驗/R13_新機位讀號碼/FULL/策略模擬.json"""
import json, os, re, sys
from collections import Counter, defaultdict, deque
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path  # noqa: E402
from crossing import LineCrossing  # noqa: E402
D = re.compile(r'\d+')
CLIPS = ['tpe_C_600', 'tpe_D_1800', 'tpe2t_2700']


def replay(recs, clip, es=3, static=None, every=1, zone=None, good_len=None):
    Ln = L.line_of(clip); lc = LineCrossing(Ln['p1'], Ln['p2'], Ln['upstream'], L.AGG, Ln['frame'][0])
    good = defaultdict(Counter); hist = defaultdict(deque); nseen = defaultdict(int); out = []; n = 0
    for r in recs:
        v = r['tid']; rid = r.get('rawtid', v); x1, y1, x2, y2 = r['pbox']; h = y2 - y1
        allow = not (v >= 0 and good[v] and good[v].most_common(1)[0][1] >= es)
        if static and rid >= 0:
            q = hist[rid]; q.append((r['t'], (x1 + x2) / 2, (y1 + y2) / 2))
            while q and q[0][0] < r['t'] - static[0]: q.popleft()
            if r['t'] - q[0][0] >= static[0] - 0.07 and max(((q[-1][1] - a) ** 2 + (q[-1][2] - b) ** 2) ** 0.5 for _, a, b in q) < static[1] * h:
                allow = False
        if every > 1:
            k = nseen[v]; nseen[v] += 1
            if k % every: allow = False
        if zone:
            d = lc.side((x1 + x2) / 2, y2)          # 正＝上游（還沒過線）
            if not (-zone[1] <= d <= zone[0]): allow = False
        texts = r['texts'] if allow else None
        if texts is not None:
            n += 1
            for txt, sc, bb in texts:
                d_ = D.findall(txt.replace(' ', ''))
                # raw 存的信心值四捨五入到 3 位；原程式用未四捨五入的值判斷 ≥ 0.9。存成 0.900 的多半是 0.8995–0.8999，所以用 > 0.9
                if d_ and float(sc) > 0.9 and v >= 0 and (good_len is None or len(max(d_, key=len)) == good_len): good[v][max(d_, key=len)] += 1
        out.append(dict(r, texts=texts))
    return out, n


def evaluate(clip, recs, tmp):
    with open(tmp, 'w', encoding='utf-8') as fo:
        for r in recs: fo.write(json.dumps(r) + '\n')
    ev = L.crossing_events(tmp, clip, 'v22')
    if clip.startswith('tpe2t_'):
        x = L.official_eval(clip, ev); return dict(found=x['found'], n=x['official_in_clip'], wrong=x['time_mismatch'] + x['not_in_list'])
    x = L.gt_eval(clip, ev); return dict(full=x['full'], n=x['n_gt'], wrong=x['wrong'])


POLICIES = {
    'v22(es3)': dict(es=3),
    'es2': dict(es=2), 'es5': dict(es=5), 'es999(全讀)': dict(es=999),
    'static2': dict(es=3, static=(2.0, 0.1)), 'static3': dict(es=3, static=(3.0, 0.1)),
    'every2': dict(es=3, every=2), 'every3': dict(es=3, every=3),
    'zone300_100': dict(es=3, zone=(300, 100)), 'zone500_150': dict(es=3, zone=(500, 150)), 'zone800_200': dict(es=3, zone=(800, 200)),
    'every2+static2': dict(es=3, every=2, static=(2.0, 0.1)),
    'static2+zone500': dict(es=3, static=(2.0, 0.1), zone=(500, 150)),
    'static2+zone800': dict(es=3, static=(2.0, 0.1), zone=(800, 200)),
    'es3_len5': dict(es=3, good_len=5),
    'es3_len5+static2+zone500': dict(es=3, good_len=5, static=(2.0, 0.1), zone=(500, 150)),
}


def main():
    res = {}; tmp = os.path.join(HERE, 'FULL', '_tmp_policy.jsonl')
    for c in CLIPS:
        p = raw_path('R13_FULL_ocr', c)
        if not os.path.exists(p): print(f'[略過] {c}：完整 OCR 還沒跑完'); continue
        recs = [json.loads(l) for l in open(p, encoding='utf-8')]
        # 驗證：es=3 重播必須和 v2.2 的 raw 逐筆相同
        ref = [json.loads(l) for l in open(raw_path('FROZEN_CONFIG_v2_2', c), encoding='utf-8')]
        rp, _ = replay(recs, c, es=3)
        same = len(rp) == len(ref) and all(a['texts'] == b['texts'] and a['pbox'] == b['pbox'] and a['tid'] == b['tid'] for a, b in zip(rp, ref))
        nd = sum(1 for a, b in zip(rp, ref) if a['texts'] != b['texts'])
        print(f'{c}: 完整 OCR {sum(r["texts"] is not None for r in recs)} 次；es=3 重播和 v2.2 raw 逐筆相同：{same}（不同 {nd} 筆；信心值四捨五入到 0.900 時無法判斷）')
        res.setdefault('_validation', {})[c] = dict(identical=same, diff_records=nd, records=len(ref))
        for name, pol in POLICIES.items():
            rr, n = replay(recs, c, **pol); m = evaluate(c, rr, tmp)
            res.setdefault(name, {})[c] = dict(ocr=n, **m)
            print(f'  {name:16s} OCR {n:5d} 次  {m}')
    if os.path.exists(tmp): os.remove(tmp)
    json.dump(dict(policies={k: str(v) for k, v in POLICIES.items()}, results=res), open(os.path.join(HERE, 'FULL', '策略模擬.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

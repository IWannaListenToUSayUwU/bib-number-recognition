r"""R13 E3 候選（提速）：不動的人不跑 OCR —— 離線模擬。
做法：raw.jsonl 中，若某人（ByteTrack 編號）在過去 S 秒內，人框中心移動不到 P×人框高度，這一格的 OCR 就當作沒做（texts=None），
再用 v2.2 的過線模組重算事件，看 OCR 次數少多少、分數變多少。
這是保守的模擬：真的不做 OCR 時，提早停止的時間點可能不同，但只會影響不動的人。
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_static_sim.py [S=2.0] [P=0.1] [raw 來源=FROZEN_CONFIG_v2_2] [K=1]
  K>1：另外模擬「同一個人每 K 格才 OCR 一次」（追蹤仍是每秒 16 格；K=2 ≈ OCR 每秒 8 次）。S=0 表示不做「不動的人」規則。
片段：調整集＋C、D（不跑檢查集）。"""
import json, os, sys
from collections import defaultdict, deque
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from r13_e1 import raw_path, TUNE, GUARD  # noqa: E402


def simulate(rawp, S, P, K=1):
    hist = defaultdict(deque); out = []; n_ocr = n_skip = 0; seen = defaultdict(int)
    for l in open(rawp, encoding='utf-8'):
        r = json.loads(l); rid = r.get('rawtid', r['tid'])
        x1, y1, x2, y2 = r['pbox']; cx, cy = (x1 + x2) / 2, (y1 + y2) / 2; h = max(1, y2 - y1)
        q = hist[rid]; q.append((r['t'], cx, cy))
        while q and q[0][0] < r['t'] - S: q.popleft()
        static = S > 0 and (r['t'] - q[0][0] >= S - 0.07) and max(((cx - a) ** 2 + (cy - b) ** 2) ** 0.5 for _, a, b in q) < P * h
        k = seen[rid]; seen[rid] += 1
        if r['texts'] is not None:
            n_ocr += 1
            if static or (K > 1 and k % K): n_skip += 1; r = dict(r, texts=None)
        out.append(r)
    return out, n_ocr, n_skip


def main():
    a = sys.argv[1:]; S = float(a[0]) if a else 2.0; P = float(a[1]) if len(a) > 1 else 0.1
    src = a[2] if len(a) > 2 else 'FROZEN_CONFIG_v2_2'; K = int(a[3]) if len(a) > 3 else 1
    tmp = os.path.join(HERE, 'E3_sim'); os.makedirs(tmp, exist_ok=True)
    tot = dict(ocr=0, skip=0, base_found=0, sim_found=0, n=0, base_full=0, sim_full=0, gn=0)
    for c in TUNE + GUARD:
        p = raw_path(src, c)
        if not os.path.exists(p): continue
        recs, n_ocr, n_skip = simulate(p, S, P, K)
        tp = os.path.join(tmp, f'{c}.jsonl')
        with open(tp, 'w', encoding='utf-8') as fo:
            for r in recs: fo.write(json.dumps(r) + '\n')
        e0 = L.crossing_events(p, c); e1 = L.crossing_events(tp, c)
        if c in TUNE:
            b, s = L.official_eval(c, e0), L.official_eval(c, e1)
            msg = f"官方找到 {b['found']} → {s['found']} / {b['official_in_clip']}；一致 {b['consistent']} → {s['consistent']}；錯誤輸出 {b['time_mismatch'] + b['not_in_list']} → {s['time_mismatch'] + s['not_in_list']}"
            tot['base_found'] += b['found']; tot['sim_found'] += s['found']; tot['n'] += b['official_in_clip']
        else:
            b, s = L.gt_eval(c, e0), L.gt_eval(c, e1)
            msg = f"score_v2 {b['full']} → {s['full']} / {b['n_gt']}；錯誤輸出 {b['wrong']} → {s['wrong']}"
            tot['base_full'] += b['full']; tot['sim_full'] += s['full']; tot['gn'] += b['n_gt']
        tot['ocr'] += n_ocr; tot['skip'] += n_skip
        print(f'{c}: OCR {n_ocr} 次，可省 {n_skip}（{n_skip / max(1, n_ocr):.0%}）；{msg}')
        os.remove(tp)
    print(f"合計 S={S} P={P} K={K}：OCR 可省 {tot['skip']}/{tot['ocr']}（{tot['skip'] / max(1, tot['ocr']):.0%}）；"
          f"調整集找到 {tot['base_found']} → {tot['sim_found']} / {tot['n']}；C+D {tot['base_full']} → {tot['sim_full']} / {tot['gn']}")
    json.dump(dict(S=S, P=P, K=K, src=src, **tot), open(os.path.join(tmp, f'模擬_S{S}_P{P}_K{K}.json'), 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main()

r"""用官方完賽名單「獨立」評估舊機位（轉角）A～D 段的號碼輸出（不靠舊 AI 答案，也不看過線，只看出現的號碼）。
系統輸出：raw.jsonl → aggregate3（v2.2 投票規則）。A、B：R04 的每秒 8 格 raw，以及 R13 用 v2.2 16 格重跑的（AB16）；C、D 用 R06（16 格）和 R05（8 格）。
時間差：轉角機位沒有時鐘，用「系統輸出中在名單上的號碼」的 官方時間 − 出現時間 的中位數 m（對讀錯有抗性）。
  一致＝號碼在名單且 |官方 − 出現時間 − m| ≤ 25 秒（轉角到終點的跑步時間因人而異，MAD 約 4～6 秒）
  精確度＝一致的輸出 ÷ 全部輸出（5 碼以外的輸出也算在分母）
  召回率＝官方中 m＋10 ≤ 官方時間 − 片段時間 ≤ m＋50 的人（片段中段，避開邊緣）有被輸出的比例
用法（在專案根目錄）：python 30_實驗/R13_新機位讀號碼/r13_oldclips_official.py　輸出：診斷\舊機位_官方名單評估.json"""
import json, os, statistics, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r13_lib as L  # noqa: E402
from aggregate3 import aggregate3  # noqa: E402
X = os.path.join(L.ROOT, '30_實驗')
SRC = {('tpe_A_300', '8fps_R04'): os.path.join(X, 'R04_台北馬基準', 'out', 'tpe_A_300', 'raw.jsonl'),
       ('tpe_B_1200', '8fps_R04'): os.path.join(X, 'R04_台北馬基準', 'out', 'tpe_B_1200', 'raw.jsonl'),
       ('tpe_C_600', '8fps_R05'): os.path.join(X, 'R05_5碼修正', 'out', 'tpe_C_600', 'raw.jsonl'),
       ('tpe_D_1800', '8fps_R05'): os.path.join(X, 'R05_5碼修正', 'out', 'tpe_D_1800', 'raw.jsonl'),
       ('tpe_C_600', '16fps_R06'): os.path.join(X, 'R06_16fps', 'out', 'tpe_C_600', 'raw.jsonl'),
       ('tpe_D_1800', '16fps_R06'): os.path.join(X, 'R06_16fps', 'out', 'tpe_D_1800', 'raw.jsonl'),
       ('tpe_A_300', '16fps_R13'): os.path.join(X, 'R13_新機位讀號碼', 'AB16', 'out', 'FROZEN_CONFIG_v2_2', 'tpe_A_300', 'raw.jsonl'),
       ('tpe_B_1200', '16fps_R13'): os.path.join(X, 'R13_新機位讀號碼', 'AB16', 'out', 'FROZEN_CONFIG_v2_2', 'tpe_B_1200', 'raw.jsonl')}
TOL = 25.0


def preds(rawp, W):
    rows = []
    for l in open(rawp, encoding='utf-8'):
        r = json.loads(l)
        for txt, sc, bb in (r.get('texts') or []): rows.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc))
    return aggregate3(rows, **L.AGG, frame_w=W)


def main():
    off = {r['bib']: L.sec(r['time']) for r in L.official()['rows']}; out = {}
    for (c, src), p in SRC.items():
        if not os.path.exists(p): continue
        P = preds(p, 1920)
        d = [off[x['bib']] - x['t'] for x in P if x['bib'] in off]
        m = statistics.median(d)
        ok = [x for x in P if x['bib'] in off and abs(off[x['bib']] - x['t'] - m) <= TOL]
        dur = 60.0
        mid = [b for b, t in off.items() if m + 10 <= t - 0 <= m + 50]          # 片段時間 0..60 → 官方 ≈ m＋t
        got = {x['bib'] for x in ok}
        rec = sum(1 for b in mid if b in got)
        r = dict(outputs=len(P), consistent=len(ok), precision=round(len(ok) / len(P), 3), precision_ci=L.wilson(len(ok), len(P)),
                 mid_official=len(mid), mid_found=rec, recall_mid=round(rec / len(mid), 3) if mid else None, recall_ci=L.wilson(rec, len(mid)) if mid else None,
                 offset_median=round(m, 1), non5=sum(1 for x in P if len(x['bib']) != 5))
        out[f'{c}|{src}'] = r
        print(f"{c:11s} {src:10s} 輸出 {len(P):3d}｜官方一致 {len(ok):3d}（精確度 {r['precision']}）｜非 5 碼 {r['non5']}｜片段中段官方 {len(mid)} 人、讀到 {rec}（召回 {r['recall_mid']}）")
    json.dump(dict(rules=__doc__, results=out), open(os.path.join(HERE, '診斷', '舊機位_官方名單評估.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

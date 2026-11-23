r"""20_測試基準 唯一評分程式。所有實驗的分數都只能用這支算，才能互相比較。
用法：python score.py <結果資料夾> [片段 ...]
  <結果資料夾> 底下要有 <片段名>\result.csv（以及 raw.jsonl，用來算混人軌跡）
  不給片段就評所有有 result.csv 的片段。
規則（與第三輪起的 evaluate.py 相同）：
  TP = 號碼完全相同、時間落在正確答案 [t0-2, t1+2]；同一個正確號碼只算一次，重複輸出算 FP
  與 partial（只看得清部分數字，? 為萬用字元）相容的輸出不計 FP 也不計 TP
  F1 = 2PR/(P+R)，P = TP/(TP+FP)，R = TP/正確號碼數
附加指標：mixed_tracks = 同一條軌跡中 conf>=0.9 的讀數完全等於兩個以上不同的正確號碼（換人沒切開）
輸出：螢幕 + <結果資料夾>\score.json"""
import csv, json, os, re, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 2.0

def compat(pat, b):
    return pat != '?' and len(pat) == len(b) and all(p == '?' or p == c for p, c in zip(pat, b))

def score_clip(preds, g):
    matched = set(); tp = fp = ign = 0; fps = []
    for b, t, sc in sorted(preds, key=lambda x: -x[2]):
        hit = next((i for i, s in enumerate(g['sure']) if s['bib'] == b and s['t0'] - TOL <= t <= s['t1'] + TOL), None)
        if hit is not None and hit not in matched:
            matched.add(hit); tp += 1
        elif hit is None and any(compat(p['pat'], b) and p['t0'] - TOL <= t <= p['t1'] + TOL for p in g['partial']):
            ign += 1
        else:
            fp += 1; fps.append([b, round(t, 1)])
    return dict(tp=tp, fp=fp, ign=ign, n=len(g['sure']), fn=[s['bib'] for i, s in enumerate(g['sure']) if i not in matched], fp_list=fps)

def f1(tp, fp, n):
    P = tp / (tp + fp) if tp + fp else 0; R = tp / n if n else 0
    return dict(TP=tp, FP=fp, N=n, P=round(P, 3), R=round(R, 3), F1=round(2 * P * R / (P + R), 3) if P + R else 0)

def mixed(rawp, sure):
    per = defaultdict(set)
    if not os.path.exists(rawp): return None
    for l in open(rawp, encoding='utf-8'):
        r = json.loads(l)
        for txt, sc, _ in (r.get('texts') or []):
            d = re.sub(r'\D', '', txt)
            if sc >= 0.9 and d in sure: per[r['tid']].add(d)
    return dict(mixed_tracks=sum(len(s) >= 2 for s in per.values()), tracks_with_correct_read=len(per))

def main():
    root = os.path.abspath(sys.argv[1])
    clips = sys.argv[2:] or sorted(d for d in os.listdir(root) if os.path.exists(os.path.join(root, d, 'result.csv')))
    res = {}; T = dict(tp=0, fp=0, n=0, mixed=0, tracks=0)
    for c in clips:
        gp = os.path.join(HERE, 'gt', c + '.json')
        if not os.path.exists(gp): print(f'[略過] {c}：20_測試基準\\gt 沒有正確答案'); continue
        g = json.load(open(gp, encoding='utf-8'))
        preds = [(r['bib'], float(r['time_s']), float(r['score'])) for r in csv.DictReader(open(os.path.join(root, c, 'result.csv'), encoding='utf-8'))]
        s = score_clip(preds, g); m = mixed(os.path.join(root, c, 'raw.jsonl'), {x['bib'] for x in g['sure']})
        res[c] = dict(**f1(s['tp'], s['fp'], s['n']), ignored=s['ign'], FN=s['fn'], FP_list=s['fp_list'], **(m or {}))
        T['tp'] += s['tp']; T['fp'] += s['fp']; T['n'] += s['n']
        if m: T['mixed'] += m['mixed_tracks']; T['tracks'] += m['tracks_with_correct_read']
        print(f"{c:12s} F1={res[c]['F1']:.3f}  P={res[c]['P']:.3f} R={res[c]['R']:.3f}  TP={s['tp']} FP={s['fp']} 正解={s['n']}" + (f"  混人軌跡={m['mixed_tracks']}/{m['tracks_with_correct_read']}" if m else ''))
    tot = dict(**f1(T['tp'], T['fp'], T['n']), mixed_tracks=T['mixed'], tracks_with_correct_read=T['tracks'], clips=list(res))
    print(f"{'合計':10s} F1={tot['F1']:.3f}  P={tot['P']:.3f} R={tot['R']:.3f}  混人軌跡={T['mixed']}/{T['tracks']}")
    json.dump(dict(total=tot, per_clip=res, scorer='20_測試基準/score.py', tol_s=TOL), open(os.path.join(root, 'score.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()

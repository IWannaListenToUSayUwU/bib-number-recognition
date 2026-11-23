r"""R10 過線雛形：用現有的 raw.jsonl（不需 GPU）算過線事件，並做初步評估。
用法（在專案根目錄）：python 30_實驗/R10_過線雛形/r10_crossing.py
輸入：30_實驗/R05_5碼修正/out/<片段>/raw.jsonl（v2.1 每秒 8 格、讀 3 次就停；用 v2.2 的投票規則重算＝v2.2 8fps）
輸出：30_實驗/R10_過線雛形/out/ 底下
  v2_2_8fps_重算/<片段>/result.csv、score.json   （確認 0.917 能重現；舊指標）
  crossing/<來源>_<片段>_events_w<秒>.csv          （過線事件，w＝過線後等幾秒定案）
  crossing/summary.json                            （各片段、各等待秒數的統計與初步評估）
  抽查/抽查_過線_<來源>.jpg、抽查/抽查清單_<來源>.csv（隨機 20 個事件的過線畫面，給人眼核對）
  抽查/線_<片段>.jpg                               （線畫在四段片段上的樣子）
初步評估（score_v2 草案）：還沒有「過線時間」的正確答案（R11 才做），所以只能檢查：
  號碼是否在正確答案裡、且過線時間落在該號碼出現期間 [t0-2, t1+10] 內；以及各類事件的數量與延遲。
  同時比較兩種抽取來源：R05（每秒 8 格）與 R06（每秒 16 格），兩者都用 v2.2 的投票規則。"""
import csv, json, math, os, random, subprocess, sys
from collections import Counter
import cv2, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src'))
from aggregate3 import aggregate3, load4
from crossing import run_file
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
CLIPS = ['tpe_C_600', 'tpe_D_1800']
SOURCES = {'8fps': os.path.join(ROOT, '30_實驗', 'R05_5碼修正', 'out', '{}', 'raw.jsonl'),   # v2.1 抽取、8 格
           '16fps': os.path.join(ROOT, '30_實驗', 'R06_16fps', 'out', '{}', 'raw.jsonl')}    # v2.2 抽取、16 格（同一支 extract4）
RAW = SOURCES['8fps']
EVAL_AFTER = 10.0   # 初步評估：過線時間要落在該號碼「出現期間 [t0-2, t1+10]」內（跑者讀到號碼後，要再跑幾秒才到線）
CFG = json.load(open(os.path.join(ROOT, '10_程式', 'work', 'FROZEN_CONFIG_v2_2.json'), encoding='utf-8'))
LINE = json.load(open(os.path.join(ROOT, '10_程式', 'work', 'LINE_tpe_v1.json'), encoding='utf-8'))
AGG = CFG['aggregate']; W = LINE['frame'][0]
WAITS = [1.0, 2.0, 3.0, 1e9]          # 1e9 = 不限（等軌跡結束，等同離線）
MAIN_WAIT = 3.0


def imwrite(p, img):
    os.makedirs(os.path.dirname(p), exist_ok=True); cv2.imencode('.jpg', img)[1].tofile(p)


def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def compat(pat, b):
    return pat != '?' and len(pat) == len(b) and all(p == '?' or p == c for p, c in zip(pat, b))


def reproduce_v22():
    """用 R05 的讀數＋v2.2 投票規則重算 result.csv，再用 20_測試基準/score.py 評分。"""
    root = os.path.join(OUT, 'v2_2_8fps_重算')
    for c in CLIPS:
        rows, _ = load4(RAW.format(c))
        preds = aggregate3(rows, **AGG, frame_w=W)
        os.makedirs(os.path.join(root, c), exist_ok=True)
        with open(os.path.join(root, c, 'result.csv'), 'w', newline='', encoding='utf-8') as fo:
            wr = csv.writer(fo); wr.writerow(['bib', 'time_s', 'first_s', 'last_s', 'score', 'tids'])
            for p in sorted(preds, key=lambda x: x['t']):
                wr.writerow([p['bib'], f'{p["t"]:.3f}', f'{p["t0"]:.3f}', f'{p["t1"]:.3f}', f'{p["score"]:.3f}', ';'.join(map(str, p['tids']))])
    r = subprocess.run([sys.executable, os.path.join(ROOT, '20_測試基準', 'score.py'), root] + CLIPS, capture_output=True, text=True, encoding='utf-8')
    print(r.stdout.strip())
    return json.load(open(os.path.join(root, 'score.json'), encoding='utf-8'))['total']


def evaluate(events, g, res_bibs):
    """初步評估：每個事件分類，並算號碼正確率（含 95% 區間）。"""
    sure = {s['bib']: s for s in g['sure']}; seen = set(); cat = Counter()
    for e in events:
        b = e['bib']
        if not b:
            e['eval'] = 'unknown'
        elif e['dup']:
            e['eval'] = 'dup'
        elif b in sure and sure[b]['t0'] - 2 <= e['t_cross'] <= sure[b]['t1'] + EVAL_AFTER:
            e['eval'] = 'dup' if b in seen else 'correct'; seen.add(b)
        elif any(compat(p['pat'], b) for p in g['partial']):
            e['eval'] = 'partial'
        else:
            e['eval'] = 'wrong'
        cat[e['eval']] += 1
    lat = sorted(e['latency'] for e in events)
    n_bib = cat['correct'] + cat['wrong'] + cat['dup']
    runners = len(g['sure']) + len(g['partial']) + g.get('n_unreadable', 0) + g.get('n_nobib', 0)
    return dict(events=len(events), **{k: cat[k] for k in ('correct', 'wrong', 'dup', 'partial', 'unknown')},
                bib_precision=round(cat['correct'] / n_bib, 3) if n_bib else 0, bib_precision_ci=wilson(cat['correct'], n_bib),
                sure_found=len(seen), sure_total=len(g['sure']), sure_found_offline=len(res_bibs & set(sure)),
                gt_runners_all=runners,
                latency_median=lat[len(lat) // 2] if lat else None, latency_max=lat[-1] if lat else None)


def draw_line(img, scale=1.0, off=(0, 0)):
    p1 = (int((LINE['p1'][0] - off[0]) * scale), int((LINE['p1'][1] - off[1]) * scale))
    p2 = (int((LINE['p2'][0] - off[0]) * scale), int((LINE['p2'][1] - off[1]) * scale))
    cv2.line(img, p1, p2, (255, 0, 255), 2)


def grab(clip, t):
    cap = cv2.VideoCapture(os.path.join(ROOT, '20_測試基準', 'clips', clip + '.mp4'))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps))); ok, f = cap.read(); cap.release()
    return f if ok else None


def line_previews():
    for c in CLIPS:
        f = grab(c, 30.0)
        if f is None: continue
        draw_line(f); cv2.circle(f, tuple(LINE['upstream']), 8, (0, 255, 0), -1)
        cv2.putText(f, c + '  magenta = line, green = upstream', (20, 40), 0, 1.0, (255, 0, 255), 3)
        imwrite(os.path.join(HERE, '抽查', f'線_{c}.jpg'), cv2.resize(f, (960, 506)))


def sample_sheet(allev, n=20, seed=0, tag=''):
    """隨機抽 n 個事件，截過線那一格（以腳的交點為中心裁 360x360），拼成一張圖。"""
    random.seed(seed); pick = sorted(random.sample(allev, min(n, len(allev))), key=lambda e: (e['clip'], e['t_cross']))
    tiles = []
    for i, e in enumerate(pick, 1):
        f = grab(e['clip'], e['t_cross'])
        x0 = int(min(max(e['x'] - 180, 0), f.shape[1] - 360)); y0 = int(min(max(e['y'] - 300, 0), f.shape[0] - 360))
        draw_line(f); cv2.circle(f, (e['x'], e['y']), 6, (0, 255, 255), -1)
        tile = f[y0:y0 + 360, x0:x0 + 360].copy()
        lab = f"#{i} {e['clip'][4]} t={e['t_cross']:.2f} {e['bib'] or '?'}"
        cv2.rectangle(tile, (0, 0), (360, 30), (0, 0, 0), -1); cv2.putText(tile, lab, (5, 22), 0, 0.65, (255, 255, 255), 2)
        tiles.append(tile); e['sample_no'] = i
    while len(tiles) % 5: tiles.append(np.zeros((360, 360, 3), np.uint8))
    sheet = np.vstack([np.hstack(tiles[r:r + 5]) for r in range(0, len(tiles), 5)])
    imwrite(os.path.join(HERE, '抽查', f'抽查_過線_{tag}.jpg'), sheet)
    with open(os.path.join(HERE, '抽查', f'抽查清單_{tag}.csv'), 'w', newline='', encoding='utf-8-sig') as fo:
        wr = csv.writer(fo); wr.writerow(['編號', '片段', '過線時間', '系統號碼', '初步評估', '人眼號碼（請填）', '過線時間是否正確（請填）'])
        for e in pick: wr.writerow([e['sample_no'], e['clip'], e['t_cross'], e['bib'] or '?', e['eval'], '', ''])


def main():
    summ = dict(line=LINE, aggregate='FROZEN_CONFIG_v2_2 (aggregate3)', sources={k: v.replace(ROOT, '') for k, v in SOURCES.items()}, eval_window=[-2, EVAL_AFTER])
    summ['v2_2_8fps_重算_舊指標'] = reproduce_v22()
    os.makedirs(os.path.join(OUT, 'crossing'), exist_ok=True)
    res = {}
    for src, rawp in SOURCES.items():
        main_events = []; res[src] = {}
        for c in CLIPS:
            g = json.load(open(os.path.join(ROOT, '20_測試基準', 'gt', c + '.json'), encoding='utf-8'))
            res_bibs = {r['bib'] for r in csv.DictReader(open(os.path.join(OUT, 'v2_2_8fps_重算', c, 'result.csv'), encoding='utf-8'))}
            res[src][c] = {}
            for w in WAITS:
                ev, diag = run_file(rawp.format(c), p1=LINE['p1'], p2=LINE['p2'], upstream=LINE['upstream'], agg=AGG, frame_w=W, decide_after=w)
                m = evaluate(ev, g, res_bibs); m.update(diagnostics=diag)
                gaps = [e['gap'] for e in ev]; m['crossings_gap_over_0.3s'] = sum(x > 0.3 for x in gaps)
                key = 'offline' if w >= 1e8 else f'w{w:g}'; res[src][c][key] = m
                cols = ['id', 't_cross', 'bib', 'guess', 'score', 'n_reads', 'latency', 'decided_by', 'dup', 'eval', 'vid', 'rawtid', 'x', 'y', 'u', 'gap', 'split_at_cross']
                with open(os.path.join(OUT, 'crossing', f'{src}_{c}_events_{key}.csv'), 'w', newline='', encoding='utf-8-sig') as fo:
                    wr = csv.DictWriter(fo, cols, extrasaction='ignore'); wr.writeheader(); wr.writerows(ev)
                if w == MAIN_WAIT:
                    for e in ev: e['clip'] = c
                    main_events += ev
                print(f"{src:5s} {c} {key:8s} 事件={m['events']} 正確={m['correct']} 錯={m['wrong']} 重複={m['dup']} 部分={m['partial']} 未知={m['unknown']} "
                      f"號碼正確率={m['bib_precision']} {m['bib_precision_ci']} 找到sure={m['sure_found']}/{m['sure_total']}(離線{m['sure_found_offline']}) "
                      f"間隔>0.3s={m['crossings_gap_over_0.3s']} 延遲中位={m['latency_median']} 診斷={diag}")
        sample_sheet(main_events, tag=src)
    summ['per_source'] = res
    line_previews()
    json.dump(summ, open(os.path.join(OUT, 'crossing', 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

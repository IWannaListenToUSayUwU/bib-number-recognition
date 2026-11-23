r"""R11 準備：產生標註工具要用的候選事件與過線光帶圖，並把系統結果整理成 score_v2 的格式。
用法（在專案根目錄）：python 30_實驗/R11_過線正確答案/r11_prepare.py
輸出：
  30_實驗/R11_過線正確答案/標註/candidates_<片段>.json   標註工具的候選事件（每秒 16 格、v2.2 投票、等 3 秒定案）
  30_實驗/R11_過線正確答案/標註/slit_<片段>.png、slit_<片段>.json   過線光帶圖（橫軸：每一格；縱軸：線上位置 u）
  30_實驗/R11_過線正確答案/out/<來源>/<片段>/events.csv   系統過線事件（score_v2 的輸入格式），來源＝8fps、16fps
不需要 GPU；只讀 20_測試基準 的片段，不修改。"""
import csv, json, os, sys
import cv2, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src'))
from aggregate3 import norm
from crossing import LineCrossing
HERE = os.path.dirname(os.path.abspath(__file__)); ANN = os.path.join(HERE, '標註')
CLIPS = ['tpe_C_600', 'tpe_D_1800']
SOURCES = {'8fps': os.path.join(ROOT, '30_實驗', 'R05_5碼修正', 'out', '{}', 'raw.jsonl'),
           '16fps': os.path.join(ROOT, '30_實驗', 'R06_16fps', 'out', '{}', 'raw.jsonl')}
CAND_SOURCE = '16fps'; WAIT = 3.0
LINE = json.load(open(os.path.join(ROOT, '10_程式', 'work', 'LINE_tpe_v1.json'), encoding='utf-8'))
AGG = json.load(open(os.path.join(ROOT, '10_程式', 'work', 'FROZEN_CONFIG_v2_2.json'), encoding='utf-8'))['aggregate']
EV_COLS = ['id', 't_cross', 'bib', 'guess', 'score', 'n_reads', 'latency', 'decided_by', 'dup', 'vid', 'rawtid', 'x', 'y', 'u', 'gap', 'split_at_cross']
N_U = 274; OFFS = [0, 20, 40, 60]   # 光帶圖：沿線取 274 點；每點往上取 0/20/40/60 像素，挑和背景差最多的那一個


def run(rawp, clip):
    lc = LineCrossing(LINE['p1'], LINE['p2'], LINE['upstream'], AGG, LINE['frame'][0], decide_after=WAIT)
    recs = [json.loads(l) for l in open(rawp.format(clip), encoding='utf-8')]
    for r in recs: lc.feed(r)
    return lc.flush(), lc, recs


def write_events(src, clip, ev):
    od = os.path.join(HERE, 'out', src, clip); os.makedirs(od, exist_ok=True)
    with open(os.path.join(od, 'events.csv'), 'w', newline='', encoding='utf-8') as fo:
        wr = csv.DictWriter(fo, EV_COLS, extrasaction='ignore'); wr.writeheader(); wr.writerows(ev)


def best_bib_frame(lc, recs_by_vt, e):
    """這個人最適合看號碼的一格：讀數和系統號碼（沒有就用猜測）相同、信心×字高最大的那一格。"""
    target = e['bib'] or e['guess']; best = None
    for x in lc.reads.get(e['vid'], []):
        s = norm(x['txt'])
        if not s: continue
        k = (s == target, x['sc'] * x['bh'])
        if best is None or k > best[0]: best = (k, x)
    if best is None: return None
    x = best[1]; pb = recs_by_vt.get((e['vid'], x['t']))
    return dict(t=x['t'], text_box=x['bbox'], pbox=pb, text=x['txt'], conf=x['sc'])


def cross_pbox(recs, e):
    c = [r for r in recs if r.get('rawtid') == e['rawtid']]
    if not c: return None
    r = min(c, key=lambda r: abs(r['t'] - e['t_cross'])); return r['pbox']


def gt_candidates(g, t, sysbib=''):
    out = [dict(bib=s['bib'], status='sure', t0=s['t0'], t1=s['t1']) for s in g['sure'] if s['t0'] - 2 <= t <= s['t1'] + 10]
    out += [dict(bib=p['pat'], status='partial', t0=p['t0'], t1=p['t1']) for p in g['partial'] if p['t0'] - 2 <= t <= p['t1'] + 10]
    return sorted(out, key=lambda c: (c['bib'] != sysbib, abs(c['t1'] + 3 - t)))   # 和系統號碼相同的排第一；其餘依「讀到號碼後約 3 秒到線」排


def slit(clip):
    cap = cv2.VideoCapture(os.path.join(ROOT, '20_測試基準', 'clips', clip + '.mp4'))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    u = np.linspace(0, 1, N_U); xs = LINE['p1'][0] + u * (LINE['p2'][0] - LINE['p1'][0]); ys = LINE['p1'][1] + u * (LINE['p2'][1] - LINE['p1'][1])
    samples = []
    while True:
        ok, f = cap.read()
        if not ok: break
        H, W = f.shape[:2]
        xi = np.clip(np.round(xs).astype(int), 0, W - 1)
        samples.append(np.stack([f[np.clip(np.round(ys - o).astype(int), 0, H - 1), xi] for o in OFFS], 1))   # [N_U, len(OFFS), 3]
    cap.release()
    A = np.stack(samples).astype(np.int16)                 # [F, N_U, O, 3]
    bg = np.median(A, axis=0)                              # 背景（每個取樣點的時間中位數）
    dev = np.abs(A - bg).sum(-1)                           # [F, N_U, O]
    k = dev.argmax(-1)                                     # 每格每點挑差最多的高度
    col = np.take_along_axis(A, k[..., None, None].repeat(3, -1), 2)[:, :, 0]   # [F, N_U, 3]
    d = np.take_along_axis(dev, k[..., None], 2)[..., 0]
    w = np.clip(d / 120.0, 0.25, 1.0)[..., None]           # 和背景差越少越暗，讓跑者的腳比較明顯
    img = (col * w).clip(0, 255).astype(np.uint8).transpose(1, 0, 2)   # [N_U, F, 3]：縱軸 u、橫軸時間
    os.makedirs(ANN, exist_ok=True)
    cv2.imencode('.png', img)[1].tofile(os.path.join(ANN, f'slit_{clip}.png'))
    json.dump(dict(clip=clip, fps=fps, frames=len(samples), n_u=N_U, offsets=OFFS, line=LINE['p1'] + LINE['p2']),
              open(os.path.join(ANN, f'slit_{clip}.json'), 'w', encoding='utf-8'))
    return len(samples), fps


def main():
    os.makedirs(ANN, exist_ok=True)
    for src, rawp in SOURCES.items():
        for c in CLIPS:
            ev, lc, recs = run(rawp, c); write_events(src, c, ev)
            print(f'{src} {c}: {len(ev)} 個過線事件 → out/{src}/{c}/events.csv')
            if src != CAND_SOURCE: continue
            g = json.load(open(os.path.join(ROOT, '20_測試基準', 'gt', c + '.json'), encoding='utf-8'))
            by_vt = {(r['tid'], r['t']): r['pbox'] for r in recs}
            cands = []
            for e in ev:
                cands.append(dict(sys_id=e['id'], t_sys=e['t_cross'], x=e['x'], y=e['y'], u=e['u'], bib=e['bib'], guess=e['guess'],
                                  dup=e['dup'], latency=e['latency'], cross_pbox=cross_pbox(recs, e), bib_frame=best_bib_frame(lc, by_vt, e),
                                  ai_gt=gt_candidates(g, e['t_cross'], e['bib'] or e['guess'])[:5]))
            json.dump(dict(clip=c, source=f'{CAND_SOURCE} (R06 raw) + v2.2 aggregate3, decide_after={WAIT}', line='LINE_tpe_v1', items=cands),
                      open(os.path.join(ANN, f'candidates_{c}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for c in CLIPS:
        n, fps = slit(c); print(f'光帶圖 {c}: {n} 格（{fps:g} fps）')


if __name__ == '__main__':
    main()

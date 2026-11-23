"""第三版聚合（v2.2）：修正寫死像素與規則衝突。
(1) size_ref="rel_track"：字高權重改成相對於同一軌跡中最大的字高（與解析度無關）；"abs40" 為舊行為。
(2) accept_hi：同一軌跡中某號碼有 >= accept_hi 次信心>=0.9 的讀數就直接採用（與抽取的提早停止條件一致）。
(3) static_rel：固定位置門檻依畫面寬度等比例換算（基準 1280）。
以下為原第二輪說明：第二輪聚合：在 aggregate 的基礎上
(1) 記錄每個預測來自哪些軌跡與時間區間（供 demo 疊字使用）；
(2) 固定位置文字過濾：同一號碼的讀數在畫面上幾乎不動、又持續數秒 → 視為背景（車牌、看板）。"""
import json, re, numpy as np
from collections import defaultdict
D = re.compile(r'\d+')

def norm(txt):
    m = D.findall((txt or '').replace(' ', ''))
    return max(m, key=len) if m else ''

def load4(path):
    rows, boxes = [], defaultdict(list)
    for l in open(path):
        r = json.loads(l)
        boxes[r['tid']].append((r['t'], r['pbox']))
        for txt, sc, bb in (r.get('texts') or []):
            rows.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc))
    return rows, boxes

def aggregate3(rows, min_conf=0.8, min_votes=1, min_score=0.9, minlen=2, maxlen=5, size_w=True, size_ref="rel_track", accept_hi=3, frame_w=1280,
               merge_gap=4.0, substr=True, sub_gap=3.0, static_px=12, static_sec=2.0, static=True, static_rel=True):
    if static_rel:
        static_px = static_px * frame_w / 1280.0
    maxbh = defaultdict(float)
    for r in rows:
        s = norm(r['txt'])
        if minlen <= len(s) <= maxlen and r['sc'] >= min_conf:
            maxbh[r['tid']] = max(maxbh[r['tid']], r['bh'])
    groups = defaultdict(list)
    for r in rows:
        s = norm(r['txt']); c = r['sc']
        if not (minlen <= len(s) <= maxlen) or c < min_conf:
            continue
        if not size_w:
            w = c
        elif size_ref == 'abs40':
            w = c * min(1.0, r['bh'] / 40)
        else:
            w = c * min(1.0, r['bh'] / max(1.0, maxbh[r['tid']]))
        key = r['tid'] if r['tid'] >= 0 else ('f', r['t'], tuple(r['bbox']))
        cx, cy = (r['bbox'][0] + r['bbox'][2]) / 2, (r['bbox'][1] + r['bbox'][3]) / 2
        groups[key].append((s, w, r['t'], cx, cy, c))
    cand = []
    for key, v in groups.items():
        tally = defaultdict(float); cnt = defaultdict(int); tbest = {}; hi = defaultdict(int)
        for s, w, t, cx_, cy_, c_ in v:
            tally[s] += w; cnt[s] += 1; hi[s] += (c_ >= 0.9)
            if s not in tbest or w > tbest[s][0]: tbest[s] = (w, t)
        if substr:
            for a in sorted(tally, key=len):
                longer = [b for b in tally if len(b) > len(a) and a in b]
                if longer:
                    b = max(longer, key=lambda z: tally[z]); tally[b] += tally.pop(a); cnt[b] += cnt.pop(a); hi[b] += hi.pop(a, 0)
        s = max(tally, key=tally.get)
        if cnt[s] >= min_votes and (tally[s] >= min_score or (accept_hi and hi[s] >= accept_hi)):
            pts = [(t, cx, cy) for ss, w, t, cx, cy, c_ in v]
            cand.append(dict(bib=s, t=tbest.get(s, (0, v[0][2]))[1], score=tally[s], tids={key},
                             t0=min(p[0] for p in pts), t1=max(p[0] for p in pts), pts=pts))
    if static:   # 固定位置：讀數中心點的移動範圍很小且持續夠久
        keep = []
        allpts = defaultdict(list)
        for c in cand: allpts[c['bib']] += c['pts']
        for c in cand:
            P = np.array(allpts[c['bib']])
            if len(P) >= 3 and (P[:, 0].max() - P[:, 0].min()) >= static_sec and \
               (P[:, 1].max() - P[:, 1].min()) <= static_px and (P[:, 2].max() - P[:, 2].min()) <= static_px:
                continue
            keep.append(c)
        cand = keep
    cand.sort(key=lambda c: (c['bib'], c['t0']))
    out = []
    for c in cand:
        if out and out[-1]['bib'] == c['bib'] and c['t0'] - out[-1]['t1'] <= merge_gap:
            p = out[-1]; best = p if p['score'] >= c['score'] else c
            out[-1] = dict(bib=p['bib'], t=best['t'], score=p['score'] + c['score'], tids=p['tids'] | c['tids'],
                           t0=min(p['t0'], c['t0']), t1=max(p['t1'], c['t1']), pts=p['pts'] + c['pts'])
        else:
            out.append(c)
    if substr:
        out = [c for c in out if not any(len(o['bib']) > len(c['bib']) and c['bib'] in o['bib'] and abs(o['t'] - c['t']) <= sub_gap for o in out)]
    return out

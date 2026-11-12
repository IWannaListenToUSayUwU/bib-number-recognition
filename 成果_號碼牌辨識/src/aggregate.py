"""把逐格讀數聚合成最終預測 [(bib, t, score)]。"""
import json, re
from collections import defaultdict
D = re.compile(r'\d+')

def norm(txt):
    m = D.findall((txt or '').replace(' ', ''))
    return max(m, key=len) if m else ''

def reads_of(r, reader):
    """回傳此筆偵測的 (字串, 信心) 候選。"""
    if '+' in reader:
        return [x for k in reader.split('+') for x in reads_of(r, k)]
    if reader == 'rap':
        return [(norm(r['rap'][0]), r['rap'][1])]
    if reader == 'ez':
        return [(norm(r['ez'][0]), r['ez'][1])]
    if reader == 'rapd':
        c = [(norm(t), s) for t, s in r['rapd']]
        c = [x for x in c if x[0]]
        return [max(c, key=lambda x: (len(x[0]), x[1]))] if c else []
    if reader == 'svhn':
        return [(r['svhn'][0], r['svhn'][1])]
    raise ValueError(reader)

def aggregate(rows, reader='rap', minlen=2, maxlen=4, min_conf=0.5, min_votes=1, min_score=0.0,
              use_track=True, size_w=True, merge_gap=4.0, min_bh=0, srcs=None, substr=True, sub_gap=3.0):
    groups = defaultdict(list)
    for r in rows:
        if r['bh'] < min_bh or (srcs and r.get('src') not in srcs):
            continue
        for s, c in reads_of(r, reader):
            if not (minlen <= len(s) <= maxlen) or c < min_conf:
                continue
            key = r['tid'] if use_track and r['tid'] >= 0 else ('frame', r['t'], tuple(r['bbox']))
            w = c * (min(1.0, r['bh'] / 40) if size_w else 1.0)
            groups[key].append((s, w, r['t']))
    cand = []
    for key, v in groups.items():
        tally = defaultdict(float); cnt = defaultdict(int); tbest = {}
        for s, w, t in v:
            tally[s] += w; cnt[s] += 1
            if s not in tbest or w > tbest[s][0]:
                tbest[s] = (w, t)
        if substr:   # 軌跡內：較短讀數若為較長讀數的子字串，票數併入較長者
            for a in sorted(tally, key=len):
                longer = [b for b in tally if len(b) > len(a) and a in b]
                if longer:
                    b = max(longer, key=lambda z: tally[z])
                    tally[b] += tally.pop(a); cnt[b] += cnt.pop(a)
        s = max(tally, key=tally.get)
        total = sum(tally.values())
        if cnt[s] >= min_votes and tally[s] >= min_score:
            cand.append((s, tbest[s][1], tally[s], tally[s] / total, min(t for _, _, t in v), max(t for _, _, t in v)))
    # 相同號碼、時間相近的軌跡合併
    cand.sort(key=lambda x: (x[0], x[1]))
    out = []
    for c in cand:
        if out and out[-1][0] == c[0] and c[4] - out[-1][5] <= merge_gap:
            p = out[-1]
            best = p if p[2] >= c[2] else c
            out[-1] = (p[0], best[1], p[2] + c[2], best[3], min(p[4], c[4]), max(p[5], c[5]))
        else:
            out.append(c)
    if substr:   # 跨軌跡：時間相近時，較短號碼若為較長號碼的子字串則刪除
        keep = []
        for c in out:
            if any(len(o[0]) > len(c[0]) and c[0] in o[0] and abs(o[1] - c[1]) <= sub_gap for o in out):
                continue
            keep.append(c)
        out = keep
    return [(s, t, sc) for s, t, sc, *_ in out]

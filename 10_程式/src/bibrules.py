"""號碼定案規則（2026-11-23，由 30_實驗/R13_新機位讀號碼/r13_lib.py 整理成正式模組）。
在過線模組（crossing.LineCrossing）「定案」那一步套用比賽層的資料：
  v22        不用名單（和 v2.2 相同）
  len5       只保留 bib_len 碼的號碼（只需要知道號碼幾碼）
  pre_keep   投票前丟掉「bib_len 碼但不在名單」的讀數 → v2.2 投票 → 不在名單的號碼：短一碼且「前或後補一碼後名單上只有一個」才補，否則讀不出
  cons       pre_keep 之後還讀不出的人：多次部分讀數（3～bib_len 碼）和名單比（完全相同 1、子字串 len/bib_len、只差一碼 0.6，乘信心加總），
             最高分 ≥ cons_min 且 ≥ cons_margin×第二名才採用
  cons_color cons＋號碼布顏色：文字框內偏藍比例 ≥ blue_hi → 只考慮 hi_lead 開頭；≤ blue_lo → 只考慮 lo_lead 開頭；
             已定案但開頭和顏色矛盾 → 讀不出。只在名單上兩種開頭都存在時才用顏色。
R13 結果：新機位檢查集官方名單找到率 v22 0.150 → cons_color 0.225、錯誤輸出 25 → 3；C+D score_v2 92 → 91。
選項 decision.long_trim（2026-11-24，R17；預設關閉）：比 bib_len 長的讀數（號碼前多印組別字，OCR 讀成 130042）→ 取名單上唯一的 bib_len 碼片段；
  沒有名單時取最後 bib_len 碼。關閉時結果和原本逐字相同（R17 重算 R14 的 C、D 段驗證）。
"""
import json, os
from crossing import LineCrossing
from aggregate3 import norm

MODES = ('v22', 'len5', 'pre_keep', 'cons', 'cons_color')


def completer(reg, bib_len):
    """不在名單的號碼 → 名單上的號碼或 None（短一碼時，前或後補一碼後名單上唯一才補）。"""
    def fix(s):
        if s in reg: return s
        if len(s) != bib_len - 1: return None
        c = ({d + s for d in '0123456789'} | {s + d for d in '0123456789'}) & reg
        return c.pop() if len(c) == 1 else None
    return fix


class SubIndex:
    def __init__(self, reg, bib_len):
        self.idx = {}
        for b in reg:
            for n in range(3, bib_len + 1):
                for i in range(len(b) - n + 1): self.idx.setdefault(b[i:i + n], set()).add(b)

    def get(self, s): return self.idx.get(s, set())


def other_lead(b, hi, lo):
    return (lo if b[0] == hi else hi) + b[1:]


def consensus(rows, reg, idx, bib_len, cons_min, cons_margin, min_conf=0.5, lead=None, colors_rule=None):
    """同一人多次部分讀數 → 名單上最符合的號碼（或 None）。lead：只考慮這個開頭（顏色判斷；只過濾兩種開頭都在名單上的號碼）。"""
    reads = [(norm(x['txt']), x['sc']) for x in rows]
    reads = [(s, c) for s, c in reads if 3 <= len(s) <= bib_len and c >= min_conf]
    if not reads: return None, 0.0
    cand = set()
    for s, _ in reads:
        cand |= idx.get(s)
        if len(s) == bib_len: cand |= {s[:i] + d + s[i + 1:] for i in range(bib_len) for d in '0123456789'} & reg
    if lead is not None and colors_rule:
        hi, lo = colors_rule['hi_lead'], colors_rule['lo_lead']
        cand = {b for b in cand if not (b[0] in (hi, lo) and b[0] != lead and other_lead(b, hi, lo) in reg)}
    if not cand: return None, 0.0
    def sim(s, b):
        if s == b: return 1.0
        if s in b: return len(s) / float(bib_len)
        if len(s) == bib_len and sum(p != q for p, q in zip(s, b)) == 1: return 0.6
        return 0.0
    sc = sorted(((sum(c * sim(s, b) for s, c in reads), b) for b in cand), reverse=True)
    best, b1 = sc[0]; second = sc[1][0] if len(sc) > 1 else 0.0
    return (b1 if best >= cons_min and best >= cons_margin * max(second, 1e-9) else None), best


def color_cache(video_path, raw_path, rule, cache_path=None):
    """raw 裡每一筆 3 碼以上數字讀數的文字框 → 框內符合 rule['hsv'] 的像素比例。從頭依序讀影片一次（不跳轉）。"""
    import cv2
    if cache_path and os.path.exists(cache_path):
        return {(t, tuple(bb)): v for t, bb, v in json.load(open(cache_path, encoding='utf-8'))}
    H = rule['hsv']; need = {}
    for l in open(raw_path, encoding='utf-8'):
        r = json.loads(l)
        for txt, sc, bb in (r.get('texts') or []):
            if len(norm(txt)) >= 3: need.setdefault(r['t'], []).append(tuple(bb))
    cap = cv2.VideoCapture(video_path); fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    byframe = {}
    for t, bbs in need.items(): byframe.setdefault(int(round(t * fps)), []).extend((t, bb) for bb in bbs)
    out = {}; last = max(byframe) if byframe else -1; fi = -1
    while fi < last:
        ok, f = cap.read(); fi += 1
        if not ok: break
        for t, (x1, y1, x2, y2) in byframe.get(fi, []):
            c = f[max(0, y1):y2, max(0, x1):x2]
            if c.size == 0: continue
            hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV); h, s_, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
            out[(t, (x1, y1, x2, y2))] = float(((h >= H['h'][0]) & (h <= H['h'][1]) & (s_ >= H['s_min']) & (v >= H['v_min'])).mean())
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        json.dump([[t, list(bb), v] for (t, bb), v in out.items()], open(cache_path, 'w', encoding='utf-8'))
    return out


class RuleCrossing(LineCrossing):
    """crossing.LineCrossing＋號碼定案規則。mode 見本檔開頭；reg＝號碼名單（set）；colors＝color_cache 的結果。"""
    def __init__(self, *a, mode='v22', reg=None, bib_len=5, decision=None, colors_rule=None, colors=None, **k):
        super().__init__(*a, **k)
        if mode not in MODES: raise ValueError(mode)
        self.mode = mode; self.reg = reg or set(); self.bib_len = bib_len; D = decision or {}
        self.cons_min = float(D.get('cons_min', 1.5)); self.cons_margin = float(D.get('cons_margin', 1.5)); self.cons_min_conf = float(D.get('cons_min_conf', 0.5))
        self.colors_rule = colors_rule; self.colors = colors or {}
        self.fix = completer(self.reg, bib_len) if self.reg else None
        self.idx = SubIndex(self.reg, bib_len) if mode in ('cons', 'cons_color') else None
        self.long_trim = bool(D.get('long_trim', False))   # R17：號碼前多印一個字（組別字）→ OCR 讀成 6 碼（例 130042）

    def _trim(self, rows):
        """long_trim：比 bib_len 長的讀數 → 取其中「在名單上」的 bib_len 碼片段（唯一才取）；沒有名單時取最後 bib_len 碼。"""
        if not self.long_trim: return rows
        out = []
        for x in rows:
            s = norm(x['txt'])
            if len(s) > self.bib_len:
                w = {s[i:i + self.bib_len] for i in range(len(s) - self.bib_len + 1)}
                if self.reg:
                    w &= self.reg
                    if len(w) == 1: x = dict(x, txt=w.pop())
                else:
                    x = dict(x, txt=s[-self.bib_len:])
            out.append(x)
        return out

    def _blue(self, rows):
        v = sorted(self.colors[(x['t'], tuple(x['bbox']))] for x in rows if (x['t'], tuple(x['bbox'])) in self.colors)
        return v[len(v) // 2] if v else None

    def _decide(self, e, horizon, why):
        vid = e['vid']; orig0 = self.reads.get(vid, []); orig = self._trim(orig0)
        if self.mode in ('pre_keep', 'cons', 'cons_color'):
            self.reads[vid] = [x for x in orig if not (len(norm(x['txt'])) == self.bib_len and norm(x['txt']) not in self.reg)]
        elif self.long_trim:
            self.reads[vid] = orig
        try:
            super()._decide(e, horizon, why)
        finally:
            self.reads[vid] = orig0
        b = e['bib']
        if self.mode == 'len5' and b and len(b) != self.bib_len: e['bib'] = ''
        if self.mode in ('pre_keep', 'cons', 'cons_color') and b: e['bib'] = self.fix(b) or ''
        if self.mode in ('cons', 'cons_color'):
            rows = [x for x in orig if x['t'] <= horizon]; lead = None
            if self.mode == 'cons_color' and self.colors_rule:
                R = self.colors_rule; bl = self._blue(rows); e['blue'] = bl
                lead = None if bl is None else (R['hi_lead'] if bl >= R['blue_hi'] else R['lo_lead'] if bl <= R['blue_lo'] else None)
                if e['bib'] and lead is not None and e['bib'][0] in (R['hi_lead'], R['lo_lead']) and e['bib'][0] != lead \
                        and other_lead(e['bib'], R['hi_lead'], R['lo_lead']) in self.reg:
                    e['bib'] = ''; e['decided_by'] = e.get('decided_by', '') + '+color_veto'
            if not e['bib']:
                cb, _ = consensus(rows, self.reg, self.idx, self.bib_len, self.cons_min, self.cons_margin, self.cons_min_conf,
                                  lead=lead, colors_rule=self.colors_rule)
                if cb: e['bib'] = cb; e['decided_by'] = e.get('decided_by', '') + ('+cons_color' if self.mode == 'cons_color' else '+cons')


def events(raw_path, S, video_path=None, color_cache_path=None):
    """用合併後的設定 S（settings.for_clip）從 raw.jsonl 算過線事件（含號碼定案規則）。機位沒有計時線時回傳 None。"""
    C = S['camera']; G = S['G']
    if not C.get('line'): return None
    X = G['crossing']; mode = S['mode']; R = S['race']
    colors = None
    if mode == 'cons_color':
        if not video_path: raise ValueError('cons_color 需要影片路徑（量號碼布顏色）')
        colors = color_cache(video_path, raw_path, R['bib_colors'], color_cache_path)
    lc = RuleCrossing(C['line']['p1'], C['line']['p2'], C['line']['upstream'], G['aggregate'], C['frame'][0],
                      decide_after=X['decide_after'], track_gap=X['track_gap'], u_range=tuple(X['u_range']), min_travel=X['min_travel'],
                      max_gap=X['max_gap'], dedupe_gap=X['dedupe_gap'],
                      mode=mode, reg=S['bibs'], bib_len=R.get('bib_len', 5), decision=G['decision'],
                      colors_rule=R.get('bib_colors'), colors=colors)
    for l in open(raw_path, encoding='utf-8'): lc.feed(json.loads(l))
    ev = lc.flush()
    if mode != 'v22':                                # 號碼改過 → 重算重複標記（同號 dedupe_gap 秒內再過線）
        seen = {}
        for e in ev:
            b = e['bib']; e['dup'] = bool(b) and b in seen and e['t_cross'] - seen[b] <= lc.dedupe_gap
            if b and not e['dup']: seen[b] = e['t_cross']
    return ev


EV_COLS = ['id', 't_cross', 'bib', 'guess', 'score', 'n_reads', 'latency', 'decided_by', 'dup', 'vid', 'rawtid', 'x', 'y', 'u', 'gap', 'split_at_cross']


def write_events(ev, path):
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as fo:
        w = csv.DictWriter(fo, EV_COLS, extrasaction='ignore'); w.writeheader(); w.writerows(ev)

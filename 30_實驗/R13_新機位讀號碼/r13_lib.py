r"""R13 共用函式：號碼名單規則（E1）、過線事件、官方成績對照（任何 tpe2 片段）、C／D 的 score_v2。
官方對照的規則和 R12 `r12_official.py` 完全相同（計畫.md ③）：
  系統槍聲時間＝片段開頭時鐘＋t_cross；官方一致＝號碼在官方名單且 |官方−系統| ≤ 2 秒；
  官方名單找到率＝官方時間在片段第 1～59 秒的人中，系統有輸出同號碼且官方一致的比例。
號碼名單模式（mode）：
  v22      不用名單（和 v2.2 相同）
  len5     只保留 5 碼的號碼（不用名單；主辦單位至少知道號碼是幾碼）
  post     投票後：號碼不在名單 → 4 碼且「0＋號碼」在名單就補 0，否則當讀不出
  pre      投票前：每筆讀數先過名單（4 碼且補 0 後在名單 → 補 0；不在名單 → 丟掉），再用 v2.2 的投票
  pre_noz  同 pre，但不補 0（用來看補 0 的效果）
  post_noz 同 post，但不補 0（號碼不在名單就當讀不出）
  pre_keep 投票前只丟掉「5 碼但不在名單」的讀數（較短的讀數保留，讓子字串合併照常運作），投票後再套 post_uq
  cons     pre_keep 之後，還是讀不出的事件用「共識解碼」補：同一人多次部分讀數（3～5 碼）和名單比，
           分數＝Σ 信心×相似度（完全相同 1、是子字串 len/5、5 碼只差一碼 0.6），最高分 ≥ CONS_MIN 且 ≥ CONS_MARGIN×第二名才採用
  cons_color 同 cons，再加號碼布顏色（2022 臺北馬：1 開頭藍紫底、0 開頭白底；r13_bibcolor.py 量的）：
           這個人數字讀數文字框內的藍色比例中位數 ≥ BLUE_HI → 只考慮 1 開頭的號碼；≤ BLUE_LO → 只考慮 0 開頭；
           已定案的號碼若開頭和顏色矛盾 → 改成讀不出。顏色只用在「名單上 0 開頭和 1 開頭兩個版本都存在」的號碼（尾 4 碼 ≤ 1783）
  post_uq  同 post，但 4 碼號碼改成「前面或後面補一碼後，名單上只有唯一一個」才補（例：7701 → 只有 07701；1015 → 01015、10150～10159 有多個，不補）"""
import csv, json, math, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src')); sys.path.insert(0, os.path.join(ROOT, '20_測試基準'))
from aggregate3 import norm            # noqa: E402
from crossing import LineCrossing      # noqa: E402
import score_v2                         # noqa: E402

AGG = json.load(open(os.path.join(ROOT, '10_程式', 'work', 'FROZEN_CONFIG_v2_2.json'), encoding='utf-8'))['aggregate']
MAN = json.load(open(os.path.join(ROOT, '20_測試基準', 'MANIFEST.json'), encoding='utf-8'))
OFFICIAL = os.path.join(HERE, '官方成績', '官方完賽名單_全馬.json')
EV_COLS = ['id', 't_cross', 'bib', 'guess', 'score', 'n_reads', 'latency', 'decided_by', 'dup', 'vid', 'rawtid', 'x', 'y', 'u', 'gap', 'split_at_cross']
TOL = 2.0; WAIT = 3.0
CLOCK_A = 13324.067   # tpe2 原片 3000 秒（tpe2_A 第 0 秒）的槍聲時間（R12 時鐘對照.json）


def sec(s):
    h, m, x = map(int, s.split(':')); return h * 3600 + m * 60 + x


_off = None


def official():
    global _off
    if _off is None: _off = json.load(open(OFFICIAL, encoding='utf-8'))
    return _off


def registry():
    return {r['bib'] for r in official()['rows']}


def clock_at_t0(clip):
    return CLOCK_A + (MAN['clips'][clip]['start_s'] - 3000)


def line_of(clip):
    return json.load(open(os.path.join(ROOT, '10_程式', 'work', MAN['clips'][clip].get('line') or 'LINE_tpe_v1') + '.json', encoding='utf-8'))


# ---------- 號碼名單規則 ----------
def mapper(mode, reg):
    def fix(s):
        if s in reg: return s
        if mode == 'post_uq':
            if len(s) != 4: return None
            c = {d + s for d in '0123456789'} | {s + d for d in '0123456789'}
            c &= reg
            return c.pop() if len(c) == 1 else None
        if len(s) == 4 and '0' + s in reg and mode not in ('pre_noz', 'post_noz'): return '0' + s
        return None
    return fix


CONS_MIN = float(os.environ.get('CONS_MIN', '1.5')); CONS_MARGIN = float(os.environ.get('CONS_MARGIN', '1.5'))
_subidx = {}


def sub_index(reg):
    key = id(reg)
    if key not in _subidx:
        idx = {}
        for b in reg:
            for L_ in (3, 4, 5):
                for i in range(len(b) - L_ + 1): idx.setdefault(b[i:i + L_], set()).add(b)
        _subidx[key] = idx
    return _subidx[key]


BLUE_HI = float(os.environ.get('BLUE_HI', '0.40')); BLUE_LO = float(os.environ.get('BLUE_LO', '0.30'))


def color_cache(clip, rawp):
    """raw 裡每一筆 3 碼以上數字讀數的文字框 → 框內藍色比例（HSV H 95–140、S ≥ 60、V ≥ 40）。
    從頭依序讀影片一次（不跳轉，跳轉很慢）；結果依 raw 的 sha256 存在 _color_cache 資料夾，重算時直接讀。"""
    import cv2, hashlib
    h = hashlib.sha256(open(rawp, 'rb').read()).hexdigest()[:16]
    cp = os.path.join(HERE, '_color_cache', f'{clip}_{h}.json')
    if os.path.exists(cp):
        return {(t, tuple(bb)): v for t, bb, v in json.load(open(cp, encoding='utf-8'))}
    need = {}
    for l in open(rawp, encoding='utf-8'):
        r = json.loads(l)
        for txt, sc, bb in (r.get('texts') or []):
            if len(norm(txt)) >= 3: need.setdefault(int(round(r['t'] * 30)), []).append((r['t'], tuple(bb)))
    out = {}; cap = cv2.VideoCapture(os.path.join(ROOT, '20_測試基準', 'clips', clip + '.mp4')); last = max(need) if need else -1; fi = -1
    while fi < last:
        ok, f = cap.read(); fi += 1
        if not ok: break
        for t, (x1, y1, x2, y2) in need.get(fi, []):
            c = f[max(0, y1):y2, max(0, x1):x2]
            if c.size == 0: continue
            hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV); hh, s_, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
            out[(t, (x1, y1, x2, y2))] = float(((hh >= 95) & (hh <= 140) & (s_ >= 60) & (v >= 40)).mean())
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    json.dump([[t, list(bb), v] for (t, bb), v in out.items()], open(cp, 'w', encoding='utf-8'))
    return out


def other_lead(b):
    return ('1' if b[0] == '0' else '0') + b[1:]


def track_blue(rows, colors):
    v = sorted(colors[(x['t'], tuple(x['bbox']))] for x in rows if (x['t'], tuple(x['bbox'])) in colors)
    return v[len(v) // 2] if v else None


def consensus(rows, reg, min_conf=0.5, lead=None):
    """同一人多次部分讀數 → 名單上最符合的號碼（或 None）。lead：只考慮這個開頭數字的號碼（顏色判斷）。"""
    idx = sub_index(reg); reads = []
    for x in rows:
        s = norm(x['txt'])
        if 3 <= len(s) <= 5 and x['sc'] >= min_conf: reads.append((s, x['sc']))
    if not reads: return None, 0.0
    cand = set()
    for s, _ in reads:
        cand |= idx.get(s, set())
        if len(s) == 5: cand |= {s[:i] + d + s[i + 1:] for i in range(5) for d in '0123456789'} & reg
    if lead is not None: cand = {b for b in cand if not (b[0] in '01' and b[0] != lead and other_lead(b) in reg)}
    if not cand: return None, 0.0
    def sim(s, b):
        if s == b: return 1.0
        if s in b: return len(s) / 5.0
        if len(s) == 5 and sum(p != q for p, q in zip(s, b)) == 1: return 0.6
        return 0.0
    sc = sorted(((sum(c * sim(s, b) for s, c in reads), b) for b in cand), reverse=True)
    best, b1 = sc[0]; second = sc[1][0] if len(sc) > 1 else 0.0
    return (b1 if best >= CONS_MIN and best >= CONS_MARGIN * max(second, 1e-9) else None), best


class RegLC(LineCrossing):
    """v2.2 的過線模組，只在「定案」那一步套用號碼名單規則。"""
    def __init__(self, *a, mode='v22', reg=None, colors=None, **k):
        super().__init__(*a, **k); self.mode = mode; self.colors = colors or {}; self.reg = reg or set(); self.fix = mapper('post_uq' if mode in ('pre_keep', 'cons', 'cons_color') else mode, self.reg)

    def _decide(self, e, horizon, why):
        vid = e['vid']; orig = self.reads.get(vid, [])
        if self.mode in ('pre_keep', 'cons', 'cons_color'):
            self.reads[vid] = [x for x in orig if not (len(norm(x['txt'])) == 5 and norm(x['txt']) not in self.reg)]
        if self.mode in ('pre', 'pre_noz'):
            rows = []
            for x in orig:
                s = norm(x['txt'])
                if not s: continue
                f = self.fix(s)
                if f: rows.append(dict(x, txt=f))
            self.reads[vid] = rows
        try:
            super()._decide(e, horizon, why)
        finally:
            self.reads[vid] = orig
        b = e['bib']
        if self.mode in ('post', 'post_noz', 'post_uq', 'pre_keep', 'cons', 'cons_color') and b:
            e['bib'] = self.fix(b) or ''
        if self.mode == 'cons' and not e['bib']:
            rows = [x for x in orig if x['t'] <= horizon]
            cb, cs = consensus(rows, self.reg)
            if cb: e['bib'] = cb; e['decided_by'] = e.get('decided_by', '') + '+cons'
        if self.mode == 'cons_color':
            rows = [x for x in orig if x['t'] <= horizon]
            bl = track_blue(rows, self.colors); lead = None if bl is None else ('1' if bl >= BLUE_HI else '0' if bl <= BLUE_LO else None)
            if e['bib'] and lead is not None and e['bib'][0] in '01' and e['bib'][0] != lead and other_lead(e['bib']) in self.reg:
                e['bib'] = ''; e['decided_by'] = e.get('decided_by', '') + '+color_veto'
            if not e['bib']:
                cb, cs = consensus(rows, self.reg, lead=lead)
                if cb: e['bib'] = cb; e['decided_by'] = e.get('decided_by', '') + '+cons_color'
            e['blue'] = bl
        if self.mode == 'len5' and b and len(b) != 5:
            e['bib'] = ''
        if self.mode != 'v22' and e['bib'] != b:   # 重新算重複（同號 5 秒內）
            e['dup'] = False


def crossing_events(rawp, clip, mode='v22', reg=None, wait=WAIT):
    L = line_of(clip)
    colors = color_cache(clip, rawp) if mode == 'cons_color' else None
    lc = RegLC(L['p1'], L['p2'], L['upstream'], AGG, L['frame'][0], decide_after=wait, mode=mode, reg=reg, colors=colors)
    for l in open(rawp, encoding='utf-8'): lc.feed(json.loads(l))
    ev = lc.flush()
    if mode != 'v22':                             # 號碼改過 → 重算重複標記（同號 5 秒內再過線；score_v2 不看這欄，自己判斷重複）
        seen = {}
        for e in ev:
            b = e['bib']; e['dup'] = bool(b) and b in seen and e['t_cross'] - seen[b] <= lc.dedupe_gap
            if b and not e['dup']: seen[b] = e['t_cross']
    return ev


def write_events(ev, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as fo:
        w = csv.DictWriter(fo, EV_COLS, extrasaction='ignore'); w.writeheader(); w.writerows(ev)


# ---------- 評分 ----------
def official_eval(clip, ev):
    t0 = clock_at_t0(clip); offl = {}
    for r in official()['rows']:
        x = sec(r['time'])
        if t0 - 5 <= x <= t0 + 65: offl.setdefault(r['bib'], []).append(x)
    cnt = Counter(); found = set(); d = []
    for e in ev:
        b = e['bib']; g = t0 + float(e['t_cross'])
        if not b: cnt['unknown'] += 1; continue
        if b in offl:
            dd = min((x - g for x in offl[b]), key=abs)
            if abs(dd) <= TOL: cnt['consistent'] += 1; found.add(b); d.append(dd)
            else: cnt['time_mismatch'] += 1
        else: cnt['not_in_list'] += 1
    inside = [b for b, ts in offl.items() if any(t0 + 1 <= x <= t0 + 59 for x in ts)]
    return dict(events=len(ev), official_in_clip=len(inside), found=sum(1 for b in inside if b in found),
                consistent=cnt['consistent'], time_mismatch=cnt['time_mismatch'], not_in_list=cnt['not_in_list'], unknown=cnt['unknown'], deltas=d)


def gt_eval(clip, ev):
    g = json.load(open(os.path.join(ROOT, '20_測試基準', 'gt_crossing', clip + '.json'), encoding='utf-8'))
    sys_ev = [dict(t=float(e['t_cross']), bib=e['bib'] or '', u=float(e['u']), latency=e.get('latency')) for e in ev]
    s = score_v2.score_clip(sys_ev, g['events']); raw = s.pop('_raw')
    return dict(n_gt=s['n_gt'], full=raw['full'], wrong=raw['wrong'], corr=raw['corr'], unk=raw['unk'])


def wilson(k, n): return score_v2.wilson(k, n)

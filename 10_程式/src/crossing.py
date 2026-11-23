"""過線模組（R10 雛形）：從逐格的人物框紀錄算出「號碼＋過線時間」。

輸入：raw.jsonl 格式的紀錄（extract4／5／6 的輸出），每筆 = 某一格中的一個人：
      {"t": 秒, "tid": 虛擬軌跡編號, "rawtid": ByteTrack 編號, "pbox": [x1,y1,x2,y2], "texts": [[字, 信心, 字框], ...] 或 null}
輸出：過線事件，每個人一筆：號碼（讀不出就空白）、過線時間、延遲……

可即時運算的設計：
- 紀錄必須依時間順序一筆一筆餵進來（feed），模組只用「過去到現在」的資料。
- 過線判斷：人物框底部中心（腳的位置）從線的上游側跑到下游側，用前後兩格內插出過線時間。
  用 ByteTrack 編號判斷（位置是連續的），號碼則掛在過線那一刻的虛擬軌跡上。
- 號碼定案：過線後再等 decide_after 秒（或軌跡結束，取先到者），只用這段時間以前的讀數投票，
  投票規則直接沿用 aggregate3（和 v2.2 相同）。過線時間本身取自畫面時間，不受定案延遲影響。
- 延遲 latency = 定案時間 - 過線時間（資料上的延遲，不含運算時間）。
"""
import math
from collections import defaultdict
from aggregate3 import aggregate3, norm


class LineCrossing:
    def __init__(self, p1, p2, upstream, agg, frame_w, decide_after=3.0, track_gap=1.0,
                 u_range=(0.0, 1.3), min_travel=100.0, max_gap=2.0, dedupe_gap=5.0):
        """p1、p2：線的兩端（畫面像素）；upstream：跑者來的那一側的任一點。
        agg：aggregate3 的參數（FROZEN_CONFIG 的 aggregate 區塊）。
        u_range：交點落在線段上的範圍（0＝p1，1＝p2，可略為延長）。
        min_travel：從軌跡第一次出現到過線至少要移動的像素（排除站在線旁的人）。
        max_gap：前後兩格相隔超過這麼多秒就不內插（視為追蹤中斷）。
        dedupe_gap：同一個號碼在這麼多秒內再次過線，標記為重複。"""
        self.p1 = p1; self.dx = p2[0] - p1[0]; self.dy = p2[1] - p1[1]
        self.L = math.hypot(self.dx, self.dy)
        self.up = 1.0 if self._raw_side(*upstream) > 0 else -1.0
        self.agg = {k: v for k, v in agg.items()}; self.frame_w = frame_w
        self.decide_after = decide_after; self.track_gap = track_gap
        self.u_range = u_range; self.min_travel = min_travel; self.max_gap = max_gap; self.dedupe_gap = dedupe_gap
        self.trk = {}                       # rawtid -> 狀態
        self.reads = defaultdict(list)      # 虛擬軌跡 -> 讀數（aggregate3 的 row 格式）
        self.last_seen = {}                 # 虛擬軌跡 -> 最後出現時間
        self.pending = []; self.events = []; self.recent = {}
        self.now = -math.inf; self.nid = 0

    # --- 幾何 ---
    def _raw_side(self, x, y):
        return self.dx * (y - self.p1[1]) - self.dy * (x - self.p1[0])

    def side(self, x, y):
        """有號距離（像素）：正＝上游側（還沒過線），負＝下游側。"""
        return self.up * self._raw_side(x, y) / self.L

    def _u(self, x, y):
        return ((x - self.p1[0]) * self.dx + (y - self.p1[1]) * self.dy) / (self.L ** 2)

    # --- 串流介面 ---
    def feed(self, r):
        t = r['t']
        if t > self.now:
            self._decide_due(t); self.now = t
        vid = r['tid']; rid = r.get('rawtid', vid)
        if vid is not None and vid >= 0:
            self.last_seen[vid] = t
            for txt, sc, bb in (r.get('texts') or []):
                self.reads[vid].append(dict(t=t, tid=vid, bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc))
        if rid is None or rid < 0:
            return
        x1, y1, x2, y2 = r['pbox']; fx, fy = (x1 + x2) / 2, y2
        d = self.side(fx, fy)
        st = self.trk.get(rid)
        if st is None:
            self.trk[rid] = dict(t=t, d=d, x=fx, y=fy, vid=vid, x0=fx, y0=fy, d0=d, crossed=False, t0=t)
            return
        if not st['crossed'] and st['d'] > 0 >= d:
            a = st['d'] / (st['d'] - d)
            tc = st['t'] + a * (t - st['t'])
            px, py = st['x'] + a * (fx - st['x']), st['y'] + a * (fy - st['y'])
            u = self._u(px, py); gap = t - st['t']
            travel = math.hypot(px - st['x0'], py - st['y0'])
            if self.u_range[0] <= u <= self.u_range[1] and travel >= self.min_travel and gap <= self.max_gap:
                st['crossed'] = True; self.nid += 1
                self.pending.append(dict(id=self.nid, t_cross=round(tc, 3), vid=vid if a >= 0.5 else st['vid'],
                                         rawtid=rid, x=round(px), y=round(py), u=round(u, 3), gap=round(gap, 3),
                                         split_at_cross=(vid != st['vid'])))
        st.update(t=t, d=d, x=fx, y=fy, vid=vid)

    def _horizon(self, e):
        return min(e['t_cross'] + self.decide_after, self.last_seen.get(e['vid'], e['t_cross']) + self.track_gap)

    def _decide_due(self, t):
        keep = []
        for e in self.pending:
            h = self._horizon(e)
            if h < t:
                self._decide(e, h, 'window' if h == e['t_cross'] + self.decide_after else 'track_end')
            else:
                keep.append(e)
        self.pending = keep

    def _decide(self, e, horizon, why):
        rows = [x for x in self.reads.get(e['vid'], []) if x['t'] <= horizon]
        preds = aggregate3(rows, **self.agg, frame_w=self.frame_w) if rows else []
        best = max(preds, key=lambda p: p['score']) if preds else None
        tally = defaultdict(float)
        for x in rows:
            s = norm(x['txt'])
            if self.agg.get('minlen', 2) <= len(s) <= self.agg.get('maxlen', 5):
                tally[s] += x['sc']
        guess = max(tally, key=tally.get) if tally else ''
        bib = best['bib'] if best else ''
        dup = bool(bib) and bib in self.recent and e['t_cross'] - self.recent[bib] <= self.dedupe_gap
        if bib and not dup:
            self.recent[bib] = e['t_cross']
        e.update(bib=bib, guess=guess, score=round(best['score'], 3) if best else 0.0, n_reads=len(rows),
                 decided_at=round(horizon, 3), latency=round(horizon - e['t_cross'], 3), decided_by=why, dup=dup)
        self.events.append(e)

    def flush(self):
        """資料結束：把還沒定案的事件用目前為止的資料定案。"""
        for e in self.pending:
            h = self._horizon(e)
            if h > self.now:
                self._decide(e, self.now, 'eof')
            else:
                self._decide(e, h, 'window' if h == e['t_cross'] + self.decide_after else 'track_end')
        self.pending = []
        return sorted(self.events, key=lambda e: e['t_cross'])

    def diagnostics(self, near_px=150):
        """可能漏計的軌跡：在線前不遠處消失、或第一次出現就已經在線後。"""
        ended_near = [rid for rid, s in self.trk.items() if not s['crossed'] and 0 < s['d'] <= near_px]
        started_after = [rid for rid, s in self.trk.items() if s['d0'] <= 0]
        return dict(tracks=len(self.trk), crossed=sum(s['crossed'] for s in self.trk.values()),
                    ended_near_line=len(ended_near), started_after_line=len(started_after))


def run_file(path, **kw):
    import json
    lc = LineCrossing(**kw)
    for l in open(path, encoding='utf-8'):
        lc.feed(json.loads(l))
    return lc.flush(), lc.diagnostics()

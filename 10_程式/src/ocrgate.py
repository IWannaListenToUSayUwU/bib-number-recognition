"""OCR 閘門（2026-11-23，R13 E3）：決定某個人在這一格要不要做 OCR（提早停止另外由抽取程式處理）。
兩條規則（都在 R13 用「完整 OCR」精確重播驗證過：C+D OCR −22%、新機位 −29%，分數不變）：
  不動的人不讀：同一個人（ByteTrack 編號）過去 static_s 秒內，人框中心移動不到 static_p×人框高度 → 不做 OCR
  只讀線附近  ：腳的位置（人框底部中心）離計時線的有號距離不在 [−zone_down, +zone_up] 像素內 → 不做 OCR（正＝上游、還沒過線）
判斷方式和 30_實驗/R13_新機位讀號碼/r13_policy_sim.py 的重播完全相同。
"""
import math
from collections import defaultdict, deque


class OcrGate:
    def __init__(self, static_s=0.0, static_p=0.1, zone_line=None, zone_up=None, zone_down=None):
        self.static_s = float(static_s or 0.0); self.static_p = float(static_p)
        self.hist = defaultdict(deque)
        self.zone = None
        if zone_line and zone_up is not None and zone_down is not None:
            p1, p2, up = zone_line['p1'], zone_line['p2'], zone_line['upstream']
            self.p1 = p1; self.dx = p2[0] - p1[0]; self.dy = p2[1] - p1[1]; self.L = math.hypot(self.dx, self.dy)
            self.up = 1.0 if self._raw_side(*up) > 0 else -1.0
            self.zone = (float(zone_up), float(zone_down))
        self.n_static = 0; self.n_zone = 0

    def _raw_side(self, x, y):
        return self.dx * (y - self.p1[1]) - self.dy * (x - self.p1[0])

    def side(self, x, y):
        """有號距離（像素）：正＝上游側（還沒過線），負＝下游側。和 crossing.LineCrossing.side 相同。"""
        return self.up * self._raw_side(x, y) / self.L

    @property
    def active(self):
        return self.static_s > 0 or self.zone is not None

    def allow(self, t, rawtid, pbox):
        """每個人每一格都要呼叫一次（不論最後有沒有做 OCR），歷史才會正確。回傳 False＝這一格不做 OCR。"""
        x1, y1, x2, y2 = pbox; h = y2 - y1; ok = True
        if self.static_s > 0 and rawtid is not None and rawtid >= 0:
            q = self.hist[rawtid]; q.append((t, (x1 + x2) / 2, (y1 + y2) / 2))
            while q and q[0][0] < t - self.static_s: q.popleft()
            if t - q[0][0] >= self.static_s - 0.07 and max(math.hypot(q[-1][1] - a, q[-1][2] - b) for _, a, b in q) < self.static_p * h:
                ok = False; self.n_static += 1
        if self.zone is not None:
            d = self.side((x1 + x2) / 2, y2)
            if not (-self.zone[1] <= d <= self.zone[0]):
                if ok: self.n_zone += 1
                ok = False
        return ok

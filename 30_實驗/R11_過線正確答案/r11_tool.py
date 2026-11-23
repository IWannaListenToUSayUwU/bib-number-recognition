r"""R11 過線標註工具（本機網頁伺服器）。只用 Python 標準函式庫＋OpenCV，不需要 GPU、不連網路。
用法（在專案根目錄）：python 30_實驗/R11_過線正確答案/r11_tool.py   然後用瀏覽器開 http://localhost:8765
需要先跑過 r11_prepare.py（產生候選事件與光帶圖）。
標註會自動存到各片段的標註資料夾 annot_<片段>.json（C、D：R11_過線正確答案/標註；tpe2：R12_第二機位/標註），每次存檔前把舊檔留成 .bak。"""
import json, os, sys, threading, time
from collections import OrderedDict
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import cv2, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__)); ANN = os.path.join(HERE, '標註'); WEB = os.path.join(HERE, 'web')
# 片段登記：片段 → (標註資料夾, 計時線)。R12 第二機位的片段在候選檔產生後才會出現在選單。
R12ANN = os.path.join(ROOT, '30_實驗', 'R12_第二機位', '標註')
REG = [('tpe_C_600', ANN, 'LINE_tpe_v1'), ('tpe_D_1800', ANN, 'LINE_tpe_v1')]
REG += [(c, R12ANN, 'LINE_tpe2_v1') for c in ('tpe2_A_3000', 'tpe2_B_4200', 'tpe2_C_5400')
        if os.path.exists(os.path.join(R12ANN, f'candidates_{c}.json'))]
CLIPS = [r[0] for r in REG]; ANNOF = {r[0]: r[1] for r in REG}; LINEOF = {r[0]: r[2] for r in REG}
LINES = {n: json.load(open(os.path.join(ROOT, '10_程式', 'work', n + '.json'), encoding='utf-8')) for n in set(LINEOF.values())}
# 畫面裁切：人物（寬、高、中心在腳點上方幾像素）與「前 2 秒全景」的範圍（中心 x、y、寬、高）
VIEW = {'LINE_tpe_v1': dict(pw=360, ph=420, pdy=150, wide=[850, 640, 1300, 720]),
        'LINE_tpe2_v1': dict(pw=440, ph=640, pdy=270, wide=[1150, 640, 1500, 840])}
OFFICIAL = os.path.join(ROOT, '30_實驗', 'R12_第二機位', '官方成績', '官方成績_片段時間窗.json')


def official_rows(clip):
    """官方成績（只在核對清單用）：回傳 [{bib, t}]，t＝官方槍聲時間換成片段秒數。"""
    o = load_json(OFFICIAL)
    if not o or clip not in o['clips']: return None
    c = o['clips'][clip]; t0 = c['clock_at_t0']
    return [dict(bib=r['bib'], t=round(sum(int(x) * k for x, k in zip(r['time'].split(':'), (3600, 60, 1))) - t0, 2)) for r in c['rows']]
OFFCHK = os.path.join(HERE, '分析', '官方名單核對.json')


def official_check_rows(clip):
    """C、D（轉角機位，沒有時鐘）：r11_official_check.py 用估計時間差做的官方名單核對，只回傳「可能看錯／可能漏標」的項目。
    partial 不回傳名單上的候選號碼（規則：不能照名單把 ? 補上），只在「名單中完全找不到符合的號碼」時提醒。"""
    o = load_json(OFFCHK)
    if not o: return None
    out = []
    for r in o['rows']:
        if r['clip'] != clip: continue
        if r['status'] == 'sure': out.append(dict(bib=r['bib'], t=r['t'], msg=r['check'] + (('：' + r['detail']) if r['detail'] else ''), hint='可能看錯，請再看一次'))
        elif r['status'] == 'partial' and r['check'].endswith('：0 個'):
            out.append(dict(bib=r['bib'], t=r['t'], msg='名單中找不到符合這個樣式、時間又對得上的號碼', hint='看得清的那幾碼可能看錯，請再看一次'))
        elif r['status'] == 'old_ai_sure' and '時間對得上' in r['check']:
            out.append(dict(bib=r['bib'], t=r['t'], msg='舊 AI 答案有、官方名單時間也對得上，人工答案沒有', hint='可能漏標，或已標成別的號碼／partial；請在光帶圖附近找'))
    return out
PORT = int(os.environ.get('R11_PORT', '8765'))


class Frames:
    """讀片段的某一格；同一片段共用一個 VideoCapture，最近用過的格數放快取。"""
    def __init__(self, n_cache=40):
        self.caps = {}; self.last = {}; self.cache = OrderedDict(); self.n = n_cache; self.lock = threading.Lock()

    def get(self, clip, idx):
        key = (clip, idx)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key); return self.cache[key]
            cap = self.caps.get(clip)
            if cap is None:
                cap = self.caps[clip] = cv2.VideoCapture(os.path.join(ROOT, '20_測試基準', 'clips', clip + '.mp4')); self.last[clip] = -10
            if not (0 < idx - self.last[clip] <= 8):
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx); self.last[clip] = idx - 1
            f = None
            while self.last[clip] < idx:
                ok, f = cap.read()
                if not ok: return None
                self.last[clip] += 1
                self.cache[(clip, self.last[clip])] = f
                while len(self.cache) > self.n: self.cache.popitem(last=False)
            return f


FR = Frames()


def crop(clip, idx, cx, cy, w, h, scale=1.0, line=True, boxes=()):
    f = FR.get(clip, idx)
    if f is None: return None
    g = f.copy(); L = LINES[LINEOF[clip]]
    if line: cv2.line(g, tuple(L['p1']), tuple(L['p2']), (255, 0, 255), 2)
    for b in boxes: cv2.rectangle(g, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (0, 255, 255), 2)
    H, W = g.shape[:2]; w = int(min(w, W)); h = int(min(h, H))
    x0 = int(min(max(cx - w / 2, 0), W - w)); y0 = int(min(max(cy - h / 2, 0), H - h))
    c = g[y0:y0 + h, x0:x0 + w]
    if scale != 1.0: c = cv2.resize(c, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    return cv2.imencode('.jpg', c, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()


def load_json(p, default=None):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


SAVE_LOCK = threading.Lock()


def save_annot(clip, data):
    """存檔前檢查：網頁載入時看到的版本（base_updated）必須和檔案目前的版本相同，
    否則代表別的視窗／分頁已經存過，拒絕存檔，避免舊畫面把新標註蓋掉。"""
    p = os.path.join(ANNOF[clip], f'annot_{clip}.json'); tmp = p + '.tmp'
    cur = (load_json(p) or {}).get('updated')
    if 'base_updated' in data and data.pop('base_updated') != cur:
        return None
    data['clip'] = clip; data['updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(tmp, 'w', encoding='utf-8') as fo: json.dump(data, fo, ensure_ascii=False, indent=1)
    if os.path.exists(p): os.replace(p, p + '.bak')
    os.replace(tmp, p)
    return data['updated']


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def js(self, obj, code=200): self.send(code, json.dumps(obj, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ('/', '/index.html'):
                return self.send(200, open(os.path.join(WEB, 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
            if u.path == '/api/clips':
                return self.js([dict(clip=c, slit=load_json(os.path.join(ANNOF[c], f'slit_{c}.json'))) for c in CLIPS])
            clip = q.get('clip')
            if clip not in CLIPS: return self.js({'error': 'bad clip'}, 400)
            if u.path == '/api/data':
                A = ANNOF[clip]
                return self.js(dict(candidates=load_json(os.path.join(A, f'candidates_{clip}.json')),
                                    annot=load_json(os.path.join(A, f'annot_{clip}.json')),
                                    slit=load_json(os.path.join(A, f'slit_{clip}.json')), line=LINES[LINEOF[clip]],
                                    line_name=LINEOF[clip], view=VIEW[LINEOF[clip]], official=official_rows(clip), official_check=official_check_rows(clip),
                                    old_gt=load_json(os.path.join(ROOT, '20_測試基準', 'gt', clip + '.json'))))
            if u.path == '/api/slit':
                return self.send(200, open(os.path.join(ANNOF[clip], f'slit_{clip}.png'), 'rb').read(), 'image/png')
            if u.path == '/api/frame':
                boxes = [list(map(float, b.split(','))) for b in q.get('boxes', '').split(';') if b.count(',') == 3]
                img = crop(clip, int(q['f']), float(q['cx']), float(q['cy']), float(q.get('w', 360)), float(q.get('h', 420)),
                           float(q.get('scale', 1)), q.get('line', '1') == '1', boxes)
                return self.send(200, img, 'image/jpeg') if img else self.js({'error': 'frame'}, 404)
            return self.js({'error': 'not found'}, 404)
        except Exception as e:
            return self.js({'error': repr(e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != '/api/save': return self.js({'error': 'not found'}, 404)
        n = int(self.headers.get('Content-Length', 0)); data = json.loads(self.rfile.read(n).decode('utf-8'))
        clip = data.get('clip')
        if clip not in CLIPS: return self.js({'error': 'bad clip'}, 400)
        with SAVE_LOCK:
            upd = save_annot(clip, data)
        if upd is None:
            return self.js({'error': '檔案已在別的視窗或分頁更新過，為避免覆蓋，這次沒有存檔。請重新整理頁面（F5）再繼續。'}, 409)
        return self.js({'ok': True, 'saved': upd[-8:], 'updated': upd})


if __name__ == '__main__':
    for c in CLIPS:
        if not os.path.exists(os.path.join(ANNOF[c], f'candidates_{c}.json')): sys.exit('請先執行 r11_prepare.py')
    print(f'R11 過線標註工具：http://localhost:{PORT}  （關閉視窗或按 Ctrl+C 結束；標註存在 {ANN}）', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

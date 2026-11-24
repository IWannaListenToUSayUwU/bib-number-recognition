r"""R15 多人標註網站：讓其他人透過 Tailscale 一起標註。只用 Python 標準函式庫＋OpenCV，不需要 GPU。
用法（在專案根目錄）：python 30_實驗/R15_多人標註/r15_server.py [--host 100.65.210.69] [--port 8780]
  只綁 Tailscale 位址。這台電腦的乙太網路是校網公開 IP，**不可以綁 0.0.0.0**（否則整個校網都連得到）。
三種工作（規則寫在 R15 計畫.md）：
  1. 過線標註：tpe2_B_4200、tpe2_C_5400（第二機位完整標註；和 R11 同一套規則）
  2. 獨立重標：tpe_C_600、tpe_D_1800（不顯示第一位標註者的答案，也不顯示由他的答案算出的官方名單核對）
  3. 抽樣讀號：抽樣窗.json 的 50 個時間窗；網頁只給時間，不給號碼（答案只在 r15_sample_eval.py 評分時用）
每位標註者分開存檔：30_實驗/R15_多人標註/標註/<名字>/annot_<片段>.json、sample.json（存檔前舊檔留 .bak；別的分頁存過就拒絕存檔）。
重用 R11 標註工具的讀影格、裁切、官方成績換算（r11_tool.py 不改）。"""
import json, os, re, sys, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '30_實驗', 'R11_過線正確答案'))
import r11_tool as T  # noqa: E402

WEB = os.path.join(HERE, 'web'); STORE = os.path.join(HERE, '標註')
SAMPLE = json.load(open(os.path.join(HERE, '抽樣窗.json'), encoding='utf-8'))
LABEL_TASKS = [  # (片段, 工作名稱)
    ('tpe2_B_4200', '過線標註'), ('tpe2_C_5400', '過線標註'),
    ('tpe_C_600', '獨立重標'), ('tpe_D_1800', '獨立重標'),
]
LABEL_CLIPS = [c for c, _ in LABEL_TASKS]
SAMPLE_CLIPS = sorted({w['clip'] for w in SAMPLE['windows']})
for c in SAMPLE_CLIPS:                       # 抽樣用的片段不在 R11 工具的登記表，補上計時線（畫線用）
    T.LINEOF.setdefault(c, 'LINE_tpe2_v1')
if 'LINE_tpe2_v1' not in T.LINES:
    T.LINES['LINE_tpe2_v1'] = json.load(open(os.path.join(ROOT, '10_程式', 'work', 'LINE_tpe2_v1.json'), encoding='utf-8'))
T.FR = T.Frames(n_cache=60)                  # 多人同時看，快取多放一點（每格約 6 MB）
ALL_CLIPS = set(LABEL_CLIPS) | set(SAMPLE_CLIPS)
for c in LABEL_CLIPS:
    if c not in T.ANNOF: sys.exit(f'{c} 還沒有候選事件（先跑 r11_prepare.py／r12_prepare.py）')
NAME_RE = re.compile(r'^[0-9A-Za-z_\-一-鿿]{1,20}$')
LOCK = threading.Lock()


def mine(who, name):
    return os.path.join(STORE, who, name)


def save_json(p, data):
    """存檔：網頁載入時看到的版本（base_updated）要和檔案目前的版本一樣，不一樣代表別的分頁存過 → 拒絕。"""
    cur = (T.load_json(p) or {}).get('updated')
    if data.pop('base_updated', None) != cur: return None
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data['updated'] = time.strftime('%Y-%m-%d %H:%M:%S'); tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fo: json.dump(data, fo, ensure_ascii=False, indent=1)
    if os.path.exists(p): os.replace(p, p + '.bak')
    os.replace(tmp, p)
    return data['updated']


def progress(who):
    out = {}
    for c in LABEL_CLIPS:
        a = T.load_json(mine(who, f'annot_{c}.json')) or {}
        n = len(T.load_json(os.path.join(T.ANNOF[c], f'candidates_{c}.json'))['items'])
        out[c] = dict(done=sum(1 for i in a.get('items', []) if i.get('reviewed') and i.get('sys_id') is not None), total=n,
                      added=sum(1 for i in a.get('items', []) if i.get('sys_id') is None), slit=bool(a.get('slit_checked')))
    s = T.load_json(mine(who, 'sample.json')) or {}
    out['sample'] = dict(done=len(s.get('answers', {})), total=len(SAMPLE['windows']))
    return out


def clampf(q, k, lo, hi, d):
    try: return min(max(float(q.get(k, d)), lo), hi)
    except ValueError: return d


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def js(self, obj, code=200): self.send(code, json.dumps(obj, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def page(self, name): self.send(200, open(os.path.join(WEB, name), 'rb').read(), 'text/html; charset=utf-8')

    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ('/', '/index.html'): return self.page('index.html')
            if u.path == '/label': return self.page('label.html')
            if u.path == '/sample': return self.page('sample.html')
            if u.path == '/api/tasks':
                return self.js(dict(label=[dict(clip=c, task=t) for c, t in LABEL_TASKS], sample_total=len(SAMPLE['windows'])))
            if u.path == '/api/progress':
                whos = sorted(d for d in os.listdir(STORE) if os.path.isdir(os.path.join(STORE, d))) if os.path.isdir(STORE) else []
                return self.js({w: progress(w) for w in whos if NAME_RE.match(w)})
            if u.path in ('/api/frame', '/api/slit'):
                clip = q.get('clip')
                if clip not in ALL_CLIPS: return self.js({'error': 'bad clip'}, 400)
                if u.path == '/api/slit':
                    if clip not in LABEL_CLIPS: return self.js({'error': 'bad clip'}, 400)
                    return self.send(200, open(os.path.join(T.ANNOF[clip], f'slit_{clip}.png'), 'rb').read(), 'image/png')
                boxes = [list(map(float, b.split(','))) for b in q.get('boxes', '').split(';') if b.count(',') == 3][:4]
                img = T.crop(clip, int(clampf(q, 'f', 0, 1e6, 0)), clampf(q, 'cx', 0, 1920, 960), clampf(q, 'cy', 0, 1080, 540),
                             clampf(q, 'w', 16, 1920, 360), clampf(q, 'h', 16, 1080, 420), clampf(q, 'scale', 0.05, 3, 1),
                             q.get('line', '1') == '1', boxes)
                return self.send(200, img, 'image/jpeg') if img else self.js({'error': 'frame'}, 404)
            who = q.get('who', '')
            if not NAME_RE.match(who): return self.js({'error': '名字只能用中英文、數字、- 和 _（最多 20 字）'}, 400)
            if u.path == '/api/data':
                clip = q.get('clip')
                if clip not in LABEL_CLIPS: return self.js({'error': 'bad clip'}, 400)
                A = T.ANNOF[clip]
                return self.js(dict(candidates=T.load_json(os.path.join(A, f'candidates_{clip}.json')),
                                    annot=T.load_json(mine(who, f'annot_{clip}.json')),
                                    slit=T.load_json(os.path.join(A, f'slit_{clip}.json')), line=T.LINES[T.LINEOF[clip]],
                                    line_name=T.LINEOF[clip], view=T.VIEW[T.LINEOF[clip]], official=T.official_rows(clip),
                                    official_check=None,   # 由第一位標註者的答案算出 → 不給（獨立重標）
                                    old_gt=T.load_json(os.path.join(ROOT, '20_測試基準', 'gt', clip + '.json'))))
            if u.path == '/api/sample':
                return self.js(dict(windows=SAMPLE['windows'], half=SAMPLE['half_window_s'], fps=30,
                                    view=T.VIEW['LINE_tpe2_v1'], mine=T.load_json(mine(who, 'sample.json'))))
            return self.js({'error': 'not found'}, 404)
        except Exception as e:
            return self.js({'error': repr(e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get('Content-Length', 0))
            if n > 2_000_000: return self.js({'error': 'too large'}, 413)
            data = json.loads(self.rfile.read(n).decode('utf-8')); who = data.get('who', '')
            if not NAME_RE.match(who): return self.js({'error': '名字不合規則'}, 400)
            if u.path == '/api/save':
                clip = data.get('clip')
                if clip not in LABEL_CLIPS: return self.js({'error': 'bad clip'}, 400)
                data['annotator'] = who; p = mine(who, f'annot_{clip}.json')
            elif u.path == '/api/sample_save':
                data = dict(who=who, annotator=who, base_updated=data.get('base_updated'), answers=data.get('answers') or {})
                p = mine(who, 'sample.json')
            else:
                return self.js({'error': 'not found'}, 404)
            with LOCK: upd = save_json(p, data)
            if upd is None:
                return self.js({'error': '這份標註已在別的分頁或電腦存過，為避免覆蓋，這次沒有存檔。請重新整理頁面（F5）再繼續。'}, 409)
            return self.js({'ok': True, 'saved': upd[-8:], 'updated': upd})
        except Exception as e:
            return self.js({'error': repr(e)}, 500)


if __name__ == '__main__':
    a = sys.argv; host = a[a.index('--host') + 1] if '--host' in a else '100.65.210.69'
    port = int(a[a.index('--port') + 1]) if '--port' in a else 8780
    if host in ('0.0.0.0', '', '::'): sys.exit('不可以綁 0.0.0.0：這台電腦的乙太網路是公開 IP。請用 Tailscale 位址。')
    os.makedirs(STORE, exist_ok=True)
    try: srv = ThreadingHTTPServer((host, port), H)
    except OSError as e: sys.exit(f'開不起來（{e}）。Tailscale 有開嗎？位址 {host} 是不是這台電腦的？埠 {port} 是不是已經在用？')
    print(f'R15 多人標註網站：http://{host}:{port}  （只有 Tailscale 網路內的人連得到；關掉這個視窗就停止）', flush=True)
    srv.serve_forever()

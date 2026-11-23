"""三層設定（2026-11-23 起）：全域（演算法）＋比賽（號碼位數、名單、號碼布顏色）＋機位（計時線、只讀線附近範圍、時鐘位置）。
說明見 10_程式/config/README.md。

  全域  10_程式/config/global/GLOBAL_vX.json   定版後不改；只能用分數調的參數都在這裡，而且只有一套
  比賽  10_程式/config/race/<比賽>.json         賽前從主辦單位拿到的事實資料，同一場比賽的所有機位共用
  機位  10_程式/config/camera/<機位>.json       架好攝影機後點選的幾何資料，不需要正確答案

片段屬於哪個機位、哪場比賽，記在 20_測試基準/MANIFEST.json 的 camera、race 欄位。
用法：
  from settings import for_clip, extract_kwargs
  S = for_clip('GLOBAL_v3_0', 'tpe_C_600')        # 合併後的設定（含三個檔案的 sha256）
  kw = extract_kwargs(S)                            # 給抽取程式（extract8.process）的參數
"""
import hashlib, json, os

SRC = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.dirname(SRC)                         # 10_程式
ROOT = os.path.dirname(PROG)                        # 專案根目錄
CONF = os.path.join(PROG, 'config')
MANIFEST = os.path.join(ROOT, '20_測試基準', 'MANIFEST.json')
SCHEMA = 'layered_v1'
DECISION_MODES = ('cons_color', 'cons', 'pre_keep', 'len5', 'v22')


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def _load(kind, name):
    p = os.path.join(CONF, kind, name.removesuffix('.json') + '.json')
    if not os.path.exists(p): raise FileNotFoundError(f'找不到{kind}設定：{p}')
    d = json.load(open(p, encoding='utf-8'))
    if d.get('schema') != SCHEMA: raise ValueError(f'{p} 不是 {SCHEMA} 格式')
    return d, p


def is_layered(cfgname):
    return os.path.exists(os.path.join(CONF, 'global', cfgname.removesuffix('.json') + '.json'))


def load_global(name):
    g, p = _load('global', name)
    for k in ('extract', 'aggregate', 'crossing', 'decision'):
        if k not in g: raise ValueError(f'{p} 缺少 {k}')
    if g['decision'].get('mode') not in DECISION_MODES: raise ValueError(f'{p} decision.mode 必須是 {DECISION_MODES}')
    return g, p


def load_race(name):
    r, p = _load('race', name)
    bibs = None
    if r.get('bib_list'):
        bp = os.path.join(CONF, 'race', r['bib_list'])
        bibs = {l.strip() for l in open(bp, encoding='utf-8') if l.strip()}
        if r.get('bib_len') and any(len(b) != r['bib_len'] for b in bibs): raise ValueError(f'{bp} 有號碼長度不是 {r["bib_len"]}')
        r = dict(r, _bib_list_path=bp, _bib_list_sha256=_sha(bp))
    return r, p, bibs


def load_camera(name):
    c, p = _load('camera', name)
    if c.get('line') and not all(k in c['line'] for k in ('p1', 'p2', 'upstream')): raise ValueError(f'{p} line 要有 p1、p2、upstream')
    return c, p


def clip_info(clip):
    m = json.load(open(MANIFEST, encoding='utf-8'))
    if clip not in m['clips']: raise KeyError(f'{clip} 不在 MANIFEST')
    return m['clips'][clip]


def effective_mode(G, race, bibs):
    """依比賽層有哪些資料，決定實際用的定案模式（全域 decision.mode → fallback 依序退回）。"""
    order = [G['decision']['mode']] + list(G['decision'].get('fallback', [])) + ['v22']
    for m in order:
        if m == 'cons_color' and bibs and race.get('bib_colors'): return m
        if m in ('cons', 'pre_keep') and bibs: return m
        if m == 'len5' and race.get('bib_len'): return m
        if m == 'v22': return m
    return 'v22'


def for_clip(global_name, clip):
    G, gp = load_global(global_name); info = clip_info(clip)
    if not info.get('camera') or not info.get('race'): raise ValueError(f'MANIFEST 中 {clip} 沒有 camera／race 欄位')
    R, rp, bibs = load_race(info['race']); C, cp = load_camera(info['camera'])
    mode = effective_mode(G, R, bibs)
    sha = {'global': _sha(gp), 'race': _sha(rp), 'camera': _sha(cp)}
    if R.get('_bib_list_sha256'): sha['bib_list'] = R['_bib_list_sha256']
    return dict(clip=clip, global_name=os.path.basename(gp)[:-5], race_name=info['race'], camera_name=info['camera'],
                G=G, race=R, camera=C, bibs=bibs, mode=mode, sha256=sha, can_cross=bool(C.get('line')))


def extract_kwargs(S):
    """全域 extract 區塊（去掉 script、fps、use_zone）＋機位的「只讀線附近」範圍。"""
    E = dict(S['G']['extract']); E.pop('script', None); E.pop('fps', None); use_zone = E.pop('use_zone', False)
    C = S['camera']
    if use_zone and C.get('line') and C.get('zone'):
        E['zone_line'] = {k: C['line'][k] for k in ('p1', 'p2', 'upstream')}
        E['zone_up'] = float(C['zone']['up_px']); E['zone_down'] = float(C['zone']['down_px'])
    return E


def summary(S):
    """寫進 run_info.json 的摘要。"""
    return dict(global_name=S['global_name'], race=S['race_name'], camera=S['camera_name'], decision_mode=S['mode'],
                can_cross=S['can_cross'], sha256=S['sha256'])

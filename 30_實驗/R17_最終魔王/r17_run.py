r"""R17 最終魔王：在「新屋魚米之鄉馬拉松終點」影片的指定時段跑完整流程（抽取 → 過線事件），沿用三層設定。
用法（專案根目錄，bibread 環境）：
  python 30_實驗/R17_最終魔王/r17_run.py <標籤> <全域設定> <時段> [--gpu]
    全域設定：config/global 裡的名稱（例 GLOBAL_v3_0），或 R17 資料夾內的 json 路徑（開發中的變體，不放進 config/global）
    時段：test | dev | all | "t0-t1,t0-t1"（秒）
    --gpu：文字辨識改用 GPU（onnxruntime-gpu 1.26，另裝在 C:\Users\ShiLaCow\bibread_ortgpu\ort126；R16）
輸出：30_實驗/R17_最終魔王/out/<標籤>/seg_<t0>/raw.jsonl、events.csv、stats.json，以及 run_info.json。
比賽層 xinwu2026、機位層 xinwu_finish 固定（config/race、config/camera）。"""
import sys, os, json, time, importlib, inspect
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
VIDEO = os.path.join(ROOT, '00_原始素材', '最終魔王', '2026 10 04 2026新屋魚米之鄉馬拉松終點 GP020205.mp4')
ORT126 = r'C:\Users\ShiLaCow\bibread_ortgpu\ort126'
# 測試段（定版前只跑一次；開發不看）與開發段：每段 60 秒，影片長 1063 秒
TEST = [(180, 240), (420, 480), (660, 720), (900, 960)]
DEV = [(t, t + 60) for t in range(0, 1020, 60) if (t, t + 60) not in TEST] + [(1020, 1062)]
args = [a for a in sys.argv[1:] if not a.startswith('--')]; GPU = '--gpu' in sys.argv
if len(args) < 3: sys.exit(__doc__)
tag, gname, segspec = args[:3]
if GPU: sys.path.insert(0, ORT126)
import torch  # noqa: E402  先載入 CUDA DLL（GPU 版 ORT 借用）
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src'))
if GPU:
    import rapidocr_onnxruntime as _R
    _orig = _R.RapidOCR
    _R.RapidOCR = lambda **kw: _orig(**kw, det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
import settings, bibrules  # noqa: E402
from videoio import probe, frames  # noqa: E402


def segments(spec):
    if spec == 'test': return TEST
    if spec == 'dev': return DEV
    if spec == 'all': return sorted(TEST + DEV)
    return [tuple(float(x) for x in s.split('-')) for s in spec.split(',')]


def load_global(g):
    if g.endswith('.json'):
        p = g if os.path.isabs(g) else os.path.join(HERE, g)
        return json.load(open(p, encoding='utf-8')), p
    return settings.load_global(g)


def main():
    G, gp = load_global(gname)
    R, rp, bibs = settings.load_race('xinwu2026'); C, cp = settings.load_camera('xinwu_finish')
    mode = settings.effective_mode(G, R, bibs); G = settings.apply_camera(G, C)
    S = dict(clip='xinwu', global_name=os.path.basename(gp)[:-5], race_name='xinwu2026', camera_name='xinwu_finish',
             G=G, race=R, camera=C, bibs=bibs, mode=mode, can_cross=True)
    E = G['extract']; script = os.path.splitext(os.path.basename(E['script']))[0]; fps = E['fps']
    process = importlib.import_module(script).process
    ok = set(inspect.signature(process).parameters)
    kw = {k: v for k, v in settings.extract_kwargs(S).items() if k in ok}
    bad = set(settings.extract_kwargs(S)) - ok
    if bad: sys.exit(f'設定的抽取參數 {sorted(bad)} 不被 {script}.process 接受')
    out = os.path.join(HERE, 'out', tag); os.makedirs(out, exist_ok=True)
    W, H, dur = probe(VIDEO)
    segs = segments(segspec)
    info = dict(tag=tag, global_file=os.path.relpath(gp, ROOT), mode=mode, gpu_ocr=GPU, gpu=torch.cuda.get_device_name(0),
                extract=script, extract_kwargs=kw, fps=fps, segments=segs, start=time.strftime('%Y-%m-%d %H:%M:%S'))
    json.dump(info, open(os.path.join(out, 'run_info.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.environ.setdefault('BIB_OCR_THREADS', '8')
    for t0, t1 in segs:
        od = os.path.join(out, f'seg_{int(t0):04d}'); os.makedirs(od, exist_ok=True)
        if os.path.exists(os.path.join(od, 'DONE.txt')): continue
        st = {}; a = time.time()
        with open(os.path.join(od, 'raw.jsonl'), 'w', encoding='utf-8') as fo:
            for r in process(frames(VIDEO, t0, min(t1, dur - 0.05), fps, W, H), fps=fps, stats=st, **kw):
                fo.write(json.dumps(r) + '\n')
        ext = time.time() - a
        ev = bibrules.events(os.path.join(od, 'raw.jsonl'), S, video_path=VIDEO)
        bibrules.write_events(ev, os.path.join(od, 'events.csv'))
        json.dump(dict(stats=st, extract_sec=round(ext, 1), seg=[t0, t1], n_events=len(ev), n_bib=sum(1 for e in ev if e['bib'])),
                  open(os.path.join(od, 'stats.json'), 'w'))
        open(os.path.join(od, 'DONE.txt'), 'w').close()
        print(time.strftime('%H:%M:%S'), f'seg {t0}-{t1}: 抽取 {ext:.0f}s，過線 {len(ev)}（有號碼 {sum(1 for e in ev if e["bib"])}） {st}', flush=True)
    print('完成', tag, flush=True)


if __name__ == '__main__':
    main()

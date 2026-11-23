r"""30_實驗 通用執行程式（規格.md 第 3 節）。不要另外複製 run_clip.py，所有實驗都走這支。
用法：python run_experiment.py <實驗名> <設定檔名> <片段1> [片段2 ...] [--novideo]
  例：python run_experiment.py R08_換人偵測 FROZEN_CONFIG_v2_4 tpe_C_600 tpe_D_1800
強制檢查（任何一項不過就停，不會產生半套結果）：
  1. 一定要有 CUDA GPU（沒有就停，不准退回 CPU）
  2. 片段必須在 20_測試基準\clips，且 sha256 與 MANIFEST.json 一致（確保每次測的是同一份原始資料）
  3. 設定檔必須在 10_程式\work
輸出一律在 30_實驗\<實驗名>\out\<設定檔名>\<片段>\ ：raw.jsonl、result.csv、stats.json、(標註影片)
並寫 run_info.json（設定檔與程式的 sha256、GPU 名稱、時間），跑完自動用 20_測試基準\score.py 評分 → score.json
三層設定（2026-11-23 起，見 10_程式\config\README.md）：設定檔名是 10_程式\config\global\ 下的 GLOBAL_vX 時，
  每個片段依 MANIFEST 的 camera、race 合併機位層、比賽層（只讀線附近的範圍、號碼名單、號碼布顏色），
  抽取完另外寫 events.csv（過線事件＋號碼定案規則），並用 score_v2 評分 → score_v2.json。舊的 FROZEN_CONFIG_* 照舊。"""
import csv, hashlib, inspect, json, os, sys, time, importlib
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, '10_程式', 'src'); CFGDIR = os.path.join(ROOT, '10_程式', 'work'); BENCH = os.path.join(ROOT, '20_測試基準')
sys.path.insert(0, SRC); sys.path.insert(0, BENCH)

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def die(msg):
    print('[停止] ' + msg, flush=True); sys.exit(2)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]; novideo = '--novideo' in sys.argv
    if len(args) < 3: die('用法：python run_experiment.py <實驗名> <設定檔名> <片段...>')
    exp, cfgname, clips = args[0], args[1].removesuffix('.json'), args[2:]
    import torch
    if not torch.cuda.is_available(): die('偵測不到 CUDA GPU。請確認是在 bibread 環境執行，且 torch 是 CUDA 版。不准用 CPU 跑。')
    gpu = torch.cuda.get_device_name(0)
    import settings
    layered = settings.is_layered(cfgname)
    cfgp = os.path.join(settings.CONF, 'global', cfgname + '.json') if layered else os.path.join(CFGDIR, cfgname + '.json')
    if not os.path.exists(cfgp): die(f'找不到設定檔 {cfgp}')
    CFG = json.load(open(cfgp, encoding='utf-8'))
    LAY = {}
    if layered:
        for c in clips:
            try: LAY[c] = settings.for_clip(cfgname, c)
            except Exception as e: die(f'三層設定合併失敗（{c}）：{e}')
    man = json.load(open(os.path.join(BENCH, 'MANIFEST.json'), encoding='utf-8'))
    for c in clips:
        if c not in man['clips']: die(f'{c} 不在 20_測試基準\\MANIFEST.json')
        vp = os.path.join(BENCH, 'clips', c + '.mp4')
        if not os.path.exists(vp) or sha(vp) != man['clips'][c]['sha256']: die(f'{c}.mp4 不存在或內容與 MANIFEST 不符（原始資料被改過）')
    E = dict(CFG['extract']); script = os.path.splitext(os.path.basename(E.pop('script')))[0]; fps = E.pop('fps')
    process = importlib.import_module(script).process
    ok = set(inspect.signature(process).parameters); ex = {k: v for k, v in E.items() if k in ok}
    AG = CFG['aggregate']
    if 'size_ref' in AG: from aggregate3 import aggregate3 as agg; aggname = 'aggregate3'
    else: from aggregate2 import aggregate2 as agg; aggname = 'aggregate2'
    outroot = os.path.join(HERE, exp, 'out', cfgname); os.makedirs(outroot, exist_ok=True)
    logp = os.path.join(outroot, 'log.txt')
    def log(m):
        line = time.strftime('%Y-%m-%d %H:%M:%S ') + m; print(line, flush=True)
        open(logp, 'a', encoding='utf-8').write(line + '\n')
    info = dict(exp=exp, config=cfgname, config_sha256=sha(cfgp), gpu=gpu, start=time.strftime('%Y-%m-%d %H:%M:%S'),
                extract=script, aggregate=aggname, src_sha256={f: sha(os.path.join(SRC, f + '.py')) for f in {script, aggname, 'feat6', 'extract5', 'extract4', 'videoio'} if os.path.exists(os.path.join(SRC, f + '.py'))},
                clips={c: man['clips'][c]['sha256'] for c in clips}, extract_args=ex, fps=fps)
    if layered:
        info['layered'] = {c: settings.summary(S) for c, S in LAY.items()}
        info['extract_args'] = {c: {k: v for k, v in settings.extract_kwargs(S).items() if k in ok} for c, S in LAY.items()}
        for f in ('settings', 'ocrgate', 'bibrules', 'crossing'):
            info['src_sha256'][f] = sha(os.path.join(SRC, f + '.py'))
    json.dump(info, open(os.path.join(outroot, 'run_info.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import cv2
    from videoio import probe, frames
    os.environ.setdefault('BIB_OCR_THREADS', '8')
    for c in clips:
        vp = os.path.join(BENCH, 'clips', c + '.mp4'); od = os.path.join(outroot, c); os.makedirs(od, exist_ok=True)
        W, H, dur = probe(vp); st = {}; t0 = time.time(); last = t0
        log(f'[{c}] 開始 GPU={gpu} {script} fps={fps}')
        with open(os.path.join(od, 'raw.jsonl'), 'w', encoding='utf-8') as fo:
            exc = ex
            if layered:
                kwl = settings.extract_kwargs(LAY[c]); bad = set(kwl) - ok
                if bad: die(f'{c}：設定的抽取參數 {sorted(bad)} 不被 {script}.process 接受（打錯字或抽取程式不對）')
                exc = {k: v for k, v in kwl.items() if k in ok}
                fr = LAY[c]['camera'].get('frame')
                if fr and (fr[0], fr[1]) != (W, H): die(f'{c} 畫面 {W}x{H} 和機位層 {LAY[c]["camera_name"]} 的 {fr} 不同')
            for r in process(frames(vp, 0.0, dur, fps, W, H), fps=fps, stats=st, **exc):
                fo.write(json.dumps(r) + '\n')
                if time.time() - last > 60: last = time.time(); log(f'[{c}]   進度 {r["t"]:.1f}/{dur:.0f}s {st}')
        t_ext = time.time() - t0
        rows, boxes = [], defaultdict(list)
        for l in open(os.path.join(od, 'raw.jsonl'), encoding='utf-8'):
            r = json.loads(l); boxes[r['tid']].append((r['t'], r['pbox']))
            for txt, sc, bb in (r.get('texts') or []):
                rows.append(dict(t=r['t'], tid=r['tid'], bh=bb[3] - bb[1], bbox=bb, txt=txt, sc=sc))
        preds = agg(rows, **AG, frame_w=W) if aggname == 'aggregate3' else agg(rows, **AG)
        with open(os.path.join(od, 'result.csv'), 'w', newline='', encoding='utf-8') as fo:
            wr = csv.writer(fo); wr.writerow(['bib', 'time_s', 'first_s', 'last_s', 'score', 'tids'])
            for p in sorted(preds, key=lambda x: x['t']):
                wr.writerow([p['bib'], f'{p["t"]:.3f}', f'{p["t0"]:.3f}', f'{p["t1"]:.3f}', f'{p["score"]:.3f}', ';'.join(str(x) for x in sorted(p['tids'], key=str))])
        json.dump(dict(stats=st, extract_sec=round(t_ext)), open(os.path.join(od, 'stats.json'), 'w'))
        log(f'[{c}] 抽取 {t_ext:.0f}s，定案 {len(preds)} 個號碼')
        if layered and LAY[c]['can_cross']:
            import bibrules
            t1 = time.time()
            ev = bibrules.events(os.path.join(od, 'raw.jsonl'), LAY[c], video_path=vp)
            bibrules.write_events(ev, os.path.join(od, 'events.csv'))
            log(f'[{c}] 過線事件 {len(ev)} 個（有號碼 {sum(1 for e in ev if e["bib"])}；定案規則 {LAY[c]["mode"]}；{time.time() - t1:.0f}s）')
        if not novideo:
            label = {tid: (p['bib'], p['t0'] - 1, p['t1'] + 1) for p in preds for tid in p['tids'] if isinstance(tid, int)}
            at = defaultdict(list)
            for tid, lst in boxes.items():
                for t, b in lst: at[round(t, 3)].append((tid, b))
            vw = cv2.VideoWriter(os.path.join(od, f'{c}_標註.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
            for t, f in frames(vp, 0.0, dur, fps, W, H):
                g = f.copy()
                for tid, (x1, y1, x2, y2) in at.get(round(t, 3), []):
                    L = label.get(tid)
                    if L and L[1] <= t <= L[2]:
                        cv2.rectangle(g, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(g, L[0], (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5)
                        cv2.putText(g, L[0], (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
                    else:
                        cv2.rectangle(g, (x1, y1), (x2, y2), (160, 160, 160), 1)
                vw.write(g)
            vw.release(); log(f'[{c}] 標註影片完成')
        open(os.path.join(od, 'DONE.txt'), 'w').close()
    import score
    sys.argv = ['score.py', outroot] + clips; score.main()
    log('評分完成 → score.json')
    if layered:
        import score_v2
        sys.argv = ['score_v2.py', outroot] + [c for c in clips if LAY[c]['can_cross']]; score_v2.main()
        log('過線評分完成 → score_v2.json（只算有過線正確答案的片段）')

if __name__ == '__main__':
    main()

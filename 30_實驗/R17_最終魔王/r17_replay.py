r"""R17 重播：拿某次抽取的 raw.jsonl，換一份全域設定（只有過線 crossing／定案 decision／aggregate 有作用，抽取參數不會重跑），
重新算過線事件，存成新標籤，之後用 r17_eval.py 評分。不需要 GPU，幾秒鐘。
用法：python 30_實驗/R17_最終魔王/r17_replay.py <來源標籤> <新標籤> <設定 json（R17 資料夾內路徑）>"""
import sys, os, json, glob, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '10_程式', 'src'))
import settings, bibrules  # noqa: E402


def main():
    src, dst, gfile = sys.argv[1:4]
    G = json.load(open(os.path.join(HERE, gfile), encoding='utf-8'))
    R, rp, bibs = settings.load_race('xinwu2026'); C, cp = settings.load_camera('xinwu_finish')
    S = dict(G=G, race=R, camera=C, bibs=bibs, mode=settings.effective_mode(G, R, bibs), can_cross=True)
    out = os.path.join(HERE, 'out', dst); os.makedirs(out, exist_ok=True)
    info = json.load(open(os.path.join(HERE, 'out', src, 'run_info.json'), encoding='utf-8'))
    info.update(replay_of=src, replay_global=gfile, mode=S['mode'])
    json.dump(info, open(os.path.join(out, 'run_info.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = 0
    for d in sorted(glob.glob(os.path.join(HERE, 'out', src, 'seg_*'))):
        if not os.path.exists(os.path.join(d, 'DONE.txt')): continue
        od = os.path.join(out, os.path.basename(d)); os.makedirs(od, exist_ok=True)
        ev = bibrules.events(os.path.join(d, 'raw.jsonl'), S)
        bibrules.write_events(ev, os.path.join(od, 'events.csv'))
        st = json.load(open(os.path.join(d, 'stats.json'))); st.update(n_events=len(ev), n_bib=sum(1 for e in ev if e['bib']), replay_of=src)
        json.dump(st, open(os.path.join(od, 'stats.json'), 'w'))
        open(os.path.join(od, 'DONE.txt'), 'w').close(); n += 1
    print(f'{dst}：重播 {src} 的 {n} 段（定案模式 {S["mode"]}）')


if __name__ == '__main__':
    main()

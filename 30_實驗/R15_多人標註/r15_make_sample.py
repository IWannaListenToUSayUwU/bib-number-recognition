r"""R15 抽樣讀號：從官方完賽名單抽 50 個「時間窗」（第二機位 5 段，每段 10 個），只存「片段＋時間」，不存號碼。
標註者在網頁上看每個時間窗（目標時間前後 1.5 秒），寫下這段時間跨過計時線、看得清的號碼；評分時才用官方名單比對（r15_sample_eval.py）。
  - 片段：tpe2_A_3000（檢查集）、tpe2t_2700／3600／4800／5700（調整集）。tpe2_B、tpe2_C 另做完整過線標註，不抽。
  - 時間換算：片段秒數＝官方槍聲時間 − 片段第 0 秒的時鐘（R12 時鐘對照：tpe2 原片 3000 秒＝13324.067）。
  - 只抽片段 3～57 秒內的人；同一片段的時間窗至少隔 3.5 秒（不重疊）；亂數種子固定，結果可重現。
用法（在專案根目錄）：python 30_實驗/R15_多人標註/r15_make_sample.py
輸出：30_實驗/R15_多人標註/抽樣窗.json（已存在就不覆寫）"""
import hashlib, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OFF = os.path.join(ROOT, '30_實驗', 'R13_新機位讀號碼', '官方成績', '官方完賽名單_全馬.json')
OUT = os.path.join(HERE, '抽樣窗.json')
CLIPS = ['tpe2_A_3000', 'tpe2t_2700', 'tpe2t_3600', 'tpe2t_4800', 'tpe2t_5700']
PER_CLIP, GAP, T_MIN, T_MAX, HALF, SEED = 10, 3.5, 3.0, 57.0, 1.5, 20261123
CLOCK_A = 13324.067   # tpe2 原片 3000 秒的槍聲時間（R12 時鐘對照.json；r13_lib.CLOCK_A）


def sec(s):
    h, m, x = map(int, s.split(':')); return h * 3600 + m * 60 + x


def main():
    if os.path.exists(OUT): sys.exit(f'{OUT} 已存在，不覆寫（抽樣定了就不改）')
    man = json.load(open(os.path.join(ROOT, '20_測試基準', 'MANIFEST.json'), encoding='utf-8'))['clips']
    rows = json.load(open(OFF, encoding='utf-8'))['rows']
    rnd = random.Random(SEED); wins = []
    for c in CLIPS:
        t0 = CLOCK_A + (man[c]['start_s'] - 3000)
        ts = sorted({round(sec(r['time']) - t0, 3) for r in rows if T_MIN <= sec(r['time']) - t0 <= T_MAX})
        rnd.shuffle(ts); pick = []
        for t in ts:
            if all(abs(t - p) >= GAP for p in pick): pick.append(t)
            if len(pick) == PER_CLIP: break
        wins += [dict(clip=c, t=t) for t in sorted(pick)]
    for k, w in enumerate(wins, 1): w['id'] = f'W{k:02d}'
    json.dump(dict(note='抽樣讀號的時間窗（只有片段與時間，沒有號碼）。答案在評分時才從官方名單算。', half_window_s=HALF,
                   seed=SEED, clips=CLIPS, per_clip=PER_CLIP, min_gap_s=GAP, clock_a=CLOCK_A,
                   official_sha256=hashlib.sha256(open(OFF, 'rb').read()).hexdigest(), windows=wins),
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(wins)} 個時間窗 → {OUT}')


if __name__ == '__main__':
    main()

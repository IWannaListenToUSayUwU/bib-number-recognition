r"""R12 準備：GPU 跑完後，用正式流程的 raw.jsonl 算過線事件，並產生標註工具要用的候選與光帶圖。
用法（在專案根目錄）：python 30_實驗/R12_第二機位/r12_prepare.py
輸入：30_實驗/R12_第二機位/out/FROZEN_CONFIG_v2_2/<片段>/raw.jsonl（v2.2、每秒 16 格、正式流程）
輸出：
  30_實驗/R12_第二機位/out_crossing/<片段>/events.csv   系統過線事件（score_v2 格式）；tpe2 用 LINE_tpe2_v1，C、D 用 LINE_tpe_v1
  30_實驗/R12_第二機位/標註/candidates_<tpe2片段>.json、slit_<tpe2片段>.png/.json   標註工具用
過線模組、投票規則、等待時間和 R11 完全相同（直接沿用 r11_prepare 的函式，只換每段的計時線）。不需要 GPU。"""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, '30_實驗', 'R11_過線正確答案'))
import r11_prepare as P  # noqa: E402
RAW = os.path.join(HERE, 'out', 'FROZEN_CONFIG_v2_2', '{}', 'raw.jsonl')
ANN = os.path.join(HERE, '標註'); OUTC = os.path.join(HERE, 'out_crossing')
CLIPS = {'tpe2_A_3000': 'LINE_tpe2_v1', 'tpe2_B_4200': 'LINE_tpe2_v1', 'tpe2_C_5400': 'LINE_tpe2_v1',
         'tpe_C_600': 'LINE_tpe_v1', 'tpe_D_1800': 'LINE_tpe_v1'}


def line(name):
    return json.load(open(os.path.join(ROOT, '10_程式', 'work', name + '.json'), encoding='utf-8'))


def main():
    os.makedirs(ANN, exist_ok=True); P.ANN = ANN; summ = {}
    for c, ln in CLIPS.items():
        if not os.path.exists(RAW.format(c)): print(f'[略過] {c}：還沒有 raw.jsonl'); continue
        P.LINE = line(ln)                      # r11_prepare 的函式讀模組層級的 LINE
        ev, lc, recs = P.run(RAW, c)
        od = os.path.join(OUTC, c); os.makedirs(od, exist_ok=True)
        import csv
        with open(os.path.join(od, 'events.csv'), 'w', newline='', encoding='utf-8') as fo:
            wr = csv.DictWriter(fo, P.EV_COLS, extrasaction='ignore'); wr.writeheader(); wr.writerows(ev)
        summ[c] = dict(events=len(ev), with_bib=sum(1 for e in ev if e['bib']), dup=sum(1 for e in ev if e['dup']), line=ln)
        print(c, summ[c])
        if not c.startswith('tpe2_'): continue
        by_vt = {(r['tid'], r['t']): r['pbox'] for r in recs}
        cands = [dict(sys_id=e['id'], t_sys=e['t_cross'], x=e['x'], y=e['y'], u=e['u'], bib=e['bib'], guess=e['guess'],
                      dup=e['dup'], latency=e['latency'], cross_pbox=P.cross_pbox(recs, e), bib_frame=P.best_bib_frame(lc, by_vt, e),
                      ai_gt=[]) for e in ev]
        json.dump(dict(clip=c, source=f'R12 正式流程 v2.2 16fps raw + aggregate3, decide_after={P.WAIT}', line=ln, items=cands),
                  open(os.path.join(ANN, f'candidates_{c}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        n, fps = P.slit(c); print(f'  光帶圖 {n} 格（{fps:g} fps）')
    json.dump(summ, open(os.path.join(OUTC, '摘要.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

r"""第一階段成績單（2026-11-24，R18）：固定 3 個測試集、固定指標，一個指令列出每個版本的分數。
用法（專案根目錄）：python 20_測試基準/scorecard.py
輸出：20_測試基準/成績單.md、成績單.json
測試集（都已經用過，不是保留卷；真正的期末考要用沒看過的新影片，跑一次就定）：
  corner  臺北馬轉角 C、D 段（122 位過線跑者）：人工過線正確答案 v1_1，score_v2「號碼和過線時間都對」÷ 全部過線跑者
  finish  臺北馬終點 tpe2_A/B/C（官方時間在片段 1～59 秒的 160 人）：官方完賽名單，號碼＋時間 ±2 秒找到率（r13_lib.official_eval）
  xinwu   新屋魚米之鄉終點測試段 4×60 秒（92 人）：官方 10K＋21K 成績，號碼＋時間 ±2 秒找到率（r17_eval）
  finish、xinwu 的分母是「全部完賽者」，包含號碼本來就看不到的人 → 比人工答案嚴格；人眼看得出的上限尚未量測。
新增版本：在 VERSIONS 加一筆（各測試集的 events.csv 位置）。"""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, '30_實驗', 'R13_新機位讀號碼')); sys.path.insert(0, os.path.join(ROOT, '30_實驗', 'R17_最終魔王'))
import score_v2  # noqa: E402

E = lambda *p: os.path.join(ROOT, '30_實驗', *p)
VERSIONS = {
    'v3.0': dict(corner=E('R14_三層設定', 'out', 'GLOBAL_v3_0'), finish=E('R13_新機位讀號碼', '檢查集', 'cons_color'), xinwu='frozen_v30g',
                 note='C、D：R14 GPU 端對端（CPU 文字辨識）；tpe2：R13 檢查集（v2.2 抽取＋cons_color 定案，R14 證實和 v3.0 抽取的 OCR 相同）；新屋：只跑了第 1 段（結構性原因必為 0）'),
    'v3.1': dict(corner=E('R18_v3_1定版', 'out', 'GLOBAL_v3_1'), finish=E('R18_v3_1定版', 'out', 'GLOBAL_v3_1'), xinwu='r17e_test',
                 note='C、D、tpe2：R18（CPU 文字辨識）；新屋：R17 r17e_test（GPU 文字辨識；v3.1＋機位層覆寫重播和 r17e 逐字相同）'),
}
CORNER = ['tpe_C_600', 'tpe_D_1800']; FINISH = ['tpe2_A_3000', 'tpe2_B_4200', 'tpe2_C_5400']


def speed(d, clips):
    xs = []
    for c in clips:
        p = os.path.join(d, c, 'stats.json')
        if os.path.exists(p): xs.append(json.load(open(p))['extract_sec'] / 60.0)
    return round(sum(xs) / len(xs), 1) if xs and len(xs) == len(clips) else None


def corner(d):
    if not all(os.path.exists(os.path.join(d, c, 'events.csv')) for c in CORNER): return None
    T = dict(full=0, corr=0, wrong=0, n=0, absdt=[])
    for c in CORNER:
        g = json.load(open(os.path.join(HERE, 'gt_crossing', c + '.v1_1.json'), encoding='utf-8'))
        s = score_v2.score_clip(score_v2.load_sys(os.path.join(d, c, 'events.csv')), g['events']); raw = s.pop('_raw')
        T['full'] += raw['full']; T['corr'] += raw['corr']; T['wrong'] += raw['wrong']; T['n'] += s['n_gt']; T['absdt'] += raw['absdt']
    return dict(main=score_v2.ratio(T['full'], T['n']), out_error=score_v2.ratio(T['wrong'], T['corr'] + T['wrong']),
                time_med=score_v2.pct(T['absdt'], 0.5), speed=speed(d, CORNER))


def finish(d):
    import r13_lib as L
    if not all(os.path.exists(os.path.join(d, c, 'events.csv')) for c in FINISH): return None
    k = n = bad = out = 0; dts = []
    for c in FINISH:
        ev = list(__import__('csv').DictReader(open(os.path.join(d, c, 'events.csv'), encoding='utf-8-sig')))
        ev = [e for e in ev if str(e.get('dup', 'False')) != 'True']
        r = L.official_eval(c, ev)
        k += r['found']; n += r['official_in_clip']; bad += r['time_mismatch'] + r['not_in_list']; out += r['consistent'] + r['time_mismatch'] + r['not_in_list']
        dts += [abs(x) for x in r['deltas']]
    dts.sort()
    return dict(main=score_v2.ratio(k, n), out_error=score_v2.ratio(bad, out), wrong_out=bad, time_med=dts[len(dts) // 2] if dts else None, speed=speed(d, FINISH))


def xinwu(tag):
    import r17_eval as X
    if not os.path.exists(E('R17_最終魔王', 'out', tag, 'run_info.json')): return None
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()): r = X.evaluate(tag)
    return dict(main=r['found'], out_error=score_v2.ratio(r['wrong_out'], r['n_out_bib']) if r['n_out_bib'] else None, wrong_out=r['wrong_out'],
                time_med=r['time_err']['abs_med'], segments=len(r['segments']), n_expected=r['n_expected'])


def fmt(m):
    if not m: return '—'
    v = m['main']; return f"{v['value']:.3f}（{v['k']}/{v['n']}，[{max(0, v['ci95'][0]):.2f}, {v['ci95'][1]:.2f}]）"


def main():
    res = {v: dict(corner=corner(c['corner']), finish=finish(c['finish']), xinwu=xinwu(c['xinwu']), note=c['note']) for v, c in VERSIONS.items()}
    json.dump(res, open(os.path.join(HERE, '成績單.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    L = ['# 成績單（第一階段）', '', '由 `20_測試基準/scorecard.py` 產生，請勿手改。主要指標＝號碼和過線時間都對的比例（括號：對的人數／全部過線跑者，95% 信賴區間）。', '',
         '| 版本 | 臺北馬轉角 C+D（人工答案） | 臺北馬終點 tpe2（官方名單） | 新屋終點測試段（官方名單） |', '|---|---|---|---|']
    for v, r in res.items(): L.append(f"| {v} | {fmt(r['corner'])} | {fmt(r['finish'])} | {fmt(r['xinwu'])} |")
    L += ['', '| 版本 | 測試集 | 輸出號碼錯誤率 | 時間誤差中位數（秒） | 處理時間÷影片長度 |', '|---|---|---|---|---|']
    for v, r in res.items():
        for k, name in (('corner', '轉角 C+D'), ('finish', '終點 tpe2'), ('xinwu', '新屋')):
            m = r[k]
            if not m: continue
            oe = m.get('out_error'); L.append(f"| {v} | {name} | {oe['value'] if oe else '—'}（{oe['k'] if oe else 0}/{oe['n'] if oe else 0}） | {round(m['time_med'], 2) if m.get('time_med') is not None else '—'} | {m.get('speed') or '—'} |")
    L += ['', '說明：'] + [f'- {v}：{r["note"]}' for v, r in res.items()] + [
        '- 終點 tpe2、新屋的分母是全部完賽者（含號碼本來就看不到的人），比人工答案嚴格；人眼看得出的上限尚未量測。',
        '- 三個測試集都已經用過（C+D 調過參數），不是保留卷。',
        '- 處理時間÷影片長度：小於 1 才是即時。新屋用 GPU 文字辨識且兩個工作同時跑，不列速度。']
    open(os.path.join(HERE, '成績單.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()

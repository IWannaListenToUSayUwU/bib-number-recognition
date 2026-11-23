r"""R11 匯出：把使用者的標註（標註/annot_<片段>.json）轉成正式的過線正確答案，並登記到 MANIFEST.json。
用法（在專案根目錄）：python 30_實驗/R11_過線正確答案/r11_export.py [--version v1_1] [--clips tpe2_A_3000,tpe2_B_4200]
  不加 --clips 時匯出 C、D（R11）；tpe2_* 片段的標註在 R12_第二機位/標註，計時線用 LINE_tpe2_v1。
  會先檢查：每個系統候選都看過、光帶圖已勾選看完、每位跑者都有過線時間與號碼狀態。不通過就不匯出。
  正確答案一旦匯出就不覆寫（規格.md 第 2 節）；要修正請用 --version 另存新版（例：tpe_C_600.v1_1.json）。
輸出：20_測試基準/gt_crossing/<片段>[.<版本>].json、MANIFEST.json 的 crossing_gt 區塊、標註/標註摘要.json"""
import hashlib, json, os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__)); ANN = os.path.join(HERE, '標註')
BENCH = os.path.join(ROOT, '20_測試基準'); OUTD = os.path.join(BENCH, 'gt_crossing')
CLIPS = ['tpe_C_600', 'tpe_D_1800']
BIB_LEN = 5  # 台北馬號碼一律 5 碼（舊正確答案 A～D 的 sure 號碼全部 5 碼）
R12ANN = os.path.join(ROOT, '30_實驗', 'R12_第二機位', '標註')
def ann_of(c): return R12ANN if c.startswith('tpe2_') else ANN
def line_of(c): return 'LINE_tpe2_v1' if c.startswith('tpe2_') else 'LINE_tpe_v1'
def linep(c): return os.path.join(ROOT, '10_程式', 'work', line_of(c) + '.json')


def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def check(clip):
    a = json.load(open(os.path.join(ann_of(clip), f'annot_{clip}.json'), encoding='utf-8'))
    cand = json.load(open(os.path.join(ann_of(clip), f'candidates_{clip}.json'), encoding='utf-8'))
    items = {i['key']: i for i in a['items']}; err = []
    miss = [c['sys_id'] for c in cand['items'] if not items.get(f"sys-{c['sys_id']}", {}).get('reviewed')]
    if miss: err.append(f'還有 {len(miss)} 個系統候選沒看：{miss[:10]}')
    if not a.get('slit_checked'): err.append('光帶圖還沒勾選「已從頭看到尾」')
    for i in a['items']:
        if i.get('verdict') == 'runner' and (i.get('t_gt') is None or not i.get('status')):
            err.append(f"{i['key']}：跑者缺過線時間或號碼狀態")
        if i['sys_id'] is None and not i.get('reviewed'): err.append(f"{i['key']}：人工新增的事件還沒儲存")
    # 2026-11-22 補上的有效性檢查（v1 匯出後發現）：同一號碼只能過線一次；號碼一律 5 碼、看不清的每位一個 ?
    run = [i for i in a['items'] if i.get('reviewed') and i.get('verdict') == 'runner']
    seen = {}
    for i in run:
        b = i.get('bib') or ''
        if i.get('status') == 'sure': seen.setdefault(b, []).append(round(i['t_gt'], 2))
        if i.get('status') in ('sure', 'partial') and len(b) != BIB_LEN:
            err.append(f"{i['key']}（{i['t_gt']:.2f}s）：號碼「{b}」不是 {BIB_LEN} 碼")
    for b, ts in seen.items():
        if len(ts) > 1: err.append(f'號碼 {b} 標成 sure 的跑者有 {len(ts)} 位（{ts} 秒）：同一個人只會過線一次')
    return a, err


def main():
    ver = sys.argv[sys.argv.index('--version') + 1] if '--version' in sys.argv else None
    os.makedirs(OUTD, exist_ok=True); allerr = {}; done = {}
    clips = sys.argv[sys.argv.index('--clips') + 1].split(',') if '--clips' in sys.argv else CLIPS
    for c in clips:
        if not os.path.exists(os.path.join(ann_of(c), f'annot_{c}.json')): allerr[c] = ['還沒有標註檔']; continue
        a, err = check(c)
        if err: allerr[c] = err; continue
        runners = sorted((i for i in a['items'] if i.get('reviewed') and i['verdict'] == 'runner'), key=lambda i: i['t_gt'])
        out = os.path.join(OUTD, f'{c}.json' if not ver else f'{c}.{ver}.json')
        if os.path.exists(out): allerr[c] = [f'{os.path.relpath(out, ROOT)} 已存在，正確答案不覆寫；要修正請加 --version 另存新版']; continue
        gt = dict(clip=c, version=ver or 'v1', line=line_of(c), line_sha256=sha(linep(c)), fps=30, annotator='user（人工）',
                  protocol='30_實驗/R11_過線正確答案/計畫.md 標註規則', created=time.strftime('%Y-%m-%d %H:%M:%S'),
                  candidates=('R12 正式流程（16fps、v2.2）' if c.startswith('tpe2_') else 'R10 過線模組（16fps、v2.2）') + '＋光帶圖人工補漏',
                  events=[dict(t=round(i['t_gt'], 3), u=round(i['u'], 3), bib=i.get('bib', ''), status=i['status'],
                               source='system' if i['sys_id'] is not None else 'human_added') for i in runners])
        json.dump(gt, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        sysi = [i for i in a['items'] if i['sys_id'] is not None]
        done[c] = dict(file=os.path.relpath(out, ROOT), sha256=sha(out), n_events=len(runners),
                       status_count={s: sum(i['status'] == s for i in runners) for s in ('sure', 'partial', 'unreadable', 'nobib')},
                       human_added=sum(i['sys_id'] is None for i in runners),
                       system_candidates=len(sysi), not_runner=sum(i['verdict'] == 'not_runner' for i in sysi),
                       same_person_dup=sum(i['verdict'] == 'same_person_dup' for i in sysi),
                       prefill_bib_edited=sum(bool(i.get('bib_edited')) for i in sysi if i['verdict'] == 'runner'))
    for c, e in allerr.items(): print(f'[未匯出] {c}：' + '；'.join(e))
    if not done: return
    mp = os.path.join(BENCH, 'MANIFEST.json'); man = json.load(open(mp, encoding='utf-8'))
    man.setdefault('crossing_gt', {})
    for c, d in done.items():
        man.setdefault('line_configs', {})[line_of(c)] = sha(linep(c))
        man['crossing_gt'][os.path.basename(d['file'])] = dict(sha256=d['sha256'], n_events=d['n_events'], created=time.strftime('%Y-%m-%d'))
        print(f"[匯出] {d['file']}：{d['n_events']} 位過線跑者 {d['status_count']}，人工補漏 {d['human_added']}，預填號碼被改 {d['prefill_bib_edited']}")
    json.dump(man, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for A in {ann_of(c) for c in done}:
        sp = os.path.join(A, '標註摘要.json'); old = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
        old.update({c: d for c, d in done.items() if ann_of(c) == A}); json.dump(old, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

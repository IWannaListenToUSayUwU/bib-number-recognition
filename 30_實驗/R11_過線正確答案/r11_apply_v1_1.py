r"""R11 正確答案 v1 → v1_1：把使用者同意的修正（分析/v1_1修正建議.md，2026-11-23 使用者回覆「全部照建議」）寫進標註檔。
- 先備份：標註/annot_<片段>.before_v1_1.json（已存在就不覆寫）。
- 每筆修改記在該項目的 v1_1_fix 欄位（原本的號碼、狀態、理由）；bib_edited 依「和預填號碼是否不同」重算。
- 更新標註檔的 updated 時間：如果標註工具的舊畫面還開著，它會拒絕存檔，不會蓋掉這次修改。
- 只改標註檔；正式答案由 r11_export.py --version v1_1 另存（v1 不動）。
用法（在專案根目錄）：python 30_實驗/R11_過線正確答案/r11_apply_v1_1.py"""
import json, os, shutil, time
HERE = os.path.dirname(os.path.abspath(__file__)); ANN = os.path.join(HERE, '標註')
REF = '分析/v1_1修正建議.md'
FIX = {  # key: (新號碼, 新狀態, 建議表編號與理由)
    'tpe_C_600': {
        'sys-23': ('04182', 'sure', '#5 4 碼 partial；25.75～26.38 秒清楚'),
        'sys-25': ('01434', 'sure', '#6 4 碼 partial；28.44～30.31 秒清楚'),
        'sys-42': ('07381', 'sure', '#7 4 碼 partial；52.44～54.69 秒清楚'),
    },
    'tpe_D_1800': {
        'sys-17': ('05266', 'sure', '#1 同號碼兩位：過線的是橘白背心，14.19、14.56 秒清楚 05266；02691 是 sys-15'),
        'sys-42': ('', 'unreadable', '#2 同號碼兩位：過線的是黑衣紫褲，腰間白色看不到數字；03045 是 sys-44'),
        'sys-64': ('03710', 'sure', '#3 同號碼兩位：過線的是綠衣，43.31、43.69 秒清楚 03710；04159 是 sys-61'),
        'sys-72': ('', 'unreadable', '#4 同號碼兩位：過線的是黃外套，號碼布在外套裡看不清；10472 是 sys-73'),
        'sys-10': ('01596', 'sure', '#8 4 碼 partial；7.69、8.06 秒'),
        'sys-34': ('03636', 'sure', '#9 4 碼 partial；24.38、24.75 秒清楚'),
        'sys-69': ('04544', 'sure', '#10 4 碼 partial；49.38、50.50 秒清楚'),
        'sys-55': ('01136', 'sure', '#12 官方名單可疑：暗紅背心 38.69、39.06 秒清楚 01136'),
        'sys-57': ('06348', 'sure', '#14 過線的是橘紅背心，39.81、40.19 秒清楚 06348'),
        'sys-27': ('11069', 'sure', '#15 過線的是藍綠外套女生，18.19～18.69 秒清楚 11069；05266 是 sys-17'),
        'sys-62': ('05634', 'sure', '#16 黃衣，40.62～43.25 秒清楚 05634（規則：看得清就照寫，不限過線那一格）'),
        'sys-60': ('10493', 'sure', '#17 黑色長袖女生，41.69、42.06 秒清楚 10493'),
        'sys-70': ('11525', 'sure', '#18 桃紅背心女生，48.94～50.81 秒清楚 11525'),
        'sys-71': ('05301', 'sure', '#19 紅背心，51.19～51.94 秒清楚 05301'),
    },
}
KEEP = {  # 核對後保留（只加註記）
    'tpe_D_1800': {
        'sys-47': '#11 保留：33.44～35.31 秒都清楚 04387；不在完賽名單最可能是沒完賽',
        'sys-20': '#13 保留：過線者和系統讀到 08036 的是同一人；+37 秒是轉角到終點的配速差',
    },
}


def main():
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for clip in FIX:
        p = os.path.join(ANN, f'annot_{clip}.json'); bak = os.path.join(ANN, f'annot_{clip}.before_v1_1.json')
        if not os.path.exists(bak): shutil.copy2(p, bak)
        a = json.load(open(p, encoding='utf-8')); items = {i['key']: i for i in a['items']}
        for k, (bib, st, why) in FIX[clip].items():
            i = items[k]
            if i.get('v1_1_fix'): print(f'[略過] {clip} {k} 已套用過'); continue
            i['v1_1_fix'] = dict(from_bib=i.get('bib', ''), from_status=i.get('status'), reason=why, ref=REF, at=now,
                                 approved='使用者 2026-11-23「全部照建議」')
            print(f"{clip} {k}：{i.get('bib', '') or '（空）'} {i.get('status')} → {bib or '（空）'} {st}")
            i['bib'], i['status'] = bib, st
            i['bib_edited'] = bib != (i.get('prefill_bib') or '')
        for k, why in KEEP.get(clip, {}).items():
            i = items[k]
            if not i.get('v1_1_fix'):
                i['v1_1_fix'] = dict(kept=True, reason=why, ref=REF, at=now, approved='使用者 2026-11-23「全部照建議」')
                print(f"{clip} {k}：保留 {i.get('bib')}")
        a['updated'] = now
        json.dump(a, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

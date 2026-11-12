"""疊字正確率抽樣：同一份 raw4 快取，模擬「舊版疊字（第一個穩定讀數、不切軌跡、永遠顯示）」與
「新版疊字（定案結果、切軌跡、只在讀到時間 ±1 秒內顯示）」，每 1 秒取一格、抽出有標籤的人物框，
裁成小圖（標籤寫在圖上方的白邊，不遮擋號碼牌），兩版混合打亂後供盲檢。"""
import sys, os, json, random, re, cv2, numpy as np
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))
from frames import grab
from aggregate2 import load4, aggregate2
D = re.compile(r'\d+')
cfg = json.load(open('work/FROZEN_CONFIG_v2.json'))['aggregate']
which = sys.argv[1]; per_clip = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rnd = random.Random(7); items = []
os.makedirs(f'work/overlay_check/{which}/img', exist_ok=True)
for fn in sorted(os.listdir(f'work/raw4/{which}')):
    if not fn.endswith('.jsonl'): continue
    clip = fn[:-6]; vid = clip.split('_')[0]
    raw = [json.loads(l) for l in open(f'work/raw4/{which}/{fn}')]
    rows, _ = load4(f'work/raw4/{which}/{fn}')
    # 新版
    lab_new = {}
    for p in aggregate2(rows, **cfg):
        for tid in p['tids']:
            if isinstance(tid, int): lab_new[tid] = (p['bib'], p['t0'] - 1, p['t1'] + 1)
    # 舊版：依 rawtid、第一次出現 conf>=0.9 數字後就一直顯示目前最多數
    good = defaultdict(Counter); cand = {'old': [], 'new': []}
    for r in raw:
        t = r['t']; ts = abs(t - round(t)) < 1e-6
        for txt, sc, bb in (r['texts'] or []):
            d = D.findall(txt.replace(' ', ''))
            if d and sc >= 0.9: good[r['rawtid']][max(d, key=len)] += 1
        if not ts: continue
        if good[r['rawtid']]:
            cand['old'].append((t, r['pbox'], good[r['rawtid']].most_common(1)[0][0]))
        L = lab_new.get(r['tid'])
        if L and L[1] <= t <= L[2]:
            cand['new'].append((t, r['pbox'], L[0]))
    for style in ['old', 'new']:
        for t, b, lab in rnd.sample(cand[style], min(per_clip, len(cand[style]))):
            items.append(dict(clip=clip, vid=vid, t=t, box=b, label=lab, style=style))
rnd.shuffle(items)
key = []
for i, it in enumerate(items):
    f = grab(it['vid'], it['t']).copy(); x1, y1, x2, y2 = it['box']
    c = f[max(0, y1):y2, max(0, x1):x2]
    s = 360 / c.shape[0]; c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    pad = np.full((60, max(c.shape[1], 460), 3), 255, np.uint8)
    cv2.putText(pad, f'#{i:03d}  label={it["label"]}', (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    body = np.full((360, pad.shape[1], 3), 255, np.uint8); body[:, :c.shape[1]] = c
    cv2.imwrite(f'work/overlay_check/{which}/img/{i:03d}.jpg', np.vstack([pad, body]))
    key.append(dict(id=i, **{k: it[k] for k in ['clip', 't', 'label', 'style']}))
json.dump(key, open(f'work/overlay_check/{which}/key.json', 'w'), indent=1)
print(len(items), 'items', Counter(k['style'] for k in key))
# 每 4 張拼成一張，方便檢查者檢視
imgs = sorted(os.listdir(f'work/overlay_check/{which}/img'))
os.makedirs(f'work/overlay_check/{which}/sheets', exist_ok=True)
for k in range(0, len(imgs), 4):
    tiles = [cv2.imread(f'work/overlay_check/{which}/img/{f}') for f in imgs[k:k + 4]]
    Wm = max(t.shape[1] for t in tiles)
    tiles = [np.pad(t, ((0, 0), (0, Wm - t.shape[1]), (0, 0)), constant_values=255) for t in tiles]
    while len(tiles) < 4: tiles.append(np.full_like(tiles[0], 255))
    sheet = np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])])
    cv2.imwrite(f'work/overlay_check/{which}/sheets/sheet_{k // 4:02d}.jpg', sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
print('sheets', (len(imgs) + 3) // 4)

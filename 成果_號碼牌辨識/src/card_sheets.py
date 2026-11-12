"""把跑者卡 4 張一組拼成一張，方便標註者逐張檢視。"""
import sys, os, glob, cv2, numpy as np
for d in sys.argv[1:]:
    cards = sorted(glob.glob(f'{d}/card_*.jpg'))
    os.makedirs(f'{d}/sheets', exist_ok=True)
    for k in range(0, len(cards), 4):
        imgs = []
        for c in cards[k:k + 4]:
            im = cv2.imread(c); s = 300 / im.shape[0]
            im = cv2.resize(im, (min(1400, int(im.shape[1] * s)), 300))
            pad = np.zeros((300, 1400, 3), np.uint8); pad[:, :im.shape[1]] = im
            imgs.append(pad)
        cv2.imwrite(f'{d}/sheets/sheet_{k // 4:02d}.jpg', np.vstack(imgs), [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(d, len(cards), 'cards ->', (len(cards) + 3) // 4, 'sheets')

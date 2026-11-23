"""辨識器變體：在文字行裁切快取上離線重新辨識。輸出 r3/rec/{set}/{clip}.json = {crop_id: {variant: [text, conf]}}"""
import sys, os, json, math, glob, cv2, numpy as np, onnxruntime as ort
sys.path.insert(0, 'src')
so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; so.log_severity_level = 4

class PPRec:
    def __init__(self, model, chars):
        self.s = ort.InferenceSession(model, so, providers=['CPUExecutionProvider']); self.inp = self.s.get_inputs()[0].name
        self.chars = ['<b>'] + chars + [' ']
        self.dig = np.array([0] + [i for i, c in enumerate(self.chars) if c in list('0123456789')])
    def logits(self, img):
        h, w = img.shape[:2]; W = int(min(320, max(16, math.ceil(48 * w / h))))
        x = cv2.resize(img, (W, 48), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.
        x = ((x - 0.5) / 0.5).transpose(2, 0, 1)[None]
        return self.s.run(None, {self.inp: x})[0][0]          # T x C (softmax)
    def decode(self, P, digits=False):
        if digits:
            Q = P[:, self.dig]; Q = Q / (Q.sum(1, keepdims=True) + 1e-9); idx = self.dig[Q.argmax(1)]; pr = Q.max(1); raw = P[np.arange(len(P)), idx]
        else:
            idx = P.argmax(1); pr = P.max(1); raw = pr
        out, cf, rw, prev = [], [], [], -1
        for i, p, r in zip(idx, pr, raw):
            if i != prev and i != 0: out.append(self.chars[i]); cf.append(float(p)); rw.append(float(r))
            prev = i
        return ''.join(out), (float(np.mean(cf)) if cf else 0.0), (float(np.mean(rw)) if rw else 0.0)

def engines():
    import rapidocr_onnxruntime as R, onnxocr
    m4 = os.path.dirname(R.__file__) + '/models/ch_PP-OCRv4_rec_infer.onnx'
    ch4 = ort.InferenceSession(m4, so, providers=['CPUExecutionProvider']).get_modelmeta().custom_metadata_map['character'].splitlines()
    d5 = os.path.dirname(onnxocr.__file__) + '/models/ppocrv5/'
    ch5 = [l.rstrip('\n') for l in open(d5 + 'ppocrv5_dict.txt', encoding='utf-8')]
    return PPRec(m4, ch4), PPRec(d5 + 'rec/rec.onnx', ch5)

def run(sets):
    v4, v5 = engines()
    from onnxtr.models import recognition_predictor
    pq = recognition_predictor('parseq', load_in_8_bit=False)
    for s in sets:
        for d in sorted(glob.glob(f'r3/crops/{s}/*/')):
            clip = os.path.basename(d.rstrip('/')); out = f'r3/rec/{s}/{clip}.json'
            if os.path.exists(out): continue
            os.makedirs(os.path.dirname(out), exist_ok=True); res = {}
            for it in json.load(open(d + 'index.json')):
                img = cv2.imread(f'{d}{it["id"]}.png')
                if img is None: continue
                X1, Y1, X2, Y2 = it['crop']; x1, y1, x2, y2 = it['bbox']
                tight = img[max(0, y1 - Y1):max(1, y2 - Y1), max(0, x1 - X1):max(1, x2 - X1)]
                r = {}
                for name, eng in [('v4', v4), ('v5', v5)]:
                    for cn, c in [('m', img), ('t', tight)]:
                        if c.size == 0 or min(c.shape[:2]) < 3: continue
                        P = eng.logits(c)
                        t, cf, _ = eng.decode(P); r[f'{name}{cn}'] = [t, cf]
                        t, cf, rw = eng.decode(P, digits=True); r[f'{name}{cn}_dig'] = [t, cf, rw]
                try:
                    o = pq([cv2.cvtColor(img, cv2.COLOR_BGR2RGB)]); r['parseq_m'] = [o[0][0], float(o[0][1])]
                    if tight.size and min(tight.shape[:2]) >= 3:
                        o = pq([cv2.cvtColor(tight, cv2.COLOR_BGR2RGB)]); r['parseq_t'] = [o[0][0], float(o[0][1])]
                except Exception as e: r['parseq_err'] = str(e)[:80]
                res[it['id']] = r
            json.dump(res, open(out, 'w')); print(s, clip, len(res), flush=True)
if __name__ == '__main__':
    run(sys.argv[1:] or ['dev', 'test', 'test2'])

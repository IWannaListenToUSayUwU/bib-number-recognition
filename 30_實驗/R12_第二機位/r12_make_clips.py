r"""R12：從第二機位原始影片剪出 60 秒測試片段到 20_測試基準\clips（原始影片唯讀，不改）。
選段規則（事前寫死，見 計畫.md）：在機位固定的區間 2600–5870 秒內等距取 3 段：3000、4200、5400 秒起。
格式：1920×1080、每秒 30 格（原片 59.94 格，用 fps=30 轉成固定 30 格，讓既有工具的「時間＝格數÷30」不用改）、H.264 crf 16、無聲音。
用法（在專案根目錄）：python 30_實驗/R12_第二機位/r12_make_clips.py
已存在的片段不覆寫。完成後印出 sha256，給 MANIFEST 登記用。"""
import hashlib, json, os, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r12_overview import SRC  # noqa: E402
CLIPDIR = os.path.join(ROOT, '20_測試基準', 'clips')
SEGS = [('tpe2_A_3000', 3000), ('tpe2_B_4200', 4200), ('tpe2_C_5400', 5400)]
DUR = 60


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def main():
    info = {}
    for name, s in SEGS:
        out = os.path.join(CLIPDIR, name + '.mp4')
        if os.path.exists(out):
            print(f'[略過] {name} 已存在')
        else:
            tmp = out + '.part.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(s), '-i', SRC, '-t', str(DUR), '-vf', 'fps=30',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-an',
                            '-movflags', '+faststart', tmp], check=True)
            os.replace(tmp, out)
        pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries',
                                        'stream=width,height,r_frame_rate,nb_read_frames:format=duration', '-of', 'json', out],
                                       capture_output=True, text=True).stdout)
        st = pr['streams'][0]
        info[name] = dict(sha256=sha(out), start_s=s, end_s=s + DUR, width=st['width'], height=st['height'],
                          fps=st['r_frame_rate'], frames=int(st['nb_read_frames']), duration=float(pr['format']['duration']))
        print(name, info[name])
    json.dump(info, open(os.path.join(HERE, '片段資訊.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

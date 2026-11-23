import sys, os, json; sys.path.insert(0, os.path.dirname(__file__))
from extract3 import run
split = json.load(open('work/split.json')); which, vids, fps, outdir = sys.argv[1], sys.argv[2].split(','), float(sys.argv[3]), sys.argv[4]
os.makedirs(f'{outdir}/{which}', exist_ok=True)
for v in vids:
    for c in split[v][which]:
        o = f'{outdir}/{which}/{v}_{c["start"]}.jsonl'
        if os.path.exists(o + '.done'): continue
        run(v, c['start'], c['end'], o, fps=fps); open(o + '.done', 'w').close()

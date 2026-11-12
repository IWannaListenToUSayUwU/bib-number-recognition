import sys, os, json; sys.path.insert(0, os.path.dirname(__file__))
from extract3 import run
vid, start, end, out, fps = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], float(sys.argv[5])
run(vid, start, end, out, fps=fps); open(out + '.done', 'w').close()

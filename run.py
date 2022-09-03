from zrun import ZRun
import sys

def run():
    t = ZRun()
    t.run_from_path(sys.argv[1])

run()
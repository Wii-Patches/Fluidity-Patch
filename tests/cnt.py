#!/usr/bin/env python3
"""cnt.py <wad> <secs> <n> -- read n counters at 0x80002C00 after secs (WIIMOTE=1 for a remote)."""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp
wad, secs, n = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
user = os.path.abspath(os.environ.get('USERDIR', dp.WORK + '/dolphin_user'))
dp.prepare(user, pad=not os.environ.get('NOPAD'), wiimote=bool(os.environ.get('WIIMOTE')))
dp.launch(user, wad, 'Null')
try:
    g = dp.connect(); g.cont()
    for t in range(int(sys.argv[4]) if len(sys.argv) > 4 else 2):
        time.sleep(secs)
        g.interrupt()
        print(' '.join('%d' % x for x in struct.unpack('>%dI' % n, g.read_mem(0x80002C00, 4 * n))), flush=True)
        g.cont()
finally:
    dp.stop(user)

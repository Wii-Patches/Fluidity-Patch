#!/usr/bin/env python3
"""pcs.py <wad> <secs> [n] -- sample the program counter n times (no Wii Remote, GC pad plugged in)."""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp
wad, secs = sys.argv[1], float(sys.argv[2]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
user = os.path.abspath(os.environ.get('USERDIR', dp.WORK + '/dolphin_user'))
dp.prepare(user, pad=not os.environ.get('NOPAD'), wiimote=bool(os.environ.get('WIIMOTE')))
dp.launch(user, wad, 'Null')
try:
    g = dp.connect(); g.cont()
    time.sleep(secs)
    for i in range(n):
        g.interrupt()
        pc = g.cmd('p40'); lr = g.cmd('p43')
        print('pc=%s lr=%s' % (pc, lr))
        g.cont(); time.sleep(0.4)
finally:
    dp.stop(user)

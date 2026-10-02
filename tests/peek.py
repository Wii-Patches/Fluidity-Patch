#!/usr/bin/env python3
"""peek.py <wad> <secs> addr[:len] ... -- boot, wait, read memory over the GDB stub (GC pad plugged in)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp
wad, secs = sys.argv[1], float(sys.argv[2])
user = os.path.abspath(os.environ.get('USERDIR', dp.WORK + '/dolphin_user'))
dp.prepare(user, pad=not os.environ.get('NOPAD'), wiimote=bool(os.environ.get('WIIMOTE')))
dp.launch(user, wad, 'Null')
try:
    g = dp.connect(); g.cont(); pad = dp.Pad(user)
    time.sleep(secs)
    if os.environ.get('PRESS'):
        pad.press(os.environ['PRESS']); time.sleep(1.5)
    g.interrupt()
    for a in sys.argv[3:]:
        addr, _, n = a.partition(':')
        n = int(n, 0) if n else 16
        b = g.read_mem(int(addr, 16), n)
        print('%08X:' % int(addr, 16), ' '.join(b[i:i+4].hex() for i in range(0, len(b), 4)))
finally:
    dp.stop(user)

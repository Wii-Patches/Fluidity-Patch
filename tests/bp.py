#!/usr/bin/env python3
"""bp.py <wad> <secs> addr... -- set breakpoints, report which are reached (no Wii Remote unless WIIMOTE=1)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp
wad, secs = sys.argv[1], float(sys.argv[2]); addrs = [int(a, 16) for a in sys.argv[3:]]
user = os.path.abspath(os.environ.get('USERDIR', dp.WORK + '/dolphin_user'))
dp.prepare(user, pad=not os.environ.get('NOPAD'), wiimote=bool(os.environ.get('WIIMOTE')))
dp.launch(user, wad, 'Null')
try:
    g = dp.connect()
    time.sleep(secs)
    g.interrupt()
    for a in addrs:
        print('Z0', hex(a), g.cmd('Z0,%x,4' % a))
    for i in range(len(addrs) * 3):
        g.cont()
        g.s.settimeout(8)
        try:
            r = g.recv()
        except Exception as e:
            print('no stop within 8 s'); break
        pc = g.cmd('p40')
        print('stopped', r, 'pc', pc, 'lr', g.cmd('p43'))
        for a in addrs:
            g.cmd('z0,%x,4' % a)
        g.interrupt() if False else None
        for a in addrs:
            g.cmd('Z0,%x,4' % a)
finally:
    dp.stop(user)

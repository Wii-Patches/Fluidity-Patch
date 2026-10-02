#!/usr/bin/env python3
"""mgr.py <wad> <secs> -- dump the game's controller manager (pointer at r13-0x2010) words of interest."""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp
wad, secs = sys.argv[1], float(sys.argv[2])
user = os.path.abspath(os.environ.get('USERDIR', dp.WORK + '/dolphin_user'))
dp.prepare(user, pad=not os.environ.get('NOPAD'), wiimote=bool(os.environ.get('WIIMOTE')))
dp.launch(user, wad, 'Null')
try:
    g = dp.connect(); g.cont(); time.sleep(secs); g.interrupt()
    m = struct.unpack('>I', g.read_mem(0x80547650, 4))[0]
    print('mgr = %08X' % m)
    for off, n in ((0x40, 0x20), (0x40e0, 0x20)):
        b = g.read_mem(m + off, n)
        print('+%04X:' % off, ' '.join(b[i:i+4].hex() for i in range(0, n, 4)))
    print('masks 8046ca08:', g.read_mem(0x8046ca08, 16).hex(), ' 804c84d8:', g.read_mem(0x804c84d8, 16).hex())
finally:
    dp.stop(user)

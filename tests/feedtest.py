#!/usr/bin/env python3
"""feedtest.py <feed-wad> [secs] -- boot a DEBUG_FEED build (tools/gcbuild.py with DEBUG_FEED=1), write GC pad
responses straight into STATE+0x20/0x24 and print what KPAD channel 0 makes of each. Region via REGION=WFLE|WFLP."""
import os, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp
from padtest import kpad, KPAD0
B0 = dict(A=1, B=2, X=4, Y=8, Start=0x10)
B1 = dict(Left=1, Right=2, Down=4, Up=8, Z=0x10, R=0x20, L=0x40)
def word(name='N'):
    b0 = b1 = 0x00; sx = sy = cx = cy = 0x80; lt = rt = 0
    for n in name.split('+'):
        if n in B0: b0 |= B0[n]
        elif n in B1: b1 |= B1[n]
        elif n.startswith('stk='): x, y = map(float, n[4:].split(',')); sx, sy = int(128 + 127*x), int(128 + 127*y)
        elif n.startswith('cst='): x, y = map(float, n[4:].split(',')); cx, cy = int(128 + 127*x), int(128 + 127*y)
    if 'L' in name.split('+'): lt = 0xFF
    if 'R' in name.split('+'): rt = 0xFF
    return struct.pack('>II', b0 << 24 | (b1 | 0x80) << 16 | sx << 8 | sy, cx << 24 | cy << 16 | lt << 8 | rt)
def main():
    region = os.environ.get('REGION', 'WFLE')
    user = os.path.abspath(dp.WORK + '/dolphin_user')
    dp.prepare(user, frames=False, pad=False, wiimote=bool(os.environ.get('WIIMOTE')))
    dp.launch(user, sys.argv[1], 'Null')
    try:
        g = dp.connect(); g.cont(); time.sleep(float(sys.argv[2]) if len(sys.argv) > 2 else 40)
        for step in sys.argv[3:] or ['N', 'A']:
            g.interrupt(); g.cmd('M80001840,8:' + word(step).hex()); g.cont(); time.sleep(1.5)
            g.interrupt(); k = kpad(g, KPAD0[region]); acc = struct.unpack('>fff', g.read_mem(KPAD0[region] + 0xC, 12))
            print('%-14s hold=%08X chold=%04X ext=%d ls=(%.2f,%.2f) rs=(%.2f,%.2f) acc=(%.2f,%.2f,%.2f)' % (step, k['hold'], k['chold'], k['ext'], *k['ls'], *k['rs'], *acc), flush=True)
            g.cont()
    finally:
        dp.stop(user)
if __name__ == "__main__": main()

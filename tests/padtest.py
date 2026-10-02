#!/usr/bin/env python3
"""padtest.py <wad> [secs] -- boot a patched WAD with a GameCube pad (Dolphin Pipe) and no Wii Remote,
press things, and print what the game's KPAD (channel 0) makes of them."""
import os, shutil, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp

KPAD0 = {'WFLE': 0x804FD6C8, 'WFLP': 0x804FF988}


def kpad(g, base):
    b = g.read_mem(base, 0x100)
    hold, trig, rel = struct.unpack('>III', b[0:12])
    chold = struct.unpack('>I', b[0x60:0x64])[0]
    ls = struct.unpack('>ff', b[0x6C:0x74]); rs = struct.unpack('>ff', b[0x74:0x7C])
    return dict(hold=hold, ext=b[0x5C], err=b[0x5D], dpd=b[0x5E], chold=chold, ls=ls, rs=rs)


def main():
    wad = sys.argv[1]
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 40
    region = os.environ.get('REGION', 'WFLE')
    user = os.path.abspath(os.environ.get('USERDIR', dp.WORK + '/dolphin_user'))
    dp.prepare(user, frames=bool(os.environ.get('FRAMES')), pad=True, wiimote=bool(os.environ.get('WIIMOTE')))
    dp.launch(user, wad, os.environ.get('VIDEO', 'Null'))
    try:
        g = dp.connect()
        g.cont()
        pad = dp.Pad(user)
        time.sleep(secs)
        for step in sys.argv[3:] or ['A']:
            if step == 'N':
                pad.cmd('RELEASE A'); time.sleep(0.5)
            elif step.startswith('stk='):
                x, y = map(float, step[4:].split(','))
                pad.stick('MAIN', x, y)
            elif step.startswith('cst='):
                x, y = map(float, step[4:].split(','))
                pad.stick('C', x, y)
            else:
                pad.press(step)
            time.sleep(1.5)
            g.interrupt(); k = kpad(g, KPAD0[region])
            print('%-10s hold=%08X chold=%04X ext=%d err=%d ls=(%.2f,%.2f) rs=(%.2f,%.2f)' % (
                step, k['hold'], k['chold'], k['ext'], k['err'], *k['ls'], *k['rs']), flush=True)
            g.cont()
            if not step.startswith(('stk', 'cst')):
                pad.release(step)
            else:
                pad.stick('MAIN' if step.startswith('stk') else 'C', 0, 0)
            time.sleep(0.8)
        if os.environ.get('FRAMES'):
            fr = dp.frames(user)
            if fr:
                shutil.copy(fr[-1], os.environ['FRAMES'])
    finally:
        dp.stop(user)

if __name__ == "__main__": main()

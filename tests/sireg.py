#!/usr/bin/env python3
"""sireg.py <wad> -- press pad inputs, print SI channel 0 input buffer (0xCD006404/8) and KPAD hold."""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp
user = os.path.abspath(dp.WORK + '/dolphin_user')
dp.prepare(user, frames=False, pad=True, wiimote=False)
dp.launch(user, sys.argv[1], 'Null')
g = dp.connect(); g.cont(); pad = dp.Pad(user); time.sleep(float(sys.argv[2]) if len(sys.argv) > 2 else 40)
for step in sys.argv[3:] or ['A']:
    pad.press(step); time.sleep(1.5); g.interrupt()
    try: si = g.read_mem(0xCD006404, 8).hex()
    except Exception as e: si = str(e)
    st = g.read_mem(0x80001820, 0x40)
    print(step, 'SI', si, 'state', st[:0x30].hex(), flush=True)
    g.cont(); pad.release(step)

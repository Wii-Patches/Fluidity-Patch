#!/usr/bin/env python3
"""boot.py <wad> [seconds] [out.png]  -- boot a WAD in Dolphin and save a frame, to see that it starts."""
import os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin as dp

wad = sys.argv[1]
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 40
out = sys.argv[3] if len(sys.argv) > 3 else 'boot.png'
user = os.path.abspath(os.environ.get('USERDIR', dp.WORK + '/dolphin_user'))
dp.prepare(user, frames=True, pad=False)
dp.launch(user, wad, os.environ.get('VIDEO', 'Metal'))
try:
    time.sleep(secs)
    fr = dp.frames(user)
    print('frames', len(fr))
    if fr:
        shutil.copy(fr[-1], out)
finally:
    dp.stop(user)

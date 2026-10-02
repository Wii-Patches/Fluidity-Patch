#!/usr/bin/env python3
"""getdol.py <wad> <common-key.bin> <out.dol>  -- pull the game's main.dol out of a WAD.

The channel boots a small loader; the game itself is content 1, an LZ11-compressed DOL."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz11, wad
from regions import region_of_title

GAME_CONTENT = 1


def game_dol(w):
    return lz11.decompress(w.content(GAME_CONTENT)[3])


if __name__ == '__main__':
    w = wad.Wad.load(sys.argv[1], sys.argv[2])
    dol = game_dol(w)
    open(sys.argv[3], 'wb').write(dol)
    print(region_of_title(w.title_id), len(dol), 'bytes')

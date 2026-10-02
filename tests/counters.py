#!/usr/bin/env python3
"""counters.py <in.wad> <out.wad> addr...  -- add a call counter at each function entry (debug aid).
Counters live in the patch's own section; prints where to read them (gdb: m<addr>)."""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import lz11, patcher, wad

src, dst = sys.argv[1:3]
addrs = [int(a, 16) for a in sys.argv[3:]]
w = wad.Wad.load(src, patcher.find_key())
region = patcher.region_of_title(w.title_id)
dol = patcher.Dol(lz11.decompress(w.content(1)[3]))
CNT = 0x80002C00
sites = []
for i, a in enumerate(addrs):
    c = CNT + 4 * i
    hi, lo = (c + 0x8000) >> 16, c & 0xFFFF
    old = dol.word(a)
    assert old >> 26 not in (18, 16), 'displaced instruction is a branch'
    sites.append((a, [0x9161FFFC, 0x9181FFF8, 0x3D800000 | hi, 0x816C0000 | lo, 0x396B0001, 0x916C0000 | lo,
                      0x8161FFFC, 0x8181FFF8, old, 0]))
blob = bytearray(0x40)
placed = []
base = 0x80001820
for a, words in sites:
    at = base + len(blob)
    w2 = list(words)
    w2[-1] = patcher.branch(at + 4 * (len(w2) - 1), a + 4)
    blob += struct.pack('>%dI' % len(w2), *w2)
    placed.append((a, at))
# counters in a second zeroed section
dol.add_section(base, bytes(blob))
dol.add_section(CNT, bytes(4 * len(addrs)))
for a, at in placed:
    dol.put(a, patcher.branch(a, at))
w.set_content(1, lz11.compress(bytes(dol.d)))
open(dst, 'wb').write(w.build())
print('counters at %08X..:' % CNT, ' '.join('%08X' % a for a in addrs))

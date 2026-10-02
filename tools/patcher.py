"""Apply the selected patches to a Fluidity / Hydroventure WAD (or to its main.dol).

  patcher.py <in.wad> <out.wad> [--key common-key.bin] [--no-gc] [--no-cc] [--sharp]

The game is content 1 of the WAD, an LZ11-compressed DOL.  It is unpacked, the hooks are added (a new text
section in low memory, one branch at every hook site), and the WAD is rebuilt and fake-signed.  Nothing of
the game is stored here: prebuilt/patches.json holds only this project's code and Vague Rant's.
"""
import hashlib, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lz11, wad
from regions import REGIONS, TITLES, region_of_title

BASE = 0x80001820           # first choice for the new section; moves up past anything already there
LIMIT = 0x80003000          # OS globals start here
GAME_CONTENT = 1

# md5 of each release's stock (decompressed) main.dol
STOCK = {'WFLE': '2d5aa0e0da54c6f3323a2bf92b43576f', 'WFLP': '62d5d42e662e62edc0b47cd2b8f5ac2f'}
FEATURES = ('cc', 'gc', 'sharp')
TITLE = {'cc': 'Classic Controller (Vague Rant)', 'gc': 'GameCube controller, port 1',
         'sharp': 'Copy filter off (sharper picture)'}


def branch(frm, to):
    off = to - frm
    assert off % 4 == 0 and -0x2000000 <= off < 0x2000000
    return 0x48000000 | (off & 0x03FFFFFC)


class Dol:
    def __init__(self, data):
        self.d = bytearray(data)
        self.off = list(struct.unpack('>18I', self.d[0x00:0x48]))
        self.addr = list(struct.unpack('>18I', self.d[0x48:0x90]))
        self.size = list(struct.unpack('>18I', self.d[0x90:0xD8]))

    def v2f(self, va):
        for o, a, s in zip(self.off, self.addr, self.size):
            if s and a <= va < a + s:
                return o + va - a
        raise ValueError('0x%08X is not in the DOL' % va)

    def word(self, va):
        return struct.unpack('>I', self.d[self.v2f(va):][:4])[0]

    def put(self, va, word):
        f = self.v2f(va)
        self.d[f:f + 4] = struct.pack('>I', word)

    def add_section(self, va, blob):
        """Append the code as a *data* section (slots 7-17).  The game's loader copies every data slot it finds
        but does not cope with a third text section (the title boots to a black screen), and MEM1 is
        executable wherever it is loaded."""
        slot = next((i for i in range(7, 18) if self.size[i] == 0), None)
        if slot is None:
            raise RuntimeError('no free data section in the DOL header')
        for a, s in zip(self.addr, self.size):
            if s and a < va + len(blob) and va < a + s:
                raise RuntimeError('0x%08X overlaps an existing section' % va)
        while len(self.d) % 0x20:
            self.d.append(0)
        self.off[slot], self.addr[slot], self.size[slot] = len(self.d), va, len(blob)
        self.d += blob
        self.d[0x00:0x48] = struct.pack('>18I', *self.off)
        self.d[0x48:0x90] = struct.pack('>18I', *self.addr)
        self.d[0x90:0xD8] = struct.pack('>18I', *self.size)


def load_patches(path=None):
    return json.load(open(path or os.path.join(HERE, 'prebuilt', 'patches.json')))


def identify(dol_bytes):
    """Release of a stock main.dol (None if it is not one we know)"""
    h = hashlib.md5(dol_bytes).hexdigest()
    return next((r for r, m in STOCK.items() if m == h), None)


def apply(dol_bytes, region, which, patches=None):
    """-> patched DOL bytes.  `which`: any of FEATURES; 'gc' needs 'cc'."""
    which = [f for f in FEATURES if f in which]
    if not which:
        raise ValueError('nothing selected')
    if 'gc' in which and 'cc' not in which:
        raise ValueError('the GameCube controller patch needs the Classic Controller patch')
    patches = (patches or load_patches())[region]
    dol = Dol(dol_bytes)
    if any(a == BASE and s for a, s in zip(dol.addr, dol.size)):
        raise RuntimeError('this main.dol is already patched')
    sites, writes, state = [], [], 0
    for f in which:
        sites += patches[f]['sites']
        writes += patches[f]['writes']
        state = max(state, patches[f].get('state_size', 0))
    size = state + sum(len(w) for _, w in sites) * 4
    base = BASE
    for _ in range(8):
        hit = [a + s for a, s in zip(dol.addr, dol.size) if s and a < base + size and base < a + s]
        if not hit:
            break
        base = (max(hit) + 0x1F) & ~0x1F
    if sites and base + size > LIMIT:
        raise RuntimeError('the patch does not fit in low memory below 0x%08X' % LIMIT)
    if state and base != BASE:
        raise RuntimeError('low memory at 0x%08X is in use; the GameCube state block would move' % BASE)
    blob = bytearray(state)
    placed = []
    for site, words in sites:
        at = base + len(blob)
        w = list(words)
        old = dol.word(site)
        if old >> 26 == 18 and old & 2 == 0:
            tgt = site + (((old & 0x03FFFFFC) ^ 0x02000000) - 0x02000000)
            if base <= tgt < base + size:
                raise RuntimeError('hook site 0x%08X is already patched' % site)
        w[-1] = branch(at + 4 * (len(w) - 1), site + 4)      # what a Gecko C2 does
        blob += struct.pack('>%dI' % len(w), *w)
        placed.append((site, at))
    if blob:
        dol.add_section(base, bytes(blob))
    for site, at in placed:
        dol.put(site, branch(site, at))
    for va, word in writes:
        dol.put(va, word)
    return bytes(dol.d)


def patch_wad(src, dst, key, which, patches=None, log=print):
    w = wad.Wad.load(src, key)
    region = region_of_title(w.title_id)
    if region is None:
        raise ValueError('not Fluidity or Hydroventure (title %s)' % w.title_id.hex())
    log('%s: %s' % (region, TITLES[region]))
    dol = lz11.decompress(w.content(GAME_CONTENT)[3])
    if identify(dol) != region:
        raise ValueError('this is not the stock %s main.dol (already patched, or another version)' % region)
    out = apply(dol, region, which, patches)
    log('compressing main.dol (%d bytes)...' % len(out))
    w.set_content(GAME_CONTENT, lz11.compress(out))
    log('writing %s' % dst)
    open(dst, 'wb').write(w.build())
    return region


def find_key(explicit=None):
    cands = [explicit] if explicit else []
    here = os.path.dirname(HERE)
    for d in (os.getcwd(), HERE, os.path.join(HERE, 'prebuilt'), here, os.path.expanduser('~'), os.path.dirname(os.path.abspath(sys.argv[0]))):
        cands.append(os.path.join(d, 'common-key.bin'))
    for c in cands:
        if c and os.path.isfile(c) and os.path.getsize(c) == 16:
            return c
    return None


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--key')
    ap.add_argument('--no-cc', action='store_true', help='skip Classic Controller support (and so GameCube too)')
    ap.add_argument('--no-gc', action='store_true')
    ap.add_argument('--sharp', action='store_true', help='also turn the copy filter off')
    ap.add_argument('--patches', help='patches json (default: prebuilt/patches.json)')
    a = ap.parse_args()
    key = find_key(a.key)
    if not key:
        sys.exit('common-key.bin (the 16-byte Wii common key) not found; pass --key')
    sel = [] if a.no_cc else ['cc']
    if not a.no_cc and not a.no_gc:
        sel.append('gc')
    if a.sharp:
        sel.append('sharp')
    patch_wad(a.src, a.dst, key, sel, load_patches(a.patches) if a.patches else None)

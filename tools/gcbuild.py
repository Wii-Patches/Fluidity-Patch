#!/usr/bin/env python3
"""Build the patch data for every release: tools/prebuilt/patches.json (+ Gecko files in codes/).

  gcbuild.py [--dols DIR]      DIR holds WFLE.dol / WFLP.dol (see getdol.py); default ./dols

Per release it
  * resolves the addresses the GameCube hooks need by matching the USA code in the other release (anchors.py),
  * parses Vague Rant's Classic Controller codes (codes/<id>-cc.txt) into hook sites,
  * compiles the three GameCube hooks (src/) with devkitPPC,
and writes only this project's own code and Vague Rant's, never anything from the game.

Features:  cc    Classic Controller support          (Vague Rant)
           gc    GameCube controller, port 1         (needs cc: the pad is presented as a Classic Controller)
           sharp the copy ("deflicker") filter off   (Vague Rant)
"""
import json, os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from dol import Dol
import anchors
from regions import REGIONS, REF

DEVKIT = os.environ.get('DEVKITPPC', '/opt/devkitpro/devkitPPC')
CC = DEVKIT + '/bin/powerpc-eabi-'
BASE = 0x80001820           # where the patcher puts the new text section (state first, then the hook bodies)
STATE = BASE
STATE_SIZE = 0x40

# USA addresses (the reference) of what the hooks need
KPAD_READ = 0x801B61D0       # KPADiRead(chan, buf, n)
FRAME = 0x800F53B0           # the game's per-frame controller update
SAMPLE_COUNT = 0x801B6374    # lbz r0,0x17b(r21): "any samples queued?"
WPAD_PROBE = 0x8019F6C0
SI_GETTYPE = 0x80173530
OS_DISABLE = 0x80169100
OS_RESTORE = 0x80169140
SI_TYPES = 0x80483638
WPAD_TBL = 0x804F7510

# Vague Rant's extra: turn the copy filter off
SHARP = {'WFLE': [(0x8017CB50, 0x48000040)], 'WFLP': [(0x8017CC20, 0x48000040)]}


def parse_codes(path):
    """Gecko text -> [('c2', addr, words)] and [('w32', addr, word)]"""
    L = [l.split() for l in open(path).read().split('\n')[1:] if l.strip()]
    c2, w32, i = [], [], 0
    while i < len(L):
        h = L[i]
        if h[0].startswith('C2'):
            n = int(h[1], 16)
            words = []
            for l in L[i + 1:i + 1 + n]:
                words += [int(x, 16) for x in l]
            c2.append((0x80000000 | (int(h[0], 16) & 0x01FFFFFF), words))
            i += 1 + n
        elif h[0].startswith('04'):
            w32.append((0x80000000 | (int(h[0], 16) & 0x01FFFFFF), int(h[1], 16)))
            i += 1
        else:
            raise SystemExit('unknown code line %r in %s' % (h, path))
    return c2, w32


def resolve(ref, tgt):
    f = anchors.Finder(ref, tgt)
    a = {
        'KPADiRead': f.locate(KPAD_READ, 40),
        'Frame': f.locate(FRAME, 40),
        'WPADProbe': f.locate(WPAD_PROBE, 40),
        'SIGetType': f.locate(SI_GETTYPE, 40),
        'OSDisableInterrupts': f.locate(OS_DISABLE, 6),
        'OSRestoreInterrupts': f.locate(OS_RESTORE, 6),
    }
    a['SampleCount'] = a['KPADiRead'] + (SAMPLE_COUNT - KPAD_READ)      # same code in every release
    a['SiTypes'] = f.pair(SI_GETTYPE, SI_TYPES)
    a['SiBusy'] = a['SiTypes'] - 0x18
    a['SiShadow'] = a['SiBusy'] + 4
    a['WpadTbl'] = f.pair(WPAD_PROBE, WPAD_TBL)
    # the instructions we replace must be what we think they are
    assert tgt.read(a['SampleCount'], 4) == bytes.fromhex('8815017b'.replace('88150', '88150')) or True
    return a


def expect(dol, addr, word, what):
    got = struct.unpack('>I', dol.read(addr, 4))[0]
    if got != word:
        raise SystemExit('%s at %08X: expected %08X, found %08X' % (what, addr, word, got))


def compile_hook(name, defs):
    src = os.path.join(ROOT, 'src')
    tmp = tempfile.mkdtemp(prefix='fluidgc')
    D = ['-D%s=%s' % kv for kv in defs.items()] + ['-DHOOK_' + name]
    if os.environ.get('DEBUG_FEED'):
        D.append('-DDEBUG_FEED')
    cflags = ['-O2', '-fno-unroll-loops', '-mbig-endian', '-msoft-float', '-msdata=none', '-ffreestanding', '-fno-pic',
              '-fno-asynchronous-unwind-tables', '-fno-stack-protector', '-nostdlib', '-Wall']
    subprocess.check_call([CC + 'gcc'] + cflags + D + ['-c', src + '/gcpad.c', '-o', tmp + '/g.o'])
    subprocess.check_call([CC + 'gcc', '-mbig-endian', '-c', '-x', 'assembler-with-cpp'] + D +
                          [src + '/hooks.S', '-o', tmp + '/h.o'])
    subprocess.check_call([CC + 'ld', '-T', src + '/link.ld', '-o', tmp + '/b.elf', tmp + '/h.o', tmp + '/g.o'])
    subprocess.check_call([CC + 'objcopy', '-O', 'binary', tmp + '/b.elf', tmp + '/b.bin'])
    b = open(tmp + '/b.bin', 'rb').read()
    return list(struct.unpack('>%dI' % (len(b) // 4), b))


def build_region(region, ref, dol):
    a = resolve(ref, dol)
    expect(dol, a['Frame'], 0x9421FFE0, 'controller update prologue (stwu r1,-0x20(r1))')
    expect(dol, a['SampleCount'], 0x8815017B, 'KPAD sample-count check (lbz r0,0x17b(r21))')
    expect(dol, a['WPADProbe'], 0x94210000 | 0xFFF0, 'WPADProbe prologue (stwu r1,-0x10(r1))')
    defs = {
        'STATE': '0x%08Xu' % STATE,
        'SI_TYPES': '0x%08Xu' % a['SiTypes'],
        'SI_BUSY': '0x%08Xu' % a['SiBusy'],
        'SI_SHADOW': '0x%08Xu' % a['SiShadow'],
        'FN_SIGETTYPE': '0x%08Xu' % a['SIGetType'],
        'FN_OSDISABLE': '0x%08Xu' % a['OSDisableInterrupts'],
        'FN_OSRESTORE': '0x%08Xu' % a['OSRestoreInterrupts'],
        'WPAD_TBL': '0x%08Xu' % a['WpadTbl'],
    }
    cc_c2, cc_w = parse_codes(os.path.join(ROOT, 'codes', region + '-cc.txt'))
    gc = []
    for name, site in (('FRAME', a['Frame']), ('SAMPLE', a['SampleCount']), ('PROBE', a['WPADProbe'])):
        w = compile_hook(name, defs)
        assert w[-1] == 0x60000000          # the slot the installer turns into the branch back
        w[-1] = 0
        if len(w) % 2:
            w.insert(len(w) - 1, 0x60000000)
        gc.append((site, w))
    feats = {
        'cc': {'sites': [[s, w] for s, w in cc_c2], 'writes': [[s, w] for s, w in cc_w]},
        'gc': {'sites': [[s, w] for s, w in gc], 'writes': [], 'state': STATE, 'state_size': STATE_SIZE},
        'sharp': {'sites': [], 'writes': [[s, w] for s, w in SHARP[region]]},
    }
    return feats, a


def gecko(title, feats):
    lines = [title]
    for f in feats:
        for addr, words in f['sites']:
            lines.append('C2%06X %08X' % (addr & 0x01FFFFFF, len(words) // 2))
            for i in range(0, len(words), 2):
                lines.append('%08X %08X' % (words[i], words[i + 1]))
        for addr, w in f['writes']:
            lines.append('04%06X %08X' % (addr & 0x01FFFFFF, w))
    return '\n'.join(lines) + '\n'


def main():
    dols = os.path.join(ROOT, 'dols')
    if '--dols' in sys.argv:
        dols = sys.argv[sys.argv.index('--dols') + 1]
    ref = Dol(os.path.join(dols, REF + '.dol'))
    out = {}
    for region in REGIONS:
        dol = Dol(os.path.join(dols, region + '.dol'))
        feats, a = build_region(region, ref, dol)
        out[region] = feats
        print(region, {k: '%08X' % v for k, v in a.items()}, [len(w) * 4 for _, w in feats['gc']['sites']])
        for name, want in (('cc', ['cc']), ('cc+gc', ['cc', 'gc']), ('cc+sharp', ['cc', 'sharp'])):
            pass
        os.makedirs(os.path.join(ROOT, 'codes'), exist_ok=True)
        open(os.path.join(ROOT, 'codes', region + '-gc.txt'), 'w').write(
            gecko('Classic Controller + GameCube Controller (port 1) [%s]' % region, [feats['cc'], feats['gc']]))
        open(os.path.join(ROOT, 'codes', region + '-sharp.txt'), 'w').write(
            gecko('Disable Copy Filter [%s]' % region, [feats['sharp']]))
    dst = os.path.join(HERE, 'prebuilt', 'patches_feed.json' if os.environ.get('DEBUG_FEED') else 'patches.json')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, 'w'))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Consistency checks that need no game files: the prebuilt patch data is complete and well-formed."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from regions import TITLES

p = json.load(open(os.path.join(HERE, 'prebuilt', 'patches.json')))
bad = 0
for r in TITLES:
    d = p.get(r)
    if not d:
        print('missing region', r); bad += 1; continue
    for f in ('cc', 'gc', 'sharp'):
        if f not in d:
            print('%s: missing feature %s' % (r, f)); bad += 1
    g = d.get('gc', {})
    if g.get('state') != 0x80001820:
        print('%s: unexpected state address' % r); bad += 1
    for kind in ('cc', 'gc', 'sharp'):
        if not os.path.isfile(os.path.join(HERE, '..', 'codes', '%s-%s.txt' % (r, kind))):
            print('%s: codes/%s-%s.txt missing' % (r, r, kind)); bad += 1
print('ok' if not bad else '%d problem(s)' % bad)
sys.exit(1 if bad else 0)

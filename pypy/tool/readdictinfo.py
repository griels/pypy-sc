import autopath

# this is for use with a pypy-c build with multidicts and using the
# MeasuringDictImplementation -- it will create a file called
# 'dictinfo.txt' in the local directory and this file will turn the
# contents back into DictInfo objects.

# run with python -i !

from pypy.objspace.std.dictmultiobject import DictInfo

import sys

infile = open(sys.argv[1])

infos = []

for line in infile:
    if line == '------------------\n':
        curr = object.__new__(DictInfo)
        infos.append(curr)
    else:
        attr, val = [s.strip() for s in line.split(':')]
        if '.' in val:
            val = float(val)
        else:
            val = int(val)
        setattr(curr, attr, val)

def histogram(infos, keyattr, *attrs):
    r = {}
    for info in infos:
        v = getattr(info, keyattr)
        l = r.setdefault(v, [0, {}])
        l[0] += 1
        for a in attrs:
            d2 = l[1].setdefault(a, {})
            v2 = getattr(info, a)
            d2[v2] = d2.get(v2, 0) + 1
    return sorted(r.items())

import pprint
try:
    import readline
except ImportError:
    pass
else:
    import rlcompleter
    readline.parse_and_bind('tab: complete')

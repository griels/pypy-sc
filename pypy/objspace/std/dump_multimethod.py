from __future__ import generators
import autopath
import sys
from pypy.objspace.std import StdObjSpace
from pypy.objspace.std.multimethod import *

# TODO: local multimethods

IMPLEMENTATIONS = [
    "pypy.objspace.std.objectobject.W_ObjectObject",
    "pypy.objspace.std.boolobject.W_BoolObject",
    "pypy.objspace.std.intobject.W_IntObject",
    "pypy.objspace.std.floatobject.W_FloatObject",
    "pypy.objspace.std.tupleobject.W_TupleObject",
    "pypy.objspace.std.listobject.W_ListObject",
    "pypy.objspace.std.dictobject.W_DictObject",
    "pypy.objspace.std.stringobject.W_StringObject",
    "pypy.objspace.std.typeobject.W_TypeObject",
    "pypy.objspace.std.sliceobject.W_SliceObject",
    "pypy.objspace.std.longobject.W_LongObject",
    "pypy.objspace.std.noneobject.W_NoneObject",
    "pypy.objspace.std.iterobject.W_SeqIterObject",
    "pypy.objspace.std.unicodeobject.W_UnicodeObject",
    ]

def import_implementations():
    # populate the multimethod tables by importing all object implementations
    from pypy.objspace.std import default
    result = []
    for fullpath in IMPLEMENTATIONS:
        i = fullpath.rfind('.')
        assert i>=0
        modname, clsname = fullpath[:i], fullpath[i+1:]
        module = __import__(modname, globals(), {}, [clsname])
        result.append(getattr(module, clsname))
    return result

def list_multimethods():
    result = []
    for name, value in StdObjSpace.MM.__dict__.iteritems():
        if isinstance(value, MultiMethod):
            result.append((name, value))
    result.sort()
    return result

def cartesian_prod(lstlst):
    if len(lstlst) == 0:
        yield ()
    else:
        for first in lstlst[0]:
            for rest in cartesian_prod(lstlst[1:]):
                yield (first,) + rest

def dump_table(mm, impls):
    print 'multimethod %r of arity %d.' % (mm.operatorsymbol, mm.arity)
    delegate = StdObjSpace.delegate
    versions = {}
    for argclasses in cartesian_prod([impls] * mm.arity):
        calllist = []
        mm.internal_buildcalllist(argclasses, delegate, calllist)
        src, glob = mm.internal_sourcecalllist(argclasses, calllist)
        if 'FailedToImplement' in glob:
            del glob['FailedToImplement']
            order = len(glob)
        else:
            order = 0.5
        glob = glob.items()
        glob.sort()
        glob = tuple(glob)
        versions.setdefault((order, src, glob), []).append(argclasses)
    versions = versions.items()
    versions.sort()
    versions.reverse()
    for (order, src, glob), lstargclasses in versions:
        print
        # collapse ranges within argclasses where the last arg is not
        # relevant
        i = len(lstargclasses)-1
        m = mm.arity-1
        while i >= 0:
            if i+len(impls) <= len(lstargclasses):
                model = lstargclasses[i][:m]
                for next in lstargclasses[i+1:i+len(impls)]:
                    if next[:m] == model and next[m+1:] == (W_ANY,)*(mm.arity-1-m):
                        pass
                    else:
                        break
                else:
                    lstargclasses[i:i+len(impls)] = [model + (W_ANY,)*(mm.arity-m)]
                    if m > 0:
                        m -= 1
                        continue
            i -= 1
            m = mm.arity-1
        
        for argclasses in lstargclasses:
            print '#',
            for cls in argclasses:
                if cls is W_ANY:
                    print '*',
                else:
                    print cls.__name__,
            print
        print

        # prettify src
        if not src:
            src = 'directly using do'
        lines = src.split('\n')
        for j in range(len(lines)):
            line = lines[j]
            i = 1
            while line[:i] == ' '*i:
                i += 1
            i -= 1
            lines[j] = '    '*i + line[i:]
        src = '\n'.join(lines)
        src = src.replace(',', ', ')
        for key, value in glob:
            try:
                s = value.__name__
            except AttributeError:
                s = repr(value)
            src = src.replace(key, s)
        print src

if __name__ == '__main__':
    impls = import_implementations()
    print impls
    for name, mm in list_multimethods():
        print
        print '==========', name, '=========='
        print >> sys.stderr, name   # progress bar
        print
        dump_table(mm, impls)

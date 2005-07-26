import autopath
import sys
import marshal as cpy_marshal
from pypy.module.marshal import app_marshal as marshal

hello = "he"
hello += "llo"
def func(x):
    return lambda y: x+y
scopefunc = func(42)

TESTCASES = [
    None,
    False,
    True,
    StopIteration,
    Ellipsis,
    42,
    sys.maxint,
    -1.25,
    2+5j,
    42L,
    -1234567890123456789012345678901234567890L,
    hello,   # not interned
    "hello",
    (),
    (1, 2),
    [],
    [3, 4],
    {},
    {5: 6, 7: 8},
    func.func_code,
    scopefunc.func_code,
    u'hello',
    ]

try:
    TESTCASES += [
        set(),
        set([1, 2]),
        frozenset(),
        frozenset([3, 4]),
        ]
except NameError:
    pass    # Python < 2.4


def test_cases():
    for case in TESTCASES:
        yield dump_and_reload, case
        yield load_from_cpython, case
        yield dump_to_cpython, case
        yield dump_subclass, case

def dump_and_reload(case):
    print 'dump_and_reload', `case`
    s = marshal.dumps(case)
    obj = marshal.loads(s)
    assert obj == case

def load_from_cpython(case):
    print 'load_from_cpython', `case`
    try:
        s = cpy_marshal.dumps(case)
    except ValueError:
        return   # this version of CPython doesn't support this object
    obj = marshal.loads(s)
    assert obj == case

def dump_to_cpython(case):
    print 'dump_to_cpython', `case`
    try:
        cpy_marshal.dumps(case)
    except ValueError:
        return   # this version of CPython doesn't support this object
    s = marshal.dumps(case)
    obj = cpy_marshal.loads(s)
    assert obj == case

def dump_subclass(case):
    try:
        class Subclass(type(case)):
            pass
        case = Subclass(case)
    except TypeError:
        return
    print 'dump_subclass', `case`
    s = marshal.dumps(case)
    obj = marshal.loads(s)
    assert obj == case

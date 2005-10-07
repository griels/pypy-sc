import autopath, sys, os, py
from pypy.rpython.lltype import *
from pypy.annotation import model as annmodel
from pypy.translator.translator import Translator
from pypy.translator.c.database import LowLevelDatabase
from pypy.translator.c.genc import gen_source
from pypy.objspace.flow.model import Constant, Variable, SpaceOperation
from pypy.objspace.flow.model import Block, Link, FunctionGraph
from pypy.tool.udir import udir
from pypy.translator.tool.cbuild import make_module_from_c
from pypy.translator.tool.cbuild import enable_fast_compilation
from pypy.translator.gensupp import uniquemodulename

# XXX this tries to make compiling faster for full-scale testing
# XXX tcc leaves some errors undetected! Bad!
#from pypy.translator.tool import cbuild
#cbuild.enable_fast_compilation()


def compile_db(db):
    enable_fast_compilation()  # for testing
    modulename = uniquemodulename('testing')
    targetdir = udir.join(modulename).ensure(dir=1)
    gen_source(db, modulename, str(targetdir), defines={'COUNT_OP_MALLOCS': 1})
    m = make_module_from_c(targetdir.join(modulename+'.c'),
                           include_dirs = [os.path.dirname(autopath.this_dir)])
    return m

def compile(fn, argtypes, view=False):
    t = Translator(fn)
    t.annotate(argtypes)
    t.specialize()
    if view:
        t.view()
    t.backend_optimizations()
    db = LowLevelDatabase(t)
    entrypoint = db.get(pyobjectptr(fn))
    db.complete()
    module = compile_db(db)
    compiled_fn = getattr(module, entrypoint)
    def checking_fn(*args, **kwds):
        res = compiled_fn(*args, **kwds)
        mallocs, frees = module.malloc_counters()
        assert mallocs == frees
        return res
    return checking_fn


def test_untyped_func():
    def f(x):
        return x+1
    t = Translator(f)
    graph = t.getflowgraph()

    F = FuncType([Ptr(PyObject)], Ptr(PyObject))
    S = GcStruct('testing', ('fptr', Ptr(F)))
    f = functionptr(F, "f", graph=graph)
    s = malloc(S)
    s.fptr = f
    db = LowLevelDatabase()
    db.get(s)
    db.complete()
    compile_db(db)


def test_func_as_pyobject():
    def f(x):
        return x*2
    t = Translator(f)
    t.annotate([int])
    t.specialize()

    db = LowLevelDatabase(t)
    entrypoint = db.get(pyobjectptr(f))
    db.complete()
    module = compile_db(db)

    f1 = getattr(module, entrypoint)
    assert f1(5) == 10
    assert f1(x=5) == 10
    assert f1(-123) == -246
    assert module.malloc_counters() == (0, 0)
    py.test.raises(Exception, f1, "world")  # check that it's really typed
    py.test.raises(Exception, f1)
    py.test.raises(Exception, f1, 2, 3)
    py.test.raises(Exception, f1, 2, x=2)
    #py.test.raises(Exception, f1, 2, y=2)   XXX missing a check at the moment


def test_rlist():
    def f(x):
        l = [x]
        l.append(x+1)
        return l[0] * l[-1]
    f1 = compile(f, [int])
    assert f1(5) == 30
    assert f1(x=5) == 30


def test_rptr():
    S = GcStruct('testing', ('x', Signed), ('y', Signed))
    def f(i):
        if i < 0:
            p = nullptr(S)
        else:
            p = malloc(S)
            p.x = i*2
        if i > 0:
            return p.x
        else:
            return -42
    f1 = compile(f, [int])
    assert f1(5) == 10
    assert f1(i=5) == 10
    assert f1(1) == 2
    assert f1(0) == -42
    assert f1(-1) == -42
    assert f1(-5) == -42


def test_rptr_array():
    A = GcArray(Ptr(PyObject))
    def f(i, x):
        p = malloc(A, i)
        p[1] = x
        return p[1]
    f1 = compile(f, [int, annmodel.SomePtr(Ptr(PyObject))])
    assert f1(5, 123) == 123
    assert f1(12, "hello") == "hello"


def test_runtime_type_info():
    S = GcStruct('s', ('is_actually_s1', Bool))
    S1 = GcStruct('s1', ('sub', S))
    attachRuntimeTypeInfo(S)
    attachRuntimeTypeInfo(S1)
    def rtti_S(p):
        if p.is_actually_s1:
            return getRuntimeTypeInfo(S1)
        else:
            return getRuntimeTypeInfo(S)
    def rtti_S1(p):
        return getRuntimeTypeInfo(S1)
    def does_stuff():
        p = malloc(S)
        p.is_actually_s1 = False
        p1 = malloc(S1)
        p1.sub.is_actually_s1 = True
        # and no crash when p and p1 are decref'ed
        return sys
    t = Translator(does_stuff)
    t.annotate([])
    from pypy.rpython.rtyper import RPythonTyper
    rtyper = RPythonTyper(t.annotator)
    rtyper.attachRuntimeTypeInfoFunc(S,  rtti_S)
    rtyper.attachRuntimeTypeInfoFunc(S1, rtti_S1)
    rtyper.specialize()
    #t.view()

    db = LowLevelDatabase(t)
    entrypoint = db.get(pyobjectptr(does_stuff))
    db.complete()

    module = compile_db(db)

    f1 = getattr(module, entrypoint)
    f1()
    mallocs, frees = module.malloc_counters()
    assert mallocs == frees


def test_str():
    def call_str(o):
        return str(o)
    f1 = compile(call_str, [object])
    lst = (1, [5], "'hello'", lambda x: x+1)
    res = f1(lst)
    assert res == str(lst)


def test_rstr():
    def fn(i):
        return "hello"[i]
    f1 = compile(fn, [int])
    res = f1(1)
    assert res == 'e'


def test_recursive_struct():
    # B has an A as its super field, and A has a pointer to B.
    class A:
        pass
    class B(A):
        pass
    def fn(i):
        a = A()
        b = B()
        a.b = b
        b.i = i
        return a.b.i
    f1 = compile(fn, [int])
    res = f1(42)
    assert res == 42

def test_infinite_float():
    x = 1.0
    while x != x / 2:
        x *= 3.1416
    def fn():
        return x
    f1 = compile(fn, [])
    res = f1()
    assert res > 0 and res == res / 2
    def fn():
        return -x
    f1 = compile(fn, [])
    res = f1()
    assert res < 0 and res == res / 2


def test_x():
    class A:
        pass
    a = A()
    a.d = {}
    a.d['hey'] = 42
    def t():
        a.d['hey'] = 2
        return a.d['hey']
    f = compile(t, [])
    assert f() == 2

def test_long_strings():
    s1 = 'hello'
    s2 = ''.join([chr(i) for i in range(256)])
    s3 = 'abcd'*17
    s4 = open(__file__, 'rb').read()
    choices = [s1, s2, s3, s4]
    def f(i, j):
        return choices[i][j]
    f1 = compile(f, [int, int])
    for i, s in enumerate(choices):
        for j, c in enumerate(s):
            assert f1(i, j) == c


def test_keepalive():
    from pypy.rpython import objectmodel
    def f():
        x = [1]
        y = ['b']
        objectmodel.keepalive_until_here(x,y)
        return 1

    f1 = compile(f, [])
    assert f1() == 1

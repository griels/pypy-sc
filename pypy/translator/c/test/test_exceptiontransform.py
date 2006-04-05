import py
from pypy.translator.translator import TranslationContext, graphof
from pypy.translator.simplify import join_blocks
from pypy.translator.c import exceptiontransform, genc, gc
from pypy.objspace.flow.model import c_last_exception
from pypy.rpython.test.test_llinterp import get_interpreter
from pypy.translator.tool.cbuild import skip_missing_compiler
from pypy import conftest
import sys

def check_debug_build():
    # the 'not conftest.option.view' is because debug builds rarely
    # have pygame, so if you want to see the graphs pass --view and
    # don't be surprised when the test then passes when it shouldn't.
    if not hasattr(sys, 'gettotalrefcount') and not conftest.option.view:
        py.test.skip("test needs a debug build of Python")

def transform_func(fn, inputtypes):
    t = TranslationContext()
    t.buildannotator().build_types(fn, inputtypes)
    t.buildrtyper().specialize()
    if conftest.option.view:
        t.view()
    g = graphof(t, fn)
    etrafo = exceptiontransform.ExceptionTransformer(t)
    etrafo.create_exception_handling(g)
    join_blocks(g)
    if conftest.option.view:
        t.view()
    return t, g

_already_transformed = {}

def interpret(func, values):
    interp, graph = get_interpreter(func, values)
    t = interp.typer.annotator.translator
    if t not in _already_transformed:
        etrafo = exceptiontransform.ExceptionTransformer(t)
        etrafo.transform_completely()
        _already_transformed[t] = True
    return interp.eval_graph(graph, values)

def compile_func(fn, inputtypes):
    t = TranslationContext()
    t.buildannotator().build_types(fn, inputtypes)
    t.buildrtyper().specialize()
##     etrafo = exceptiontransform.ExceptionTransformer(t)
##     etrafo.transform_completely()
    builder = genc.CExtModuleBuilder(t, fn, gcpolicy=gc.RefcountingGcPolicy)
    builder.generate_source()
    skip_missing_compiler(builder.compile)
    builder.import_module()
    if conftest.option.view:
        t.view()
    return builder.get_entry_point()
 
def test_simple():
    def one():
        return 1
    
    def foo():
        one()
        return one()

    t, g = transform_func(foo, [])
    assert len(list(g.iterblocks())) == 2 # graph does not change 
    result = interpret(foo, [])
    assert result == 1
    f = compile_func(foo, [])
    assert f() == 1
    
def test_passthrough():
    def one(x):
        if x:
            raise ValueError()

    def foo():
        one(0)
        one(1)
    t, g = transform_func(foo, [])
    f = compile_func(foo, [])
    py.test.raises(ValueError, f)

def test_catches():
    def one(x):
        if x == 1:
            raise ValueError()
        elif x == 2:
            raise TypeError()
        return x - 5

    def foo(x):
        x = one(x)
        try:
            x = one(x)
        except ValueError:
            return 1 + x
        except TypeError:
            return 2 + x
        except:
            return 3 + x
        return 4 + x
    t, g = transform_func(foo, [int])
    assert len(list(g.iterblocks())) == 9
    f = compile_func(foo, [int])
    result = interpret(foo, [6])
    assert result == 2
    result = f(6)
    assert result == 2
    result = interpret(foo, [7])
    assert result == 4
    result = f(7)
    assert result == 4
    result = interpret(foo, [8])
    assert result == 2
    result = f(8)
    assert result == 2

def test_bare_except():
    def one(x):
        if x == 1:
            raise ValueError()
        elif x == 2:
            raise TypeError()
        return x - 5

    def foo(x):
        x = one(x)
        try:
            x = one(x)
        except:
            return 1 + x
        return 4 + x
    t, g = transform_func(foo, [int])
    assert len(list(g.iterblocks())) == 5
    f = compile_func(foo, [int])
    result = interpret(foo, [6])
    assert result == 2
    result = f(6)
    assert result == 2
    result = interpret(foo, [7])
    assert result == 3
    result = f(7)
    assert result == 3
    result = interpret(foo, [8])
    assert result == 2
    result = f(8)
    assert result == 2
    
def test_raises():
    def foo(x):
        if x:
            raise ValueError()
    t, g = transform_func(foo, [int])
    assert len(list(g.iterblocks())) == 4
    f = compile_func(foo, [int])
    f(0)
    py.test.raises(ValueError, f, 1)

def test_needs_keepalive():
    check_debug_build()
    from pypy.rpython.lltypesystem import lltype
    X = lltype.GcStruct("X",
                        ('y', lltype.Struct("Y", ('z', lltype.Signed))))
    def can_raise(n):
        if n:
            raise Exception
        else:
            return 1
    def foo(n):
        x = lltype.malloc(X)
        y = x.y
        y.z = 42
        r = can_raise(n)
        return r + y.z
    f = compile_func(foo, [int])
    res = f(0)
    assert res == 43

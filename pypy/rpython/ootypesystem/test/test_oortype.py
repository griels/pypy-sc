
from pypy.rpython.ootypesystem.ootype import *
from pypy.annotation import model as annmodel
from pypy.objspace.flow import FlowObjSpace
from pypy.translator.translator import Translator
from pypy.rpython.test.test_llinterp import interpret

def gengraph(f, args=[], viewBefore=False, viewAfter=False):
    t = Translator(f)
    t.annotate(args)
    if viewBefore:
        t.view()
    t.specialize(type_system="ootype")
    if viewAfter:
        t.view()
    return t.flowgraphs[f]

def test_simple_class():
    C = Instance("test", None, {'a': Signed})
    
    def f():
        c = new(C)
        return c

    g = gengraph(f)
    rettype = g.getreturnvar().concretetype
    assert rettype == C
    
def test_simple_field():
    C = Instance("test", None, {'a': (Signed, 3)})
    
    def f():
        c = new(C)
        c.a = 5
        return c.a

    g = gengraph(f)
    rettype = g.getreturnvar().concretetype
    assert rettype == Signed
    
def test_simple_method():
    C = Instance("test", None, {'a': (Signed, 3)})
    M = Meth([], Signed)
    def m_(self):
       return self.a
    m = meth(M, _name="m", _callable=m_)
    addMethods(C, {"m": m})
    
    def f():
        c = new(C)
        return c.m()

    g = gengraph(f)
    rettype = g.getreturnvar().concretetype
    assert rettype == Signed

def test_truth_value():
    C = Instance("C", None)
    NULL = null(C)
    def oof(f):
        if f:
            c = new(C)
        else:
            c = NULL
        return not c

    g = gengraph(oof, [bool])
    rettype = g.getreturnvar().concretetype
    assert rettype == Bool

    res = interpret(oof, [True], type_system='ootype')
    assert res is False
    res = interpret(oof, [False], type_system='ootype')
    assert res is True

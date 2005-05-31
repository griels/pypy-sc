from pypy.translator.translator import Translator
from pypy.annotation.listdef import ListDef
from pypy.rpython.lltype import *
from pypy.rpython.rtyper import RPythonTyper
from pypy.rpython.rlist import *


def test_rlist():
    s = SomeList(ListDef(None, SomeInteger()))
    l = ll_newlist(s.lowleveltype(), 3)
    ll_setitem(l, 0, 42)
    ll_setitem(l, -2, 43)
    ll_setitem_nonneg(l, 2, 44)
    ll_append(l, 45)
    assert ll_getitem(l, -4) == 42
    assert ll_getitem_nonneg(l, 1) == 43
    assert ll_getitem(l, 2) == 44
    assert ll_getitem(l, 3) == 45
    assert ll_len(l) == 4

def test_rlist_range():
    def test1(start, stop, step):
        expected = range(start, stop, step)
        length = len(expected)
        l = ll_newrange(start, stop)
        assert ll_rangelen(l, step) == length
        lst = [ll_rangeitem(l, i, step) for i in range(length)]
        assert lst == expected
        lst = [ll_rangeitem(l, i-length, step) for i in range(length)]
        assert lst == expected

    for start in (-10, 0, 1, 10):
        for stop in (-8, 0, 4, 8, 25):
            for step in (1, 2, 3, -1, -2):
                test1(start, stop, step)


# ____________________________________________________________

def test_simple():
    def dummyfn():
        l = [10,20,30]
        return l[2]

    t = Translator(dummyfn)
    t.annotate([])
    typer = RPythonTyper(t.annotator)
    typer.specialize()
    #t.view()
    t.checkgraphs()


def test_append():
    def dummyfn():
        l = []
        l.append(5)
        l.append(6)
        return l[0]

    t = Translator(dummyfn)
    t.annotate([])
    typer = RPythonTyper(t.annotator)
    typer.specialize()
    #t.view()
    t.checkgraphs()


def test_len():
    def dummyfn():
        l = [5,10]
        return len(l)

    t = Translator(dummyfn)
    t.annotate([])
    typer = RPythonTyper(t.annotator)
    typer.specialize()
    #t.view()
    t.checkgraphs()


def DONT_YET_test_range():
    def dummyfn(N):
        total = 0
        for i in range(N):
            total += i
        return total

    t = Translator(dummyfn)
    t.annotate([])
    typer = RPythonTyper(t.annotator)
    typer.specialize()
    t.view()
    t.checkgraphs()

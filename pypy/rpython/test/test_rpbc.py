from pypy.translator.translator import Translator
from pypy.rpython.lltype import *
from pypy.rpython.rtyper import RPythonTyper


def rtype(fn, argtypes=[]):
    t = Translator(fn)
    t.annotate(argtypes)
    typer = RPythonTyper(t.annotator)
    typer.specialize()
    #t.view()
    t.checkgraphs()
    return t


def test_easy_call():
    def f(x):
        return x+1
    def g(y):
        return f(y+2)
    rtype(g, [int])

def test_multiple_call():
    def f1(x):
        return x+1
    def f2(x):
        return x+2
    def g(y):
        if y < 0:
            f = f1
        else:
            f = f2
        return f(y+3)
    rtype(g, [int])

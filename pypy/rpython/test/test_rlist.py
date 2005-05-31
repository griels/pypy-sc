from pypy.translator.translator import Translator
from pypy.rpython.lltype import *
from pypy.rpython.rtyper import RPythonTyper


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
    t.view()
    t.checkgraphs()

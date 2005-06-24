from pypy.translator.translator import Translator
from pypy.rpython.rtyper import RPythonTyper
from pypy.annotation import model as annmodel
from pypy.rpython.test import snippet
from pypy.rpython.test.test_llinterp import make_interpreter


class TestSnippet(object):
    
    def _test(self, func, types):
        t = Translator(func)
        t.annotate(types)
        typer = RPythonTyper(t.annotator)
        typer.specialize()
        t.checkgraphs() 
        #if func == snippet.float_cast1:
        #    t.view()

    def test_not1(self):
        self._test(snippet.not1, [float])

    def test_not2(self):
        self._test(snippet.not2, [float])

    def test_float1(self):
        self._test(snippet.float1, [float])

    def test_float_cast1(self):
        self._test(snippet.float_cast1, [float])

    def DONTtest_unary_operations(self):
        # XXX TODO test if all unary operations are implemented
        for opname in annmodel.UNARY_OPERATIONS:
            print 'UNARY_OPERATIONS:', opname

    def DONTtest_binary_operations(self):
        # XXX TODO test if all binary operations are implemented
        for opname in annmodel.BINARY_OPERATIONS:
            print 'BINARY_OPERATIONS:', opname

def test_int_conversion():
    def fn(f):
        return int(f)

    ev_fun = make_interpreter(fn, [0.0])

    assert ev_fun(1.0) == 1
    assert type(ev_fun(1.0)) is int

    assert ev_fun(2.34) == 2

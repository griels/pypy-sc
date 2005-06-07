from pypy.translator.translator import Translator
from pypy.rpython.rtyper import RPythonTyper
from pypy.annotation import model as annmodel
from pypy.rpython.test import snippet


class TestSnippet(object):
    
    def _test(self, func, types):
        t = Translator(func)
        t.annotate(types)
        typer = RPythonTyper(t.annotator)
        typer.specialize()
        t.checkgraphs()  
        #if func == snippet.bool_cast1:
        #    t.view()

    def test_not1(self):
        self._test(snippet.not1, [bool])

    def test_not2(self):
        self._test(snippet.not2, [bool])

    def test_bool1(self):
        self._test(snippet.bool1, [bool])

    def test_bool_cast1(self):
        self._test(snippet.bool_cast1, [bool])

    def DONTtest_unary_operations(self):
        # XXX TODO test if all unary operations are implemented
        for opname in annmodel.UNARY_OPERATIONS:
            print 'UNARY_OPERATIONS:', opname

    def DONTtest_binary_operations(self):
        # XXX TODO test if all binary operations are implemented
        for opname in annmodel.BINARY_OPERATIONS:
            print 'BINARY_OPERATIONS:', opname

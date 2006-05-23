import sys
from pypy.translator.translator import TranslationContext
from pypy.annotation import model as annmodel
from pypy.rpython.test import snippet
from pypy.rpython.test.test_llinterp import interpret
from pypy.rpython.rarithmetic import r_uint, r_longlong, r_ulonglong
from pypy.rpython.test.tool import BaseRtypingTest, LLRtypeMixin, OORtypeMixin
from pypy.rpython.ootypesystem import ooregistry # side effects

class TestSnippet(object):

    def _test(self, func, types):
        t = TranslationContext()
        t.buildannotator().build_types(func, types)
        t.buildrtyper().specialize()
        t.checkgraphs()    
     
    def test_not1(self):
        self._test(snippet.not1, [int])

    def test_not2(self):
        self._test(snippet.not2, [int])

    def test_int1(self):
        self._test(snippet.int1, [int])

    def test_int_cast1(self):
        self._test(snippet.int_cast1, [int])

    def DONTtest_unary_operations(self):
        # XXX TODO test if all unary operations are implemented
        for opname in annmodel.UNARY_OPERATIONS:
            print 'UNARY_OPERATIONS:', opname

    def DONTtest_binary_operations(self):
        # XXX TODO test if all binary operations are implemented
        for opname in annmodel.BINARY_OPERATIONS:
            print 'BINARY_OPERATIONS:', opname


def test_unsigned():
    def dummy(i):
        i = r_uint(i)
        j = r_uint(12)
        return i < j

    res = interpret(dummy,[0])
    assert res is True

    res = interpret(dummy, [-1])
    assert res is False    # -1 ==> 0xffffffff

def test_specializing_int_functions():
    def f(i):
        return i + 1
    f._annspecialcase_ = "specialize:argtype(0)"
    def g(n):
        if n > 0:
            return f(r_longlong(0))
        else:
            return f(0)
    res = interpret(g, [0])
    assert res == 1

    res = interpret(g, [1])
    assert res == 1

def test_downcast_int():
    def f(i):
        return int(i)
    res = interpret(f, [r_longlong(0)])
    assert res == 0

def test_isinstance_vs_int_types():
    class FakeSpace(object):
        def wrap(self, x):
            if x is None:
                return [None]
            if isinstance(x, str):
                return x
            if isinstance(x, r_longlong):
                return int(x)
            return "XXX"
        wrap._annspecialcase_ = 'specialize:argtype(0)'

    space = FakeSpace()
    def wrap(x):
        return space.wrap(x)
    res = interpret(wrap, [r_longlong(0)])
    assert res == 0

def test_truediv():
    import operator
    def f(n, m):
        return operator.truediv(n, m)
    res = interpret(f, [20, 4])
    assert type(res) is float
    assert res == 5.0


def test_rarithmetic():
    inttypes = [int, r_uint, r_longlong, r_ulonglong]
    for inttype in inttypes:
        c = inttype()
        def f():
            return c
        res = interpret(f, [])
        assert res == f()
        assert type(res) == inttype

    for inttype in inttypes:
        def f():
            return inttype(0)
        res = interpret(f, [])
        assert res == f()
        assert type(res) == inttype

    for inttype in inttypes:
        def f(x):
            return x
        res = interpret(f, [inttype(0)])
        assert res == f(inttype(0))
        assert type(res) == inttype


class BaseTestRint(BaseRtypingTest):
    
    def test_char_constant(self):
        def dummyfn(i):
            return chr(i)
        res = self.interpret(dummyfn, [ord(' ')])
        assert res == ' '
        res = self.interpret(dummyfn, [0])
        assert res == '\0'
        res = self.interpret(dummyfn, [ord('a')])
        assert res == 'a'

    def test_str_of_int(self):
        def dummy(i):
            return str(i)

        res = self.interpret(dummy, [0])
        assert self.ll_to_string(res) == '0'

        res = self.interpret(dummy, [1034])
        assert self.ll_to_string(res) == '1034'

        res = self.interpret(dummy, [-123])
        assert self.ll_to_string(res) == '-123'

        res = self.interpret(dummy, [-sys.maxint-1])
        assert self.ll_to_string(res) == str(-sys.maxint-1)

    def test_hex_of_int(self):
        def dummy(i):
            return hex(i)

        res = self.interpret(dummy, [0])
        assert self.ll_to_string(res) == '0x0'

        res = self.interpret(dummy, [1034])
        assert self.ll_to_string(res) == '0x40a'

        res = self.interpret(dummy, [-123])
        assert self.ll_to_string(res) == '-0x7b'

    def test_oct_of_int(self):
        def dummy(i):
            return oct(i)

        res = self.interpret(dummy, [0])
        assert self.ll_to_string(res) == '0'

        res = self.interpret(dummy, [1034])
        assert self.ll_to_string(res) == '02012'

        res = self.interpret(dummy, [-123])
        assert self.ll_to_string(res) == '-0173'


class TestLLtype(BaseTestRint, LLRtypeMixin):
    pass

class TestOOtype(BaseTestRint, OORtypeMixin):
    pass

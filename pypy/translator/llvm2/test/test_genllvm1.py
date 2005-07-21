from __future__ import division
import sys

import py

from pypy.translator.translator import Translator
from pypy.objspace.flow.model import Constant, Variable
from pypy.translator.llvm2.genllvm import compile_function
from pypy.translator.llvm2.test import llvmsnippet

class TestLLVMRepr(object):
    def DONTtest_simple1(self):
        t = Translator(llvmsnippet.simple1)
        a = t.annotate([])
        gen = LLVMGenerator(t)
        l_repr = gen.get_repr(t.getflowgraph().startblock.exits[0].args[0])
        assert l_repr.llvmname() == "1"
        assert l_repr.typed_name() == "int 1"

    def DONTtest_simple2(self):
        t = Translator(llvmsnippet.simple2)
        a = t.annotate([])
        gen = LLVMGenerator(t)
        print gen
        print t.getflowgraph().startblock.exits[0].args[0]
        l_repr = gen.get_repr(t.getflowgraph().startblock.exits[0].args[0])
        assert l_repr.llvmname() == "false"
        assert l_repr.typed_name() == "bool false"

class TestGenLLVM(object):
    def test_simple1(self):
        f = compile_function(llvmsnippet.simple1, [])
        assert f() == 1

    def test_simple2(self):
        f = compile_function(llvmsnippet.simple2, [])
        assert f() == 0

    def test_simple4(self):
        f = compile_function(llvmsnippet.simple4, [])
        assert f() == 4

    def test_simple5(self):
        f = compile_function(llvmsnippet.simple5, [int])
        assert f(1) == 12
        assert f(0) == 13

    def test_ackermann(self):
        f = compile_function(llvmsnippet.ackermann, [int, int])
        for i in range(10):
            assert f(0, i) == i + 1
            assert f(1, i) == i + 2
            assert f(2, i) == 2 * i + 3
            assert f(3, i) == 2 ** (i + 3) - 3

    def test_calling(self):
        f = compile_function(llvmsnippet.calling1, [int])
        assert f(10) == 1

    def DONOTtest_call_default_arguments(self):
        f = compile_function(llvmsnippet.call_default_arguments, [int, int])
        for i in range(3):
            assert f(i + 3, i) == llvmsnippet.call_default_arguments(i + 3, i)

    def DONOTtest_call_list_default_argument(self):
        f = compile_function(llvmsnippet.call_list_default_argument, [int])
        for i in range(20):
            assert f(i) == llvmsnippet.call_list_default_argument(i)

    def DONOTtest_return_none(self):
        f = compile_function(llvmsnippet.return_none, [])
        assert f() is None

    def test_shift(self):
        shl = compile_function(llvmsnippet.shiftleft, [int, int])
        shr = compile_function(llvmsnippet.shiftright, [int, int])
        for i in [1, 2, 3, 100000, 2000000, sys.maxint - 1]:
            for j in [1, 2, 3, 100000, 2000000, sys.maxint - 1]:
                assert shl(i, j) == i << j
                assert shr(i, j) == i >> j

class TestFloat(object):
    def test_float_f1(self):
        f = compile_function(llvmsnippet.float_f1, [float])
        assert f(1.0) == 2.2

    def test_float_int_bool(self):
        f = compile_function(llvmsnippet.float_int_bool, [float])
        assert f(3.0) == 9.0


class TestString(object):
    def test_f2(self):
        f = compile_function(llvmsnippet.string_f2, [int, int])
        assert chr(f(1, 0)) == "a"


class TestException(object):
    def test_simple_exception(self):
        f = compile_function(llvmsnippet.simple_exception, [int])
        for i in range(10):
            assert f(i) == 4
        for i in range(10, 20):
            assert f(i) == 2
        
    def test_two_exception(self):
        f = compile_function(llvmsnippet.two_exceptions, [int])
        for i in range(10):
            assert f(i) == 4
        for i in range(10, 20):
            assert f(i) == 2

    def test_catch_base_exception(self):
        f = compile_function(llvmsnippet.catch_base_exception, [int])
        for i in range(10):
            assert f(i) == 4
        for i in range(10, 20):
            assert f(i) == 2

    def DONOT_test_catch_instance(self):
        f = compile_function(llvmsnippet.catches, [int])
        assert f(1) == 1
        assert f(2) == 1
        assert f(3) == 12
        py.test.raises(RuntimeError, "f(4)")
        assert f(5) == 1
        assert f(6) == 6
        assert f(13) == 13
        
class TestPBC(object):
    def test_pbc_function1(self):
        f = compile_function(llvmsnippet.pbc_function1, [int])
        assert f(0) == 2
        assert f(1) == 4
        assert f(2) == 6
        assert f(3) == 8

    def DONOTtest_pbc_function2(self):
        f = compile_function(llvmsnippet.pbc_function2, [int])
        assert f(0) == 13
        assert f(1) == 15
        assert f(2) == 17
        assert f(3) == 19


import autopath
import py

import StringIO

from pypy.translator.translator import Translator
from pypy.translator.llvm.genllvm import LLVMGenerator
from pypy.translator.test import snippet as test
from pypy.objspace.flow.model import Constant, Variable

from pypy.translator.llvm.test import llvmsnippet

def setup_module(mod): 
    mod.llvm_found = 0 #is_on_path("llvm-as")

def compile_function(function, annotate):
    t = Translator(function)
    a = t.annotate(annotate)
    gen = LLVMGenerator(t)
    return gen.compile()

def is_on_path(name):
    try:
        py.path.local.sysfind(name) 
    except py.error.ENOENT: 
        return False 
    else: 
        return True

class TestLLVMRepr(object):
    def DONOT_test_simple1(self):
        t = Translator(llvmsnippet.simple1)
        a = t.annotate([])
        gen = LLVMGenerator(t)
        l_repr = gen.get_repr(t.getflowgraph().startblock.exits[0].args[0])
        assert l_repr.llvmname() == "1"
        assert l_repr.typed_name() == "int 1"
        print gen.l_entrypoint.get_functions()
        assert gen.l_entrypoint.get_functions() == """\
int %simple1() {
block0:
\tbr label %block1
block1:
\t%v0 = phi int [1, %block0]
\tret int %v0
}

"""

    def test_simple2(self):
        t = Translator(llvmsnippet.simple2)
        a = t.annotate([])
        gen = LLVMGenerator(t)
        print gen
        print t.getflowgraph().startblock.exits[0].args[0]
        l_repr = gen.get_repr(t.getflowgraph().startblock.exits[0].args[0])
        assert l_repr.llvmname() == "false"
        assert l_repr.typed_name() == "bool false"

    def test_typerepr(self):
        t = Translator(llvmsnippet.simple1)
        a = t.annotate([])
        gen = LLVMGenerator(t)
        l_repr = gen.get_repr(str)
        assert l_repr.llvmname() == "%std.string*"

    def test_stringrepr(self):
        t = Translator(llvmsnippet.simple3)
        a = t.annotate([])
        gen = LLVMGenerator(t)
        l_repr1 = gen.get_repr(t.getflowgraph().startblock.exits[0].args[0])
        l_repr2 = gen.get_repr(t.getflowgraph().startblock.exits[0].args[0])
        assert l_repr1 is l_repr2
        assert l_repr1.typed_name() == "%std.string* %glb.StringRepr.2"
        assert l_repr2.get_globals() == """%glb.StringRepr.1 = \
internal constant [13 x sbyte] c"Hello, Stars!"
%glb.StringRepr.2 = internal constant %std.string {uint 13,\
sbyte* getelementptr ([13 x sbyte]* %glb.StringRepr.1, uint 0, uint 0)}"""

class TestGenLLVM(object):
    def setup_method(self,method):
        if not llvm_found:
            py.test.skip("llvm-as not found on path")

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

class TestLLVMArray(object):
    def setup_method(self, method):
        if not llvm_found:
            py.test.skip("llvm-as not found on path.")

    def test_simplearray(self):
        f = compile_function(llvmsnippet.arraytestsimple, [])
        assert f() == 42

    def test_simplearray1(self):
        f = compile_function(llvmsnippet.arraytestsimple1, [])
        assert f() == 43

    def test_simplearray_setitem(self):
        f = compile_function(llvmsnippet.arraytestsetitem, [int])
        assert f(32) == 64

class TestSnippet(object):
    def setup_method(self, method):
        if not llvm_found:
            py.test.skip("llvm-as not found on path.")
        
    def test_if_then_else(self):
        f = compile_function(test.if_then_else, [int, int, int])
        assert f(0, 12, 13) == 13
        assert f(13, 12, 13) == 12
        
    def test_my_gcd(self):
        f = compile_function(test.my_gcd, [int, int])
        assert f(15, 5) == 5
        assert f(18, 42) == 6

    def test_is_perfect_number(self):
        f = compile_function(test.is_perfect_number, [int])
        assert f(28) == 1
        assert f(123) == 0
        assert f(496) == 1

    def test_my_bool(self):
        f = compile_function(test.my_bool, [int])
        assert f(10) == 1
        assert f(1) == 1
        assert f(0) == 0
        
    def test_while_func(self):
        while_func = compile_function(test.while_func, [int])
        assert while_func(10) == 55

    def test_factorial2(self):
        factorial2 = compile_function(test.factorial2, [int])
        assert factorial2(5) == 120

    def test_factorial(self):
        factorial = compile_function(test.factorial, [int])
        assert factorial(5) == 120

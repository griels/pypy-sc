from __future__ import division
import py

from pypy.translator.translator import Translator
from pypy.objspace.flow.model import Constant, Variable
from pypy.translator.llvm2.genllvm import compile_function
from pypy.translator.llvm2.test import llvmsnippet

class TestClass(object):
    def test_classsimple(self):
        f = compile_function(llvmsnippet.class_simple, [])
        assert f() == 14

    def test_classsimple1(self):
        f = compile_function(llvmsnippet.class_simple1, [int])
        assert f(2) == 10

    def test_id_int(self):
        f = compile_function(llvmsnippet.id_int, [int])
        for i in range(1, 20):
            assert f(i) == i

    def test_classsimple2(self):
        f = compile_function(llvmsnippet.class_simple2, [int])
        assert f(2) == 10

    def SEGFAULTtest_method_of_base_class(self):
        f = compile_function(llvmsnippet.method_of_base_class, [])
        assert f() == 14

    def SEGFAULTtest_attribute_from_base_class(self):
        f = compile_function(llvmsnippet.attribute_from_base_class, [])
        assert f() == 4

    def SEGFAULTtest_direct_call_of_virtual_method(self):
        f = compile_function(llvmsnippet.direct_call_of_virtual_method, [])
        assert f() == 14

    def test_flow_type(self):
        f = compile_function(llvmsnippet.flow_type, [])
        assert f() == 16

    def test_merge_class(self):
        f = compile_function(llvmsnippet.merge_classes, [bool])
        assert f(True) == 1
        assert f(False) == 2

    def test_attribute_instance(self):
        f = compile_function(llvmsnippet.attribute_instance, [bool])
        assert f(True) == 1
        assert f(False) == 2

    def test_global_instance(self):
        f = compile_function(llvmsnippet.global_instance, [int])
        assert f(-1) == 41
        for i in range(20):
            assert f(i) == 2 * i

    def test_call_degrading_func(self):
        f = compile_function(llvmsnippet.call_degrading_func, [bool])
        assert f(True) == -36
        assert f(False) == 14
    
    def DONOTtest_circular_classdef(self):
        f = compile_function(llvmsnippet.circular_classdef, [])
        assert f() == 10

"""
Test the rctypes pointer implementation
"""

import py.test
from pypy.translator.translator import TranslationContext
from pypy import conftest
from pypy.rpython.test.test_llinterp import interpret

from ctypes import c_int, c_float, POINTER, pointer

import pypy.rpython.rctypes.implementation

class Test_annotation:
    def test_simple(self):
        res = c_int(42)
        ptrres = POINTER(c_int)(res)
        assert res.value == ptrres.contents.value

    def test_annotate_c_int_ptr(self):
        ptrtype = POINTER(c_int)
        def func():
            res = c_int(42)
            ptrres  = ptrtype(res)
            return ptrres.contents.value
        
        t = TranslationContext()
        a = t.buildannotator()
        s = a.build_types(func, [])

        if conftest.option.view:
            t.view()

        assert s.knowntype == int

    def test_annotate_c_float_ptr(self):
        ptrtype = POINTER(c_float)
        def func():
            res = c_float(4.2)
            ptrres  = ptrtype(res)
            return ptrres.contents.value
        
        t = TranslationContext()
        a = t.buildannotator()
        s = a.build_types(func, [])

        if conftest.option.view:
            t.view()

        assert s.knowntype == float

    def test_annotate_pointer_fn(self):
        def func():
            p = pointer(c_int(123))
            return p.contents.value

        t = TranslationContext()
        a = t.buildannotator()
        s = a.build_types(func, [])

        if conftest.option.view:
            t.view()

        assert s.knowntype == int


class Test_specialization:
    def test_specialize_c_int_ptr(self):
        ptrtype = POINTER(c_int)
        def func():
            res = c_int(42)
            ptrres = ptrtype(res)
            return ptrres.contents.value

        res = interpret(func, [])
        assert res == 42

    def test_specialize_mutate_via_pointer(self):
        ptrtype = POINTER(c_int)
        def func():
            res = c_int(6)
            p1 = ptrtype(res)
            p2 = ptrtype(p1.contents)
            p2.contents.value *= 7
            return res.value

        res = interpret(func, [])
        assert res == 42

    def test_keepalive(self):
        ptrtype = POINTER(c_int)
        def func(n):
            if n == 1:
                x = c_int(6)
                p1 = ptrtype(x)
            else:
                y = c_int(7)
                p1 = ptrtype(y)
            # x or y risk being deallocated by the time we get there,
            # unless p1 correctly keeps them alive.  The llinterpreter
            # detects this error exactly.
            return p1.contents.value

        res = interpret(func, [3])
        assert res == 7

    def test_keepalive_2(self):
        ptrtype = POINTER(c_int)
        ptrptrtype = POINTER(ptrtype)
        def func(n):
            if n == 1:
                p1 = ptrtype(c_int(6))
                p2 = ptrptrtype(p1)
            else:
                if n == 2:
                    p1 = ptrtype(c_int(7))
                else:
                    p1 = ptrtype(c_int(8))
                p2 = ptrptrtype(p1)
            del p1
            p3 = ptrptrtype(p2.contents)
            p3.contents.contents.value *= 6
            return p2.contents.contents.value

        assert func(2) == 42
        res = interpret(func, [2])
        assert res == 42

    def test_specialize_pointer_fn(self):
        def func():
            p = pointer(c_int(123))
            return p.contents.value

        assert func() == 123
        res = interpret(func, [])
        assert res == 123

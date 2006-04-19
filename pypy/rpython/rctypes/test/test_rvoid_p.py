"""
Test the c_void_p implementation.
"""

import py.test
import pypy.rpython.rctypes.implementation
from pypy.annotation.annrpython import RPythonAnnotator
from pypy.translator.translator import TranslationContext
from pypy.translator.c.test.test_genc import compile
from pypy import conftest
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.test.test_llinterp import interpret

from ctypes import c_void_p, c_int, cast, pointer, POINTER

class Test_annotation:
    def test_annotate_c_void_p(self):
        def fn():
            x = c_int(12)
            p1 = cast(pointer(x), c_void_p)
            p2 = cast(p1, POINTER(c_int))
            assert p2.contents.value == 12
            return p1, p2

        t = TranslationContext()
        a = t.buildannotator()
        s = a.build_types(fn, [])
        assert s.items[0].knowntype == c_void_p
        assert s.items[1].knowntype == POINTER(c_int)

        if conftest.option.view:
            t.view()

class Test_specialization:
    def test_specialize_c_void_p(self):
        def func():
            x = c_int(12)
            p1 = cast(pointer(x), c_void_p)
            p2 = cast(p1, POINTER(c_int))
            return p1, p2.contents.value

        res = interpret(func, [])
        assert lltype.typeOf(res.item0.c_data[0]) == llmemory.Address
        assert res.item1 == 12

class Test_compilation:
    def test_compile_c_char_p(self):
        def func():
            x = c_int(12)
            p1 = cast(pointer(x), c_void_p)
            p2 = cast(p1, POINTER(c_int))
            return p2.contents.value

        fn = compile(func, [])
        assert fn() == 12

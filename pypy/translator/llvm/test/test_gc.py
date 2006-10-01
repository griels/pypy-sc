import sys

import py

from pypy.translator.llvm.test.runtest import *

def test_GC_malloc(): 
    #XXX how to get to gcpolicy?
    #if not use_boehm_gc:
    #    py.test.skip("test_GC_malloc skipped because Boehm collector library was not found")
    #    return
    def tuple_getitem(n): 
        x = 666
        i = 0
        while i < n:
            l = (1,2,i,4,5,6,7,8,9,10,11)
            x += l[2]
            i += 1
        return x
    mod, f = compile_test(tuple_getitem, [int], gcpolicy="boehm")
    n = 5000
    result = tuple_getitem(n)
    assert f(n) == result
    get_heap_size = getattr(mod, "GC_get_heap_size_wrapper")
    heap_size_start = get_heap_size()
    for i in range(0,25):
        assert f(n) == result
        heap_size_inc = get_heap_size() - heap_size_start
        assert heap_size_inc < 1000000

def test_nogc(): 
    def tuple_getitem(n): 
        x = 666
        i = 0
        while i < n:
            l = (1,2,i,4,5,6,7,8,9,10,11)
            x += l[2]
            i += 1
        return x
    mod, f = compile_test(tuple_getitem, [int], gcpolicy="none")
    assert f(5000) == tuple_getitem(5000)

def test_ref(): 
    py.test.skip("broken by r32613, partially fixed by r32619 but not really")
    def tuple_getitem(n): 
        x = 666
        i = 0
        while i < n:
            l = (1,2,i,4,5,6,7,8,9,10,11)
            x += l[2]
            i += 1
        return x
    mod, f = compile_test(tuple_getitem, [int], gcpolicy="ref")
    assert f(5000) == tuple_getitem(5000)


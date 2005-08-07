import py

from pypy.translator.llvm2.genllvm import compile_function
from pypy.translator.test.snippet import try_raise_choose
from pypy.rpython.rarithmetic import r_uint

import sys

class TestException(Exception):
    pass

class MyException(Exception):
    def __init__(self, n):
        self.n = n

def getitem(l, i):  #LookupError, KeyError
    if not isinstance(i, int):
        raise TypeError
    if i < 0:
        i = len(l) - i
    if i>= len(l):
        raise IndexError
    return l[i]

def test_simple1():
    def raise_(i):
        if i:
            raise TestException()
        else:
            return 3
    def fn(i):
        try:
            a = raise_(i) + 11
            b = raise_(i) + 12
            c = raise_(i) + 13
            return a+b+c
        except TestException: 
            return 7
        else:
            return 3
    f = compile_function(fn, [int])
    assert f(0) == fn(0)
    assert f(1) == fn(1)

def test_simple2():
    def fn(n):
        lst = range(10)
        try:
            getitem(lst,n)
        except:
            return 2
        return 4
    f = compile_function(fn, [int])
    assert f(-1) == fn(-1)
    assert f( 0) == fn( 0)
    assert f(10) == fn(10)

def test_simple3():
    def raise_(i):
        if i == 0:
            raise TestException()
        elif i == 1:
            raise MyException(42)
        else:
            return 3
    def fn(i):
        try:
            a = raise_(i) + 11
            b = raise_(i) + 12
            c = raise_(i) + 13
            return a+b+c
        except TestException: 
            return 7
        except MyException: 
            return 123
        except:
            return 22
        return 66
    f = compile_function(fn, [int])
    assert f(0) == fn(0)
    assert f(1) == fn(1)
    assert f(2) == fn(2)

def test_pass_exc():
    def fn(n):
        lst = range(10)
        try:
            getitem(lst,n)
        except:
            pass
        return 4
    f = compile_function(fn, [int])
    assert f(-1) == fn(-1)
    assert f( 0) == fn( 0)
    assert f(10) == fn(10)

def test_zerodiv_int():
    def zerodiv_int(n):
        try:
            r=100/n
        except ZeroDivisionError:
            return n+7
        return r
    f = compile_function(zerodiv_int, [int])
    for i in (-50,0,50):
        assert f(i) == zerodiv_int(i)

def test_zerodiv_uint():
    def zerodiv_uint(n):
        try:
            r=100/n
        except ZeroDivisionError:
            return n+7
        return r
    f = compile_function(zerodiv_uint, [r_uint])
    for i in (0,50,100):
        assert f(i) == zerodiv_uint(i)

def test_zerodivrem_int():
    def zerodivrem_int(n):
        try:
            r=100%n
        except ZeroDivisionError:
            return n+7
        return r
    f = compile_function(zerodivrem_int, [int])
    for i in (-50,0,50):
        assert f(i) == zerodivrem_int(i)

def test_zerodivrem_uint():
    def zerodivrem_uint(n):
        try:
            r=100%n
        except ZeroDivisionError:
            return n+7
        return r
    f = compile_function(zerodivrem_uint, [r_uint])
    for i in (0,50,100):
        assert f(i) == zerodivrem_uint(i)

def test_neg_int_ovf():
    py.test.skip("When does int_neg_ovf get generated")    
    def neg_int_ovf(n):
        try:
            r=-n
        except OverflowError:
            return 123
        return r
    f = compile_function(neg_int_ovf, [int])
    for i in (-sys.maxint-1, -sys.maxint, 0, sys.maxint-1, sys.maxint):
        assert f(i) == neg_int_ovf(i)

def test_abs_int_ovf():
    py.test.skip("When does int_abs_ovf get generated")    
    def abs_int_ovf(n):
        try:
            r=abs(n)
        except OverflowError:
            return 123
        return r
    f = compile_function(abs_int_ovf, [int], True)
    for i in (-sys.maxint-1, -sys.maxint, 0, sys.maxint-1, sys.maxint):
        assert f(i) == abs_int_ovf(i)

def test_reraise1():
    def fn(n):
        lst = range(10)
        try:
            getitem(lst,n)
        except:
            raise
        return 4
    f = compile_function(fn, [int])
    py.test.raises(Exception, "f(-1)")
    assert f( 0) == fn( 0)
    py.test.raises(Exception, "f(10)")

def test_reraise2():
    def fn(n):
        lst = range(10)
        try:
            getitem(lst,n)
        except Exception, e:
            raise e
        return 4
    f = compile_function(fn, [int])
    py.test.raises(Exception, "f(-1)")
    assert f( 0) == fn( 0)
    py.test.raises(Exception, "f(10)")

def test_simple_exception():
    def fn(n):
        lst = range(10)
        try:
            getitem(lst,n)
        except IndexError:
            return 2
        return 4
    f = compile_function(fn, [int])
    for i in range(10):
        assert f(i) == fn(i)
    for i in range(10, 20):
        assert f(i) == fn(i)

def test_two_exceptions():
    def fn(n):
        lst = range(10)
        try:
            getitem(lst,n)
        except IndexError:
            return 2
        except KeyError:
            return 3
        return 4
    f = compile_function(fn, [int])
    for i in range(10):
        assert f(i) == fn(i)
    for i in range(10, 20):
        assert f(i) == fn(i)

def test_catch_base_exception():
    def fn(n):
        lst = range(10)
        try:
            getitem(lst,n)
        except LookupError:
            return 2
        return 4
    f = compile_function(fn, [int])
    for i in range(10):
        assert f(i) == fn(i)
    for i in range(10, 20):
        assert f(i) == fn(i)

def test_catches():
    def raises(i):
        if i == 3:
            raise MyException, 12
        if i == 4:
            raise IndexError
        if i > 5:
            raise MyException(i)
        return 1
    def fn(i):
        try:
            return raises(i)
        except MyException, e:
            return e.n
        except:
            return 123
    f = compile_function(fn, [int])
    assert f(1) == fn(1)
    assert f(2) == fn(2)
    assert f(3) == fn(3)
    #py.test.raises(RuntimeError, "f(4)")   #XXX would like to test: py.test.not_raises(....)
    assert f(5) == fn(5)
    assert f(6) == fn(6)
    assert f(13) == fn(13)

def test_try_raise_choose():
    f = compile_function(try_raise_choose, [int])
    for i in [-1, 0, 1, 2]:
        assert f(i) == i

def test_raise_outside_testfn():
    py.test.skip("Test needs --nomagic!")    
    def raiser(n):
        if n < 0:
            raise ValueError("hello")
        else:
            raise MyException("world")

    def intermediate(n):
        raiser(n)
        
    def testfn(n):
        try:
            intermediate(n)
        except ValueError:
            return 1
        except Exception:
            return 2
        return 0
    
    f = compile_function(testfn, [int])
    assert f(1) == testfn(1)
    assert f(-1) == testfn(-1)


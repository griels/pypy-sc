import py
from pypy.translator.translator import Translator


class TestException(Exception):
    pass

class MyException(Exception):
    pass

def test_simple1():
    def raise_(i):
        if i == 0:
            raise TestException()
        elif i == 1:
            raise MyException()
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
    t = Translator(fn)
    t.annotate([int]).simplify()
    t.specialize()
    #t.view()
    f = t.ccompile()
    assert f(0) == fn(0)
    assert f(1) == fn(1)
    assert f(2) == fn(2)

def test_implicit_index_error_lists():
    def fn(n):
        lst = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        try:
            return lst[n]
        except:
            return 2
    t = Translator(fn)
    t.annotate([int]).simplify()
    t.specialize()
    #t.view()
    f = t.ccompile()
    assert f(-1) == fn(-1)
    assert f( 0) == fn( 0)
    assert f(10) == fn(10)

def test_myexception():
    def g():
        raise MyException
    def f():
        try:
            g()
        except MyException:
            return 5
        else:
            return 2

    t = Translator(f)
    t.annotate([]).simplify()
    t.specialize()
    #t.view()
    f1 = t.ccompile()
    assert f1() == 5

def test_raise_outside_testfn():
    def testfn(n):
        if n < 0:
            raise ValueError("hello")
        else:
            raise MyException("world")

    t = Translator(testfn)
    t.annotate([int]).simplify()
    t.specialize()
    f1 = t.ccompile()
    assert py.test.raises(ValueError, f1, -1)
    try:
        f1(1)
    except Exception, e:
        assert str(e) == 'MyException'   # which is genc's best effort
    else:
        py.test.fail("f1(1) did not raise anything")

def test_assert():
    def testfn(n):
        assert n >= 0

    # big confusion with py.test's AssertionError handling here...
    # some hacks to try to disable it for the current test.
    saved = no_magic()
    try:
        t = Translator(testfn)
        t.annotate([int]).simplify()
        t.specialize()
        f1 = t.ccompile()
        res = f1(0)
        assert res is None, repr(res)
        res = f1(42)
        assert res is None, repr(res)
        py.test.raises(AssertionError, f1, -2)
    finally:
        restore_magic(saved)


def no_magic():
    import __builtin__
    try:
        py.magic.revert(__builtin__, 'AssertionError')
        return True
    except ValueError:
        return False

def restore_magic(saved):
    if saved:
        py.magic.invoke(assertion=True)

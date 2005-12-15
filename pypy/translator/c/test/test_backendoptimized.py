import autopath
from pypy.translator.c.test.test_typed import TestTypedTestCase as _TestTypedTestCase
from pypy.translator.backendopt.all import backend_optimizations
from pypy.rpython import objectmodel


class TestTypedOptimizedTestCase(_TestTypedTestCase):

    def process(self, t):
        _TestTypedTestCase.process(self, t)
        self.t = t
        backend_optimizations(t)

    def test_remove_same_as(self):
        def f(n=bool):
            if bool(bool(bool(n))):
                return 123
            else:
                return 456
        fn = self.getcompiled(f)
        assert f(True) == 123
        assert f(False) == 456

    def test__del__(self):
        import os
        class B(object):
            pass
        b = B()
        b.nextid = 0
        b.num_deleted = 0
        class A(object):
            def __init__(self):
                self.id = b.nextid
                b.nextid += 1

            def __del__(self):
                b.num_deleted += 1

        def f(x=int):
            a = A()
            for i in range(x):
                a = A()
            return b.num_deleted

        fn = self.getcompiled(f)
        res = f(5)
        assert res == 5
        res = fn(5)
        # translated function looses its last reference earlier
        assert res == 6
    
    def test_del_inheritance(self):
        class State:
            pass
        s = State()
        s.a_dels = 0
        s.b_dels = 0
        class A(object):
            def __del__(self):
                s.a_dels += 1
        class B(A):
            def __del__(self):
                s.b_dels += 1
        class C(A):
            pass
        def f():
            A()
            B()
            C()
            A()
            B()
            C()
            return s.a_dels * 10 + s.b_dels
        res = f()
        assert res == 42
        fn = self.getcompiled(f)
        res = fn()
        assert res == 42

    def test_casttoandfromint(self):
        class A(object):
            pass
        def f():
            a = A()
            return objectmodel.cast_object_to_int(a)
        def g():
            a = A()
            i = objectmodel.cast_object_to_int(a)
            return objectmodel.cast_object_to_int(
                objectmodel.cast_int_to_object(i, A)) == i
        fn = self.getcompiled(f)
        res = fn()
        # cannot really test anything about 'res' here
        gn = self.getcompiled(g)
        res = gn()
        assert res
    

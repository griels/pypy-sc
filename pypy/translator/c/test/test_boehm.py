import py
from pypy.translator.translator import TranslationContext
from pypy.rpython.lltypesystem import lltype
from pypy.translator.tool.cbuild import check_boehm_presence
from pypy.translator.c.genc import CExtModuleBuilder
from pypy import conftest

def setup_module(mod):
    if not check_boehm_presence():
        py.test.skip("Boehm GC not present")

class AbstractGCTestClass:
    gcpolicy = "boehm"
   
    # deal with cleanups
    def setup_method(self, meth):
        self._cleanups = []
    def teardown_method(self, meth):
        while self._cleanups:
            #print "CLEANUP"
            self._cleanups.pop()()

    def getcompiled(self, func, argstypelist = [],
                    annotatorpolicy=None):
        from pypy.config.pypyoption import get_pypy_config
        config = get_pypy_config(translating=True)
        config.translation.gc = self.gcpolicy
        config.translation.simplifying = True
        t = TranslationContext(config=config)
        self.t = t
        a = t.buildannotator(policy=annotatorpolicy)
        a.build_types(func, argstypelist)
        t.buildrtyper().specialize()
        t.checkgraphs()
        def compile():
            cbuilder = CExtModuleBuilder(t, func, config=config)
            c_source_filename = cbuilder.generate_source()
            if conftest.option.view:
                t.view()
            cbuilder.compile()
            mod = cbuilder.isolated_import()
            self._cleanups.append(cbuilder.cleanup) # schedule cleanup after test
            return cbuilder.get_entry_point()
        return compile()


class TestUsingBoehm(AbstractGCTestClass):
    gcpolicy = "boehm"

    def test_malloc_a_lot(self):
        def malloc_a_lot():
            i = 0
            while i < 10:
                i += 1
                a = [1] * 10
                j = 0
                while j < 20:
                    j += 1
                    a.append(j)
        fn = self.getcompiled(malloc_a_lot)
        fn()

    def test__del__(self):
        from pypy.rpython.lltypesystem.lloperation import llop
        class State:
            pass
        s = State()
        class A(object):
            def __del__(self):
                s.a_dels += 1
        class B(A):
            def __del__(self):
                s.b_dels += 1
        class C(A):
            pass
        def f():
            s.a_dels = 0
            s.b_dels = 0
            A()
            B()
            C()
            A()
            B()
            C()
            llop.gc__collect(lltype.Void)
            return s.a_dels * 10 + s.b_dels
        fn = self.getcompiled(f)
        # we can't demand that boehm has collected all of the objects,
        # even with the gc__collect call.  calling the compiled
        # function twice seems to help, though.
        res = 0
        res += fn()
        res += fn()
        # if res is still 0, then we haven't tested anything so fail.
        # it might be the test's fault though.
        assert 0 < res <= 84

    def test_id_is_weak(self):
        # test that id(obj) does not keep obj alive
        py.test.skip("fails")
        from pypy.rpython.lltypesystem.lloperation import llop
        class State:
            pass
        s = State()
        class A(object):
            def __del__(self):
                s.a_dels += 1
        class B(A):
            def __del__(self):
                s.b_dels += 1
        class C(A):
            pass
        def run_once():
            a = A()
            ida = id(a)
            b = B()
            idb = id(b)
            c = C()
            idc = id(c)
            llop.gc__collect(lltype.Void)
            llop.gc__collect(lltype.Void)
            llop.gc__collect(lltype.Void)
            return ida, idb, idc
        def f(n):
            s.a_dels = 0
            s.b_dels = 0
            a1, b1, c1 = run_once()
            a2, b2, c2 = run_once()
            a3, b3, c3 = run_once()
            a4, b4, c4 = run_once()
            a5, b5, c5 = run_once()
            return (s.a_dels, s.b_dels,
                    a1, b1, c1,
                    a2, b2, c2,
                    a3, b3, c3,
                    a4, b4, c4,
                    a5, b5, c5)
        fn = self.getcompiled(f, [int])
        # we can't demand that boehm has collected all of the objects,
        # even with the gc__collect call.
        res = fn(50)
        res1, res2 = res[:2]
        # if res1 or res2 is still 0, then we haven't tested anything so fail.
        # it might be the test's fault though.
        print res1, res2
        assert 0 < res1 <= 10
        assert 0 < res2 <= 5

    def test_weakgcaddress_is_weak(self):
        py.test.skip("weakgcaddress as we know it is fragile")
        from pypy.rpython.lltypesystem.lloperation import llop
        from pypy.rlib.objectmodel import cast_object_to_weakgcaddress
        class State:
            pass
        s = State()
        class A(object):
            def __del__(self):
                s.a_dels += 1
        def f(i):
            if i:
                s.a_dels = 0
                a = A()
                # this should not keep a alive
                s.a = cast_object_to_weakgcaddress(a)
                a = None
            llop.gc__collect(lltype.Void)
            llop.gc__collect(lltype.Void)
            llop.gc__collect(lltype.Void)
            return s.a_dels
        fn = self.getcompiled(f, [int])
        # we can't demand that boehm has collected all of the objects,
        # even with the gc__collect call.  calling the compiled
        # function twice seems to help, though.
        fn(1)
        fn(0)
        fn(0)
        res = fn(0)
        print res
        assert res == 1

    def test_del_raises(self):
        from pypy.rpython.lltypesystem.lloperation import llop
        import os
        class A(object):
            def __del__(self):
                s.dels += 1
                raise Exception
        class State:
            pass
        s = State()
        s.dels = 0
        def g():
            a = A()
        def f():
            s.dels = 0
            for i in range(10):
                g()
            llop.gc__collect(lltype.Void)
            return s.dels
        fn = self.getcompiled(f)
        # we can't demand that boehm has collected all of the objects,
        # even with the gc__collect call.  calling the compiled
        # function twice seems to help, though.
        res = 0
        res += fn()
        res += fn()
        # if res is still 0, then we haven't tested anything so fail.
        # it might be the test's fault though.
        assert res > 0

    def test_memory_error_varsize(self):
        N = int(2**31-1)
        A = lltype.GcArray(lltype.Char)
        def alloc(n):
            return lltype.malloc(A, n)
        def f():
            try:
                x = alloc(N)
            except MemoryError:
                y = alloc(10)
                return len(y)
            y = alloc(10)
            return len(y) # allocation may work on 64 bits machines
        fn = self.getcompiled(f)
        res = fn()
        assert res == 10
        
    # this test shows if we have a problem with refcounting PyObject
    def test_refcount_pyobj(self):
        from pypy.rpython.lltypesystem.lloperation import llop
        def prob_with_pyobj(b):
            return 3, b
        def collect():
            llop.gc__collect(lltype.Void)
        f = self.getcompiled(prob_with_pyobj, [object])
        c = self.getcompiled(collect, [])
        from sys import getrefcount as g
        obj = None
        before = g(obj)
        f(obj)
        f(obj)
        f(obj)
        f(obj)
        f(obj)
        c()
        c()
        c()
        c()
        c()
        after = g(obj)
        assert abs(before - after) < 5

    def test_zero_malloc(self):
        T = lltype.GcStruct("C", ('x', lltype.Signed))
        def fixed_size():
            t = lltype.malloc(T, zero=True)
            return t.x
        c_fixed_size = self.getcompiled(fixed_size, [])
        res = c_fixed_size()
        assert res == 0
        A = lltype.GcArray(lltype.Signed)
        def var_size():
            a = lltype.malloc(A, 1, zero=True)
            return a[0]
        c_var_size = self.getcompiled(var_size, [])
        res = c_var_size()
        assert res == 0

    def test_gc_set_max_heap_size(self):
        def g(n):
            return 'x' * n
        def fn():
            from pypy.rlib import rgc
            rgc.set_max_heap_size(500000)
            s1 = s2 = s3 = None
            try:
                s1 = g(10000)
                s2 = g(100000)
                s3 = g(1000000)
            except MemoryError:
                pass
            return (s1 is not None) + (s2 is not None) + (s3 is not None)
        c_fn = self.getcompiled(fn, [])
        res = c_fn()
        assert res == 2

    def test_weakref(self):
        import weakref
        from pypy.rlib import rgc

        class A:
            pass

        def fn(n):
            keepalive = []
            weakrefs = []
            a = None
            for i in range(n):
                if i & 1 == 0:
                    a = A()
                    a.index = i
                weakrefs.append(weakref.ref(a))
                if i % 7 == 6:
                    keepalive.append(a)
            rgc.collect()
            count_free = 0
            for i in range(n):
                a = weakrefs[i]()
                if i % 7 == 6:
                    assert a is not None
                if a is not None:
                    assert a.index == i & ~1
                else:
                    count_free += 1
            return count_free
        c_fn = self.getcompiled(fn, [int])
        res = c_fn(7000)
        # more than half of them should have been freed, ideally up to 6000
        assert 3500 <= res <= 6000

    def test_prebuilt_weakref(self):
        import weakref
        from pypy.rlib import rgc
        class A:
            pass
        a = A()
        a.hello = 42
        r1 = weakref.ref(a)
        r2 = weakref.ref(A())
        rgc.collect()
        assert r2() is None
        def fn(n):
            if n:
                r = r1
            else:
                r = r2
            a = r()
            if a is None:
                return -5
            else:
                return a.hello
        c_fn = self.getcompiled(fn, [int])
        res = c_fn(1)
        assert res == 42
        res = c_fn(0)
        assert res == -5


class TestUsingExactBoehm(TestUsingBoehm):
    gcpolicy = "exact_boehm"



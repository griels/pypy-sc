from pypy.rpython.lltypesystem.lltype import *
from pypy.translator.c.test import test_typed


class TestLowLevelType(test_typed.CompilationTestCase):

    def test_simple(self):
        S = GcStruct("s", ('v', Signed))
        def llf():
            s = malloc(S)
            return s.v
        fn = self.getcompiled(llf)
        assert fn() == 0

    def test_simple2(self):
        S = Struct("s", ('v', Signed))
        S2 = GcStruct("s2", ('a',S), ('b',S))
        def llf():
            s = malloc(S2)
            s.a.v = 6
            s.b.v = 12
            return s.a.v + s.b.v
        fn = self.getcompiled(llf)
        assert fn() == 18

    def test_fixedsizearray(self):
        S = Struct("s", ('v', Signed))
        A7 = FixedSizeArray(Signed, 7)
        A3 = FixedSizeArray(S, 3)
        A42 = FixedSizeArray(A7, 6)
        BIG = GcStruct("big", ("a7", A7), ("a3", A3), ("a42", A42))
        def llf():
            big = malloc(BIG)
            a7 = big.a7
            a3 = big.a3
            a42 = big.a42
            a7[0] = -1
            a7.item6 = -2
            a3[0].v = -3
            a3[2].v = -4
            a42[0][0] = -5
            a42[5][6] = -6
            assert a7[0] == -1
            assert a7[6] == -2
            assert a3[0].v == -3
            assert a3.item2.v == -4
            assert a42[0][0] == -5
            assert a42[5][6] == -6
            return len(a42)*100 + len(a42[4])
        fn = self.getcompiled(llf)
        res = fn()
        assert fn() == 607

    def test_recursivearray(self):
        A = ForwardReference()
        A.become(FixedSizeArray(Struct("S", ('a', Ptr(A))), 5))
        TREE = GcStruct("TREE", ("root", A), ("other", A))
        def llf():
            tree = malloc(TREE)
            tree.root[0].a = tree.root
            tree.root[1].a = tree.other
            assert tree.root[0].a[0].a[0].a[0].a[0].a[1].a == tree.other
        fn = self.getcompiled(llf)
        fn()

    def test_prebuilt_array(self):
        A = FixedSizeArray(Signed, 5)
        a = malloc(A, immortal=True)
        a[0] = 8
        a[1] = 5
        a[2] = 12
        a[3] = 12
        a[4] = 15
        def llf():
            s = ''
            for i in range(5):
                s += chr(64+a[i])
            assert s == "HELLO"
        fn = self.getcompiled(llf)
        fn()

    def test_call_with_fixedsizearray(self):
        A = FixedSizeArray(Struct('s1', ('x', Signed)), 5)
        S = GcStruct('s', ('a', Ptr(A)))
        a = malloc(A, immortal=True)
        a[1].x = 123
        def g(x):
            return x[1].x
        def llf():
            s = malloc(S)
            s.a = a
            return g(s.a)
        fn = self.getcompiled(llf)
        res = fn()
        assert res == 123

    def test_more_prebuilt_arrays(self):
        A = FixedSizeArray(Struct('s1', ('x', Signed)), 5)
        S = GcStruct('s', ('a1', Ptr(A)), ('a2', A))
        s = malloc(S, zero=True)
        s.a1 = malloc(A, immortal=True)
        s.a1[2].x = 50
        s.a2[2].x = 60
        def llf(n):
            if n == 1:
                a = s.a1
            else:
                a = s.a2
            return a[2].x
        fn = self.getcompiled(llf, [int])
        res = fn(1)
        assert res == 50
        res = fn(2)
        assert res == 60

    def test_fnptr_with_fixedsizearray(self):
        A = ForwardReference()
        F = FuncType([Ptr(A)], Signed)
        A.become(FixedSizeArray(Struct('s1', ('f', Ptr(F)), ('n', Signed)), 5))
        a = malloc(A, immortal=True)
        a[3].n = 42
        def llf(n):
            if a[n].f:
                return a[n].f(a)
            else:
                return -1
        fn = self.getcompiled(llf, [int])
        res = fn(4)
        assert res == -1

    def test_direct_arrayitems(self):
        for a in [malloc(GcArray(Signed), 5),
                  malloc(FixedSizeArray(Signed, 5), immortal=True),
                  malloc(Array(Signed, hints={'nolength': True}), 5,
                         immortal=True),
                  ]:
            a[0] = 0
            a[1] = 10
            a[2] = 20
            a[3] = 30
            a[4] = 40
            b0 = direct_arrayitems(a)
            b1 = direct_ptradd(b0, 1)
            b2 = direct_ptradd(b1, 1)
            def llf(n):
                b0 = direct_arrayitems(a)
                b3 = direct_ptradd(direct_ptradd(b0, 5), -2)
                saved = a[n]
                a[n] = 1000
                try:
                    return b0[0] + b3[-2] + b2[1] + b1[3]
                finally:
                    a[n] = saved
            fn = self.getcompiled(llf, [int])
            res = fn(0)
            assert res == 1000 + 10 + 30 + 40
            res = fn(1)
            assert res == 0 + 1000 + 30 + 40
            res = fn(2)
            assert res == 0 + 10 + 30 + 40
            res = fn(3)
            assert res == 0 + 10 + 1000 + 40
            res = fn(4)
            assert res == 0 + 10 + 30 + 1000

    def test_structarray_add(self):
        from pypy.rpython.lltypesystem import llmemory
        S = Struct("S", ("x", Signed))
        PS = Ptr(S)
        size = llmemory.sizeof(S)
        A = GcArray(S)
        def llf(n):
            a = malloc(A, 5)
            a[3].x = 42
            adr_s = llmemory.cast_ptr_to_adr(a[0])
            adr_s += size * n
            s = llmemory.cast_adr_to_ptr(adr_s, PS)
            return s.x
        fn = self.getcompiled(llf, [int])
        res = fn(3)
        assert res == 42

    def test_direct_fieldptr(self):
        S = GcStruct('S', ('x', Signed), ('y', Signed))
        def llf(n):
            s = malloc(S)
            a = direct_fieldptr(s, 'y')
            a[0] = n
            return s.y

        fn = self.getcompiled(llf, [int])
        res = fn(34)
        assert res == 34

    def test_prebuilt_subarrays(self):
        a1 = malloc(GcArray(Signed), 5, zero=True)
        a2 = malloc(FixedSizeArray(Signed, 5), immortal=True)
        s  = malloc(GcStruct('S', ('x', Signed), ('y', Signed)), zero=True)
        a1[3] = 7000
        a2[1] =  600
        s.x   =   50
        s.y   =    4
        p1 = direct_ptradd(direct_arrayitems(a1), 3)
        p2 = direct_ptradd(direct_arrayitems(a2), 1)
        p3 = direct_fieldptr(s, 'x')
        p4 = direct_fieldptr(s, 'y')
        def llf():
            a1[3] += 1000
            a2[1] +=  100
            s.x   +=   10
            s.y   +=    1
            return p1[0] + p2[0] + p3[0] + p4[0]

        fn = self.getcompiled(llf)
        res = fn()
        assert res == 8765

    def test_pystruct(self):
        PS1 = PyStruct('PS1', ('head', PyObject), ('x', Signed),
                       hints = {'inline_head': True})
        class mytype(object):
            pass
        mytype_ptr = pyobjectptr(mytype)
        def llf():
            p = malloc(PS1, flavor='cpy', extra_args=(mytype_ptr,))
            return cast_pointer(Ptr(PyObject), p)

        fn = self.getcompiled(llf)
        res = fn()
        assert type(res).__name__.endswith('mytype')

    def test_pystruct_prebuilt(self):
        PS1 = PyStruct('PS1', ('head', PyObject), ('x', Signed),
                       hints = {'inline_head': True})
        class mytype(object):
            pass

        def llsetup(phead):
            "Called when the CPython ext module is imported."
            p = cast_pointer(Ptr(PS1), phead)
            p.x = 27

        mytype_ptr = pyobjectptr(mytype)
        p = malloc(PS1, flavor='cpy', extra_args=(mytype_ptr,))
        p.x = -5   # overridden by llsetup()

        def llf():
            return p.x

        def process(t):
            rtyper = t.buildrtyper()
            rtyper.specialize()
            llsetup_ptr = rtyper.annotate_helper_fn(llsetup, [Ptr(PyObject)])
            phead = cast_pointer(Ptr(PyObject), p)
            phead._obj.setup_fnptr = llsetup_ptr

        self.process = process
        fn = self.getcompiled(llf)
        res = fn()
        assert res == 27
        del self.process

    def test_union(self):
        U = Struct('U', ('s', Signed), ('c', Char),
                   hints={'union': True})
        u = malloc(U, immortal=True)
        def llf(c):
            u.s = 0x10203040
            u.c = chr(c)
            return u.s

        fn = self.getcompiled(llf, [int])
        res = fn(0x33)
        assert res in [0x10203033, 0x33203040]

    def test_sizeof_void_array(self):
        from pypy.rpython.lltypesystem import llmemory
        A = Array(Void)
        size1 = llmemory.sizeof(A, 1)
        size2 = llmemory.sizeof(A, 14)
        def f(x):
            if x:
                return size1
            else:
                return size2
        fn = self.getcompiled(f, [int])
        res1 = fn(1)
        res2 = fn(0)
        assert res1 == res2

    def test_null_padding(self):
        from pypy.rpython.lltypesystem import llmemory
        from pypy.rpython.lltypesystem import rstr
        chars_offset = llmemory.FieldOffset(rstr.STR, 'chars') + \
                       llmemory.ArrayItemsOffset(rstr.STR.chars)
        # sadly, there's no way of forcing this to fail if the strings
        # are allocated in a region of memory such that they just
        # happen to get a NUL byte anyway :/ (a debug build will
        # always fail though)
        def trailing_byte(s):
            adr_s = llmemory.cast_ptr_to_adr(s)
            return (adr_s + chars_offset).char[len(s)]
        def f(x):
            r = 0
            for i in range(x):
                r += ord(trailing_byte(' '*(100-x*x)))
            return r
        fn = self.getcompiled(f, [int])
        res = fn(10)
        assert res == 0

    def test_cast_primitive(self):
        def f(x):
            x = cast_primitive(UnsignedLongLong, x)
            x <<= 60
            x /= 3
            x <<= 1
            x = cast_primitive(SignedLongLong, x)
            x >>= 32
            return cast_primitive(Signed, x)
        fn = self.getcompiled(f, [int])
        res = fn(14)
        assert res == -1789569707

    def test_prebuilt_integers(self):
        from pypy.rlib.unroll import unrolling_iterable
        from pypy.rpython.lltypesystem import rffi
        class Prebuilt:
            pass
        p = Prebuilt()
        NUMBER_TYPES = rffi.NUMBER_TYPES
        names = unrolling_iterable([TYPE.__name__ for TYPE in NUMBER_TYPES])
        for name, TYPE in zip(names, NUMBER_TYPES):
            value = cast_primitive(TYPE, 1)
            setattr(p, name, value)

        def f(x):
            total = x
            for name in names:
                total += rffi.cast(Signed, getattr(p, name))
            return total

        fn = self.getcompiled(f, [int])
        res = fn(100)
        assert res == 100 + len(list(names))

    def test_array_nolength(self):
        A = Array(Signed, hints={'nolength': True})
        a1 = malloc(A, 3, immortal=True)
        a1[0] = 30
        a1[1] = 300
        a1[2] = 3000
        a1dummy = malloc(A, 2, immortal=True)

        def f(n):
            if n & 1:
                src = a1dummy
            else:
                src = a1
            a2 = malloc(A, n, flavor='raw')
            for i in range(n):
                a2[i] = src[i % 3] + i
            res = a2[n // 2]
            free(a2, flavor='raw')
            return res

        fn = self.getcompiled(f, [int])
        res = fn(100)
        assert res == 3050

    def test_gcarray_nolength(self):
        A = GcArray(Signed, hints={'nolength': True})
        a1 = malloc(A, 3, immortal=True)
        a1[0] = 30
        a1[1] = 300
        a1[2] = 3000
        a1dummy = malloc(A, 2, immortal=True)

        def f(n):
            if n & 1:
                src = a1dummy
            else:
                src = a1
            a2 = malloc(A, n)
            for i in range(n):
                a2[i] = src[i % 3] + i
            res = a2[n // 2]
            return res

        fn = self.getcompiled(f, [int])
        res = fn(100)
        assert res == 3050

    def test_structarray_nolength(self):
        S = Struct('S', ('x', Signed))
        A = Array(S, hints={'nolength': True})
        a1 = malloc(A, 3, immortal=True)
        a1[0].x = 30
        a1[1].x = 300
        a1[2].x = 3000
        a1dummy = malloc(A, 2, immortal=True)

        def f(n):
            if n & 1:
                src = a1dummy
            else:
                src = a1
            a2 = malloc(A, n, flavor='raw')
            for i in range(n):
                a2[i].x = src[i % 3].x + i
            res = a2[n // 2].x
            free(a2, flavor='raw')
            return res

        fn = self.getcompiled(f, [int])
        res = fn(100)
        assert res == 3050

    def test_arithmetic_cornercases(self):
        import operator, sys
        from pypy.rlib.unroll import unrolling_iterable
        from pypy.rlib.rarithmetic import r_longlong, r_ulonglong

        class Undefined:
            def __eq__(self, other):
                return True
        undefined = Undefined()

        def getmin(cls):
            if cls is int:
                return -sys.maxint-1
            elif cls.SIGNED:
                return cls(-(cls.MASK>>1)-1)
            else:
                return cls(0)
        getmin._annspecialcase_ = 'specialize:memo'

        def getmax(cls):
            if cls is int:
                return sys.maxint
            elif cls.SIGNED:
                return cls(cls.MASK>>1)
            else:
                return cls(cls.MASK)
        getmax._annspecialcase_ = 'specialize:memo'
        maxlonglong = long(getmax(r_longlong))

        classes = unrolling_iterable([int, r_uint, r_longlong, r_ulonglong])
        operators = unrolling_iterable([operator.add,
                                        operator.sub,
                                        operator.mul,
                                        operator.floordiv,
                                        operator.mod,
                                        operator.lshift,
                                        operator.rshift])
        def f(n):
            result = ()
            for cls in classes:
                values = [getmin(cls), getmax(cls)]
                for OP in operators:
                    for x in values:
                        res1 = OP(x, n)
                        result += (res1,)
            return result

        def assert_eq(a, b):
            # for better error messages when it fails
            assert len(a) == len(b)
            for i in range(len(a)):
                assert a[i] == b[i]

        fn = self.getcompiled(f, [int])
        res = fn(1)
        print res
        assert_eq(res, (
            # int
            -sys.maxint, undefined,               # add
            undefined, sys.maxint-1,              # sub
            -sys.maxint-1, sys.maxint,            # mul
            -sys.maxint-1, sys.maxint,            # floordiv
            0, 0,                                 # mod
            0, -2,                                # lshift
            (-sys.maxint-1)//2, sys.maxint//2,    # rshift
            # r_uint
            1, 0,                                 # add
            sys.maxint*2+1, sys.maxint*2,         # sub
            0, sys.maxint*2+1,                    # mul
            0, sys.maxint*2+1,                    # floordiv
            0, 0,                                 # mod
            0, sys.maxint*2,                      # lshift
            0, sys.maxint,                        # rshift
            # r_longlong
            -maxlonglong, undefined,              # add
            undefined, maxlonglong-1,             # sub
            -maxlonglong-1, maxlonglong,          # mul
            -maxlonglong-1, maxlonglong,          # floordiv
            0, 0,                                 # mod
            0, -2,                                # lshift
            (-maxlonglong-1)//2, maxlonglong//2,  # rshift
            # r_ulonglong
            1, 0,                                 # add
            maxlonglong*2+1, maxlonglong*2,       # sub
            0, maxlonglong*2+1,                   # mul
            0, maxlonglong*2+1,                   # floordiv
            0, 0,                                 # mod
            0, maxlonglong*2,                     # lshift
            0, maxlonglong,                       # rshift
            ))

        res = fn(5)
        print res
        assert_eq(res, (
            # int
            -sys.maxint+4, undefined,             # add
            undefined, sys.maxint-5,              # sub
            undefined, undefined,                 # mul
            (-sys.maxint-1)//5, sys.maxint//5,    # floordiv
            (-sys.maxint-1)%5, sys.maxint%5,      # mod
            0, -32,                               # lshift
            (-sys.maxint-1)//32, sys.maxint//32,  # rshift
            # r_uint
            5, 4,                                 # add
            sys.maxint*2-3, sys.maxint*2-4,       # sub
            0, sys.maxint*2-3,                    # mul
            0, (sys.maxint*2+1)//5,               # floordiv
            0, (sys.maxint*2+1)%5,                # mod
            0, sys.maxint*2-30,                   # lshift
            0, sys.maxint>>4,                     # rshift
            # r_longlong
            -maxlonglong+4, undefined,            # add
            undefined, maxlonglong-5,             # sub
            undefined, undefined,                 # mul
            (-maxlonglong-1)//5, maxlonglong//5,  # floordiv
            (-maxlonglong-1)%5, maxlonglong%5,    # mod
            0, -32,                               # lshift
            (-maxlonglong-1)//32, maxlonglong//32,# rshift
            # r_ulonglong
            5, 4,                                 # add
            maxlonglong*2-3, maxlonglong*2-4,     # sub
            0, maxlonglong*2-3,                   # mul
            0, (maxlonglong*2+1)//5,              # floordiv
            0, (maxlonglong*2+1)%5,               # mod
            0, maxlonglong*2-30,                  # lshift
            0, maxlonglong>>4,                    # rshift
            ))

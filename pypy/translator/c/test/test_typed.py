import autopath
import sys
import py

from py.test import raises

from pypy import conftest
from pypy.translator.test import snippet 
from pypy.translator.translator import TranslationContext
from pypy.rpython.rarithmetic import r_uint, r_ulonglong, r_longlong, intmask

# XXX this tries to make compiling faster for full-scale testing
from pypy.translator.tool import cbuild
cbuild.enable_fast_compilation()

class CompilationTestCase:

    def annotatefunc(self, func):
        t = TranslationContext(simplifying=True)
        # builds starting-types from func_defs 
        argstypelist = []
        if func.func_defaults:
            for spec in func.func_defaults:
                if isinstance(spec, tuple):
                    spec = spec[0] # use the first type only for the tests
                argstypelist.append(spec)
        a = t.buildannotator()
        a.build_types(func, argstypelist)
        a.simplify()
        return t

    def compilefunc(self, t, func):
        from pypy.translator.c import genc
        builder = genc.CExtModuleBuilder(t, func)
        builder.generate_source()
        builder.compile()
        builder.import_module()
        return builder.get_entry_point()

    def getcompiled(self, func, view=False):
        from pypy.translator.transform import insert_ll_stackcheck
        t = self.annotatefunc(func)
        self.process(t)
        if view or conftest.option.view:
            t.view()
        t.checkgraphs()
        insert_ll_stackcheck(t)
        return self.compilefunc(t, func)

    def process(self, t):
        t.buildrtyper().specialize()
        #raisingop2direct_call(t)


class TestTypedTestCase(CompilationTestCase):

    def test_set_attr(self):
        set_attr = self.getcompiled(snippet.set_attr)
        assert set_attr() == 2

    def test_inheritance2(self):
        inheritance2 = self.getcompiled(snippet.inheritance2)
        assert inheritance2() == ((-12, -12), (3, "world"))

    def test_factorial2(self):
        factorial2 = self.getcompiled(snippet.factorial2)
        assert factorial2(5) == 120

    def test_factorial(self):
        factorial = self.getcompiled(snippet.factorial)
        assert factorial(5) == 120

    def test_simple_method(self):
        simple_method = self.getcompiled(snippet.simple_method)
        assert simple_method(55) == 55

    def test_sieve_of_eratosthenes(self):
        sieve_of_eratosthenes = self.getcompiled(snippet.sieve_of_eratosthenes)
        assert sieve_of_eratosthenes() == 1028

    def test_nested_whiles(self):
        nested_whiles = self.getcompiled(snippet.nested_whiles)
        assert nested_whiles(5,3) == '!!!!!'

    def test_call_five(self):
        call_five = self.getcompiled(snippet.call_five)
        result = call_five()
        assert result == [5]
        # --  currently result isn't a real list, but a pseudo-array
        #     that can't be inspected from Python.
        #self.assertEquals(result.__class__.__name__[:8], "list of ")

    def test_call_unpack_56(self):
        call_unpack_56 = self.getcompiled(snippet.call_unpack_56)
        result = call_unpack_56()
        assert result == (2, 5, 6)

    def test_class_defaultattr(self):
        class K:
            n = "hello"
        def class_defaultattr():
            k = K()
            k.n += " world"
            return k.n
        fn = self.getcompiled(class_defaultattr)
        assert fn() == "hello world"

    def test_tuple_repr(self):
        def tuple_repr(x=int, y=object):
            z = x, y
            while x:
                x = x-1
            return z
        fn = self.getcompiled(tuple_repr)
        assert fn(6,'a') == (6,'a')

    def test_classattribute(self):
        fn = self.getcompiled(snippet.classattribute)
        assert fn(1) == 123
        assert fn(2) == 456
        assert fn(3) == 789
        assert fn(4) == 789
        assert fn(5) == 101112

    def test_get_set_del_slice(self):
        fn = self.getcompiled(snippet.get_set_del_slice)
        l = list('abcdefghij')
        result = fn(l)
        assert l == [3, 'c', 8, 11, 'h', 9]
        assert result == ([3, 'c'], [9], [11, 'h'])

    def test_slice_long(self):
        def slice_long(l=list, n=long):
            return l[:n]
        fn = self.getcompiled(slice_long)
        l = list('abc')
        result = fn(l, 2**32)
        assert result == list('abc')
        result = fn(l, 2**64)
        assert result == list('abc')

    def test_type_conversion(self):
        # obfuscated test case specially for typer.insert_link_conversions()
        def type_conversion(n=int):
            if n > 3:
                while n > 0:
                    n = n-1
                    if n == 5:
                        n += 3.1416
            return n
        fn = self.getcompiled(type_conversion)
        assert fn(3) == 3
        assert fn(5) == 0
        assert abs(fn(7) + 0.8584) < 1E-5

    def test_do_try_raise_choose(self):
        fn = self.getcompiled(snippet.try_raise_choose)
        result = []
        for n in [-1,0,1,2]:
            result.append(fn(n))
        assert result == [-1,0,1,2]    

    def test_is_perfect_number(self):
        fn = self.getcompiled(snippet.is_perfect_number)
        for i in range(1, 33):
            perfect = fn(i)
            assert perfect is (i in (6,28))

    def test_prime(self):
        fn = self.getcompiled(snippet.prime)
        result = [fn(i) for i in range(1, 21)]
        assert result == [False, True, True, False, True, False, True, False,
                          False, False, True, False, True, False, False, False,
                          True, False, True, False]

    def test_mutate_global(self):
        class Stuff:
            pass
        g1 = Stuff(); g1.value = 1 
        g2 = Stuff(); g2.value = 2
        g3 = Stuff(); g3.value = 3
        g1.next = g3
        g2.next = g3
        g3.next = g3
        def do_things():
            g1.next = g1
            g2.next = g1
            g3.next = g2
            return g3.next.next.value
        fn = self.getcompiled(do_things)
        assert fn() == 1

    def test_float_ops(self):
        def f(x=float):
            return abs((-x) ** 3 + 1)
        fn = self.getcompiled(f)
        assert fn(-4.5) == 92.125
        assert fn(4.5) == 90.125

    def test_memoryerror(self):
        def f(i=int):
            lst = [0]*i
            lst[-1] = 5
            return lst[0]
        fn = self.getcompiled(f)
        assert fn(1) == 5
        assert fn(2) == 0
        py.test.raises(MemoryError, fn, sys.maxint//2+1)
        py.test.raises(MemoryError, fn, sys.maxint)

    def test_chr(self):
        def f(x=int):
            try:
                return 'Yes ' + chr(x)
            except ValueError:
                return 'No'
        fn = self.getcompiled(f)
        assert fn(65) == 'Yes A'
        assert fn(256) == 'No'
        assert fn(-1) == 'No'

    def test_unichr(self):
        def f(x=int):
            try:
                return ord(unichr(x))
            except ValueError:
                return -42
        fn = self.getcompiled(f)
        assert fn(65) == 65
        assert fn(-12) == -42
        assert fn(sys.maxint) == -42

    def test_list_indexerror(self):
        def f(i=int):
            lst = [123, 456]
            try:
                lst[i] = 789
            except IndexError:
                return 42
            return lst[0]
        fn = self.getcompiled(f)
        assert fn(1) == 123
        assert fn(2) == 42
        assert fn(-2) == 789
        assert fn(-3) == 42

    def test_long_long(self):
        def f(i=r_ulonglong):
            return 4*i
        fn = self.getcompiled(f, view=False)
        assert fn(sys.maxint) == 4*sys.maxint

        def g(i=r_longlong):
            return 4*i
        gn = self.getcompiled(g, view=False)
        assert gn(sys.maxint) == 4*sys.maxint

    def test_specializing_int_functions(self):
        def f(i):
            return i + 1
        f._annspecialcase_ = "specialize:argtype(0)"
        def g(n=int):
            if n > 0:
                return f(r_longlong(0))
            else:
                return f(0)

        fn = self.getcompiled(g)
        assert g(0) == 1
        assert g(1) == 1

    def test_downcast_int(self):
        def f(i=r_longlong):
            return int(i)
        fn = self.getcompiled(f)
        assert fn(0) == 0

    def test_function_ptr(self):
        def f1():
            return 1
        def f2():
            return 2
        def g(i=int):
            if i:
                f = f1
            else:
                f = f2
            return f()
        fn = self.getcompiled(g)
        assert fn(0) == 2
        assert fn(1) == 1

    def test_call_five(self):
        # --  the result of call_five() isn't a real list, but an rlist
        #     that can't be converted to a PyListObject
        def wrapper():
            lst = snippet.call_five()
            return len(lst), lst[0]
        call_five = self.getcompiled(wrapper)
        result = call_five()
        assert result == (1, 5)

    def test_get_set_del_slice(self):
        def get_set_del_nonneg_slice(): # no neg slices for now!
            l = [ord('a'), ord('b'), ord('c'), ord('d'), ord('e'), ord('f'), ord('g'), ord('h'), ord('i'), ord('j')]
            del l[:1]
            bound = len(l)-1
            if bound >= 0:
                del l[bound:]
            del l[2:4]
            #l[:1] = [3]
            #bound = len(l)-1
            #assert bound >= 0
            #l[bound:] = [9]    no setting slice into lists for now
            #l[2:4] = [8,11]
            l[0], l[-1], l[2], l[3] =3, 9, 8, 11

            list_3_c = l[:2]
            list_9 = l[5:]
            list_11_h = l[3:5]
            return (len(l), l[0], l[1], l[2], l[3], l[4], l[5],
                    len(list_3_c),  list_3_c[0],  list_3_c[1],
                    len(list_9),    list_9[0],
                    len(list_11_h), list_11_h[0], list_11_h[1])
        fn = self.getcompiled(get_set_del_nonneg_slice)
        result = fn()
        assert result == (6, 3, ord('c'), 8, 11, ord('h'), 9,
                          2, 3, ord('c'),
                          1, 9,
                          2, 11, ord('h'))

    def test_is(self):
        def testfn():
            l1 = []
            return l1 is l1
        fn = self.getcompiled(testfn)
        result = fn()
        assert result is True
        def testfn():
            l1 = []
            return l1 is None
        fn = self.getcompiled(testfn)
        result = fn()
        assert result is False

    def test_str_compare(self):
        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
            return s1[i] == s2[j]
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(6):
                res = fn(i, j)
                assert res is testfn(i, j)

        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
            return s1[i] != s2[j]
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(6):
                res = fn(i, j)
                assert res is testfn(i, j)
                
        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
            return s1[i] < s2[j]
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(6):
                res = fn(i, j)
                assert res is testfn(i, j)
                
        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
            return s1[i] <= s2[j]
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(6):
                res = fn(i, j)
                assert res is testfn(i, j)
                
        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
            return s1[i] > s2[j]
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(6):
                res = fn(i, j)
                assert res is testfn(i, j)
                
        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'twos', 'foobar']
            return s1[i] >= s2[j]
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(6):
                res = fn(i, j)
                assert res is testfn(i, j)
                
    def test_str_methods(self):
        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'ne', 'e', 'twos', 'foobar', 'fortytwo']
            return s1[i].startswith(s2[j])
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(9):
                res = fn(i, j)
                assert res is testfn(i, j)
        def testfn(i=int, j=int):
            s1 = ['one', 'two']
            s2 = ['one', 'two', 'o', 'on', 'ne', 'e', 'twos', 'foobar', 'fortytwo']
            return s1[i].endswith(s2[j])
        fn = self.getcompiled(testfn)
        for i in range(2):
            for j in range(9):
                res = fn(i, j)
                assert res is testfn(i, j)

    def test_str_join(self):
        def testfn(i=int, j=int):
            s1 = [ '', ',', ' and ']
            s2 = [ [], ['foo'], ['bar', 'baz', 'bazz']]
            return s1[i].join(s2[j])
        fn = self.getcompiled(testfn)
        for i in range(3):
            for j in range(3):
                res = fn(i, j)
                assert res == fn(i, j)
    
    def test_unichr_eq(self):
        l = list(u'Hello world')
        def f(i=int,j=int):
            return l[i] == l[j]
        fn = self.getcompiled(f)
        for i in range(len(l)):
            for j in range(len(l)):
                res = fn(i,j)
                assert res == f(i,j) 
    
    def test_unichr_ne(self):
        l = list(u'Hello world')
        def f(i=int,j=int):
            return l[i] != l[j]
        fn = self.getcompiled(f)
        for i in range(len(l)):
            for j in range(len(l)):
                res = fn(i,j)
                assert res == f(i,j)

    def test_unichr_ord(self):
        l = list(u'Hello world')
        def f(i=int):
            return ord(l[i]) 
        fn = self.getcompiled(f)
        for i in range(len(l)):
            res = fn(i)
            assert res == f(i)

    def test_unichr_unichr(self):
        l = list(u'Hello world')
        def f(i=int, j=int):
            return l[i] == unichr(j)
        fn = self.getcompiled(f)
        for i in range(len(l)):
            for j in range(len(l)):
                res = fn(i, ord(l[j]))
                assert res == f(i, ord(l[j]))

    def test_slice_long(self):
        "the parent's test_slice_long() makes no sense here"

    def test_int_overflow(self):
        fn = self.getcompiled(snippet.add_func)
        raises(OverflowError, fn, sys.maxint)

    def test_int_floordiv_ovf_zer(self):
        fn = self.getcompiled(snippet.div_func)
        raises(OverflowError, fn, -1)
        raises(ZeroDivisionError, fn, 0)

    def test_int_mul_ovf(self):
        fn = self.getcompiled(snippet.mul_func)
        for y in range(-5, 5):
            for x in range(-5, 5):
                assert fn(x, y) == snippet.mul_func(x, y)
        n = sys.maxint / 4
        assert fn(n, 3) == snippet.mul_func(n, 3)
        assert fn(n, 4) == snippet.mul_func(n, 4)
        raises(OverflowError, fn, n, 5)

    def test_int_mod_ovf_zer(self):
        fn = self.getcompiled(snippet.mod_func)
        raises(OverflowError, fn, -1)
        raises(ZeroDivisionError, fn, 0)

    def test_int_rshift_val(self):
        fn = self.getcompiled(snippet.rshift_func)
        raises(ValueError, fn, -1)

    def test_int_lshift_ovf_val(self):
        fn = self.getcompiled(snippet.lshift_func)
        raises(ValueError, fn, -1)
        raises(OverflowError, fn, 1)

    def test_int_unary_ovf(self):
        fn = self.getcompiled(snippet.unary_func)
        for i in range(-3,3):
            assert fn(i) == (-(i), abs(i-1))
        raises (OverflowError, fn, -sys.maxint-1)
        raises (OverflowError, fn, -sys.maxint)

    # floats 
    def test_float_operations(self): 
        import math
        def func(x=float, y=float): 
            z = x + y / 2.1 * x 
            z = math.fmod(z, 60.0)
            z = pow(z, 2)
            z = -z
            return int(z) 

        fn = self.getcompiled(func)
        assert fn(5.0, 6.0) == func(5.0, 6.0) 

    def test_rpbc_bound_method_static_call(self):
        class R:
            def meth(self):
                return 0
        r = R()
        m = r.meth
        def fn():
            return m()
        res = self.getcompiled(fn)()
        assert res == 0

    def test_constant_return_disagreement(self):
        class R:
            def meth(self):
                return 0
        r = R()
        def fn():
            return r.meth()
        res = self.getcompiled(fn)()
        assert res == 0


    def test_stringformatting(self):
        def fn(i=int):
            return "you said %d, you did"%i
        f = self.getcompiled(fn)
        assert f(1) == fn(1)

    def test_int2str(self):
        def fn(i=int):
            return str(i)
        f = self.getcompiled(fn)
        assert f(1) == fn(1)

    def test_float2str(self):
        def fn(i=float):
            return str(i)
        f = self.getcompiled(fn)
        res = f(1.0)
        assert type(res) is str and float(res) == 1.0
        
    def test_uint_arith(self):
        def fn(i=r_uint):
            try:
                return ~(i*(i+1))/(i-1)
            except ZeroDivisionError:
                return r_uint(91872331)
        f = self.getcompiled(fn)
        for value in range(15):
            i = r_uint(value)
            assert f(i) == fn(i)

    def test_ord_returns_a_positive(self):
        def fn(i=int):
            return ord(chr(i))
        f = self.getcompiled(fn)
        assert f(255) == 255

    def test_hash_preservation(self):
        class C:
            pass
        class D(C):
            pass
        c = C()
        d = D()
        def fn():
            d2 = D()
            # xxx check for this CPython peculiarity for now:
            x = (hash(d2) & sys.maxint) == (id(d2) & sys.maxint)
            return x, hash(c)+hash(d)
        
        f = self.getcompiled(fn)

        res = f()

        from pypy.rpython.rarithmetic import intmask
        
        assert res[0] == True
        assert res[1] == intmask(hash(c)+hash(d))

    def test_list_basic_ops(self):
        def list_basic_ops(i=int, j=int):
            l = [1,2,3]
            l.insert(0, 42)
            del l[1]
            l.append(i)
            listlen = len(l)
            l.extend(l) 
            del l[listlen:]
            l += [5,6] 
            l[1] = i
            return l[j]
        f = self.getcompiled(list_basic_ops)
        for i in range(6): 
            for j in range(6): 
                assert f(i,j) == list_basic_ops(i,j)

    def test_range2list(self):
        def fn():
            r = range(10, 37, 4)
            r.reverse()
            return r[0]
        f = self.getcompiled(fn)
        assert f() == fn()

    def test_range_idx(self):
        def fn(idx=int):
            r = range(10, 37, 4)
            try:
                return r[idx]
            except: raise
        f = self.getcompiled(fn)
        assert f(0) == fn(0)
        assert f(-1) == fn(-1)
        raises(IndexError, f, 42)

    def test_range_step(self):
        def fn(step=int):
            r = range(10, 37, step)
            # we always raise on step = 0
            return r[-2]
        f = self.getcompiled(fn)#, view=True)
        assert f(1) == fn(1)
        assert f(3) == fn(3)
        raises(ValueError, f, 0)

    def test_range_iter(self):
        def fn(start=int, stop=int, step=int):
            res = 0
            if step == 0:
                if stop >= start:
                    r = range(start, stop, 1)
                else:
                    r = range(start, stop, -1)
            else:
                r = range(start, stop, step)
            for i in r:
                res = res * 51 + i
            return res
        f = self.getcompiled(fn)
        for args in [2, 7, 0], [7, 2, 0], [10, 50, 7], [50, -10, -3]:
            assert f(*args) == intmask(fn(*args))

    def test_recursion_detection(self):
        def f(n=int, accum=int):
            if n == 0:
                return accum
            else:
                return f(n-1, accum*n)
        fn = self.getcompiled(f)
        assert fn(7, 1) == 5040
        assert fn(7, 1) == 5040    # detection must work several times, too
        assert fn(7, 1) == 5040
        py.test.raises(RuntimeError, fn, -1, 0)

    def test_list_len_is_true(self):

        class X(object):
            pass
        class A(object):
            def __init__(self):
                self.l = []

            def append_to_list(self, e):
                self.l.append(e)

            def check_list_is_true(self):
                did_loop = 0
                while self.l:
                    did_loop = 1
                    if len(self.l):
                        break
                return did_loop
            
        a1 = A()
        def f():
            for ii in range(1):
                a1.append_to_list(X())
            return a1.check_list_is_true()
        fn = self.getcompiled(f)
        assert fn() == 1

    def test_infinite_recursion(self):
        def f(x):
            if x:
                return f(x)
            return 1
        def g(x=int):
            try:
                f(x)
            except RuntimeError:
                return 42
            return 1
        fn = self.getcompiled(g)
        assert fn(0) == 1
        assert fn(1) == 42

    def test_r_dict_exceptions(self):
        from pypy.rpython.objectmodel import r_dict
        
        def raising_hash(obj):
            if obj.startswith("bla"):
                raise TypeError
            return 1
        def eq(obj1, obj2):
            return obj1 is obj2
        def f():
            d1 = r_dict(eq, raising_hash)
            d1['xxx'] = 1
            try:
                x = d1["blabla"]
            except Exception:
                return 42
            return x
        fn = self.getcompiled(f)    
        res = fn()
        assert res == 42

        def f():
            d1 = r_dict(eq, raising_hash)
            d1['xxx'] = 1
            try:
                x = d1["blabla"]
            except TypeError:
                return 42
            return x
        fn = self.getcompiled(f)    
        res = fn()
        assert res == 42    

        def f():
            d1 = r_dict(eq, raising_hash)
            d1['xxx'] = 1
            try:
                d1["blabla"] = 2
            except TypeError:
                return 42
            return 0
        fn = self.getcompiled(f)    
        res = fn()
        assert res == 42    

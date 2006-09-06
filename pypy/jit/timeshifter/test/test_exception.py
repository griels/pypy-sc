import py
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.llinterp import LLException
from pypy.jit.timeshifter.test.test_timeshift import TimeshiftingTests
from pypy.jit.timeshifter.test.test_timeshift import P_NOVIRTUAL
from pypy.jit.timeshifter.test.test_vlist import P_OOPSPEC


class TestException(TimeshiftingTests):

    def test_exception_check_melts_away(self):
        def ll_two(x):
            if x == 0:
                raise ValueError
            return x-1
        def ll_function(y):
            return ll_two(y) + 40

        res = self.timeshift(ll_function, [3], [0], policy=P_NOVIRTUAL)
        assert res == 42
        self.check_insns({})

    def test_propagate_exception(self):
        S = lltype.Struct('S', ('flag', lltype.Signed))
        s = lltype.malloc(S, immortal=True)
        def ll_two(x):
            if x == 0:
                raise ValueError
            return x+7
        def ll_function(y):
            res = ll_two(y)
            s.flag = 1
            return res

        s.flag = 0
        res = self.timeshift(ll_function, [0], [], policy=P_NOVIRTUAL)
        assert res == -1
        assert s.flag == 0

        s.flag = 0
        res = self.timeshift(ll_function, [0], [0], policy=P_NOVIRTUAL)
        assert res == -1
        assert s.flag == 0

        s.flag = 0
        res = self.timeshift(ll_function, [17], [0], policy=P_NOVIRTUAL)
        assert res == 24
        assert s.flag == 1
        self.check_insns({'setfield': 1})

    def test_catch(self):
        def ll_two(x):
            if x == 0:
                raise ValueError
            return x+7
        def ll_function(y):
            try:
                return ll_two(y)
            except ValueError:
                return 42

        res = self.timeshift(ll_function, [0], [], policy=P_NOVIRTUAL)
        assert res == 42

        res = self.timeshift(ll_function, [0], [0], policy=P_NOVIRTUAL)
        assert res == 42

        res = self.timeshift(ll_function, [17], [0], policy=P_NOVIRTUAL)
        assert res == 24
        self.check_insns({})

    def test_catch_from_outside(self):
        def ll_function(x):
            lst = [5]
            if x:
                lst.append(x)
            # 'lst' is forced at this point
            try:
                return lst[1] * 2   # direct_call to ll_getitem
            except IndexError:
                return -11

        res = self.timeshift(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == -11

        res = self.timeshift(ll_function, [0], [0], policy=P_OOPSPEC)
        assert res == -11

        res = self.timeshift(ll_function, [17], [0], policy=P_OOPSPEC)
        assert res == 34

    def test_exception_from_virtual(self):
        py.test.skip("in-progress... regress... sidewaysgress")
        def ll_function(n):
            lst = []
            lst.append(5)
            try:
                return lst[n]   # direct_call to ll_getitem
            except IndexError:
                return -11

        res = self.timeshift(ll_function, [2], [0], policy=P_OOPSPEC)
        assert res == -11

        res = self.timeshift(ll_function, [0], [0], policy=P_OOPSPEC)
        assert res == 5

        # the next case degenerates anyway
        res = self.timeshift(ll_function, [2], [], policy=P_OOPSPEC)
        assert res == -11
